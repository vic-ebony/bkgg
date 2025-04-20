# D:\bkgg\mybackend\myapp\views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateformat import format as format_date
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
# --- 確保導入了所有需要的模塊 ---
from django.db.models import Count, Q, Prefetch, Max, F, OuterRef, Subquery, Value, CharField, Case, When
from django.db.models.functions import Coalesce
from django.db import transaction
from django.core.exceptions import ValidationError # <<< 導入 ValidationError
# --- ---
from django.views.decorators.http import require_POST, require_GET
from django.template.loader import render_to_string
from .models import (
    Animal, Hall, Review, PendingAppointment, Note, Announcement,
    StoryReview, WeeklySchedule, ReviewFeedback, UserTitleRule, UserProfile,
    SiteConfiguration # <<< 導入 SiteConfiguration
)
import traceback
import html
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.contrib import messages
from .forms import MergeTransferForm
from .utils import get_user_title_from_count
from collections import defaultdict

logger = logging.getLogger(__name__)
User = get_user_model()

try:
    from schedule_parser.models import DailySchedule
    SCHEDULE_PARSER_ENABLED = True
except ImportError:
    print("WARNING: schedule_parser app or DailySchedule model not found. Daily schedule features will be disabled.")
    SCHEDULE_PARSER_ENABLED = False
    DailySchedule = None

# --- render_animal_rows function (保持不變) ---
def render_animal_rows(request, animals_qs, fetch_daily_slots=False):
    """Renders HTML table rows for a queryset of Animals."""
    animal_daily_slots = {}
    animal_ids_on_page = [a.id for a in animals_qs if a] # Filter out None animals

    if fetch_daily_slots and SCHEDULE_PARSER_ENABLED and DailySchedule is not None and animal_ids_on_page:
        try:
            daily_schedules_qs = DailySchedule.objects.filter(
                animal_id__in=animal_ids_on_page
            ).values('animal_id', 'time_slots')
            animal_daily_slots = {schedule['animal_id']: schedule['time_slots'] for schedule in daily_schedules_qs}
        except Exception as slot_err:
            logger.error(f"Error fetching daily slots inside render_animal_rows: {slot_err}", exc_info=True)

    pending_ids = set()
    notes_by_animal = {}
    if request.user.is_authenticated and animal_ids_on_page:
        try:
            pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user, animal_id__in=animal_ids_on_page))
            notes_qs = Note.objects.filter(user=request.user, animal_id__in=animal_ids_on_page)
            notes_by_animal = {str(note.animal_id): note for note in notes_qs}
        except Exception as e:
            logger.error(f"Error fetching pending/notes for user {request.user.username}: {e}", exc_info=True)

    rendered_rows_html_list = []
    for animal_instance in animals_qs:
        if not animal_instance:
             logger.warning("Skipping None animal instance in render_animal_rows")
             continue

        review_count = getattr(animal_instance, 'approved_review_count', None)
        if review_count is None:
            try:
                review_count = Review.objects.filter(animal=animal_instance, approved=True).count()
            except Exception as count_err:
                logger.error(f"Error counting reviews for animal {animal_instance.id}: {count_err}", exc_info=True)
                review_count = 0

        animal_id_str = str(animal_instance.id)
        today_slots_for_template = animal_daily_slots.get(animal_instance.id)
        note_instance = notes_by_animal.get(animal_id_str)

        row_context = {
            'animal': animal_instance,
            'user': request.user,
            'today_slots': today_slots_for_template,
            'is_pending': animal_id_str in pending_ids,
            'note': note_instance,
            'review_count': review_count,
        }
        try:
            rendered_html = render_to_string('myapp/partials/_animal_table_rows.html', row_context, request=request)
            rendered_rows_html_list.append(rendered_html)
        except Exception as render_err:
            logger.error(f"Error rendering partial _animal_table_rows.html for animal {animal_instance.id}: {render_err}", exc_info=True)
            rendered_rows_html_list.append(f'<tr><td colspan="5" style="color:red; font-style:italic;">渲染錯誤: {animal_instance.name} (ID: {animal_instance.id})</td></tr>')

    return "".join(rendered_rows_html_list)


# --- Home View (保持不變) ---
def home(request):
    is_ajax_request = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    fetch_type = request.GET.get('fetch')
    is_daily_schedule_ajax = is_ajax_request and fetch_type == 'daily_schedule'

    if is_daily_schedule_ajax:
        hall_id = request.GET.get('hall_id')
        logger.debug(f"Received AJAX request for daily schedule, hall_id: {hall_id}")
        if not hall_id:
            logger.warning("Daily schedule AJAX request missing hall_id.")
            return JsonResponse({'error': '請求缺少館別 ID (hall_id)'}, status=400)
        try:
            hall_id_int = int(hall_id)
            selected_hall = get_object_or_404(Hall, id=hall_id_int, is_active=True)
            logger.info(f"Fetching daily schedule for Hall: {selected_hall.name} (ID: {hall_id_int})")
        except (ValueError, TypeError):
            logger.warning(f"Invalid hall_id format received: {hall_id}")
            return JsonResponse({'error': '無效的館別 ID 格式'}, status=400)
        except Http404:
            logger.warning(f"Hall ID {hall_id} not found or not active for daily schedule request.")
            hall_name = Hall.objects.filter(id=hall_id_int).values_list('name', flat=True).first() or f"館別 {hall_id}"
            return JsonResponse({'table_html': f'<tr class="empty-table-message"><td colspan="5">{hall_name} 不存在或未啟用</td></tr>', 'first_animal': {}}, status=404)

        try:
            if not SCHEDULE_PARSER_ENABLED or DailySchedule is None:
                 logger.warning("Daily schedule feature accessed but schedule_parser is disabled or DailySchedule model is None.")
                 raise RuntimeError("DailySchedule is not available.")

            prefetch_animal = Prefetch(
                'animal',
                queryset=Animal.objects.select_related('hall').filter(
                    is_active=True
                ).annotate(
                    approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
                )
            )
            daily_schedules_qs = DailySchedule.objects.filter(
                hall_id=hall_id_int
            ).prefetch_related(prefetch_animal).order_by('animal__order', 'animal__name')

            animals_for_render = [ds.animal for ds in daily_schedules_qs if ds.animal]
            logger.debug(f"Found {len(animals_for_render)} active animals with daily schedules for Hall ID {hall_id_int}")
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
                    logger.warning(f"Error getting first animal data for daily schedule (Animal ID {first_animal_obj.id}): {e}")

            return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})

        except RuntimeError as r_err:
             logger.warning(f"Daily schedule feature accessed but disabled: {r_err}")
             error_html = f'<tr class="empty-table-message"><td colspan="5">每日班表功能未啟用</td></tr>'
             return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=501)
        except Exception as e:
            logger.error(f"Error during Daily Schedule AJAX processing for Hall ID {hall_id}: {e}", exc_info=True)
            error_html = f'<tr class="empty-table-message"><td colspan="5">載入班表時發生內部錯誤</td></tr>'
            return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)

    elif is_ajax_request:
        logger.debug(f"Received AJAX request, fetch_type: {fetch_type}")
        if fetch_type == 'pending': return ajax_get_pending_list(request)
        elif fetch_type == 'my_notes': return ajax_get_my_notes(request)
        elif fetch_type == 'latest_reviews': return ajax_get_latest_reviews(request)
        elif fetch_type == 'recommendations': return ajax_get_recommendations(request)
        else:
            logger.error(f"Unknown fetch_type '{fetch_type}' received on home URL via AJAX.")
            return JsonResponse({'error': '未知的請求類型'}, status=400)

    else:
        logger.info("Rendering full home page (index.html)")
        halls = Hall.objects.filter(is_active=True, is_visible=True).order_by('order', 'name')
        context = {'halls': halls, 'user': request.user}
        initial_pending_count = 0

        if request.user.is_authenticated:
            try:
                initial_pending_count = PendingAppointment.objects.filter(user=request.user).count()
                logger.debug(f"Initial pending count for user {request.user.username}: {initial_pending_count}")
            except Exception as e:
                logger.error(f"Error fetching initial pending count for user {request.user.username}: {e}")
        context['pending_count'] = initial_pending_count

        try:
            context['announcement'] = Announcement.objects.filter(is_active=True).order_by('-updated_at').first()
        except Exception as e:
            logger.error(f"Error fetching announcement: {e}")
            context['announcement'] = None

        featured_animal = None
        site_logo_url = None

        try:
            featured_animal = Animal.objects.select_related('hall').annotate(
                 approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
            ).filter(
                 is_featured=True,
                 is_active=True,
                 photo__isnull=False
             ).exclude(photo='').order_by('order', 'name').first()
            if featured_animal:
                logger.debug(f"Featured animal found: {featured_animal.name}")
            else:
                 logger.debug("No featured animal found.")
        except Exception as e:
             logger.error(f"Error fetching featured animal: {e}", exc_info=True)

        try:
            site_config = SiteConfiguration.get_solo()
            site_logo_url = site_config.site_logo.url if site_config.site_logo else None
            logger.debug(f"Site logo URL: {site_logo_url}")
        except SiteConfiguration.DoesNotExist:
            logger.warning("SiteConfiguration object does not exist.")
        except AttributeError:
             logger.warning("SiteConfiguration.get_solo() not found. Assuming django-solo is not used or SiteConfiguration is not a SingletonModel.")
        except Exception as e:
             logger.error(f"Error fetching site configuration/logo: {e}", exc_info=True)

        context['featured_animal'] = featured_animal
        context['site_logo_url'] = site_logo_url

        login_error = request.session.pop('login_error', None)
        if login_error:
            context['login_error'] = login_error
            logger.debug(f"Login error message passed to context: {login_error}")

        context['selected_hall_id'] = 'all'
        template_path = 'myapp/index.html'

        try:
            return render(request, template_path, context)
        except Exception as e:
            logger.critical(f"CRITICAL ERROR rendering main template {template_path}: {e}", exc_info=True)
            raise


# --- AJAX Views (Pending, Notes, Latest Reviews, Recommendations) (保持不變) ---
@login_required
@require_GET
def ajax_get_pending_list(request):
    logger.info(f"User {request.user.username} requesting pending list.")
    try:
        pending_appointments_qs = PendingAppointment.objects.filter(
            user=request.user
        ).select_related(
            'animal', 'animal__hall'
        ).order_by('-added_at')

        animal_ids = list(pending_appointments_qs.values_list('animal_id', flat=True))
        animals_qs = Animal.objects.filter(
            id__in=animal_ids
        ).filter(
            Q(is_active=True) & (Q(hall__isnull=True) | Q(hall__is_active=True))
        ).annotate(
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        )
        animals_dict = {a.id: a for a in animals_qs}
        animals_list_ordered = [animals_dict.get(pa.animal_id) for pa in pending_appointments_qs if pa.animal_id in animals_dict]
        logger.debug(f"Found {len(animals_list_ordered)} active pending animals for user {request.user.username}.")

        table_html = render_animal_rows(request, animals_list_ordered, fetch_daily_slots=True)

        first_animal_data = {}
        if animals_list_ordered:
            first_animal = animals_list_ordered[0]
            first_animal_data = {
                'photo_url': first_animal.photo.url if first_animal.photo else '',
                'name': first_animal.name or '',
                'introduction': first_animal.introduction or ''
            }

        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})

    except Exception as e:
        logger.error(f"Error in ajax_get_pending_list for user {request.user.username}: {e}", exc_info=True)
        error_html = '<tr class="empty-table-message"><td colspan="5">載入待約清單時發生錯誤</td></tr>'
        return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)

@login_required
@require_GET
def ajax_get_my_notes(request):
    hall_id = request.GET.get('hall_id')
    selected_hall_id = hall_id or 'all'
    logger.info(f"User {request.user.username} requesting notes. Hall filter: {selected_hall_id}")

    try:
        notes_base_qs = Note.objects.filter(
            user=request.user
        ).filter(
            Q(animal__is_active=True) & (Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True))
        ).select_related('animal', 'animal__hall')

        if selected_hall_id != "all":
            try:
                hall_id_int = int(selected_hall_id)
                notes_qs = notes_base_qs.filter(animal__hall_id=hall_id_int)
                logger.debug(f"Filtering notes by Hall ID: {hall_id_int}")
            except (ValueError, TypeError):
                logger.warning(f"Invalid hall_id '{selected_hall_id}' received for notes filter.")
                return JsonResponse({'error': '無效的館別 ID 格式'}, status=400)
        else:
            notes_qs = notes_base_qs.all()
            logger.debug("Fetching all notes (no hall filter).")

        notes_qs = notes_qs.order_by('-updated_at')
        animal_ids = list(notes_qs.values_list('animal_id', flat=True))
        animals_list_ordered = []

        if animal_ids:
            animals_qs = Animal.objects.filter(
                id__in=animal_ids
            ).annotate(
                approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
            )
            animals_dict = {a.id: a for a in animals_qs}
            animals_list_ordered = [animals_dict.get(note.animal_id) for note in notes_qs if note.animal_id in animals_dict]
            logger.debug(f"Found {len(animals_list_ordered)} animals with notes matching filter.")

        table_html = render_animal_rows(request, animals_list_ordered, fetch_daily_slots=True)

        first_animal_data = {}
        if animals_list_ordered:
            first_animal = animals_list_ordered[0]
            first_animal_data = {
                'photo_url': first_animal.photo.url if first_animal.photo else '',
                'name': first_animal.name or '',
                'introduction': first_animal.introduction or ''
            }

        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})

    except Exception as e:
        logger.error(f"Error in ajax_get_my_notes for user {request.user.username} (Hall: {selected_hall_id}): {e}", exc_info=True)
        error_html = '<tr class="empty-table-message"><td colspan="5">載入筆記時發生錯誤</td></tr>'
        return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)


@require_GET
def ajax_get_latest_reviews(request):
    logger.info("Requesting latest reviews.")
    try:
        latest_reviewed_animals_subquery = Review.objects.filter(
            animal=OuterRef('pk'),
            approved=True
        ).order_by('-approved_at', '-created_at').values('approved_at')[:1]

        latest_created_time_subquery = Review.objects.filter(
             animal=OuterRef('pk'),
             approved=True
        ).order_by('-approved_at', '-created_at').values('created_at')[:1]

        latest_reviewed_animals_qs = Animal.objects.filter(
            is_active=True,
            hall__is_active=True,
            reviews__approved=True
        ).annotate(
            latest_approved_time=Subquery(latest_reviewed_animals_subquery),
            latest_created_time=Subquery(latest_created_time_subquery),
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        ).filter(
            latest_approved_time__isnull=False
        ).select_related('hall').order_by('-latest_approved_time', '-latest_created_time')[:20]

        logger.debug(f"Found {latest_reviewed_animals_qs.count()} animals for latest reviews list (ordered by approved_at).")

        table_html = render_animal_rows(request, latest_reviewed_animals_qs, fetch_daily_slots=True)

        first_animal_data = {}
        if latest_reviewed_animals_qs.exists():
            first_animal = latest_reviewed_animals_qs.first()
            first_animal_data = {
                'photo_url': first_animal.photo.url if first_animal.photo else '',
                'name': first_animal.name or '',
                'introduction': first_animal.introduction or ''
            }

        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})

    except Exception as e:
        logger.error(f"Error in ajax_get_latest_reviews: {e}", exc_info=True)
        error_html = '<tr class="empty-table-message"><td colspan="5">載入最新心得時發生錯誤</td></tr>'
        return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)


@require_GET
def ajax_get_recommendations(request):
    logger.info("Requesting recommendations.")
    try:
        recommended_animals_qs = Animal.objects.filter(
            is_active=True,
            is_recommended=True,
            hall__is_active=True
        ).select_related('hall').annotate(
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        ).order_by('hall__order', 'order', 'name')

        logger.debug(f"Found {recommended_animals_qs.count()} recommended animals.")
        table_html = render_animal_rows(request, recommended_animals_qs, fetch_daily_slots=True)

        first_animal_data = {}
        if recommended_animals_qs.exists():
            first_animal = recommended_animals_qs.first()
            first_animal_data = {
                'photo_url': first_animal.photo.url if first_animal.photo else '',
                'name': first_animal.name or '',
                'introduction': first_animal.introduction or ''
            }

        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})

    except Exception as e:
        logger.error(f"Error in ajax_get_recommendations: {e}", exc_info=True)
        error_html = '<tr class="empty-table-message"><td colspan="5">載入每日推薦時發生錯誤</td></tr>'
        return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)

# --- User Authentication Views (保持不變) ---
# ... (user_login, user_logout 函數代碼) ...
def user_login(request):
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        logger.info(f"Login attempt for username: '{username}'")
        if not username or not password:
            logger.warning("Login attempt failed: Username or password missing.")
            request.session['login_error'] = '請輸入帳號和密碼'
            return redirect('myapp:home')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            request.session.pop('login_error', None)
            logger.info(f"User '{username}' logged in successfully.")
            return redirect('myapp:home')
        else:
            logger.warning(f"Login failed for username '{username}': Invalid credentials.")
            request.session['login_error'] = '帳號或密碼錯誤'
            return redirect('myapp:home')
    return redirect('myapp:home')

@require_POST
@login_required
def user_logout(request):
    user_display = request.user.username if request.user.is_authenticated else "N/A"
    logout(request)
    logger.info(f"User '{user_display}' logged out.")
    return redirect('myapp:home')

# --- Add Story Review View (保持不變) ---
# ... (add_story_review 函數代碼) ...
@login_required
@require_POST
def add_story_review(request):
    animal_id = request.POST.get("animal_id")
    user = request.user
    logger.info(f"User {user.username} attempting to add story review for animal ID: {animal_id}")
    if not animal_id:
        logger.warning("Add story review failed: Missing animal ID.")
        return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    try:
        animal = get_object_or_404(Animal, id=animal_id)
        logger.debug(f"Found animal: {animal.name} for story review.")
    except Http404:
        logger.warning(f"Add story review failed: Animal ID {animal_id} not found.")
        return JsonResponse({"success": False, "error": "找不到該美容師"}, status=404)
    except (ValueError, TypeError):
        logger.warning(f"Add story review failed: Invalid animal ID format: {animal_id}.")
        return JsonResponse({"success": False, "error": "無效的美容師 ID"}, status=400)

    face_list = request.POST.getlist("face")
    temperament_list = request.POST.getlist("temperament")
    scale_list = request.POST.getlist("scale")
    content = request.POST.get("content", "").strip()
    age_str = request.POST.get("age")
    cup_size_value = request.POST.get("cup_size", "")
    errors = {}
    if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
    if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
    if not content: errors['content'] = "心得內容不能為空"
    age = None
    if age_str:
        try:
            age = int(age_str)
            if age <= 0: raise ValueError("Age must be positive")
        except (ValueError, TypeError):
            errors['age'] = "年紀必須是有效的正整數"
    if errors:
        error_message = "輸入無效: " + "; ".join([f"{k}: {v}" for k, v in errors.items()])
        logger.warning(f"Add story review validation failed for user {user.username}: {errors}")
        return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)

    try:
        new_story = StoryReview.objects.create(
            animal=animal, user=user, age=age,
            looks=request.POST.get("looks") or None,
            face=','.join(filter(None, face_list)),
            temperament=','.join(filter(None, temperament_list)),
            physique=request.POST.get("physique") or None,
            cup=request.POST.get("cup") or None,
            cup_size=cup_size_value or None,
            skin_texture=request.POST.get("skin_texture") or None,
            skin_color=request.POST.get("skin_color") or None,
            music=request.POST.get("music") or None,
            music_price=request.POST.get("music_price") or None,
            sports=request.POST.get("sports") or None,
            sports_price=request.POST.get("sports_price") or None,
            scale=','.join(filter(None, scale_list)),
            content=content, approved=False, approved_at=None, expires_at=None, reward_granted=False
        )
        logger.info(f"Story Review {new_story.id} created for animal {animal_id} by user {user.username}. Needs approval.")
        return JsonResponse({"success": True, "message": "限時動態心得已提交，待審核後將顯示"})
    except Exception as e:
        logger.error(f"Error creating story review for animal {animal_id} by user {user.username}: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": "儲存限時動態心得時發生內部錯誤"}, status=500)

# --- add_review 函數 (GET 部分已修改, POST 保持不變) ---
def add_review(request):
    if request.method == "POST":
        if not request.user.is_authenticated:
            logger.warning("Anonymous user attempted to post a review.")
            return JsonResponse({"success": False, "error": "請先登入才能提交心得"}, status=401)
        user = request.user
        animal_id = request.POST.get("animal_id")
        logger.info(f"User {user.username} attempting to add review for animal ID: {animal_id}")
        if not animal_id:
            logger.warning("Add review failed: Missing animal ID.")
            return JsonResponse({"success": False, "error": "缺少美容師 ID"}, status=400)
        try:
            animal = get_object_or_404(Animal, id=animal_id)
            logger.debug(f"Found animal: {animal.name} for review.")
        except Http404:
            logger.warning(f"Add review failed: Animal ID {animal_id} not found.")
            return JsonResponse({"success": False, "error": "找不到指定的美容師"}, status=404)
        except (ValueError, TypeError):
            logger.warning(f"Add review failed: Invalid animal ID format: {animal_id}.")
            return JsonResponse({"success": False, "error": "無效的美容師 ID"}, status=400)

        face_list = request.POST.getlist("face")
        temperament_list = request.POST.getlist("temperament")
        scale_list = request.POST.getlist("scale")
        content = request.POST.get("content", "").strip()
        age_str = request.POST.get("age")
        cup_size_value = request.POST.get("cup_size", "")
        errors = {}
        if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
        if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
        if not content: errors['content'] = "心得內容不能為空"
        age = None
        if age_str:
            try:
                age = int(age_str)
                if age <= 0: raise ValueError("Age must be positive")
            except (ValueError, TypeError):
                errors['age'] = "年紀必須是有效的正整數"
        if errors:
            error_message = "輸入無效: " + "; ".join([f"{k}: {v}" for k, v in errors.items()])
            logger.warning(f"Add review validation failed for user {user.username}: {errors}")
            return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)

        try:
            new_review = Review.objects.create(
                animal=animal, user=user, age=age,
                looks=request.POST.get("looks") or None,
                face=','.join(filter(None, face_list)),
                temperament=','.join(filter(None, temperament_list)),
                physique=request.POST.get("physique") or None,
                cup=request.POST.get("cup") or None,
                cup_size=cup_size_value or None,
                skin_texture=request.POST.get("skin_texture") or None,
                skin_color=request.POST.get("skin_color") or None,
                music=request.POST.get("music") or None,
                music_price=request.POST.get("music_price") or None,
                sports=request.POST.get("sports") or None,
                sports_price=request.POST.get("sports_price") or None,
                scale=','.join(filter(None, scale_list)),
                content=content,
                approved=False,
                approved_at=None,
                reward_granted=False
            )
            logger.info(f"Review {new_review.id} created for animal {animal_id} by user {user.username}. Needs approval.")
            return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
        except Exception as e:
            logger.error(f"Error creating review for animal {animal_id} by user {user.username}: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": "儲存心得時發生內部錯誤"}, status=500)

    elif request.method == "GET":
        animal_id = request.GET.get("animal_id")
        logger.debug(f"Fetching reviews for animal_id: {animal_id}")

        if not animal_id:
            logger.warning("Fetch reviews request missing animal_id.")
            return JsonResponse({"error": "缺少 animal_id"}, status=400)

        try:
            animal = get_object_or_404(
                Animal.objects.filter(
                    Q(is_active=True) & (Q(hall__isnull=True) | Q(hall__is_active=True))
                ),
                id=animal_id
            )
            logger.debug(f"Found animal {animal.name} to fetch reviews for.")
        except (Http404, ValueError, TypeError):
            logger.warning(f"Animal not found or invalid ID for fetching reviews: {animal_id}")
            return JsonResponse({"error": "找不到或無效的 animal_id"}, status=404)

        reviews_qs = Review.objects.filter(
            animal=animal, approved=True
        ).select_related('user').annotate(
            good_to_have_you_count=Count('feedback', filter=Q(feedback__feedback_type='good_to_have_you')),
            good_looking_count=Count('feedback', filter=Q(feedback__feedback_type='good_looking'))
        ).order_by("-approved_at", "-created_at")

        user_ids = list(reviews_qs.values_list('user_id', flat=True).distinct())
        user_total_counts = {}
        user_titles = {}

        if user_ids:
             logger.debug(f"Fetching total counts for user IDs: {user_ids}")
             try:
                 review_counts_query = Review.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(count=Count('id'))
                 for item in review_counts_query: user_total_counts[item['user_id']] = user_total_counts.get(item['user_id'], 0) + item['count']
                 story_counts_query = StoryReview.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(count=Count('id'))
                 for item in story_counts_query: user_total_counts[item['user_id']] = user_total_counts.get(item['user_id'], 0) + item['count']
                 for user_id, total_count in user_total_counts.items():
                     user_titles[user_id] = get_user_title_from_count(total_count)
                 logger.debug(f"Calculated user titles: {user_titles}")
             except Exception as count_err:
                 logger.error(f"Error fetching user total review counts: {count_err}", exc_info=True)

        data = []
        for r in reviews_qs:
            user_display_name = "匿名"; display_date = ""; user_title = None; author_id = None
            if hasattr(r, 'user') and r.user:
                user_display_name = r.user.first_name or r.user.username
                author_id = r.user.id
                user_title = user_titles.get(r.user_id)
            else:
                logger.warning(f"Review {r.id} is missing user information.")

            if r.approved_at:
                 try:
                     display_date = timezone.localtime(r.approved_at).strftime("%Y-%m-%d")
                 except Exception as date_err:
                     logger.error(f"Error formatting approved_at for review {r.id}: {date_err}")
                     display_date = "日期錯誤"
            elif r.created_at:
                 try:
                     display_date = timezone.localtime(r.created_at).strftime("%Y-%m-%d")
                     logger.warning(f"Review {r.id} is approved but missing approved_at, using created_at as fallback.")
                 except Exception as date_err:
                     logger.error(f"Error formatting created_at fallback for review {r.id}: {date_err}")
                     display_date = "日期錯誤"
            else:
                 display_date = "日期未知"

            data.append({
                "id": r.id, "author_id": author_id, "user": user_display_name, "user_title": user_title,
                "age": r.age, "looks": r.looks, "face": r.face, "temperament": r.temperament,
                "physique": r.physique, "cup": r.cup, "cup_size": r.cup_size,
                "skin_texture": r.skin_texture, "skin_color": r.skin_color,
                "music": r.music, "music_price": r.music_price,
                "sports": r.sports, "sports_price": r.sports_price,
                "scale": r.scale, "content": r.content,
                "display_date": display_date, # 使用 display_date
                "good_to_have_you_count": r.good_to_have_you_count,
                "good_looking_count": r.good_looking_count,
            })
        return JsonResponse({"reviews": data})

    logger.warning(f"Unsupported method {request.method} for add_review view.")
    return JsonResponse({"error": "請求方法不支援"}, status=405)


# --- *** 修改 add_pending_appointment 函數 (修正上限邏輯) *** ---
@require_POST
@login_required
def add_pending_appointment(request):
    animal_id = request.POST.get("animal_id")
    user = request.user
    logger.info(f"User {user.username} attempting to add pending appointment for animal ID: {animal_id}")

    if not animal_id:
        logger.warning("Add pending failed: Missing animal ID.")
        return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)

    created = False
    message = ""
    final_limit = '未知' # 代表上限
    animal = None
    current_count = 0 # 代表當前已使用數量

    try:
        with transaction.atomic():
            animal = get_object_or_404(Animal, id=animal_id)
            profile = UserProfile.objects.select_for_update().get(user=user)
            logger.debug(f"User {user.username} profile locked. Current pending limit (max): {profile.pending_list_limit}")

            # --- 獲取當前已有的待約數量 ---
            current_count = PendingAppointment.objects.filter(user=user).count()

            # --- 檢查是否已達上限 ---
            if current_count >= profile.pending_list_limit:
                logger.warning(f"User {user.username} failed to add pending: Limit reached ({current_count} >= {profile.pending_list_limit}).")
                return JsonResponse({
                    "success": False,
                    "error": f"待約清單已達上限 ({profile.pending_list_limit})！",
                    "pending_count": current_count, # 返回當前數量
                    "remaining_limit": profile.pending_list_limit # 返回上限
                }, status=403)

            # 嘗試創建，如果已存在則不做任何事
            obj, created = PendingAppointment.objects.get_or_create(user=user, animal=animal)

            if created:
                logger.info(f"Pending appointment CREATED for animal {animal_id} by user {user.username}.")
                message = f"{animal.name} 已加入待約清單"
                success_status = True
                current_count += 1 # 更新計數
            else:
                logger.info(f"Pending appointment for animal {animal_id} by user {user.username} already exists.")
                message = f"{animal.name} 已在待約清單中"
                success_status = True
                # 計數不變

            # 獲取最終上限值
            final_limit = profile.pending_list_limit

        # --- 事務外部 ---
        # current_count 和 final_limit 在事務內已確定

        return JsonResponse({
            "success": success_status,
            "message": message,
            "pending_count": current_count, # 回傳最新的已使用數量
            "remaining_limit": final_limit  # 回傳上限值
        })

    except UserProfile.DoesNotExist:
         logger.error(f"UserProfile not found for user {user.username} (ID: {user.id}) during add_pending (initial fetch)")
         return JsonResponse({"success": False, "error": "找不到使用者設定檔，無法檢查次數"}, status=500)
    except Http404:
        logger.warning(f"Add pending failed: Animal ID {animal_id} not found.")
        animal_name_fallback = f"美容師 #{animal_id}" if animal_id else "未知美容師"
        return JsonResponse({"success": False, "error": f"找不到 {animal_name_fallback}"}, status=404)
    except (ValueError, TypeError):
        logger.warning(f"Add pending failed: Invalid animal ID format: {animal_id}.")
        return JsonResponse({"success": False, "error": "無效的美容師 ID"}, status=400)
    except Exception as e:
        # 處理 unique constraint 的 fallback
        if 'unique constraint' in str(e) and 'myapp_pendingappointment' in str(e).lower():
            logger.warning(f"Unique constraint violation during add_pending for user {user.username}, animal {animal_id}. Assuming already exists.")
            try:
                pending_count = PendingAppointment.objects.filter(user=user).count()
                current_limit = UserProfile.objects.get(user=user).pending_list_limit
                try: animal_name = Animal.objects.get(id=animal_id).name
                except Animal.DoesNotExist: animal_name = f"美容師 #{animal_id}"
                except (ValueError, TypeError): animal_name = "未知美容師"

                return JsonResponse({
                    "success": True, "message": f"{animal_name} 已在待約清單中",
                    "pending_count": pending_count, "remaining_limit": current_limit
                })
            except UserProfile.DoesNotExist:
                 logger.error(f"UserProfile not found for user {user.username} during add_pending unique constraint fallback.")
                 return JsonResponse({"success": False, "error": "檢查待約狀態時發生錯誤"}, status=500)
            except Exception as fallback_e:
                  logger.error(f"Error in add_pending unique constraint fallback: {fallback_e}", exc_info=True)
                  return JsonResponse({"success": False, "error": "加入待約時發生未知錯誤"}, status=500)
        else:
            logger.error(f"Error adding pending appointment for user {user.username}, animal {animal_id}: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": "加入待約時發生錯誤"}, status=500)
# --- *** add_pending_appointment 函數修改結束 *** ---


# --- remove_pending (保持不變) ---
@require_POST
@login_required
def remove_pending(request):
    animal_id = request.POST.get("animal_id")
    user = request.user
    logger.info(f"User {user.username} attempting to remove pending appointment for animal ID: {animal_id}")
    if not animal_id:
        logger.warning("Remove pending failed: Missing animal ID.")
        return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    try:
        try: animal_id_int = int(animal_id)
        except (ValueError, TypeError):
            logger.warning(f"Remove pending failed: Invalid animal ID format: {animal_id}")
            raise ValueError("無效的美容師 ID 格式")
        deleted_count, _ = PendingAppointment.objects.filter(user=user, animal_id=animal_id_int).delete()
        pending_count = PendingAppointment.objects.filter(user=user).count() # 獲取刪除後的數量
        if deleted_count == 0:
            animal_exists = Animal.objects.filter(id=animal_id_int).exists()
            if not animal_exists:
                logger.warning(f"Remove pending failed: Animal ID {animal_id_int} does not exist.")
                return JsonResponse({"success": False, "error": "找不到該美容師", "pending_count": pending_count}, status=404)
            else:
                logger.warning(f"Remove pending failed: Pending item for animal ID {animal_id_int} not found for user {user.username}.")
                return JsonResponse({"success": False, "error": "該待約項目不存在", "pending_count": pending_count}, status=404)
        animal_name = Animal.objects.filter(id=animal_id_int).values_list('name', flat=True).first() or "該美容師"
        logger.info(f"Pending appointment removed for animal ID {animal_id_int} by user {user.username}. New count: {pending_count}")
        try:
            remaining_limit = UserProfile.objects.get(user=user).pending_list_limit # 獲取上限值
        except UserProfile.DoesNotExist:
            logger.error(f"UserProfile not found for user {user.username} when getting limit after remove_pending.")
            remaining_limit = '未知'
        return JsonResponse({
            "success": True, "message": f"{animal_name} 待約項目已移除",
            "pending_count": pending_count, # 返回刪除後的數量
            "animal_id": animal_id_int,
            "remaining_limit": remaining_limit # 返回上限值
        })
    except ValueError as ve:
        count = PendingAppointment.objects.filter(user=user).count()
        return JsonResponse({"success": False, "error": str(ve), "pending_count": count}, status=400)
    except UserProfile.DoesNotExist:
         logger.error(f"UserProfile not found for user {user.username} during remove_pending.")
         count = PendingAppointment.objects.filter(user=user).count()
         return JsonResponse({"success": False, "error": "找不到使用者設定檔", "pending_count": count}, status=500)
    except Exception as e:
        logger.error(f"Error removing pending appointment for user {user.username}, animal ID {animal_id}: {e}", exc_info=True)
        count = PendingAppointment.objects.filter(user=user).count()
        return JsonResponse({"success": False, "error": "移除待約時發生錯誤", "pending_count": count}, status=500)


# --- *** 修改 add_note 函數 (修正上限邏輯) *** ---
@require_POST
@login_required
def add_note(request):
    animal_id = request.POST.get("animal_id")
    content = request.POST.get("content", "").strip()
    user = request.user
    logger.info(f"User {user.username} attempting to add/update note for animal ID: {animal_id}")

    if not animal_id:
        logger.warning("Add/Update note failed: Missing animal ID.")
        return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    if not content:
        logger.warning("Add/Update note failed: Content is empty.")
        return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)

    note_instance = None
    created = False
    message = ""
    final_limit = '未知' # 代表上限
    final_notes_count = 0 # 代表已用數量

    try:
        with transaction.atomic():
            animal = get_object_or_404(Animal, id=animal_id)
            profile = UserProfile.objects.select_for_update().get(user=user)
            logger.debug(f"User {user.username} profile locked. Current notes limit (max): {profile.notes_limit}")

            existing_note = Note.objects.filter(user=user, animal=animal).first()
            current_notes_count = Note.objects.filter(user=user).count() # 計算不包含當前筆記的數量

            if not existing_note:
                # --- 創建新筆記 ---
                logger.debug("Attempting to create a new note.")
                # --- *** 檢查是否已達上限 *** ---
                if current_notes_count >= profile.notes_limit:
                     logger.warning(f"User {user.username} failed to create note: Limit reached ({current_notes_count} >= {profile.notes_limit}).")
                     raise ValidationError(f"筆記數量已達上限 ({profile.notes_limit})！")
                # --- *** 修改結束 *** ---

                note_instance = Note.objects.create(user=user, animal=animal, content=content)
                created = True
                logger.info(f"Note CREATED (ID: {note_instance.id}) for animal {animal_id} by user {user.username}.")

                # --- *** 修改：不再減少上限 *** ---
                # profile.notes_limit = F('notes_limit') - 1 # <--- 移除
                # profile.save(update_fields=['notes_limit']) # <--- 移除
                # --- *** 修改結束 *** ---
                message = "筆記已新增"
                final_notes_count = current_notes_count + 1
            else:
                # --- 更新現有筆記 ---
                logger.debug(f"Updating existing note (ID: {existing_note.id}).")
                note_instance = existing_note
                note_instance.content = content
                note_instance.save(update_fields=['content', 'updated_at'])
                created = False
                logger.info(f"Note UPDATED (ID: {note_instance.id}) for animal {animal_id} by user {user.username}.")
                message = "筆記已更新"
                final_notes_count = current_notes_count # 更新時數量不變

            # 讀取最終上限值
            final_limit = profile.notes_limit

        # --- 事務外部 ---
        # final_notes_count 和 final_limit 已確定

        return JsonResponse({
            "success": True,
            "message": message,
            "note_id": note_instance.id,
            "note_content": note_instance.content,
            "animal_id": animal.id,
            "notes_count": final_notes_count, # 回傳最新的已用數量
            "remaining_limit": final_limit    # 回傳上限值
        })

    except UserProfile.DoesNotExist:
         logger.error(f"UserProfile not found for user {user.username} (ID: {user.id}) during add_note (initial fetch)")
         return JsonResponse({"success": False, "error": "找不到使用者設定檔，無法執行操作"}, status=500)
    except Http404:
        logger.warning(f"Add/Update note failed: Animal ID {animal_id} not found.")
        return JsonResponse({"success": False, "error": "找不到該美容師"}, status=404)
    except (ValueError, TypeError):
        logger.warning(f"Add/Update note failed: Invalid animal ID format: {animal_id}.")
        return JsonResponse({"success": False, "error": "無效的美容師 ID"}, status=400)
    except ValidationError as ve: # 捕獲上限檢查的錯誤
         logger.warning(f"Add note failed for user {user.username}: {ve.message}")
         # 在事務外獲取當前計數和上限以顯示
         current_notes_count_fallback = Note.objects.filter(user=user).count()
         try:
             limit_fallback = UserProfile.objects.get(user=user).notes_limit
         except UserProfile.DoesNotExist:
             limit_fallback = '未知'
         return JsonResponse({
             "success": False,
             "error": ve.message,
             "notes_count": current_notes_count_fallback, # 返回當前數量
             "remaining_limit": limit_fallback          # 返回當前上限
             }, status=403)
    except Exception as e:
        if 'unique constraint' in str(e) and 'myapp_note' in str(e).lower():
             logger.warning(f"Unique constraint violation during add_note for user {user.username}, animal {animal_id}. Assuming update.")
             try:
                 existing_note = Note.objects.get(user=user, animal=animal)
                 existing_note.content = content
                 existing_note.save(update_fields=['content', 'updated_at'])
                 current_limit = UserProfile.objects.get(user=user).notes_limit
                 notes_count = Note.objects.filter(user=user).count()
                 return JsonResponse({
                     "success": True, "message": "筆記已更新", "note_id": existing_note.id,
                     "note_content": existing_note.content, "animal_id": animal.id,
                     "notes_count": notes_count, "remaining_limit": current_limit
                 })
             except Note.DoesNotExist:
                 logger.error("Note not found after unique constraint error in add_note.")
                 return JsonResponse({"success": False, "error": "儲存筆記時發生衝突"}, status=500)
             except UserProfile.DoesNotExist:
                 logger.error(f"UserProfile not found for user {user.username} during add_note unique constraint fallback.")
                 return JsonResponse({"success": False, "error": "儲存筆記時發生使用者設定錯誤"}, status=500)
             except Exception as fallback_e:
                  logger.error(f"Error in add_note unique constraint fallback: {fallback_e}", exc_info=True)
                  return JsonResponse({"success": False, "error": "更新筆記時發生未知錯誤"}, status=500)
        else:
            logger.error(f"Error adding/updating note for user {user.username}, animal {animal_id}: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": "儲存筆記時發生錯誤"}, status=500)
# --- *** add_note 函數修改結束 *** ---


# --- delete_note (保持不變，但回傳值稍作調整) ---
@require_POST
@login_required
def delete_note(request):
    note_id = request.POST.get("note_id")
    user = request.user
    logger.info(f"User {user.username} attempting to delete note ID: {note_id}")
    if not note_id:
        logger.warning("Delete note failed: Missing note ID.")
        return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    try:
        try: note_id_int = int(note_id)
        except (ValueError, TypeError):
            logger.warning(f"Delete note failed: Invalid note ID format: {note_id}")
            raise ValueError("無效的筆記 ID 格式")
        note = get_object_or_404(Note, id=note_id_int, user=user)
        animal_id = note.animal_id
        deleted_count, _ = note.delete()
        if deleted_count == 0:
            logger.error(f"Delete note failed for note ID {note_id_int} even after finding it.")
            return JsonResponse({"success": False, "error": "刪除失敗，筆記可能已被移除"})
        else:
            logger.info(f"Note {note_id_int} deleted successfully for animal {animal_id} by user {user.username}.")
            # 獲取刪除後的計數和上限
            notes_count = Note.objects.filter(user=user).count()
            try:
                limit = UserProfile.objects.get(user=user).notes_limit
            except UserProfile.DoesNotExist:
                limit = '未知'
            return JsonResponse({
                "success": True, "message": "筆記已刪除",
                "animal_id": animal_id,
                "notes_count": notes_count, # 返回最新的已用數量
                "remaining_limit": limit # 返回上限
                })
    except Http404:
        logger.warning(f"Delete note failed: Note ID {note_id} not found or does not belong to user {user.username}.")
        return JsonResponse({"success": False, "error": "筆記不存在或無權限刪除"}, status=404)
    except ValueError as ve:
        return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        logger.error(f"Error deleting note ID {note_id} for user {user.username}: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": "刪除筆記時發生錯誤"}, status=500)

# --- update_note (保持不變，但回傳值稍作調整) ---
@require_POST
@login_required
def update_note(request):
    note_id = request.POST.get("note_id")
    content = request.POST.get("content", "").strip()
    user = request.user
    logger.info(f"User {user.username} attempting to update note ID: {note_id}")
    if not note_id:
        logger.warning("Update note failed: Missing note ID.")
        return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    if not content:
        logger.warning("Update note failed: Content is empty.")
        return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)
    try:
        try: note_id_int = int(note_id)
        except (ValueError, TypeError):
            logger.warning(f"Update note failed: Invalid note ID format: {note_id}")
            raise ValueError("無效的筆記 ID 格式")
        note = get_object_or_404(Note.objects.select_related('animal'), id=note_id_int, user=user)
        animal = note.animal
        note.content = content
        note.save(update_fields=['content', 'updated_at'])
        logger.info(f"Note {note_id_int} updated successfully by user {user.username}.")
        try:
            limit = UserProfile.objects.get(user=user).notes_limit
        except UserProfile.DoesNotExist:
             logger.error(f"UserProfile not found for user {user.username} when getting limit after update_note.")
             limit = '未知'
        # 獲取更新後的計數
        notes_count = Note.objects.filter(user=user).count()
        return JsonResponse({
            "success": True, "message": "筆記已更新", "note_id": note.id,
            "note_content": note.content, "animal_id": animal.id,
            "notes_count": notes_count, # 返回已用數量
            "remaining_limit": limit # 返回上限
            })
    except Http404:
        logger.warning(f"Update note failed: Note ID {note_id} not found or does not belong to user {user.username}.")
        return JsonResponse({"success": False, "error": "筆記不存在或無權限修改"}, status=404)
    except ValueError as ve:
        return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except UserProfile.DoesNotExist:
         logger.error(f"UserProfile not found for user {user.username} during update_note.")
         return JsonResponse({"success": False, "error": "找不到使用者設定檔"}, status=500)
    except Exception as e:
        logger.error(f"Error updating note ID {note_id} for user {user.username}: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": "更新筆記時發生錯誤"}, status=500)


# --- AJAX Views (Stories, Schedule) (保持不變) ---
# ... (ajax_get_active_stories, ajax_get_story_detail, ajax_get_weekly_schedule 函數代碼) ...
@require_GET
def ajax_get_active_stories(request):
    logger.debug("Fetching active stories.")
    try:
        now = timezone.now()
        active_stories_qs = StoryReview.objects.filter(
            animal__is_active=True,
            animal__hall__is_active=True,
            approved=True,
            expires_at__gt=now
        ).select_related(
            'animal', 'animal__hall', 'user'
        ).order_by('-approved_at')
        stories_data = []
        for s in active_stories_qs:
            stories_data.append({
                'id': s.id,
                'animal_id': s.animal_id,
                'animal_name': s.animal.name if s.animal else '未知',
                'animal_photo_url': s.animal.photo.url if s.animal and s.animal.photo else None,
                'hall_name': s.animal.hall.name if s.animal and s.animal.hall else '未知館別',
                'user_name': s.user.first_name or s.user.username if s.user else '匿名',
                'remaining_time': s.remaining_time_display
            })
        return JsonResponse({'stories': stories_data})
    except Exception as e:
        logger.error(f"Error in ajax_get_active_stories: {e}", exc_info=True)
        return JsonResponse({'error': '無法載入限時動態'}, status=500)

@require_GET
def ajax_get_story_detail(request, story_id):
    logger.debug(f"Fetching story detail for story_id: {story_id}")
    try:
        now = timezone.now()
        story = get_object_or_404(
            StoryReview.objects.filter(
                animal__is_active=True,
                animal__hall__is_active=True,
                approved=True,
                expires_at__gt=now
            ).select_related(
                'animal', 'animal__hall', 'user'
            ).annotate(
                good_to_have_you_count=Count('feedback', filter=Q(feedback__feedback_type='good_to_have_you')),
                good_looking_count=Count('feedback', filter=Q(feedback__feedback_type='good_looking'))
            ),
            pk=story_id
        )
        animal = story.animal; user = story.user
        approved_at_display = format_date(timezone.localtime(story.approved_at), 'Y-m-d H:i') if story.approved_at else ""
        author_id = user.id if user else None
        user_title = None
        if user:
            try:
                review_count = Review.objects.filter(user=user, approved=True).count()
                story_review_count = StoryReview.objects.filter(user=user, approved=True).count()
                total_count = review_count + story_review_count
                user_title = get_user_title_from_count(total_count)
            except Exception as count_err:
                logger.error(f"Error fetching total review count for user {user.id} in story detail: {count_err}", exc_info=True)
        story_data = {
            'id': story.id, 'author_id': author_id, 'animal_id': animal.id, 'animal_name': animal.name,
            'animal_photo_url': animal.photo.url if animal.photo else None,
            'hall_name': animal.hall.name if animal.hall else '未知館別',
            'user_name': user.first_name or user.username if user else '匿名',
            'user_title': user_title, 'remaining_time': story.remaining_time_display,
            'approved_at_display': approved_at_display, 'age': story.age, 'looks': story.looks,
            'face': story.face, 'temperament': story.temperament, 'physique': story.physique,
            'cup': story.cup, 'cup_size': story.cup_size, 'skin_texture': story.skin_texture,
            'skin_color': story.skin_color, 'music': story.music, 'music_price': story.music_price,
            'sports': story.sports, 'sports_price': story.sports_price, 'scale': story.scale,
            'content': story.content,
            'good_to_have_you_count': story.good_to_have_you_count,
            'good_looking_count': story.good_looking_count,
        }
        return JsonResponse({'success': True, 'story': story_data})
    except Http404:
        logger.warning(f"Story detail fetch failed: Story ID {story_id} not found, inactive, or expired.")
        return JsonResponse({'success': False, 'error': '找不到該動態、或動態已過期'}, status=404)
    except Exception as e:
        logger.error(f"Error in ajax_get_story_detail for ID {story_id}: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '無法載入動態詳情'}, status=500)

@require_GET
def ajax_get_weekly_schedule(request):
    hall_id = request.GET.get('hall_id')
    logger.debug(f"Fetching weekly schedule for hall_id: {hall_id}")
    if not hall_id:
        logger.warning("Weekly schedule request missing hall_id.")
        return JsonResponse({'success': False, 'error': '缺少館別 ID'}, status=400)
    try:
        hall_id_int = int(hall_id)
        hall = get_object_or_404(Hall, id=hall_id_int, is_active=True)
        hall_name = hall.name
        logger.debug(f"Found active hall: {hall_name}")
    except (ValueError, TypeError):
        logger.warning(f"Invalid hall_id format for weekly schedule: {hall_id}")
        return JsonResponse({'success': False, 'error': '無效的館別 ID 格式'}, status=400)
    except Http404:
        try:
            hall_name = Hall.objects.get(id=hall_id_int).name
            logger.warning(f"Weekly schedule request for inactive hall: {hall_name} (ID: {hall_id})")
            return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': hall_name, 'message': f'{hall_name} 未啟用或未找到'}, status=404)
        except Hall.DoesNotExist:
            logger.warning(f"Weekly schedule request for non-existent hall ID: {hall_id}")
            return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': f"館別 {hall_id}", 'message': f'館別 {hall_id} 不存在'}, status=404)
        except Exception as inner_e:
             logger.error(f"Error fetching hall name after Http404 for weekly schedule (ID {hall_id}): {inner_e}", exc_info=True)
             return JsonResponse({'success': False, 'error': '獲取館別信息時出錯'}, status=500)
    except Exception as e:
        logger.error(f"Error getting Hall object for weekly schedule (ID {hall_id}): {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '獲取館別信息時發生錯誤'}, status=500)
    try:
        schedules = WeeklySchedule.objects.filter(hall_id=hall_id_int).order_by('order')
        schedule_urls = [s.schedule_image.url for s in schedules if s.schedule_image]
        if schedule_urls:
            logger.debug(f"Found {len(schedule_urls)} weekly schedule images for hall {hall_name}.")
            return JsonResponse({'success': True, 'schedule_urls': schedule_urls, 'hall_name': hall_name})
        else:
            logger.info(f"No weekly schedule images found for hall {hall_name} (ID: {hall_id}).")
            return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': hall_name, 'message': f'{hall_name} 未上傳班表圖片'})
    except Exception as e:
        logger.error(f"Error fetching weekly schedule images for Hall ID {hall_id}: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '載入每週班表圖片出錯'}, status=500)


# --- Hall of Fame View (保持不變) ---
@require_GET
def ajax_get_hall_of_fame(request):
    logger.info("Fetching Hall of Fame data (multi-category).")
    rankings = {}
    top_n = 10
    all_top_user_ids = set()

    try:
        logger.debug("Calculating Review ranking...")
        review_ranks_qs = Review.objects.filter(approved=True, user__isnull=False) \
            .values('user') \
            .annotate(count=Count('id')) \
            .filter(count__gt=0) \
            .order_by('-count', 'user__username')[:top_n]
        review_ranks = list(review_ranks_qs)
        all_top_user_ids.update(r['user'] for r in review_ranks)
        logger.debug(f"Review ranking calculated: {len(review_ranks)} users.")

        logger.debug("Calculating StoryReview ranking...")
        story_ranks_qs = StoryReview.objects.filter(approved=True, user__isnull=False) \
            .values('user') \
            .annotate(count=Count('id')) \
            .filter(count__gt=0) \
            .order_by('-count', 'user__username')[:top_n]
        story_ranks = list(story_ranks_qs)
        all_top_user_ids.update(s['user'] for s in story_ranks)
        logger.debug(f"StoryReview ranking calculated: {len(story_ranks)} users.")

        feedback_ranks_data = {}
        feedback_types = ['good_looking', 'good_to_have_you']
        for fb_type in feedback_types:
            logger.debug(f"Calculating {fb_type} feedback ranking...")
            recipient_id_annotation = Coalesce('review__user_id', 'story_review__user_id')
            feedback_ranks_qs = ReviewFeedback.objects.filter(feedback_type=fb_type) \
                .annotate(recipient_id=recipient_id_annotation) \
                .filter(recipient_id__isnull=False) \
                .values('recipient_id') \
                .annotate(count=Count('id')) \
                .filter(count__gt=0) \
                .order_by('-count', 'recipient_id')[:top_n]
            feedback_ranks_list = list(feedback_ranks_qs)
            feedback_ranks_data[fb_type] = feedback_ranks_list
            all_top_user_ids.update(f['recipient_id'] for f in feedback_ranks_list)
            logger.debug(f"{fb_type} feedback ranking calculated: {len(feedback_ranks_list)} users.")

        logger.debug(f"Fetching details and titles for {len(all_top_user_ids)} unique top users.")
        all_user_details = {u.id: u for u in User.objects.filter(id__in=all_top_user_ids)}

        user_total_counts = defaultdict(int)
        review_counts_all = Review.objects.filter(user_id__in=all_top_user_ids, approved=True).values('user_id').annotate(count=Count('id'))
        story_counts_all = StoryReview.objects.filter(user_id__in=all_top_user_ids, approved=True).values('user_id').annotate(count=Count('id'))
        for item in review_counts_all:
            user_total_counts[item['user_id']] += item['count']
        for item in story_counts_all:
            user_total_counts[item['user_id']] += item['count']

        all_user_titles = {
            user_id: get_user_title_from_count(user_total_counts.get(user_id, 0))
            for user_id in all_top_user_ids
        }
        logger.debug("User titles calculated.")

        rankings['reviews'] = [
            {
                'rank': i + 1,
                'user_name': all_user_details[r['user']].first_name or all_user_details[r['user']].username,
                'user_title': all_user_titles.get(r['user']),
                'count': r['count'],
                'user_id': r['user']
            }
            for i, r in enumerate(review_ranks) if r['user'] in all_user_details
        ]
        rankings['stories'] = [
            {
                'rank': i + 1,
                'user_name': all_user_details[s['user']].first_name or all_user_details[s['user']].username,
                'user_title': all_user_titles.get(s['user']),
                'count': s['count'],
                 'user_id': s['user']
            }
            for i, s in enumerate(story_ranks) if s['user'] in all_user_details
        ]
        for fb_type, ranks_list in feedback_ranks_data.items():
            rankings[fb_type] = [
                {
                    'rank': i + 1,
                    'user_name': all_user_details[f['recipient_id']].first_name or all_user_details[f['recipient_id']].username,
                    'user_title': all_user_titles.get(f['recipient_id']),
                    'count': f['count'],
                    'user_id': f['recipient_id']
                }
                for i, f in enumerate(ranks_list) if f['recipient_id'] in all_user_details
            ]

        logger.debug(f"Final rankings data prepared: {list(rankings.keys())}")
        return JsonResponse({'success': True, 'rankings': rankings})

    except Exception as e:
        logger.error(f"Error in ajax_get_hall_of_fame: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '無法載入名人堂數據'}, status=500)


# --- View for adding feedback (保持不變) ---
@login_required
@require_POST
def add_review_feedback(request):
    review_id = request.POST.get('review_id')
    story_review_id = request.POST.get('story_review_id')
    feedback_type = request.POST.get('feedback_type')
    user = request.user
    logger.info(f"User {user.username} attempting feedback type '{feedback_type}' on review_id='{review_id}', story_review_id='{story_review_id}'")
    valid_feedback_types = dict(ReviewFeedback.FEEDBACK_CHOICES).keys()
    if not feedback_type or feedback_type not in valid_feedback_types:
        logger.warning(f"Invalid feedback type: {feedback_type}")
        return JsonResponse({'success': False, 'error': '無效的回饋類型'}, status=400)
    if not review_id and not story_review_id:
        logger.warning("Feedback attempt missing target review/story ID.")
        return JsonResponse({'success': False, 'error': '缺少目標心得 ID'}, status=400)
    if review_id and story_review_id:
        logger.warning("Feedback attempt provided both review and story ID.")
        return JsonResponse({'success': False, 'error': '不能同時提供兩種心得 ID'}, status=400)

    target_review = None; target_story_review = None; target_author = None; target_description = ""
    try:
        if review_id:
            try:
                target_review = Review.objects.select_related('user').get(pk=review_id, approved=True)
                target_author = target_review.user
                target_description = f"Review ID {review_id}"
            except Review.DoesNotExist:
                logger.warning(f"Feedback target Review ID {review_id} not found or not approved.")
                return JsonResponse({'success': False, 'error': '找不到或未審核的一般心得'}, status=404)
        elif story_review_id:
            try:
                target_story_review = StoryReview.objects.select_related('user').get(pk=story_review_id, approved=True, expires_at__gt=timezone.now())
                target_author = target_story_review.user
                target_description = f"StoryReview ID {story_review_id}"
            except StoryReview.DoesNotExist:
                logger.warning(f"Feedback target StoryReview ID {story_review_id} not found, not approved, or expired.")
                return JsonResponse({'success': False, 'error': '找不到、未審核或已過期的限時動態心得'}, status=404)
        if target_author == user:
            logger.warning(f"User {user.username} attempted to give feedback on their own {target_description}.")
            return JsonResponse({'success': False, 'error': '不能對自己的心得給予回饋'}, status=403)
        feedback_data = {'user': user, 'feedback_type': feedback_type, 'review': target_review, 'story_review': target_story_review }
        with transaction.atomic():
            obj, created = ReviewFeedback.objects.get_or_create(**feedback_data)
            current_counts_qs = ReviewFeedback.objects.filter(review=target_review, story_review=target_story_review)
            good_to_have_you_count = current_counts_qs.filter(feedback_type='good_to_have_you').count()
            good_looking_count = current_counts_qs.filter(feedback_type='good_looking').count()
            if not created:
                logger.info(f"User {user.username} already gave feedback '{feedback_type}' on {target_description}.")
                return JsonResponse({ 'success': False, 'error': '你已經給過這個回饋了', 'good_to_have_you_count': good_to_have_you_count, 'good_looking_count': good_looking_count, }, status=409)
            logger.info(f"Feedback '{feedback_type}' successfully added by user {user.username} to {target_description}.")
            return JsonResponse({ 'success': True, 'message': '回饋成功！', 'good_to_have_you_count': good_to_have_you_count, 'good_looking_count': good_looking_count, })
    except Exception as e:
        logger.error(f"Error adding review feedback by user {user.username} for type '{feedback_type}' on {target_description}: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '處理回饋時發生內部錯誤'}, status=500)

# --- View for fetching profile data (保持不變) ---
@login_required
@require_GET
def ajax_get_profile_data(request):
    user = request.user
    logger.info(f"Fetching profile data for user: {user.username}")
    profile_data = {
        'username': user.username,
        'first_name': user.first_name or '',
    }
    try:
        profile, created = UserProfile.objects.get_or_create(user=user)
        if created:
            logger.warning(f"UserProfile created on-the-fly for user {user.username} in ajax_get_profile_data. Initial limits: P={profile.pending_list_limit}, N={profile.notes_limit}")
        approved_reviews_count = Review.objects.filter(user=user, approved=True).count()
        approved_stories_count = StoryReview.objects.filter(user=user, approved=True).count()
        total_reviews = approved_reviews_count + approved_stories_count
        user_title = get_user_title_from_count(total_reviews)
        profile_data['approved_reviews_count'] = approved_reviews_count
        profile_data['approved_stories_count'] = approved_stories_count
        profile_data['total_reviews'] = total_reviews
        profile_data['user_title'] = user_title
        good_to_have_you_received = ReviewFeedback.objects.filter( Q(review__user=user) | Q(story_review__user=user), feedback_type='good_to_have_you' ).count()
        good_looking_received = ReviewFeedback.objects.filter( Q(review__user=user) | Q(story_review__user=user), feedback_type='good_looking' ).count()
        profile_data['good_to_have_you_received'] = good_to_have_you_received
        profile_data['good_looking_received'] = good_looking_received
        pending_count = PendingAppointment.objects.filter(user=user).count()
        notes_count = Note.objects.filter(user=user).count()
        profile_data['pending_count'] = pending_count
        profile_data['notes_count'] = notes_count
        profile_data['pending_list_limit'] = profile.pending_list_limit
        profile_data['notes_limit'] = profile.notes_limit
        logger.debug(f"Profile data fetched for {user.username}: Reviews={total_reviews}, Pending={pending_count}/{profile.pending_list_limit}, Notes={notes_count}/{profile.notes_limit}")
        return JsonResponse({'success': True, 'profile_data': profile_data})
    except Exception as e:
        logger.error(f"Error fetching profile data for user {user.username}: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '讀取個人檔案資料時發生錯誤'}, status=500)

# --- Admin Merge/Transfer View (保持不變) ---
@staff_member_required
def merge_transfer_animal_view(request, animal_id):
    animal_original = get_object_or_404(Animal, pk=animal_id)
    logger.info(f"Admin merge/transfer view accessed for Animal ID: {animal_id} ({animal_original.name})")
    form = None
    if request.method == 'POST':
        logger.info("Handling POST request for animal merge/transfer.")
        form = MergeTransferForm(request.POST, request.FILES, animal_original=animal_original)
        if form.is_valid():
            logger.debug("Merge/Transfer form is valid.")
            duplicate_animal = form.cleaned_data.get('duplicate_animal')
            target_hall = duplicate_animal.hall
            new_name = duplicate_animal.name
            if not target_hall:
                logger.warning(f"Merge aborted: Duplicate animal {duplicate_animal.id} ({duplicate_animal.name}) has no assigned hall.")
                messages.error(request, f"合併失敗：選擇的重複記錄 '{duplicate_animal.name}' (ID: {duplicate_animal.id}) 沒有有效的館別，無法確定目標館別。")
                context = _get_merge_view_context(request, animal_original, form)
                return render(request, 'admin/myapp/animal/merge_transfer_form.html', context)
            if Animal.objects.filter(hall=target_hall, name__iexact=new_name, is_active=True).exclude(pk=animal_original.id).exclude(pk=duplicate_animal.id).exists():
                 logger.warning(f"Merge aborted: Another active animal named '{new_name}' already exists in target hall '{target_hall.name}'.")
                 messages.error(request, f"合併失敗：目標館別 '{target_hall.name}' 中已存在另一位啟用中的美容師名為 '{new_name}'。請先處理該衝突或選擇其他重複記錄。")
                 context = _get_merge_view_context(request, animal_original, form)
                 return render(request, 'admin/myapp/animal/merge_transfer_form.html', context)
            logger.info(f"Processing merge: Duplicate ID {duplicate_animal.id} ({duplicate_animal.name}) into Original ID {animal_original.id} ({animal_original.name}). Target Hall: {target_hall.name}, New Name: {new_name}")
            try:
                with transaction.atomic():
                    logger.info(f"Starting transaction for MERGE animal ID {animal_original.id}...")
                    log_prefix = f"[Merge Animal ID {animal_original.id}]"
                    logger.debug(f"{log_prefix} Applying descriptive data and tags from duplicate...")
                    if duplicate_animal.introduction: animal_original.introduction = duplicate_animal.introduction
                    if duplicate_animal.photo:
                        if animal_original.photo and animal_original.photo.name != duplicate_animal.photo.name:
                            logger.debug(f"{log_prefix} Deleting old photo: {animal_original.photo.name}")
                            try: animal_original.photo.delete(save=False)
                            except Exception as photo_delete_err: logger.warning(f"{log_prefix} Warning: Error deleting old photo file: {photo_delete_err}")
                        if not animal_original.photo or (animal_original.photo and duplicate_animal.photo and animal_original.photo.name != duplicate_animal.photo.name):
                            animal_original.photo = duplicate_animal.photo
                            logger.debug(f"{log_prefix} Applied photo from duplicate.")
                    if duplicate_animal.fee is not None: animal_original.fee = duplicate_animal.fee
                    if duplicate_animal.height is not None: animal_original.height = duplicate_animal.height
                    if duplicate_animal.weight is not None: animal_original.weight = duplicate_animal.weight
                    if duplicate_animal.cup_size: animal_original.cup_size = duplicate_animal.cup_size
                    tag_fields_to_copy = ['is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer', 'is_featured']
                    for field_name in tag_fields_to_copy:
                        if hasattr(animal_original, field_name) and hasattr(duplicate_animal, field_name):
                            duplicate_value = getattr(duplicate_animal, field_name)
                            setattr(animal_original, field_name, duplicate_value)
                        else: logger.warning(f"{log_prefix} Tag field '{field_name}' not found on both models, skipping.")
                    logger.debug(f"{log_prefix} Descriptive data and tags applied.")
                    logger.debug(f"{log_prefix} Transferring related records...")
                    models_to_transfer = [Review, StoryReview, Note, PendingAppointment]
                    for model_class in models_to_transfer:
                        model_name = model_class.__name__
                        logger.debug(f"{log_prefix} Processing {model_name} transfer...")
                        try:
                            if hasattr(model_class, 'animal'):
                                duplicate_related_qs = model_class.objects.filter(animal=duplicate_animal)
                                if not duplicate_related_qs.exists():
                                    logger.debug(f"{log_prefix} No {model_name} records found for duplicate animal.")
                                    continue
                                if model_name in ['Note', 'PendingAppointment']:
                                    timestamp_field = 'updated_at' if model_name == 'Note' else 'added_at'
                                    logger.debug(f"{log_prefix} Special handling for {model_name} using {timestamp_field} for conflicts.")
                                    original_related_users = set(model_class.objects.filter(animal=animal_original).values_list('user_id', flat=True))
                                    duplicate_related_users = set(duplicate_related_qs.values_list('user_id', flat=True))
                                    conflicting_user_ids = original_related_users.intersection(duplicate_related_users)
                                    kept_from_duplicate_count = 0; deleted_from_duplicate_count = 0; deleted_from_original_count = 0
                                    if conflicting_user_ids:
                                        logger.debug(f"{log_prefix} Found {len(conflicting_user_ids)} conflicts for {model_name}. Resolving...")
                                        for user_id in conflicting_user_ids:
                                            try:
                                                original_item = model_class.objects.get(animal=animal_original, user_id=user_id)
                                                duplicate_item = model_class.objects.get(animal=duplicate_animal, user_id=user_id)
                                                keep_original = True
                                                orig_ts = getattr(original_item, timestamp_field, None); dup_ts = getattr(duplicate_item, timestamp_field, None)
                                                if orig_ts and dup_ts:
                                                    if dup_ts > orig_ts: keep_original = False
                                                elif not orig_ts and dup_ts: keep_original = False
                                                if keep_original:
                                                    duplicate_item.delete(); deleted_from_duplicate_count += 1
                                                    logger.debug(f"{log_prefix} Conflict {model_name} User {user_id}: Kept original, deleted duplicate.")
                                                else:
                                                    original_item.delete(); deleted_from_original_count += 1
                                                    duplicate_item.animal = animal_original; duplicate_item.save()
                                                    kept_from_duplicate_count += 1
                                                    logger.debug(f"{log_prefix} Conflict {model_name} User {user_id}: Kept duplicate (reassigned), deleted original.")
                                            except model_class.DoesNotExist: logger.warning(f"{log_prefix} Conflict resolution error: {model_name} not found for user {user_id} during conflict check.")
                                            except Exception as cr_err: logger.error(f"{log_prefix} Error resolving {model_name} conflict for user {user_id}: {cr_err}", exc_info=True); raise cr_err
                                        logger.debug(f"{log_prefix} {model_name} Conflict resolution summary: Kept {kept_from_duplicate_count} (dup), Deleted {deleted_from_duplicate_count} (dup), Deleted {deleted_from_original_count} (orig).")
                                    else: logger.debug(f"{log_prefix} No user conflicts found for {model_name}.")
                                    remaining_update_qs = model_class.objects.filter(animal=duplicate_animal)
                                    remaining_update_count = remaining_update_qs.count()
                                    updated_count_bulk = 0
                                    if remaining_update_count > 0:
                                        updated_count_bulk = remaining_update_qs.update(animal=animal_original)
                                        logger.debug(f"{log_prefix} {model_name} updated (remaining non-conflicting): {updated_count_bulk}")
                                    else: logger.debug(f"{log_prefix} No remaining non-conflicting {model_name} found for duplicate.")
                                    total_transferred_or_resolved = kept_from_duplicate_count + updated_count_bulk
                                else:
                                    generic_qs = model_class.objects.filter(animal=duplicate_animal)
                                    generic_count = generic_qs.count()
                                    if generic_count > 0:
                                        updated_count = generic_qs.update(animal=animal_original)
                                        logger.debug(f"{log_prefix} {model_name} updated (generic bulk): {updated_count}")
                                        total_transferred_or_resolved = updated_count
                                    else:
                                         logger.debug(f"{log_prefix} No {model_name} records found for duplicate animal (generic).")
                                         total_transferred_or_resolved = 0
                                logger.info(f"{log_prefix} Transferred/resolved {total_transferred_or_resolved} {model_name} record(s) from duplicate {duplicate_animal.id} to original {animal_original.id}.")
                            else: logger.warning(f"{log_prefix} Skipping {model_name} transfer (model has no 'animal' field).")
                        except Exception as transfer_err: logger.error(f"{log_prefix} Error transferring {model_name} from duplicate {duplicate_animal.id}: {transfer_err}", exc_info=True); raise transfer_err
                    logger.debug(f"{log_prefix} Cleaning up ReviewFeedback for duplicate animal...")
                    feedback_to_delete_qs = ReviewFeedback.objects.filter(Q(review__animal=duplicate_animal) | Q(story_review__animal=duplicate_animal))
                    deleted_feedback_count, _ = feedback_to_delete_qs.delete()
                    if deleted_feedback_count > 0: logger.info(f"{log_prefix} Deleted {deleted_feedback_count} ReviewFeedback records associated with duplicate's (ID: {duplicate_animal.id}) reviews/stories.")
                    else: logger.debug(f"{log_prefix} No ReviewFeedback records found associated with duplicate's reviews/stories.")
                    if SCHEDULE_PARSER_ENABLED and DailySchedule:
                        logger.debug(f"{log_prefix} Handling DailySchedule cleanup and transfer...")
                        try:
                            duplicate_schedules_qs = DailySchedule.objects.filter(animal=duplicate_animal)
                            original_schedule_in_target_hall = DailySchedule.objects.filter(animal=animal_original, hall=target_hall).first()
                            deleted_orig_wrong_hall, _ = DailySchedule.objects.filter(animal=animal_original).exclude(hall=target_hall).delete()
                            if deleted_orig_wrong_hall > 0: logger.info(f"{log_prefix} Cleaned up {deleted_orig_wrong_hall} pre-existing DailySchedule for original animal (ID {animal_original.id}) in incorrect halls.")
                            if original_schedule_in_target_hall:
                                deleted_dup_count, _ = duplicate_schedules_qs.delete()
                                if deleted_dup_count > 0: logger.info(f"{log_prefix} Discarded {deleted_dup_count} DailySchedule from duplicate because original already has one in target hall.")
                            else:
                                schedule_to_transfer = duplicate_schedules_qs.first()
                                if schedule_to_transfer:
                                    schedule_to_transfer.animal = animal_original; schedule_to_transfer.hall = target_hall; schedule_to_transfer.save()
                                    logger.info(f"{log_prefix} Transferred DailySchedule (ID {schedule_to_transfer.id}) from duplicate to original in target hall.")
                                    deleted_other_dups, _ = duplicate_schedules_qs.exclude(pk=schedule_to_transfer.pk).delete()
                                    if deleted_other_dups > 0: logger.warning(f"{log_prefix} Deleted {deleted_other_dups} other redundant DailySchedule from duplicate ID {duplicate_animal.id}.")
                                else: logger.info(f"{log_prefix} No DailySchedule found for duplicate animal to transfer.")
                        except Exception as ds_err: logger.error(f"{log_prefix} Error handling DailySchedule during merge: {ds_err}", exc_info=True); raise ds_err
                    else: logger.debug(f"{log_prefix} Skipping DailySchedule handling (not enabled or model not found).")
                    logger.debug(f"{log_prefix} Merging aliases...")
                    original_aliases = animal_original.aliases if isinstance(animal_original.aliases, list) else []
                    duplicate_aliases = duplicate_animal.aliases if isinstance(duplicate_animal.aliases, list) else []
                    valid_original = {str(a).strip() for a in original_aliases if a and str(a).strip()}
                    valid_duplicate = {str(a).strip() for a in duplicate_aliases if a and str(a).strip()}
                    merged_aliases_set = valid_original.union(valid_duplicate)
                    if duplicate_animal.name not in merged_aliases_set: merged_aliases_set.add(duplicate_animal.name)
                    if duplicate_animal.hall:
                        dup_history_marker = f"{duplicate_animal.name}@{duplicate_animal.hall.name}"
                        if dup_history_marker not in merged_aliases_set: merged_aliases_set.add(dup_history_marker)
                    animal_original.aliases = list(merged_aliases_set)
                    logger.debug(f"{log_prefix} Aliases merged (pre-final update). Current set: {animal_original.aliases}")
                    logger.debug(f"{log_prefix} Updating final animal's core info...")
                    old_name = animal_original.name; old_hall = animal_original.hall
                    animal_original.hall = target_hall; animal_original.name = new_name; animal_original.is_active = True
                    current_aliases_set = set(animal_original.aliases)
                    if old_name != new_name and old_name not in current_aliases_set:
                        current_aliases_set.add(old_name)
                        logger.debug(f"{log_prefix} Added old name '{old_name}' to aliases.")
                    if old_hall != target_hall and old_hall and old_hall.name:
                        history_marker = f"{old_name}@{old_hall.name}"
                        if history_marker not in current_aliases_set:
                            current_aliases_set.add(history_marker)
                            logger.debug(f"{log_prefix} Added history marker '{history_marker}' to aliases.")
                    animal_original.aliases = list(current_aliases_set)
                    logger.debug(f"{log_prefix} Final state before save: Hall={animal_original.hall.name}, Name={animal_original.name}, Active={animal_original.is_active}, Aliases={animal_original.aliases}")
                    animal_original.save()
                    logger.info(f"{log_prefix} Final animal (ID {animal_original.id}) saved successfully.")
                    duplicate_pk_to_delete = duplicate_animal.pk; duplicate_name_to_delete = duplicate_animal.name
                    logger.info(f"{log_prefix} Deleting duplicate animal record ID: {duplicate_pk_to_delete} ({duplicate_name_to_delete})...")
                    if duplicate_animal.photo and (not animal_original.photo or duplicate_animal.photo.name != animal_original.photo.name):
                        logger.debug(f"{log_prefix} Deleting photo file of duplicate: {duplicate_animal.photo.name}")
                        try: duplicate_animal.photo.delete(save=False)
                        except Exception as dup_photo_del_err: logger.warning(f"{log_prefix} Warning: Error deleting photo file for duplicate ID {duplicate_pk_to_delete}: {dup_photo_del_err}")
                    duplicate_animal.delete()
                    logger.info(f"{log_prefix} Duplicate animal deleted successfully.")
                logger.info(f"{log_prefix} Merge transaction completed successfully.")
                messages.success(request, f"美容師資料已成功從 '{duplicate_name_to_delete}' (ID: {duplicate_pk_to_delete}) 合併至 '{new_name}' @ '{target_hall.name}' (ID: {animal_original.id})。關聯記錄、標籤和班表已處理。")
                return redirect('admin:myapp_animal_changelist')
            except Exception as e:
                logger.error(f"Error during MERGE transaction for animal {animal_original.id} from {duplicate_animal.id}: {e}", exc_info=True)
                error_message = f"處理合併時發生內部錯誤: {e}"
                if 'violates unique constraint' in str(e).lower(): error_message = f"處理合併時遇到資料庫唯一性衝突，操作未完成。請檢查資料。錯誤：{e}"
                messages.error(request, error_message)
        else:
            logger.warning(f"Merge/Transfer form invalid. Errors: {form.errors.as_json()}")
            messages.error(request, "表單驗證失敗，請檢查輸入。")
    if form is None: form = MergeTransferForm(animal_original=animal_original)
    context = _get_merge_view_context(request, animal_original, form)
    return render(request, 'admin/myapp/animal/merge_transfer_form.html', context)

def _get_merge_view_context(request, animal_original, form):
    """Prepares context data for the merge/transfer form template."""
    approved_review_count = '計算錯誤'; story_review_count = '計算錯誤'; notes_count = '計算錯誤'; pending_count = '計算錯誤'; aliases_display_text = '獲取錯誤'; daily_schedule_info = '未啟用或錯誤'
    try:
        approved_review_count = Review.objects.filter(animal=animal_original, approved=True).count()
        story_review_count = StoryReview.objects.filter(animal=animal_original, approved=True).count()
        notes_count = Note.objects.filter(animal=animal_original).count()
        pending_count = PendingAppointment.objects.filter(animal=animal_original).count()
        aliases_data = animal_original.aliases
        if isinstance(aliases_data, list):
            display_aliases = [str(a).strip() for a in aliases_data if a and str(a).strip()]
            display_text_list = display_aliases[:3]
            suffix = '...' if len(display_aliases) > 3 else ''
            aliases_display_text = ", ".join(display_text_list) + suffix if display_text_list else "無"
        elif isinstance(aliases_data, str) and aliases_data.strip(): aliases_display_text = aliases_data[:30] + ('...' if len(aliases_data) > 30 else '')
        elif aliases_data: aliases_display_text = str(aliases_data)
        else: aliases_display_text = "無"
        if SCHEDULE_PARSER_ENABLED and DailySchedule:
             try:
                 schedule = DailySchedule.objects.filter(animal=animal_original).first()
                 if schedule: daily_schedule_info = f"館別: {schedule.hall.name if schedule.hall else '未知'}, 時段: {schedule.time_slots or '無'}, 日期: {schedule.date}"
                 else: daily_schedule_info = "無記錄"
             except Exception as ds_err:
                  logger.warning(f"Error fetching DailySchedule info for animal {animal_original.id} in context: {ds_err}")
                  daily_schedule_info = f"讀取錯誤: {ds_err}"
        else: daily_schedule_info = "每日班表功能未啟用"
    except Exception as count_error:
        logger.warning(f"Warning: Error counting related objects or formatting aliases for animal {animal_original.id} in context: {count_error}")
    opts = Animal._meta; app_label = opts.app_label
    has_view_permission = request.user.has_perm(f'{app_label}.view_animal')
    has_change_permission = request.user.has_perm(f'{app_label}.change_animal')
    has_delete_permission = request.user.has_perm(f'{app_label}.delete_animal')
    has_add_permission = request.user.has_perm(f'{app_label}.add_animal')
    context = {
        'title': f"合併/轉移 美容師資料: {animal_original.name}", 'animal_original': animal_original, 'form': form,
        'opts': opts, 'has_view_permission': has_view_permission, 'has_change_permission': has_change_permission,
        'has_delete_permission': has_delete_permission, 'is_popup': False, 'save_as': False,
        'has_add_permission': has_add_permission, 'app_label': app_label,
        'approved_review_count': approved_review_count, 'story_review_count': story_review_count,
        'notes_count': notes_count, 'pending_count': pending_count, 'aliases_display_text': aliases_display_text,
        'daily_schedule_info': daily_schedule_info,
    }
    return context

# --- views.py File End ---