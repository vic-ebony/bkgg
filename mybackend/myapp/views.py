# myapp/views.py
from django.shortcuts import render, redirect
from django.utils import timezone
# from django.contrib import messages # 如果需要圖片上傳功能的消息提示，取消註釋
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Prefetch # 確保 Prefetch 已導入
from django.views.decorators.http import require_POST
# from django.core.paginator import Paginator # 如果需要 my_notes 分頁功能，取消註釋
from django.template.loader import render_to_string
# import re # 如果需要圖片上傳功能，取消註釋
# import pytesseract # 如果需要圖片上傳功能，取消註釋
# from PIL import Image # 如果需要圖片上傳功能，取消註釋
# 確保導入所有模型，包括 Announcement
from .models import Animal, Hall, Review, PendingAppointment, Note, Announcement

# --- Tesseract 配置 (如果需要圖片上傳功能，取消註釋並確保路徑正確) ---
# try:
#     pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
#     tessdata_dir_config = r'--tessdata-dir "C:\\Program Files\\Tesseract-OCR\\tessdata"'
#     pytesseract.get_tesseract_version()
# except Exception as e:
#     print(f"Warning: Tesseract not configured or found correctly: {e}")

# --- 工具函數 (如果需要圖片上傳功能，取消註釋) ---
# def parse_schedule_line(line):
#     pattern = r'^(?P<name>[\u4e00-\u9fa5A-Za-z0-9]+)\s+(?P<measurements>\d+/\d+/[A-Z])\s+(?P<fee>\d+)$'
#     m = re.match(pattern, line.strip())
#     if m: return m.groupdict()
#     return None

# --- 價格格式化函數 (如果價格字段是 CharField，可能不需要特殊格式化) ---
# def format_price(value):
#     if value is None: return None
#     return str(value)

# --- 主頁視圖 (入口頁面) ---
def home(request):
    # --- AJAX 請求處理 (優先判斷) ---
    is_ajax_request = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    is_daily_schedule_ajax = is_ajax_request and request.GET.get('ajax') == '1'

    # 打印調試信息
    print("-" * 20)
    print(f"Request Path: {request.path}")
    print(f"Request GET Params: {request.GET}")
    print(f"Is AJAX Header Present: {is_ajax_request}")
    print(f"Is 'ajax=1' Param Present: {'ajax' in request.GET and request.GET.get('ajax') == '1'}")
    print(f"Handling as Daily Schedule AJAX: {is_daily_schedule_ajax}")


    if is_daily_schedule_ajax:
        print(">>> Handling as Daily Schedule AJAX Request <<<")
        hall_id = request.GET.get('hall_id')
        selected_hall_id = hall_id or 'all'
        print(f"    Selected Hall ID: {selected_hall_id}")

        try:
            # **只在 AJAX 請求時查詢 animals**
            animals_base_qs = Animal.objects.filter(is_active=True).select_related('hall')
            if selected_hall_id != "all":
                try: hall_id_int = int(selected_hall_id); animals_qs = animals_base_qs.filter(hall_id=hall_id_int)
                except (ValueError, TypeError): animals_qs = animals_base_qs.all() # 無效 ID 顯示全部
            else:
                animals_qs = animals_base_qs.all()

            animals_for_ajax = animals_qs.annotate(
                approved_review_count=Count('reviews', filter=Q(reviews__approved=True))
            ).order_by(*Animal._meta.ordering) # 使用模型定義的排序

            # 獲取用戶狀態
            pending_ids = set()
            notes_by_animal = {}
            if request.user.is_authenticated:
                 pending_ids = set(str(pa.animal_id) for pa in PendingAppointment.objects.filter(user=request.user))
                 notes_by_animal = {str(note.animal_id): note for note in Note.objects.filter(user=request.user)}

            ajax_context = {
                'animals': animals_for_ajax, # 傳遞動物列表
                'user': request.user,
                'pending_ids': pending_ids,
                'notes_by_animal': notes_by_animal
            }

            # ******************** 修改開始 ********************
            # 渲染新的包裹模板，這個模板內部會進行迴圈並 include 單行模板
            print(f"    Rendering partial template: partials/_daily_schedule_table_content.html") # 更新打印信息
            table_html = render_to_string('partials/_daily_schedule_table_content.html', ajax_context, request=request)
            print(f"    Partial HTML rendered successfully (length: {len(table_html)}).")

            # 獲取第一個動物的信息，用於更新 Modal 的照片和介紹區域
            first_animal_data = {}
            try:
                if animals_for_ajax: # 檢查列表是否為空
                     first_animal = animals_for_ajax[0]
                     first_animal_data = {
                         'photo_url': first_animal.photo.url if first_animal.photo else '',
                         'name': first_animal.name or '', # 確保有默認值
                         'introduction': first_animal.introduction or '' # 確保有默認值
                     }
            except Exception as e:
                print(f"    Warning: Error getting first animal data for AJAX response: {e}")

            print(f"    Returning JSON including table_html and first_animal data.")
            # 返回 JSON，同時包含渲染好的 HTML 和第一個動物的信息
            return JsonResponse({
                'table_html': table_html,
                'first_animal': first_animal_data # 將第一個動物信息也返回給 JS
            })
            # ******************** 修改結束 ********************

        except Exception as e:
            print(f"    !!! Error during AJAX handling: {e} !!!")
            # 打印更詳細的錯誤追蹤信息
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'伺服器處理班表請求時發生錯誤: {e}'}, status=500)

    else:
        print(">>> Handling as Full Page Request (Rendering index.html) <<<")
        # --- 渲染完整入口頁面的邏輯 ---
        halls = Hall.objects.all().order_by('order', 'name')
        context = {'halls': halls, 'user': request.user}

        # 獲取公告和宣傳圖
        try:
            active_announcement = Announcement.objects.filter(is_active=True).first()
            context['announcement'] = active_announcement
        except Exception as e: print(f"Error fetching announcement: {e}"); context['announcement'] = None
        try:
            first_animal_for_promo = Animal.objects.filter(is_active=True, photo__isnull=False).exclude(photo='').order_by('?').first()
            context['promo_photo_url'] = first_animal_for_promo.photo.url if first_animal_for_promo else None
            context['promo_animal_name'] = first_animal_for_promo.name if first_animal_for_promo else None
        except Exception as e: print(f"Error fetching promo photo: {e}"); context['promo_photo_url'] = None; context['promo_animal_name'] = None

        # 獲取用戶特定數據
        pending_ids = set(); notes_by_animal = {}; pending_appointments_list = []; my_notes_list = []; latest_reviews_qs = Review.objects.none()
        if request.user.is_authenticated:
            try:
                # 使用 Prefetch 優化相關查詢 (如果需要訪問動物的其他關聯數據)
                pending_appointments_qs = PendingAppointment.objects.filter(user=request.user).select_related('animal', 'animal__hall')
                notes_qs = Note.objects.filter(user=request.user).select_related('animal', 'animal__hall')
                pending_animal_ids = set(str(pa.animal_id) for pa in pending_appointments_qs) # 改為 pa.animal_id
                notes_by_animal = {str(note.animal_id): note for note in notes_qs}
                pending_appointments_list = list(pending_appointments_qs)
                my_notes_list = list(notes_qs)
                latest_reviews_qs = Review.objects.filter(approved=True).select_related('animal', 'animal__hall', 'user').order_by("-created_at")[:15]
                # 為 Modal 中的動物添加心得計數 (優化)
                animal_ids_in_modals = set(pa.animal_id for pa in pending_appointments_list if pa.animal_id) | set(n.animal_id for n in my_notes_list if n.animal_id) | set(r.animal_id for r in latest_reviews_qs if r.animal_id)
                if animal_ids_in_modals:
                     counts_for_modals = Animal.objects.filter(id__in=animal_ids_in_modals).annotate(modal_review_count=Count('reviews', filter=Q(reviews__approved=True))).values('id', 'modal_review_count')
                     counts_dict = {item['id']: item['modal_review_count'] for item in counts_for_modals}
                     # 直接更新列表中的對象，避免再次查詢
                     for pa in pending_appointments_list:
                         if hasattr(pa, 'animal') and pa.animal: pa.animal.approved_review_count = counts_dict.get(pa.animal_id, 0)
                     for note in my_notes_list:
                         if hasattr(note, 'animal') and note.animal: note.animal.approved_review_count = counts_dict.get(note.animal_id, 0)
                     for review in latest_reviews_qs:
                         if hasattr(review, 'animal') and review.animal: review.animal.approved_review_count = counts_dict.get(review.animal_id, 0)
            except Exception as e: print(f"Error fetching user-specific data: {e}")

        context['pending_ids'] = pending_ids # 確保傳遞的是集合
        context['notes_by_animal'] = notes_by_animal
        context['pending_appointments'] = pending_appointments_list
        context['my_notes'] = my_notes_list
        context['latest_reviews'] = latest_reviews_qs
        login_error = request.session.pop('login_error', None);
        if login_error: context['login_error'] = login_error
        context['selected_hall_id'] = 'all' # 用於標記初始狀態，如果需要
        print("    Rendering full template: index.html")
        try:
            return render(request, 'index.html', context)
        except Exception as e:
            print(f"    !!! Error rendering index.html: {e} !!!")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': '渲染頁面時發生內部錯誤'}, status=500)


# --- 圖片上傳視圖 (完整實現，如果需要) ---
# @login_required # 限制管理員或其他有權限的用戶
# def upload_schedule_image_view(request):
#     if request.method == "POST":
#         hall_id = request.POST.get("hall")
#         schedule_image_file = request.FILES.get("schedule_image")
#         if not hall_id or not schedule_image_file:
#             messages.error(request, "請選擇館別並上傳班表圖片")
#             return redirect("upload_schedule_image") # 假設 URL name 是這個
#         try:
#             hall = Hall.objects.get(id=hall_id)
#             image = Image.open(schedule_image_file)
#             ocr_text = pytesseract.image_to_string(image, lang='chi_sim', config=tessdata_dir_config) # 假設使用簡體中文識別
#         except Hall.DoesNotExist:
#             messages.error(request, "選擇的館別不存在")
#             return redirect("upload_schedule_image")
#         except pytesseract.TesseractNotFoundError:
#              messages.error(request, "Tesseract 未安裝或未正確配置路徑")
#              return redirect("upload_schedule_image")
#         except Exception as e:
#             messages.error(request, f"處理圖片或 OCR 時發生錯誤: {e}")
#             return redirect("upload_schedule_image")

#         lines = ocr_text.splitlines()
#         update_results = []
#         processed_count = 0
#         for line in lines:
#             parsed = parse_schedule_line(line) # 使用你的解析函數
#             if parsed:
#                 name = parsed["name"]
#                 measurements = parsed["measurements"]
#                 fee_str = parsed["fee"]
#                 # 嘗試根據名稱查找 (可能需要更精確的匹配邏輯)
#                 # 例如：移除可能的標點符號，或者使用更模糊的查詢
#                 cleaned_name = re.sub(r'[^\w]', '', name) # 簡單清理名稱
#                 if not cleaned_name: continue # 跳過空名稱

#                 animal_qs = Animal.objects.filter(name__icontains=cleaned_name) # 模糊匹配
#                 matched_animal = animal_qs.first()

#                 if matched_animal:
#                     try:
#                         matched_animal.fee = int(fee_str)
#                         # 解析三圍，增加錯誤處理
#                         try:
#                             height, weight, cup = measurements.split("/")
#                             matched_animal.height = int(height)
#                             matched_animal.weight = int(weight)
#                             matched_animal.cup_size = cup.strip().upper() # 清理並轉大寫
#                         except ValueError:
#                              update_results.append(f"無法解析 {name} 的三圍: {measurements}")
#                         except Exception as split_err:
#                              update_results.append(f"分割 {name} 的三圍時出錯 ({measurements}): {split_err}")

#                         matched_animal.hall = hall # 更新館別
#                         matched_animal.is_active = True # 假設上傳班表意味著啟用
#                         matched_animal.save()
#                         update_results.append(f"已更新 {matched_animal.name} ({hall.name})：三圍 {measurements}, 台費 {fee}")
#                         processed_count += 1
#                     except ValueError:
#                          update_results.append(f"處理 {name} 時費用格式錯誤: {fee_str}")
#                     except Exception as save_err:
#                         update_results.append(f"保存 {name} 時出錯: {save_err}")
#                 else:
#                     update_results.append(f"找不到匹配的記錄：{name} (嘗試匹配: {cleaned_name})")

#         if processed_count > 0:
#             messages.success(request, f"成功更新 {processed_count} 筆資料。")
#         else:
#              messages.warning(request, "未更新任何資料，請檢查圖片內容或解析邏輯。")
#         for res in update_results: # 顯示詳細處理結果
#                 messages.info(request, res)
#         return redirect("upload_schedule_image")
#     else: # GET 請求
#         halls = Hall.objects.all().order_by('order', 'name')
#         return render(request, "upload_schedule.html", {"halls": halls}) # 假設模板名


# --- 用戶認證視圖 ---
def user_login(request):
    if request.method == "POST":
        username = request.POST.get('username', '').strip() # 獲取並清理
        password = request.POST.get('password', '') # 密碼不清空格
        if not username or not password:
             request.session['login_error'] = '請輸入帳號和密碼'
             return redirect('home')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            request.session.pop('login_error', None) # 登入成功清除錯誤
            return redirect('home')
        else:
            request.session['login_error'] = '帳號或密碼錯誤'
            return redirect('home')
    # GET 請求也重定向回首頁
    return redirect('home')

@require_POST
def user_logout(request):
    logout(request)
    # messages.success(request, "您已成功登出。") # 可以取消註釋以顯示消息
    return redirect('home')

# --- 心得處理 ---
@login_required
def add_review(request):
    if request.method == "POST":
        animal_id = request.POST.get("animal_id")
        if not animal_id: return JsonResponse({"success": False, "error": "缺少 animal_id"})
        try: animal = Animal.objects.get(id=animal_id)
        except (Animal.DoesNotExist, ValueError, TypeError): return JsonResponse({"success": False, "error": "找不到或無效的動物 ID"})

        face_list = request.POST.getlist("face")
        temperament_list = request.POST.getlist("temperament")
        scale_list = request.POST.getlist("scale")
        content = request.POST.get("content", "").strip()
        age_str = request.POST.get("age")

        # 後端驗證
        errors = {}
        if len(face_list) > 3: errors['face'] = "臉蛋最多選3個"
        if len(temperament_list) > 3: errors['temperament'] = "氣質最多選3個"
        if not content: errors['content'] = "心得內容不能為空"
        age = None
        if age_str:
            try: age = int(age_str); assert age > 0
            except (ValueError, AssertionError): errors['age'] = "年紀必須是正整數"

        if errors: # 如果有驗證錯誤
            return JsonResponse({"success": False, "error": "輸入無效", "errors": errors}, status=400) # 返回 400 狀態碼和錯誤細節

        try:
            Review.objects.create(
                animal=animal, user=request.user, age=age,
                looks=request.POST.get("looks"),
                face=','.join(face_list),
                temperament=','.join(temperament_list),
                physique=request.POST.get("physique"),
                cup=request.POST.get("cup"), cup_size=request.POST.get("cup_size"),
                skin_texture=request.POST.get("skin_texture"), skin_color=request.POST.get("skin_color"),
                music=request.POST.get("music"), music_price=request.POST.get("music_price") or None,
                sports=request.POST.get("sports"), sports_price=request.POST.get("sports_price") or None,
                scale=','.join(scale_list), content=content, approved=False # 預設不通過審核
            )
            return JsonResponse({"success": True, "message": "評論已提交，待審核後將顯示"})
        except Exception as e:
             print(f"Error creating review: {e}")
             import traceback
             traceback.print_exc()
             return JsonResponse({"success": False, "error": "儲存心得時發生內部錯誤"}, status=500)

    elif request.method == "GET":
        animal_id = request.GET.get("animal_id")
        if not animal_id: return JsonResponse({"reviews": []})
        try: animal = Animal.objects.get(id=animal_id)
        except (Animal.DoesNotExist, ValueError, TypeError): return JsonResponse({"reviews": []})

        reviews_qs = Review.objects.filter(animal=animal, approved=True).select_related('user').order_by("-created_at")
        # 優化：一次查詢所有相關用戶的心得總數
        user_ids = list(reviews_qs.values_list('user_id', flat=True).distinct())
        user_review_counts = {}
        if user_ids:
            counts_query = Review.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(totalCount=Count('id'))
            user_review_counts = {item['user_id']: item['totalCount'] for item in counts_query}

        data = []
        for r in reviews_qs:
            user_display_name = "匿名"
            if hasattr(r, 'user') and r.user: user_display_name = r.user.first_name or r.user.username
            # 格式化日期
            formatted_date = ""
            if r.created_at:
                try: formatted_date = timezone.localtime(r.created_at).strftime("%Y-%m-%d")
                except Exception as date_err: print(f"Error formatting date {r.created_at}: {date_err}")

            data.append({
                "user": user_display_name,
                "totalCount": user_review_counts.get(r.user_id, 0), # 使用預先計算的總數
                "age": r.age,
                "looks": r.looks,
                "face": r.face,
                "temperament": r.temperament,
                "physique": r.physique,
                "cup": r.cup,
                "cup_size": r.cup_size,
                "skin_texture": r.skin_texture,
                "skin_color": r.skin_color,
                "music": r.music,
                "music_price": r.music_price,
                "sports": r.sports,
                "sports_price": r.sports_price,
                "scale": r.scale,
                "content": r.content,
                "created_at": formatted_date # 使用格式化後的日期
            })
        return JsonResponse({"reviews": data})

    return JsonResponse({"success": False, "error": "請求方法不支援"}, status=405)

# --- 待約處理 ---
@require_POST
@login_required
def add_pending_appointment(request):
     animal_id = request.POST.get("animal_id");
     if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"})
     try:
         animal = Animal.objects.filter(id=animal_id).first()
         if not animal: return JsonResponse({"success": False, "error": "找不到該動物"})
         _, created = PendingAppointment.objects.get_or_create(user=request.user, animal=animal)
         if not created: return JsonResponse({"success": False, "error": "該美容師已在待約清單中"}) # 之前可能就是這樣寫的，保持一致
         pending_count = PendingAppointment.objects.filter(user=request.user).count()
         return JsonResponse({"success": True, "message": f"{animal.name} 已加入待約清單", "pending_count": pending_count})
     except (ValueError, TypeError): return JsonResponse({"success": False, "error": "無效的動物 ID"})
     except Exception as e:
         print(f"Error adding pending appointment: {e}");
         import traceback; traceback.print_exc()
         return JsonResponse({"success": False, "error": "加入待約時發生錯誤"}, status=500)

@require_POST
@login_required
def remove_pending(request):
    animal_id = request.POST.get("animal_id");
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"})
    try:
        # 先嘗試刪除
        deleted_count, _ = PendingAppointment.objects.filter(user=request.user, animal_id=animal_id).delete()

        if deleted_count == 0:
            # 如果沒刪除任何東西，檢查動物是否存在，給出更精確的錯誤
            if not Animal.objects.filter(id=animal_id).exists():
                return JsonResponse({"success": False, "error": "找不到該動物"})
            else:
                # 動物存在，但待約項目不存在
                return JsonResponse({"success": False, "error": "該待約項目不存在"})

        # 刪除成功，計算剩餘數量
        pending_count = PendingAppointment.objects.filter(user=request.user).count()
        # 獲取動物名稱用於消息提示（可選）
        animal_name = Animal.objects.filter(id=animal_id).values_list('name', flat=True).first() or "該美容師"
        return JsonResponse({"success": True, "message": f"{animal_name} 待約項目已移除", "pending_count": pending_count})
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "無效的動物 ID"})
    except Exception as e:
        print(f"Error removing pending appointment: {e}");
        import traceback; traceback.print_exc()
        return JsonResponse({"success": False, "error": "移除待約時發生錯誤"}, status=500)

# --- 筆記處理 ---
@require_POST
@login_required
def add_note(request): # 同時處理新增和更新
    animal_id = request.POST.get("animal_id"); content = request.POST.get("content", "").strip();
    if not animal_id: return JsonResponse({"success": False, "error": "缺少動物 ID"})
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"})
    try:
        animal = Animal.objects.filter(id=animal_id).first()
        if not animal: return JsonResponse({"success": False, "error": "找不到該美容師"})
        # 使用 update_or_create 簡化邏輯
        note, created = Note.objects.update_or_create(
            user=request.user,
            animal=animal,
            defaults={"content": content} # 無論新增或更新，都設置 content
        )
        message = "筆記已新增" if created else "筆記已更新"
        return JsonResponse({"success": True, "message": message, "note_id": note.id, "note_content": note.content})
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "無效的動物 ID"})
    except Exception as e:
        print(f"Error adding/updating note: {e}");
        import traceback; traceback.print_exc()
        return JsonResponse({"success": False, "error": "儲存筆記時發生錯誤"}, status=500)

@require_POST
@login_required
def delete_note(request):
    note_id = request.POST.get("note_id");
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"})
    try:
        deleted_count, _ = Note.objects.filter(id=note_id, user=request.user).delete()
        if deleted_count == 0:
            # 檢查筆記是否存在，但可能不屬於該用戶
            if Note.objects.filter(id=note_id).exists():
                 return JsonResponse({"success": False, "error": "無權限刪除此筆記"})
            else:
                 return JsonResponse({"success": False, "error": "筆記不存在"})
        return JsonResponse({"success": True, "message": "筆記已刪除"})
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "無效的筆記 ID"})
    except Exception as e:
        print(f"Error deleting note: {e}");
        import traceback; traceback.print_exc()
        return JsonResponse({"success": False, "error": "刪除筆記時發生錯誤"}, status=500)

# update_note 視圖現在與 add_note 功能完全重疊，因為 add_note 使用了 update_or_create
# 如果沒有特殊邏輯，可以安全地移除 update_note 視圖及其 URL 配置
# 如果要保留，確保前端調用的是正確的 URL
@require_POST
@login_required
def update_note(request):
    note_id = request.POST.get("note_id"); content = request.POST.get("content", "").strip();
    if not note_id: return JsonResponse({"success": False, "error": "缺少筆記 ID"})
    if not content: return JsonResponse({"success": False, "error": "筆記內容不能為空"})
    try:
        # 嘗試獲取屬於當前用戶的筆記
        note = Note.objects.get(id=note_id, user=request.user)
        note.content = content
        note.save(update_fields=['content']) # 只更新 content 字段
        return JsonResponse({"success": True, "message": "筆記已更新", "note_id": note.id, "note_content": note.content})
    except Note.DoesNotExist:
        # 筆記不存在或不屬於該用戶
        return JsonResponse({"success": False, "error": "筆記不存在或無權限"})
    except (ValueError, TypeError):
        return JsonResponse({"success": False, "error": "無效的筆記 ID"})
    except Exception as e:
        print(f"Error updating note: {e}");
        import traceback; traceback.print_exc()
        return JsonResponse({"success": False, "error": "更新筆記時發生錯誤"}, status=500)

# --- my_notes 相關視圖 (如果不需要單獨頁面，可以刪除) ---
# @login_required
# def my_notes_json(request): ...
# @login_required
# def my_notes(request): ...