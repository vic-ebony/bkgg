# D:\bkgg\mybackend\myapp\views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateformat import format as format_date
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Prefetch, Max, F, OuterRef, Subquery # 確保導入 Q
from django.db.models.functions import Coalesce
from django.db import transaction # <<< 確保導入 transaction
from django.views.decorators.http import require_POST, require_GET
from django.template.loader import render_to_string
from .models import (
    Animal, Hall, Review, PendingAppointment, Note, Announcement,
    StoryReview, WeeklySchedule, ReviewFeedback, UserTitleRule, UserProfile,
    SiteConfiguration
)
import traceback
import html
import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.contrib import messages
from .forms import MergeTransferForm # Assuming MergeTransferForm is in forms.py
from .utils import get_user_title_from_count # Assuming get_user_title_from_count is in utils.py
from collections import defaultdict
from django.core.exceptions import ValidationError
from django.db import models as db_models # Alias to avoid potential naming conflicts

logger = logging.getLogger(__name__)
User = get_user_model()

try:
    # Attempt to import DailySchedule from schedule_parser app
    from schedule_parser.models import DailySchedule
    SCHEDULE_PARSER_ENABLED = True
    logger.info("schedule_parser app and DailySchedule model found. Daily schedule features enabled.")
except ImportError:
    logger.warning("schedule_parser app or DailySchedule model not found. Daily schedule features will be disabled.")
    SCHEDULE_PARSER_ENABLED = False
    DailySchedule = None # Define as None if import fails

# --- Define CUP_ORDER globally or within the view if preferred ---
CUP_ORDER = [
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L',
    'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'
]
# Create a mapping for quick index lookup
CUP_ORDER_MAP = {cup: i for i, cup in enumerate(CUP_ORDER)}


# --- render_animal_rows function ---
def render_animal_rows(request, animals_qs, fetch_daily_slots=False):
    """Renders HTML table rows for a queryset of Animals."""
    animal_daily_slots = {}
    # Get IDs of animals actually present in the queryset to optimize subsequent queries
    animal_ids_on_page = [a.id for a in animals_qs if a] # Filter out None animals if any edge case allows it

    if fetch_daily_slots and SCHEDULE_PARSER_ENABLED and DailySchedule is not None and animal_ids_on_page:
        try:
            # Fetch daily schedules only for animals on the current page/results
            daily_schedules_qs = DailySchedule.objects.filter(
                animal_id__in=animal_ids_on_page
            ).values('animal_id', 'time_slots') # Only fetch needed fields
            animal_daily_slots = {schedule['animal_id']: schedule['time_slots'] for schedule in daily_schedules_qs}
            logger.debug(f"Fetched daily slots for animal IDs: {list(animal_daily_slots.keys())}")
        except Exception as slot_err:
            logger.error(f"Error fetching daily slots inside render_animal_rows: {slot_err}", exc_info=True)

    pending_ids = set()
    notes_by_animal = {}
    # Fetch pending/note status only if user is logged in and there are animals to check
    if request.user.is_authenticated and animal_ids_on_page:
        try:
            # Fetch pending status and notes efficiently for animals on the current page
            pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user, animal_id__in=animal_ids_on_page))
            notes_qs = Note.objects.filter(user=request.user, animal_id__in=animal_ids_on_page)
            notes_by_animal = {str(note.animal_id): note for note in notes_qs} # Map note by animal ID string
            logger.debug(f"Fetched pending IDs: {pending_ids} and note IDs: {list(notes_by_animal.keys())} for user {request.user.username}")
        except Exception as e:
            logger.error(f"Error fetching pending/notes for user {request.user.username}: {e}", exc_info=True)

    rendered_rows_html_list = []
    for animal_instance in animals_qs:
        # Basic check in case queryset somehow contains None
        if not animal_instance:
             logger.warning("Skipping None animal instance in render_animal_rows")
             continue

        # Use prefetched review count if available (from annotations), otherwise query
        review_count = getattr(animal_instance, 'approved_review_count', None)
        if review_count is None:
            # Fallback query if annotation wasn't applied in the calling view
            try:
                review_count = Review.objects.filter(animal=animal_instance, approved=True).count()
                # logger.warning(f"Review count for animal {animal_instance.id} not annotated, queried separately.") # Optional: Log if fallback query happens
            except Exception as count_err:
                logger.error(f"Error counting reviews for animal {animal_instance.id}: {count_err}", exc_info=True)
                review_count = 0 # Default to 0 on error

        animal_id_str = str(animal_instance.id)
        today_slots_for_template = animal_daily_slots.get(animal_instance.id) # Use fetched slots map
        note_instance = notes_by_animal.get(animal_id_str) # Use fetched notes map

        # Prepare context for the partial template
        row_context = {
            'animal': animal_instance,
            'user': request.user,
            'today_slots': today_slots_for_template,
            'is_pending': animal_id_str in pending_ids, # Use fetched pending status
            'note': note_instance, # Pass the whole note object (or None)
            'review_count': review_count,
            # Pass necessary data directly for JS via data-* attributes in the template
            'animal_data': {
                 'photo_url': animal_instance.photo.url if animal_instance.photo else '',
                 'introduction': animal_instance.introduction or '',
                 'note_id': note_instance.id if note_instance else '',
                 'note_content': note_instance.content if note_instance else '', # Pre-pass note content
                 'pending': animal_id_str in pending_ids # Pass boolean pending status for JS logic
            }
        }
        try:
            # Render the partial template (_animal_table_rows.html) for each animal row
            rendered_html = render_to_string('myapp/partials/_animal_table_rows.html', row_context, request=request)
            rendered_rows_html_list.append(rendered_html)
        except Exception as render_err:
            logger.error(f"Error rendering partial _animal_table_rows.html for animal {animal_instance.id}: {render_err}", exc_info=True)
            # Provide a fallback row in case of rendering error to avoid breaking the table
            rendered_rows_html_list.append(f'<tr><td colspan="5" style="color:red; font-style:italic;">渲染錯誤: {animal_instance.name} (ID: {animal_instance.id})</td></tr>')

    return "".join(rendered_rows_html_list)


# --- Home View ---
def home(request):
    is_ajax_request = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    fetch_type = request.GET.get('fetch')
    is_daily_schedule_ajax = is_ajax_request and fetch_type == 'daily_schedule'

    # --- Handle AJAX request for Daily Schedule ---
    if is_daily_schedule_ajax:
        hall_id = request.GET.get('hall_id')
        logger.debug(f"Received AJAX request for daily schedule, hall_id: {hall_id}")
        if not hall_id:
            logger.warning("Daily schedule AJAX request missing hall_id.")
            return JsonResponse({'error': '請求缺少館別 ID (hall_id)'}, status=400)
        try:
            hall_id_int = int(hall_id)
            selected_hall = get_object_or_404(Hall, id=hall_id_int, is_active=True) # Ensure hall exists and is active
            logger.info(f"Fetching daily schedule for Hall: {selected_hall.name} (ID: {hall_id_int})")
        except (ValueError, TypeError):
            logger.warning(f"Invalid hall_id format received: {hall_id}")
            return JsonResponse({'error': '無效的館別 ID 格式'}, status=400)
        except Http404:
            logger.warning(f"Hall ID {hall_id} not found or not active for daily schedule request.")
            hall_name = Hall.objects.filter(id=hall_id_int).values_list('name', flat=True).first() or f"館別 {hall_id}"
            return JsonResponse({'table_html': f'<tr class="empty-table-message"><td colspan="5">{hall_name} 不存在或未啟用</td></tr>', 'first_animal': {}}, status=404)

        try:
            # Check if schedule parser is enabled
            if not SCHEDULE_PARSER_ENABLED or DailySchedule is None:
                 logger.warning("Daily schedule feature accessed but schedule_parser is disabled or DailySchedule model is None.")
                 raise RuntimeError("DailySchedule is not available.") # Raise specific error

            # Prefetch related animal data, including review count annotation
            prefetch_animal = Prefetch(
                'animal',
                queryset=Animal.objects.select_related('hall').filter(
                    is_active=True # Ensure prefetched animals are active
                ).annotate(
                    approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
                )
            )
            # Fetch daily schedules for the selected hall, prefetching optimized animal data
            daily_schedules_qs = DailySchedule.objects.filter(
                hall_id=hall_id_int
            ).prefetch_related(prefetch_animal).order_by('animal__order', 'animal__name') # Order by animal order

            # Extract valid animal instances from the prefetched data
            animals_for_render = [ds.animal for ds in daily_schedules_qs if ds.animal]
            logger.debug(f"Found {len(animals_for_render)} active animals with daily schedules for Hall ID {hall_id_int}")

            # Render the table rows using the helper function
            table_html = render_animal_rows(request, animals_for_render, fetch_daily_slots=True) # Pass True to fetch slots

            # Get data for the first animal to display in the top section
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

        except RuntimeError as r_err: # Catch specific error if feature disabled
             logger.warning(f"Daily schedule feature accessed but disabled: {r_err}")
             error_html = f'<tr class="empty-table-message"><td colspan="5">每日班表功能未啟用</td></tr>'
             return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=501) # 501 Not Implemented
        except Exception as e: # Catch any other unexpected errors
            logger.error(f"Error during Daily Schedule AJAX processing for Hall ID {hall_id}: {e}", exc_info=True)
            error_html = f'<tr class="empty-table-message"><td colspan="5">載入班表時發生內部錯誤</td></tr>'
            return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500) # 500 Internal Server Error

    # --- Handle Other AJAX requests via fetch_type ---
    elif is_ajax_request:
        logger.debug(f"Received AJAX request, fetch_type: {fetch_type}")
        if fetch_type == 'pending': return ajax_get_pending_list(request)
        elif fetch_type == 'my_notes': return ajax_get_my_notes(request)
        elif fetch_type == 'latest_reviews': return ajax_get_latest_reviews(request)
        elif fetch_type == 'recommendations': return ajax_get_recommendations(request)
        # Note: ajax_search_beauticians is handled by its own URL now
        else:
            logger.error(f"Unknown fetch_type '{fetch_type}' received on home URL via AJAX.")
            return JsonResponse({'error': '未知的請求類型'}, status=400) # 400 Bad Request

    # --- Full Page Render (Non-AJAX) ---
    else:
        logger.info("Rendering full home page (index.html)")
        # Get active and visible halls for navigation menus
        halls = Hall.objects.filter(is_active=True, is_visible=True).order_by('order', 'name')
        context = {'halls': halls, 'user': request.user}
        initial_pending_count = 0

        # Get initial pending count for logged-in users
        if request.user.is_authenticated:
            try:
                initial_pending_count = PendingAppointment.objects.filter(user=request.user).count()
                logger.debug(f"Initial pending count for user {request.user.username}: {initial_pending_count}")
            except Exception as e:
                logger.error(f"Error fetching initial pending count for user {request.user.username}: {e}")
        context['pending_count'] = initial_pending_count

        # Get the latest active announcement
        try:
            context['announcement'] = Announcement.objects.filter(is_active=True).order_by('-updated_at').first()
        except Exception as e:
            logger.error(f"Error fetching announcement: {e}")
            context['announcement'] = None

        # --- 獲取主打美容師和 Logo ---
        featured_animal = None
        site_logo_url = None

        try:
            # Find the first featured, active animal with a photo
            featured_animal = Animal.objects.select_related('hall').annotate(
                 approved_review_count=Count('reviews', filter=Q(reviews__approved=True)) # Annotate review count
            ).filter(
                 is_featured=True,
                 is_active=True,
                 photo__isnull=False # Ensure photo exists
             ).exclude(photo='').order_by('order', 'name').first() # Order to get consistent result if multiple featured
            if featured_animal:
                logger.debug(f"Featured animal found: {featured_animal.name}")
            else:
                 logger.debug("No featured animal found.")
        except Exception as e:
             logger.error(f"Error fetching featured animal: {e}", exc_info=True)

        try:
            # Get site logo from SiteConfiguration singleton model
            site_config = SiteConfiguration.get_solo()
            site_logo_url = site_config.site_logo.url if site_config.site_logo else None
            logger.debug(f"Site logo URL: {site_logo_url}")
        except SiteConfiguration.DoesNotExist:
            logger.warning("SiteConfiguration object does not exist. Cannot load logo.")
        except AttributeError: # Handle case where django-solo might not be installed/configured
             logger.warning("SiteConfiguration.get_solo() not found. Assuming django-solo is not used or SiteConfiguration is not a SingletonModel.")
        except Exception as e:
             logger.error(f"Error fetching site configuration/logo: {e}", exc_info=True)

        context['featured_animal'] = featured_animal
        context['site_logo_url'] = site_logo_url
        # --- 獲取結束 ---

        # Pass login error message from session if exists (set by user_login view)
        login_error = request.session.pop('login_error', None)
        if login_error:
            context['login_error'] = login_error
            logger.debug(f"Login error message passed to context: {login_error}")

        context['selected_hall_id'] = 'all' # Default value, might be used by JS later
        template_path = 'myapp/index.html'

        try:
            return render(request, template_path, context)
        except Exception as e:
            # Log critical rendering errors
            logger.critical(f"CRITICAL ERROR rendering main template {template_path}: {e}", exc_info=True)
            raise # Re-raise the exception for Django's default error handling
# --- Home View 結束 ---


# --- AJAX Views (Pending, Notes, Latest Reviews, Recommendations) ---
@login_required # Requires user to be logged in
@require_GET # Only allow GET requests
def ajax_get_pending_list(request):
    logger.info(f"User {request.user.username} requesting pending list.")
    try:
        # Get user's pending appointments, ordered by most recently added
        pending_appointments_qs = PendingAppointment.objects.filter(
            user=request.user
        ).select_related(
            'animal', 'animal__hall' # Optimize related object fetching
        ).order_by('-added_at')

        # Get IDs of animals in the pending list
        animal_ids = list(pending_appointments_qs.values_list('animal_id', flat=True))

        # Fetch details ONLY for active animals whose hall is also active (or null hall)
        animals_qs = Animal.objects.filter(
            id__in=animal_ids
        ).filter(
            Q(is_active=True) & (Q(hall__isnull=True) | Q(hall__is_active=True))
        ).annotate(
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True)) # Annotate review count
        )
        # Create a dictionary for quick lookup
        animals_dict = {a.id: a for a in animals_qs}

        # Order the final animal list based on the original pending appointment order
        animals_list_ordered = [animals_dict.get(pa.animal_id) for pa in pending_appointments_qs if pa.animal_id in animals_dict]
        logger.debug(f"Found {len(animals_list_ordered)} active pending animals for user {request.user.username}.")

        # Render table rows using the helper function
        table_html = render_animal_rows(request, animals_list_ordered, fetch_daily_slots=True) # Fetch slots

        # Get data for the first animal for top section display
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
    selected_hall_id = hall_id or 'all' # Default to 'all' if no hall_id provided
    logger.info(f"User {request.user.username} requesting notes. Hall filter: {selected_hall_id}")

    try:
        # Base query for user's notes on active animals/halls
        notes_base_qs = Note.objects.filter(
            user=request.user
        ).filter(
            Q(animal__is_active=True) & (Q(animal__hall__isnull=True) | Q(animal__hall__is_active=True))
        ).select_related('animal', 'animal__hall') # Optimize fetching

        # Apply hall filter if a specific hall ID is provided
        if selected_hall_id != "all":
            try:
                hall_id_int = int(selected_hall_id)
                notes_qs = notes_base_qs.filter(animal__hall_id=hall_id_int)
                logger.debug(f"Filtering notes by Hall ID: {hall_id_int}")
            except (ValueError, TypeError):
                logger.warning(f"Invalid hall_id '{selected_hall_id}' received for notes filter.")
                return JsonResponse({'error': '無效的館別 ID 格式'}, status=400)
        else:
            notes_qs = notes_base_qs.all() # No hall filter
            logger.debug("Fetching all notes (no hall filter).")

        # Order notes by most recently updated
        notes_qs = notes_qs.order_by('-updated_at')
        animal_ids = list(notes_qs.values_list('animal_id', flat=True))
        animals_list_ordered = []

        if animal_ids:
            # Fetch animal details for the notes found
            animals_qs = Animal.objects.filter(
                id__in=animal_ids # Already filtered for active animals/halls in notes_qs
            ).annotate(
                approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
            )
            animals_dict = {a.id: a for a in animals_qs}
            # Order animals based on note update time
            animals_list_ordered = [animals_dict.get(note.animal_id) for note in notes_qs if note.animal_id in animals_dict]
            logger.debug(f"Found {len(animals_list_ordered)} animals with notes matching filter.")

        # Render table rows
        table_html = render_animal_rows(request, animals_list_ordered, fetch_daily_slots=True) # Fetch slots

        # Get data for the first animal
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


@require_GET # Public view, no login required
def ajax_get_latest_reviews(request):
    logger.info("Requesting latest reviews.")
    try:
        # Subquery to get the latest approval timestamp for each animal
        latest_approved_time_subquery = Review.objects.filter(
            animal=OuterRef('pk'),
            approved=True
        ).order_by('-approved_at', '-created_at').values('approved_at')[:1] # Use approved_at primarily

        # Subquery to get the corresponding creation time for tie-breaking
        latest_created_time_subquery = Review.objects.filter(
             animal=OuterRef('pk'),
             approved=True
        ).order_by('-approved_at', '-created_at').values('created_at')[:1]

        # Query active animals in active halls that have at least one approved review
        latest_reviewed_animals_qs = Animal.objects.filter(
            is_active=True,
            hall__is_active=True, # Ensure hall is active
            reviews__approved=True # Efficiently check if any approved review exists
        ).annotate(
            latest_approved_time=Subquery(latest_approved_time_subquery),
            latest_created_time=Subquery(latest_created_time_subquery), # Annotate for ordering
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True)) # Annotate count
        ).filter(
            latest_approved_time__isnull=False # Ensure annotation worked (animal has approved reviews)
        ).select_related('hall').order_by('-latest_approved_time', '-latest_created_time')[:20] # Order and limit

        # Log the number of animals found (using list conversion to avoid potential re-query)
        results_list = list(latest_reviewed_animals_qs)
        logger.debug(f"Found {len(results_list)} animals for latest reviews list (ordered by approved_at).")

        # Render rows using the evaluated list
        table_html = render_animal_rows(request, results_list, fetch_daily_slots=True) # Fetch slots

        # Get data for the first animal
        first_animal_data = {}
        if results_list: # Check if the list is not empty
             first_animal = results_list[0]
             logger.debug(f"First animal for latest reviews: {first_animal.name}")
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


@require_GET # Public view
def ajax_get_recommendations(request):
    logger.info("Requesting recommendations.")
    try:
        # Query active, recommended animals in active halls
        recommended_animals_qs = Animal.objects.filter(
            is_active=True,
            is_recommended=True,
            hall__is_active=True # Ensure hall is active
        ).select_related('hall').annotate(
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        ).order_by('hall__order', 'order', 'name') # Defined ordering

        # Evaluate the queryset to get the list
        results_list = list(recommended_animals_qs)
        logger.debug(f"Found {len(results_list)} recommended animals.")

        # Render rows
        table_html = render_animal_rows(request, results_list, fetch_daily_slots=True) # Fetch slots

        # Get data for the first animal
        first_animal_data = {}
        if results_list:
             first_animal = results_list[0]
             logger.debug(f"First recommended animal: {first_animal.name}")
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

# --- User Authentication Views ---
def user_login(request):
    # Handles login attempts via POST
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        logger.info(f"Login attempt for username: '{username}'")
        if not username or not password:
            logger.warning("Login attempt failed: Username or password missing.")
            request.session['login_error'] = '請輸入帳號和密碼'
            return redirect('myapp:home') # Redirect back with error message

        # Authenticate user
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Login successful
            login(request, user)
            request.session.pop('login_error', None) # Clear any previous login error
            logger.info(f"User '{username}' logged in successfully.")
            return redirect('myapp:home') # Redirect to home page
        else:
            # Login failed
            logger.warning(f"Login failed for username '{username}': Invalid credentials.")
            request.session['login_error'] = '帳號或密碼錯誤'
            return redirect('myapp:home') # Redirect back with error message

    # If GET request or any other method, just redirect to home
    return redirect('myapp:home')

@require_POST # Enforce logout via POST request
@login_required # User must be logged in to logout
def user_logout(request):
    user_display = request.user.username if request.user.is_authenticated else "N/A" # Get username before logout
    logout(request)
    logger.info(f"User '{user_display}' logged out.")
    return redirect('myapp:home') # Redirect to home page after logout

# --- Add Story Review View ---
@login_required
@require_POST
def add_story_review(request):
    animal_id = request.POST.get("animal_id")
    user = request.user
    logger.info(f"User {user.username} attempting to add story review for animal ID: {animal_id}")

    # Basic validation for animal_id presence
    if not animal_id:
        logger.warning("Add story review failed: Missing animal ID.")
        return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)

    # Validate animal_id and fetch animal
    try:
        animal = get_object_or_404(Animal, id=animal_id)
        logger.debug(f"Found animal: {animal.name} for story review.")
    except Http404:
        logger.warning(f"Add story review failed: Animal ID {animal_id} not found.")
        return JsonResponse({"success": False, "error": "找不到該美容師"}, status=404)
    except (ValueError, TypeError): # Catch non-integer IDs
        logger.warning(f"Add story review failed: Invalid animal ID format: {animal_id}.")
        return JsonResponse({"success": False, "error": "無效的美容師 ID"}, status=400)

    # Process form data
    face_list = request.POST.getlist("face")
    temperament_list = request.POST.getlist("temperament")
    scale_list = request.POST.getlist("scale")
    content = request.POST.get("content", "").strip()
    age_str = request.POST.get("age")
    cup_size_value = request.POST.get("cup_size", "")

    # Server-side validation (matches frontend logic)
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

    # Create the StoryReview object if validation passes
    try:
        new_story = StoryReview.objects.create(
            animal=animal,
            user=user,
            age=age,
            looks=request.POST.get("looks") or None,
            face=','.join(filter(None, face_list)), # Join list items
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
            # Default values for approval and timestamps
            approved=False,
            approved_at=None,
            expires_at=None,
            reward_granted=False
        )
        logger.info(f"Story Review {new_story.id} created for animal {animal_id} by user {user.username}. Needs approval.")
        return JsonResponse({"success": True, "message": "限時動態心得已提交，待審核後將顯示"})
    except Exception as e:
        logger.error(f"Error creating story review for animal {animal_id} by user {user.username}: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": "儲存限時動態心得時發生內部錯誤"}, status=500)


# --- add_review 函數 ---
# Handles both POST (submit review) and GET (fetch reviews for an animal)
def add_review(request):
    if request.method == "POST":
        # --- Handle Review Submission ---
        if not request.user.is_authenticated:
            logger.warning("Anonymous user attempted to post a review.")
            return JsonResponse({"success": False, "error": "請先登入才能提交心得"}, status=401) # 401 Unauthorized

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

        # Process form data
        face_list = request.POST.getlist("face")
        temperament_list = request.POST.getlist("temperament")
        scale_list = request.POST.getlist("scale")
        content = request.POST.get("content", "").strip()
        age_str = request.POST.get("age")
        cup_size_value = request.POST.get("cup_size", "")

        # Validation
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

        # Create Review object
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
                approved=False, # Reviews start as unapproved
                approved_at=None,
                reward_granted=False # Reward is granted on approval via signal
            )
            logger.info(f"Review {new_review.id} created for animal {animal_id} by user {user.username}. Needs approval.")
            return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
        except Exception as e:
            logger.error(f"Error creating review for animal {animal_id} by user {user.username}: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": "儲存心得時發生內部錯誤"}, status=500)

    elif request.method == "GET":
        # --- Handle Fetching Reviews for an Animal ---
        animal_id = request.GET.get("animal_id")
        logger.debug(f"Fetching reviews for animal_id: {animal_id}")

        if not animal_id:
            logger.warning("Fetch reviews request missing animal_id.")
            return JsonResponse({"error": "缺少 animal_id"}, status=400)

        try:
            # Get the animal, ensuring it and its hall are active/visible
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

        # Fetch approved reviews, optimize related user fetching, annotate feedback counts
        reviews_qs = Review.objects.filter(
            animal=animal, approved=True
        ).select_related('user').annotate(
            good_to_have_you_count=Count('feedback', filter=Q(feedback__feedback_type='good_to_have_you')),
            good_looking_count=Count('feedback', filter=Q(feedback__feedback_type='good_looking'))
        ).order_by("-approved_at", "-created_at") # Order by approval, then creation

        # Efficiently get user titles for all authors in the results
        user_ids = list(reviews_qs.values_list('user_id', flat=True).distinct())
        user_total_counts = defaultdict(int) # Use defaultdict for easier counting
        user_titles = {}
        if user_ids:
             logger.debug(f"Fetching total counts for user IDs: {user_ids}")
             try:
                 # Aggregate counts efficiently
                 review_counts_query = Review.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(count=Count('id'))
                 story_counts_query = StoryReview.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(count=Count('id'))
                 for item in review_counts_query: user_total_counts[item['user_id']] += item['count']
                 for item in story_counts_query: user_total_counts[item['user_id']] += item['count']
                 # Determine titles based on totals
                 for user_id, total_count in user_total_counts.items():
                     user_titles[user_id] = get_user_title_from_count(total_count)
                 logger.debug(f"Calculated user titles: {user_titles}")
             except Exception as count_err:
                 logger.error(f"Error fetching user total review counts: {count_err}", exc_info=True)
                 # Continue without titles if error occurs

        # Prepare data list for JSON response
        data = []
        for r in reviews_qs:
            user_display_name = "匿名"; display_date = ""; user_title = None; author_id = None
            if hasattr(r, 'user') and r.user:
                user_display_name = r.user.first_name or r.user.username # Prefer first name
                author_id = r.user.id
                user_title = user_titles.get(r.user_id) # Get pre-calculated title
            else:
                logger.warning(f"Review {r.id} is missing user information.")

            # Format date safely
            if r.approved_at:
                 try: display_date = timezone.localtime(r.approved_at).strftime("%Y-%m-%d")
                 except Exception as date_err: logger.error(f"Error formatting approved_at for review {r.id}: {date_err}"); display_date = "日期錯誤"
            elif r.created_at: # Fallback if approved_at is missing but review is approved (should not happen ideally)
                 try: display_date = timezone.localtime(r.created_at).strftime("%Y-%m-%d"); logger.warning(f"Review {r.id} approved but missing approved_at, using created_at.")
                 except Exception as date_err: logger.error(f"Error formatting created_at fallback for review {r.id}: {date_err}"); display_date = "日期錯誤"
            else: display_date = "日期未知"

            data.append({
                "id": r.id, "author_id": author_id, "user": user_display_name, "user_title": user_title,
                "age": r.age, "looks": r.looks, "face": r.face, "temperament": r.temperament,
                "physique": r.physique, "cup": r.cup, "cup_size": r.cup_size,
                "skin_texture": r.skin_texture, "skin_color": r.skin_color,
                "music": r.music, "music_price": r.music_price,
                "sports": r.sports, "sports_price": r.sports_price,
                "scale": r.scale, "content": r.content,
                "display_date": display_date,
                # Include annotated feedback counts
                "good_to_have_you_count": r.good_to_have_you_count,
                "good_looking_count": r.good_looking_count,
            })
        return JsonResponse({"reviews": data})

    # Handle unsupported methods
    logger.warning(f"Unsupported method {request.method} for add_review view.")
    return JsonResponse({"error": "請求方法不支援"}, status=405) # 405 Method Not Allowed


# --- add_pending_appointment 函數 ---
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
    remaining_limit = '未知'
    animal = None

    try:
        with transaction.atomic():
            animal = get_object_or_404(Animal, id=animal_id)
            # Lock the profile row for update to prevent race conditions on limits
            profile = UserProfile.objects.select_for_update().get(user=user)
            logger.debug(f"User {user.username} profile locked. Current pending limit: {profile.pending_list_limit}")

            # Check if user has remaining limit
            if profile.pending_list_limit <= 0:
                logger.warning(f"User {user.username} failed to add pending: Limit reached ({profile.pending_list_limit}).")
                return JsonResponse({"success": False, "error": "待約次數不足，請分享心得獲取更多次數！"}, status=403) # 403 Forbidden

            # Try to get or create the pending appointment
            obj, created = PendingAppointment.objects.get_or_create(user=user, animal=animal)

            if created:
                # Decrement limit only if a new entry was created
                profile.pending_list_limit = F('pending_list_limit') - 1
                profile.save(update_fields=['pending_list_limit'])
                profile.refresh_from_db() # Refresh to get the updated value after F() expression
                logger.info(f"Pending appointment CREATED for animal {animal_id} by user {user.username}. Limit decremented to {profile.pending_list_limit}.")
                message = f"{animal.name} 已加入待約清單"
                remaining_limit = profile.pending_list_limit # Get updated limit
            else:
                logger.info(f"Pending appointment for animal {animal_id} by user {user.username} already exists. Limit not changed.")
                message = f"{animal.name} 已在待約清單中"
                remaining_limit = profile.pending_list_limit # Get current limit

        # --- Outside the transaction ---
        # Get the final pending count for the user
        pending_count = PendingAppointment.objects.filter(user=user).count()

        # Append remaining limit info to the message
        message += f" (剩餘 {remaining_limit} 次)"

        return JsonResponse({
            "success": True,
            "message": message,
            "pending_count": pending_count,
            "remaining_limit": remaining_limit # Also return the numeric value
        })

    except UserProfile.DoesNotExist:
         logger.error(f"UserProfile not found for user {user.username} (ID: {user.id}) during add_pending")
         return JsonResponse({"success": False, "error": "找不到使用者設定檔，無法檢查次數"}, status=500)
    except Http404:
        logger.warning(f"Add pending failed: Animal ID {animal_id} not found.")
        return JsonResponse({"success": False, "error": "找不到該美容師"}, status=404)
    except (ValueError, TypeError):
        logger.warning(f"Add pending failed: Invalid animal ID format: {animal_id}.")
        return JsonResponse({"success": False, "error": "無效的美容師 ID"}, status=400)
    except Exception as e:
        # Handle potential unique constraint violation gracefully if transaction fails mid-way
        # This can happen in high concurrency scenarios if get_or_create check passes but insert fails
        if 'unique constraint' in str(e).lower() and 'myapp_pendingappointment' in str(e).lower():
            logger.warning(f"Unique constraint violation during add_pending for user {user.username}, animal {animal_id}. Handling as 'already exists'.")
            try:
                # Re-fetch counts and limit outside the failed transaction
                pending_count = PendingAppointment.objects.filter(user=user).count()
                profile = UserProfile.objects.get(user=user) # No lock needed here
                remaining_limit = profile.pending_list_limit
                try:
                    # Ensure animal name is available for the message
                    if not animal: animal = Animal.objects.get(id=animal_id)
                    animal_name = animal.name
                except Animal.DoesNotExist: animal_name = f"美容師 #{animal_id}"

                final_message = f"{animal_name} 已在待約清單中 (剩餘 {remaining_limit} 次)"

                return JsonResponse({
                    "success": True, # Still considered success from user perspective
                    "message": final_message,
                    "pending_count": pending_count,
                    "remaining_limit": remaining_limit
                })
            except Exception as fallback_e:
                  logger.error(f"Error in add_pending unique constraint fallback: {fallback_e}", exc_info=True)
                  return JsonResponse({"success": False, "error": "加入待約時發生未知錯誤"}, status=500)
        else:
            # Log other unexpected errors
            logger.error(f"Error adding pending appointment for user {user.username}, animal {animal_id}: {e}", exc_info=True)
            return JsonResponse({"success": False, "error": "加入待約時發生錯誤"}, status=500)


# --- remove_pending 函數 ---
@require_POST
@login_required
def remove_pending(request):
    animal_id_str = request.POST.get("animal_id")
    user = request.user
    logger.info(f"[remove_pending] User {user.username} attempting remove for animal_id_str: '{animal_id_str}'")

    if not animal_id_str:
        logger.warning("[remove_pending] Failed: Missing animal ID.")
        return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)

    remaining_limit = '未知'
    new_pending_count = 0
    was_deleted = False
    animal_id_int = None
    animal_name = "該美容師" # Default name

    try:
        # Validate and parse animal ID
        try:
            animal_id_int = int(animal_id_str)
            logger.debug(f"[remove_pending] Parsed animal_id: {animal_id_int}")
            # Try to get animal name early for messages
            try:
                animal_name = Animal.objects.get(pk=animal_id_int).name
            except Animal.DoesNotExist:
                logger.warning(f"[remove_pending] Animal ID {animal_id_int} does not exist.")
                # Continue, but the item won't be found in PendingAppointment either
        except (ValueError, TypeError):
             logger.warning(f"[remove_pending] Failed: Invalid animal ID format: {animal_id_str}")
             count = PendingAppointment.objects.filter(user=user).count() # Get current count for context
             return JsonResponse({"success": False, "error": "無效的美容師 ID 格式", "pending_count": count}, status=400)

        # Use transaction to ensure atomicity of delete + limit increment
        with transaction.atomic():
            logger.debug(f"[remove_pending] Starting transaction for user {user.username}")
            profile = None
            try:
                # Lock profile row for update
                profile = UserProfile.objects.select_for_update().get(user=user)
                logger.debug(f"[remove_pending] Profile locked for user {user.username}. Current limit: {profile.pending_list_limit}, Max: {profile.max_pending_limit}")
            except UserProfile.DoesNotExist:
                 logger.error(f"[remove_pending] UserProfile not found for user {user.username} (ID: {user.id}) INSIDE TRANSACTION")
                 raise UserProfile.DoesNotExist(f"UserProfile for {user.username} not found.") # Reraise to abort transaction
            except Exception as profile_err:
                 logger.error(f"[remove_pending] Error fetching/locking profile for user {user.username}: {profile_err}", exc_info=True)
                 raise # Reraise to abort transaction

            logger.debug(f"[remove_pending] Attempting to delete PendingAppointment for user {user.id}, animal {animal_id_int}")
            # Perform delete operation, get count of deleted items
            deleted_count, deleted_details = PendingAppointment.objects.filter(user=user, animal_id=animal_id_int).delete()
            logger.info(f"[remove_pending] Deletion result: deleted_count={deleted_count}, details={deleted_details}")

            if deleted_count > 0:
                was_deleted = True # Mark as deleted for later checks
                logger.debug(f"[remove_pending] Incrementing pending_list_limit for user {user.username}. Current: {profile.pending_list_limit}, Max: {profile.max_pending_limit}")

                # Increment limit only if it's below the maximum allowed
                if profile.pending_list_limit < profile.max_pending_limit:
                    try:
                        # Use simple increment and save within transaction
                        profile.pending_list_limit += 1
                        profile.save(update_fields=['pending_list_limit'])
                        profile.refresh_from_db() # Get the updated value after save
                        remaining_limit = profile.pending_list_limit
                        logger.info(f"[remove_pending] Successfully incremented pending_list_limit for user {user.username} to {remaining_limit}.")
                    except Exception as increment_err:
                        logger.error(f"[remove_pending] Error incrementing limit via profile.save() for user {user.username}: {increment_err}", exc_info=True)
                        # If save fails, re-fetch value before potential rollback
                        remaining_limit = UserProfile.objects.get(pk=profile.pk).pending_list_limit
                        raise increment_err # Reraise to ensure transaction rollback
                else:
                     # Limit already at max, don't increment
                     logger.warning(f"[remove_pending] Profile limit already at max ({profile.max_pending_limit}) for user {user.username}. Limit not incremented.")
                     remaining_limit = profile.pending_list_limit # Keep max value

            else:
                # Item was not found to delete (might have been deleted already)
                logger.warning(f"[remove_pending] Pending item for animal ID {animal_id_int} not found for user {user.username}. Limit not incremented.")
                remaining_limit = profile.pending_list_limit # Use current limit from locked profile
                error_msg = "該待約項目不存在或已被移除"
                status_code = 404 # Not Found seems appropriate
                logger.warning(f"[remove_pending] Returning {status_code} error from inside transaction: {error_msg}")
                # Need to return response here, as transaction would otherwise commit successfully
                current_count = PendingAppointment.objects.filter(user=user).count() # Count outside this attempt
                # Note: This return bypasses the final check outside transaction, which is fine if nothing was deleted.
                return JsonResponse({"success": False, "error": error_msg, "pending_count": current_count, "remaining_limit": remaining_limit}, status=status_code)

        # --- Outside Transaction ---
        logger.debug("[remove_pending] Transaction committed successfully.")
        # Get final count after potential deletion
        new_pending_count = PendingAppointment.objects.filter(user=user).count()
        logger.debug(f"[remove_pending] Final pending count after transaction: {new_pending_count}")

        # *** Final consistency check (optional but recommended) ***
        if was_deleted and animal_id_int is not None:
             exists_after_delete = PendingAppointment.objects.filter(user=user, animal_id=animal_id_int).exists()
             logger.info(f"[remove_pending] FINAL CHECK: PendingAppointment for user {user.id}, animal {animal_id_int} exists after supposed delete: {exists_after_delete}")
             if exists_after_delete:
                  # This indicates a potential issue (e.g., transaction rollback didn't happen?)
                  logger.error(f"[remove_pending] CRITICAL: Item still exists after delete transaction committed!")
                  # Return error even if transaction claimed success
                  return JsonResponse({"success": False, "error": "移除待約時發生內部錯誤，請稍後再試", "pending_count": new_pending_count}, status=500)

        # Prepare success response using data determined within the transaction
        response_data = {
            "success": True,
            "message": f"{animal_name} 待約項目已移除",
            "pending_count": new_pending_count,
            "animal_id": animal_id_int,
            "remaining_limit": remaining_limit
        }
        logger.info(f"[remove_pending] Returning success response: {response_data}")
        return JsonResponse(response_data)

    # --- Outer Exception Handling ---
    except UserProfile.DoesNotExist as e: # Catch if initial profile lock failed
        logger.error(f"[remove_pending] Caught UserProfile.DoesNotExist outside transaction for user {user.username}: {e}")
        count = PendingAppointment.objects.filter(user=user).count() # Get current count anyway
        return JsonResponse({"success": False, "error": "找不到使用者設定檔", "pending_count": count}, status=500)
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"[remove_pending] UNEXPECTED outer error for user {user.username}, animal ID '{animal_id_str}': {e}", exc_info=True)
        count = PendingAppointment.objects.filter(user=user).count()
        return JsonResponse({"success": False, "error": "移除待約時發生伺服器錯誤", "pending_count": count}, status=500)


# --- add_note 函數 ---
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
    final_remaining_limit = '未知'
    animal = None

    try:
        with transaction.atomic():
            animal = get_object_or_404(Animal, id=animal_id)
            # Lock profile for update
            profile = UserProfile.objects.select_for_update().get(user=user)
            logger.debug(f"User {user.username} profile locked. Current notes limit: {profile.notes_limit}")

            # Use update_or_create to handle both add and update atomically
            note_instance, created = Note.objects.update_or_create(
                user=user,
                animal=animal,
                defaults={"content": content} # Update content if exists, or set if new
            )

            if created:
                logger.debug("Attempting to create a new note.")
                # Check limit *before* decrementing if it's a new note
                if profile.notes_limit <= 0:
                    logger.warning(f"User {user.username} failed to create note: Limit reached ({profile.notes_limit}).")
                    # Raise validation error to automatically roll back transaction
                    raise ValidationError("筆記次數不足，請分享心得獲取更多次數！")

                # Decrement limit for new note creation
                profile.notes_limit = F('notes_limit') - 1
                profile.save(update_fields=['notes_limit'])
                profile.refresh_from_db() # Get updated value after F() expression
                final_remaining_limit = profile.notes_limit
                logger.info(f"Note CREATED (ID: {note_instance.id}) for animal {animal_id} by user {user.username}. Limit decremented to {final_remaining_limit}.")
                message = "筆記已新增"
            else:
                # Note was updated, limit doesn't change
                final_remaining_limit = profile.notes_limit # Use current limit
                logger.info(f"Note UPDATED (ID: {note_instance.id}) for animal {animal_id} by user {user.username}.")
                message = "筆記已更新"

        # --- Outside the transaction ---
        # Append remaining limit info to the message
        message += f" (剩餘 {final_remaining_limit} 次)"

        return JsonResponse({
            "success": True,
            "message": message,
            "note_id": note_instance.id,
            "note_content": note_instance.content, # Return the saved content
            "animal_id": animal.id,
            "remaining_limit": final_remaining_limit # Return numeric value
        })

    except UserProfile.DoesNotExist:
         logger.error(f"UserProfile not found for user {user.username} (ID: {user.id}) during add_note")
         return JsonResponse({"success": False, "error": "找不到使用者設定檔，無法執行操作"}, status=500)
    except Http404:
        logger.warning(f"Add/Update note failed: Animal ID {animal_id} not found.")
        return JsonResponse({"success": False, "error": "找不到該美容師"}, status=404)
    except (ValueError, TypeError): # Handle case where animal_id is not a number
        logger.warning(f"Add/Update note failed: Invalid animal ID format: {animal_id}.")
        return JsonResponse({"success": False, "error": "無效的美容師 ID"}, status=400)
    except ValidationError as ve: # Catch limit error specifically
         logger.warning(f"Add note failed for user {user.username}: {ve.message}")
         # Fetch current limit to return if possible, even if creation failed
         current_limit = '未知'
         try:
            current_limit = UserProfile.objects.get(user=user).notes_limit
         except UserProfile.DoesNotExist:
             pass
         return JsonResponse({"success": False, "error": ve.message, "remaining_limit": current_limit}, status=403) # 403 Forbidden
    except Exception as e:
        logger.error(f"Error adding/updating note for user {user.username}, animal {animal_id}: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": "儲存筆記時發生錯誤"}, status=500)


# --- delete_note 函數 ---
@require_POST
@login_required
def delete_note(request):
    note_id_str = request.POST.get("note_id")
    user = request.user
    logger.info(f"[delete_note] User {user.username} attempting delete for note_id_str: '{note_id_str}'")

    if not note_id_str:
        logger.warning("[delete_note] Failed: Missing note ID.")
        return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)

    animal_id = None
    final_remaining_limit = '未知'
    was_deleted = False # Flag to track if delete occurred
    note_id_int = None

    try:
        # Validate and parse note ID
        try:
            note_id_int = int(note_id_str)
            logger.debug(f"[delete_note] Parsed note_id: {note_id_int}")
        except (ValueError, TypeError):
            logger.warning(f"[delete_note] Failed: Invalid note ID format: {note_id_str}")
            return JsonResponse({"success": False, "error": "無效的筆記 ID 格式"}, status=400)

        # Use transaction for atomicity
        with transaction.atomic():
            logger.debug(f"[delete_note] Starting transaction for user {user.username}")
            profile = None
            try:
                # Lock profile for update
                profile = UserProfile.objects.select_for_update().get(user=user)
                logger.debug(f"[delete_note] Profile locked for user {user.username}. Current limit: {profile.notes_limit}, Max: {profile.max_notes_limit}")
            except UserProfile.DoesNotExist:
                 logger.error(f"[delete_note] UserProfile not found for user {user.username} (ID: {user.id}) INSIDE TRANSACTION")
                 raise UserProfile.DoesNotExist(f"UserProfile for {user.username} not found.") # Abort transaction
            except Exception as profile_err:
                 logger.error(f"[delete_note] Error fetching/locking profile for user {user.username}: {profile_err}", exc_info=True)
                 raise # Abort transaction

            logger.debug(f"[delete_note] Attempting to find Note for id {note_id_int}, user {user.id}")
            try:
                # Get the note, ensuring it belongs to the user
                note = Note.objects.get(id=note_id_int, user=user)
                animal_id = note.animal_id # Get animal ID before deleting
                logger.debug(f"[delete_note] Note found (Animal ID: {animal_id}). Attempting delete.")

                # Perform delete
                deleted_count, deleted_details = note.delete()
                logger.info(f"[delete_note] Deletion result: deleted_count={deleted_count}, details={deleted_details}")

                if deleted_count > 0:
                    was_deleted = True # Mark as deleted
                    logger.debug(f"[delete_note] Incrementing notes_limit for user {user.username}. Current: {profile.notes_limit}, Max: {profile.max_notes_limit}")

                    # Increment limit only if below the maximum allowed
                    if profile.notes_limit < profile.max_notes_limit:
                        try:
                            profile.notes_limit += 1
                            profile.save(update_fields=['notes_limit'])
                            profile.refresh_from_db() # Get updated value
                            final_remaining_limit = profile.notes_limit
                            logger.info(f"[delete_note] Successfully incremented notes_limit for user {user.username} to {final_remaining_limit}.")
                        except Exception as increment_err:
                            logger.error(f"[delete_note] Error incrementing limit via profile.save() for user {user.username}: {increment_err}", exc_info=True)
                            final_remaining_limit = UserProfile.objects.get(pk=profile.pk).notes_limit # Re-fetch pre-save value
                            raise increment_err # Abort transaction
                    else:
                         logger.warning(f"[delete_note] Profile limit already at max ({profile.max_notes_limit}) for user {user.username}. Limit not incremented.")
                         final_remaining_limit = profile.notes_limit # Keep max value

                else:
                    # This case indicates an issue if get() succeeded but delete returned 0
                    logger.error(f"[delete_note] Delete failed (deleted_count=0) for note ID {note_id_int} even after finding it. No limit increment.")
                    final_remaining_limit = profile.notes_limit # Use current limit
                    # Return error immediately from within transaction
                    return JsonResponse({"success": False, "error": "刪除失敗，筆記可能已被移除", "remaining_limit": final_remaining_limit }, status=500) # Internal server error seems appropriate

            except Note.DoesNotExist:
                 # Note wasn't found for this user and ID
                 logger.warning(f"[delete_note] Note ID {note_id_int} not found or does not belong to user {user.username}.")
                 current_limit = profile.notes_limit # Use the limit fetched earlier
                 # Return error immediately
                 return JsonResponse({"success": False, "error": "筆記不存在或無權限刪除", "remaining_limit": current_limit}, status=404)

        # --- Outside Transaction ---
        logger.debug("[delete_note] Transaction committed successfully.")

        # *** Final consistency check after commit ***
        if was_deleted and note_id_int is not None:
             exists_after_delete = Note.objects.filter(pk=note_id_int).exists()
             logger.info(f"[delete_note] FINAL CHECK: Note for id {note_id_int} exists after supposed delete: {exists_after_delete}")
             if exists_after_delete:
                  # Log critical error if item still exists
                  logger.error(f"[delete_note] CRITICAL: Item still exists after delete transaction committed!")
                  return JsonResponse({"success": False, "error": "刪除筆記時發生內部錯誤，請稍後再試", "remaining_limit": final_remaining_limit}, status=500)

        # Prepare success response
        response_data = {
            "success": True,
            "message": "筆記已刪除",
            "animal_id": animal_id, # Include animal_id for potential UI updates
            "remaining_limit": final_remaining_limit # Return the final limit count
        }
        logger.info(f"[delete_note] Returning success response: {response_data}")
        return JsonResponse(response_data)

    # --- Outer Exception Handling ---
    except UserProfile.DoesNotExist as e: # Catch if initial profile lock failed
        logger.error(f"[delete_note] Caught UserProfile.DoesNotExist outside transaction for user {user.username}: {e}")
        return JsonResponse({"success": False, "error": "找不到使用者設定檔"}, status=500)
    except Exception as e: # Catch any other unexpected errors
        logger.error(f"[delete_note] UNEXPECTED outer error for user {user.username}, note ID '{note_id_str}': {e}", exc_info=True)
        return JsonResponse({"success": False, "error": "刪除筆記時發生伺服器錯誤"}, status=500)


# --- update_note ---
@require_POST
@login_required
def update_note(request):
    note_id = request.POST.get("note_id")
    content = request.POST.get("content", "").strip()
    user = request.user
    logger.info(f"User {user.username} attempting to update note ID: {note_id}")

    # Validate inputs
    if not note_id:
        logger.warning("Update note failed: Missing note ID.")
        return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    if not content:
        logger.warning("Update note failed: Content is empty.")
        return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)

    try:
        note_id_int = int(note_id)
        # Ensure note exists and belongs to the user, fetch related animal
        note = get_object_or_404(Note.objects.select_related('animal'), id=note_id_int, user=user)
        animal = note.animal # Get animal for response data

        # Update note content and save
        note.content = content
        note.save(update_fields=['content', 'updated_at']) # Only update specific fields for efficiency
        logger.info(f"Note {note_id_int} updated successfully by user {user.username}.")

        # Fetch current notes limit for the response message
        try:
            remaining_limit = UserProfile.objects.get(user=user).notes_limit
            message = f"筆記已更新 (剩餘 {remaining_limit} 次)"
        except UserProfile.DoesNotExist:
             logger.error(f"UserProfile not found for user {user.username} when getting limit after update_note.")
             remaining_limit = '未知'
             message = "筆記已更新 (無法獲取剩餘次數)"

        # Return success response
        return JsonResponse({
            "success": True,
            "message": message,
            "note_id": note.id,
            "note_content": note.content, # Return updated content
            "animal_id": animal.id,
            "remaining_limit": remaining_limit
            })

    except Http404:
        logger.warning(f"Update note failed: Note ID {note_id} not found or does not belong to user {user.username}.")
        return JsonResponse({"success": False, "error": "筆記不存在或無權限修改"}, status=404)
    except ValueError: # Handle invalid note_id format (non-integer)
        logger.warning(f"Update note failed: Invalid note ID format: {note_id}")
        return JsonResponse({"success": False, "error": "無效的筆記 ID 格式"}, status=400)
    except UserProfile.DoesNotExist: # Should ideally not happen if user is logged in
         logger.error(f"UserProfile not found for user {user.username} during update_note limit fetch.")
         # Return success=True because note *was* updated, but indicate limit issue
         # Need to re-fetch note details if profile fetch fails mid-way
         try:
            note_details = Note.objects.values('id', 'content', 'animal_id').get(id=note_id_int)
            return JsonResponse({
               "success": True,
               "message": "筆記已更新 (無法獲取剩餘次數)",
               "note_id": note_details['id'],
               "note_content": note_details['content'],
               "animal_id": note_details['animal_id'],
               "remaining_limit": '錯誤'
            })
         except Note.DoesNotExist: # If note somehow got deleted between get and here
             return JsonResponse({"success": False, "error": "更新筆記時發生錯誤 (筆記不存在)"}, status=404)
         except Exception as inner_e:
              logger.error(f"Inner error fetching note details during UserProfile error handling: {inner_e}")
              return JsonResponse({"success": False, "error": "更新筆記時發生內部錯誤"}, status=500)

    except Exception as e: # Catch other potential errors during update or limit fetch
        logger.error(f"Error updating note ID {note_id} for user {user.username}: {e}", exc_info=True)
        return JsonResponse({"success": False, "error": "更新筆記時發生錯誤"}, status=500)


# --- AJAX Views (Stories, Schedule, HOF, Feedback) ---
@require_GET
def ajax_get_active_stories(request):
    logger.info("[ajax_get_active_stories] Fetching active stories.") # Log function entry
    try:
        now = timezone.now()
        # Log the current time for comparison
        logger.debug(f"[ajax_get_active_stories] Current time (UTC): {now}")

        active_stories_qs = StoryReview.objects.filter(
            animal__is_active=True,         # Filter active animal
            animal__hall__is_active=True,   # Filter active hall
            approved=True,                  # Filter approved story
            expires_at__gt=now              # Filter non-expired stories
        ).select_related(
            'animal', 'animal__hall', 'user' # Preload related objects
        ).order_by('-approved_at')           # Order by newest first

        # Log the count before serialization
        story_count = active_stories_qs.count()
        logger.info(f"[ajax_get_active_stories] Found {story_count} potential active stories in DB.")

        stories_data = []
        for s in active_stories_qs:
             # Log each story being processed
             logger.debug(f"[ajax_get_active_stories] Processing Story ID: {s.id}, Animal: {s.animal_id}, Expires: {s.expires_at}")
             try:
                 # Safely access related fields
                 animal_name = s.animal.name if s.animal else '未知美容師'
                 animal_photo_url = s.animal.photo.url if s.animal and s.animal.photo else None
                 hall_name = s.animal.hall.name if s.animal and s.animal.hall else '未知館別'
                 user_name = s.user.first_name or s.user.username if s.user else '匿名'
                 remaining_time = s.remaining_time_display # Access property safely

                 stories_data.append({
                     'id': s.id,
                     'animal_id': s.animal_id,
                     'animal_name': animal_name,
                     'animal_photo_url': animal_photo_url,
                     'hall_name': hall_name,
                     'user_name': user_name,
                     'remaining_time': remaining_time
                 })
             except Exception as serial_err:
                  # Log error during processing a specific story
                  logger.error(f"[ajax_get_active_stories] Error processing story ID {s.id}: {serial_err}", exc_info=True)
                  # Optionally skip this story or add a placeholder with error info

        # Log the final count being sent
        logger.info(f"[ajax_get_active_stories] Returning {len(stories_data)} stories in JSON response.")
        return JsonResponse({'stories': stories_data})
    except Exception as e:
        # Log unexpected errors in the view
        logger.error(f"[ajax_get_active_stories] Unexpected error: {e}", exc_info=True)
        return JsonResponse({'error': '無法載入限時動態', 'details': str(e)}, status=500)


@require_GET
def ajax_get_story_detail(request, story_id):
    logger.debug(f"Fetching story detail for story_id: {story_id}")
    try:
        now = timezone.now()
        # Fetch the specific story, ensuring it's active, approved, and not expired
        story = get_object_or_404(
            StoryReview.objects.filter(
                animal__is_active=True,      # Animal active
                animal__hall__is_active=True, # Hall active
                approved=True,               # Story approved
                expires_at__gt=now           # Story not expired
            ).select_related(
                'animal', 'animal__hall', 'user' # Optimize related fetching
            ).annotate(
                # Annotate feedback counts directly
                good_to_have_you_count=Count('feedback', filter=Q(feedback__feedback_type='good_to_have_you')),
                good_looking_count=Count('feedback', filter=Q(feedback__feedback_type='good_looking'))
            ),
            pk=story_id # Filter by primary key
        )
        animal = story.animal; user = story.user

        # Format timestamp safely
        approved_at_display = format_date(timezone.localtime(story.approved_at), 'Y-m-d H:i') if story.approved_at else ""

        # Get author ID and title
        author_id = user.id if user else None
        user_title = None
        if user:
            try:
                # Calculate total review count for title
                review_count = Review.objects.filter(user=user, approved=True).count()
                story_review_count = StoryReview.objects.filter(user=user, approved=True).count()
                total_count = review_count + story_review_count
                user_title = get_user_title_from_count(total_count)
            except Exception as count_err:
                logger.error(f"Error fetching total review count for user {user.id} in story detail: {count_err}", exc_info=True)

        # Prepare data for JSON response
        story_data = {
            'id': story.id, 'author_id': author_id, 'animal_id': animal.id, 'animal_name': animal.name,
            'animal_photo_url': animal.photo.url if animal.photo else None,
            'hall_name': animal.hall.name if animal.hall else '未知館別',
            'user_name': user.first_name or user.username if user else '匿名',
            'user_title': user_title, 'remaining_time': story.remaining_time_display,
            'approved_at_display': approved_at_display,
            # Include all relevant fields from the model
            'age': story.age, 'looks': story.looks, 'face': story.face, 'temperament': story.temperament,
            'physique': story.physique, 'cup': story.cup, 'cup_size': story.cup_size,
            'skin_texture': story.skin_texture, 'skin_color': story.skin_color,
            'music': story.music, 'music_price': story.music_price,
            'sports': story.sports, 'sports_price': story.sports_price,
            'scale': story.scale, 'content': story.content,
            # Include annotated feedback counts
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
        # Ensure hall exists and is active
        hall = get_object_or_404(Hall, id=hall_id_int, is_active=True)
        hall_name = hall.name
        logger.debug(f"Found active hall: {hall_name}")
    except (ValueError, TypeError):
        logger.warning(f"Invalid hall_id format for weekly schedule: {hall_id}")
        return JsonResponse({'success': False, 'error': '無效的館別 ID 格式'}, status=400)
    except Http404:
        # Try to get hall name even if inactive/not found for better error message
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
    except Exception as e: # Catch other errors fetching hall
        logger.error(f"Error getting Hall object for weekly schedule (ID {hall_id}): {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '獲取館別信息時發生錯誤'}, status=500)

    # Fetch schedule images for the found active hall
    try:
        schedules = WeeklySchedule.objects.filter(hall_id=hall_id_int).order_by('order')
        schedule_urls = [s.schedule_image.url for s in schedules if s.schedule_image] # Get URLs safely
        if schedule_urls:
            logger.debug(f"Found {len(schedule_urls)} weekly schedule images for hall {hall_name}.")
            return JsonResponse({'success': True, 'schedule_urls': schedule_urls, 'hall_name': hall_name})
        else:
            # No images found for this hall
            logger.info(f"No weekly schedule images found for hall {hall_name} (ID: {hall_id}).")
            return JsonResponse({'success': False, 'schedule_urls': [], 'hall_name': hall_name, 'message': f'{hall_name} 未上傳班表圖片'})
    except Exception as e:
        logger.error(f"Error fetching weekly schedule images for Hall ID {hall_id}: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '載入每週班表圖片出錯'}, status=500)

@require_GET
def ajax_get_hall_of_fame(request):
    logger.info("Fetching Hall of Fame data (multi-category).")
    rankings = {} # Dictionary to hold rankings for different types
    top_n = 10    # Number of users to show per category
    all_top_user_ids = set() # Collect all unique user IDs across rankings

    try:
        # --- Calculate Rankings for each category ---
        logger.debug("Calculating Review ranking...")
        review_ranks_qs = Review.objects.filter(approved=True, user__isnull=False) \
            .values('user') \
            .annotate(count=Count('id')) \
            .filter(count__gt=0) \
            .order_by('-count', 'user__username')[:top_n]
        review_ranks = list(review_ranks_qs) # Execute query
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

        # Calculate feedback rankings (received)
        feedback_ranks_data = {}
        feedback_types = ['good_looking', 'good_to_have_you']
        for fb_type in feedback_types:
            logger.debug(f"Calculating {fb_type} feedback ranking (received)...")
            # Annotate the recipient user ID using Coalesce
            recipient_id_annotation = Coalesce('review__user_id', 'story_review__user_id')
            feedback_ranks_qs = ReviewFeedback.objects.filter(feedback_type=fb_type) \
                .annotate(recipient_id=recipient_id_annotation) \
                .filter(recipient_id__isnull=False) \
                .values('recipient_id') \
                .annotate(count=Count('id')) \
                .filter(count__gt=0) \
                .order_by('-count', 'recipient_id')[:top_n] # Use recipient_id for tie-breaking if needed
            feedback_ranks_list = list(feedback_ranks_qs)
            feedback_ranks_data[fb_type] = feedback_ranks_list
            all_top_user_ids.update(f['recipient_id'] for f in feedback_ranks_list)
            logger.debug(f"{fb_type} feedback ranking calculated: {len(feedback_ranks_list)} users.")

        # --- Fetch User Details and Titles Efficiently ---
        logger.debug(f"Fetching details and titles for {len(all_top_user_ids)} unique top users.")
        # Fetch all relevant user objects in one query
        all_user_details = {u.id: u for u in User.objects.filter(id__in=all_top_user_ids)}

        # Calculate total review counts for titles
        user_total_counts = defaultdict(int)
        review_counts_all = Review.objects.filter(user_id__in=all_top_user_ids, approved=True).values('user_id').annotate(count=Count('id'))
        story_counts_all = StoryReview.objects.filter(user_id__in=all_top_user_ids, approved=True).values('user_id').annotate(count=Count('id'))
        for item in review_counts_all: user_total_counts[item['user_id']] += item['count']
        for item in story_counts_all: user_total_counts[item['user_id']] += item['count']

        # Get titles for all users
        all_user_titles = {
            user_id: get_user_title_from_count(user_total_counts.get(user_id, 0))
            for user_id in all_top_user_ids
        }
        logger.debug("User titles calculated.")

        # --- Format Ranking Data for JSON ---
        rankings['reviews'] = [
            {
                'rank': i + 1,
                # Use fetched user details, prefer first_name
                'user_name': all_user_details[r['user']].first_name or all_user_details[r['user']].username,
                'user_title': all_user_titles.get(r['user']), # Get calculated title
                'count': r['count'],
                'user_id': r['user'] # Include user ID if needed by frontend
            }
            for i, r in enumerate(review_ranks) if r['user'] in all_user_details # Ensure user exists
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
        # Format feedback rankings
        for fb_type, ranks_list in feedback_ranks_data.items():
            rankings[fb_type] = [
                {
                    'rank': i + 1,
                    'user_name': all_user_details[f['recipient_id']].first_name or all_user_details[f['recipient_id']].username,
                    'user_title': all_user_titles.get(f['recipient_id']), # Use recipient title
                    'count': f['count'],
                    'user_id': f['recipient_id']
                }
                for i, f in enumerate(ranks_list) if f['recipient_id'] in all_user_details # Ensure recipient user exists
            ]

        logger.debug(f"Final rankings data prepared: {list(rankings.keys())}")
        return JsonResponse({'success': True, 'rankings': rankings})

    except Exception as e:
        logger.error(f"Error in ajax_get_hall_of_fame: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '無法載入名人堂數據'}, status=500)

@login_required
@require_POST
def add_review_feedback(request):
    review_id = request.POST.get('review_id')
    story_review_id = request.POST.get('story_review_id')
    feedback_type = request.POST.get('feedback_type')
    user = request.user
    logger.info(f"User {user.username} attempting feedback type '{feedback_type}' on review_id='{review_id}', story_review_id='{story_review_id}'")

    # Validate feedback type
    valid_feedback_types = dict(ReviewFeedback.FEEDBACK_CHOICES).keys()
    if not feedback_type or feedback_type not in valid_feedback_types:
        logger.warning(f"Invalid feedback type: {feedback_type}")
        return JsonResponse({'success': False, 'error': '無效的回饋類型'}, status=400)

    # Ensure exactly one target ID is provided
    if not review_id and not story_review_id:
        logger.warning("Feedback attempt missing target review/story ID.")
        return JsonResponse({'success': False, 'error': '缺少目標心得 ID'}, status=400)
    if review_id and story_review_id:
        logger.warning("Feedback attempt provided both review and story ID.")
        return JsonResponse({'success': False, 'error': '不能同時提供兩種心得 ID'}, status=400)

    target_review = None; target_story_review = None; target_author = None; target_description = ""
    try:
        # Fetch the target review/story and check conditions
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
                # Ensure story is approved and not expired
                target_story_review = StoryReview.objects.select_related('user').get(pk=story_review_id, approved=True, expires_at__gt=timezone.now())
                target_author = target_story_review.user
                target_description = f"StoryReview ID {story_review_id}"
            except StoryReview.DoesNotExist:
                logger.warning(f"Feedback target StoryReview ID {story_review_id} not found, not approved, or expired.")
                return JsonResponse({'success': False, 'error': '找不到、未審核或已過期的限時動態心得'}, status=404)

        # Prevent self-feedback
        if target_author == user:
            logger.warning(f"User {user.username} attempted to give feedback on their own {target_description}.")
            return JsonResponse({'success': False, 'error': '不能對自己的心得給予回饋'}, status=403) # 403 Forbidden

        # Prepare data for get_or_create
        feedback_data = {'user': user, 'feedback_type': feedback_type, 'review': target_review, 'story_review': target_story_review }

        # Use transaction to ensure atomicity of check/create and count fetching
        with transaction.atomic():
            # Attempt to create the feedback record, check if it was newly created
            obj, created = ReviewFeedback.objects.get_or_create(**feedback_data)

            # Re-fetch counts after potential creation/check
            target_filter = Q(review=target_review) if review_id else Q(story_review=target_story_review)
            good_to_have_you_count = ReviewFeedback.objects.filter(target_filter, feedback_type='good_to_have_you').count()
            good_looking_count = ReviewFeedback.objects.filter(target_filter, feedback_type='good_looking').count()

            if not created:
                # Feedback already existed
                logger.info(f"User {user.username} already gave feedback '{feedback_type}' on {target_description}.")
                # Return updated counts even if already voted
                return JsonResponse({
                    'success': False,
                    'error': '你已經給過這個回饋了',
                    'good_to_have_you_count': good_to_have_you_count,
                    'good_looking_count': good_looking_count,
                }, status=409) # 409 Conflict

            # Feedback successfully created
            logger.info(f"Feedback '{feedback_type}' successfully added by user {user.username} to {target_description}.")
            return JsonResponse({
                'success': True,
                'message': '回饋成功！',
                'good_to_have_you_count': good_to_have_you_count,
                'good_looking_count': good_looking_count,
            })
    except Exception as e:
        logger.error(f"Error adding review feedback by user {user.username} for type '{feedback_type}' on {target_description}: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': '處理回饋時發生內部錯誤'}, status=500)


# --- View for fetching profile data ---
@login_required
@require_GET
def ajax_get_profile_data(request):
    user = request.user
    logger.info(f"Fetching profile data for user: {user.username} (ID: {user.id})")
    profile_data = {
        'username': user.username,
        'first_name': user.first_name or '', # Use first name if available
    }
    try:
        profile = UserProfile.objects.get(user=user)
        logger.debug(f"Profile object fetched: {profile}")

        # Calculate counts efficiently
        approved_reviews_count = Review.objects.filter(user=user, approved=True).count()
        approved_stories_count = StoryReview.objects.filter(user=user, approved=True).count()
        total_reviews = approved_reviews_count + approved_stories_count

        # Count feedback received by this user
        good_to_have_you_received = ReviewFeedback.objects.filter( Q(review__user=user) | Q(story_review__user=user), feedback_type='good_to_have_you' ).count()
        good_looking_received = ReviewFeedback.objects.filter( Q(review__user=user) | Q(story_review__user=user), feedback_type='good_looking' ).count()

        # Count current pending/notes items
        pending_count = PendingAppointment.objects.filter(user=user).count()
        notes_count = Note.objects.filter(user=user).count()

        # Get user title based on total reviews
        user_title = get_user_title_from_count(total_reviews)

        # Populate profile data dictionary
        profile_data['approved_reviews_count'] = approved_reviews_count
        profile_data['approved_stories_count'] = approved_stories_count
        profile_data['user_title'] = user_title
        profile_data['good_to_have_you_received'] = good_to_have_you_received
        profile_data['good_looking_received'] = good_looking_received
        profile_data['pending_count'] = pending_count # Current usage
        profile_data['notes_count'] = notes_count     # Current usage
        profile_data['max_pending_limit'] = profile.max_pending_limit # Max limit
        profile_data['max_notes_limit'] = profile.max_notes_limit     # Max limit

        logger.info(f"Profile data prepared for {user.username}: {profile_data}")
        return JsonResponse({'success': True, 'profile_data': profile_data})

    except UserProfile.DoesNotExist:
        # This should ideally not happen due to the post_save signal creating profiles
        logger.error(f"CRITICAL: UserProfile does NOT exist for user {user.username} (ID: {user.id}) in ajax_get_profile_data! Check user creation signal.")
        # Return default/error values
        profile_data.update({
             'approved_reviews_count': 0, 'approved_stories_count': 0, 'user_title': None,
             'good_to_have_you_received': 0, 'good_looking_received': 0,
             'pending_count': 0, 'notes_count': 0,
             'max_pending_limit': 0, 'max_notes_limit': 0 # Indicate 0 limits if profile missing
        })
        return JsonResponse({'success': False, 'error': '找不到使用者設定檔，請聯繫管理員', 'profile_data': profile_data}, status=500)
    except Exception as e:
        logger.error(f"Error fetching profile data for user {user.username}: {e}", exc_info=True)
        # Return N/A or error indicators
        profile_data.update({
             'approved_reviews_count': 'N/A', 'approved_stories_count': 'N/A', 'user_title': None,
             'good_to_have_you_received': 'N/A', 'good_looking_received': 'N/A',
             'pending_count': 'N/A', 'notes_count': 'N/A',
             'max_pending_limit': 'N/A', 'max_notes_limit': 'N/A'
        })
        return JsonResponse({'success': False, 'error': '讀取個人檔案資料時發生錯誤', 'profile_data': profile_data}, status=500)


# --- 搜尋 View (僅搜尋姓名 + 篩選) ---
@require_GET
def ajax_search_beauticians(request):
    """處理美容師搜尋的 AJAX 請求 (僅搜尋姓名，包含篩選條件)"""
    term = request.GET.get('q', '').strip()
    # --- 獲取篩選參數 ---
    min_height_str = request.GET.get('min_height', '').strip()
    max_height_str = request.GET.get('max_height', '').strip()
    min_weight_str = request.GET.get('min_weight', '').strip()
    max_weight_str = request.GET.get('max_weight', '').strip()
    cup_min_str = request.GET.get('cup_min', '').strip().upper() # Convert to uppercase for consistency
    cup_max_str = request.GET.get('cup_max', '').strip().upper()
    min_fee_str = request.GET.get('min_fee', '').strip()
    max_fee_str = request.GET.get('max_fee', '').strip()

    logger.info(
        f"Received AJAX search request. Name Term: '{term}', " # Updated log message
        f"Height: {min_height_str or 'Any'}-{max_height_str or 'Any'}, "
        f"Weight: {min_weight_str or 'Any'}-{max_weight_str or 'Any'}, "
        f"Cup Range: {cup_min_str or 'Any'}-{cup_max_str or 'Any'}, "
        f"Fee: {min_fee_str or 'Any'}-{max_fee_str or 'Any'}"
    )

    # --- 判斷是否有任何搜尋/篩選條件 ---
    has_keyword = bool(term)
    has_filters = bool(min_height_str or max_height_str or min_weight_str or max_weight_str or cup_min_str or cup_max_str or min_fee_str or max_fee_str)

    if not has_keyword and not has_filters:
        return JsonResponse({
            'table_html': '<tr class="empty-table-message"><td colspan="5">請輸入姓名或使用篩選器</td></tr>', # Updated prompt
            'first_animal': {}
        })

    try:
        # --- 驗證並轉換數字參數 ---
        min_height, max_height = None, None
        min_weight, max_weight = None, None
        min_fee, max_fee = None, None
        try:
            if min_height_str: min_height = int(min_height_str)
            if max_height_str: max_height = int(max_height_str)
            if min_weight_str: min_weight = int(min_weight_str)
            if max_weight_str: max_weight = int(max_weight_str)
            if min_fee_str: min_fee = int(min_fee_str)
            if max_fee_str: max_fee = int(max_fee_str)
            # Basic validation for ranges (min <= max if both provided)
            if min_height is not None and max_height is not None and min_height > max_height: min_height, max_height = max_height, min_height; logger.warning("Swapped min/max height.")
            if min_weight is not None and max_weight is not None and min_weight > max_weight: min_weight, max_weight = max_weight, min_weight; logger.warning("Swapped min/max weight.")
            if min_fee is not None and max_fee is not None and min_fee > max_fee: min_fee, max_fee = max_fee, min_fee; logger.warning("Swapped min/max fee.")
        except (ValueError, TypeError):
            logger.warning("Invalid number format in search filters. Ignoring invalid number fields.")
            # Reset invalid fields to None
            if not isinstance(min_height, int): min_height = None
            if not isinstance(max_height, int): max_height = None
            if not isinstance(min_weight, int): min_weight = None
            if not isinstance(max_weight, int): max_weight = None
            if not isinstance(min_fee, int): min_fee = None
            if not isinstance(max_fee, int): max_fee = None
            pass # Continue with other valid filters

        # --- 處理罩杯範圍 ---
        allowed_cups = [] # List of cup sizes to filter by
        if cup_min_str and cup_min_str in CUP_ORDER_MAP:
            min_cup_index = CUP_ORDER_MAP[cup_min_str]
            if cup_max_str and cup_max_str in CUP_ORDER_MAP:
                max_cup_index = CUP_ORDER_MAP[cup_max_str]
                # Ensure min_index <= max_index for a valid range
                if min_cup_index <= max_cup_index:
                    allowed_cups = CUP_ORDER[min_cup_index : max_cup_index + 1]
                else:
                    # If user selected invalid range (e.g., E-C), use only the minimum selected cup
                    allowed_cups = [cup_min_str]
                    logger.warning(f"Invalid cup range: min {cup_min_str} > max {cup_max_str}. Using only min value.")
            else:
                # Only minimum cup selected, include all cups from min onwards
                allowed_cups = CUP_ORDER[min_cup_index:]
        elif cup_max_str and cup_max_str in CUP_ORDER_MAP:
            # Only maximum cup selected, include all cups up to max
            max_cup_index = CUP_ORDER_MAP[cup_max_str]
            allowed_cups = CUP_ORDER[: max_cup_index + 1]

        if allowed_cups:
            logger.debug(f"Filtering by allowed cups: {allowed_cups}")

        # --- 查詢邏輯 ---
        # Start with base query for active animals/halls
        base_query = Animal.objects.filter(
            is_active=True
        ).filter(
            Q(hall__isnull=True) | Q(hall__is_active=True)
        )

        # *** 修改：只根據姓名搜尋 ***
        search_query = base_query
        if has_keyword:
             search_query = search_query.filter(
                Q(name__icontains=term) # Only filter by name
            )
        # *** -------------------- ***

        # --- 應用篩選條件 ---
        if min_height is not None: search_query = search_query.filter(height__gte=min_height)
        if max_height is not None: search_query = search_query.filter(height__lte=max_height)
        if min_weight is not None: search_query = search_query.filter(weight__gte=min_weight)
        if max_weight is not None: search_query = search_query.filter(weight__lte=max_weight)
        # *** 應用罩杯範圍篩選 ***
        if allowed_cups:
            search_query = search_query.filter(cup_size__in=allowed_cups)
        # *** ----------------- ***
        if min_fee is not None: search_query = search_query.filter(fee__gte=min_fee)
        if max_fee is not None: search_query = search_query.filter(fee__lte=max_fee)

        # --- Finalize query: Select related, annotate count, order, limit ---
        final_query = search_query.select_related('hall').annotate(
            approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        ).order_by('hall__order', 'order', 'name')

        results_limit = 50 # Limit the number of results returned
        search_results = list(final_query[:results_limit]) # Execute query and get list
        result_count = len(search_results) # Count items in the list

        logger.debug(f"Found {result_count} beauticians matching criteria (limit {results_limit})")

        # --- 渲染 HTML ---
        table_html = render_animal_rows(request, search_results, fetch_daily_slots=True) # Fetch slots for results

        # --- 獲取第一個結果 ---
        first_animal_data = {}
        if search_results: # Check if list is not empty
            first_animal_obj = search_results[0]
            try:
                first_animal_data = {
                    'photo_url': first_animal_obj.photo.url if first_animal_obj.photo else '',
                    'name': first_animal_obj.name or '',
                    'introduction': first_animal_obj.introduction or ''
                }
            except Exception as e:
                logger.warning(f"Error getting first animal data for search result (Animal ID {first_animal_obj.id}): {e}")

        # --- 處理空結果 ---
        if not table_html.strip() and result_count == 0:
             table_html = '<tr class="empty-table-message"><td colspan="5">找不到符合條件的美容師</td></tr>'

        return JsonResponse({
            'table_html': table_html,
            'first_animal': first_animal_data
        })

    except Exception as e:
        logger.error(f"Error during beautician search AJAX for term '{term}' and filters: {e}", exc_info=True)
        error_html = '<tr class="empty-table-message"><td colspan="5">搜尋時發生內部錯誤</td></tr>'
        return JsonResponse({'table_html': error_html, 'first_animal': {}}, status=500)
# --- Search View 結束 ---


# --- Admin Merge/Transfer View ---
@staff_member_required # Decorator to ensure only staff users can access
def merge_transfer_animal_view(request, animal_id):
    # Get the original animal record or return 404
    animal_original = get_object_or_404(Animal, pk=animal_id)
    logger.info(f"Admin merge/transfer view accessed for Animal ID: {animal_id} ({animal_original.name})")
    form = None # Initialize form

    if request.method == 'POST':
        logger.info("Handling POST request for animal merge/transfer.")
        # Pass original animal instance to the form for validation/context
        form = MergeTransferForm(request.POST, request.FILES, animal_original=animal_original)

        if form.is_valid():
            logger.debug("Merge/Transfer form is valid.")
            # Get validated data
            duplicate_animal = form.cleaned_data.get('duplicate_animal')
            target_hall = duplicate_animal.hall # Target hall is determined by the duplicate record selected
            new_name = duplicate_animal.name # Use the name from the duplicate record

            # --- Pre-merge Validations ---
            if not target_hall:
                logger.warning(f"Merge aborted: Duplicate animal {duplicate_animal.id} ({duplicate_animal.name}) has no assigned hall.")
                messages.error(request, f"合併失敗：選擇的重複記錄 '{duplicate_animal.name}' (ID: {duplicate_animal.id}) 沒有有效的館別，無法確定目標館別。")
                context = _get_merge_view_context(request, animal_original, form)
                return render(request, 'admin/myapp/animal/merge_transfer_form.html', context)

            # Check if another ACTIVE animal with the SAME NAME already exists in the TARGET HALL
            # Exclude the original and duplicate animals themselves from this check
            if Animal.objects.filter(
                hall=target_hall, name__iexact=new_name, is_active=True
            ).exclude(pk=animal_original.id).exclude(pk=duplicate_animal.id).exists():
                 logger.warning(f"Merge aborted: Another active animal named '{new_name}' already exists in target hall '{target_hall.name}'.")
                 messages.error(request, f"合併失敗：目標館別 '{target_hall.name}' 中已存在另一位啟用中的美容師名為 '{new_name}'。請先處理該衝突或選擇其他重複記錄。")
                 context = _get_merge_view_context(request, animal_original, form)
                 return render(request, 'admin/myapp/animal/merge_transfer_form.html', context)

            # --- Proceed with Merge Transaction ---
            logger.info(f"Processing merge: Duplicate ID {duplicate_animal.id} ({duplicate_animal.name}) into Original ID {animal_original.id} ({animal_original.name}). Target Hall: {target_hall.name}, New Name: {new_name}")
            try:
                with transaction.atomic(): # Ensure all operations succeed or fail together
                    logger.info(f"Starting transaction for MERGE animal ID {animal_original.id}...")
                    log_prefix = f"[Merge Animal ID {animal_original.id}]" # For cleaner logs

                    # 1. Copy descriptive data and tags from duplicate to original
                    logger.debug(f"{log_prefix} Applying descriptive data and tags from duplicate...")
                    if duplicate_animal.introduction: animal_original.introduction = duplicate_animal.introduction
                    # Handle photo - delete old if exists and different, then assign new
                    if duplicate_animal.photo:
                        if animal_original.photo and animal_original.photo.name != duplicate_animal.photo.name:
                            logger.debug(f"{log_prefix} Deleting old photo: {animal_original.photo.name}")
                            try: animal_original.photo.delete(save=False) # Delete file without saving model yet
                            except Exception as photo_delete_err: logger.warning(f"{log_prefix} Warning: Error deleting old photo file: {photo_delete_err}")
                        # Assign new photo if original doesn't have one or if they are different
                        if not animal_original.photo or (animal_original.photo and duplicate_animal.photo and animal_original.photo.name != duplicate_animal.photo.name):
                            animal_original.photo = duplicate_animal.photo
                            logger.debug(f"{log_prefix} Applied photo from duplicate.")
                    # Copy other fields if they have values in the duplicate
                    if duplicate_animal.fee is not None: animal_original.fee = duplicate_animal.fee
                    if duplicate_animal.height is not None: animal_original.height = duplicate_animal.height
                    if duplicate_animal.weight is not None: animal_original.weight = duplicate_animal.weight
                    if duplicate_animal.cup_size: animal_original.cup_size = duplicate_animal.cup_size
                    # Copy boolean tag fields
                    tag_fields_to_copy = ['is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer', 'is_featured']
                    for field_name in tag_fields_to_copy:
                        if hasattr(animal_original, field_name) and hasattr(duplicate_animal, field_name):
                            duplicate_value = getattr(duplicate_animal, field_name)
                            setattr(animal_original, field_name, duplicate_value)
                        else: logger.warning(f"{log_prefix} Tag field '{field_name}' not found on both models, skipping.")
                    logger.debug(f"{log_prefix} Descriptive data and tags applied.")

                    # 2. Transfer related records (Reviews, Stories, Notes, Pending)
                    logger.debug(f"{log_prefix} Transferring related records...")
                    models_to_transfer = [Review, StoryReview, Note, PendingAppointment]
                    for model_class in models_to_transfer:
                        model_name = model_class.__name__
                        logger.debug(f"{log_prefix} Processing {model_name} transfer...")
                        try:
                            # Check if model has the 'animal' foreign key
                            if hasattr(model_class, 'animal'):
                                duplicate_related_qs = model_class.objects.filter(animal=duplicate_animal)
                                if not duplicate_related_qs.exists():
                                    logger.debug(f"{log_prefix} No {model_name} records found for duplicate animal.")
                                    continue

                                # Special handling for models with unique_together constraints (Note, PendingAppointment)
                                if model_name in ['Note', 'PendingAppointment']:
                                    timestamp_field = 'updated_at' if model_name == 'Note' else 'added_at'
                                    logger.debug(f"{log_prefix} Special handling for {model_name} using {timestamp_field} for conflicts.")
                                    # Find users who have records for BOTH original and duplicate animals
                                    original_related_users = set(model_class.objects.filter(animal=animal_original).values_list('user_id', flat=True))
                                    duplicate_related_users = set(duplicate_related_qs.values_list('user_id', flat=True))
                                    conflicting_user_ids = original_related_users.intersection(duplicate_related_users)

                                    kept_from_duplicate_count = 0; deleted_from_duplicate_count = 0; deleted_from_original_count = 0
                                    # Resolve conflicts based on timestamp (keep the newer one)
                                    if conflicting_user_ids:
                                        logger.debug(f"{log_prefix} Found {len(conflicting_user_ids)} conflicts for {model_name}. Resolving...")
                                        for user_id in conflicting_user_ids:
                                            try:
                                                original_item = model_class.objects.get(animal=animal_original, user_id=user_id)
                                                duplicate_item = model_class.objects.get(animal=duplicate_animal, user_id=user_id)
                                                keep_original = True # Default to keeping original
                                                orig_ts = getattr(original_item, timestamp_field, None); dup_ts = getattr(duplicate_item, timestamp_field, None)
                                                # Compare timestamps if both exist
                                                if orig_ts and dup_ts:
                                                    if dup_ts > orig_ts: keep_original = False
                                                elif not orig_ts and dup_ts: keep_original = False # Keep duplicate if original has no timestamp

                                                if keep_original:
                                                    duplicate_item.delete(); deleted_from_duplicate_count += 1
                                                    logger.debug(f"{log_prefix} Conflict {model_name} User {user_id}: Kept original, deleted duplicate.")
                                                else: # Keep duplicate, delete original
                                                    original_item.delete(); deleted_from_original_count += 1
                                                    # Reassign the kept duplicate item to the original animal
                                                    duplicate_item.animal = animal_original; duplicate_item.save()
                                                    kept_from_duplicate_count += 1
                                                    logger.debug(f"{log_prefix} Conflict {model_name} User {user_id}: Kept duplicate (reassigned), deleted original.")
                                            except model_class.DoesNotExist: logger.warning(f"{log_prefix} Conflict resolution error: {model_name} not found for user {user_id} during conflict check.")
                                            except Exception as cr_err: logger.error(f"{log_prefix} Error resolving {model_name} conflict for user {user_id}: {cr_err}", exc_info=True); raise cr_err # Reraise to abort transaction
                                        logger.debug(f"{log_prefix} {model_name} Conflict resolution summary: Kept {kept_from_duplicate_count} (dup), Deleted {deleted_from_duplicate_count} (dup), Deleted {deleted_from_original_count} (orig).")
                                    else:
                                         logger.debug(f"{log_prefix} No user conflicts found for {model_name}.")

                                    # Update remaining non-conflicting items from duplicate
                                    remaining_update_qs = model_class.objects.filter(animal=duplicate_animal) # Re-query after potential deletes
                                    remaining_update_count = remaining_update_qs.count()
                                    updated_count_bulk = 0
                                    if remaining_update_count > 0:
                                        updated_count_bulk = remaining_update_qs.update(animal=animal_original) # Bulk update FK
                                        logger.debug(f"{log_prefix} {model_name} updated (remaining non-conflicting): {updated_count_bulk}")
                                    else:
                                        logger.debug(f"{log_prefix} No remaining non-conflicting {model_name} found for duplicate.")
                                    total_transferred_or_resolved = kept_from_duplicate_count + updated_count_bulk
                                else:
                                    # For models without unique constraints (Review, StoryReview), just bulk update
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
                            else:
                                logger.warning(f"{log_prefix} Skipping {model_name} transfer (model has no 'animal' field).")
                        except Exception as transfer_err:
                            logger.error(f"{log_prefix} Error transferring {model_name} from duplicate {duplicate_animal.id}: {transfer_err}", exc_info=True)
                            raise transfer_err # Reraise to abort transaction

                    # 3. Clean up ReviewFeedback associated with the duplicate's reviews/stories
                    logger.debug(f"{log_prefix} Cleaning up ReviewFeedback for duplicate animal...")
                    feedback_to_delete_qs = ReviewFeedback.objects.filter(
                        Q(review__animal=duplicate_animal) | Q(story_review__animal=duplicate_animal)
                    )
                    deleted_feedback_count, _ = feedback_to_delete_qs.delete()
                    if deleted_feedback_count > 0:
                         logger.info(f"{log_prefix} Deleted {deleted_feedback_count} ReviewFeedback records associated with duplicate's (ID: {duplicate_animal.id}) reviews/stories.")
                    else:
                         logger.debug(f"{log_prefix} No ReviewFeedback records found associated with duplicate's reviews/stories.")

                    # 4. Handle DailySchedule transfer/cleanup (if enabled)
                    if SCHEDULE_PARSER_ENABLED and DailySchedule:
                        logger.debug(f"{log_prefix} Handling DailySchedule cleanup and transfer...")
                        try:
                            duplicate_schedules_qs = DailySchedule.objects.filter(animal=duplicate_animal)
                            # Check if original animal already has a schedule in the *target* hall
                            original_schedule_in_target_hall = DailySchedule.objects.filter(animal=animal_original, hall=target_hall).first()

                            # Delete any schedules the original animal might have in *other* halls
                            deleted_orig_wrong_hall, _ = DailySchedule.objects.filter(animal=animal_original).exclude(hall=target_hall).delete()
                            if deleted_orig_wrong_hall > 0:
                                logger.info(f"{log_prefix} Cleaned up {deleted_orig_wrong_hall} pre-existing DailySchedule for original animal (ID {animal_original.id}) in incorrect halls.")

                            if original_schedule_in_target_hall:
                                # Original already has a schedule in the correct hall, discard duplicates
                                deleted_dup_count, _ = duplicate_schedules_qs.delete()
                                if deleted_dup_count > 0:
                                     logger.info(f"{log_prefix} Discarded {deleted_dup_count} DailySchedule from duplicate because original already has one in target hall.")
                            else:
                                # Original doesn't have a schedule in target hall, transfer one from duplicate if exists
                                schedule_to_transfer = duplicate_schedules_qs.first() # Get the first (or potentially only) schedule
                                if schedule_to_transfer:
                                    # Reassign the schedule to the original animal and correct hall
                                    schedule_to_transfer.animal = animal_original
                                    schedule_to_transfer.hall = target_hall
                                    schedule_to_transfer.save()
                                    logger.info(f"{log_prefix} Transferred DailySchedule (ID {schedule_to_transfer.id}) from duplicate to original in target hall.")
                                    # Delete any other schedules from the duplicate (shouldn't normally happen, but cleanup)
                                    deleted_other_dups, _ = duplicate_schedules_qs.exclude(pk=schedule_to_transfer.pk).delete()
                                    if deleted_other_dups > 0:
                                        logger.warning(f"{log_prefix} Deleted {deleted_other_dups} other redundant DailySchedule from duplicate ID {duplicate_animal.id}.")
                                else:
                                    logger.info(f"{log_prefix} No DailySchedule found for duplicate animal to transfer.")
                        except Exception as ds_err:
                            logger.error(f"{log_prefix} Error handling DailySchedule during merge: {ds_err}", exc_info=True)
                            raise ds_err # Abort transaction
                    else:
                        logger.debug(f"{log_prefix} Skipping DailySchedule handling (not enabled or model not found).")

                    # 5. Merge Aliases
                    logger.debug(f"{log_prefix} Merging aliases...")
                    original_aliases = animal_original.aliases if isinstance(animal_original.aliases, list) else []
                    duplicate_aliases = duplicate_animal.aliases if isinstance(duplicate_animal.aliases, list) else []
                    # Use sets for efficient merging and deduplication, handling potential non-string items
                    valid_original = {str(a).strip() for a in original_aliases if a and str(a).strip()}
                    valid_duplicate = {str(a).strip() for a in duplicate_aliases if a and str(a).strip()}
                    merged_aliases_set = valid_original.union(valid_duplicate)
                    # Add the duplicate's name and historical name@hall marker
                    if duplicate_animal.name not in merged_aliases_set:
                         merged_aliases_set.add(duplicate_animal.name)
                    if duplicate_animal.hall:
                        dup_history_marker = f"{duplicate_animal.name}@{duplicate_animal.hall.name}"
                        if dup_history_marker not in merged_aliases_set:
                            merged_aliases_set.add(dup_history_marker)
                    # Update original animal's aliases list
                    animal_original.aliases = list(merged_aliases_set)
                    logger.debug(f"{log_prefix} Aliases merged (pre-final update). Current set: {animal_original.aliases}")

                    # 6. Update Original Animal's Core Info (Hall, Name, Active status) and add history to aliases
                    logger.debug(f"{log_prefix} Updating final animal's core info...")
                    old_name = animal_original.name; old_hall = animal_original.hall
                    animal_original.hall = target_hall # Move to the duplicate's hall
                    animal_original.name = new_name # Adopt the duplicate's name
                    animal_original.is_active = True # Ensure the final record is active

                    # Add old name/hall info to aliases if changed
                    current_aliases_set = set(animal_original.aliases) # Use set for easy checking
                    if old_name != new_name and old_name not in current_aliases_set:
                        current_aliases_set.add(old_name)
                        logger.debug(f"{log_prefix} Added old name '{old_name}' to aliases.")
                    if old_hall != target_hall and old_hall and old_hall.name: # Check if old_hall exists and has a name
                        history_marker = f"{old_name}@{old_hall.name}"
                        if history_marker not in current_aliases_set:
                            current_aliases_set.add(history_marker)
                            logger.debug(f"{log_prefix} Added history marker '{history_marker}' to aliases.")
                    animal_original.aliases = list(current_aliases_set) # Convert back to list for JSON field

                    logger.debug(f"{log_prefix} Final state before save: Hall={animal_original.hall.name}, Name={animal_original.name}, Active={animal_original.is_active}, Aliases={animal_original.aliases}")
                    animal_original.save() # Save all changes to the original animal
                    logger.info(f"{log_prefix} Final animal (ID {animal_original.id}) saved successfully.")

                    # 7. Delete the Duplicate Animal Record
                    duplicate_pk_to_delete = duplicate_animal.pk; duplicate_name_to_delete = duplicate_animal.name
                    logger.info(f"{log_prefix} Deleting duplicate animal record ID: {duplicate_pk_to_delete} ({duplicate_name_to_delete})...")
                    # Optionally delete duplicate's photo file if it wasn't transferred
                    if duplicate_animal.photo and (not animal_original.photo or duplicate_animal.photo.name != animal_original.photo.name):
                        logger.debug(f"{log_prefix} Deleting photo file of duplicate: {duplicate_animal.photo.name}")
                        try: duplicate_animal.photo.delete(save=False)
                        except Exception as dup_photo_del_err: logger.warning(f"{log_prefix} Warning: Error deleting photo file for duplicate ID {duplicate_pk_to_delete}: {dup_photo_del_err}")
                    duplicate_animal.delete() # Delete the duplicate model instance
                    logger.info(f"{log_prefix} Duplicate animal deleted successfully.")

                # --- Transaction Complete ---
                logger.info(f"{log_prefix} Merge transaction completed successfully.")
                messages.success(request, f"美容師資料已成功從 '{duplicate_name_to_delete}' (ID: {duplicate_pk_to_delete}) 合併至 '{new_name}' @ '{target_hall.name}' (ID: {animal_original.id})。關聯記錄、標籤和班表已處理。")
                return redirect('admin:myapp_animal_changelist') # Redirect back to the animal list in admin
            except Exception as e:
                # Catch any error during the transaction
                logger.error(f"Error during MERGE transaction for animal {animal_original.id} from {duplicate_animal.id}: {e}", exc_info=True)
                error_message = f"處理合併時發生內部錯誤: {e}"
                # Provide more specific message for unique constraint errors
                if 'violates unique constraint' in str(e).lower():
                     error_message = f"處理合併時遇到資料庫唯一性衝突，操作未完成。請檢查資料。錯誤：{e}"
                messages.error(request, error_message)
                # Stay on the merge form page to show the error
                # No need to redirect here, just re-render the form below
        else:
            # Form is invalid
            logger.warning(f"Merge/Transfer form invalid. Errors: {form.errors.as_json()}")
            messages.error(request, "表單驗證失敗，請檢查輸入。")
            # Form will be re-rendered below with errors

    # Handle GET request or POST request with form errors
    if form is None:
        form = MergeTransferForm(animal_original=animal_original) # Initialize form for GET request

    # Prepare context for rendering the form template
    context = _get_merge_view_context(request, animal_original, form)
    return render(request, 'admin/myapp/animal/merge_transfer_form.html', context)

def _get_merge_view_context(request, animal_original, form):
    """Helper function to prepare context data for the merge/transfer form template."""
    approved_review_count = '計算錯誤'; story_review_count = '計算錯誤'; notes_count = '計算錯誤'; pending_count = '計算錯誤'; aliases_display_text = '獲取錯誤'; daily_schedule_info = '未啟用或錯誤'

    try:
        # Count related objects for display
        approved_review_count = Review.objects.filter(animal=animal_original, approved=True).count()
        story_review_count = StoryReview.objects.filter(animal=animal_original, approved=True).count()
        notes_count = Note.objects.filter(animal=animal_original).count()
        pending_count = PendingAppointment.objects.filter(animal=animal_original).count()

        # Format aliases for display (truncate if too long)
        aliases_data = animal_original.aliases
        if isinstance(aliases_data, list):
            display_aliases = [str(a).strip() for a in aliases_data if a and str(a).strip()]
            display_text_list = display_aliases[:3] # Show first 3 aliases
            suffix = '...' if len(display_aliases) > 3 else ''
            aliases_display_text = ", ".join(display_text_list) + suffix if display_text_list else "無"
        elif isinstance(aliases_data, str) and aliases_data.strip():
             aliases_display_text = aliases_data[:30] + ('...' if len(aliases_data) > 30 else '')
        elif aliases_data: # Handle other potential non-list/non-string types
            aliases_display_text = str(aliases_data)
        else:
            aliases_display_text = "無"

        # Get Daily Schedule info if enabled
        if SCHEDULE_PARSER_ENABLED and DailySchedule:
             try:
                 schedule = DailySchedule.objects.filter(animal=animal_original).first()
                 if schedule:
                     daily_schedule_info = f"館別: {schedule.hall.name if schedule.hall else '未知'}, 時段: {schedule.time_slots or '無'}, 日期: {schedule.date}"
                 else:
                     daily_schedule_info = "無記錄"
             except Exception as ds_err:
                  logger.warning(f"Error fetching DailySchedule info for animal {animal_original.id} in context: {ds_err}")
                  daily_schedule_info = f"讀取錯誤: {ds_err}"
        else:
             daily_schedule_info = "每日班表功能未啟用"
    except Exception as count_error:
        logger.warning(f"Warning: Error counting related objects or formatting aliases for animal {animal_original.id} in context: {count_error}")

    # Standard admin context variables
    opts = Animal._meta
    app_label = opts.app_label
    has_view_permission = request.user.has_perm(f'{app_label}.view_animal')
    has_change_permission = request.user.has_perm(f'{app_label}.change_animal')
    has_delete_permission = request.user.has_perm(f'{app_label}.delete_animal')
    has_add_permission = request.user.has_perm(f'{app_label}.add_animal')

    context = {
        'title': f"合併/轉移 美容師資料: {animal_original.name}",
        'animal_original': animal_original,
        'form': form,
        # Admin template requires these
        'opts': opts,
        'has_view_permission': has_view_permission,
        'has_change_permission': has_change_permission,
        'has_delete_permission': has_delete_permission,
        'is_popup': False, # Not a popup
        'save_as': False, # Not save as new
        'has_add_permission': has_add_permission,
        'app_label': app_label,
        # Custom context data for display
        'approved_review_count': approved_review_count,
        'story_review_count': story_review_count,
        'notes_count': notes_count,
        'pending_count': pending_count,
        'aliases_display_text': aliases_display_text,
        'daily_schedule_info': daily_schedule_info,
    }
    return context

# --- views.py File End ---