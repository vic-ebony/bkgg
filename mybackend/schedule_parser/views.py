# D:\bkgg\mybackend\schedule_parser\views.py
import json
import traceback # 用於打印詳細錯誤
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseServerError
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Q
from myapp.models import Hall, Animal # 從 myapp 導入模型
from .models import DailySchedule       # 從當前 app 導入
# --- *** 導入所有需要的解析器 *** ---
from .utils import parse_line_schedule, parse_chatanghui_schedule # <--- 導入兩個解析函數

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
            active_halls = Hall.objects.filter(is_active=True).order_by('order', 'name')
            context = {'active_halls': active_halls}
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
        # 注意：在 preview 時也需要 schedule_text
        if not schedule_text:
             return JsonResponse({'error': '請貼上文字班表'}, status=400)
        if action not in ['preview', 'save']:
             return JsonResponse({'error': '無效的操作請求'}, status=400)

        # --- 驗證所選館別 ---
        try:
            # 確保獲取 Hall 時也獲取 schedule_format_type
            selected_hall = Hall.objects.get(id=hall_id, is_active=True)
            # 假設 Hall 模型有 schedule_format_type 字段
            hall_format_type = selected_hall.schedule_format_type
        except Hall.DoesNotExist:
            return JsonResponse({'error': '選擇的館別無效或未啟用'}, status=400)
        except (ValueError, TypeError):
             return JsonResponse({'error': '館別 ID 格式錯誤'}, status=400)
        except AttributeError:
             # 如果 Hall 模型還沒有 schedule_format_type 字段，給出提示
             print(f"Error: Hall model does not have 'schedule_format_type' attribute.")
             return JsonResponse({'error': '伺服器配置錯誤：缺少館別格式類型信息'}, status=500)
        except Exception as e:
             print(f"Error getting Hall object: {e}")
             traceback.print_exc()
             return JsonResponse({'error': '獲取館別信息時出錯'}, status=500)

        # --- 修改：根據 Hall 的格式類型選擇解析器 ---
        parsed_blocks = [] # 初始化為空列表
        try:
            print(f"Parsing schedule text for Hall ID: {selected_hall.id} ({selected_hall.name}), Format Type: {hall_format_type}...")

            if hall_format_type == 'format_a': # 假設 format_a 是舊格式在模型中的值
                print("  Using parser: parse_line_schedule")
                parsed_blocks = parse_line_schedule(schedule_text)
            elif hall_format_type == 'chatanghui': # 假設 chatanghui 是新格式在模型中的值
                 print("  Using parser: parse_chatanghui_schedule")
                 parsed_blocks = parse_chatanghui_schedule(schedule_text)
            # --- 在這裡可以繼續添加 elif 來支持更多格式 ---
            # elif hall_format_type == 'format_c':
            #     parsed_blocks = parse_format_c_schedule(schedule_text)
            else:
                # 如果格式類型未知或不支持
                print(f"  Error: Unknown or unsupported schedule format type '{hall_format_type}' for Hall ID {selected_hall.id}.")
                # 返回錯誤給前端，提示不支持此格式
                return JsonResponse({'error': f'館別 "{selected_hall.name}" 的班表格式類型 ({hall_format_type}) 無法識別或尚未支援解析'}, status=400)

            print(f"Parsed {len(parsed_blocks)} blocks using the selected parser.")

        except Exception as e:
             # 捕獲解析過程中可能發生的任何異常
             print(f"Error during parsing (using parser for format '{hall_format_type}'): {e}")
             traceback.print_exc()
             # 返回具體的解析錯誤信息
             return JsonResponse({'error': f'解析 "{selected_hall.name}" 班表時發生錯誤: {e}'}, status=500)
        # --- 解析器選擇邏輯結束 ---


        # ==================================
        # --- 處理預覽 (action == 'preview') ---
        # (這部分邏輯基本不變，因為依賴的是結構統一的 parsed_blocks)
        # ==================================
        if action == 'preview':
            print("--- Handling PREVIEW action ---")
            preview_data = []
            for block in parsed_blocks:
                if not block or not block.get('name'):
                    print("Skipping invalid block:", block); continue
                match_status = "not_found"; matched_animal_id = None
                matched_animal_info = None; possible_matches = []
                search_name = block['name']
                potential_aliases = {alias.strip() for alias in [search_name, block.get('alias_suggestion')] if alias} # 移除 original_name_text，避免誤匹配
                print(f"  Matching '{search_name}' (potential aliases: {potential_aliases})...")
                try:
                    # 優先級 1: 精確匹配 (名字 + 當前館別)
                    exact_match = Animal.objects.filter(name__iexact=search_name, hall=selected_hall, is_active=True).first()
                    if exact_match:
                        print(f"    Found exact match: ID {exact_match.id}")
                        match_status = "matched_exact"; matched_animal_id = exact_match.id
                        matched_animal_info = {'id': exact_match.id, 'name': exact_match.name, 'hall_name': selected_hall.name, 'fee': exact_match.fee}
                    else:
                        # 優先級 2: 名字或別名匹配 (所有活動)
                        q_objects = Q(name__iexact=search_name)
                        for alias in potential_aliases: q_objects |= Q(aliases__contains=[alias])
                        alias_query = Animal.objects.filter(q_objects, is_active=True)
                        query_count = alias_query.count(); print(f"    Alias/Name query found {query_count} match(es).")
                        if query_count == 1:
                            animal = alias_query.first(); match_status = "matched_alias_or_name"; matched_animal_id = animal.id
                            matched_animal_info = {'id': animal.id, 'name': animal.name, 'hall_name': animal.hall.name if animal.hall else '未分館', 'fee': animal.fee}
                            print(f"    Found unique alias/name match: ID {animal.id} ({animal.name})")
                        elif query_count > 1:
                            match_status = "multiple_matches"; possible_matches = list(alias_query.select_related('hall').values('id', 'name', 'hall__name'))
                            print(f"    Found multiple matches: {possible_matches}")
                        else: match_status = "not_found"; print("    No match found.")
                    # 未找到時，提供同館選項
                    if match_status == "not_found":
                        possible_matches = list(Animal.objects.filter(hall=selected_hall, is_active=True).order_by('name').values('id', 'name'))
                        print(f"    Prepared {len(possible_matches)} possible associations from the same hall.")
                except Exception as e:
                     print(f"!!! Error during matching for name '{search_name}': {e}"); traceback.print_exc(); match_status = "error"
                preview_data.append({'parsed': block, 'status': match_status, 'matched_animal_id': matched_animal_id, 'matched_animal_info': matched_animal_info, 'possible_matches': possible_matches})
            print("--- Preview data generated ---")
            return JsonResponse({'preview_data': preview_data})

        # =================================
        # --- 處理儲存 (action == 'save') ---
        # (這部分邏輯基本不變，因為依賴的是結構統一的 final_data)
        # (費用更新邏輯會自然跳過沒有 parsed_fee 的格式)
        # =================================
        elif action == 'save':
            print(">>> Received SAVE action <<<")
            try:
                final_data_str = request.POST.get('final_data')
                # 確保也傳遞了 schedule_text (雖然在事務中可能不用，但保留以防萬一)
                schedule_text_on_save = request.POST.get('schedule_text', '')
                if not final_data_str: return JsonResponse({'error': '缺少最終確認數據'}, status=400)
                try: final_data = json.loads(final_data_str); assert isinstance(final_data, list)
                except (json.JSONDecodeError, ValueError, AssertionError) as e: return JsonResponse({'error': f'前端提交的數據格式錯誤: {e}'}, status=400)

                animals_created_count = 0; animals_updated_count = 0; schedules_created_count = 0
                print("Entering transaction...")
                with transaction.atomic():
                    items_to_process_later = []; new_animal_temp_map = {}
                    # 1. 處理新增
                    print("Processing 'add_new' operations...")
                    for index, item in enumerate(final_data):
                        if item.get('operation') == 'add_new':
                            parsed_data = item.get('parsed_data', {}); new_name = parsed_data.get('name')
                            if not new_name: print("    Skipping add: No name."); continue
                            if Animal.objects.filter(name=new_name, hall=selected_hall).exists():
                                print(f"    Skipping add: '{new_name}' exists."); existing = Animal.objects.get(name=new_name, hall=selected_hall)
                                item['animal_id'] = existing.id; item['operation'] = 'use_existing'; items_to_process_later.append(item); continue
                            aliases_list = [parsed_data.get('alias_suggestion')] if parsed_data.get('alias_suggestion') else []
                            try:
                                new_animal = Animal.objects.create(
                                    name=new_name, hall=selected_hall,
                                    fee=parsed_data.get('parsed_fee'), # 對新格式會是 None
                                    height=parsed_data.get('height'), weight=parsed_data.get('weight'),
                                    cup_size=parsed_data.get('cup'), introduction=parsed_data.get('introduction'),
                                    is_active=True, order=999, aliases=aliases_list )
                                animals_created_count += 1; print(f"    Created Animal ID: {new_animal.id}")
                                item['animal_id'] = new_animal.id; item['operation'] = 'use_existing'; items_to_process_later.append(item)
                            except Exception as create_err: print(f"    !!! Error creating animal '{new_name}': {create_err}"); traceback.print_exc()
                        else: items_to_process_later.append(item)
                    # 2. 處理現有/關聯 + 費用 + 班表數據
                    print("Processing existing/associated animals, fee updates, and schedules...")
                    animals_to_update_fee = {}; final_schedule_inputs = []; valid_final_animal_ids = set()
                    for item in items_to_process_later:
                        operation = item.get('operation'); animal_id = item.get('animal_id'); final_slots = item.get('final_slots')
                        update_fee_flag = item.get('update_fee', False); parsed_data = item.get('parsed_data', {})
                        if operation == 'ignore': continue
                        if operation == 'use_existing' or operation == 'associate':
                            if not animal_id: continue
                            try:
                                animal_id = int(animal_id)
                                parsed_fee = parsed_data.get('parsed_fee') # 新格式為 None
                                if update_fee_flag and parsed_fee is not None: # 因此此條件不滿足
                                    animals_to_update_fee[animal_id] = parsed_fee; print(f"  Marked ID {animal_id} for fee update to {parsed_fee}")
                                final_schedule_inputs.append({'animal_id': animal_id, 'slots': final_slots}); valid_final_animal_ids.add(animal_id)
                            except (ValueError, TypeError): print(f"Warning: Invalid Animal ID '{animal_id}'.")
                        else: print(f"Warning: Unknown operation '{operation}'.")

                    # --- *** 修正後的費用更新邏輯 *** ---
                    updated_fee_count_actual = 0
                    if animals_to_update_fee:
                        print(f"Updating fees for {len(animals_to_update_fee)} animals...")
                        for animal_id, new_fee in animals_to_update_fee.items():
                            try:
                                current_animal = Animal.objects.get(id=animal_id)
                                if current_animal.fee != new_fee:
                                    rows_affected = Animal.objects.filter(id=animal_id).update(fee=new_fee)
                                    updated_fee_count_actual += rows_affected # 累加受影響的行數
                                    if rows_affected > 0:
                                        print(f"  Successfully updated fee for Animal ID {animal_id}")
                                else:
                                     print(f"  Skipping fee update for ID {animal_id} (fee already matches)")
                            except Animal.DoesNotExist:
                                 print(f"  Warning: Animal ID {animal_id} not found during fee update.")
                            except Exception as fee_update_err:
                                 print(f"  !!! Error updating fee for ID {animal_id}: {fee_update_err}")
                        animals_updated_count = updated_fee_count_actual # 將最終計數賦值給外層變數
                    # --- *** 費用更新邏輯結束 *** ---

                    # 3. 清除舊班表
                    print(f"Deleting old schedules for hall ID {selected_hall.id}...")
                    try: deleted_count, _ = DailySchedule.objects.filter(hall=selected_hall).delete(); print(f"  Deleted {deleted_count} old records.")
                    except Exception as del_err: print(f"  !!! Error deleting: {del_err}"); raise
                    # 4. 批量創建新班表
                    print("Creating new schedules...")
                    schedule_objects = []; final_valid_set = set(Animal.objects.filter(id__in=valid_final_animal_ids, is_active=True).values_list('id', flat=True))
                    for info in final_schedule_inputs:
                        if info['animal_id'] in final_valid_set:
                            schedule_objects.append(DailySchedule(hall=selected_hall, animal_id=info['animal_id'], time_slots=info['slots']))
                        else: print(f"  Skipping schedule: Animal ID {info['animal_id']} not found/inactive.")
                    if schedule_objects:
                        try: DailySchedule.objects.bulk_create(schedule_objects); schedules_created_count = len(schedule_objects); print(f"  Created {schedules_created_count} new records.")
                        except Exception as bulk_err: print(f"  !!! Error bulk creating: {bulk_err}"); raise
                print("Transaction committed.")
                return JsonResponse({'success': True,'message': f'班表已儲存。新增美容師: {animals_created_count}, 更新費用: {animals_updated_count}, 更新班表: {schedules_created_count}。'})
            except Exception as e: print(f"!!! Error during SAVE: {e} !!!"); traceback.print_exc(); return JsonResponse({'error': '儲存班表時發生內部錯誤。'}, status=500)
        else: return JsonResponse({'error': '無效的操作請求'}, status=400)
    else: return HttpResponseBadRequest("不支持的請求方法")