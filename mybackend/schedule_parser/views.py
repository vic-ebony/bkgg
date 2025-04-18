# D:\bkgg\mybackend\schedule_parser\views.py
import json
import traceback # 用於打印詳細錯誤
import logging   # 添加 logging
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseServerError
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import Q
from myapp.models import Hall, Animal # 從 myapp 導入模型
from .models import DailySchedule       # 從當前 app 導入
# --- *** 導入所有需要的解析器 *** ---
from .utils import parse_line_schedule, parse_chatanghui_schedule, parse_xinyuan_schedule # <--- 導入三個解析函數

logger = logging.getLogger(__name__) # 添加 logger

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
            logger.error("Error rendering parse schedule page (GET)", exc_info=True) # 使用 logger
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
            hall_format_type = selected_hall.schedule_format_type
        except Hall.DoesNotExist:
            return JsonResponse({'error': '選擇的館別無效或未啟用'}, status=400)
        except (ValueError, TypeError):
             return JsonResponse({'error': '館別 ID 格式錯誤'}, status=400)
        except AttributeError:
             logger.error("Hall model missing 'schedule_format_type' attribute.")
             return JsonResponse({'error': '伺服器配置錯誤：缺少館別格式類型信息'}, status=500)
        except Exception as e:
             print(f"Error getting Hall object: {e}")
             logger.error(f"Error getting Hall object for ID {hall_id}", exc_info=True)
             traceback.print_exc()
             return JsonResponse({'error': '獲取館別信息時出錯'}, status=500)


        # --- *** 修改：根據 Hall 的格式類型選擇解析器 *** ---
        parsed_blocks = [] # 初始化為空列表
        try:
            print(f"Parsing schedule text for Hall ID: {selected_hall.id} ({selected_hall.name}), Format Type: {hall_format_type}...")

            if hall_format_type == 'format_a': # 假設 format_a 是舊格式
                print("  Using parser: parse_line_schedule")
                parsed_blocks = parse_line_schedule(schedule_text)
            elif hall_format_type == 'chatanghui': # 假設 chatanghui 是茶湯會格式
                 print("  Using parser: parse_chatanghui_schedule")
                 parsed_blocks = parse_chatanghui_schedule(schedule_text)
            # --- *** 新增 elif 處理芯苑館格式 *** ---
            elif hall_format_type == 'xinyuan': # 假設 xinyuan 是芯苑館格式
                 print("  Using parser: parse_xinyuan_schedule")
                 parsed_blocks = parse_xinyuan_schedule(schedule_text)
            # --- *** ---
            # --- 在這裡可以繼續添加 elif 來支持更多格式 ---
            # elif hall_format_type == 'format_d':
            #     parsed_blocks = parse_format_d_schedule(schedule_text)
            else:
                # 如果格式類型未知或不支持
                print(f"  Error: Unknown or unsupported schedule format type '{hall_format_type}' for Hall ID {selected_hall.id}.")
                logger.error(f"Unknown schedule format type '{hall_format_type}' for Hall ID {selected_hall.id}")
                return JsonResponse({'error': f'館別 "{selected_hall.name}" 的班表格式類型 ({hall_format_type}) 無法識別或尚未支援解析'}, status=400)

            print(f"Parsed {len(parsed_blocks)} blocks using the selected parser.")

        except Exception as e:
             # 捕獲解析過程中可能發生的任何異常
             print(f"Error during parsing (using parser for format '{hall_format_type}'): {e}")
             logger.error(f"Error during parsing for format '{hall_format_type}'", exc_info=True)
             traceback.print_exc()
             return JsonResponse({'error': f'解析 "{selected_hall.name}" 班表時發生錯誤: {e}'}, status=500)
        # --- 解析器選擇邏輯結束 ---


        # ==================================
        # --- 處理預覽 (action == 'preview') ---
        # (這部分邏輯基本不變)
        # ==================================
        if action == 'preview':
            print("--- Handling PREVIEW action ---")
            preview_data = []
            for block in parsed_blocks:
                if not block or not block.get('name'): print("Skipping invalid block:", block); continue
                match_status = "not_found"; matched_animal_id = None
                matched_animal_info = None; possible_matches = []
                search_name = block['name']
                potential_aliases = {alias.strip() for alias in [search_name, block.get('alias_suggestion')] if alias}
                print(f"  Matching '{search_name}' (potential aliases: {potential_aliases})...")
                try:
                    exact_match = Animal.objects.filter(name__iexact=search_name, hall=selected_hall, is_active=True).first()
                    if exact_match:
                        print(f"    Found exact match: ID {exact_match.id}")
                        match_status = "matched_exact"; matched_animal_id = exact_match.id
                        matched_animal_info = {'id': exact_match.id, 'name': exact_match.name, 'hall_name': selected_hall.name, 'fee': exact_match.fee}
                    else:
                        q_objects = Q(name__iexact=search_name)
                        for alias in potential_aliases: q_objects |= Q(aliases__contains=[alias]) # 假設 aliases 是 ArrayField
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
                    if match_status == "not_found":
                        possible_matches = list(Animal.objects.filter(hall=selected_hall, is_active=True).order_by('name').values('id', 'name'))
                        print(f"    Prepared {len(possible_matches)} possible associations from the same hall.")
                except Exception as e:
                     print(f"!!! Error during matching for name '{search_name}': {e}"); traceback.print_exc()
                     logger.error(f"Error matching name '{search_name}'", exc_info=True)
                     match_status = "error"
                preview_data.append({'parsed': block, 'status': match_status, 'matched_animal_id': matched_animal_id, 'matched_animal_info': matched_animal_info, 'possible_matches': possible_matches})
            print("--- Preview data generated ---")
            return JsonResponse({'preview_data': preview_data})


        # =================================
        # --- 處理儲存 (action == 'save') ---
        # (這部分邏輯基本不變)
        # =================================
        elif action == 'save':
            print(">>> Received SAVE action <<<")
            try:
                final_data_str = request.POST.get('final_data')
                schedule_text_on_save = request.POST.get('schedule_text', '') # 獲取 schedule_text
                if not final_data_str: return JsonResponse({'error': '缺少最終確認數據'}, status=400)
                try: final_data = json.loads(final_data_str); assert isinstance(final_data, list)
                except (json.JSONDecodeError, ValueError, AssertionError) as e: return JsonResponse({'error': f'前端提交的數據格式錯誤: {e}'}, status=400)

                animals_created_count = 0; animals_updated_count = 0; schedules_created_count = 0
                updated_alias_count_actual = 0 # 初始化別名更新計數器
                updated_fee_count_actual = 0   # 初始化費用更新計數器

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
                                    fee=parsed_data.get('parsed_fee'), height=parsed_data.get('height'),
                                    weight=parsed_data.get('weight'), cup_size=parsed_data.get('cup'),
                                    introduction=parsed_data.get('introduction'), is_active=True,
                                    order=999, aliases=aliases_list )
                                animals_created_count += 1; print(f"    Created Animal ID: {new_animal.id}")
                                item['animal_id'] = new_animal.id; item['operation'] = 'use_existing'; items_to_process_later.append(item)
                            except Exception as create_err: print(f"    !!! Error creating animal '{new_name}': {create_err}"); traceback.print_exc(); logger.error(f"Error creating animal '{new_name}'", exc_info=True)
                        else: items_to_process_later.append(item)

                    # 2. 處理現有/關聯 Animal 的更新和班表數據整理
                    print("Processing existing/associated animals, fee/alias updates, and schedules...")
                    animals_to_update_fee = {}; animals_to_update_aliases = {}; final_schedule_inputs = []; valid_final_animal_ids = set()
                    for item in items_to_process_later:
                        operation = item.get('operation'); animal_id = item.get('animal_id'); final_slots = item.get('final_slots')
                        update_fee_flag = item.get('update_fee', False); parsed_data = item.get('parsed_data', {})
                        if operation == 'ignore': continue
                        if operation == 'use_existing' or operation == 'associate':
                            if not animal_id: continue
                            try:
                                animal_id = int(animal_id)
                                parsed_fee = parsed_data.get('parsed_fee')
                                if update_fee_flag and parsed_fee is not None:
                                    animals_to_update_fee[animal_id] = parsed_fee; print(f"  Marked ID {animal_id} for fee update to {parsed_fee}")
                                if operation == 'associate': # 只在關聯時添加別名
                                    parsed_name = parsed_data.get('name'); parsed_alias = parsed_data.get('alias_suggestion')
                                    aliases_to_add = [a for a in [parsed_name, parsed_alias] if a]
                                    if aliases_to_add:
                                        if animal_id not in animals_to_update_aliases: animals_to_update_aliases[animal_id] = []
                                        animals_to_update_aliases[animal_id].extend(aliases_to_add); print(f"  Marked ID {animal_id} to add aliases: {aliases_to_add}")
                                final_schedule_inputs.append({'animal_id': animal_id, 'slots': final_slots}); valid_final_animal_ids.add(animal_id)
                            except (ValueError, TypeError): print(f"Warning: Invalid Animal ID '{animal_id}'.")
                        else: print(f"Warning: Unknown operation '{operation}'.")

                    # 批量更新費用和別名
                    animal_ids_to_process = valid_final_animal_ids
                    animals_to_update = {animal.id: animal for animal in Animal.objects.filter(id__in=animal_ids_to_process)}
                    print(f"Found {len(animals_to_update)} existing animals to potentially update.")
                    for animal_id in animal_ids_to_process:
                        animal_instance = animals_to_update.get(animal_id)
                        if not animal_instance: continue
                        needs_save = False; update_fields = []
                        # 更新費用
                        new_fee = animals_to_update_fee.get(animal_id)
                        if new_fee is not None and animal_instance.fee != new_fee:
                            animal_instance.fee = new_fee; needs_save = True; update_fields.append('fee'); updated_fee_count_actual += 1; print(f"  Updating fee for ID {animal_id}")
                        # 更新別名
                        aliases_to_add = animals_to_update_aliases.get(animal_id)
                        if aliases_to_add:
                            if not isinstance(animal_instance.aliases, list): animal_instance.aliases = []
                            aliases_changed = False; current_aliases_lower = {a.lower() for a in animal_instance.aliases if isinstance(a, str)}; main_name_lower = animal_instance.name.lower()
                            for alias in set(aliases_to_add):
                                alias_lower = alias.strip().lower()
                                if alias_lower and alias_lower != main_name_lower and alias_lower not in current_aliases_lower:
                                    animal_instance.aliases.append(alias.strip()); aliases_changed = True; print(f"  Adding alias '{alias.strip()}' to ID {animal_id}")
                            if aliases_changed: needs_save = True; update_fields.append('aliases'); updated_alias_count_actual += 1
                        # 保存更改
                        if needs_save:
                            try: animal_instance.save(update_fields=update_fields)
                            except Exception as save_err: print(f"  !!! Error saving updates for ID {animal_id}: {save_err}"); logger.error(f"Error saving Animal ID {animal_id}", exc_info=True)
                    animals_updated_count = updated_fee_count_actual # 只計數費用更新？或者可以分開計數

                    # 3. 清除舊班表
                    print(f"Deleting old schedules for hall ID {selected_hall.id}...")
                    try: deleted_count, _ = DailySchedule.objects.filter(hall=selected_hall).delete(); print(f"  Deleted {deleted_count} old records.")
                    except Exception as del_err: print(f"  !!! Error deleting: {del_err}"); logger.error(f"Error deleting old schedules for Hall {selected_hall.id}", exc_info=True); raise
                    # 4. 批量創建新班表
                    print("Creating new schedules...")
                    schedule_objects = []; final_valid_set = set(animals_to_update.keys()) # 使用已確認存在的動物ID
                    for info in final_schedule_inputs:
                        if info['animal_id'] in final_valid_set:
                            schedule_objects.append(DailySchedule(hall=selected_hall, animal_id=info['animal_id'], time_slots=info['slots']))
                        else: print(f"  Skipping schedule: Animal ID {info['animal_id']} not in valid set.")
                    if schedule_objects:
                        try: DailySchedule.objects.bulk_create(schedule_objects); schedules_created_count = len(schedule_objects); print(f"  Created {schedules_created_count} new records.")
                        except Exception as bulk_err: print(f"  !!! Error bulk creating: {bulk_err}"); logger.error("Error bulk creating schedules", exc_info=True); raise

                print("Transaction committed successfully.")
                return JsonResponse({
                    'success': True,
                    'message': f'班表已儲存。新增美容師: {animals_created_count}, 更新費用: {updated_fee_count_actual}, 更新別名: {updated_alias_count_actual}, 更新班表: {schedules_created_count}。'
                })

            except Exception as e:
                print(f"!!! Error during SAVE action processing: {e} !!!"); traceback.print_exc()
                logger.error("Error processing SAVE action", exc_info=True)
                return JsonResponse({'error': '儲存班表時發生內部錯誤，請檢查伺服器日誌。'}, status=500)

        else: # 無效的 action
            print(f"Error: Invalid action '{action}' received.")
            return JsonResponse({'error': '無效的操作請求'}, status=400)

    else: # 非 GET 或 POST 請求
        print(f"Error: Unsupported HTTP method '{request.method}'.")
        return HttpResponseBadRequest("不支持的請求方法")

# --- views.py 文件結束 ---