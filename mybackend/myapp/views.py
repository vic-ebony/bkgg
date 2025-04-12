# myapp/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
# from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Prefetch, Max # Ensure Max is imported
from django.views.decorators.http import require_POST
# from django.core.paginator import Paginator
from django.template.loader import render_to_string # For rendering partials
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
                try:
                    hall_id_int = int(selected_hall_id)
                    animals_qs = animals_base_qs.filter(hall_id=hall_id_int)
                except (ValueError, TypeError):
                    # Handle invalid hall_id gracefully, maybe return all or error
                    print(f"    Warning: Invalid hall_id '{selected_hall_id}' received. Defaulting to all.")
                    animals_qs = animals_base_qs.all() # Or return error JsonResponse?
            else:
                animals_qs = animals_base_qs.all()

            animals_for_ajax = animals_qs.annotate(
                approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
            ).order_by(   # Apply custom sorting for daily schedule
                '-is_hidden_edition', # True (隱藏版) 在前
                '-is_exclusive',      # True (獨家) 在前
                '-is_hot',            # True (熱門) 在前
                '-is_newcomer',       # True (新人) 在前
                'order',              # 按自訂排序欄位
                'name'                # 最後按名字排序以確保一致性
            )

            pending_ids = set()
            notes_by_animal = {}
            if request.user.is_authenticated:
                 # Cast animal_id to string for consistency
                 pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user))
                 animal_ids_in_current_ajax = [a.id for a in animals_for_ajax]
                 # Cast animal_id to string for keys
                 notes_by_animal = {str(note.animal_id): note for note in Note.objects.filter(user=request.user, animal_id__in=animal_ids_in_current_ajax)}

            # --- START: AJAX HTML Rendering ---
            rendered_rows_html_list = []
            print(f"    Rendering partial template for {len(animals_for_ajax)} animals...")
            for animal_instance in animals_for_ajax:
                 # Prepare context for *each* animal row
                 row_context = {
                     'animal': animal_instance,
                     'user': request.user,
                     'pending_ids': pending_ids,
                     'notes_by_animal': notes_by_animal
                     # Note: animal_instance already has 'approved_review_count' from annotation
                 }
                 try:
                     # Render the partial for the current animal
                     rendered_html_for_animal = render_to_string('partials/_animal_table_rows.html', row_context, request=request)
                     rendered_rows_html_list.append(rendered_html_for_animal)
                 except Exception as render_err:
                      print(f"    !!! Error rendering partial for animal {animal_instance.id}: {render_err} !!!")
                      traceback.print_exc()
                      # Decide how to handle: skip row, add error placeholder, or fail entire request?
                      # Adding a simple placeholder for this example:
                      rendered_rows_html_list.append(f'<tr><td colspan="5">Error loading data for {animal_instance.name}</td></tr>')

            table_html = "".join(rendered_rows_html_list) # Join all rendered rows
            print(f"    AJAX Partial HTML rendered successfully (total length: {len(table_html)}).")
            # --- END: AJAX HTML Rendering ---

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
        try: context['announcement'] = Announcement.objects.filter(is_active=True).order_by('-created_at').first()
        except Exception as e: print(f"Error fetching announcement: {e}"); context['announcement'] = None
        try:
            first_animal_for_promo = Animal.objects.filter(is_active=True, photo__isnull=False).exclude(photo='').order_by('?').first()
            context['promo_photo_url'] = first_animal_for_promo.photo.url if first_animal_for_promo else None
            context['promo_animal_name'] = first_animal_for_promo.name if first_animal_for_promo else None
        except Exception as e: print(f"Error fetching promo photo: {e}"); context['promo_photo_url'] = None; context['promo_animal_name'] = None

        # Fetch User-Specific Data (Pending, Notes) and Latest Reviewed Animals
        pending_ids = set()
        notes_by_animal = {}
        pending_appointments_list = []
        my_notes_list = []
        latest_reviewed_animals_qs = Animal.objects.none() # Initialize

        if request.user.is_authenticated:
            try:
                # Fetch base querysets for pending and notes with ORDERING
                pending_appointments_qs = PendingAppointment.objects.filter(
                    user=request.user
                ).select_related('animal', 'animal__hall').order_by('-added_at') # Order pending list

                notes_qs = Note.objects.filter(
                    user=request.user
                ).select_related('animal', 'animal__hall').order_by('-updated_at') # Order notes list

                # Prepare lists (now they are already ordered from the queryset)
                pending_appointments_list = list(pending_appointments_qs)
                my_notes_list = list(notes_qs)

                # Prepare sets for quick lookups (used by template/JS)
                pending_ids = set(str(pa.animal_id) for pa in pending_appointments_list if pa.animal_id)
                notes_by_animal = {str(note.animal_id): note for note in my_notes_list if note.animal_id}

            except Exception as e:
                print(f"Error fetching pending/notes base data for user {request.user.username}: {e}")
                traceback.print_exc()

        # Fetch Latest Reviewed Animals (Visible to all users)
        try:
            # This query annotates counts correctly for *this* list
            latest_reviewed_animals_qs = Animal.objects.filter(is_active=True) \
                .annotate(
                    latest_review_time=Max('reviews__created_at', filter=Q(reviews__approved=True))
                ) \
                .filter(latest_review_time__isnull=False) \
                .annotate(
                    approved_review_count=Count('reviews', filter=Q(reviews__approved=True)) # Annotation for this list
                ) \
                .select_related('hall') \
                .order_by('-latest_review_time') \
                [:20] # Limit to 20
            print(f"    Fetched {len(latest_reviewed_animals_qs)} latest reviewed animals for full page render.")
            if latest_reviewed_animals_qs:
                first_latest_animal = latest_reviewed_animals_qs[0]
                print(f"    First latest reviewed animal: ID={first_latest_animal.id}, Name='{first_latest_animal.name}', Intro Length={len(first_latest_animal.introduction or '')}, Count (annotated)={getattr(first_latest_animal, 'approved_review_count', 'N/A')}")
            else:
                 print("    Latest reviewed animals list is empty.")

        except Exception as e:
             print(f"Error fetching latest reviewed animals for full page render: {e}")
             traceback.print_exc()
             latest_reviewed_animals_qs = Animal.objects.none()

        # ---- START: CORRECTED Review Count Fetching for Pending & My Notes Modals ----
        if request.user.is_authenticated:
             try:
                 # Get all animal IDs that appear in the Pending or My Notes lists
                 animal_ids_in_modals = set(pa.animal_id for pa in pending_appointments_list if pa.animal_id) | \
                                          set(n.animal_id for n in my_notes_list if n.animal_id)

                 counts_dict_for_modals = {}
                 if animal_ids_in_modals:
                     print(f"    Fetching review counts for {len(animal_ids_in_modals)} animals in Pending/My Notes modals.")
                     # Fetch counts specifically for these animals
                     counts_query = Animal.objects.filter(id__in=animal_ids_in_modals).annotate(
                         # Use the standard name expected by the template
                         approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
                     ).values('id', 'approved_review_count') # Fetch ID and the count

                     counts_dict_for_modals = {item['id']: item['approved_review_count'] for item in counts_query}
                     print(f"    Counts fetched: {counts_dict_for_modals}") # Debug print

                 # Now, iterate through the lists and explicitly attach the count
                 for item_list in [pending_appointments_list, my_notes_list]:
                     for obj in item_list:
                          # Check if the object has an animal and animal_id
                          if hasattr(obj, 'animal') and obj.animal and obj.animal_id:
                              # Get the count from our fetched dictionary, default to 0 if not found
                              count = counts_dict_for_modals.get(obj.animal_id, 0)
                              # Set the attribute directly on the animal object
                              obj.animal.approved_review_count = count
                              # Debug print (optional)
                              # print(f"      Attached count {count} to {obj.animal.name} (ID: {obj.animal_id}) in {'Pending' if isinstance(obj, PendingAppointment) else 'Notes'} list.")

             except Exception as e:
                  print(f"Error fetching/attaching review counts for Pending/My Notes modals for user {request.user.username}: {e}")
                  traceback.print_exc()
        # ---- END: CORRECTED Review Count Fetching ----

        # Add data to context
        context['pending_ids'] = pending_ids # Set for quick lookups
        context['notes_by_animal'] = notes_by_animal # Dict for quick lookups
        context['pending_appointments'] = pending_appointments_list # List is already ordered from the query
        context['my_notes'] = my_notes_list # List is already ordered from the query
        context['latest_reviewed_animals'] = latest_reviewed_animals_qs # List already has counts annotated

        # Handle login error message
        login_error = request.session.pop('login_error', None);
        if login_error: context['login_error'] = login_error
        context['selected_hall_id'] = 'all'

        # Render the full page
        print("    Rendering full template: index.html")
        try:
            return render(request, 'index.html', context)
        except Exception as e:
            print(f"    !!! Error rendering index.html: {e} !!!")
            traceback.print_exc()
            # Return a simple error response for full page load failure
            return render(request, 'error_page.html', {'error_message': '渲染頁面時發生內部錯誤'}, status=500) # Assumes error_page.html exists


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

# --- Review Handling View ---
@login_required
def add_review(request):
    if request.method == "POST":
        animal_id = request.POST.get("animal_id")
        animal = get_object_or_404(Animal, id=animal_id)

        face_list = request.POST.getlist("face")
        temperament_list = request.POST.getlist("temperament")
        scale_list = request.POST.getlist("scale")
        content = request.POST.get("content", "").strip()
        age_str = request.POST.get("age")
        cup_size_str = request.POST.get("cup_size","").strip().upper()

        errors = {}
        if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
        if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
        if not content: errors['content'] = "心得內容不能為空"
        age = None
        if age_str:
            try: age = int(age_str); assert age > 0
            except (ValueError, AssertionError): errors['age'] = "年紀必須是正整數"
        # Allowing empty cup_size, but if provided, must be alpha
        if cup_size_str and not cup_size_str.isalpha():
            errors['cup_size'] = "罩杯大小請填寫英文字母"

        if errors:
            print(f"Review submission failed validation for animal {animal_id}: {errors}")
            return JsonResponse({"success": False, "error": "輸入無效", "errors": errors}, status=400)

        try:
            new_review = Review.objects.create(
                animal=animal, user=request.user, age=age,
                looks=request.POST.get("looks") or None,
                face=','.join(face_list),
                temperament=','.join(temperament_list),
                physique=request.POST.get("physique") or None,
                cup=request.POST.get("cup") or None,
                cup_size=cup_size_str or None, # Save empty string if not provided
                skin_texture=request.POST.get("skin_texture") or None,
                skin_color=request.POST.get("skin_color") or None,
                music=request.POST.get("music") or None,
                music_price=request.POST.get("music_price") or None,
                sports=request.POST.get("sports") or None,
                sports_price=request.POST.get("sports_price") or None,
                scale=','.join(scale_list),
                content=content,
                approved=False # Default to not approved
            )
            print(f"Review {new_review.id} created for animal {animal_id} by user {request.user.username}.")
            return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
        except Exception as e:
             print(f"Error creating review for animal {animal_id}: {e}")
             traceback.print_exc()
             return JsonResponse({"success": False, "error": "儲存心得時發生內部錯誤"}, status=500)

    elif request.method == "GET":
        animal_id = request.GET.get("animal_id")
        animal = get_object_or_404(Animal, id=animal_id)
        print(f"Fetching reviews for animal {animal_id} (User: {request.user.username})")

        reviews_qs = Review.objects.filter(animal=animal, approved=True).select_related('user').order_by("-created_at")

        user_ids = list(reviews_qs.values_list('user_id', flat=True).distinct())
        user_review_counts = {}
        if user_ids:
            try:
                 # Count only *approved* reviews for the total count display
                 counts_query = Review.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(totalCount=Count('id'))
                 user_review_counts = {item['user_id']: item['totalCount'] for item in counts_query}
            except Exception as count_err:
                 print(f"Error fetching user review counts: {count_err}")

        data = []
        for r in reviews_qs:
            user_display_name = "匿名"
            if hasattr(r, 'user') and r.user:
                # Use first_name if available, otherwise username
                user_display_name = r.user.first_name or r.user.username

            formatted_date = ""
            if r.created_at:
                try:
                    # Using only date for simplicity, adjust format as needed
                    formatted_date = timezone.localtime(r.created_at).strftime("%Y-%m-%d")
                except Exception as date_err:
                    print(f"Error formatting date {r.created_at} for review {r.id}: {date_err}")

            data.append({
                "id": r.id,
                "user": user_display_name,
                "totalCount": user_review_counts.get(r.user_id, 0),
                "age": r.age, "looks": r.looks, "face": r.face, "temperament": r.temperament,
                "physique": r.physique, "cup": r.cup, "cup_size": r.cup_size,
                "skin_texture": r.skin_texture, "skin_color": r.skin_color,
                "music": r.music, "music_price": r.music_price,
                "sports": r.sports, "sports_price": r.sports_price,
                "scale": r.scale, "content": r.content,
                "created_at": formatted_date
            })
        print(f"Returning {len(data)} reviews for animal {animal_id}.")
        return JsonResponse({"reviews": data})

    return JsonResponse({"success": False, "error": "請求方法不支援"}, status=405)


# --- Pending Appointment Handling Views ---
@require_POST
@login_required
def add_pending_appointment(request):
    animal_id = request.POST.get("animal_id")
    animal = get_object_or_404(Animal, id=animal_id)
    user = request.user
    try:
        obj, created = PendingAppointment.objects.get_or_create(user=user, animal=animal)
        pending_count = PendingAppointment.objects.filter(user=user).count()
        message = f"{animal.name} 已加入待約清單" if created else f"{animal.name} 已在待約清單中"
        print(f"Pending action for animal {animal_id} by user {user.username}: {'Added' if created else 'Already Exists'}. Count: {pending_count}")

        # ---- Render row HTML ----
        # Prepare data needed by the partial template
        current_pending_ids = {str(animal.id)} # It's now pending
        note_instance = Note.objects.filter(user=user, animal=animal).first()
        current_notes_by_animal = {str(animal.id): note_instance} if note_instance else {}

        # Ensure review count is attached for the partial render
        # Fetch it directly here for simplicity in this isolated action
        try:
            animal.approved_review_count = Review.objects.filter(animal=animal, approved=True).count()
        except Exception as count_err:
            print(f"    Warning: Error fetching review count for partial render in add_pending: {count_err}")
            animal.approved_review_count = 0 # Default to 0 on error

        row_context = {
            'animal': animal,
            'user': user,
            'pending_ids': current_pending_ids,
            'notes_by_animal': current_notes_by_animal
            # animal object now has .approved_review_count attached
        }
        rendered_row_html = render_to_string('partials/_animal_table_rows.html', row_context, request=request)
        # --------

        return JsonResponse({
            "success": True, "message": message,
            "pending_count": pending_count,
            "rendered_row_html": rendered_row_html # Send back the HTML for the row(s)
        })
    except (ValueError, TypeError) as e:
        # Catch potential errors if animal_id is not a valid integer format
        print(f"Error adding pending (invalid ID format?) for animal_id '{animal_id}': {e}")
        return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    except Exception as e:
        print(f"Error adding pending for animal {animal_id}: {e}");
        traceback.print_exc()
        return JsonResponse({"success": False, "error": "加入待約時發生錯誤"}, status=500)

@require_POST
@login_required
def remove_pending(request):
    animal_id = request.POST.get("animal_id")
    user = request.user
    try:
        # Validate animal_id format first
        try:
            animal_id_int = int(animal_id)
        except (ValueError, TypeError):
            raise ValueError("無效的動物 ID 格式") # Raise specific error for catching

        # Attempt to delete
        deleted_count, _ = PendingAppointment.objects.filter(user=user, animal_id=animal_id_int).delete()

        if deleted_count == 0:
            # Check if the animal itself exists before saying it wasn't pending
            if not Animal.objects.filter(id=animal_id_int).exists():
                print(f"Remove pending failed: Animal {animal_id_int} not found (User: {user.username}).")
                return JsonResponse({"success": False, "error": "找不到該動物"}, status=404)
            else:
                # Animal exists, but wasn't in pending list for this user
                print(f"Remove pending failed: Animal {animal_id_int} was not pending for user {user.username}.")
                return JsonResponse({"success": False, "error": "該待約項目不存在"}) # Or maybe just success=True but indicate 0 removed? Changed to False for clarity.

        # If deletion was successful (deleted_count > 0)
        pending_count = PendingAppointment.objects.filter(user=user).count()
        # Get animal name for message (handle case where animal might be deleted concurrently? Unlikely but safe)
        animal_name = Animal.objects.filter(id=animal_id_int).values_list('name', flat=True).first() or "該美容師"
        print(f"Pending removed for animal {animal_id_int} by user {user.username}. Count: {pending_count}")

        return JsonResponse({
            "success": True, "message": f"{animal_name} 待約項目已移除",
            "pending_count": pending_count
        })
    except ValueError as ve:
         # Catch the specific ValueError raised for format issues
         print(f"Error removing pending: {ve} (Raw ID: '{animal_id}')")
         return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        print(f"Error removing pending for animal_id '{animal_id}': {e}");
        traceback.print_exc()
        return JsonResponse({"success": False, "error": "移除待約時發生錯誤"}, status=500)


# --- Note Handling Views ---
@require_POST
@login_required
def add_note(request):
    animal_id = request.POST.get("animal_id");
    content = request.POST.get("content", "").strip();
    note_id_from_post = request.POST.get("note_id") # Check if note_id is sent for update case

    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"}, status=400)
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)

    animal = get_object_or_404(Animal, id=animal_id)
    user = request.user
    note = None
    created = False

    try:
        # If note_id was provided in the form (hidden input), treat as update via get()
        if note_id_from_post:
             try:
                 note = Note.objects.get(id=note_id_from_post, user=user, animal=animal)
                 note.content = content
                 # --- MODIFIED: Remove update_fields to trigger auto_now ---
                 note.save() # No update_fields, so updated_at will be set
                 # --- End MODIFIED ---
                 created = False # It was an update
                 print(f"Note {note.id} updated. Updated_at: {note.updated_at}") # <-- Debug print
             except Note.DoesNotExist:
                 # If ID provided but not found/valid, return error
                 print(f"Add/Update note failed: Note ID {note_id_from_post} provided but not found for user {user.username}, animal {animal_id}.")
                 return JsonResponse({"success": False, "error": "找不到要更新的筆記或無權限"}, status=404)
        else:
            # If no note_id, use update_or_create based on user/animal pair
            note, created = Note.objects.update_or_create(
                user=user,
                animal=animal,
                defaults={"content": content}
            )
            # update_or_create automatically handles auto_now, no explicit save needed here
            print(f"Note {'created' if created else 'updated via update_or_create'}. ID: {note.id}. Updated_at: {note.updated_at}") # <-- Debug print

        message = "筆記已新增" if created else "筆記已更新"
        print(f"Note for animal {animal_id} by user {user.username}: {'Created' if created else 'Updated'}.")

        # ---- Render row HTML ----
        # We need the state *after* the add/update for the partial render
        is_pending = PendingAppointment.objects.filter(user=user, animal=animal).exists()
        current_pending_ids = {str(animal.id)} if is_pending else set()
        current_notes_by_animal = {str(animal.id): note} # The note we just saved

        # Ensure review count is attached
        try:
            animal.approved_review_count = Review.objects.filter(animal=animal, approved=True).count()
        except Exception:
            animal.approved_review_count = 0

        row_context = {
            'animal': animal,
            'user': user,
            'pending_ids': current_pending_ids,
            'notes_by_animal': current_notes_by_animal
        }
        rendered_row_html = render_to_string('partials/_animal_table_rows.html', row_context, request=request)
        # --------

        return JsonResponse({
            "success": True, "message": message,
            "note_id": note.id, "note_content": note.content, # Return the saved note details
            "animal_id": animal.id,
            "rendered_row_html": rendered_row_html # Send back the HTML for the row(s)
        })
    except (ValueError, TypeError) as e:
         # Catch potential errors if animal_id is not valid
         print(f"Error adding/updating note (invalid ID?) for animal_id '{animal_id}': {e}")
         return JsonResponse({"success": False, "error": "無效的動物 ID"}, status=400)
    except Exception as e:
        print(f"Error adding/updating note for animal {animal_id}: {e}");
        traceback.print_exc()
        return JsonResponse({"success": False, "error": "儲存筆記時發生錯誤"}, status=500)


@require_POST
@login_required
def delete_note(request):
    note_id = request.POST.get("note_id")
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    user = request.user
    try:
        # Validate note_id format
        try:
            note_id_int = int(note_id)
        except (ValueError, TypeError):
            raise ValueError("無效的筆記 ID 格式")

        # Use get_object_or_404 to handle DoesNotExist and ensure ownership
        note_to_delete = get_object_or_404(Note, id=note_id_int, user=user)
        animal_id = note_to_delete.animal_id # Get animal ID *before* deleting

        # Perform deletion
        deleted_count, _ = note_to_delete.delete()

        # deleted_count should be 1 because get_object_or_404 succeeded
        if deleted_count == 0:
             # This case should be rare due to get_object_or_404
             print(f"Delete note failed: Note {note_id_int} not found or already deleted (User: {user.username}).")
             return JsonResponse({"success": False, "error": "刪除失敗"})

        print(f"Note {note_id_int} deleted for animal {animal_id} by user {user.username}.")
        # Return success and the animal_id so the frontend knows which row's note info to clear
        return JsonResponse({
            "success": True, "message": "筆記已刪除",
            "animal_id": animal_id # Return the associated animal ID
        })
    except Note.DoesNotExist:
        # This case is technically handled by get_object_or_404, but good practice
        print(f"Delete note failed: Note {note_id} does not exist or no permission for user {user.username}.")
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve:
         # Catch the specific ValueError for format issues
         print(f"Error deleting note: {ve} (Raw ID: '{note_id}')")
         return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        print(f"Error deleting note {note_id}: {e}");
        traceback.print_exc()
        return JsonResponse({"success": False, "error": "刪除筆記時發生錯誤"}, status=500)


@require_POST
@login_required
def update_note(request):
    # This view specifically handles updates via the update_note URL,
    # expecting note_id and content.
    note_id = request.POST.get("note_id");
    content = request.POST.get("content", "").strip();

    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"}, status=400)
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"}, status=400)

    user = request.user
    try:
        # Validate note_id format
        try:
            note_id_int = int(note_id)
        except (ValueError, TypeError):
            raise ValueError("無效的筆記 ID 格式")

        # Use get_object_or_404, ensuring the note exists and belongs to the user
        # Use select_related for efficiency when accessing animal later for rendering
        note = get_object_or_404(Note.objects.select_related('animal'), id=note_id_int, user=user)
        animal = note.animal # Get the related animal

        # Update the content
        note.content = content
        # --- MODIFIED: Remove update_fields to trigger auto_now ---
        note.save() # No update_fields, so updated_at will be set
        # --- End MODIFIED ---
        print(f"Note {note_id_int} updated (via update_note view) for animal {animal.id} by user {user.username}. Updated_at: {note.updated_at}") # <-- Debug print

        # ---- Render row HTML ----
        # Need current state for partial render
        is_pending = PendingAppointment.objects.filter(user=user, animal=animal).exists()
        current_pending_ids = {str(animal.id)} if is_pending else set()
        current_notes_by_animal = {str(animal.id): note} # The updated note

        # Ensure review count
        try:
            animal.approved_review_count = Review.objects.filter(animal=animal, approved=True).count()
        except Exception:
            animal.approved_review_count = 0

        row_context = {
            'animal': animal,
            'user': user,
            'pending_ids': current_pending_ids,
            'notes_by_animal': current_notes_by_animal
        }
        rendered_row_html = render_to_string('partials/_animal_table_rows.html', row_context, request=request)
        # --------

        return JsonResponse({
            "success": True, "message": "筆記已更新",
            "note_id": note.id, "note_content": note.content, # Return updated details
            "animal_id": animal.id,
            "rendered_row_html": rendered_row_html # Return updated row HTML
        })
    except Note.DoesNotExist:
        print(f"Update note failed: Note {note_id} not found or no permission for user {user.username}.")
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"}, status=404)
    except ValueError as ve:
         # Catch specific format error
         print(f"Error updating note: {ve} (Raw ID: '{note_id}')")
         return JsonResponse({"success": False, "error": str(ve)}, status=400)
    except Exception as e:
        print(f"Error updating note {note_id}: {e}");
        traceback.print_exc()
        return JsonResponse({"success": False, "error": "更新筆記時發生錯誤"}, status=500)

# --- Optional my_notes specific views ---
# @login_required
# def my_notes_json(request): ...
# @login_required
# def my_notes(request): ...