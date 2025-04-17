# D:\bkgg\mybackend\schedule_parser\views.py
import json
import traceback # 用於打印詳細錯誤
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseServerError
from django.views.decorators.http import require_http_methods, require_POST
# --- *** 從正確路徑導入 *** ---
from django.contrib.admin.views.decorators import staff_member_required
# -----------------------
from django.db import transaction
from django.db.models import Q
# --- *** 從你的 myapp 導入模型 *** ---
from myapp.models import Hall, Animal
# -----------------------------------
from .models import DailySchedule       # 從當前 app 導入
from .utils import parse_line_schedule # 從 utils 導入

@staff_member_required # 確保只有 staff 或 superuser 可以訪問
def parse_schedule_view(request):
    """
    處理班表解析頁面的 GET 和 POST 請求。
    GET: 顯示頁面。
    POST: 根據 action 參數執行預覽或儲存操作。
    """
    if request.method == 'GET':
        # GET 請求：顯示頁面和館別下拉選單
        try:
            # 只獲取活動的 Hall 用於下拉選單
            active_halls = Hall.objects.filter(is_active=True).order_by('order', 'name')
            context = {'active_halls': active_halls}
            # 確保模板路徑正確
            return render(request, 'schedule_parser/parse_schedule.html', context)
        except Exception as e:
            print(f"Error rendering parse schedule page (GET): {e}")
            traceback.print_exc()
            return HttpResponseServerError("無法加載班表解析頁面，請稍後再試或聯繫管理員。")

    elif request.method == 'POST':
        action = request.POST.get('action') # 'preview' 或 'save'
        hall_id = request.POST.get('hall_id')
        schedule_text = request.POST.get('schedule_text')

        # --- 基本輸入驗證 ---
        if not hall_id:
            return JsonResponse({'error': '請選擇館別'}, status=400)
        if not schedule_text:
            return JsonResponse({'error': '請貼上文字班表'}, status=400)
        if action not in ['preview', 'save']:
             return JsonResponse({'error': '無效的操作請求'}, status=400)

        # --- 驗證所選館別 ---
        try:
            selected_hall = Hall.objects.get(id=hall_id, is_active=True)
        except Hall.DoesNotExist:
            return JsonResponse({'error': '選擇的館別無效或未啟用'}, status=400)
        except (ValueError, TypeError):
             return JsonResponse({'error': '館別 ID 格式錯誤'}, status=400)
        except Exception as e: # 捕獲其他可能的錯誤
             print(f"Error getting Hall object: {e}")
             traceback.print_exc()
             return JsonResponse({'error': '獲取館別信息時出錯'}, status=500)


        # --- 解析班表文字 ---
        try:
            print(f"Parsing schedule text for Hall ID: {hall_id}...")
            parsed_blocks = parse_line_schedule(schedule_text)
            print(f"Parsed {len(parsed_blocks)} blocks.")
        except Exception as e:
             print(f"Error during parsing: {e}")
             traceback.print_exc()
             return JsonResponse({'error': f'解析班表時發生錯誤: {e}'}, status=500)


        # ==================================
        # --- 處理預覽 (action == 'preview') ---
        # ==================================
        if action == 'preview':
            print("--- Handling PREVIEW action ---")
            preview_data = []
            for block in parsed_blocks:
                # 確保 block 有效且包含 name
                if not block or not block.get('name'):
                    print("Skipping invalid block:", block)
                    continue

                match_status = "not_found"
                matched_animal_id = None
                matched_animal_info = None # 存儲匹配到的動物信息 (id, name, hall_name, fee)
                possible_matches = []    # 存儲多重匹配或手動關聯的選項

                search_name = block['name']
                # 組合所有可能用於匹配的名字/別名
                potential_aliases = {alias.strip() for alias in [
                    search_name,
                    block.get('alias_suggestion'),
                    block.get('original_name_text')
                ] if alias} # 使用 set 去重並排除空值
                print(f"  Matching '{search_name}' (potential aliases: {potential_aliases})...")

                try:
                    # 優先級 1: 精確匹配 (名字 + 當前選擇館別)
                    exact_match = Animal.objects.filter(name__iexact=search_name, hall=selected_hall, is_active=True).first()
                    if exact_match:
                        print(f"    Found exact match: ID {exact_match.id}")
                        match_status = "matched_exact"
                        matched_animal_id = exact_match.id
                        matched_animal_info = {'id': exact_match.id, 'name': exact_match.name, 'hall_name': selected_hall.name, 'fee': exact_match.fee}
                    else:
                        # 優先級 2: 嘗試用名字或別名匹配 (所有活動美容師)
                        q_objects = Q(name__iexact=search_name) # 匹配當前名字 (忽略大小寫)
                        # --- 構建 JSONField 的查詢 (假設是列表) ---
                        for alias in potential_aliases:
                            q_objects |= Q(aliases__contains=[alias]) # 精確匹配列表中的元素

                        alias_query = Animal.objects.filter(q_objects, is_active=True)
                        query_count = alias_query.count()
                        print(f"    Alias/Name query found {query_count} match(es).")

                        if query_count == 1:
                            animal = alias_query.first()
                            match_status = "matched_alias_or_name"
                            matched_animal_id = animal.id
                            matched_animal_info = {'id': animal.id, 'name': animal.name, 'hall_name': animal.hall.name if animal.hall else '未分館', 'fee': animal.fee}
                            print(f"    Found unique alias/name match: ID {animal.id} ({animal.name})")
                        elif query_count > 1:
                            match_status = "multiple_matches"
                            possible_matches = list(alias_query.select_related('hall').values('id', 'name', 'hall__name'))
                            print(f"    Found multiple matches: {possible_matches}")
                        else:
                            match_status = "not_found"
                            print("    No match found.")

                    # 如果未找到，提供同館別的美容師作為手動關聯選項
                    if match_status == "not_found":
                        possible_matches = list(Animal.objects.filter(hall=selected_hall, is_active=True).order_by('name').values('id', 'name'))
                        print(f"    Prepared {len(possible_matches)} possible associations from the same hall.")

                except Exception as e:
                     print(f"!!! Error during matching for name '{search_name}': {e}")
                     traceback.print_exc()
                     match_status = "error" # 標記匹配出錯

                # 將此塊的預覽數據添加到列表
                preview_data.append({
                    'parsed': block,                # 解析出的原始資料
                    'status': match_status,         # 匹配狀態
                    'matched_animal_id': matched_animal_id, # 匹配到的 ID (如果唯一匹配)
                    'matched_animal_info': matched_animal_info, # 匹配到的動物資訊
                    'possible_matches': possible_matches, # 手動關聯的選項
                })
            # 預覽完成，返回 JSON 數據
            print("--- Preview data generated ---")
            return JsonResponse({'preview_data': preview_data})


        # =================================
        # --- 處理儲存 (action == 'save') ---
        # =================================
        elif action == 'save':
            print(">>> Received SAVE action <<<")
            try:
                final_data_str = request.POST.get('final_data')
                print(f"Raw final_data string: {final_data_str[:500]}...") # 打印部分原始字串
                if not final_data_str:
                    print("Error: Missing final_data")
                    return JsonResponse({'error': '缺少最終確認數據'}, status=400)

                try:
                    final_data = json.loads(final_data_str) # 解析前端 JSON
                    if not isinstance(final_data, list): # 基本驗證
                         raise ValueError("Final data should be a list.")
                    print(f"Parsed final_data: {final_data}")
                except (json.JSONDecodeError, ValueError) as e:
                     print(f"Error: JSONDecodeError/ValueError - {e}")
                     return JsonResponse({'error': f'前端提交的數據格式錯誤或無效: {e}'}, status=400)

                # 初始化計數器
                animals_created_count = 0
                animals_updated_count = 0
                schedules_created_count = 0

                # 使用數據庫事務確保操作的原子性
                print("Entering transaction...")
                with transaction.atomic():
                    # 1. 處理需要新增的 Animal
                    print("Processing 'add_new' operations...")
                    # 臨時映射，如果前端用索引標識新增項
                    new_animal_temp_map = {} # { 'temp_id_or_index': new_animal_object }
                    items_to_process_later = [] # 存儲非新增的操作

                    for index, item in enumerate(final_data):
                        operation = item.get('operation')
                        if operation == 'add_new':
                            parsed_data = item.get('parsed_data', {})
                            final_slots = item.get('final_slots')
                            new_name = parsed_data.get('name')
                            alias_suggestion = parsed_data.get('alias_suggestion')
                            print(f"  Attempting to add new animal: '{new_name}'")
                            if not new_name:
                                print("    Skipping add: No name provided."); continue

                            # 再次檢查重複 (在事務內更安全)
                            if Animal.objects.filter(name=new_name, hall=selected_hall).exists():
                                print(f"    Skipping add: Animal '{new_name}' already exists in hall '{selected_hall.name}'.")
                                # 可以考慮查找現有ID並轉為 'use_existing'
                                existing_animal = Animal.objects.get(name=new_name, hall=selected_hall)
                                item['animal_id'] = existing_animal.id
                                item['operation'] = 'use_existing' # 修改操作類型
                                items_to_process_later.append(item) # 加入待後續處理列表
                                continue # 不再執行新增

                            aliases_list = [alias_suggestion] if alias_suggestion else []

                            try:
                                new_animal = Animal.objects.create(
                                    name=new_name, hall=selected_hall,
                                    fee=parsed_data.get('parsed_fee'), height=parsed_data.get('height'),
                                    weight=parsed_data.get('weight'), cup_size=parsed_data.get('cup'),
                                    introduction=parsed_data.get('introduction'), is_active=True,
                                    order=999, aliases=aliases_list )
                                animals_created_count += 1
                                print(f"    Created Animal ID: {new_animal.id}")
                                # 將新創建的 animal 加入待處理列表，以便後續創建班表
                                item['animal_id'] = new_animal.id # 賦值真實 ID
                                item['operation'] = 'use_existing' # 已創建，按現有處理
                                items_to_process_later.append(item)
                            except Exception as create_err:
                                print(f"    !!! Error creating animal '{new_name}': {create_err}")
                                traceback.print_exc()
                                # 可以在這裡決定是忽略這個錯誤繼續，還是拋出異常回滾事務
                                # 暫時忽略，繼續處理其他項
                        else:
                             # 非新增操作，加入待後續處理列表
                             items_to_process_later.append(item)

                    # 2. 處理現有 Animal 的費用更新和班表數據整理
                    print("Processing existing/associated animals and fee updates...")
                    animals_to_update_fee = {} # {animal_id: new_fee}
                    final_schedule_inputs = [] # [{'animal_id': id, 'slots': '...'}, ...]
                    valid_final_animal_ids = set()

                    for item in items_to_process_later:
                        operation = item.get('operation')
                        animal_id = item.get('animal_id')
                        final_slots = item.get('final_slots')
                        update_fee_flag = item.get('update_fee', False)
                        parsed_data = item.get('parsed_data', {})

                        if operation == 'ignore':
                            continue

                        if operation == 'use_existing' or operation == 'associate':
                            if not animal_id:
                                print(f"Warning: Operation '{operation}' missing animal_id. Skipping item: {item}")
                                continue
                            try:
                                animal_id = int(animal_id) # 確保 ID 是整數
                                # 檢查費用更新標記和數據
                                parsed_fee = parsed_data.get('parsed_fee')
                                if update_fee_flag and parsed_fee is not None:
                                    # 記錄待更新費用，後面統一更新
                                    animals_to_update_fee[animal_id] = parsed_fee
                                    print(f"  Marked Animal ID {animal_id} for fee update to {parsed_fee}")

                                # 加入最終排班列表
                                final_schedule_inputs.append({'animal_id': animal_id, 'slots': final_slots})
                                valid_final_animal_ids.add(animal_id)

                            except (ValueError, TypeError):
                                 print(f"Warning: Invalid Animal ID '{animal_id}'. Skipping schedule.")
                        else:
                             print(f"Warning: Unknown operation '{operation}' during final processing. Skipping item: {item}")

                    # 批量更新費用
                    updated_fee_count_actual = 0
                    if animals_to_update_fee:
                        print(f"Updating fees for {len(animals_to_update_fee)} animals...")
                        for animal_id, new_fee in animals_to_update_fee.items():
                            try:
                                # 再次檢查費用是否真的需要更新
                                current_animal = Animal.objects.get(id=animal_id)
                                if current_animal.fee != new_fee:
                                    rows_affected = Animal.objects.filter(id=animal_id).update(fee=new_fee)
                                    if rows_affected > 0:
                                        updated_fee_count_actual += 1
                                        print(f"  Successfully updated fee for Animal ID {animal_id}")
                                else:
                                     print(f"  Skipping fee update for ID {animal_id} (fee already matches)")
                            except Animal.DoesNotExist:
                                 print(f"  Warning: Animal ID {animal_id} not found during fee update.")
                            except Exception as fee_update_err:
                                 print(f"  !!! Error updating fee for ID {animal_id}: {fee_update_err}")
                        animals_updated_count = updated_fee_count_actual


                    # 3. 清除舊班表
                    print(f"Deleting old schedules for hall ID {selected_hall.id}...")
                    try:
                        deleted_count, _ = DailySchedule.objects.filter(hall=selected_hall).delete()
                        print(f"  Deleted {deleted_count} old schedule records.")
                    except Exception as delete_err:
                         print(f"  !!! Error deleting old schedules: {delete_err}")
                         traceback.print_exc()
                         raise # 重新拋出異常以回滾事務

                    # 4. 批量創建新班表
                    print("Creating new schedules...")
                    schedule_objects = []
                    # 最後確認 animal_id 存在且 active
                    final_valid_animals_set = set(Animal.objects.filter(id__in=valid_final_animal_ids, is_active=True).values_list('id', flat=True))

                    for schedule_info in final_schedule_inputs:
                        if schedule_info['animal_id'] in final_valid_animals_set:
                            schedule_objects.append(
                                DailySchedule(
                                    hall=selected_hall,
                                    animal_id=schedule_info['animal_id'],
                                    time_slots=schedule_info['slots']
                                )
                            )
                        else:
                            print(f"  Skipping final schedule creation: Animal ID {schedule_info['animal_id']} not found or inactive.")

                    if schedule_objects:
                        try:
                            DailySchedule.objects.bulk_create(schedule_objects)
                            schedules_created_count = len(schedule_objects)
                            print(f"  Created {schedules_created_count} new schedule records.")
                        except Exception as create_err:
                             print(f"  !!! Error bulk creating schedules: {create_err}")
                             traceback.print_exc()
                             raise # 重新拋出異常以回滾事務

                # --- 事務成功結束 ---
                print("Transaction committed successfully.")
                return JsonResponse({
                    'success': True,
                    'message': f'班表已儲存。新增美容師: {animals_created_count}, 更新費用: {animals_updated_count}, 更新班表: {schedules_created_count}。'
                })

            # --- 捕獲事務內外的所有異常 ---
            except Exception as e:
                print(f"!!! Error during SAVE action processing: {e} !!!")
                traceback.print_exc()
                # 避免暴露詳細錯誤給前端，只返回通用錯誤信息
                return JsonResponse({'error': '儲存班表時發生內部錯誤，請檢查伺服器日誌。'}, status=500)

        else: # 無效的 action
            print(f"Error: Invalid action '{action}' received.")
            return JsonResponse({'error': '無效的操作請求'}, status=400)

    else: # 非 GET 或 POST 請求
        print(f"Error: Unsupported HTTP method '{request.method}'.")
        return HttpResponseBadRequest("不支持的請求方法")