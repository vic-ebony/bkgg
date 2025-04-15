# myapp/views.py
# (No changes to existing imports)
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.dateformat import format as format_date # Import date formatting
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, Http404 # Import Http404
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Prefetch, Max
from django.views.decorators.http import require_POST, require_GET # Import require_GET
from django.template.loader import render_to_string
# --- Import WeeklySchedule ---
from .models import Animal, Hall, Review, PendingAppointment, Note, Announcement, StoryReview, WeeklySchedule
import traceback

# --- Helper function to render table rows ---
# (Moved rendering logic here to avoid repetition)
def render_animal_rows(request, animals_qs):
    pending_ids = set()
    notes_by_animal = {}
    if request.user.is_authenticated:
        animal_ids_on_page = [a.id for a in animals_qs]
        pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user, animal_id__in=animal_ids_on_page))
        # *** MODIFICATION: Fetch notes specifically for the animals being rendered ***
        # We fetch notes based on user and the animals currently in the queryset.
        # The logic deciding WHICH animals are in the queryset happens in the calling view (e.g., ajax_get_my_notes filters by hall).
        notes_qs = Note.objects.filter(user=request.user, animal_id__in=animal_ids_on_page)
        notes_by_animal = {str(note.animal_id): note for note in notes_qs}
        # *** END MODIFICATION ***

    rendered_rows_html_list = []
    for animal_instance in animals_qs:
        # --- START FIX: Calculate review count within the loop if not annotated ---
        # Check if the annotation exists, otherwise calculate it
        if not hasattr(animal_instance, 'approved_review_count'):
            # This is less efficient than annotating, but provides a fallback
            try:
                animal_instance.approved_review_count = Review.objects.filter(animal=animal_instance, approved=True).count()
            except Exception as count_err:
                print(f"    Warning: Error calculating review count for {animal_instance.id} in render_animal_rows: {count_err}")
                animal_instance.approved_review_count = 0
        # --- END FIX ---

        row_context = {
            'animal': animal_instance,
            'user': request.user,
            'pending_ids': pending_ids,
            'notes_by_animal': notes_by_animal # Pass the potentially filtered notes dictionary
        }
        try:
            # *** Ensure the correct partial is used ***
            # It seems _animal_table_rows.html expects a single animal context,
            # so we render one row at a time within the loop.
            rendered_html_for_animal = render_to_string('partials/_animal_table_rows.html', row_context, request=request)
            rendered_rows_html_list.append(rendered_html_for_animal)
        except Exception as render_err:
            print(f"    !!! Error rendering partial for animal {animal_instance.id}: {render_err} !!!")
            traceback.print_exc()
            rendered_rows_html_list.append(f'<tr><td colspan="5">Error loading data for {animal_instance.name}</td></tr>')

    return "".join(rendered_rows_html_list)


# --- Home View (Initial Page Load & Daily Schedule AJAX) ---
def home(request):
    is_ajax_request = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    is_daily_schedule_ajax = is_ajax_request and request.GET.get('ajax') == '1'

    print("-" * 20); print(f"Request Path: {request.path}"); print(f"Request GET Params: {request.GET}")
    print(f"Is AJAX Header Present: {is_ajax_request}"); print(f"Handling as Daily Schedule AJAX: {is_daily_schedule_ajax}")

    if is_daily_schedule_ajax:
        # --- AJAX Handling for Daily Schedule ---
        print(">>> Handling as Daily Schedule AJAX Request <<<")
        hall_id = request.GET.get('hall_id')
        selected_hall_id = hall_id or 'all' # Default to 'all' if not provided
        print(f"    Selected Hall ID for Daily Schedule: {selected_hall_id}")
        try:
            animals_base_qs = Animal.objects.filter(is_active=True).select_related('hall')
            if selected_hall_id != "all":
                try:
                    hall_id_int = int(selected_hall_id)
                    animals_qs = animals_base_qs.filter(hall_id=hall_id_int)
                except (ValueError, TypeError):
                    print(f"    Warning: Invalid hall_id '{selected_hall_id}' for Daily Schedule. Defaulting to all.")
                    animals_qs = animals_base_qs.all() # Fallback to all if invalid ID
            else:
                animals_qs = animals_base_qs.all() # Explicitly handle 'all'

            # Apply sorting for daily schedule
            animals_for_ajax = animals_qs.annotate(
                approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
            ).order_by(
                '-is_hidden_edition', '-is_exclusive', '-is_hot', '-is_newcomer', 'order', 'name'
            )

            # *** Pass the filtered animals queryset to the helper ***
            table_html = render_animal_rows(request, animals_for_ajax)
            print(f"    Daily Schedule AJAX Partial HTML rendered successfully (total length: {len(table_html)}).")

            first_animal_data = {}
            try:
                # *** Fetch first animal from the filtered+sorted list for the top section ***
                if animals_for_ajax.exists(): # Use exists() for efficiency
                     first_animal = animals_for_ajax.first()
                     first_animal_data = {
                         'photo_url': first_animal.photo.url if first_animal.photo else '',
                         'name': first_animal.name or '',
                         'introduction': first_animal.introduction or ''
                     }
            except Exception as e:
                print(f"    Warning: Error getting first animal data for Daily Schedule AJAX response: {e}")

            print(f"    Returning JSON including table_html and first_animal data for Daily Schedule.")
            return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
        except Exception as e:
            print(f"    !!! Error during Daily Schedule AJAX handling: {e} !!!")
            traceback.print_exc()
            return JsonResponse({'error': f'伺服器處理班表請求時發生錯誤: {e}'}, status=500)
    else:
        # --- Full Page Rendering (Keep pre-loading data for initial view) ---
        print(">>> Handling as Full Page Request (Rendering index.html) <<<")
        halls = Hall.objects.all().order_by('order', 'name')
        context = {'halls': halls, 'user': request.user}

        # --- *** START FIX: Fetch initial pending count for the logged-in user *** ---
        initial_pending_count = 0
        if request.user.is_authenticated:
            try:
                initial_pending_count = PendingAppointment.objects.filter(user=request.user).count()
                print(f"    User '{request.user.username}' authenticated. Initial pending count: {initial_pending_count}")
            except Exception as e:
                print(f"    !!! Error fetching initial pending count for user {request.user.username}: {e} !!!")
        else:
             print("    User not authenticated. Initial pending count: 0")
        context['pending_count'] = initial_pending_count # Add the count to the context
        # --- *** END FIX *** ---

        try: context['announcement'] = Announcement.objects.filter(is_active=True).order_by('-created_at').first()
        except Exception as e: print(f"Error fetching announcement: {e}"); context['announcement'] = None
        try:
            first_animal_for_promo = Animal.objects.filter(is_active=True, photo__isnull=False).exclude(photo='').order_by('?').first()
            context['promo_photo_url'] = first_animal_for_promo.photo.url if first_animal_for_promo else None
            context['promo_animal_name'] = first_animal_for_promo.name if first_animal_for_promo else None
        except Exception as e: print(f"Error fetching promo photo: {e}"); context['promo_photo_url'] = None; context['promo_animal_name'] = None

        # Removed preloading of pending/notes/latest/recommended here as they are now loaded via AJAX
        context['pending_ids'] = set() # Initialize as empty, AJAX will populate if needed by other means
        context['notes_by_animal'] = {} # Initialize as empty

        # We pass 'halls' to the context so the hall menus in the modals can be rendered initially.
        context['halls'] = halls

        login_error = request.session.pop('login_error', None);
        if login_error: context['login_error'] = login_error
        context['selected_hall_id'] = 'all' # Default for daily schedule initial view (JS might override)

        # --- START: Fetch Active Story Reviews for initial load ---
        # No need to preload story data, it will be fetched via AJAX by JavaScript
        # --- END: Fetch Active Story Reviews ---

        print("    Rendering full template: index.html")
        try:
            return render(request, 'index.html', context)
        except Exception as e:
            print(f"    !!! Error rendering index.html: {e} !!!"); traceback.print_exc()
            return render(request, 'error_page.html', {'error_message': '渲染頁面時發生內部錯誤'}, status=500)


# --- AJAX View for Pending List ---
@login_required
@require_GET # This view only handles GET requests
def ajax_get_pending_list(request):
    print(">>> Handling AJAX Request for Pending List <<<")
    try:
        # Fetch pending appointments for the user
        pending_appointments_qs = PendingAppointment.objects.filter(
            user=request.user
        ).select_related(
            'animal', 'animal__hall'
        ).order_by('-added_at')

        # Extract the related Animal objects
        # We need to annotate the review count onto the Animal objects themselves
        animal_ids = list(pending_appointments_qs.values_list('animal_id', flat=True))
        animals_qs = Animal.objects.filter(id__in=animal_ids).annotate(
             approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
        )

        # Create a dictionary for easy lookup
        animals_dict = {a.id: a for a in animals_qs}

        # Reconstruct the list of animals in the original pending order
        # and attach the count
        animals_list_ordered = []
        for pa in pending_appointments_qs:
            animal = animals_dict.get(pa.animal_id)
            if animal:
                # The count is already annotated on the animal object from the animals_qs query
                animals_list_ordered.append(animal)

        # Render table rows using the helper function
        table_html = render_animal_rows(request, animals_list_ordered)

        # Get data for the first animal in the list for the top section
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
        print(f"!!! Error in ajax_get_pending_list: {e} !!!"); traceback.print_exc()
        return JsonResponse({'error': '無法載入待約清單'}, status=500)


# --- *** MODIFIED: AJAX View for My Notes (Handles Hall Filtering) *** ---
@login_required
@require_GET
def ajax_get_my_notes(request):
    print(">>> Handling AJAX Request for My Notes <<<")
    hall_id = request.GET.get('hall_id') # Get hall_id from query parameter
    selected_hall_id = hall_id or 'all' # Default to 'all' if not provided
    print(f"    Selected Hall ID for My Notes: {selected_hall_id}")

    try:
        # Base query for notes belonging to the logged-in user
        notes_base_qs = Note.objects.filter(
            user=request.user
        ).select_related(
            'animal', 'animal__hall' # Select related animal and its hall
        )

        # Apply hall filter if a specific hall ID is provided and valid
        if selected_hall_id != "all":
            try:
                hall_id_int = int(selected_hall_id)
                # Filter notes where the related animal belongs to the specified hall
                notes_qs = notes_base_qs.filter(animal__hall_id=hall_id_int)
            except (ValueError, TypeError):
                print(f"    Warning: Invalid hall_id '{selected_hall_id}' for My Notes. Defaulting to all.")
                # If hall_id is invalid, return all notes for the user (same as 'all')
                notes_qs = notes_base_qs.all()
        else:
            # If 'all' is selected, use the base query without hall filtering
            notes_qs = notes_base_qs.all()

        # Order the filtered notes (e.g., by last updated)
        notes_qs = notes_qs.order_by('-updated_at')

        # Extract the related Animal objects from the filtered notes
        animal_ids = list(notes_qs.values_list('animal_id', flat=True))
        if not animal_ids: # Handle case where there are no notes (or no notes for the selected hall)
             animals_list_ordered = []
        else:
            animals_qs = Animal.objects.filter(id__in=animal_ids).annotate(
                 approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
            )
             # Create a dictionary for easy lookup
            animals_dict = {a.id: a for a in animals_qs}
             # Reconstruct the list of animals in the original note order
            animals_list_ordered = []
            for note in notes_qs:
                animal = animals_dict.get(note.animal_id)
                if animal:
                    # The count is already annotated on the animal object
                    animals_list_ordered.append(animal)

        # Render table rows using the helper function with the ordered list of animals
        table_html = render_animal_rows(request, animals_list_ordered)
        print(f"    My Notes AJAX (Hall: {selected_hall_id}) Partial HTML rendered successfully (total length: {len(table_html)}).")

        # Get data for the first animal in the potentially filtered list
        first_animal_data = {}
        if animals_list_ordered:
            first_animal = animals_list_ordered[0]
            first_animal_data = {
                'photo_url': first_animal.photo.url if first_animal.photo else '',
                'name': first_animal.name or '',
                'introduction': first_animal.introduction or ''
            }

        print(f"    Returning JSON for My Notes (Hall: {selected_hall_id}).")
        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_my_notes: {e} !!!"); traceback.print_exc()
        return JsonResponse({'error': f'無法載入我的筆記 (Hall: {selected_hall_id}): {e}'}, status=500)
# --- *** END MODIFICATION *** ---

# --- AJAX View for Latest Reviews ---
@require_GET # Allow anonymous access if needed, or add @login_required
def ajax_get_latest_reviews(request):
    print(">>> Handling AJAX Request for Latest Reviews <<<")
    try:
        latest_reviewed_animals_qs = Animal.objects.filter(is_active=True) \
            .annotate(latest_review_time=Max('reviews__created_at', filter=Q(reviews__approved=True))) \
            .filter(latest_review_time__isnull=False) \
            .annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True))) \
            .select_related('hall') \
            .order_by('-latest_review_time') \
            [:20] # Limit to 20

        table_html = render_animal_rows(request, latest_reviewed_animals_qs) # Pass the queryset directly

        first_animal_data = {}
        if latest_reviewed_animals_qs.exists(): # Use exists()
             first_animal = latest_reviewed_animals_qs.first() # Use first()
             first_animal_data = {
                 'photo_url': first_animal.photo.url if first_animal.photo else '',
                 'name': first_animal.name or '',
                 'introduction': first_animal.introduction or ''
             }

        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_latest_reviews: {e} !!!"); traceback.print_exc()
        return JsonResponse({'error': '無法載入最新心得'}, status=500)


# --- AJAX View for Recommendations ---
@require_GET # Allow anonymous access if needed
def ajax_get_recommendations(request):
    print(">>> Handling AJAX Request for Recommendations <<<")
    try:
        recommended_animals_qs = Animal.objects.filter(is_active=True, is_recommended=True) \
            .select_related('hall') \
            .annotate(approved_review_count=Count('reviews', filter=Q(reviews__approved=True))) \
            .order_by('hall__order', 'order', 'name')

        table_html = render_animal_rows(request, recommended_animals_qs) # Pass the queryset

        first_animal_data = {}
        if recommended_animals_qs.exists(): # Use exists()
            first_animal = recommended_animals_qs.first() # Use first()
            first_animal_data = {
                'photo_url': first_animal.photo.url if first_animal.photo else '',
                'name': first_animal.name or '',
                'introduction': first_animal.introduction or ''
            }

        return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_recommendations: {e} !!!"); traceback.print_exc()
        return JsonResponse({'error': '無法載入每日推薦'}, status=500)


# --- User Authentication Views (Keep as is) ---
def user_login(request):
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        if not username or not password:
             request.session['login_error'] = '請輸入帳號和密碼'
             return redirect('home')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            request.session.pop('login_error', None)
            print(f"User '{username}' logged in successfully.")
            return redirect('home')
        else:
            print(f"Login failed for user '{username}'.")
            request.session['login_error'] = '帳號或密碼錯誤'
            return redirect('home')
    return redirect('home')

@require_POST
def user_logout(request):
    user_display = request.user.username if request.user.is_authenticated else "Unknown user"
    logout(request)
    print(f"User '{user_display}' logged out.")
    return redirect('home')

# --- START: New View for Adding Story Review ---
@login_required
@require_POST
def add_story_review(request):
    print(">>> Handling POST Request for Adding Story Review <<<")
    animal_id = request.POST.get("animal_id")
    animal = get_object_or_404(Animal, id=animal_id)

    # Reuse validation logic and data extraction from add_review
    face_list = request.POST.getlist("face")
    temperament_list = request.POST.getlist("temperament")
    scale_list = request.POST.getlist("scale")
    content = request.POST.get("content", "").strip()
    age_str = request.POST.get("age")
    # Note: Cup size from review form is named 'cup_size', map it correctly
    cup_size_value = request.POST.get("cup_size","") # Get the value from the <select>

    errors = {}
    if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
    if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
    # Scale has no limit in this form version
    if not content: errors['content'] = "心得內容不能為空"
    age = None
    if age_str:
        try:
            age = int(age_str)
            if age <= 0: errors['age'] = "年紀必須是正數"
        except (ValueError, TypeError): errors['age'] = "年紀必須是有效的數字"

    if errors:
        print(f"Story Review submission failed validation for animal {animal_id}: {errors}")
        # Return detailed errors if available
        error_message = "輸入無效"
        if errors:
             error_message += ": " + "; ".join([f"{k}: {v}" for k, v in errors.items()])
        return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)

    try:
        new_story = StoryReview.objects.create(
            animal=animal,
            user=request.user,
            age=age,
            looks=request.POST.get("looks") or None,
            face=','.join(face_list),
            temperament=','.join(temperament_list),
            physique=request.POST.get("physique") or None,
            cup=request.POST.get("cup") or None,
            cup_size=cup_size_value or None, # Use the value from the select
            skin_texture=request.POST.get("skin_texture") or None,
            skin_color=request.POST.get("skin_color") or None,
            music=request.POST.get("music") or None,
            music_price=request.POST.get("music_price") or None,
            sports=request.POST.get("sports") or None,
            sports_price=request.POST.get("sports_price") or None,
            scale=','.join(scale_list),
            content=content,
            approved=False, # Default to False, admin needs to approve
            approved_at=None, # Will be set by signal/admin
            expires_at=None   # Will be set by signal/admin
        )
        print(f"Story Review {new_story.id} created for animal {animal_id} by user {request.user.username}. Needs approval.")
        return JsonResponse({"success": True, "message": "限時動態心得已提交，待審核後將顯示"})
    except Exception as e:
        print(f"Error creating story review for animal {animal_id}: {e}")
        traceback.print_exc()
        return JsonResponse({"success": False, "error": "儲存限時動態心得時發生內部錯誤"}, status=500)
# --- END: New View for Adding Story Review ---


# --- Review Handling View (Keep as is, handles GET for review list and POST for submission) ---
@login_required
def add_review(request):
    if request.method == "POST":
        print(">>> Handling POST Request for Adding Regular Review <<<")
        animal_id = request.POST.get("animal_id")
        animal = get_object_or_404(Animal, id=animal_id)

        face_list = request.POST.getlist("face")
        temperament_list = request.POST.getlist("temperament")
        scale_list = request.POST.getlist("scale")
        content = request.POST.get("content", "").strip()
        age_str = request.POST.get("age")
        # Note: Cup size from review form is named 'cup_size', map it correctly
        cup_size_value = request.POST.get("cup_size","") # Get the value from the <select>

        errors = {}
        if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
        if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
        # Scale has no limit in this form version
        if not content: errors['content'] = "心得內容不能為空"
        age = None
        if age_str:
            try:
                age = int(age_str)
                if age <= 0: errors['age'] = "年紀必須是正數"
            except (ValueError, TypeError): errors['age'] = "年紀必須是有效的數字"

        if errors:
            print(f"Review submission failed validation for animal {animal_id}: {errors}")
            error_message = "輸入無效"
            if errors:
                 error_message += ": " + "; ".join([f"{k}: {v}" for k, v in errors.items()])
            return JsonResponse({"success": False, "error": error_message, "errors": errors}, status=400)

        try:
            new_review = Review.objects.create(
                animal=animal, user=request.user, age=age,
                looks=request.POST.get("looks") or None,
                face=','.join(face_list),
                temperament=','.join(temperament_list),
                physique=request.POST.get("physique") or None,
                cup=request.POST.get("cup") or None,
                cup_size=cup_size_value or None, # Use the value from the select
                skin_texture=request.POST.get("skin_texture") or None,
                skin_color=request.POST.get("skin_color") or None,
                music=request.POST.get("music") or None,
                music_price=request.POST.get("music_price") or None,
                sports=request.POST.get("sports") or None,
                sports_price=request.POST.get("sports_price") or None,
                scale=','.join(scale_list),
                content=content,
                approved=False
            )
            print(f"Review {new_review.id} created for animal {animal_id} by user {request.user.username}.")
            return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
        except Exception as e:
             print(f"Error creating review for animal {animal_id}: {e}")
             traceback.print_exc()
             return JsonResponse({"success": False, "error": "儲存心得時發生內部錯誤"}, status=500)

    elif request.method == "GET": # Handles fetching reviews for the review modal
        animal_id = request.GET.get("animal_id")
        animal = get_object_or_404(Animal, id=animal_id)
        print(f"Fetching reviews for animal {animal_id} (User: {request.user.username})")

        reviews_qs = Review.objects.filter(animal=animal, approved=True).select_related('user').order_by("-created_at")

        user_ids = list(reviews_qs.values_list('user_id', flat=True).distinct())
        user_review_counts = {}
        if user_ids:
            try:
                 counts_query = Review.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(totalCount=Count('id'))
                 user_review_counts = {item['user_id']: item['totalCount'] for item in counts_query}
            except Exception as count_err:
                 print(f"Error fetching user review counts: {count_err}")

        data = []
        for r in reviews_qs:
            user_display_name = "匿名"
            if hasattr(r, 'user') and r.user:
                user_display_name = r.user.first_name or r.user.username
            formatted_date = ""
            if r.created_at:
                try: formatted_date = timezone.localtime(r.created_at).strftime("%Y-%m-%d")
                except Exception as date_err: print(f"Error formatting date {r.created_at} for review {r.id}: {date_err}")
            data.append({
                "id": r.id, "user": user_display_name, "totalCount": user_review_counts.get(r.user_id, 0),
                "age": r.age, "looks": r.looks, "face": r.face, "temperament": r.temperament,
                "physique": r.physique, "cup": r.cup, "cup_size": r.cup_size,
                "skin_texture": r.skin_texture, "skin_color": r.skin_color,
                "music": r.music, "music_price": r.music_price,
                "sports": r.sports, "sports_price": r.sports_price,
                "scale": r.scale, "content": r.content, "created_at": formatted_date
            })
        print(f"Returning {len(data)} reviews for animal {animal_id}.")
        return JsonResponse({"reviews": data})

    return JsonResponse({"success": False, "error": "請求方法不支援"}, status=405)


# --- Pending Appointment Handling Views (Keep as is, JS will handle refresh if needed) ---
@require_POST
@login_required
def add_pending_appointment(request):
    animal_id = request.POST.get("animal_id")
    animal = get_object_or_404(Animal, id=animal_id)
    user = request.user
    try:
        obj, created = PendingAppointment.objects.get_or_create(user=user, animal=animal)
        pending_count = PendingAppointment.objects.filter(user=user).count() # Recalculate count after operation
        message = f"{animal.name} 已加入待約清單" if created else f"{animal.name} 已在待約清單中"
        print(f"Pending action for animal {animal_id} by user {user.username}: {'Added' if created else 'Already Exists'}. Count: {pending_count}")
        return JsonResponse({"success": True, "message": message, "pending_count": pending_count})
    except (ValueError, TypeError) as e:
        print(f"Error adding pending (invalid ID format?) for animal_id '{animal_id}': {e}")
        return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    except Exception as e:
        print(f"Error adding pending for animal {animal_id}: {e}"); traceback.print_exc()
        return JsonResponse({"success": False, "error": "加入待約時發生錯誤"}, status=500)

@require_POST
@login_required
def remove_pending(request):
    animal_id = request.POST.get("animal_id")
    user = request.user
    try:
        try: animal_id_int = int(animal_id)
        except (ValueError, TypeError): raise ValueError("無效的動物 ID 格式")
        deleted_count, _ = PendingAppointment.objects.filter(user=user, animal_id=animal_id_int).delete()
        pending_count = PendingAppointment.objects.filter(user=user).count() # Recalculate count after operation
        if deleted_count == 0:
            if not Animal.objects.filter(id=animal_id_int).exists():
                print(f"Remove pending failed: Animal {animal_id_int} not found (User: {user.username}).")
                # Still return the current count even if the delete technically failed because the item wasn't there
                return JsonResponse({"success": False, "error": "找不到該動物", "pending_count": pending_count}, status=404)
            else:
                print(f"Remove pending failed: Animal {animal_id_int} was not pending for user {user.username}.")
                # Still return the current count
                return JsonResponse({"success": False, "error": "該待約項目不存在", "pending_count": pending_count})
        animal_name = Animal.objects.filter(id=animal_id_int).values_list('name', flat=True).first() or "該美容師"
        print(f"Pending removed for animal {animal_id_int} by user {user.username}. Count: {pending_count}")
        return JsonResponse({
            "success": True, "message": f"{animal_name} 待約項目已移除",
            "pending_count": pending_count, "animal_id": animal_id_int
        })
    except ValueError as ve:
         print(f"Error removing pending: {ve} (Raw ID: '{animal_id}')")
         # Try to return the current count even on error if possible
         current_count = 0
         if request.user.is_authenticated:
             current_count = PendingAppointment.objects.filter(user=user).count()
         return JsonResponse({"success": False, "error": str(ve), "pending_count": current_count}, status=400)
    except Exception as e:
        print(f"Error removing pending for animal_id '{animal_id}': {e}"); traceback.print_exc()
        # Try to return the current count even on error if possible
        current_count = 0
        if request.user.is_authenticated:
             current_count = PendingAppointment.objects.filter(user=user).count()
        return JsonResponse({"success": False, "error": "移除待約時發生錯誤", "pending_count": current_count}, status=500)


# --- Note Handling Views (Keep mostly as is, JS will handle refresh) ---
@require_POST
@login_required
def add_note(request):
    animal_id = request.POST.get("animal_id");
    content = request.POST.get("content", "").strip();
    note_id_from_post = request.POST.get("note_id")

    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)

    animal = get_object_or_404(Animal, id=animal_id)
    user = request.user
    note = None
    created = False

    try:
        if note_id_from_post:
             try:
                 note = Note.objects.get(id=note_id_from_post, user=user, animal=animal)
                 note.content = content
                 note.save() # Removed update_fields
                 created = False
                 print(f"Note {note.id} updated. Updated_at: {note.updated_at}")
             except Note.DoesNotExist:
                 print(f"Add/Update note failed: Note ID {note_id_from_post} provided but not found for user {user.username}, animal {animal_id}.")
                 return JsonResponse({"success": False, "error": "找不到要更新的筆記或無權限"}, status=404)
        else:
            note, created = Note.objects.update_or_create(
                user=user, animal=animal, defaults={"content": content}
            )
            print(f"Note {'created' if created else 'updated via update_or_create'}. ID: {note.id}. Updated_at: {note.updated_at}")

        message = "筆記已新增" if created else "筆記已更新"
        print(f"Note for animal {animal_id} by user {user.username}: {'Created' if created else 'Updated'}.")

        # Return note details, JS will decide if/how to refresh UI
        return JsonResponse({
            "success": True, "message": message, "note_id": note.id,
            "note_content": note.content, "animal_id": animal.id,
        })
    except (ValueError, TypeError) as e:
         print(f"Error adding/updating note (invalid ID?) for animal_id '{animal_id}': {e}")
         return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    except Exception as e:
        print(f"Error adding/updating note for animal {animal_id}: {e}"); traceback.print_exc()
        return JsonResponse({"success": False, "error": "儲存筆記時發生錯誤"}, status=500)

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
        animal_id = note_to_delete.animal_id
        deleted_count, _ = note_to_delete.delete()
        if deleted_count == 0:
             print(f"Delete note failed: Note {note_id_int} not found or already deleted (User: {user.username}).")
             return JsonResponse({"success": False, "error": "刪除失敗"})
        print(f"Note {note_id_int} deleted for animal {animal_id} by user {user.username}.")
        return JsonResponse({"success": True, "message": "筆記已刪除", "animal_id": animal_id})
    except Note.DoesNotExist:
        print(f"Delete note failed: Note {note_id} does not exist or no permission for user {user.username}.")
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve:
         print(f"Error deleting note: {ve} (Raw ID: '{note_id}')")
         return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        print(f"Error deleting note {note_id}: {e}"); traceback.print_exc()
        return JsonResponse({"success": False, "error": "刪除筆記時發生錯誤"}, status=500)

@require_POST
@login_required
def update_note(request):
    note_id = request.POST.get("note_id");
    content = request.POST.get("content", "").strip();

    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)

    user = request.user
    try:
        try: note_id_int = int(note_id)
        except (ValueError, TypeError): raise ValueError("無效的筆記 ID 格式")
        note = get_object_or_404(Note.objects.select_related('animal'), id=note_id_int, user=user)
        animal = note.animal
        note.content = content
        note.save() # Removed update_fields
        print(f"Note {note_id_int} updated (via update_note view) for animal {animal.id} by user {user.username}. Updated_at: {note.updated_at}")

        # Return note details, JS will decide if/how to refresh UI
        return JsonResponse({
            "success": True, "message": "筆記已更新", "note_id": note.id,
            "note_content": note.content, "animal_id": animal.id
        })
    except Note.DoesNotExist:
        print(f"Update note failed: Note {note_id} not found or no permission for user {user.username}.")
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve:
         print(f"Error updating note: {ve} (Raw ID: '{note_id}')")
         return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        print(f"Error updating note {note_id}: {e}"); traceback.print_exc()
        return JsonResponse({"success": False, "error": "更新筆記時發生錯誤"}, status=500)

# --- START: New AJAX View for Active Stories ---
@require_GET
def ajax_get_active_stories(request):
    print(">>> Handling AJAX Request for Active Story Reviews <<<")
    try:
        now = timezone.now()
        active_stories = StoryReview.objects.filter(
            approved=True,
            expires_at__gt=now
        ).select_related(
            'animal', 'animal__hall', 'user' # Select related fields for efficiency
        ).order_by('-approved_at') # Show newest approved first

        stories_data = []
        for story in active_stories:
            animal = story.animal
            user = story.user
            stories_data.append({
                'id': story.id,
                'animal_id': animal.id,
                'animal_name': animal.name,
                'animal_photo_url': animal.photo.url if animal.photo else None,
                'hall_name': animal.hall.name if animal.hall else '未知館別',
                'user_name': user.first_name or user.username, # Or '匿名'?
                'remaining_time': story.remaining_time_display,
            })

        return JsonResponse({'stories': stories_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_active_stories: {e} !!!"); traceback.print_exc()
        return JsonResponse({'error': '無法載入限時動態'}, status=500)
# --- END: New AJAX View for Active Stories ---


# --- START: New AJAX View for Story Detail ---
@require_GET
def ajax_get_story_detail(request, story_id):
    print(f">>> Handling AJAX Request for Story Detail (ID: {story_id}) <<<")
    try:
        story = get_object_or_404(
            StoryReview.objects.select_related('animal', 'animal__hall', 'user'),
            pk=story_id
        )

        # Double-check if it's still active (though the panel should only show active ones)
        if not story.is_active:
            print(f"    Story {story_id} is no longer active.")
            return JsonResponse({'success': False, 'error': '此限時動態已過期或未審核'}, status=404)

        animal = story.animal
        user = story.user

        # Format the approval date for display
        approved_at_display = ""
        if story.approved_at:
            try:
                # Format as needed, e.g., 'Y-m-d H:i' or just date 'Y-m-d'
                approved_at_display = format_date(timezone.localtime(story.approved_at), 'Y-m-d H:i')
            except Exception as date_err:
                 print(f"    Warning: Error formatting approved_at for story {story_id}: {date_err}")


        story_data = {
            'id': story.id,
            'animal_id': animal.id,
            'animal_name': animal.name,
            'animal_photo_url': animal.photo.url if animal.photo else None,
            'hall_name': animal.hall.name if animal.hall else '未知館別',
            'user_name': user.first_name or user.username, # Or '匿名'?
            'remaining_time': story.remaining_time_display,
            'approved_at_display': approved_at_display, # Add formatted date

            # Include all the review content fields
            'age': story.age,
            'looks': story.looks,
            'face': story.face,
            'temperament': story.temperament,
            'physique': story.physique,
            'cup': story.cup,
            'cup_size': story.cup_size,
            'skin_texture': story.skin_texture,
            'skin_color': story.skin_color,
            'music': story.music,
            'music_price': story.music_price,
            'sports': story.sports,
            'sports_price': story.sports_price,
            'scale': story.scale,
            'content': story.content,
        }

        print(f"    Returning details for story {story_id}.")
        return JsonResponse({'success': True, 'story': story_data})

    except Http404:
         print(f"    Story {story_id} not found.")
         return JsonResponse({'success': False, 'error': '找不到指定的限時動態'}, status=404)
    except Exception as e:
        print(f"!!! Error in ajax_get_story_detail for ID {story_id}: {e} !!!"); traceback.print_exc()
        return JsonResponse({'success': False, 'error': '無法載入限時動態詳情'}, status=500)
# --- END: New AJAX View for Story Detail ---


# --- START: Modified AJAX View for Weekly Schedule Images ---
@require_GET # This view only handles GET requests
def ajax_get_weekly_schedule(request):
    hall_id = request.GET.get('hall_id')
    print(f">>> Handling AJAX Request for Weekly Schedule (Hall ID: {hall_id}) <<<")

    if not hall_id:
        return JsonResponse({'success': False, 'error': '缺少館別 ID'}, status=400)

    try:
        hall_id_int = int(hall_id)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': '無效的館別 ID 格式'}, status=400)

    try:
        # Fetch ALL schedules for the hall, ordered by the 'order' field
        schedules = WeeklySchedule.objects.filter(
            hall_id=hall_id_int
        ).order_by('order').select_related('hall') # Added order_by

        if schedules.exists():
            # Extract URLs from the schedules that have an image
            schedule_urls = [s.schedule_image.url for s in schedules if s.schedule_image]
            hall_name = schedules.first().hall.name # Get hall name from the first schedule

            if schedule_urls:
                print(f"    Found {len(schedule_urls)} weekly schedule images for Hall {hall_id}.")
                return JsonResponse({
                    'success': True,
                    'schedule_urls': schedule_urls, # Return a list of URLs
                    'hall_name': hall_name
                })
            else:
                # Schedules exist but have no images? Or filter removed them.
                print(f"    Weekly schedule entries found for Hall {hall_id}, but no valid images associated.")
                return JsonResponse({
                    'success': False,
                    'schedule_urls': [],
                    'hall_name': hall_name,
                    'message': '此館別班表紀錄中未找到有效圖片' # More specific message
                })
        else:
            # No WeeklySchedule objects found for this hall
            print(f"    No weekly schedule entries found for Hall {hall_id}.")
            hall_name = Hall.objects.filter(id=hall_id_int).values_list('name', flat=True).first() or '此館別'
            return JsonResponse({
                'success': False,
                'schedule_urls': [], # Empty list
                 # Try to get hall name even if no schedules exist
                'hall_name': hall_name,
                'message': f'{hall_name}尚未上傳本週班表'
            })

    except Hall.DoesNotExist: # Should not happen if hall_id_int is valid, but good practice
         return JsonResponse({'success': False, 'error': '找不到指定的館別'}, status=404)
    except Exception as e:
        print(f"!!! Error fetching weekly schedule for Hall {hall_id}: {e} !!!"); traceback.print_exc()
        return JsonResponse({'success': False, 'error': '載入每週班表時發生伺服器錯誤'}, status=500)
# --- END: Modified AJAX View for Weekly Schedule Images ---


# --- START: New AJAX View for Hall of Fame ---
@require_GET # No login required, usually
def ajax_get_hall_of_fame(request):
    print(">>> Handling AJAX Request for Hall of Fame <<<")
    try:
        top_users = Review.objects.filter(approved=True) \
                        .values('user', 'user__username', 'user__first_name') \
                        .annotate(review_count=Count('id')) \
                        .order_by('-review_count')[:10] # Get top 10

        hall_of_fame_data = []
        for rank, user_data in enumerate(top_users, 1):
            # Prefer first_name, fallback to username
            user_display_name = user_data.get('user__first_name') or user_data.get('user__username', '未知用戶')
            if not user_display_name.strip(): # Handle empty first name/username edge case
                user_display_name = f"用戶_{user_data.get('user', 'N/A')}" # Fallback using user ID

            hall_of_fame_data.append({
                'rank': rank,
                'user_name': user_display_name,
                'review_count': user_data.get('review_count', 0)
            })

        print(f"    Returning {len(hall_of_fame_data)} users for Hall of Fame.")
        return JsonResponse({'users': hall_of_fame_data})
    except Exception as e:
        print(f"!!! Error in ajax_get_hall_of_fame: {e} !!!"); traceback.print_exc()
        return JsonResponse({'error': '無法載入紓壓名人堂'}, status=500)
# --- END: New AJAX View for Hall of Fame ---