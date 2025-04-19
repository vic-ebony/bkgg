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
from myapp.models import Hall, Animal # 從 myapp 導入模型 (假設路徑正確)
from .models import DailySchedule       # 從當前 app 導入
# --- *** 導入所有需要的解析器 (包括新增的 lezuan) *** ---
from .utils import (
    parse_line_schedule,
    parse_chatanghui_schedule,
    parse_xinyuan_schedule,
    parse_shouzhongqing_schedule,
    parse_pokemon_schedule,
    parse_aibao_schedule,
    parse_hanxiang_schedule,
    parse_pandora_schedule,
    parse_wangfei_schedule,
    parse_lezuan_schedule # <--- 導入樂鑽解析函數
)

logger = logging.getLogger(__name__) # 添加 logger

@staff_member_required # 確保只有 staff 或 superuser 可以訪問
def parse_schedule_view(request):
    """
    處理班表解析頁面的 GET 和 POST 請求。
    GET: 顯示頁面。
    POST: 根據 action 參數執行預覽或儲存操作。
    (預覽邏輯修改為只做精確匹配，不提供關聯選項)
    """
    if request.method == 'GET':
        # GET 請求：顯示頁面和館別下拉選單
        try:
            active_halls = Hall.objects.filter(is_active=True).order_by('order', 'name')
            context = {'active_halls': active_halls}
            return render(request, 'schedule_parser/parse_schedule.html', context)
        except Exception as e:
            print(f"Error rendering parse schedule page (GET): {e}")
            logger.error("Error rendering parse schedule page (GET)", exc_info=True)
            traceback.print_exc()
            return HttpResponseServerError("無法加載班表解析頁面，請稍後再試或聯繫管理員。")

    elif request.method == 'POST':
        action = request.POST.get('action') # 'preview' 或 'save'
        hall_id = request.POST.get('hall_id')
        schedule_text = request.POST.get('schedule_text')

        # --- 基本輸入驗證 ---
        if not hall_id: return JsonResponse({'error': '請選擇館別'}, status=400)
        if not schedule_text: return JsonResponse({'error': '請貼上文字班表'}, status=400)
        if action not in ['preview', 'save']: return JsonResponse({'error': '無效的操作請求'}, status=400)

        # --- 驗證所選館別 ---
        try:
            selected_hall = Hall.objects.get(id=hall_id, is_active=True)
            hall_format_type = selected_hall.schedule_format_type
        except Hall.DoesNotExist: return JsonResponse({'error': '選擇的館別無效或未啟用'}, status=400)
        except (ValueError, TypeError): return JsonResponse({'error': '館別 ID 格式錯誤'}, status=400)
        except AttributeError:
             logger.error("Hall model missing 'schedule_format_type' attribute.")
             return JsonResponse({'error': '伺服器配置錯誤：缺少館別格式類型信息'}, status=500)
        except Exception as e:
             print(f"Error getting Hall object: {e}")
             logger.error(f"Error getting Hall object for ID {hall_id}", exc_info=True)
             traceback.print_exc()
             return JsonResponse({'error': '獲取館別信息時出錯'}, status=500)

        # --- 根據 Hall 的格式類型選擇解析器 ---
        parsed_blocks = []
        try:
            print(f"Parsing schedule text for Hall ID: {selected_hall.id} ({selected_hall.name}), Format Type: {hall_format_type}...")
            logger.info(f"Parsing schedule text for Hall ID: {selected_hall.id} ({selected_hall.name}), Format Type: {hall_format_type}...")

            parser_function = None
            # (選擇解析器的邏輯不變)
            if hall_format_type == 'format_a': parser_function = parse_line_schedule
            elif hall_format_type == 'chatanghui': parser_function = parse_chatanghui_schedule
            elif hall_format_type == 'xinyuan': parser_function = parse_xinyuan_schedule
            elif hall_format_type == 'shouzhongqing': parser_function = parse_shouzhongqing_schedule
            elif hall_format_type == 'pokemon': parser_function = parse_pokemon_schedule
            elif hall_format_type == 'aibao': parser_function = parse_aibao_schedule
            elif hall_format_type == 'hanxiang': parser_function = parse_hanxiang_schedule
            elif hall_format_type == 'pandora': parser_function = parse_pandora_schedule
            elif hall_format_type == 'wangfei': parser_function = parse_wangfei_schedule
            elif hall_format_type == 'lezuan': parser_function = parse_lezuan_schedule

            if parser_function:
                print(f"  Using parser: {parser_function.__name__}")
                logger.debug(f"Using parser: {parser_function.__name__}")
                parsed_blocks = parser_function(schedule_text)
            else:
                logger.error(f"Unknown schedule format type '{hall_format_type}' for Hall ID {selected_hall.id}")
                return JsonResponse({'error': f'館別 "{selected_hall.name}" 的班表格式類型 ({hall_format_type}) 無法識別或尚未支援解析'}, status=400)

            print(f"Parsed {len(parsed_blocks)} blocks.")
            logger.info(f"Parsed {len(parsed_blocks)} blocks using parser for format '{hall_format_type}'.")

        except Exception as e:
             print(f"Error during parsing: {e}")
             logger.error(f"Error during parsing for format '{hall_format_type}'", exc_info=True)
             traceback.print_exc()
             return JsonResponse({'error': f'解析 "{selected_hall.name}" 班表時發生錯誤: {e}'}, status=500)
        # --- 解析器選擇邏輯結束 ---

        # ==================================
        # --- 處理預覽 (action == 'preview') ---
        # --- *** 修改匹配邏輯：只做精確匹配，移除所有關聯 *** ---
        # ==================================
        if action == 'preview':
            print("--- Handling PREVIEW action (Exact Match Only) ---")
            logger.info("Handling PREVIEW action (Exact Match Only)")
            preview_data = []
            for block in parsed_blocks:
                if not block or not block.get('name'):
                    print("Skipping invalid block:", block)
                    logger.warning(f"Skipping invalid parsed block: {block}")
                    continue

                match_status = "not_found" # 預設未找到
                matched_animal_id = None
                matched_animal_info = None
                possible_matches = [] # *** 不再需要提供任何建議 ***

                search_name = block['name']

                print(f"  Matching '{search_name}' strictly (exact name) within Hall '{selected_hall.name}'...")
                logger.debug(f"Matching '{search_name}' strictly (exact name) within Hall '{selected_hall.name}'")

                try:
                    # 1. 精確匹配 (名字 + 所選館別) - 這是唯一會產生匹配的條件
                    exact_match = Animal.objects.filter(
                        name__iexact=search_name, # 忽略大小寫
                        hall=selected_hall,       # 關鍵：限制在所選館別
                        is_active=True
                    ).first()

                    if exact_match:
                        print(f"    Found exact match: ID {exact_match.id}")
                        logger.debug(f"Found exact match within hall: ID {exact_match.id} for name '{search_name}'")
                        match_status = "matched_exact"
                        matched_animal_id = exact_match.id
                        matched_animal_info = {
                            'id': exact_match.id,
                            'name': exact_match.name,
                            'hall_name': selected_hall.name,
                            'fee': exact_match.fee
                        }
                    else:
                        # 如果精確匹配失敗，直接標記為 not_found
                        match_status = "not_found"
                        print("    No exact match found within the selected hall.")
                        logger.debug(f"No exact match found for name '{search_name}' within hall '{selected_hall.name}'")
                        # *** 不再進行別名查詢，也不提供同館其他美容師作為關聯選項 ***
                        possible_matches = [] # 確保為空

                    # --- *** 所有別名匹配、多重匹配的邏輯已完全移除 *** ---

                except Exception as e:
                     print(f"!!! Error during matching for name '{search_name}': {e}")
                     logger.error(f"Error matching name '{search_name}'", exc_info=True)
                     traceback.print_exc()
                     match_status = "error" # 標記為錯誤狀態

                # 添加到預覽數據列表
                preview_data.append({
                    'parsed': block,
                    'status': match_status,          # 只會是 matched_exact, not_found, 或 error
                    'matched_animal_id': matched_animal_id,
                    'matched_animal_info': matched_animal_info,
                    'possible_matches': possible_matches # 永遠是空列表
                })

            print("--- Preview data generated (Exact Match Only) ---")
            logger.info("Preview data generated successfully (Exact Match Only).")
            return JsonResponse({'preview_data': preview_data})

        # =================================
        # --- 處理儲存 (action == 'save') ---
        # (儲存邏輯基本不變，但 'associate' 操作實際上不會再從前端傳來)
        # =================================
        elif action == 'save':
            print(">>> Received SAVE action <<<")
            logger.info("Received SAVE action")
            try:
                final_data_str = request.POST.get('final_data')
                schedule_text_on_save = request.POST.get('schedule_text', '')

                if not final_data_str:
                    logger.warning("Save action missing 'final_data'.")
                    return JsonResponse({'error': '缺少最終確認數據'}, status=400)
                try:
                    final_data = json.loads(final_data_str)
                    assert isinstance(final_data, list)
                except (json.JSONDecodeError, ValueError, AssertionError) as e:
                    logger.error(f"Invalid 'final_data' format: {e}. Data: {final_data_str[:200]}...")
                    return JsonResponse({'error': f'前端提交的數據格式錯誤: {e}'}, status=400)

                animals_created_count = 0
                schedules_created_count = 0
                updated_fee_count_actual = 0
                # 'updated_alias_count_actual' 由於 'associate' 操作已移除，理論上恆為 0
                updated_alias_count_actual = 0

                print("Entering transaction...")
                logger.info("Entering transaction for saving schedule.")
                with transaction.atomic():
                    items_to_process_later = []
                    new_animal_temp_map = {}

                    # --- 第一步: 處理需要新增的美容師 ('add_new') ---
                    print("Processing 'add_new' operations...")
                    logger.debug("Processing 'add_new' operations.")
                    for index, item in enumerate(final_data):
                        if item.get('operation') == 'add_new':
                            parsed_data = item.get('parsed_data', {})
                            new_name = parsed_data.get('name')

                            if not new_name:
                                logger.warning(f"Skipping add_new at index {index}: No name.")
                                continue

                            # 嚴格檢查同名+同館是否存在
                            if Animal.objects.filter(name=new_name, hall=selected_hall, is_active=True).exists():
                                print(f"    Skipping add: '{new_name}' already exists in hall '{selected_hall.name}'. Attempting to use existing.")
                                logger.warning(f"Skipping add_new: '{new_name}' already exists in hall '{selected_hall.name}'. Will try to use existing.")
                                try:
                                    existing = Animal.objects.get(name=new_name, hall=selected_hall, is_active=True)
                                    item['animal_id'] = existing.id
                                    item['operation'] = 'use_existing' # 改為使用現有
                                    items_to_process_later.append(item)
                                except Animal.DoesNotExist:
                                     logger.error(f"Inconsistency: '{new_name}' exists check passed but get() failed.")
                                     continue
                                continue

                            # 創建新記錄 (alias_suggestion 仍可利用)
                            aliases_list = []
                            alias_sugg = parsed_data.get('alias_suggestion')
                            if alias_sugg and isinstance(alias_sugg, str):
                                aliases_list.append(alias_sugg)

                            try:
                                new_animal = Animal.objects.create(
                                    name=new_name, hall=selected_hall,
                                    fee=parsed_data.get('parsed_fee'), height=parsed_data.get('height'),
                                    weight=parsed_data.get('weight'), cup_size=parsed_data.get('cup'),
                                    introduction=parsed_data.get('introduction'),
                                    is_active=True, order=999, aliases=aliases_list
                                )
                                animals_created_count += 1
                                print(f"    Created Animal ID: {new_animal.id} for name '{new_name}'")
                                logger.info(f"Created Animal ID: {new_animal.id} for name '{new_name}' in hall '{selected_hall.name}'")
                                item['animal_id'] = new_animal.id
                                item['operation'] = 'use_existing' # 新增後視為現有，以便後續處理
                                items_to_process_later.append(item)
                            except Exception as create_err:
                                print(f"    !!! Error creating animal '{new_name}': {create_err}")
                                logger.error(f"Error creating animal '{new_name}' in hall '{selected_hall.name}'", exc_info=True)
                                traceback.print_exc()
                                continue
                        else:
                            items_to_process_later.append(item)

                    # --- 第二步: 處理現有關聯/選擇的美容師，更新費用，整理班表數據 ---
                    # (注意： 'associate' 操作理論上不會出現了)
                    print("Processing existing/associated animals, fee updates, and schedules...")
                    logger.debug("Processing existing/associated animals, fee updates, and schedules.")
                    animals_to_update_fee = {}
                    # animals_to_update_aliases 字典幾乎不會被填充，因為 'associate' 沒了
                    animals_to_update_aliases = {}
                    final_schedule_inputs = []
                    valid_final_animal_ids = set()

                    for item in items_to_process_later:
                        operation = item.get('operation')
                        animal_id = item.get('animal_id')
                        final_slots = item.get('final_slots')
                        update_fee_flag = item.get('update_fee', False)
                        parsed_data = item.get('parsed_data', {})

                        if operation == 'ignore':
                            logger.debug(f"Ignoring item for Animal ID {animal_id}.")
                            continue

                        # 只處理 'use_existing' (來自精確匹配或剛新增的)
                        if operation == 'use_existing':
                            if not animal_id:
                                logger.warning(f"Skipping item with operation 'use_existing' due to missing animal_id: {item}")
                                continue
                            try:
                                animal_id = int(animal_id)
                                # 檢查更新費用
                                parsed_fee = parsed_data.get('parsed_fee')
                                if update_fee_flag and parsed_fee is not None:
                                     animals_to_update_fee[animal_id] = parsed_fee
                                     logger.debug(f"Marked Animal ID {animal_id} for fee update to {parsed_fee}")

                                # *** 'associate' 的別名處理邏輯實際上不會被觸發 ***
                                # if operation == 'associate': ... (這段可以安全移除或保留但也沒影響)

                                final_schedule_inputs.append({
                                    'animal_id': animal_id,
                                    'slots': final_slots if final_slots is not None else ""
                                })
                                valid_final_animal_ids.add(animal_id)
                            except (ValueError, TypeError) as ve:
                                logger.warning(f"Invalid Animal ID '{animal_id}' in item: {item}. Error: {ve}")
                                continue
                        # elif operation == 'associate': # 理論上不會有這個操作了
                        #     logger.warning(f"Received unexpected 'associate' operation: {item}")
                        #     continue # 忽略意外的操作
                        else:
                             logger.warning(f"Unknown or irrelevant operation '{operation}' in item: {item}")
                             continue

                    # --- 批量更新費用 --- (別名更新邏輯幾乎無用武之地)
                    animals_to_update = {animal.id: animal for animal in Animal.objects.filter(id__in=list(valid_final_animal_ids))}
                    logger.debug(f"Found {len(animals_to_update)} animals for potential fee update.")

                    for animal_id, animal_instance in animals_to_update.items():
                        needs_save = False; update_fields = []
                        # 更新費用
                        new_fee = animals_to_update_fee.get(animal_id)
                        if new_fee is not None and animal_instance.fee != new_fee:
                             animal_instance.fee = new_fee; needs_save = True; update_fields.append('fee')
                             updated_fee_count_actual += 1
                             logger.debug(f"Updating fee for Animal ID {animal_id} to {new_fee}")

                        # # 更新別名 (幾乎不會執行)
                        # aliases_to_add = animals_to_update_aliases.get(animal_id)
                        # if aliases_to_add: ... (這段邏輯可以保留或移除)

                        if needs_save:
                            try:
                                animal_instance.save(update_fields=list(set(update_fields)))
                            except Exception as save_err:
                                logger.error(f"Error saving updates for Animal ID {animal_id}", exc_info=True)

                    # --- 第三步: 清除舊班表 ---
                    print(f"Deleting old schedules for hall ID {selected_hall.id}...")
                    logger.info(f"Deleting old schedules for hall ID {selected_hall.id} ({selected_hall.name})...")
                    try:
                        deleted_count, _ = DailySchedule.objects.filter(hall=selected_hall).delete()
                        print(f"  Deleted {deleted_count} old records.")
                        logger.info(f"Deleted {deleted_count} old DailySchedule records for hall '{selected_hall.name}'.")
                    except Exception as del_err:
                        logger.error(f"Error deleting old schedules for Hall {selected_hall.id}", exc_info=True)
                        raise

                    # --- 第四步: 批量創建新班表 ---
                    print("Creating new schedules...")
                    logger.info("Creating new DailySchedule records...")
                    schedule_objects = []
                    final_valid_set = set(animals_to_update.keys()) # 使用實際獲取到的動物ID
                    for info in final_schedule_inputs:
                        if info['animal_id'] in final_valid_set:
                             schedule_objects.append(
                                 DailySchedule(
                                     hall=selected_hall, animal_id=info['animal_id'],
                                     time_slots=info['slots'] if info['slots'] is not None else ""
                                 )
                             )
                        else:
                             logger.warning(f"Skipping schedule creation for Animal ID {info['animal_id']} as it was not in the final valid set.")

                    if schedule_objects:
                        try:
                            DailySchedule.objects.bulk_create(schedule_objects)
                            schedules_created_count = len(schedule_objects)
                            print(f"  Successfully created {schedules_created_count} new schedule records.")
                            logger.info(f"Bulk created {schedules_created_count} new DailySchedule records for hall '{selected_hall.name}'.")
                        except Exception as bulk_err:
                            logger.error("Error bulk creating DailySchedule records", exc_info=True)
                            raise

                # --- 事務成功提交 ---
                print("Transaction committed successfully.")
                logger.info("Schedule save transaction committed successfully.")
                # 更新返回消息，移除別名更新計數
                return JsonResponse({
                    'success': True,
                    'message': f'班表已儲存。新增美容師: {animals_created_count}, 更新費用: {updated_fee_count_actual}, 總計更新班表: {schedules_created_count} 筆。'
                })

            except Exception as e:
                print(f"!!! Error during SAVE action processing: {e} !!!")
                logger.critical("Critical error during SAVE action processing", exc_info=True)
                traceback.print_exc()
                return JsonResponse({'error': '儲存班表時發生內部錯誤，請檢查伺服器日誌或聯繫管理員。'}, status=500)

        else:
            logger.warning(f"Invalid action '{action}' received in POST request.")
            return JsonResponse({'error': '無效的操作請求'}, status=400)

    else:
        logger.warning(f"Unsupported HTTP method '{request.method}' received for parse_schedule_view.")
        return HttpResponseBadRequest("不支持的請求方法")

# --- views.py 文件結束 ---