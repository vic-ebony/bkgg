# D:\bkgg\mybackend\myapp\views.py
# --- 保持所有原始導入 ---
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateformat import format as format_date # Import date formatting
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, Http404 # Import Http404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Prefetch, Max
from django.views.decorators.http import require_POST, require_GET # Import require_GET
from django.template.loader import render_to_string
from .models import Animal, Hall, Review, PendingAppointment, Note, Announcement, StoryReview, WeeklySchedule
import traceback
import html
import logging # 添加 logging

logger = logging.getLogger(__name__) # 添加 logger

# --- *** 導入 DailySchedule (保持不變) *** ---
try:
    from schedule_parser.models import DailySchedule
    SCHEDULE_PARSER_ENABLED = True
except ImportError:
    print("WARNING: schedule_parser app or DailySchedule model not found. Daily schedule features will be disabled.")
    SCHEDULE_PARSER_ENABLED = False
    DailySchedule = None
# ------------------------------------

# --- *** 修改後的 render_animal_rows，增加 fetch_daily_slots 和詳細打印 *** ---
def render_animal_rows(request, animals_qs, fetch_daily_slots=False):
    """
    渲染動物表格行的通用函數。
    可以選擇是否查詢並包含當日的 DailySchedule 時段。
    增加了詳細的調試打印信息。
    """
    print(f"\n--- render_animal_rows called. fetch_daily_slots={fetch_daily_slots} ---")
    animal_daily_slots = {}
    animal_ids_on_page = [a.id for a in animals_qs]
    print(f"    Animal IDs passed in: {animal_ids_on_page}")
    if fetch_daily_slots and SCHEDULE_PARSER_ENABLED and DailySchedule is not None and animal_ids_on_page:
        print(f"    Attempting to fetch daily slots for these IDs...")
        try:
            daily_schedules_qs = DailySchedule.objects.filter(
                animal_id__in=animal_ids_on_page
            ).values('animal_id', 'time_slots')
            for schedule in daily_schedules_qs:
                animal_daily_slots[schedule['animal_id']] = schedule['time_slots']
            print(f"    Fetched daily slots data: {animal_daily_slots}")
        except Exception as slot_err:
            print(f"    !!! Error fetching daily slots inside render_animal_rows: {slot_err}")
            traceback.print_exc()
    else:
         print(f"    Skipping fetch daily slots. Reason: fetch_daily_slots={fetch_daily_slots}, SCHEDULE_PARSER_ENABLED={SCHEDULE_PARSER_ENABLED}, DailySchedule exists={DailySchedule is not None}, animal_ids_on_page exists={bool(animal_ids_on_page)}")

    pending_ids = set(); notes_by_animal = {}
    if request.user.is_authenticated and animal_ids_on_page:
        try:
            pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user, animal_id__in=animal_ids_on_page))
            notes_qs = Note.objects.filter(user=request.user, animal_id__in=animal_ids_on_page)
            notes_by_animal = {str(note.animal_id): note for note in notes_qs}
        except Exception as e: print(f"Error fetching pending/notes: {e}")

    rendered_rows_html_list = []
    print(f"    Processing {len(animals_qs)} animals for rendering...")
    for animal_instance in animals_qs:
        if not hasattr(animal_instance, 'approved_review_count'):
             try: animal_instance.approved_review_count = Review.objects.filter(animal=animal_instance, approved=True).count()
             except Exception as count_err: print(f"    Warning: Error calc review count for {animal_instance.id}: {count_err}"); animal_instance.approved_review_count = 0

        animal_id_str = str(animal_instance.id)
        today_slots_for_template = animal_daily_slots.get(animal_instance.id)
        print(f"      - Animal ID: {animal_instance.id} ({animal_instance.name}), Found slots: {today_slots_for_template}")

        row_context = {
            'animal': animal_instance, 'user': request.user,
            'today_slots': today_slots_for_template,
            'is_pending': animal_id_str in pending_ids,
            'note': notes_by_animal.get(animal_id_str),
            'review_count': getattr(animal_instance, 'approved_review_count', 0),
        }
        try:
            rendered_html = render_to_string('myapp/partials/_animal_table_rows.html', row_context, request=request)
            rendered_rows_html_list.append(rendered_html)
        except Exception as render_err:
            print(f"!!! Error rendering partial (animal_rows) for {animal_instance.id}: {render_err} !!!"); traceback.print_exc()
            # 使用 logger 記錄錯誤
            logger.error(f"Error rendering row for animal {animal_instance.id}", exc_info=True)
            rendered_rows_html_list.append(f'<tr><td colspan="5">渲染錯誤: {animal_instance.name}</td></tr>') # 更具体的错误提示

    print("--- render_animal_rows finished ---")
    return "".join(rendered_rows_html_list)

# --- *** 移除舊的 render_daily_schedule_rows 函數 *** ---
# (確保這裡沒有舊的 render_daily_schedule_rows 函數定義)

# --- Home View (修改以使用新的 render_animal_rows 並修正 fetch_type 判斷) ---
def home(request):
    is_ajax_request = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    fetch_type = request.GET.get('fetch')
    is_daily_schedule_ajax = is_ajax_request and fetch_type == 'daily_schedule'

    print("-" * 20); print(f"Request Path: {request.path}"); print(f"Request GET Params: {request.GET}")
    print(f"Is AJAX Request: {is_ajax_request}"); print(f"Handling as Daily Schedule AJAX: {is_daily_schedule_ajax}")

    if is_daily_schedule_ajax:
        print(">>> Handling as Daily Schedule AJAX Request <<<")
        hall_id = request.GET.get('hall_id')
        if not hall_id: return JsonResponse({'error': '請求缺少館別 ID (hall_id)'}, status=400)
        print(f"    Selected Hall ID for Daily Schedule: {hall_id}")

        try:
            hall_id_int = int(hall_id); selected_hall = get_object_or_404(Hall, id=hall_id_int, is_active=True)
            print(f"    Hall '{selected_hall.name}' found and active.")
        except (ValueError, TypeError): return JsonResponse({'error': '無效的館別 ID 格式'}, status=400)
        except Http404: return JsonResponse({'table_html': '<tr class="empty-table-message"><td colspan="5">所選館別不存在或未啟用</td></tr>', 'first_animal': {}}, status=404)

        try:
            daily_schedules_qs = DailySchedule.objects.filter(
                hall_id=hall_id_int
            ).select_related(
                'animal', 'animal__hall'
            ).annotate(
                 approved_review_count=Count('animal__reviews', filter=Q(animal__reviews__approved=True))
            ).order_by('animal__order', 'animal__name')

            animals_for_render = []
            for ds in daily_schedules_qs:
                if ds.animal:
                    setattr(ds.animal, 'approved_review_count', ds.approved_review_count)
                    animals_for_render.append(ds.animal)

            table_html = render_animal_rows(request, animals_for_render, fetch_daily_slots=True)
            print(f"    Daily Schedule AJAX using render_animal_rows rendered (length: {len(table_html)}).")

            first_animal_data = {}
            if animals_for_render:
                first_animal_obj = animals_for_render[0]
                try: first_animal_data = {'photo_url': first_animal_obj.photo.url if first_animal_obj.photo else '','name': first_animal_obj.name or '','introduction': first_animal_obj.introduction or ''}
                except Exception as e: print(f"    Warning: Error getting first animal data: {e}")

            print(f"    Returning JSON for Daily Schedule.")
            return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})

        except Exception as e:
            print(f"    !!! Error during Daily Schedule AJAX processing: {e} !!!"); traceback.print_exc()
            logger.error("Error processing daily schedule AJAX", exc_info=True) # 使用 logger
            error_html = f'<tr class="empty-table-message"><td colspan="5">載入班表時發生內部錯誤</td></tr>'
            return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)

    # --- 處理其他 AJAX 請求 (修正 fetch_type 判斷) ---
    elif is_ajax_request:
        print(f">>> Handling AJAX Request. Received fetch_type = '{fetch_type}' (Type: {type(fetch_type)}) <<<")
        if fetch_type == 'pending':
            print("    Dispatching to ajax_get_pending_list...")
            return ajax_get_pending_list(request)
        # --- *** 修改這裡的判斷條件 *** ---
        elif fetch_type == 'my_notes': # <-- 從 'notes' 改為 'my_notes'
        # --- *** 修改結束 *** ---
             print("    Dispatching to ajax_get_my_notes...")
             return ajax_get_my_notes(request)
        elif fetch_type == 'latest_reviews':
             print("    Dispatching to ajax_get_latest_reviews...")
             return ajax_get_latest_reviews(request)
        elif fetch_type == 'recommendations':
             print("    Dispatching to ajax_get_recommendations...")
             return ajax_get_recommendations(request)
        else:
            print(f"    ERROR: Unknown fetch_type '{fetch_type}', returning 400.")
            return JsonResponse({'error': '未知的請求類型'}, status=400)

    # --- Full Page Rendering (保持不變) ---
    else:
        print(">>> Handling as Full Page Request (Rendering myapp/index.html) <<<")
        halls = Hall.objects.filter(is_active=True, is_visible=True).order_by('order', 'name')
        context = {'halls': halls, 'user': request.user}; initial_pending_count = 0
        if request.user.is_authenticated:
            try: initial_pending_count = PendingAppointment.objects.filter(user=request.user).count()
            except Exception as e: print(f"Error fetching initial pending count: {e}")
        context['pending_count'] = initial_pending_count
        try: context['announcement'] = Announcement.objects.filter(is_active=True).order_by('-created_at').first()
        except Exception as e: print(f"Error fetching announcement: {e}"); context['announcement'] = None
        try:
            first_animal_for_promo = Animal.objects.filter(is_active=True, photo__isnull=False).exclude(photo='').filter(Q(hall__isnull=True) | Q(hall__is_active=True)).order_by('?').first()
            context['promo_photo_url'] = first_animal_for_promo.photo.url if first_animal_for_promo else None
            context['promo_animal_name'] = first_animal_for_promo.name if first_animal_for_promo else None
        except Exception as e: print(f"Error fetching promo photo: {e}"); context['promo_photo_url'] = None; context['promo_animal_name'] = None
        login_error = request.session.pop('login_error', None);
        if login_error: context['login_error'] = login_error
        context['selected_hall_id'] = 'all'
        template_path = 'myapp/index.html'
        print(f"    Rendering full template: {template_path}")
        try: return render(request, template_path, context)
        except Exception as e:
            print(f"    !!! Error rendering {template_path}: {e} !!!"); traceback.print_exc()
            logger.error(f"Error rendering template {template_path}", exc_info=True) # 使用 logger
            raise

# ======================================================================
# --- 以下 AJAX view 現在需要調用修改後的 render_animal_rows ---
# ======================================================================

# --- AJAX View for Pending List (修改調用) ---
@login_required
@require_GET
def ajax_get_pending_list(request):
    print(">>> Handling AJAX Request for Pending List <<<")
    try:
        pending_appointments_qs = PendingAppointment.objects.filter(user=request.user).select_related('animal', 'animal__hall').order_by('-added_at')
        animal_ids = list(pending_appointments_qs.values_list('animal_id', flat=True))
        animals_qs = Animal.objects.filter(id__in=animal_ids).filter(Q(hall__isnull=True) | Q(hall__is_active=True)).annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True)))
        animals_dict = {a.id: a for a in animals_qs}
        animals_list_ordered = []
        for pa in pending_appointments_qs:
            animal = animals_dict.get(pa.animal_id)
            if animal: animals_list_ordered.append(animal)
        table_html = render_animal_rows(request, animals_list_ordered, fetch_daily_slots=True) # <-- 確認傳遞 True
        first_animal_data = {}
        if animals_list_ordered:
            first_animal = animals_list_ordered[0]
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '', 'name': first_animal.name or '', 'introduction': first_animal.introduction or '' }
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_pending_list: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching pending list", exc_info=True)
        return JsonResponse({'error': '無法載入待約清單'}, status=500)

# --- AJAX View for My Notes (修改調用) ---
@login_required
@require_GET
def ajax_get_my_notes(request):
    print(">>> Handling AJAX Request for My Notes <<<")
    hall_id = request.GET.get('hall_id'); selected_hall_id = hall_id or 'all'
    print(f"    Selected Hall ID for My Notes: {selected_hall_id}")
    try:
        notes_base_qs = Note.objects.filter(user=request.user).filter(Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True)).select_related('animal', 'animal__hall')
        if selected_hall_id != "all":
            try:
                hall_id_int = int(selected_hall_id)
                notes_qs = notes_base_qs.filter(animal__hall_id=hall_id_int)
            except (ValueError, TypeError):
                # --- *** 修改：處理無效 hall_id 時返回 400 *** ---
                print(f"Error: Invalid hall_id '{selected_hall_id}' received for notes.")
                return JsonResponse({'error': '無效的館別 ID 格式'}, status=400)
        else:
            notes_qs = notes_base_qs.all()

        notes_qs = notes_qs.order_by('-updated_at')
        animal_ids = list(notes_qs.values_list('animal_id', flat=True)); animals_list_ordered = []
        if animal_ids:
            animals_qs = Animal.objects.filter(id__in=animal_ids).annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True)))
            animals_dict = {a.id: a for a in animals_qs}
            for note in notes_qs:
                animal = animals_dict.get(note.animal_id)
                if animal: animals_list_ordered.append(animal)
        table_html = render_animal_rows(request, animals_list_ordered, fetch_daily_slots=True) # <-- 確認傳遞 True
        print(f"    My Notes AJAX (Hall: {selected_hall_id}) Partial HTML rendered (length: {len(table_html)}).")
        first_animal_data = {}
        if animals_list_ordered:
            first_animal = animals_list_ordered[0]
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '','name': first_animal.name or '','introduction': first_animal.introduction or ''}
        print(f"    Returning JSON for My Notes (Hall: {selected_hall_id}).")
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_my_notes: {e} !!!"); traceback.print_exc()
        logger.error(f"Error fetching my notes (Hall: {selected_hall_id})", exc_info=True)
        return JsonResponse({'error': f'無法載入我的筆記'}, status=500) # 簡化錯誤信息

# --- AJAX View for Latest Reviews (修改調用) ---
@require_GET
def ajax_get_latest_reviews(request):
    print(">>> Handling AJAX Request for Latest Reviews <<<")
    try:
        latest_reviewed_animals_qs = Animal.objects.filter(is_active=True).filter(
            Q(hall__isnull=True) | Q(hall__is_active=True)).annotate(
            latest_review_time=Max('reviews__created_at', filter=Q(reviews__approved=True)), approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        ).filter(latest_review_time__isnull=False).select_related('hall').order_by('-latest_review_time')[:20]
        table_html = render_animal_rows(request, latest_reviewed_animals_qs, fetch_daily_slots=True) # <-- 確認傳遞 True
        first_animal_data = {}
        if latest_reviewed_animals_qs.exists():
             first_animal = latest_reviewed_animals_qs.first()
             first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '','name': first_animal.name or '','introduction': first_animal.introduction or ''}
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_latest_reviews: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching latest reviews", exc_info=True)
        return JsonResponse({'error': '無法載入最新心得'}, status=500)

# --- AJAX View for Recommendations (修改調用) ---
@require_GET
def ajax_get_recommendations(request):
    print(">>> Handling AJAX Request for Recommendations <<<")
    try:
        recommended_animals_qs = Animal.objects.filter(is_active=True, is_recommended=True).filter(
            Q(hall__isnull=True) | Q(hall__is_active=True)).select_related('hall').annotate(
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True))).order_by('hall__order', 'order', 'name')
        table_html = render_animal_rows(request, recommended_animals_qs, fetch_daily_slots=True) # <-- 確認傳遞 True
        first_animal_data = {}
        if recommended_animals_qs.exists():
            first_animal = recommended_animals_qs.first()
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '','name': first_animal.name or '','introduction': first_animal.introduction or ''}
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_recommendations: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching recommendations", exc_info=True)
        return JsonResponse({'error': '無法載入每日推薦'}, status=500)

# --- User Authentication Views (保持不變) ---
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

# --- Add Story Review View (保持不變) ---
@login_required
@require_POST
def add_story_review(request):
    print(">>> Handling POST Request for Adding Story Review <<<")
    animal_id = request.POST.get("animal_id"); user = request.user
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    try: animal = get_object_or_404(Animal, id=animal_id)
    except (Http404): return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
    except (ValueError, TypeError): return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    face_list = request.POST.getlist("face"); temperament_list = request.POST.getlist("temperament"); scale_list = request.POST.getlist("scale"); content = request.POST.get("content", "").strip(); age_str = request.POST.get("age"); cup_size_value = request.POST.get("cup_size",""); errors = {}
    if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
    if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
    if not content: errors['content'] = "心得內容不能為空"
    age = None
    if age_str:
        try: age = int(age_str); assert age > 0
        except (ValueError, TypeError, AssertionError): errors['age'] = "年紀必須是有效的正數"
    if errors: error_message = "輸入無效: " + "; ".join([f"{k}: {v}" for k, v in errors.items()]); return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)
    try:
        new_story = StoryReview.objects.create(animal=animal, user=user, age=age, looks=request.POST.get("looks") or None, face=','.join(face_list), temperament=','.join(temperament_list), physique=request.POST.get("physique") or None, cup=request.POST.get("cup") or None, cup_size=cup_size_value or None, skin_texture=request.POST.get("skin_texture") or None, skin_color=request.POST.get("skin_color") or None, music=request.POST.get("music") or None, music_price=request.POST.get("music_price") or None, sports=request.POST.get("sports") or None, sports_price=request.POST.get("sports_price") or None, scale=','.join(scale_list), content=content, approved=False, approved_at=None, expires_at=None )
        print(f"Story Review {new_story.id} created for {animal_id}. Needs approval.")
        return JsonResponse({"success": True, "message": "限時動態心得已提交，待審核後將顯示"})
    except Exception as e:
        print(f"Error creating story review: {e}"); traceback.print_exc()
        logger.error("Error creating story review", exc_info=True)
        return JsonResponse({"success": False, "error": "儲存限時動態心得時發生內部錯誤"}, status=500)

# --- Add Regular Review View (修正 SyntaxError) ---
@login_required
def add_review(request):
    if request.method == "POST":
        print(">>> Handling POST Request for Adding Regular Review <<<")
        animal_id = request.POST.get("animal_id"); user = request.user
        if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
        try: animal = get_object_or_404(Animal, id=animal_id)
        except (Http404): return JsonResponse({"success": False, "error": "找不到指定的動物"}, status=404)
        except (ValueError, TypeError): return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
        face_list = request.POST.getlist("face"); temperament_list = request.POST.getlist("temperament"); scale_list = request.POST.getlist("scale"); content = request.POST.get("content", "").strip(); age_str = request.POST.get("age"); cup_size_value = request.POST.get("cup_size",""); errors = {}
        if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
        if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
        if not content: errors['content'] = "心得內容不能為空"
        age = None
        if age_str:
            try: age = int(age_str); assert age > 0
            except (ValueError, TypeError, AssertionError): errors['age'] = "年紀必須是有效的正數"
        if errors: error_message = "輸入無效: " + "; ".join([f"{k}: {v}" for k, v in errors.items()]); return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)
        try:
            new_review = Review.objects.create(animal=animal, user=user, age=age, looks=request.POST.get("looks") or None, face=','.join(face_list), temperament=','.join(temperament_list), physique=request.POST.get("physique") or None, cup=request.POST.get("cup") or None, cup_size=cup_size_value or None, skin_texture=request.POST.get("skin_texture") or None, skin_color=request.POST.get("skin_color") or None, music=request.POST.get("music") or None, music_price=request.POST.get("music_price") or None, sports=request.POST.get("sports") or None, sports_price=request.POST.get("sports_price") or None, scale=','.join(scale_list), content=content, approved=False)
            print(f"Review {new_review.id} created for {animal_id}.")
            return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
        except Exception as e:
            print(f"Error creating review: {e}"); traceback.print_exc()
            logger.error("Error creating regular review", exc_info=True)
            return JsonResponse({"success": False, "error": "儲存心得時發生內部錯誤"}, status=500)

    elif request.method == "GET": # Fetching reviews for modal
        animal_id = request.GET.get("animal_id")
        if not animal_id: return JsonResponse({"error": "缺少 animal_id"}, status=400)
        try: animal = get_object_or_404(Animal.objects.filter(Q(hall__isnull=True) | Q(hall__is_active=True)), id=animal_id, is_active=True)
        except Http404: return JsonResponse({"error": "找不到動物或動物未啟用"}, status=404)
        except (ValueError, TypeError): return JsonResponse({"error": "無效的 animal_id"}, status=400)
        print(f"Fetching reviews for animal {animal_id}")
        reviews_qs = Review.objects.filter(animal=animal, approved=True).select_related('user').order_by("-created_at")
        user_ids = list(reviews_qs.values_list('user_id', flat=True).distinct()); user_review_counts = {}
        if user_ids:
            try: counts_query = Review.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(totalCount=Count('id')); user_review_counts = {item['user_id']: item['totalCount'] for item in counts_query}
            except Exception as count_err: print(f"Error fetching user review counts: {count_err}")
        data = []
        for r in reviews_qs:
            user_display_name = "匿名"; formatted_date = ""
            if hasattr(r, 'user') and r.user: user_display_name = r.user.first_name or r.user.username
            if r.created_at:
                try:
                    formatted_date = timezone.localtime(r.created_at).strftime("%Y-%m-%d")
                except Exception as date_err:
                    print(f"Error formatting date: {date_err}")
                    formatted_date = "日期錯誤"
            data.append({"id": r.id, "user": user_display_name, "totalCount": user_review_counts.get(r.user_id, 0), "age": r.age, "looks": r.looks, "face": r.face, "temperament": r.temperament, "physique": r.physique, "cup": r.cup, "cup_size": r.cup_size, "skin_texture": r.skin_texture, "skin_color": r.skin_color, "music": r.music, "music_price": r.music_price, "sports": r.sports, "sports_price": r.sports_price, "scale": r.scale, "content": r.content, "created_at": formatted_date})
        print(f"Returning {len(data)} reviews for animal {animal_id}.")
        return JsonResponse({"reviews": data})
    return JsonResponse({"error": "請求方法不支援"}, status=405)

# --- Pending Appointment Handling Views (修正 SyntaxError) ---
@require_POST
@login_required
def add_pending_appointment(request): # <--- 確認函數名稱已修正
    animal_id = request.POST.get("animal_id"); user = request.user
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    try: animal = get_object_or_404(Animal, id=animal_id)
    except Http404: return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
    except (ValueError, TypeError): return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    try:
        obj, created = PendingAppointment.objects.get_or_create(user=user, animal=animal)
        pending_count = PendingAppointment.objects.filter(user=user).count()
        message = f"{animal.name} 已加入待約清單" if created else f"{animal.name} 已在待約清單中"
        print(f"Pending: {'Added' if created else 'Exists'} for {animal_id} by {user.username}. Count: {pending_count}")
        return JsonResponse({"success": True, "message": message, "pending_count": pending_count})
    except Exception as e:
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
        try: animal_id_int = int(animal_id)
        except (ValueError, TypeError): raise ValueError("無效的動物 ID 格式")

        deleted_count, _ = PendingAppointment.objects.filter(user=user, animal_id=animal_id_int).delete()
        pending_count = PendingAppointment.objects.filter(user=user).count()

        # --- *** 修正：拆分 if/else 和 return *** ---
        if deleted_count == 0:
            animal_exists = Animal.objects.filter(id=animal_id_int).exists()
            if not animal_exists:
                return JsonResponse({"success": False, "error": "找不到該動物", "pending_count": pending_count}, status=404)
            else:
                return JsonResponse({"success": False, "error": "該待約項目不存在", "pending_count": pending_count}, status=404)
        # --- *** 修正結束 *** ---

        animal_name = Animal.objects.filter(id=animal_id_int).values_list('name', flat=True).first() or "該美容師"
        print(f"Pending removed {animal_id_int} by {user.username}. Count: {pending_count}")
        return JsonResponse({"success": True, "message": f"{animal_name} 待約項目已移除", "pending_count": pending_count, "animal_id": animal_id_int})

    except ValueError as ve:
        print(f"Error remove pending: {ve}")
        count = PendingAppointment.objects.filter(user=user).count()
        return JsonResponse({"success": False, "error": str(ve), "pending_count": count}, status=400)
    except Exception as e:
        print(f"Error remove pending: {e}"); traceback.print_exc()
        logger.error("Error removing pending appointment", exc_info=True)
        count = PendingAppointment.objects.filter(user=user).count()
        return JsonResponse({"success": False, "error": "移除待約時發生錯誤", "pending_count": count}, status=500)

# --- Note Handling Views (保持不變) ---
@require_POST
@login_required
def add_note(request):
    animal_id = request.POST.get("animal_id"); content = request.POST.get("content", "").strip(); note_id = request.POST.get("note_id"); user = request.user
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)
    try: animal = get_object_or_404(Animal, id=animal_id)
    except Http404: return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
    except (ValueError, TypeError): return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    note = None; created = False
    try:
        if note_id: # 更新現有筆記
             try: note = Note.objects.get(id=note_id, user=user, animal=animal); note.content = content; note.save(); created = False; print(f"Note {note.id} updated.")
             except Note.DoesNotExist: return JsonResponse({"success": False, "error": "找不到要更新的筆記"}, status=404)
        else: # 新增或更新筆記
            note, created = Note.objects.update_or_create(user=user, animal=animal, defaults={"content": content}); print(f"Note {'created' if created else 'updated'}. ID: {note.id}.")
        message = "筆記已新增" if created else "筆記已更新"
        print(f"Note for {animal_id} by {user.username}: {'Created' if created else 'Updated'}.")
        return JsonResponse({"success": True, "message": message, "note_id": note.id, "note_content": note.content, "animal_id": animal.id})
    except Exception as e:
        print(f"Error add/update note: {e}"); traceback.print_exc()
        logger.error("Error adding/updating note", exc_info=True)
        return JsonResponse({"success": False, "error": "儲存筆記時發生錯誤"}, status=500)

@require_POST
@login_required
def delete_note(request):
    note_id = request.POST.get("note_id"); user = request.user
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    try:
        try: note_id_int = int(note_id)
        except (ValueError, TypeError): raise ValueError("無效的筆記 ID 格式")
        note = get_object_or_404(Note, id=note_id_int, user=user); animal_id = note.animal_id; deleted_count, _ = note.delete()
        if deleted_count == 0: return JsonResponse({"success": False, "error": "刪除失敗"})
        print(f"Note {note_id_int} deleted for {animal_id}."); return JsonResponse({"success": True, "message": "筆記已刪除", "animal_id": animal_id})
    except Http404: return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve: return JsonResponse({"success": False, "error": str(ve)}, status=400)
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
        try: note_id_int = int(note_id)
        except (ValueError, TypeError): raise ValueError("無效的筆記 ID 格式")
        note = get_object_or_404(Note.objects.select_related('animal'), id=note_id_int, user=user); animal = note.animal; note.content = content; note.save()
        print(f"Note {note_id_int} updated for {animal.id}."); return JsonResponse({"success": True, "message": "筆記已更新", "note_id": note.id, "note_content": note.content, "animal_id": animal.id})
    except Http404: return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve: return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        print(f"Error updating note: {e}"); traceback.print_exc()
        logger.error("Error updating note", exc_info=True)
        return JsonResponse({"success": False, "error": "更新筆記時發生錯誤"}, status=500)

# --- AJAX View for Active Stories (保持不變) ---
@require_GET
def ajax_get_active_stories(request):
    print(">>> Handling AJAX Request for Active Story Reviews <<<")
    try:
        now = timezone.now()
        active_stories_qs = StoryReview.objects.filter(Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True), approved=True, expires_at__gt=now, animal__is_active=True).select_related('animal', 'animal__hall', 'user').order_by('-approved_at')
        stories_data = [{'id': s.id, 'animal_id': s.animal_id, 'animal_name': s.animal.name, 'animal_photo_url': s.animal.photo.url if s.animal.photo else None, 'hall_name': s.animal.hall.name if s.animal.hall else '未知館別', 'user_name': s.user.first_name or s.user.username, 'remaining_time': s.remaining_time_display} for s in active_stories_qs]
        return JsonResponse({'stories': stories_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_active_stories: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching active stories", exc_info=True)
        return JsonResponse({'error': '無法載入限時動態'}, status=500)

# --- AJAX View for Story Detail (保持不變) ---
@require_GET
def ajax_get_story_detail(request, story_id):
    print(f">>> Handling AJAX Request for Story Detail (ID: {story_id}) <<<")
    try:
        story = get_object_or_404(StoryReview.objects.filter(Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True), approved=True, expires_at__gt=timezone.now(), animal__is_active=True).select_related('animal', 'animal__hall', 'user'), pk=story_id)
        animal = story.animal; user = story.user; approved_at_display = format_date(timezone.localtime(story.approved_at), 'Y-m-d H:i') if story.approved_at else ""
        story_data = {'id': story.id, 'animal_id': animal.id, 'animal_name': animal.name, 'animal_photo_url': animal.photo.url if animal.photo else None, 'hall_name': animal.hall.name if animal.hall else '未知館別', 'user_name': user.first_name or user.username, 'remaining_time': story.remaining_time_display, 'approved_at_display': approved_at_display, 'age': story.age, 'looks': story.looks, 'face': story.face, 'temperament': story.temperament, 'physique': story.physique, 'cup': story.cup, 'cup_size': story.cup_size, 'skin_texture': story.skin_texture, 'skin_color': story.skin_color, 'music': story.music, 'music_price': story.music_price, 'sports': story.sports, 'sports_price': story.sports_price, 'scale': story.scale, 'content': story.content}
        print(f"    Returning details for story {story_id}."); return JsonResponse({'success': True, 'story': story_data})
    except Http404: print(f"    Story {story_id} not found/inactive."); return JsonResponse({'success': False, 'error': '找不到動態'}, status=404)
    except Exception as e:
        print(f"!!! Error in ajax_get_story_detail for ID {story_id}: {e} !!!"); traceback.print_exc()
        logger.error(f"Error fetching story detail for ID {story_id}", exc_info=True)
        return JsonResponse({'success': False, 'error': '無法載入動態詳情'}, status=500)

# --- AJAX View for Weekly Schedule Images (修正 SyntaxError) ---
@require_GET
def ajax_get_weekly_schedule(request):
    hall_id = request.GET.get('hall_id')
    print(f">>> Handling AJAX Request for Weekly Schedule (Hall ID: {hall_id}) <<<")
    if not hall_id: return JsonResponse({'success': False, 'error': '缺少館別 ID'}, status=400)
    try:
        hall_id_int = int(hall_id)
        hall = get_object_or_404(Hall, id=hall_id_int, is_active=True)
        hall_name = hall.name
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': '無效的館別 ID 格式'}, status=400)
    # --- *** 修正：拆分 except Http404 塊 *** ---
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
    # --- *** 修正結束 *** ---
    except Exception as e:
         print(f"!!! Error getting Hall: {e} !!!")
         traceback.print_exc()
         logger.error(f"Error getting Hall object for ID {hall_id}", exc_info=True)
         return JsonResponse({'success': False, 'error': '獲取館別信息時發生錯誤'}, status=500)

    # 如果成功獲取到活動的 Hall，繼續執行
    try:
        schedules = WeeklySchedule.objects.filter(hall_id=hall_id_int).order_by('order')
        schedule_urls = [s.schedule_image.url for s in schedules if s.schedule_image]
        if schedule_urls:
            print(f"    Found {len(schedule_urls)} images.");
            return JsonResponse({'success': True, 'schedule_urls': schedule_urls, 'hall_name': hall_name})
        else:
            print(f"    No images for Hall {hall_id}.")
            return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': hall_name, 'message': f'{hall_name} 未上傳班表圖片'})
    except Exception as e:
        print(f"!!! Error fetch weekly schedule: {e} !!!"); traceback.print_exc()
        logger.error(f"Error fetching weekly schedule for Hall ID {hall_id}", exc_info=True)
        return JsonResponse({'success': False, 'error': '載入每週班表出錯'}, status=500)

# --- AJAX View for Hall of Fame (保持不變) ---
@require_GET
def ajax_get_hall_of_fame(request):
    print(">>> Handling AJAX Request for Hall of Fame <<<")
    try:
        top_users = Review.objects.filter(approved=True).values('user', 'user__username', 'user__first_name').annotate(review_count=Count('id')).order_by('-review_count')[:10]
        data = [{'rank': r+1, 'user_name': (d.get('user__first_name') or d.get('user__username') or f"用戶_{d.get('user','N/A')}") , 'review_count': d.get('review_count',0)} for r,d in enumerate(top_users)]
        print(f"    Returning {len(data)} users."); return JsonResponse({'users': data})
    except Exception as e:
        print(f"!!! Error in ajax_get_hall_of_fame: {e} !!!"); traceback.print_exc()
        logger.error("Error fetching Hall of Fame", exc_info=True)
        return JsonResponse({'error': '無法載入名人堂'}, status=500)

# --- views.py 文件結束 ---