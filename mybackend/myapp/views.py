# D:\bkgg\mybackend\myapp\views.py
# --- 保持所有原始導入 ---
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateformat import format as format_date
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Prefetch, Max, F
from django.db import transaction
from django.views.decorators.http import require_POST, require_GET
from django.template.loader import render_to_string
from .models import (
    Animal, Hall, Review, PendingAppointment, Note, Announcement, StoryReview, WeeklySchedule
)
import traceback
import html
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.contrib import messages
# --- *** 導入 *修改後* 的表單 *** ---
from .forms import MergeTransferForm
# --- *** ---

logger = logging.getLogger(__name__)

try:
    from schedule_parser.models import DailySchedule
    SCHEDULE_PARSER_ENABLED = True
except ImportError:
    print("WARNING: schedule_parser app or DailySchedule model not found. Daily schedule features will be disabled.")
    SCHEDULE_PARSER_ENABLED = False
    DailySchedule = None

# --- render_animal_rows (縮排已檢查) ---
def render_animal_rows(request, animals_qs, fetch_daily_slots=False):
    animal_daily_slots = {}
    animal_ids_on_page = [a.id for a in animals_qs]
    if fetch_daily_slots and SCHEDULE_PARSER_ENABLED and DailySchedule is not None and animal_ids_on_page:
        try:
            daily_schedules_qs = DailySchedule.objects.filter(
                animal_id__in=animal_ids_on_page
            ).values('animal_id', 'time_slots')
            for schedule in daily_schedules_qs:
                animal_daily_slots[schedule['animal_id']] = schedule['time_slots']
        except Exception as slot_err:
            print(f"    !!! Error fetching daily slots inside render_animal_rows: {slot_err}")
            traceback.print_exc()

    pending_ids = set(); notes_by_animal = {}
    if request.user.is_authenticated and animal_ids_on_page:
        try:
            pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user, animal_id__in=animal_ids_on_page))
            notes_qs = Note.objects.filter(user=request.user, animal_id__in=animal_ids_on_page)
            notes_by_animal = {str(note.animal_id): note for note in notes_qs}
        except Exception as e:
            print(f"Error fetching pending/notes: {e}")

    rendered_rows_html_list = []
    for animal_instance in animals_qs:
        review_count = getattr(animal_instance, 'approved_review_count', None)
        if review_count is None:
            try:
                review_count = Review.objects.filter(animal=animal_instance, approved=True).count()
            except Exception as count_err:
                review_count = 0

        animal_id_str = str(animal_instance.id)
        today_slots_for_template = animal_daily_slots.get(animal_instance.id)

        row_context = {
            'animal': animal_instance, 'user': request.user,
            'today_slots': today_slots_for_template,
            'is_pending': animal_id_str in pending_ids,
            'note': notes_by_animal.get(animal_id_str),
            'review_count': review_count,
        }
        try:
            rendered_html = render_to_string('myapp/partials/_animal_table_rows.html', row_context, request=request)
            rendered_rows_html_list.append(rendered_html)
        except Exception as render_err:
            print(f"!!! Error rendering partial (animal_rows) for {animal_instance.id}: {render_err} !!!"); traceback.print_exc()
            logger.error(f"Error rendering row for animal {animal_instance.id}", exc_info=True)
            rendered_rows_html_list.append(f'<tr><td colspan="5">渲染錯誤: {animal_instance.name}</td></tr>')

    return "".join(rendered_rows_html_list)

# --- Home View (縮排已檢查) ---
def home(request):
    is_ajax_request = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    fetch_type = request.GET.get('fetch')
    is_daily_schedule_ajax = is_ajax_request and fetch_type == 'daily_schedule'

    if is_daily_schedule_ajax:
        hall_id = request.GET.get('hall_id')
        if not hall_id: return JsonResponse({'error': '請求缺少館別 ID (hall_id)'}, status=400)
        try:
            hall_id_int = int(hall_id); selected_hall = get_object_or_404(Hall, id=hall_id_int, is_active=True)
        except (ValueError, TypeError):
            return JsonResponse({'error': '無效的館別 ID 格式'}, status=400)
        except Http404:
            return JsonResponse({'table_html': '<tr class="empty-table-message"><td colspan="5">所選館別不存在或未啟用</td></tr>', 'first_animal': {}}, status=404)
        try:
            prefetch_animal = Prefetch(
                'animal',
                queryset=Animal.objects.select_related('hall').annotate(
                    approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
                )
            )
            daily_schedules_qs = DailySchedule.objects.filter(
                hall_id=hall_id_int
            ).prefetch_related(prefetch_animal).order_by('animal__order', 'animal__name')
            animals_for_render = [ds.animal for ds in daily_schedules_qs if ds.animal]
            table_html = render_animal_rows(request, animals_for_render, fetch_daily_slots=True)
            first_animal_data = {}
            if animals_for_render:
                first_animal_obj = animals_for_render[0]
                try:
                    first_animal_data = {
                        'photo_url': first_animal_obj.photo.url if first_animal_obj.photo else '',
                        'name': first_animal_obj.name or '',
                        'introduction': first_animal_obj.introduction or ''
                    }
                except Exception as e:
                    print(f"    Warning: Error getting first animal data: {e}")
            return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
        except Exception as e:
            print(f"    !!! Error during Daily Schedule AJAX processing: {e} !!!"); traceback.print_exc()
            logger.error("Error processing daily schedule AJAX", exc_info=True)
            error_html = f'<tr class="empty-table-message"><td colspan="5">載入班表時發生內部錯誤</td></tr>'
            return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)

    elif is_ajax_request:
        if fetch_type == 'pending': return ajax_get_pending_list(request)
        elif fetch_type == 'my_notes': return ajax_get_my_notes(request)
        elif fetch_type == 'latest_reviews': return ajax_get_latest_reviews(request)
        elif fetch_type == 'recommendations': return ajax_get_recommendations(request)
        else:
            print(f"    ERROR: Unknown fetch_type '{fetch_type}', returning 400.")
            return JsonResponse({'error': '未知的請求類型'}, status=400)

    else: # Full page render
        halls = Hall.objects.filter(is_active=True, is_visible=True).order_by('order', 'name')
        context = {'halls': halls, 'user': request.user}; initial_pending_count = 0
        if request.user.is_authenticated:
            try:
                initial_pending_count = PendingAppointment.objects.filter(user=request.user).count()
            except Exception as e:
                print(f"Error fetching initial pending count: {e}")
        context['pending_count'] = initial_pending_count
        try:
            context['announcement'] = Announcement.objects.filter(is_active=True).order_by('-created_at').first()
        except Exception as e:
            print(f"Error fetching announcement: {e}"); context['announcement'] = None
        try:
            first_animal_for_promo = Animal.objects.filter(is_active=True, photo__isnull=False).exclude(photo='').filter(Q(hall__isnull=True) | Q(hall__is_active=True)).order_by('?').first()
            context['promo_photo_url'] = first_animal_for_promo.photo.url if first_animal_for_promo else None
            context['promo_animal_name'] = first_animal_for_promo.name if first_animal_for_promo else None
        except Exception as e:
            print(f"Error fetching promo photo: {e}"); context['promo_photo_url'] = None; context['promo_animal_name'] = None
        login_error = request.session.pop('login_error', None);
        if login_error: context['login_error'] = login_error
        context['selected_hall_id'] = 'all'
        template_path = 'myapp/index.html'
        try:
            return render(request, template_path, context)
        except Exception as e:
            print(f"    !!! Error rendering {template_path}: {e} !!!"); traceback.print_exc()
            logger.error(f"Error rendering template {template_path}", exc_info=True)
            raise

# --- AJAX Views (Pending, Notes, Reviews, Recs - 縮排已檢查) ---
@login_required
@require_GET
def ajax_get_pending_list(request):
    try:
        pending_appointments_qs = PendingAppointment.objects.filter(user=request.user).select_related('animal', 'animal__hall').order_by('-added_at')
        animal_ids = list(pending_appointments_qs.values_list('animal_id', flat=True))
        animals_qs = Animal.objects.filter(id__in=animal_ids).filter(Q(is_active=True) & (Q(hall__isnull=True) | Q(hall__is_active=True))).annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True)))
        animals_dict = {a.id: a for a in animals_qs}
        animals_list_ordered = [animals_dict.get(pa.animal_id) for pa in pending_appointments_qs if pa.animal_id in animals_dict]
        table_html = render_animal_rows(request, animals_list_ordered, fetch_daily_slots=True)
        first_animal_data = {}
        if animals_list_ordered:
            first_animal = animals_list_ordered[0]
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '', 'name': first_animal.name or '', 'introduction': first_animal.introduction or '' }
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_pending_list: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching pending list", exc_info=True)
        return JsonResponse({'error': '無法載入待約清單'}, status=500)

@login_required
@require_GET
def ajax_get_my_notes(request):
    hall_id = request.GET.get('hall_id'); selected_hall_id = hall_id or 'all'
    try:
        notes_base_qs = Note.objects.filter(user=request.user).filter(Q(animal__is_active=True) & (Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True))).select_related('animal', 'animal__hall')
        if selected_hall_id != "all":
            try:
                hall_id_int = int(selected_hall_id)
                notes_qs = notes_base_qs.filter(animal__hall_id=hall_id_int)
            except (ValueError, TypeError):
                print(f"Error: Invalid hall_id '{selected_hall_id}' received for notes.")
                return JsonResponse({'error': '無效的館別 ID 格式'}, status=400)
        else:
            notes_qs = notes_base_qs.all()
        notes_qs = notes_qs.order_by('-updated_at')
        animal_ids = list(notes_qs.values_list('animal_id', flat=True)); animals_list_ordered = []
        if animal_ids:
            animals_qs = Animal.objects.filter(id__in=animal_ids).annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True)))
            animals_dict = {a.id: a for a in animals_qs}
            animals_list_ordered = [animals_dict.get(note.animal_id) for note in notes_qs if note.animal_id in animals_dict]
        table_html = render_animal_rows(request, animals_list_ordered, fetch_daily_slots=True)
        first_animal_data = {}
        if animals_list_ordered:
            first_animal = animals_list_ordered[0]
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '','name': first_animal.name or '','introduction': first_animal.introduction or ''}
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_my_notes: {e} !!!"); traceback.print_exc()
        logger.error(f"Error fetching my notes (Hall: {selected_hall_id})", exc_info=True)
        return JsonResponse({'error': f'無法載入我的筆記'}, status=500)

@require_GET
def ajax_get_latest_reviews(request):
    try:
        latest_reviewed_animals_qs = Animal.objects.filter(is_active=True).filter(
            Q(hall__isnull=True) | Q(hall__is_active=True)).annotate(
            latest_review_time=Max('reviews__created_at', filter=Q(reviews__approved=True)), approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        ).filter(latest_review_time__isnull=False).select_related('hall').order_by('-latest_review_time')[:20]
        table_html = render_animal_rows(request, latest_reviewed_animals_qs, fetch_daily_slots=True)
        first_animal_data = {}
        if latest_reviewed_animals_qs.exists():
            first_animal = latest_reviewed_animals_qs.first()
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '','name': first_animal.name or '','introduction': first_animal.introduction or ''}
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_latest_reviews: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching latest reviews", exc_info=True)
        return JsonResponse({'error': '無法載入最新心得'}, status=500)

@require_GET
def ajax_get_recommendations(request):
    try:
        recommended_animals_qs = Animal.objects.filter(is_active=True, is_recommended=True).filter(
            Q(hall__isnull=True) | Q(hall__is_active=True)).select_related('hall').annotate(
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True))).order_by('hall__order', 'order', 'name')
        table_html = render_animal_rows(request, recommended_animals_qs, fetch_daily_slots=True)
        first_animal_data = {}
        if recommended_animals_qs.exists():
            first_animal = recommended_animals_qs.first()
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '','name': first_animal.name or '','introduction': first_animal.introduction or ''}
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_recommendations: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching recommendations", exc_info=True)
        return JsonResponse({'error': '無法載入每日推薦'}, status=500)

# --- User Authentication Views (縮排已檢查) ---
def user_login(request):
    if request.method == "POST":
        username = request.POST.get('username', '').strip(); password = request.POST.get('password', '')
        if not username or not password: request.session['login_error'] = '請輸入帳號和密碼'; return redirect('myapp:home')
        user = authenticate(request, username=username, password=password)
        if user is not None: login(request, user); request.session.pop('login_error', None); print(f"User '{username}' logged in."); return redirect('myapp:home')
        else: print(f"Login failed for '{username}'."); request.session['login_error'] = '帳號或密碼錯誤'; return redirect('myapp:home')
    return redirect('myapp:home')

@require_POST
@login_required
def user_logout(request):
    user_display = request.user.username if request.user.is_authenticated else "N/A"; logout(request)
    print(f"User '{user_display}' logged out."); return redirect('myapp:home')

# --- Add Story Review View (縮排已檢查) ---
@login_required
@require_POST
def add_story_review(request):
    animal_id = request.POST.get("animal_id"); user = request.user
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    try:
        animal = get_object_or_404(Animal, id=animal_id)
    except Http404:
        return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    face_list = request.POST.getlist("face"); temperament_list = request.POST.getlist("temperament"); scale_list = request.POST.getlist("scale"); content = request.POST.get("content", "").strip(); age_str = request.POST.get("age"); cup_size_value = request.POST.get("cup_size",""); errors = {}
    if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
    if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
    if not content: errors['content'] = "心得內容不能為空"
    age = None
    if age_str:
        try:
            age = int(age_str); assert age > 0
        except (ValueError, TypeError, AssertionError):
            errors['age'] = "年紀必須是有效的正數"
    if errors:
        error_message = "輸入無效: " + "; ".join([f"{k}: {v}" for k, v in errors.items()])
        return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)
    try:
        new_story = StoryReview.objects.create(animal=animal, user=user, age=age, looks=request.POST.get("looks") or None, face=','.join(face_list), temperament=','.join(temperament_list), physique=request.POST.get("physique") or None, cup=request.POST.get("cup") or None, cup_size=cup_size_value or None, skin_texture=request.POST.get("skin_texture") or None, skin_color=request.POST.get("skin_color") or None, music=request.POST.get("music") or None, music_price=request.POST.get("music_price") or None, sports=request.POST.get("sports") or None, sports_price=request.POST.get("sports_price") or None, scale=','.join(scale_list), content=content, approved=False, approved_at=None, expires_at=None )
        print(f"Story Review {new_story.id} created for {animal_id}. Needs approval.")
        return JsonResponse({"success": True, "message": "限時動態心得已提交，待審核後將顯示"})
    except Exception as e:
        print(f"Error creating story review: {e}"); traceback.print_exc()
        logger.error("Error creating story review", exc_info=True)
        return JsonResponse({"success": False, "error": "儲存限時動態心得時發生內部錯誤"}, status=500)

# --- Add Regular Review View (縮排已檢查) ---
@login_required
def add_review(request):
    if request.method == "POST":
        animal_id = request.POST.get("animal_id"); user = request.user
        if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
        try:
            animal = get_object_or_404(Animal, id=animal_id)
        except Http404:
            return JsonResponse({"success": False, "error": "找不到指定的動物"}, status=404)
        except (ValueError, TypeError):
            return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
        face_list = request.POST.getlist("face"); temperament_list = request.POST.getlist("temperament"); scale_list = request.POST.getlist("scale"); content = request.POST.get("content", "").strip(); age_str = request.POST.get("age"); cup_size_value = request.POST.get("cup_size",""); errors = {}
        if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
        if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
        if not content: errors['content'] = "心得內容不能為空"
        age = None
        if age_str:
            try:
                age = int(age_str); assert age > 0
            except (ValueError, TypeError, AssertionError):
                errors['age'] = "年紀必須是有效的正數"
        if errors:
            error_message = "輸入無效: " + "; ".join([f"{k}: {v}" for k, v in errors.items()])
            return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)
        try:
            new_review = Review.objects.create(animal=animal, user=user, age=age, looks=request.POST.get("looks") or None, face=','.join(face_list), temperament=','.join(temperament_list), physique=request.POST.get("physique") or None, cup=request.POST.get("cup") or None, cup_size=cup_size_value or None, skin_texture=request.POST.get("skin_texture") or None, skin_color=request.POST.get("skin_color") or None, music=request.POST.get("music") or None, music_price=request.POST.get("music_price") or None, sports=request.POST.get("sports") or None, sports_price=request.POST.get("sports_price") or None, scale=','.join(scale_list), content=content, approved=False)
            print(f"Review {new_review.id} created for {animal_id}.")
            return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
        except Exception as e:
            print(f"Error creating review: {e}"); traceback.print_exc()
            logger.error("Error creating regular review", exc_info=True)
            return JsonResponse({"success": False, "error": "儲存心得時發生內部錯誤"}, status=500)

    elif request.method == "GET":
        animal_id = request.GET.get("animal_id")
        if not animal_id: return JsonResponse({"error": "缺少 animal_id"}, status=400)
        try:
            animal = get_object_or_404(Animal.objects.filter(Q(is_active=True) & (Q(hall__isnull=True) | Q(hall__is_active=True))), id=animal_id)
        except Http404:
            return JsonResponse({"error": "找不到動物或動物未啟用"}, status=404)
        except (ValueError, TypeError):
            return JsonResponse({"error": "無效的 animal_id"}, status=400)
        reviews_qs = Review.objects.filter(animal=animal, approved=True).select_related('user').order_by("-created_at")
        user_ids = list(reviews_qs.values_list('user_id', flat=True).distinct()); user_review_counts = {}
        if user_ids:
            try:
                counts_query = Review.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(totalCount=Count('id'))
                user_review_counts = {item['user_id']: item['totalCount'] for item in counts_query}
            except Exception as count_err:
                print(f"Error fetching user review counts: {count_err}")
        data = []
        for r in reviews_qs:
            user_display_name = "匿名"; formatted_date = ""
            if hasattr(r, 'user') and r.user:
                user_display_name = r.user.first_name or r.user.username
            if r.created_at:
                try:
                    formatted_date = timezone.localtime(r.created_at).strftime("%Y-%m-%d")
                except Exception as date_err:
                    print(f"Error formatting date: {date_err}"); formatted_date = "日期錯誤"
            data.append({"id": r.id, "user": user_display_name, "totalCount": user_review_counts.get(r.user_id, 0), "age": r.age, "looks": r.looks, "face": r.face, "temperament": r.temperament, "physique": r.physique, "cup": r.cup, "cup_size": r.cup_size, "skin_texture": r.skin_texture, "skin_color": r.skin_color, "music": r.music, "music_price": r.music_price, "sports": r.sports, "sports_price": r.sports_price, "scale": r.scale, "content": r.content, "created_at": formatted_date})
        return JsonResponse({"reviews": data})
    return JsonResponse({"error": "請求方法不支援"}, status=405)

# --- Pending Appointment Handling Views (縮排已檢查) ---
@require_POST
@login_required
def add_pending_appointment(request):
    animal_id = request.POST.get("animal_id"); user = request.user
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    try:
        animal = get_object_or_404(Animal, id=animal_id)
    except Http404:
        return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    try: # Outer try
        obj, created = PendingAppointment.objects.get_or_create(user=user, animal=animal)
        pending_count = PendingAppointment.objects.filter(user=user).count()
        message = f"{animal.name} 已加入待約清單" if created else f"{animal.name} 已在待約清單中"
        return JsonResponse({"success": True, "message": message, "pending_count": pending_count})
    except Exception as e: # <<<<< Except corresponding to the outer try (Line 859 approx.)
        if 'violates unique constraint' in str(e) and 'myapp_pendingappointment' in str(e):
            pending_count = PendingAppointment.objects.filter(user=user).count()
            return JsonResponse({"success": False, "error": f"{animal.name} 已在待約清單中", "pending_count": pending_count}, status=409)
        print(f"Error add pending: {e}"); traceback.print_exc()
        logger.error("Error adding pending appointment", exc_info=True)
        pending_count = PendingAppointment.objects.filter(user=user).count()
        return JsonResponse({"success": False, "error": "加入待約時發生錯誤", "pending_count": pending_count}, status=500)

@require_POST
@login_required
def remove_pending(request):
    animal_id = request.POST.get("animal_id"); user = request.user
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    try:
        try:
            animal_id_int = int(animal_id)
        except (ValueError, TypeError):
            raise ValueError("無效的動物 ID 格式")
        deleted_count, _ = PendingAppointment.objects.filter(user=user, animal_id=animal_id_int).delete()
        pending_count = PendingAppointment.objects.filter(user=user).count()
        if deleted_count == 0:
            animal_exists = Animal.objects.filter(id=animal_id_int).exists()
            if not animal_exists:
                return JsonResponse({"success": False, "error": "找不到該動物", "pending_count": pending_count}, status=404)
            else:
                return JsonResponse({"success": False, "error": "該待約項目不存在", "pending_count": pending_count}, status=404)
        animal_name = Animal.objects.filter(id=animal_id_int).values_list('name', flat=True).first() or "該美容師"
        print(f"Pending removed {animal_id_int} by {user.username}. Count: {pending_count}")
        return JsonResponse({"success": True, "message": f"{animal_name} 待約項目已移除", "pending_count": pending_count, "animal_id": animal_id_int})
    except ValueError as ve:
        count = PendingAppointment.objects.filter(user=user).count()
        return JsonResponse({"success": False, "error": str(ve), "pending_count": count}, status=400)
    except Exception as e:
        print(f"Error remove pending: {e}"); traceback.print_exc()
        logger.error("Error removing pending appointment", exc_info=True)
        count = PendingAppointment.objects.filter(user=user).count()
        return JsonResponse({"success": False, "error": "移除待約時發生錯誤", "pending_count": count}, status=500)

# --- Note Handling Views (縮排已檢查) ---
@require_POST
@login_required
def add_note(request):
    animal_id = request.POST.get("animal_id"); content = request.POST.get("content", "").strip(); note_id = request.POST.get("note_id"); user = request.user
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)
    try:
        animal = get_object_or_404(Animal, id=animal_id)
    except Http404:
        return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    note = None; created = False
    try:
        if note_id:
            try:
                note = Note.objects.get(id=note_id, user=user, animal=animal)
                note.content = content
                note.save()
                created = False
            except Note.DoesNotExist:
                return JsonResponse({"success": False, "error": "找不到要更新的筆記"}, status=404)
        else:
            note, created = Note.objects.update_or_create(
                user=user,
                animal=animal,
                defaults={"content": content}
            )
        message = "筆記已新增" if created else "筆記已更新"
        return JsonResponse({"success": True, "message": message, "note_id": note.id, "note_content": note.content, "animal_id": animal.id})
    except Exception as e:
        if 'violates unique constraint' in str(e) and 'myapp_note' in str(e):
            return JsonResponse({"success": False, "error": "儲存筆記時發生衝突"}, status=409)
        print(f"Error add/update note: {e}"); traceback.print_exc()
        logger.error("Error adding/updating note", exc_info=True)
        return JsonResponse({"success": False, "error": "儲存筆記時發生錯誤"}, status=500)

@require_POST
@login_required
def delete_note(request):
    note_id = request.POST.get("note_id"); user = request.user
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    try:
        try:
            note_id_int = int(note_id)
        except (ValueError, TypeError):
            raise ValueError("無效的筆記 ID 格式")
        note = get_object_or_404(Note, id=note_id_int, user=user); animal_id = note.animal_id; deleted_count, _ = note.delete()
        if deleted_count == 0: return JsonResponse({"success": False, "error": "刪除失敗"})
        print(f"Note {note_id_int} deleted for {animal_id}."); return JsonResponse({"success": True, "message": "筆記已刪除", "animal_id": animal_id})
    except Http404:
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve:
        return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        print(f"Error deleting note: {e}"); traceback.print_exc()
        logger.error("Error deleting note", exc_info=True)
        return JsonResponse({"success": False, "error": "刪除筆記時發生錯誤"}, status=500)

@require_POST
@login_required
def update_note(request):
    note_id = request.POST.get("note_id"); content = request.POST.get("content", "").strip(); user = request.user
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)
    try:
        try:
            note_id_int = int(note_id)
        except (ValueError, TypeError):
            raise ValueError("無效的筆記 ID 格式")
        note = get_object_or_404(Note.objects.select_related('animal'), id=note_id_int, user=user); animal = note.animal
        note.content = content
        note.save()
        return JsonResponse({"success": True, "message": "筆記已更新", "note_id": note.id, "note_content": note.content, "animal_id": animal.id})
    except Http404:
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve:
        return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        print(f"Error updating note: {e}"); traceback.print_exc()
        logger.error("Error updating note", exc_info=True)
        return JsonResponse({"success": False, "error": "更新筆記時發生錯誤"}, status=500)

# --- AJAX Views (Stories, Schedule, HoF - 縮排已檢查) ---
@require_GET
def ajax_get_active_stories(request):
    try:
        now = timezone.now()
        active_stories_qs = StoryReview.objects.filter(Q(animal__is_active=True) & (Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True)), approved=True, expires_at__gt=now).select_related('animal', 'animal__hall', 'user').order_by('-approved_at')
        stories_data = [{'id': s.id, 'animal_id': s.animal_id, 'animal_name': s.animal.name, 'animal_photo_url': s.animal.photo.url if s.animal.photo else None, 'hall_name': s.animal.hall.name if s.animal.hall else '未知館別', 'user_name': s.user.first_name or s.user.username, 'remaining_time': s.remaining_time_display} for s in active_stories_qs]
        return JsonResponse({'stories': stories_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_active_stories: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching active stories", exc_info=True)
        return JsonResponse({'error': '無法載入限時動態'}, status=500)

@require_GET
def ajax_get_story_detail(request, story_id):
    try:
        story = get_object_or_404(StoryReview.objects.filter(Q(animal__is_active=True) & (Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True)), approved=True, expires_at__gt=timezone.now()).select_related('animal', 'animal__hall', 'user'), pk=story_id)
        animal = story.animal; user = story.user; approved_at_display = format_date(timezone.localtime(story.approved_at), 'Y-m-d H:i') if story.approved_at else ""
        story_data = {'id': story.id, 'animal_id': animal.id, 'animal_name': animal.name, 'animal_photo_url': animal.photo.url if animal.photo else None, 'hall_name': animal.hall.name if animal.hall else '未知館別', 'user_name': user.first_name or user.username, 'remaining_time': story.remaining_time_display, 'approved_at_display': approved_at_display, 'age': story.age, 'looks': story.looks, 'face': story.face, 'temperament': story.temperament, 'physique': story.physique, 'cup': story.cup, 'cup_size': story.cup_size, 'skin_texture': story.skin_texture, 'skin_color': story.skin_color, 'music': story.music, 'music_price': story.music_price, 'sports': story.sports, 'sports_price': story.sports_price, 'scale': story.scale, 'content': story.content}
        return JsonResponse({'success': True, 'story': story_data})
    except Http404:
        print(f"    Story {story_id} not found/inactive."); return JsonResponse({'success': False, 'error': '找不到動態'}, status=404)
    except Exception as e:
        print(f"!!! Error in ajax_get_story_detail for ID {story_id}: {e} !!!"); traceback.print_exc()
        logger.error(f"Error fetching story detail for ID {story_id}", exc_info=True)
        return JsonResponse({'success': False, 'error': '無法載入動態詳情'}, status=500)

@require_GET
def ajax_get_weekly_schedule(request):
    hall_id = request.GET.get('hall_id')
    if not hall_id: return JsonResponse({'success': False, 'error': '缺少館別 ID'}, status=400)
    try:
        hall_id_int = int(hall_id)
        hall = get_object_or_404(Hall, id=hall_id_int, is_active=True)
        hall_name = hall.name
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': '無效的館別 ID 格式'}, status=400)
    except Http404:
        try:
            hall_name = Hall.objects.get(id=hall_id_int).name
            print(f"    Hall {hall_id} inactive.")
            return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': hall_name, 'message': f'{hall_name} 未啟用'}, status=404)
        except Hall.DoesNotExist:
            hall_name = '此館別'
            print(f"    Hall {hall_id} does not exist.")
            return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': hall_name, 'message': f'{hall_name} 不存在'}, status=404)
        except Exception as inner_e:
            print(f"    Error fetching hall name after Http404: {inner_e}")
            logger.error(f"Error fetching hall name after Http404 for ID {hall_id_int}", exc_info=True)
            return JsonResponse({'success': False, 'error': '獲取館別信息時出錯'}, status=500)
    except Exception as e:
        print(f"!!! Error getting Hall: {e} !!!")
        traceback.print_exc()
        logger.error(f"Error getting Hall object for ID {hall_id}", exc_info=True)
        return JsonResponse({'success': False, 'error': '獲取館別信息時發生錯誤'}, status=500)
    try:
        schedules = WeeklySchedule.objects.filter(hall_id=hall_id_int).order_by('order')
        schedule_urls = [s.schedule_image.url for s in schedules if s.schedule_image]
        if schedule_urls:
            return JsonResponse({'success': True, 'schedule_urls': schedule_urls, 'hall_name': hall_name})
        else:
            print(f"    No images for Hall {hall_id}.")
            return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': hall_name, 'message': f'{hall_name} 未上傳班表圖片'})
    except Exception as e:
        print(f"!!! Error fetch weekly schedule: {e} !!!"); traceback.print_exc()
        logger.error(f"Error fetching weekly schedule for Hall ID {hall_id}", exc_info=True)
        return JsonResponse({'success': False, 'error': '載入每週班表出錯'}, status=500)


@require_GET
def ajax_get_hall_of_fame(request):
    try:
        top_users = Review.objects.filter(approved=True).values('user', 'user__username', 'user__first_name').annotate(review_count=Count('id')).order_by('-review_count')[:10]
        data = [{'rank': r+1, 'user_name': (d.get('user__first_name') or d.get('user__username') or f"用戶_{d.get('user','N/A')}") , 'review_count': d.get('review_count',0)} for r,d in enumerate(top_users)]
        return JsonResponse({'users': data})
    except Exception as e:
        print(f"!!! Error in ajax_get_hall_of_fame: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching Hall of Fame", exc_info=True)
        return JsonResponse({'error': '無法載入名人堂'}, status=500)


# ======================================================================
# --- *** 修改後的合併視圖 (極簡版：自動推斷目標館別和名字) *** ---
# ======================================================================
@staff_member_required
def merge_transfer_animal_view(request, animal_id):
    """
    處理合併美容師資料的中間頁面視圖 (簡化版)。
    GET: 顯示表單 (僅需選擇重複記錄)。
    POST: 處理表單提交，執行合併，目標館別和名字由重複記錄決定。
    """
    animal_original = get_object_or_404(Animal, pk=animal_id)
    print(f"--- merge_transfer_animal_view called for Animal ID: {animal_id} ({animal_original.name}) ---")

    form = None

    if request.method == 'POST':
        print("    Handling POST request...")
        form = MergeTransferForm(request.POST, request.FILES, animal_original=animal_original)

        if form.is_valid():
            duplicate_animal = form.cleaned_data.get('duplicate_animal')
            target_hall = duplicate_animal.hall
            new_name = duplicate_animal.name

            if not target_hall:
                logger.warning(f"Merge aborted: Duplicate animal {duplicate_animal.id} ({duplicate_animal.name}) has no assigned hall.")
                messages.error(request, f"合併失敗：選擇的重複記錄 '{duplicate_animal.name}' 沒有有效的館別。")
                context = _get_merge_view_context(request, animal_original, form)
                return render(request, 'admin/myapp/animal/merge_transfer_form.html', context)

            if Animal.objects.filter(
                hall=target_hall, name__iexact=new_name, is_active=True
            ).exclude(pk=animal_original.id).exclude(pk=duplicate_animal.id).exists():
                 logger.warning(f"Merge aborted: Another active animal named '{new_name}' already exists in target hall '{target_hall.name}'.")
                 messages.error(request, f"合併失敗：目標館別 '{target_hall.name}' 中已存在另一位名為 '{new_name}' 的啟用中美容師。請先處理該衝突。")
                 context = _get_merge_view_context(request, animal_original, form)
                 return render(request, 'admin/myapp/animal/merge_transfer_form.html', context)

            print(f"    Form valid. Processing merge...")
            print(f"      Merging duplicate ID {duplicate_animal.id} ({duplicate_animal.name})")
            print(f"      Into original ID {animal_original.id} ({animal_original.name})")
            print(f"      Inferred Target Hall: {target_hall.name}")
            print(f"      Inferred New Name: {new_name}")

            try: # Outer try for the whole merge process
                with transaction.atomic():
                    print(f"    Starting transaction for MERGE...")
                    log_prefix = f"[Merge Animal ID {animal_original.id}]"

                    # --- a. Apply data and tags ---
                    print(f"{log_prefix}   - Applying descriptive data and TAGS from duplicate...")
                    if duplicate_animal.introduction: animal_original.introduction = duplicate_animal.introduction
                    if duplicate_animal.photo:
                        if animal_original.photo and animal_original.photo.name != duplicate_animal.photo.name:
                            print(f"{log_prefix}     - Deleting old photo: {animal_original.photo.name}")
                            try:
                                animal_original.photo.delete(save=False)
                            except Exception as photo_delete_err:
                                print(f"{log_prefix}     - Warning: Error deleting old photo file: {photo_delete_err}")
                        if not animal_original.photo or (animal_original.photo and duplicate_animal.photo and animal_original.photo.name != duplicate_animal.photo.name):
                            animal_original.photo = duplicate_animal.photo
                            print(f"{log_prefix}     - Applied photo from duplicate.")
                    if duplicate_animal.fee is not None: animal_original.fee = duplicate_animal.fee
                    if duplicate_animal.height is not None: animal_original.height = duplicate_animal.height
                    if duplicate_animal.weight is not None: animal_original.weight = duplicate_animal.weight
                    if duplicate_animal.cup_size: animal_original.cup_size = duplicate_animal.cup_size
                    tag_fields_to_copy = [
                        'is_recommended', 'is_hidden_edition', 'is_exclusive',
                        'is_hot', 'is_newcomer'
                    ]
                    print(f"{log_prefix}     - Copying tags from duplicate: {tag_fields_to_copy}")
                    for field_name in tag_fields_to_copy:
                        if hasattr(animal_original, field_name) and hasattr(duplicate_animal, field_name):
                            duplicate_value = getattr(duplicate_animal, field_name)
                            original_value = getattr(animal_original, field_name)
                            if original_value != duplicate_value:
                                setattr(animal_original, field_name, duplicate_value)
                                print(f"{log_prefix}       - Applied tag '{field_name}' = {duplicate_value} from duplicate (original was {original_value}).")
                        else:
                            print(f"{log_prefix}       - Warning: Tag field '{field_name}' not found on both models, skipping.")

                    # --- b. Transfer related records ---
                    print(f"{log_prefix}   - Transferring related records (excluding DailySchedule initially)...")
                    models_to_transfer = [Review, StoryReview, Note, PendingAppointment]
                    for model_class in models_to_transfer:
                        model_name = model_class.__name__
                        try:
                            if hasattr(model_class, 'animal'):
                                if model_name == 'Note':
                                    print(f"{log_prefix}     - Special handling for {model_name}: Keep newer note based on updated_at.")
                                    original_notes_users = set(model_class.objects.filter(animal=animal_original).values_list('user_id', flat=True))
                                    duplicate_notes_users = set(model_class.objects.filter(animal=duplicate_animal).values_list('user_id', flat=True))
                                    conflicting_user_ids = original_notes_users.intersection(duplicate_notes_users)
                                    notes_kept_from_duplicate_count = 0; notes_deleted_from_duplicate_count = 0; notes_deleted_from_original_count = 0
                                    if conflicting_user_ids:
                                        print(f"{log_prefix}       - Found {len(conflicting_user_ids)} conflicts for {model_name}. Resolving...")
                                        for user_id in conflicting_user_ids:
                                            try:
                                                original_note = model_class.objects.get(animal=animal_original, user_id=user_id)
                                                duplicate_note = model_class.objects.get(animal=duplicate_animal, user_id=user_id)
                                                keep_original = True
                                                if hasattr(original_note, 'updated_at') and hasattr(duplicate_note, 'updated_at'):
                                                    if original_note.updated_at and duplicate_note.updated_at:
                                                        if duplicate_note.updated_at > original_note.updated_at: keep_original = False
                                                    elif not original_note.updated_at and duplicate_note.updated_at: keep_original = False
                                                if keep_original: duplicate_note.delete(); notes_deleted_from_duplicate_count += 1
                                                else: original_note.delete(); notes_deleted_from_original_count += 1; duplicate_note.animal = animal_original; duplicate_note.save(); notes_kept_from_duplicate_count += 1
                                            except model_class.DoesNotExist: pass
                                            except Exception as cr_err: print(f"{log_prefix} Error resolving {model_name} conflict for user {user_id}: {cr_err}"); raise cr_err
                                        print(f"{log_prefix}       - {model_name} Conflict resolution summary: Kept {notes_kept_from_duplicate_count}, deleted {notes_deleted_from_duplicate_count} (dup), deleted {notes_deleted_from_original_count} (orig).")
                                    else: print(f"{log_prefix}       - No user conflicts found for {model_name}.")
                                    remaining_update_qs = model_class.objects.filter(animal=duplicate_animal)
                                    remaining_update_count = remaining_update_qs.count()
                                    if remaining_update_count > 0: updated_count_bulk = remaining_update_qs.update(animal=animal_original); print(f"{log_prefix}     - {model_name} updated (remaining non-conflicting): {updated_count_bulk}")
                                    total_transferred_or_resolved = notes_kept_from_duplicate_count + remaining_update_count
                                    logger.info(f"{log_prefix} Transferred/resolved {total_transferred_or_resolved} {model_name} from {duplicate_animal.id} to {animal_original.id}.")
                                elif model_name == 'PendingAppointment':
                                    print(f"{log_prefix}     - Special handling for {model_name}: Keep newer PA based on added_at.")
                                    original_pa_users = set(model_class.objects.filter(animal=animal_original).values_list('user_id', flat=True))
                                    duplicate_pa_users = set(model_class.objects.filter(animal=duplicate_animal).values_list('user_id', flat=True))
                                    conflicting_pa_user_ids = original_pa_users.intersection(duplicate_pa_users)
                                    pa_kept_from_duplicate_count = 0; pa_deleted_from_duplicate_count = 0; pa_deleted_from_original_count = 0
                                    if conflicting_pa_user_ids:
                                        print(f"{log_prefix}       - Found {len(conflicting_pa_user_ids)} conflicts for {model_name}. Resolving...")
                                        for user_id in conflicting_pa_user_ids:
                                            try:
                                                original_pa = model_class.objects.get(animal=animal_original, user_id=user_id)
                                                duplicate_pa = model_class.objects.get(animal=duplicate_animal, user_id=user_id)
                                                keep_original = True
                                                if hasattr(original_pa, 'added_at') and hasattr(duplicate_pa, 'added_at'):
                                                    if original_pa.added_at and duplicate_pa.added_at:
                                                        if duplicate_pa.added_at > original_pa.added_at: keep_original = False
                                                    elif not original_pa.added_at and duplicate_pa.added_at: keep_original = False
                                                if keep_original: duplicate_pa.delete(); pa_deleted_from_duplicate_count += 1
                                                else: original_pa.delete(); pa_deleted_from_original_count += 1; duplicate_pa.animal = animal_original; duplicate_pa.save(); pa_kept_from_duplicate_count += 1
                                            except model_class.DoesNotExist: pass
                                            except Exception as cr_err: print(f"{log_prefix} Error resolving {model_name} conflict for user {user_id}: {cr_err}"); raise cr_err
                                        print(f"{log_prefix}       - {model_name} Conflict resolution summary: Kept {pa_kept_from_duplicate_count}, deleted {pa_deleted_from_duplicate_count} (dup), deleted {pa_deleted_from_original_count} (orig).")
                                    else: print(f"{log_prefix}       - No user conflicts found for {model_name}.")
                                    remaining_pa_qs = model_class.objects.filter(animal=duplicate_animal)
                                    remaining_pa_count = remaining_pa_qs.count()
                                    if remaining_pa_count > 0: updated_pa_bulk = remaining_pa_qs.update(animal=animal_original); print(f"{log_prefix}     - {model_name} updated (remaining non-conflicting): {updated_pa_bulk}")
                                    total_pa_resolved = pa_kept_from_duplicate_count + remaining_pa_count
                                    logger.info(f"{log_prefix} Transferred/resolved {total_pa_resolved} {model_name} from {duplicate_animal.id} to {animal_original.id}.")
                                else:
                                    generic_qs = model_class.objects.filter(animal=duplicate_animal)
                                    generic_count = generic_qs.count()
                                    if generic_count > 0:
                                        updated_count = generic_qs.update(animal=animal_original)
                                        print(f"{log_prefix}     - {model_name} updated (generic): {updated_count}")
                                        logger.info(f"{log_prefix} Transferred {updated_count} {model_name} from {duplicate_animal.id} to {animal_original.id}.")
                            else: print(f"{log_prefix}     - Skipping {model_name} (no 'animal' field).")
                        except Exception as transfer_err:
                            logger.error(f"{log_prefix} Error transferring {model_name} from {duplicate_animal.id}", exc_info=True)
                            raise transfer_err

                    # --- c. Handle DailySchedule ---
                    if SCHEDULE_PARSER_ENABLED and DailySchedule:
                        print(f"{log_prefix}   - Handling DailySchedule cleanup and transfer (MERGE)...")
                        try:
                            duplicate_schedules_qs = DailySchedule.objects.filter(animal=duplicate_animal)
                            original_schedule_in_target_hall = DailySchedule.objects.filter(animal=animal_original, hall=target_hall).first()
                            deleted_orig_wrong_hall, _ = DailySchedule.objects.filter(animal=animal_original).exclude(hall=target_hall).delete()
                            if deleted_orig_wrong_hall > 0:
                                print(f"{log_prefix}     - Cleaned up {deleted_orig_wrong_hall} pre-existing DailySchedule for original animal (ID {animal_original.id}) in incorrect halls.")
                                logger.info(f"{log_prefix} Cleaned up {deleted_orig_wrong_hall} pre-existing DailySchedule for original animal {animal_original.id} not in target hall {target_hall.id}")
                            if original_schedule_in_target_hall:
                                deleted_dup_count, _ = duplicate_schedules_qs.delete()
                                if deleted_dup_count > 0:
                                    print(f"{log_prefix}     - Discarded {deleted_dup_count} DailySchedule from duplicate because original already has one in target hall.")
                                    logger.info(f"{log_prefix} Discarded {deleted_dup_count} DailySchedule from duplicate {duplicate_animal.id} as original {animal_original.id} already has one in target hall {target_hall.id}")
                            else:
                                schedule_to_transfer = duplicate_schedules_qs.first()
                                if schedule_to_transfer:
                                    schedule_to_transfer.animal = animal_original
                                    schedule_to_transfer.hall = target_hall
                                    schedule_to_transfer.save()
                                    print(f"{log_prefix}     - Transferred DailySchedule (ID {schedule_to_transfer.id}) from duplicate to original in target hall.")
                                    logger.info(f"{log_prefix} Transferred DailySchedule {schedule_to_transfer.id} from duplicate {duplicate_animal.id} to original {animal_original.id} in target hall {target_hall.id}")
                                    deleted_other_dups, _ = duplicate_schedules_qs.exclude(pk=schedule_to_transfer.pk).delete()
                                    if deleted_other_dups > 0:
                                        print(f"{log_prefix}     - Deleted {deleted_other_dups} other redundant DailySchedule from duplicate.")
                                        logger.warning(f"{log_prefix} Deleted {deleted_other_dups} other redundant DailySchedule from duplicate {duplicate_animal.id}")
                                else:
                                    print(f"{log_prefix}     - No DailySchedule found for duplicate animal to transfer.")
                                    logger.info(f"{log_prefix} No DailySchedule found for duplicate {duplicate_animal.id} to transfer.")
                        except Exception as ds_err:
                            logger.error(f"{log_prefix} Error handling DailySchedule during merge", exc_info=True)
                            raise ds_err

                    # --- d. Merge aliases ---
                    print(f"{log_prefix}   - Merging aliases...")
                    original_aliases = animal_original.aliases if isinstance(animal_original.aliases, list) else []
                    duplicate_aliases = duplicate_animal.aliases if isinstance(duplicate_animal.aliases, list) else []
                    valid_original = [str(a).strip() for a in original_aliases if a is not None and str(a).strip()]
                    valid_duplicate = [str(a).strip() for a in duplicate_aliases if a is not None and str(a).strip()]
                    merged_aliases_set = set(valid_original + valid_duplicate)
                    if duplicate_animal.name not in merged_aliases_set: merged_aliases_set.add(duplicate_animal.name)
                    if duplicate_animal.hall:
                        dup_history_marker = f"{duplicate_animal.name}@{duplicate_animal.hall.name}"
                        if dup_history_marker not in merged_aliases_set: merged_aliases_set.add(dup_history_marker)
                    animal_original.aliases = list(merged_aliases_set)
                    print(f"{log_prefix}     - Aliases merged (pre-final update). Current set: {animal_original.aliases}")

                    # --- e. Update animal_original core info ---
                    print(f"{log_prefix} Updating final animal's core info (using inferred name and hall)...")
                    old_name = animal_original.name
                    old_hall = animal_original.hall

                    animal_original.hall = target_hall
                    animal_original.name = new_name
                    animal_original.is_active = True

                    current_aliases = animal_original.aliases if isinstance(animal_original.aliases, list) else []
                    current_aliases_set = set(current_aliases)
                    if old_name != new_name and old_name not in current_aliases_set:
                        current_aliases_set.add(old_name)
                        print(f"{log_prefix}   - Added old name '{old_name}' to aliases.")
                    if old_hall != target_hall and old_hall and old_hall.name:
                        history_marker = f"{old_name}@{old_hall.name}"
                        if history_marker not in current_aliases_set:
                            current_aliases_set.add(history_marker)
                            print(f"{log_prefix}   - Added history marker '{history_marker}' to aliases.")
                    animal_original.aliases = list(current_aliases_set)

                    print(f"{log_prefix}   - Set hall to: {target_hall.name} (inferred)")
                    print(f"{log_prefix}   - Set name to: {new_name} (inferred)")
                    print(f"{log_prefix}   - Set is_active to: True")
                    print(f"{log_prefix}   - Final aliases list: {animal_original.aliases}")
                    animal_original.save()
                    print(f"{log_prefix}   - Final animal (ID {animal_original.id}) saved successfully.")

                    # --- f. Delete duplicate record ---
                    duplicate_pk_to_delete = duplicate_animal.pk
                    duplicate_name_to_delete = duplicate_animal.name
                    print(f"{log_prefix} Deleting duplicate animal record ID: {duplicate_pk_to_delete} ({duplicate_name_to_delete})...")
                    # --- *** Corrected Indentation for photo deletion block *** ---
                    if duplicate_animal.photo and (not animal_original.photo or duplicate_animal.photo.name != animal_original.photo.name):
                        print(f"{log_prefix}   - Deleting photo file of duplicate: {duplicate_animal.photo.name}")
                        try:
                            duplicate_animal.photo.delete(save=False)
                        except Exception as dup_photo_del_err:
                            print(f"{log_prefix}   - Warning: Error deleting photo file for duplicate ID {duplicate_pk_to_delete}: {dup_photo_del_err}")
                    # --- *** End of corrected block *** ---
                    duplicate_animal.delete()
                    print(f"{log_prefix}   - Duplicate animal deleted successfully.")
                    logger.info(f"{log_prefix} Deleted duplicate animal record ID {duplicate_pk_to_delete} ({duplicate_name_to_delete}).")

                # --- Transaction successful ---
                # print(f"{log_prefix} Transaction committed successfully.") # Commit is implicit
                logger.info(f"{log_prefix} Merge completed successfully.")
                messages.success(request, f"美容師資料已成功合併至 '{new_name}' @ '{target_hall.name}'。關聯記錄、標籤和班表已處理。")
                return redirect('admin:myapp_animal_changelist')

            except Exception as e: # Outer try's except, should align with the outer try
                print(f"    !!! Error during MERGE processing: {e} !!!"); traceback.print_exc()
                logger.error(f"Error processing merge for animal {animal_original.id} from {duplicate_animal.id}", exc_info=True)
                error_message = f"處理合併時發生內部錯誤: {e}"
                if 'violates unique constraint' in str(e):
                     error_message = f"處理合併時遇到資料庫唯一性衝突，操作未完成。錯誤：{e}"
                messages.error(request, error_message)
                # Fall through to re-render form

        else: # form is invalid
            print("    Form is invalid. Errors:", form.errors.as_json())
            # Form errors will be displayed by the template

    # --- Handle GET request or failed POST validation ---
    if form is None:
        form = MergeTransferForm(animal_original=animal_original)

    context = _get_merge_view_context(request, animal_original, form)
    return render(request, 'admin/myapp/animal/merge_transfer_form.html', context)


# --- Helper function to prepare context (縮排已檢查) ---
def _get_merge_view_context(request, animal_original, form):
    """Helper function to prepare the context for the merge view template."""
    approved_review_count = '計算錯誤'
    notes_count = '計算錯誤'
    pending_count = '計算錯誤'
    aliases_display_text = '獲取錯誤'

    try:
        approved_review_count = animal_original.reviews.filter(approved=True).count()
        notes_count = Note.objects.filter(animal=animal_original).count()
        pending_count = PendingAppointment.objects.filter(animal=animal_original).count()
        aliases_display_text = "無"
        aliases_data = animal_original.aliases
        if isinstance(aliases_data, list):
            display_aliases = [str(a).strip() for a in aliases_data[:3] if a is not None and str(a).strip()]
            suffix = '...' if len(aliases_data) > 3 else ''
            if display_aliases:
                aliases_display_text = ", ".join(display_aliases) + suffix
        elif isinstance(aliases_data, str):
            aliases_display_text = aliases_data[:30] + ('...' if len(aliases_data) > 30 else '')
        elif aliases_data:
            aliases_display_text = str(aliases_data)
    except Exception as count_error:
        print(f"Warning: Error counting related objects or formatting aliases for animal {animal_original.id}: {count_error}")

    return {
        'title': f"合併美容師資料: {animal_original.name}",
        'animal_original': animal_original,
        'form': form,
        'opts': Animal._meta,
        'has_view_permission': request.user.has_perm('myapp.view_animal'),
        'has_change_permission': request.user.has_perm('myapp.change_animal'),
        'has_delete_permission': request.user.has_perm('myapp.delete_animal'),
        'is_popup': False,
        'save_as': False,
        'has_add_permission': request.user.has_perm('myapp.add_animal'),
        'app_label': Animal._meta.app_label,
        'approved_review_count': approved_review_count,
        'notes_count': notes_count,
        'pending_count': pending_count,
        'aliases_display_text': aliases_display_text,
    }
# --- *** ---

# --- views.py 文件結束 ---