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

# --- *** 導入 DailySchedule (保持不變) *** ---
try:
    from schedule_parser.models import DailySchedule
    SCHEDULE_PARSER_ENABLED = True
except ImportError:
    print("WARNING: schedule_parser app or DailySchedule model not found. Daily schedule features will be disabled.")
    SCHEDULE_PARSER_ENABLED = False
    DailySchedule = None
# ------------------------------------

# --- 渲染函數 render_animal_rows (保持你之前提供的版本) ---
def render_animal_rows(request, animals_qs):
    pending_ids = set()
    notes_by_animal = {}
    if request.user.is_authenticated:
        animal_ids_on_page = [a.id for a in animals_qs]
        try:
            pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user, animal_id__in=animal_ids_on_page))
            notes_qs = Note.objects.filter(user=request.user, animal_id__in=animal_ids_on_page)
            notes_by_animal = {str(note.animal_id): note for note in notes_qs}
        except Exception as e:
            print(f"Error fetching pending/notes in render_animal_rows: {e}")

    rendered_rows_html_list = []
    for animal_instance in animals_qs:
        if not hasattr(animal_instance, 'approved_review_count'):
            try:
                animal_instance.approved_review_count = Review.objects.filter(animal=animal_instance, approved=True).count()
            except Exception as count_err:
                print(f"    Warning: Error calculating review count for {animal_instance.id} in render_animal_rows: {count_err}")
                animal_instance.approved_review_count = 0

        row_context = {
            'animal': animal_instance,
            'user': request.user,
            'pending_ids': pending_ids,
            'notes_by_animal': notes_by_animal,
            # --- 傳遞給模板需要的變量 ---
            'is_pending': str(animal_instance.id) in pending_ids,
            'note': notes_by_animal.get(str(animal_instance.id)),
            'review_count': getattr(animal_instance, 'approved_review_count', 0),
            'today_slots': getattr(animal_instance, 'time_slot', None) # 傳遞舊的 time_slot 給原始渲染邏輯
        }
        try:
            rendered_html_for_animal = render_to_string('myapp/partials/_animal_table_rows.html', row_context, request=request)
            rendered_rows_html_list.append(rendered_html_for_animal)
        except Exception as render_err:
            print(f"    !!! Error rendering partial (original) for animal {animal_instance.id}: {render_err} !!!")
            traceback.print_exc()
            rendered_rows_html_list.append(f'<tr><td colspan="5">Error loading data for {animal_instance.name}</td></tr>')

    return "".join(rendered_rows_html_list)

# --- 新增的渲染函數 render_daily_schedule_rows (保持不變) ---
def render_daily_schedule_rows(request, schedule_data_list, pending_ids, notes_by_animal):
    rendered_rows_html_list = []
    for item in schedule_data_list:
        animal_instance = item.get('animal')
        today_slots = item.get('today_slots')
        if not animal_instance: continue
        review_count = getattr(animal_instance, 'approved_review_count', 0)
        animal_id_str = str(animal_instance.id)
        is_pending = animal_id_str in pending_ids
        note = notes_by_animal.get(animal_id_str)
        row_context = {
            'animal': animal_instance, 'today_slots': today_slots, 'user': request.user,
            'is_pending': is_pending, 'note': note, 'review_count': review_count }
        try:
            rendered_html_for_animal = render_to_string('myapp/partials/_animal_table_rows.html', row_context, request=request)
            rendered_rows_html_list.append(rendered_html_for_animal)
        except Exception as render_err:
            print(f"!!! Error rendering partial (daily) for animal {animal_instance.id}: {render_err} !!!")
            traceback.print_exc()
            rendered_rows_html_list.append(f'<tr><td colspan="5">Error loading data for {animal_instance.name}</td></tr>')
    return "".join(rendered_rows_html_list)

# --- Home View (修改查詢和渲染調用) ---
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
        if not SCHEDULE_PARSER_ENABLED or DailySchedule is None:
             error_html = '<tr class="empty-table-message"><td colspan="5">錯誤：每日班表功能未啟用或模型不存在。</td></tr>'
             return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)
        try:
            hall_id_int = int(hall_id); selected_hall = get_object_or_404(Hall, id=hall_id_int, is_active=True)
            print(f"    Hall '{selected_hall.name}' found and active.")
        except (ValueError, TypeError): return JsonResponse({'error': '無效的館別 ID 格式'}, status=400)
        except Http404: return JsonResponse({'table_html': '<tr class="empty-table-message"><td colspan="5">所選館別不存在或未啟用</td></tr>', 'first_animal': {}}, status=404)
        try:
            daily_schedules_today = DailySchedule.objects.filter(hall_id=hall_id_int).select_related(
                'animal', 'hall', 'animal__hall').annotate(
                 approved_review_count=Count('animal__reviews', filter=Q(animal__reviews__approved=True))
            ).order_by('animal__order', 'animal__name')
            schedule_data_for_template = []; animal_ids_on_page = [ds.animal.id for ds in daily_schedules_today if ds.animal]
            pending_ids = set(); notes_by_animal = {}
            if request.user.is_authenticated and animal_ids_on_page:
                try:
                    pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user, animal_id__in=animal_ids_on_page))
                    notes_qs = Note.objects.filter(user=request.user, animal_id__in=animal_ids_on_page)
                    notes_by_animal = {str(note.animal_id): note for note in notes_qs}
                except Exception as e: print(f"Error pre-fetching pending/notes for daily: {e}")
            for ds in daily_schedules_today:
                 setattr(ds.animal, 'approved_review_count', ds.approved_review_count) # 附加 annotate 結果
                 schedule_data_for_template.append({'animal': ds.animal, 'today_slots': ds.time_slots})
            # --- 調用新的渲染函數 ---
            table_html = render_daily_schedule_rows(request, schedule_data_for_template, pending_ids, notes_by_animal)
            print(f"    Daily Schedule AJAX Partial HTML rendered (length: {len(table_html)}).")
            first_animal_data = {}
            if schedule_data_for_template:
                first_animal_obj = schedule_data_for_template[0]['animal']
                try: first_animal_data = {'photo_url': first_animal_obj.photo.url if first_animal_obj.photo else '','name': first_animal_obj.name or '','introduction': first_animal_obj.introduction or ''}
                except Exception as e: print(f"    Warning: Error getting first animal data: {e}")
            print(f"    Returning JSON for Daily Schedule.")
            return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
        except Exception as e:
            print(f"    !!! Error during Daily Schedule AJAX query/render: {e} !!!"); traceback.print_exc()
            error_html = f'<tr class="empty-table-message"><td colspan="5">載入班表時發生錯誤: {html.escape(str(e))}</td></tr>'
            return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)

    # --- 處理其他 AJAX 請求 (保持不變) ---
    elif is_ajax_request:
        print(f">>> Handling AJAX Request for: {fetch_type} <<<")
        if fetch_type == 'pending': return ajax_get_pending_list(request)
        elif fetch_type == 'notes': return ajax_get_my_notes(request)
        elif fetch_type == 'latest_reviews': return ajax_get_latest_reviews(request)
        elif fetch_type == 'recommendations': return ajax_get_recommendations(request)
        # --- 注意：這裡不再處理 daily_schedule，因為上面已經處理了 ---
        # --- 你其他的 AJAX view 如果是獨立的，需要在 urls.py 中配置並在這裡調用 ---
        # 例如：
        # elif fetch_type == 'active_stories': return ajax_get_active_stories(request)
        # elif fetch_type == 'weekly_schedule': return ajax_get_weekly_schedule(request)
        # elif fetch_type == 'hall_of_fame': return ajax_get_hall_of_fame(request)
        else: return JsonResponse({'error': '未知的請求類型'}, status=400)

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
        except Exception as e: print(f"    !!! Error rendering {template_path}: {e} !!!"); traceback.print_exc(); raise

# ======================================================================
# --- 以下是你原始的、**確認可以正常運作**的其他視圖函數 ---
# --- 這些函數的 try...except 語法已根據你的確認進行保留 ---
# ======================================================================

# --- AJAX View for Pending List ---
@login_required
@require_GET
def ajax_get_pending_list(request):
    print(">>> Handling AJAX Request for Pending List <<<")
    try:
        pending_appointments_qs = PendingAppointment.objects.filter(
            user=request.user
        ).select_related('animal', 'animal__hall').order_by('-added_at')
        animal_ids = list(pending_appointments_qs.values_list('animal_id', flat=True))
        # --- 保持原始查詢和渲染調用 ---
        animals_qs = Animal.objects.filter(
            id__in=animal_ids
        ).filter(
            Q(hall__isnull=True) | Q(hall__is_active=True)
        ).annotate(
             approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        )
        animals_dict = {a.id: a for a in animals_qs}
        animals_list_ordered = []
        for pa in pending_appointments_qs:
            animal = animals_dict.get(pa.animal_id)
            if animal: animals_list_ordered.append(animal)
        # --- 使用原始渲染函數 ---
        table_html = render_animal_rows(request, animals_list_ordered)
        # -----------------------
        first_animal_data = {}
        if animals_list_ordered:
            first_animal = animals_list_ordered[0]
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '', 'name': first_animal.name or '', 'introduction': first_animal.introduction or '' }
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e: print(f"!!! Error in ajax_get_pending_list: {e} !!!"); traceback.print_exc(); return JsonResponse({'error': '無法載入待約清單'}, status=500)

# --- AJAX View for My Notes ---
@login_required
@require_GET
def ajax_get_my_notes(request):
    print(">>> Handling AJAX Request for My Notes <<<")
    hall_id = request.GET.get('hall_id'); selected_hall_id = hall_id or 'all'
    print(f"    Selected Hall ID for My Notes: {selected_hall_id}")
    try:
        notes_base_qs = Note.objects.filter(user=request.user).filter(
            Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True)).select_related('animal', 'animal__hall')
        if selected_hall_id != "all":
            try: hall_id_int = int(selected_hall_id); notes_qs = notes_base_qs.filter(animal__hall_id=hall_id_int)
            except (ValueError, TypeError): print(f"Warn: Invalid hall_id '{selected_hall_id}'"); notes_qs = notes_base_qs.all()
        else: notes_qs = notes_base_qs.all()
        notes_qs = notes_qs.order_by('-updated_at')
        animal_ids = list(notes_qs.values_list('animal_id', flat=True)); animals_list_ordered = []
        if animal_ids:
            animals_qs = Animal.objects.filter(id__in=animal_ids).annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True)))
            animals_dict = {a.id: a for a in animals_qs}
            for note in notes_qs:
                animal = animals_dict.get(note.animal_id)
                if animal: animals_list_ordered.append(animal)
        # --- 使用原始渲染函數 ---
        table_html = render_animal_rows(request, animals_list_ordered)
        # -----------------------
        print(f"    My Notes AJAX (Hall: {selected_hall_id}) Partial HTML rendered (length: {len(table_html)}).")
        first_animal_data = {}
        if animals_list_ordered:
            first_animal = animals_list_ordered[0]
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '','name': first_animal.name or '','introduction': first_animal.introduction or ''}
        print(f"    Returning JSON for My Notes (Hall: {selected_hall_id}).")
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e: print(f"!!! Error in ajax_get_my_notes: {e} !!!"); traceback.print_exc(); return JsonResponse({'error': f'無法載入我的筆記 (Hall: {selected_hall_id}): {e}'}, status=500)

# --- AJAX View for Latest Reviews ---
@require_GET
def ajax_get_latest_reviews(request):
    print(">>> Handling AJAX Request for Latest Reviews <<<")
    try:
        latest_reviewed_animals_qs = Animal.objects.filter(is_active=True).filter(
            Q(hall__isnull=True) | Q(hall__is_active=True)).annotate(
            latest_review_time=Max('reviews__created_at', filter=Q(reviews__approved=True)), approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        ).filter(latest_review_time__isnull=False).select_related('hall').order_by('-latest_review_time')[:20]
        # --- 使用原始渲染函數 ---
        table_html = render_animal_rows(request, latest_reviewed_animals_qs)
        # -----------------------
        first_animal_data = {}
        if latest_reviewed_animals_qs.exists():
             first_animal = latest_reviewed_animals_qs.first()
             first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '','name': first_animal.name or '','introduction': first_animal.introduction or ''}
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e: print(f"!!! Error in ajax_get_latest_reviews: {e} !!!"); traceback.print_exc(); return JsonResponse({'error': '無法載入最新心得'}, status=500)

# --- AJAX View for Recommendations ---
@require_GET
def ajax_get_recommendations(request):
    print(">>> Handling AJAX Request for Recommendations <<<")
    try:
        recommended_animals_qs = Animal.objects.filter(is_active=True, is_recommended=True).filter(
            Q(hall__isnull=True) | Q(hall__is_active=True)).select_related('hall').annotate(
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True))).order_by('hall__order', 'order', 'name')
        # --- 使用原始渲染函數 ---
        table_html = render_animal_rows(request, recommended_animals_qs)
        # -----------------------
        first_animal_data = {}
        if recommended_animals_qs.exists():
            first_animal = recommended_animals_qs.first()
            first_animal_data = {'photo_url': first_animal.photo.url if first_animal.photo else '','name': first_animal.name or '','introduction': first_animal.introduction or ''}
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e: print(f"!!! Error in ajax_get_recommendations: {e} !!!"); traceback.print_exc(); return JsonResponse({'error': '無法載入每日推薦'}, status=500)

# --- User Authentication Views ---
def user_login(request):
    if request.method == "POST":
        username = request.POST.get('username', '').strip(); password = request.POST.get('password', '')
        if not username or not password: request.session['login_error'] = '請輸入帳號和密碼'; return redirect('myapp:home') # 假設有 namespace
        user = authenticate(request, username=username, password=password)
        if user is not None: login(request, user); request.session.pop('login_error', None); print(f"User '{username}' logged in."); return redirect('myapp:home')
        else: print(f"Login failed for '{username}'."); request.session['login_error'] = '帳號或密碼錯誤'; return redirect('myapp:home')
    return redirect('myapp:home')

@require_POST
@login_required
def user_logout(request):
    user_display = request.user.username if request.user.is_authenticated else "N/A"; logout(request)
    print(f"User '{user_display}' logged out."); return redirect('myapp:home') # 假設有 namespace

# --- Add Story Review View (保持原始) ---
@login_required
@require_POST
def add_story_review(request):
    print(">>> Handling POST Request for Adding Story Review <<<")
    animal_id = request.POST.get("animal_id")
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    try: animal = get_object_or_404(Animal, id=animal_id)
    except (Http404): return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
    except (ValueError, TypeError): return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)

    face_list = request.POST.getlist("face"); temperament_list = request.POST.getlist("temperament")
    scale_list = request.POST.getlist("scale"); content = request.POST.get("content", "").strip()
    age_str = request.POST.get("age"); cup_size_value = request.POST.get("cup_size","")
    errors = {}
    if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
    if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
    if not content: errors['content'] = "心得內容不能為空"
    age = None
    if age_str:
        # --- *** 原始的 try/except *** ---
        try:
            age = int(age_str)
            if age <= 0: errors['age'] = "年紀必須是正數"
        except (ValueError, TypeError):
            errors['age'] = "年紀必須是有效的數字"
        # -----------------------------
    if errors:
        error_message = "輸入無效: " + "; ".join([f"{k}: {v}" for k, v in errors.items()])
        return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)
    try:
        new_story = StoryReview.objects.create(
            animal=animal, user=request.user, age=age,
            looks=request.POST.get("looks") or None, face=','.join(face_list),
            temperament=','.join(temperament_list), physique=request.POST.get("physique") or None,
            cup=request.POST.get("cup") or None, cup_size=cup_size_value or None,
            skin_texture=request.POST.get("skin_texture") or None, skin_color=request.POST.get("skin_color") or None,
            music=request.POST.get("music") or None, music_price=request.POST.get("music_price") or None,
            sports=request.POST.get("sports") or None, sports_price=request.POST.get("sports_price") or None,
            scale=','.join(scale_list), content=content,
            approved=False, approved_at=None, expires_at=None )
        print(f"Story Review {new_story.id} created for {animal_id}. Needs approval.")
        return JsonResponse({"success": True, "message": "限時動態心得已提交，待審核後將顯示"})
    except Exception as e: print(f"Error creating story review: {e}"); traceback.print_exc(); return JsonResponse({"success": False, "error": "儲存限時動態心得時發生內部錯誤"}, status=500)

# --- Add Regular Review View (保持原始) ---
@login_required
def add_review(request):
    if request.method == "POST":
        print(">>> Handling POST Request for Adding Regular Review <<<")
        animal_id = request.POST.get("animal_id")
        if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
        try: animal = get_object_or_404(Animal, id=animal_id)
        except (Http404): return JsonResponse({"success": False, "error": "找不到指定的動物"}, status=404)
        except (ValueError, TypeError): return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)

        face_list = request.POST.getlist("face"); temperament_list = request.POST.getlist("temperament")
        scale_list = request.POST.getlist("scale"); content = request.POST.get("content", "").strip()
        age_str = request.POST.get("age"); cup_size_value = request.POST.get("cup_size","")
        errors = {}
        if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
        if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
        if not content: errors['content'] = "心得內容不能為空"
        age = None
        if age_str:
            # --- *** 原始的 try/except *** ---
            try:
                age = int(age_str)
                if age <= 0: errors['age'] = "年紀必須是正數"
            except (ValueError, TypeError):
                errors['age'] = "年紀必須是有效的數字"
            # -----------------------------
        if errors:
            error_message = "輸入無效: " + "; ".join([f"{k}: {v}" for k, v in errors.items()])
            return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)
        try:
            new_review = Review.objects.create(
                animal=animal, user=request.user, age=age,
                looks=request.POST.get("looks") or None, face=','.join(face_list),
                temperament=','.join(temperament_list), physique=request.POST.get("physique") or None,
                cup=request.POST.get("cup") or None, cup_size=cup_size_value or None,
                skin_texture=request.POST.get("skin_texture") or None, skin_color=request.POST.get("skin_color") or None,
                music=request.POST.get("music") or None, music_price=request.POST.get("music_price") or None,
                sports=request.POST.get("sports") or None, sports_price=request.POST.get("sports_price") or None,
                scale=','.join(scale_list), content=content, approved=False)
            print(f"Review {new_review.id} created for {animal_id}.")
            return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
        except Exception as e: print(f"Error creating review: {e}"); traceback.print_exc(); return JsonResponse({"success": False, "error": "儲存心得時發生內部錯誤"}, status=500)

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
                try: formatted_date = timezone.localtime(r.created_at).strftime("%Y-%m-%d")
                except Exception as date_err: print(f"Error formatting date: {date_err}")
            data.append({"id": r.id, "user": user_display_name, "totalCount": user_review_counts.get(r.user_id, 0), "age": r.age, "looks": r.looks, "face": r.face, "temperament": r.temperament, "physique": r.physique, "cup": r.cup, "cup_size": r.cup_size, "skin_texture": r.skin_texture, "skin_color": r.skin_color, "music": r.music, "music_price": r.music_price, "sports": r.sports, "sports_price": r.sports_price, "scale": r.scale, "content": r.content, "created_at": formatted_date})
        print(f"Returning {len(data)} reviews for animal {animal_id}.")
        return JsonResponse({"reviews": data})
    return JsonResponse({"error": "請求方法不支援"}, status=405)

# --- Pending Appointment Handling Views (保持原始) ---
@require_POST
@login_required
def add_pending_appointment(request):
    animal_id = request.POST.get("animal_id")
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    try: animal = get_object_or_404(Animal, id=animal_id)
    except Http404: return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
    except (ValueError, TypeError): return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    user = request.user
    try:
        obj, created = PendingAppointment.objects.get_or_create(user=user, animal=animal)
        pending_count = PendingAppointment.objects.filter(user=user).count()
        message = f"{animal.name} 已加入待約清單" if created else f"{animal.name} 已在待約清單中"
        print(f"Pending: {'Added' if created else 'Exists'} for {animal_id} by {user.username}. Count: {pending_count}")
        return JsonResponse({"success": True, "message": message, "pending_count": pending_count})
    except Exception as e: print(f"Error adding pending: {e}"); traceback.print_exc(); return JsonResponse({"success": False, "error": "加入待約時發生錯誤"}, status=500)

@require_POST
@login_required
def remove_pending(request):
    animal_id = request.POST.get("animal_id")
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    user = request.user
    try:
        try: animal_id_int = int(animal_id)
        except (ValueError, TypeError): raise ValueError("無效的動物 ID 格式")
        deleted_count, _ = PendingAppointment.objects.filter(user=user, animal_id=animal_id_int).delete()
        pending_count = PendingAppointment.objects.filter(user=user).count()
        if deleted_count == 0:
            animal_exists = Animal.objects.filter(id=animal_id_int).exists()
            if not animal_exists: return JsonResponse({"success": False, "error": "找不到該動物", "pending_count": pending_count}, status=404)
            else: return JsonResponse({"success": False, "error": "該待約項目不存在", "pending_count": pending_count}, status=404)
        animal_name = Animal.objects.filter(id=animal_id_int).values_list('name', flat=True).first() or "該美容師"
        print(f"Pending removed for {animal_id_int} by {user.username}. Count: {pending_count}")
        return JsonResponse({"success": True, "message": f"{animal_name} 待約項目已移除", "pending_count": pending_count, "animal_id": animal_id_int})
    except ValueError as ve: print(f"Error removing pending: {ve}"); current_count = PendingAppointment.objects.filter(user=user).count(); return JsonResponse({"success": False, "error": str(ve), "pending_count": current_count}, status=400)
    except Exception as e: print(f"Error removing pending: {e}"); traceback.print_exc(); current_count = PendingAppointment.objects.filter(user=user).count(); return JsonResponse({"success": False, "error": "移除待約時發生錯誤", "pending_count": current_count}, status=500)

# --- Note Handling Views (保持原始) ---
@require_POST
@login_required
def add_note(request):
    animal_id = request.POST.get("animal_id"); content = request.POST.get("content", "").strip(); note_id_from_post = request.POST.get("note_id")
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)
    try: animal = get_object_or_404(Animal, id=animal_id)
    except Http404: return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
    except (ValueError, TypeError): return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    user = request.user; note = None; created = False
    try:
        if note_id_from_post:
             try: note = Note.objects.get(id=note_id_from_post, user=user, animal=animal); note.content = content; note.save(); created = False; print(f"Note {note.id} updated.")
             except Note.DoesNotExist: return JsonResponse({"success": False, "error": "找不到要更新的筆記或無權限"}, status=404)
        else: note, created = Note.objects.update_or_create(user=user, animal=animal, defaults={"content": content}); print(f"Note {'created' if created else 'updated'}. ID: {note.id}.")
        message = "筆記已新增" if created else "筆記已更新"
        print(f"Note for {animal_id} by {user.username}: {'Created' if created else 'Updated'}.")
        return JsonResponse({"success": True, "message": message, "note_id": note.id, "note_content": note.content, "animal_id": animal.id})
    except Exception as e: print(f"Error add/update note: {e}"); traceback.print_exc(); return JsonResponse({"success": False, "error": "儲存筆記時發生錯誤"}, status=500)

@require_POST
@login_required
def delete_note(request):
    note_id = request.POST.get("note_id")
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    user = request.user
    try:
        try: note_id_int = int(note_id)
        except (ValueError, TypeError): raise ValueError("無效的筆記 ID 格式")
        note_to_delete = get_object_or_404(Note, id=note_id_int, user=user)
        animal_id = note_to_delete.animal_id; deleted_count, _ = note_to_delete.delete()
        if deleted_count == 0: return JsonResponse({"success": False, "error": "刪除失敗"})
        print(f"Note {note_id_int} deleted for {animal_id} by {user.username}.")
        return JsonResponse({"success": True, "message": "筆記已刪除", "animal_id": animal_id})
    except Http404: return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve: return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e: print(f"Error deleting note: {e}"); traceback.print_exc(); return JsonResponse({"success": False, "error": "刪除筆記時發生錯誤"}, status=500)

@require_POST
@login_required
def update_note(request):
    note_id = request.POST.get("note_id"); content = request.POST.get("content", "").strip();
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)
    user = request.user
    try:
        try: note_id_int = int(note_id)
        except (ValueError, TypeError): raise ValueError("無效的筆記 ID 格式")
        note = get_object_or_404(Note.objects.select_related('animal'), id=note_id_int, user=user)
        animal = note.animal; note.content = content; note.save()
        print(f"Note {note_id_int} updated for {animal.id} by {user.username}.")
        return JsonResponse({"success": True, "message": "筆記已更新", "note_id": note.id, "note_content": note.content, "animal_id": animal.id})
    except Http404: return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve: return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e: print(f"Error updating note: {e}"); traceback.print_exc(); return JsonResponse({"success": False, "error": "更新筆記時發生錯誤"}, status=500)

# --- AJAX View for Active Stories (保持原始) ---
@require_GET
def ajax_get_active_stories(request):
    print(">>> Handling AJAX Request for Active Story Reviews <<<")
    try:
        now = timezone.now()
        active_stories_query = StoryReview.objects.filter(
            Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True), # Q obj first
            approved=True, expires_at__gt=now, animal__is_active=True)
        active_stories_query = active_stories_query.select_related('animal', 'animal__hall', 'user')
        active_stories = active_stories_query.order_by('-approved_at')
        stories_data = []
        for story in active_stories:
            animal = story.animal; user = story.user
            stories_data.append({'id': story.id, 'animal_id': animal.id, 'animal_name': animal.name,
                'animal_photo_url': animal.photo.url if animal.photo else None, 'hall_name': animal.hall.name if animal.hall else '未知館別',
                'user_name': user.first_name or user.username, 'remaining_time': story.remaining_time_display,})
        return JsonResponse({'stories': stories_data})
    except Exception as e: print(f"!!! Error in ajax_get_active_stories: {e} !!!"); traceback.print_exc(); return JsonResponse({'error': '無法載入限時動態'}, status=500)

# --- AJAX View for Story Detail (保持原始) ---
@require_GET
def ajax_get_story_detail(request, story_id):
    print(f">>> Handling AJAX Request for Story Detail (ID: {story_id}) <<<")
    try:
        story = get_object_or_404(StoryReview.objects.filter(
                Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True),
                approved=True, expires_at__gt=timezone.now(), animal__is_active=True,
            ).select_related('animal', 'animal__hall', 'user'), pk=story_id)
        animal = story.animal; user = story.user; approved_at_display = ""
        if story.approved_at:
            try: approved_at_display = format_date(timezone.localtime(story.approved_at), 'Y-m-d H:i')
            except Exception as date_err: print(f"Warn: Formatting approved_at: {date_err}")
        story_data = {'id': story.id, 'animal_id': animal.id, 'animal_name': animal.name,
            'animal_photo_url': animal.photo.url if animal.photo else None, 'hall_name': animal.hall.name if animal.hall else '未知館別',
            'user_name': user.first_name or user.username, 'remaining_time': story.remaining_time_display, 'approved_at_display': approved_at_display,
            'age': story.age, 'looks': story.looks, 'face': story.face, 'temperament': story.temperament, 'physique': story.physique, 'cup': story.cup,
            'cup_size': story.cup_size, 'skin_texture': story.skin_texture, 'skin_color': story.skin_color, 'music': story.music, 'music_price': story.music_price,
            'sports': story.sports, 'sports_price': story.sports_price, 'scale': story.scale, 'content': story.content,}
        print(f"    Returning details for story {story_id}.")
        return JsonResponse({'success': True, 'story': story_data})
    except Http404: print(f"    Story {story_id} not found/inactive."); return JsonResponse({'success': False, 'error': '找不到指定的限時動態、已過期或相關資料已停用'}, status=404)
    except Exception as e: print(f"!!! Error in ajax_get_story_detail for ID {story_id}: {e} !!!"); traceback.print_exc(); return JsonResponse({'success': False, 'error': '無法載入限時動態詳情'}, status=500)

# --- AJAX View for Weekly Schedule Images (保持原始) ---
@require_GET
def ajax_get_weekly_schedule(request):
    hall_id = request.GET.get('hall_id')
    print(f">>> Handling AJAX Request for Weekly Schedule (Hall ID: {hall_id}) <<<")
    if not hall_id: return JsonResponse({'success': False, 'error': '缺少館別 ID'}, status=400)
    try: hall_id_int = int(hall_id); hall = get_object_or_404(Hall, id=hall_id_int, is_active=True); hall_name = hall.name
    except (ValueError, TypeError): return JsonResponse({'success': False, 'error': '無效的館別 ID 格式'}, status=400)
    except Http404:
        try: hall_name = Hall.objects.get(id=hall_id_int).name
        except Hall.DoesNotExist: hall_name = '此館別'
        print(f"    Hall {hall_id} not found or is inactive.")
        return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': hall_name, 'message': f'{hall_name} 目前已停用或不存在'}, status=404)
    try:
        schedules = WeeklySchedule.objects.filter(hall_id=hall_id_int).order_by('order')
        schedule_urls = [s.schedule_image.url for s in schedules if s.schedule_image]
        if schedule_urls: print(f"    Found {len(schedule_urls)} weekly images for Hall {hall_id}."); return JsonResponse({'success': True, 'schedule_urls': schedule_urls, 'hall_name': hall_name})
        else: print(f"    No valid weekly images for active Hall {hall_id}."); return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': hall_name, 'message': f'{hall_name} 尚未上傳本週班表圖片'})
    except Exception as e: print(f"!!! Error fetching weekly schedule: {e} !!!"); traceback.print_exc(); return JsonResponse({'success': False, 'error': '載入每週班表時發生伺服器錯誤'}, status=500)

# --- AJAX View for Hall of Fame (保持原始) ---
@require_GET
def ajax_get_hall_of_fame(request):
    print(">>> Handling AJAX Request for Hall of Fame <<<")
    try:
        top_users = Review.objects.filter(approved=True).values('user', 'user__username', 'user__first_name').annotate(review_count=Count('id')).order_by('-review_count')[:10]
        hall_of_fame_data = []
        for rank, user_data in enumerate(top_users, 1):
            user_display_name = user_data.get('user__first_name') or user_data.get('user__username')
            if not user_display_name or not user_display_name.strip(): user_display_name = f"用戶_{user_data.get('user', 'N/A')}"
            hall_of_fame_data.append({'rank': rank, 'user_name': user_display_name, 'review_count': user_data.get('review_count', 0)})
        print(f"    Returning {len(hall_of_fame_data)} users for Hall of Fame.")
        return JsonResponse({'users': hall_of_fame_data})
    except Exception as e: print(f"!!! Error in ajax_get_hall_of_fame: {e} !!!"); traceback.print_exc(); return JsonResponse({'error': '無法載入紓壓名人堂'}, status=500)