# myapp/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
# from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Prefetch
from django.views.decorators.http import require_POST
# from django.core.paginator import Paginator
from django.template.loader import render_to_string # <-- Added for rendering partials
# import re
# import pytesseract
# from PIL import Image
from .models import Animal, Hall, Review, PendingAppointment, Note, Announcement
import traceback

# --- Tesseract Config (Optional) ---
# try:
#     pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
#     tessdata_dir_config = r'--tessdata-dir "C:\\Program Files\\Tesseract-OCR\\tessdata"'
#     pytesseract.get_tesseract_version()
# except Exception as e:
#     print(f"Warning: Tesseract not configured or found correctly: {e}")

# --- Helper Functions (Optional) ---
# def parse_schedule_line(line): ...
# def format_price(value): ...

# --- Home View (Entry Point) ---
def home(request):
    is_ajax_request = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    is_daily_schedule_ajax = is_ajax_request and request.GET.get('ajax') == '1'

    print("-" * 20)
    print(f"Request Path: {request.path}")
    print(f"Request GET Params: {request.GET}")
    print(f"Is AJAX Header Present: {is_ajax_request}")
    print(f"Is 'ajax=1' Param Present: {'ajax' in request.GET and request.GET.get('ajax') == '1'}")
    print(f"Handling as Daily Schedule AJAX: {is_daily_schedule_ajax}")

    if is_daily_schedule_ajax:
        # --- AJAX Handling for Daily Schedule ---
        print(">>> Handling as Daily Schedule AJAX Request <<<")
        hall_id = request.GET.get('hall_id')
        selected_hall_id = hall_id or 'all'
        print(f"    Selected Hall ID: {selected_hall_id}")
        try:
            animals_base_qs = Animal.objects.filter(is_active=True).select_related('hall')
            if selected_hall_id != "all":
                try: hall_id_int = int(selected_hall_id); animals_qs = animals_base_qs.filter(hall_id=hall_id_int)
                except (ValueError, TypeError): animals_qs = animals_base_qs.all()
            else:
                animals_qs = animals_base_qs.all()

            animals_for_ajax = animals_qs.annotate(
                approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
            ).order_by(*Animal._meta.ordering)

            pending_ids = set()
            notes_by_animal = {}
            if request.user.is_authenticated:
                 pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user))
                 # Fetch notes only for animals being displayed in this AJAX request
                 animal_ids_in_current_ajax = [a.id for a in animals_for_ajax]
                 notes_by_animal = {str(note.animal_id): note for note in Note.objects.filter(user=request.user, animal_id__in=animal_ids_in_current_ajax)}

            ajax_context = {
                'animals': animals_for_ajax,
                'user': request.user,
                'pending_ids': pending_ids,
                'notes_by_animal': notes_by_animal
            }
            print(f"    Rendering partial template: partials/_daily_schedule_table_content.html")
            table_html = render_to_string('partials/_daily_schedule_table_content.html', ajax_context, request=request)
            print(f"    Partial HTML rendered successfully (length: {len(table_html)}).")

            first_animal_data = {}
            try:
                if animals_for_ajax:
                     first_animal = animals_for_ajax[0]
                     first_animal_data = {
                         'photo_url': first_animal.photo.url if first_animal.photo else '',
                         'name': first_animal.name or '',
                         'introduction': first_animal.introduction or ''
                     }
            except Exception as e:
                print(f"    Warning: Error getting first animal data for AJAX response: {e}")

            print(f"    Returning JSON including table_html and first_animal data.")
            return JsonResponse({'table_html': table_html, 'first_animal': first_animal_data})
        except Exception as e:
            print(f"    !!! Error during AJAX handling: {e} !!!")
            traceback.print_exc()
            return JsonResponse({'error': f'伺服器處理班表請求時發生錯誤: {e}'}, status=500)
    else:
        # --- Full Page Rendering ---
        print(">>> Handling as Full Page Request (Rendering index.html) <<<")
        halls = Hall.objects.all().order_by('order', 'name')
        context = {'halls': halls, 'user': request.user}

        # Fetch Announcement and Promo
        try: context['announcement'] = Announcement.objects.filter(is_active=True).first()
        except Exception as e: print(f"Error fetching announcement: {e}"); context['announcement'] = None
        try:
            first_animal_for_promo = Animal.objects.filter(is_active=True, photo__isnull=False).exclude(photo='').order_by('?').first()
            context['promo_photo_url'] = first_animal_for_promo.photo.url if first_animal_for_promo else None
            context['promo_animal_name'] = first_animal_for_promo.name if first_animal_for_promo else None
        except Exception as e: print(f"Error fetching promo photo: {e}"); context['promo_photo_url'] = None; context['promo_animal_name'] = None

        # Fetch User-Specific Data (Pending, Notes, Latest Reviews)
        pending_ids = set(); notes_by_animal = {}; pending_appointments_list = []; my_notes_list = []; latest_reviews_qs = Review.objects.none()
        if request.user.is_authenticated:
            try:
                # Fetch related data efficiently
                pending_appointments_qs = PendingAppointment.objects.filter(user=request.user).select_related('animal', 'animal__hall')
                notes_qs = Note.objects.filter(user=request.user).select_related('animal', 'animal__hall')
                latest_reviews_qs = Review.objects.filter(approved=True).select_related('animal', 'animal__hall', 'user').order_by("-created_at")[:15]

                # Prepare data structures for the template
                pending_ids = set(str(pa.animal_id) for pa in pending_appointments_qs if pa.animal_id)
                notes_by_animal = {str(note.animal_id): note for note in notes_qs if note.animal_id}
                pending_appointments_list = list(pending_appointments_qs)
                my_notes_list = list(notes_qs)

                # Optimize review counts for animals displayed in modals
                animal_ids_in_modals = set(pa.animal_id for pa in pending_appointments_list if pa.animal_id) | \
                                       set(n.animal_id for n in my_notes_list if n.animal_id) | \
                                       set(r.animal_id for r in latest_reviews_qs if r.animal_id)
                counts_dict = {}
                if animal_ids_in_modals:
                     counts_for_modals = Animal.objects.filter(id__in=animal_ids_in_modals).annotate(
                         modal_review_count=Count('reviews', filter=Q(reviews__approved=True))
                     ).values('id', 'modal_review_count')
                     counts_dict = {item['id']: item['modal_review_count'] for item in counts_for_modals}

                     # Add count to objects in lists
                     for item_list in [pending_appointments_list, my_notes_list]:
                         for obj in item_list:
                              if hasattr(obj, 'animal') and obj.animal:
                                   obj.animal.approved_review_count = counts_dict.get(obj.animal_id, 0)
                     for review in latest_reviews_qs:
                           if hasattr(review, 'animal') and review.animal:
                                review.animal.approved_review_count = counts_dict.get(review.animal_id, 0)
            except Exception as e:
                print(f"Error fetching user-specific data: {e}")
                traceback.print_exc()

        # Add data to context
        context['pending_ids'] = pending_ids
        context['notes_by_animal'] = notes_by_animal
        context['pending_appointments'] = pending_appointments_list
        context['my_notes'] = my_notes_list
        context['latest_reviews'] = latest_reviews_qs

        # Handle login error message
        login_error = request.session.pop('login_error', None);
        if login_error: context['login_error'] = login_error
        context['selected_hall_id'] = 'all' # For initial state if needed

        # Render the full page
        print("    Rendering full template: index.html")
        try:
            return render(request, 'index.html', context)
        except Exception as e:
            print(f"    !!! Error rendering index.html: {e} !!!")
            traceback.print_exc()
            # Consider returning a proper error page instead of JSON for a full page request
            return render(request, 'error_page.html', {'error_message': '渲染頁面時發生內部錯誤'}, status=500)

# --- Image Upload View (Optional) ---
# @login_required
# def upload_schedule_image_view(request):
#    # ... (Implementation if needed)
#    pass

# --- User Authentication Views ---
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
            return redirect('home')
        else:
            request.session['login_error'] = '帳號或密碼錯誤'
            return redirect('home')
    # Redirect GET requests back to home
    return redirect('home')

@require_POST # Ensure only POST method
def user_logout(request):
    logout(request)
    # Optional: add success message
    # messages.success(request, "您已成功登出。")
    return redirect('home')

# --- Review Handling View ---
@login_required # Ensure user is logged in
def add_review(request):
    if request.method == "POST":
        animal_id = request.POST.get("animal_id")
        animal = get_object_or_404(Animal, id=animal_id) # Use get_object_or_404 for cleaner error handling

        # Collect form data
        face_list = request.POST.getlist("face")
        temperament_list = request.POST.getlist("temperament")
        scale_list = request.POST.getlist("scale")
        content = request.POST.get("content", "").strip()
        age_str = request.POST.get("age")
        cup_size_str = request.POST.get("cup_size","").strip().upper() # Clean and uppercase

        # Backend validation
        errors = {}
        if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
        if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
        if not content: errors['content'] = "心得內容不能為空"
        age = None
        if age_str:
            try: age = int(age_str); assert age > 0
            except (ValueError, AssertionError): errors['age'] = "年紀必須是正整數"
        if cup_size_str and not cup_size_str.isalpha(): # Basic check for letters
            errors['cup_size'] = "罩杯大小請填寫英文字母"

        # Return errors if validation fails
        if errors:
            return JsonResponse({"success": False, "error": "輸入無效", "errors": errors}, status=400)

        # Create the review object
        try:
            Review.objects.create(
                animal=animal, user=request.user, age=age,
                looks=request.POST.get("looks") or None, # Ensure empty strings become None
                face=','.join(face_list),
                temperament=','.join(temperament_list),
                physique=request.POST.get("physique") or None,
                cup=request.POST.get("cup") or None,
                cup_size=cup_size_str or None, # Use cleaned cup size
                skin_texture=request.POST.get("skin_texture") or None,
                skin_color=request.POST.get("skin_color") or None,
                music=request.POST.get("music") or None,
                music_price=request.POST.get("music_price") or None, # Allow empty
                sports=request.POST.get("sports") or None,
                sports_price=request.POST.get("sports_price") or None, # Allow empty
                scale=','.join(scale_list),
                content=content,
                approved=False # Default to not approved
            )
            # Note: Review count display update happens via JS or full page refresh
            return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
        except Exception as e:
             print(f"Error creating review: {e}")
             traceback.print_exc() # Log detailed error
             return JsonResponse({"success": False, "error": "儲存心得時發生內部錯誤"}, status=500)

    elif request.method == "GET":
        # Handle GET request to fetch existing reviews for an animal
        animal_id = request.GET.get("animal_id")
        animal = get_object_or_404(Animal, id=animal_id)

        reviews_qs = Review.objects.filter(animal=animal, approved=True).select_related('user').order_by("-created_at")

        # Optimize fetching total review counts for users
        user_ids = list(reviews_qs.values_list('user_id', flat=True).distinct())
        user_review_counts = {}
        if user_ids:
            counts_query = Review.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(totalCount=Count('id'))
            user_review_counts = {item['user_id']: item['totalCount'] for item in counts_query}

        # Prepare data for JSON response
        data = []
        for r in reviews_qs:
            user_display_name = "匿名" # Default user display name
            if hasattr(r, 'user') and r.user:
                user_display_name = r.user.first_name or r.user.username # Use first name or username

            # Format creation date
            formatted_date = ""
            if r.created_at:
                try:
                    # Convert to local timezone and format
                    formatted_date = timezone.localtime(r.created_at).strftime("%Y-%m-%d")
                except Exception as date_err:
                    print(f"Error formatting date {r.created_at}: {date_err}")

            # Append review data to the list
            data.append({
                "user": user_display_name,
                "totalCount": user_review_counts.get(r.user_id, 0), # Get pre-calculated count
                "age": r.age, "looks": r.looks, "face": r.face, "temperament": r.temperament,
                "physique": r.physique, "cup": r.cup, "cup_size": r.cup_size,
                "skin_texture": r.skin_texture, "skin_color": r.skin_color,
                "music": r.music, "music_price": r.music_price,
                "sports": r.sports, "sports_price": r.sports_price,
                "scale": r.scale, "content": r.content,
                "created_at": formatted_date # Use formatted date
            })
        return JsonResponse({"reviews": data})

    # Return error for unsupported methods (like PUT, DELETE)
    return JsonResponse({"success": False, "error": "請求方法不支援"}, status=405)


# --- Pending Appointment Handling Views ---
@require_POST # Ensure only POST method
@login_required # Ensure user is logged in
def add_pending_appointment(request):
    animal_id = request.POST.get("animal_id")
    animal = get_object_or_404(Animal, id=animal_id) # Find animal or return 404
    user = request.user
    try:
        # Add or get the pending appointment
        obj, created = PendingAppointment.objects.get_or_create(user=user, animal=animal)

        # Get current pending count for the user
        pending_count = PendingAppointment.objects.filter(user=user).count()

        # Set appropriate success message
        message = f"{animal.name} 已加入待約清單" if created else f"{animal.name} 已在待約清單中"

        # ---- Render row HTML for frontend update ----
        # Determine current state needed for rendering the row correctly
        current_pending_ids = {str(animal.id)} # It's now pending
        note_instance = Note.objects.filter(user=user, animal=animal).first()
        current_notes_by_animal = {str(animal.id): note_instance} if note_instance else {}

        # Ensure review count is available for the template context
        if not hasattr(animal, 'approved_review_count'): # Check if annotation was already done
            animal.approved_review_count = Review.objects.filter(animal=animal, approved=True).count()

        row_context = {
            'animal': animal,
            'user': user,
            'pending_ids': current_pending_ids, # Pass current state
            'notes_by_animal': current_notes_by_animal
        }
        # Render the single row partial template
        rendered_row_html = render_to_string('partials/_animal_table_rows.html', row_context, request=request)
        # --------

        # Return JSON response including the rendered HTML
        return JsonResponse({
            "success": True,
            "message": message,
            "pending_count": pending_count,
            "rendered_row_html": rendered_row_html # Include HTML for JS
        })
    except (ValueError, TypeError):
        # This path is less likely due to get_object_or_404, but keep for safety
        return JsonResponse({"success": False, "error": "無效的動物 ID"})
    except Exception as e:
        print(f"Error adding pending appointment: {e}");
        traceback.print_exc() # Log detailed error
        return JsonResponse({"success": False, "error": "加入待約時發生錯誤"}, status=500)

@require_POST # Ensure only POST method
@login_required # Ensure user is logged in
def remove_pending(request):
    animal_id = request.POST.get("animal_id")
    # We don't use get_object_or_404 here because we want to handle
    # the case where the animal exists but wasn't pending.
    user = request.user
    try:
        # Attempt to delete the pending appointment
        deleted_count, _ = PendingAppointment.objects.filter(user=user, animal_id=animal_id).delete()

        # Check if anything was actually deleted
        if deleted_count == 0:
            # Check if the animal ID itself is valid
            if not Animal.objects.filter(id=animal_id).exists():
                return JsonResponse({"success": False, "error": "找不到該動物"})
            else:
                # Animal exists, but wasn't in the pending list for this user
                return JsonResponse({"success": False, "error": "該待約項目不存在"})

        # Deletion successful, get the new count
        pending_count = PendingAppointment.objects.filter(user=user).count()

        # Get animal name for a more informative message (optional)
        animal_name = Animal.objects.filter(id=animal_id).values_list('name', flat=True).first() or "該美容師"

        # Return success response
        return JsonResponse({
            "success": True,
            "message": f"{animal_name} 待約項目已移除",
            "pending_count": pending_count
        })
    except (ValueError, TypeError):
        # Handle invalid animal_id format
        return JsonResponse({"success": False, "error": "無效的動物 ID"})
    except Exception as e:
        print(f"Error removing pending appointment: {e}");
        traceback.print_exc() # Log detailed error
        return JsonResponse({"success": False, "error": "移除待約時發生錯誤"}, status=500)


# --- Note Handling Views ---
@require_POST # Ensure only POST method
@login_required # Ensure user is logged in
def add_note(request):
    # This view handles both adding a new note and updating an existing one
    animal_id = request.POST.get("animal_id");
    content = request.POST.get("content", "").strip();
    note_id = request.POST.get("note_id") # May be empty if adding new

    # Basic validation
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"})
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"})

    animal = get_object_or_404(Animal, id=animal_id) # Ensure animal exists
    user = request.user
    note = None
    created = False # Flag to indicate if a new note was created

    try:
        if note_id:
            # If note_id is provided, try to get and update the specific note
            try:
                note = Note.objects.get(id=note_id, user=user, animal=animal)
                note.content = content
                note.save(update_fields=['content']) # Efficiently update only content
                created = False # It was an update
            except Note.DoesNotExist:
                # If the note_id is invalid or doesn't belong to the user/animal
                return JsonResponse({"success": False, "error": "找不到要更新的筆記或無權限"}, status=404)
        else:
            # If no note_id, use update_or_create to add or update based on user/animal
            note, created = Note.objects.update_or_create(
                user=user,
                animal=animal,
                defaults={"content": content} # Set content whether creating or updating
            )

        # Determine success message based on 'created' flag
        message = "筆記已新增" if created else "筆記已更新"

        # ---- Render row HTML for frontend update ----
        # Determine current pending status for context
        is_pending = PendingAppointment.objects.filter(user=user, animal=animal).exists()
        current_pending_ids = {str(animal.id)} if is_pending else set()
        # We have the note object, use it directly
        current_notes_by_animal = {str(animal.id): note}

        # Ensure review count is available
        if not hasattr(animal, 'approved_review_count'):
            animal.approved_review_count = Review.objects.filter(animal=animal, approved=True).count()

        row_context = {
            'animal': animal,
            'user': user,
            'pending_ids': current_pending_ids,
            'notes_by_animal': current_notes_by_animal
        }
        # Render the single row partial template
        rendered_row_html = render_to_string('partials/_animal_table_rows.html', row_context, request=request)
        # --------

        # Return success response including note details and rendered HTML
        return JsonResponse({
            "success": True,
            "message": message,
            "note_id": note.id, # Return the note ID (new or existing)
            "note_content": note.content, # Return the saved content
            "rendered_row_html": rendered_row_html # Include HTML for JS
        })
    except (ValueError, TypeError):
        # Handle potential ID format issues (less likely with get_object_or_404)
        return JsonResponse({"success": False, "error": "無效的動物或筆記 ID"})
    except Exception as e:
        print(f"Error adding/updating note: {e}");
        traceback.print_exc() # Log detailed error
        return JsonResponse({"success": False, "error": "儲存筆記時發生錯誤"}, status=500)


@require_POST # Ensure only POST method
@login_required # Ensure user is logged in
def delete_note(request):
    note_id = request.POST.get("note_id")
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"})
    user = request.user
    try:
        # Find the note ensuring it belongs to the current user
        note_to_delete = get_object_or_404(Note, id=note_id, user=user)
        animal_id = note_to_delete.animal_id # Get animal_id BEFORE deleting

        # Delete the note
        deleted_count, _ = note_to_delete.delete()

        # Check deletion count (should be 1 if get_object_or_404 worked)
        if deleted_count == 0:
             # This state should be rare if get_object_or_404 succeeded
             return JsonResponse({"success": False, "error": "刪除失敗"})

        # Return success response, including animal_id for JS targeting
        return JsonResponse({
            "success": True,
            "message": "筆記已刪除",
            "animal_id": animal_id # Crucial for JS to know which rows to update
        })
    except Note.DoesNotExist:
        # Handled by get_object_or_404, but provides specific error message
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"})
    except (ValueError, TypeError):
        # Handle invalid note_id format
        return JsonResponse({"success": False, "error": "無效的筆記 ID"})
    except Exception as e:
        print(f"Error deleting note: {e}");
        traceback.print_exc() # Log detailed error
        return JsonResponse({"success": False, "error": "刪除筆記時發生錯誤"}, status=500)


@require_POST # Ensure only POST method
@login_required # Ensure user is logged in
def update_note(request):
    # This view might be redundant if add_note covers all update cases.
    # Kept here in case the URL structure relies on it.
    note_id = request.POST.get("note_id");
    content = request.POST.get("content", "").strip();

    # Validation
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"})
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"})

    user = request.user
    try:
        # Get the specific note belonging to the user
        note = Note.objects.get(id=note_id, user=user)
        animal = note.animal # Get the related animal for context

        # Update content and save efficiently
        note.content = content
        note.save(update_fields=['content'])

        # ---- Render row HTML for frontend update ----
        # Determine current state for rendering
        is_pending = PendingAppointment.objects.filter(user=user, animal=animal).exists()
        current_pending_ids = {str(animal.id)} if is_pending else set()
        current_notes_by_animal = {str(animal.id): note}

        # Ensure review count is available
        if not hasattr(animal, 'approved_review_count'):
            animal.approved_review_count = Review.objects.filter(animal=animal, approved=True).count()

        row_context = {
            'animal': animal,
            'user': user,
            'pending_ids': current_pending_ids,
            'notes_by_animal': current_notes_by_animal
        }
        # Render the single row partial template
        rendered_row_html = render_to_string('partials/_animal_table_rows.html', row_context, request=request)
        # --------

        # Return success response
        return JsonResponse({
            "success": True,
            "message": "筆記已更新",
            "note_id": note.id,
            "note_content": note.content,
            "rendered_row_html": rendered_row_html # Include HTML for JS
        })
    except Note.DoesNotExist:
        # Handle case where note doesn't exist or doesn't belong to user
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"})
    except (ValueError, TypeError):
        # Handle invalid note_id format
        return JsonResponse({"success": False, "error": "無效的筆記 ID"})
    except Exception as e:
        print(f"Error updating note: {e}");
        traceback.print_exc() # Log detailed error
        return JsonResponse({"success": False, "error": "更新筆記時發生錯誤"}, status=500)

# --- Optional my_notes specific views ---
# @login_required
# def my_notes_json(request): ...
# @login_required
# def my_notes(request): ...