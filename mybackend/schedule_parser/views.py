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
    """
    if request.method == 'GET':
        # GET 請求：顯示頁面和館別下拉選單
        try:
            # 只獲取 is_active=True 的館別
            active_halls = Hall.objects.filter(is_active=True).order_by('order', 'name')
            context = {'active_halls': active_halls}
            return render(request, 'schedule_parser/parse_schedule.html', context)
        except Exception as e:
            # 更詳細的錯誤記錄
            print(f"Error rendering parse schedule page (GET): {e}")
            logger.error("Error rendering parse schedule page (GET)", exc_info=True)
            traceback.print_exc() # 打印 traceback 到控制台
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
        # 驗證 action 是否有效
        if action not in ['preview', 'save']:
             return JsonResponse({'error': '無效的操作請求'}, status=400)

        # --- 驗證所選館別 ---
        try:
            # 確保獲取的是 is_active=True 的館別
            selected_hall = Hall.objects.get(id=hall_id, is_active=True)
            # --- *** 獲取館別的班表格式類型 *** ---
            hall_format_type = selected_hall.schedule_format_type
        except Hall.DoesNotExist:
            # 如果找不到對應 ID 或館別 inactive
            return JsonResponse({'error': '選擇的館別無效或未啟用'}, status=400)
        except (ValueError, TypeError):
             # 如果 hall_id 不是有效的數字格式
             return JsonResponse({'error': '館別 ID 格式錯誤'}, status=400)
        except AttributeError:
             # 如果 Hall 模型沒有 schedule_format_type 屬性
             logger.error("Hall model missing 'schedule_format_type' attribute.")
             return JsonResponse({'error': '伺服器配置錯誤：缺少館別格式類型信息'}, status=500)
        except Exception as e:
             # 捕獲其他可能的錯誤
             print(f"Error getting Hall object: {e}")
             logger.error(f"Error getting Hall object for ID {hall_id}", exc_info=True)
             traceback.print_exc()
             return JsonResponse({'error': '獲取館別信息時出錯'}, status=500)


        # --- *** 修改：根據 Hall 的格式類型選擇解析器 (加入 lezuan) *** ---
        parsed_blocks = [] # 初始化為空列表
        try:
            print(f"Parsing schedule text for Hall ID: {selected_hall.id} ({selected_hall.name}), Format Type: {hall_format_type}...")
            logger.info(f"Parsing schedule text for Hall ID: {selected_hall.id} ({selected_hall.name}), Format Type: {hall_format_type}...")

            if hall_format_type == 'format_a':
                print("  Using parser: parse_line_schedule")
                logger.debug("Using parser: parse_line_schedule")
                parsed_blocks = parse_line_schedule(schedule_text)
            elif hall_format_type == 'chatanghui':
                 print("  Using parser: parse_chatanghui_schedule")
                 logger.debug("Using parser: parse_chatanghui_schedule")
                 parsed_blocks = parse_chatanghui_schedule(schedule_text)
            elif hall_format_type == 'xinyuan':
                 print("  Using parser: parse_xinyuan_schedule")
                 logger.debug("Using parser: parse_xinyuan_schedule")
                 parsed_blocks = parse_xinyuan_schedule(schedule_text)
            elif hall_format_type == 'shouzhongqing':
                 print("  Using parser: parse_shouzhongqing_schedule")
                 logger.debug("Using parser: parse_shouzhongqing_schedule")
                 parsed_blocks = parse_shouzhongqing_schedule(schedule_text)
            elif hall_format_type == 'pokemon':
                 print("  Using parser: parse_pokemon_schedule")
                 logger.debug("Using parser: parse_pokemon_schedule")
                 parsed_blocks = parse_pokemon_schedule(schedule_text)
            elif hall_format_type == 'aibao':
                 print("  Using parser: parse_aibao_schedule")
                 logger.debug("Using parser: parse_aibao_schedule")
                 parsed_blocks = parse_aibao_schedule(schedule_text)
            elif hall_format_type == 'hanxiang':
                 print("  Using parser: parse_hanxiang_schedule")
                 logger.debug("Using parser: parse_hanxiang_schedule")
                 parsed_blocks = parse_hanxiang_schedule(schedule_text)
            elif hall_format_type == 'pandora':
                 print("  Using parser: parse_pandora_schedule")
                 logger.debug("Using parser: parse_pandora_schedule")
                 parsed_blocks = parse_pandora_schedule(schedule_text)
            elif hall_format_type == 'wangfei':
                 print("  Using parser: parse_wangfei_schedule")
                 logger.debug("Using parser: parse_wangfei_schedule")
                 parsed_blocks = parse_wangfei_schedule(schedule_text)
            # --- *** 新增 elif 處理樂鑽格式 *** ---
            elif hall_format_type == 'lezuan':
                 print("  Using parser: parse_lezuan_schedule")
                 logger.debug("Using parser: parse_lezuan_schedule")
                 parsed_blocks = parse_lezuan_schedule(schedule_text)
            # --- *** ---
            else:
                # 如果格式類型未知或不支持
                print(f"  Error: Unknown or unsupported schedule format type '{hall_format_type}' for Hall ID {selected_hall.id}.")
                logger.error(f"Unknown schedule format type '{hall_format_type}' for Hall ID {selected_hall.id}")
                return JsonResponse({'error': f'館別 "{selected_hall.name}" 的班表格式類型 ({hall_format_type}) 無法識別或尚未支援解析'}, status=400)

            print(f"Parsed {len(parsed_blocks)} blocks using the selected parser.")
            logger.info(f"Parsed {len(parsed_blocks)} blocks using parser for format '{hall_format_type}'.")

        except Exception as e:
             # 捕獲解析過程中可能發生的任何異常
             print(f"Error during parsing (using parser for format '{hall_format_type}'): {e}")
             logger.error(f"Error during parsing for format '{hall_format_type}'", exc_info=True)
             traceback.print_exc()
             return JsonResponse({'error': f'解析 "{selected_hall.name}" 班表時發生錯誤: {e}'}, status=500)
        # --- 解析器選擇邏輯結束 ---


        # ==================================
        # --- 處理預覽 (action == 'preview') ---
        # (無需修改，通用邏輯會處理 alias_suggestion (如果存在，樂鑽為 None))
        # ==================================
        if action == 'preview':
            print("--- Handling PREVIEW action ---")
            logger.info("Handling PREVIEW action")
            preview_data = []
            # 遍歷解析出的每個區塊
            for block in parsed_blocks:
                # 確保區塊有效且包含名字
                if not block or not block.get('name'):
                    print("Skipping invalid block:", block)
                    logger.warning(f"Skipping invalid parsed block: {block}")
                    continue

                match_status = "not_found" # 初始狀態：未找到
                matched_animal_id = None     # 匹配到的 Animal ID
                matched_animal_info = None # 匹配到的 Animal 詳細信息
                possible_matches = []      # 如果找不到，提供同館別的其他選項

                search_name = block['name'] # 從解析結果獲取名字
                # 獲取潛在的別名，去重 (此處已考慮 block.get('alias_suggestion'))
                potential_aliases = {alias.strip() for alias in [search_name, block.get('alias_suggestion')] if alias}

                print(f"  Matching '{search_name}' (potential aliases: {potential_aliases}) for Hall '{selected_hall.name}'...")
                logger.debug(f"Matching '{search_name}' (aliases: {potential_aliases}) for Hall '{selected_hall.name}'")

                try:
                    # 1. 精確匹配 (名字 + 館別)
                    exact_match = Animal.objects.filter(
                        name__iexact=search_name, # 忽略大小寫
                        hall=selected_hall,
                        is_active=True
                    ).first()

                    if exact_match:
                        print(f"    Found exact match: ID {exact_match.id}")
                        logger.debug(f"Found exact match: ID {exact_match.id} for name '{search_name}'")
                        match_status = "matched_exact"
                        matched_animal_id = exact_match.id
                        # 準備前端顯示的匹配信息
                        matched_animal_info = {
                            'id': exact_match.id,
                            'name': exact_match.name,
                            'hall_name': selected_hall.name, # 確定是當前館別
                            'fee': exact_match.fee # 顯示資料庫中的費用以便比對
                        }
                    else:
                        # 2. 嘗試用名字或別名在所有 active 的 Animal 中查找 (不限館別)
                        #    這有助於發現是否美容師換了館別
                        q_objects = Q(name__iexact=search_name) # 名字忽略大小寫匹配
                        if potential_aliases:
                            # 使用 __overlap 查詢 JSONField 中的別名列表是否有交集
                            q_objects |= Q(aliases__overlap=list(potential_aliases))

                        # 執行查詢，只查找 is_active=True 的
                        alias_query = Animal.objects.filter(q_objects, is_active=True).select_related('hall') # 優化查詢，預載入 hall 信息
                        query_count = alias_query.count()
                        print(f"    Alias/Name query (across all halls) found {query_count} match(es).")
                        logger.debug(f"Alias/Name query found {query_count} matches for '{search_name}'")

                        if query_count == 1:
                            # 恰好找到一個匹配項
                            animal = alias_query.first()
                            match_status = "matched_alias_or_name" # 可能是名字或別名匹配
                            matched_animal_id = animal.id
                            matched_animal_info = {
                                'id': animal.id,
                                'name': animal.name,
                                'hall_name': animal.hall.name if animal.hall else '未分館', # 顯示其所在館別
                                'fee': animal.fee
                            }
                            print(f"    Found unique alias/name match: ID {animal.id} ({animal.name}) in Hall '{matched_animal_info['hall_name']}'")
                            logger.debug(f"Found unique alias/name match: ID {animal.id} ({animal.name}) in Hall '{matched_animal_info['hall_name']}'")
                        elif query_count > 1:
                            # 找到多個匹配項 (可能是重名或別名衝突)
                            match_status = "multiple_matches"
                            # 列出所有可能的匹配項供用戶選擇
                            possible_matches = list(alias_query.values('id', 'name', 'hall__name'))
                            print(f"    Found multiple matches: {possible_matches}")
                            logger.warning(f"Found multiple ({query_count}) matches for name/alias '{search_name}': {possible_matches}")
                        else:
                            # 3. 完全找不到匹配項
                            match_status = "not_found"
                            print("    No match found via name or alias.")
                            logger.debug(f"No match found for name/alias '{search_name}'")


                    # 如果最終狀態是 "not_found"，提供當前所選館別的所有 active Animal 作為關聯選項
                    if match_status == "not_found":
                        possible_matches = list(
                            Animal.objects.filter(hall=selected_hall, is_active=True)
                                        .order_by('name')
                                        .values('id', 'name') # 只需要 ID 和名字
                        )
                        print(f"    Prepared {len(possible_matches)} possible associations from the same hall ('{selected_hall.name}').")
                        logger.debug(f"Prepared {len(possible_matches)} possible associations from hall '{selected_hall.name}'")

                except Exception as e:
                     # 捕獲匹配過程中的錯誤
                     print(f"!!! Error during matching for name '{search_name}': {e}")
                     logger.error(f"Error matching name '{search_name}'", exc_info=True)
                     traceback.print_exc()
                     match_status = "error" # 標記為錯誤狀態

                # 將此區塊的解析結果和匹配狀態添加到預覽數據列表
                preview_data.append({
                    'parsed': block,                 # 解析出的原始數據
                    'status': match_status,          # 匹配狀態 (matched_exact, matched_alias_or_name, multiple_matches, not_found, error)
                    'matched_animal_id': matched_animal_id, # 匹配到的 ID (如果唯一匹配)
                    'matched_animal_info': matched_animal_info, # 匹配到的詳細信息 (如果唯一匹配)
                    'possible_matches': possible_matches # 多個匹配或未找到時的選項列表
                })

            print("--- Preview data generated ---")
            logger.info("Preview data generated successfully.")
            # 返回 JSON 響應給前端
            return JsonResponse({'preview_data': preview_data})


        # =================================
        # --- 處理儲存 (action == 'save') ---
        # (無需修改，通用邏輯會處理 alias_suggestion (如果存在，樂鑽為 None))
        # =================================
        elif action == 'save':
            print(">>> Received SAVE action <<<")
            logger.info("Received SAVE action")
            try:
                # 從 POST 請求獲取前端最終確認的數據
                final_data_str = request.POST.get('final_data')
                # 同時獲取提交時的班表原文，可能用於存檔或其他目的
                schedule_text_on_save = request.POST.get('schedule_text', '')

                # 驗證 final_data 是否存在且格式正確
                if not final_data_str:
                    logger.warning("Save action missing 'final_data'.")
                    return JsonResponse({'error': '缺少最終確認數據'}, status=400)
                try:
                    final_data = json.loads(final_data_str)
                    # 確保是列表格式
                    assert isinstance(final_data, list)
                except (json.JSONDecodeError, ValueError, AssertionError) as e:
                    logger.error(f"Invalid 'final_data' format: {e}. Data: {final_data_str[:200]}...") # Log 前 200 字符
                    return JsonResponse({'error': f'前端提交的數據格式錯誤: {e}'}, status=400)

                # 初始化計數器
                animals_created_count = 0 # 新增美容師數量
                animals_updated_count = 0 # 更新美容師信息數量 (此處合併計數，或可分開計費/別名)
                schedules_created_count = 0 # 新增班表記錄數量
                updated_alias_count_actual = 0 # 實際更新了別名的數量
                updated_fee_count_actual = 0   # 實際更新了費用的數量

                print("Entering transaction...")
                logger.info("Entering transaction for saving schedule.")
                # 使用事務確保數據一致性
                with transaction.atomic():
                    # 創建一個列表來存儲需要稍後處理的項目 (非 'add_new' 的)
                    items_to_process_later = []
                    # 創建一個臨時映射來存儲新創建的 Animal ID，以防重名檢查失敗後仍需關聯
                    new_animal_temp_map = {}

                    # --- 第一步: 處理需要新增的美容師 ('add_new') ---
                    print("Processing 'add_new' operations...")
                    logger.debug("Processing 'add_new' operations.")
                    for index, item in enumerate(final_data):
                        if item.get('operation') == 'add_new':
                            parsed_data = item.get('parsed_data', {})
                            new_name = parsed_data.get('name')

                            if not new_name:
                                print(f"    Skipping add at index {index}: No name provided.")
                                logger.warning(f"Skipping add_new at index {index}: No name in parsed_data.")
                                continue # 跳過沒有名字的新增請求

                            # 檢查同館別下是否已存在同名 active 美容師
                            if Animal.objects.filter(name=new_name, hall=selected_hall, is_active=True).exists():
                                print(f"    Skipping add: '{new_name}' already exists in hall '{selected_hall.name}'. Associating instead.")
                                logger.warning(f"Skipping add_new: '{new_name}' already exists in hall '{selected_hall.name}'. Will try to associate.")
                                # 如果已存在，則將操作改為 'use_existing'，並記錄現有 ID
                                try:
                                    existing = Animal.objects.get(name=new_name, hall=selected_hall, is_active=True)
                                    item['animal_id'] = existing.id
                                    item['operation'] = 'use_existing' # 修改操作類型
                                    items_to_process_later.append(item) # 加入稍後處理列表
                                except Animal.DoesNotExist:
                                     # 理論上不應該發生，因爲上面 filter().exists() 為 True
                                     logger.error(f"Inconsistency: '{new_name}' exists check passed but get() failed.")
                                     # 這裡可以選擇忽略或報錯，暫定忽略此條目
                                     continue
                                continue # 處理下一條

                            # 準備別名列表 (如果有的話, 此處已考慮 alias_suggestion, 樂鑽為 None)
                            aliases_list = [parsed_data.get('alias_suggestion')] if parsed_data.get('alias_suggestion') else []

                            try:
                                # 創建新的 Animal 記錄
                                new_animal = Animal.objects.create(
                                    name=new_name,
                                    hall=selected_hall,
                                    fee=parsed_data.get('parsed_fee'), # 使用解析出的費用
                                    height=parsed_data.get('height'), # 王妃/樂鑽為 None
                                    weight=parsed_data.get('weight'), # 王妃/樂鑽為 None
                                    cup_size=parsed_data.get('cup'),   # 王妃/樂鑽為 None
                                    introduction=parsed_data.get('introduction'),
                                    is_active=True, # 默認設為 active
                                    order=999,      # 默認排序值
                                    aliases=aliases_list # 添加解析出的別名 (王妃/樂鑽為空)
                                )
                                animals_created_count += 1
                                print(f"    Created Animal ID: {new_animal.id} for name '{new_name}'")
                                logger.info(f"Created Animal ID: {new_animal.id} for name '{new_name}' in hall '{selected_hall.name}'")

                                # 將新創建的 Animal ID 存儲回 item 中，並修改操作為 use_existing
                                item['animal_id'] = new_animal.id
                                item['operation'] = 'use_existing'
                                items_to_process_later.append(item) # 加入稍後處理列表

                            except Exception as create_err:
                                # 捕獲創建過程中的錯誤 (例如數據庫約束、字段類型錯誤等)
                                print(f"    !!! Error creating animal '{new_name}': {create_err}")
                                logger.error(f"Error creating animal '{new_name}' in hall '{selected_hall.name}'", exc_info=True)
                                traceback.print_exc()
                                # 可以選擇在這裡 re-raise 錯誤來中斷事務，或者記錄錯誤並繼續處理其他條目
                                # 暫定：記錄錯誤，跳過此條目
                                continue

                        else:
                            # 如果操作不是 'add_new'，直接加入稍後處理列表
                            items_to_process_later.append(item)

                    # --- 第二步: 處理現有關聯/選擇的美容師，更新費用/別名，整理班表數據 ---
                    print("Processing existing/associated animals, fee/alias updates, and schedules...")
                    logger.debug("Processing existing/associated animals, fee/alias updates, and schedules.")
                    # 用於存儲需要更新費用的 Animal ID 和新費用
                    animals_to_update_fee = {}
                    # 用於存儲需要添加別名的 Animal ID 和要添加的別名列表
                    animals_to_update_aliases = {}
                    # 最終要寫入 DailySchedule 的數據列表 [{animal_id: X, slots: Y}, ...]
                    final_schedule_inputs = []
                    # 存儲所有有效操作涉及的 Animal ID，用於後續批量獲取和更新
                    valid_final_animal_ids = set()

                    for item in items_to_process_later:
                        operation = item.get('operation')
                        animal_id = item.get('animal_id')
                        final_slots = item.get('final_slots') # 前端確認的最終時段
                        update_fee_flag = item.get('update_fee', False) # 是否勾選了更新費用
                        parsed_data = item.get('parsed_data', {}) # 解析出的數據

                        # 如果操作是 'ignore'，直接跳過
                        if operation == 'ignore':
                            logger.debug(f"Ignoring item for Animal ID {animal_id} based on operation.")
                            continue

                        # 如果是 'use_existing' (包括剛新增的) 或 'associate' (手動選擇關聯的)
                        if operation == 'use_existing' or operation == 'associate':
                            if not animal_id:
                                logger.warning(f"Skipping item with operation '{operation}' due to missing animal_id: {item}")
                                continue # animal_id 是必須的

                            try:
                                # 確保 animal_id 是整數
                                animal_id = int(animal_id)

                                # 檢查是否需要更新費用
                                parsed_fee = parsed_data.get('parsed_fee')
                                if update_fee_flag and parsed_fee is not None:
                                     # 如果勾選了更新且解析出了費用，記錄下來
                                     animals_to_update_fee[animal_id] = parsed_fee
                                     print(f"  Marked ID {animal_id} for fee update to {parsed_fee}")
                                     logger.debug(f"Marked Animal ID {animal_id} for fee update to {parsed_fee}")

                                # 如果是手動關聯操作 ('associate')，嘗試添加解析出的名字/別名到現有記錄 (此處已考慮 alias_suggestion)
                                if operation == 'associate':
                                    parsed_name = parsed_data.get('name')
                                    parsed_alias = parsed_data.get('alias_suggestion')
                                    # 收集需要添加的別名 (解析出的名字和建議別名，去空值)
                                    aliases_to_add = [a for a in [parsed_name, parsed_alias] if a]
                                    if aliases_to_add:
                                        if animal_id not in animals_to_update_aliases:
                                            animals_to_update_aliases[animal_id] = []
                                        # 添加到待更新列表，稍後會去重處理
                                        animals_to_update_aliases[animal_id].extend(aliases_to_add)
                                        print(f"  Marked ID {animal_id} to potentially add aliases: {aliases_to_add}")
                                        logger.debug(f"Marked Animal ID {animal_id} to potentially add aliases: {aliases_to_add}")

                                # 記錄最終的班表信息
                                final_schedule_inputs.append({
                                    'animal_id': animal_id,
                                    'slots': final_slots if final_slots is not None else "" # 確保 slots 有值
                                })
                                # 將有效的 animal_id 加入集合
                                valid_final_animal_ids.add(animal_id)

                            except (ValueError, TypeError) as ve:
                                print(f"Warning: Invalid Animal ID '{animal_id}' in item: {item}. Error: {ve}")
                                logger.warning(f"Invalid Animal ID '{animal_id}' in item: {item}. Error: {ve}")
                                continue # 跳過無效 ID 的條目
                        else:
                             # 處理未知的操作類型
                             print(f"Warning: Unknown operation '{operation}' in item: {item}")
                             logger.warning(f"Unknown operation '{operation}' in item: {item}")
                             continue # 跳過未知操作

                    # --- 批量更新費用和別名 ---
                    # 獲取所有涉及的 Animal 實例
                    animal_ids_to_process = list(valid_final_animal_ids)
                    # 使用 in_bulk 或 filter 獲取對象字典，方便按 ID 訪問
                    animals_to_update = {animal.id: animal for animal in Animal.objects.filter(id__in=animal_ids_to_process)}
                    print(f"Found {len(animals_to_update)} existing animals to potentially update (fee/alias).")
                    logger.debug(f"Found {len(animals_to_update)} animals for potential fee/alias update.")

                    for animal_id in animal_ids_to_process:
                        animal_instance = animals_to_update.get(animal_id)
                        if not animal_instance:
                            logger.warning(f"Animal ID {animal_id} marked for update but not found in bulk query.")
                            continue # 如果 ID 無效或查詢失敗，跳過

                        needs_save = False # 標記此實例是否需要保存
                        update_fields = [] # 記錄需要更新的字段，用於優化 save()

                        # a. 更新費用
                        new_fee = animals_to_update_fee.get(animal_id)
                        if new_fee is not None and animal_instance.fee != new_fee:
                             animal_instance.fee = new_fee
                             needs_save = True
                             update_fields.append('fee')
                             updated_fee_count_actual += 1 # 實際更新計數
                             print(f"  Updating fee for ID {animal_id} to {new_fee}")
                             logger.debug(f"Updating fee for Animal ID {animal_id} to {new_fee}")

                        # b. 更新別名 (此處通用邏輯已兼容樂鑽格式 - 其 alias_suggestion 為 None)
                        aliases_to_add = animals_to_update_aliases.get(animal_id)
                        if aliases_to_add:
                             # 確保 instance.aliases 是列表
                             if not isinstance(animal_instance.aliases, list):
                                 animal_instance.aliases = []

                             aliases_changed = False
                             # 獲取當前別名的小寫集合，以及主要名字的小寫，用於去重和避免將主名加入別名
                             current_aliases_lower = {a.lower() for a in animal_instance.aliases if isinstance(a, str)}
                             main_name_lower = animal_instance.name.lower()

                             # 遍歷待添加的別名 (去重)
                             for alias in set(aliases_to_add):
                                 alias_lower = alias.strip().lower()
                                 # 只有當別名非空、不是主要名字、且不在現有別名中時，才添加
                                 if alias_lower and alias_lower != main_name_lower and alias_lower not in current_aliases_lower:
                                     animal_instance.aliases.append(alias.strip())
                                     aliases_changed = True
                                     print(f"  Adding alias '{alias.strip()}' to ID {animal_id}")
                                     logger.debug(f"Adding alias '{alias.strip()}' to Animal ID {animal_id}")

                             if aliases_changed:
                                 needs_save = True
                                 update_fields.append('aliases')
                                 updated_alias_count_actual += 1 # 實際更新計數

                        # c. 保存更改 (如果需要)
                        if needs_save:
                            try:
                                # 只更新修改過的字段
                                animal_instance.save(update_fields=list(set(update_fields))) # 確保字段列表唯一
                            except Exception as save_err:
                                # 捕獲保存單個 Animal 時的錯誤
                                print(f"  !!! Error saving updates for ID {animal_id}: {save_err}")
                                logger.error(f"Error saving updates for Animal ID {animal_id}", exc_info=True)
                                # 根據策略決定是否中斷或繼續
                                # 暫定：記錄錯誤，繼續處理其他 Animal

                    # 更新總的更新計數 (如果需要合併顯示)
                    animals_updated_count = updated_fee_count_actual + updated_alias_count_actual # 或者只算 unique ID?

                    # --- 第三步: 清除舊班表 ---
                    # 刪除所選館別當天的所有舊班表記錄
                    print(f"Deleting old schedules for hall ID {selected_hall.id}...")
                    logger.info(f"Deleting old schedules for hall ID {selected_hall.id} ({selected_hall.name})...")
                    try:
                        deleted_count, _ = DailySchedule.objects.filter(hall=selected_hall).delete()
                        print(f"  Deleted {deleted_count} old records.")
                        logger.info(f"Deleted {deleted_count} old DailySchedule records for hall '{selected_hall.name}'.")
                    except Exception as del_err:
                        print(f"  !!! Error deleting old schedules: {del_err}")
                        logger.error(f"Error deleting old schedules for Hall {selected_hall.id} ({selected_hall.name})", exc_info=True)
                        # 刪除失敗是嚴重問題，應該中斷事務
                        raise # 重新拋出異常，事務將回滾

                    # --- 第四步: 批量創建新班表 ---
                    print("Creating new schedules...")
                    logger.info("Creating new DailySchedule records...")
                    schedule_objects = []
                    # 使用更新後的有效 Animal ID 集合進行過濾
                    final_valid_set = set(animals_to_update.keys())

                    for info in final_schedule_inputs:
                        # 確保 animal_id 仍然有效
                        if info['animal_id'] in final_valid_set:
                             schedule_objects.append(
                                 DailySchedule(
                                     hall=selected_hall,
                                     animal_id=info['animal_id'],
                                     time_slots=info['slots'] if info['slots'] is not None else "" # 確保存儲的是字符串
                                 )
                             )
                        else:
                             print(f"  Skipping schedule creation: Animal ID {info['animal_id']} not in valid set (possibly skipped during update).")
                             logger.warning(f"Skipping schedule creation for Animal ID {info['animal_id']} as it was not in the final valid set.")

                    # 如果有需要創建的班表記錄
                    if schedule_objects:
                        try:
                            # 執行批量創建
                            DailySchedule.objects.bulk_create(schedule_objects)
                            schedules_created_count = len(schedule_objects)
                            print(f"  Successfully created {schedules_created_count} new schedule records.")
                            logger.info(f"Bulk created {schedules_created_count} new DailySchedule records for hall '{selected_hall.name}'.")
                        except Exception as bulk_err:
                            # 捕獲批量創建錯誤
                            print(f"  !!! Error bulk creating schedules: {bulk_err}")
                            logger.error("Error bulk creating DailySchedule records", exc_info=True)
                            # 批量創建失敗也應中斷事務
                            raise # 重新拋出異常

                # --- 事務成功提交 ---
                print("Transaction committed successfully.")
                logger.info("Schedule save transaction committed successfully.")
                # 返回成功的 JSON 響應和匯總信息
                return JsonResponse({
                    'success': True,
                    'message': f'班表已儲存。新增美容師: {animals_created_count}, 更新費用: {updated_fee_count_actual}, 更新別名: {updated_alias_count_actual}, 總計更新班表: {schedules_created_count} 筆。'
                })

            except Exception as e:
                # 捕獲事務處理過程中的任何未預料異常
                print(f"!!! Error during SAVE action processing: {e} !!!")
                logger.critical("Critical error during SAVE action processing", exc_info=True) # 使用 critical 級別標記嚴重錯誤
                traceback.print_exc()
                # 返回服務器錯誤響應
                return JsonResponse({'error': '儲存班表時發生內部錯誤，請檢查伺服器日誌或聯繫管理員。'}, status=500)

        else: # 無效的 action
            print(f"Error: Invalid action '{action}' received.")
            logger.warning(f"Invalid action '{action}' received in POST request.")
            return JsonResponse({'error': '無效的操作請求'}, status=400)

    else: # 非 GET 或 POST 請求
        print(f"Error: Unsupported HTTP method '{request.method}'.")
        logger.warning(f"Unsupported HTTP method '{request.method}' received for parse_schedule_view.")
        return HttpResponseBadRequest("不支持的請求方法")

# --- views.py 文件結束 ---