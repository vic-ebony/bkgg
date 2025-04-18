# D:\bkgg\mybackend\schedule_parser\utils.py
import re
import html
import logging

logger = logging.getLogger(__name__) # 創建 logger

# ============================================================
# --- 函數 1: 解析舊的 LINE 格式 (格式 A) ---
# (保持不變)
# ============================================================
def parse_line_schedule(text):
    """
    解析舊格式的 LINE 文字班表 (以 '(數字)' 開頭區塊)。
    返回一個列表，每個元素是一個包含解析信息的字典。
    """
    results = []
    current_animal_block = []
    lines = text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line: continue # 跳過空行

        if re.match(r'^\(\s*\d+\s*\)', line):
            if current_animal_block:
                parsed = process_animal_block(current_animal_block) # 調用舊格式的處理函數
                if parsed: results.append(parsed)
            current_animal_block = [line]
        elif current_animal_block:
            current_animal_block.append(line)

    if current_animal_block:
        parsed = process_animal_block(current_animal_block) # 調用旧格式的处理函数
        if parsed: results.append(parsed)

    return results

def process_animal_block(block_lines):
    """處理舊格式的單個美容師文字區塊"""
    if not block_lines: return None
    fee = None; name = None; original_name_text = ""; alias_suggestion = None
    height = None; weight = None; cup = None; intro_lines = []; time_slots_str = None
    try:
        first_line = block_lines[0]
        fee_match = re.search(r'^\(\s*(\d+)\s*\)', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100
            except ValueError: pass
        name_part_match = re.search(r'\)\s*(.*?)\s*👙', first_line)
        if name_part_match:
            original_name_text = name_part_match.group(1).strip()
            main_name_match = re.match(r'^([^\(（\s]+)', original_name_text)
            if main_name_match:
                name = main_name_match.group(1).strip()
                alias_match = re.search(r'[\(（](.+?)[\)）]', original_name_text)
                if alias_match:
                    alias_suggestion = alias_match.group(1).strip()
                    if alias_suggestion.startswith("原"): alias_suggestion = alias_suggestion[1:].strip()
            else: name = original_name_text
        size_match = re.search(r'(\d{3})\s*/\s*(\d{2,3})\s*/\s*([A-Za-z\+\-]+)', first_line)
        if size_match:
            try: height = int(size_match.group(1))
            except ValueError: pass
            try: weight = int(size_match.group(2))
            except ValueError: pass
            cup = size_match.group(3).strip()
        time_found = False
        for line in block_lines[1:]:
            line_strip = line.strip()
            if line_strip.startswith('⏰'):
                time_info = line_strip.replace('⏰', '').strip()
                if time_info == '🈵': time_slots_str = "預約滿"
                elif time_info == '人到再約' or time_info.startswith('人道'): time_slots_str = "人到再約"
                elif not time_info: time_slots_str = ""
                else:
                    slots = re.findall(r'\d{1,2}', time_info)
                    processed_slots = []
                    for s in slots:
                        try:
                            num = int(s)
                            internal_value = -1
                            if 12 <= num <= 23: internal_value = num
                            elif num == 24: internal_value = 100
                            elif 0 <= num <= 5: internal_value = num + 100
                            if internal_value != -1: processed_slots.append(internal_value)
                        except ValueError: continue
                    processed_slots.sort()
                    time_slots_str = ".".join(map(str, processed_slots))
                time_found = True
            elif not time_found:
                if not line_strip.startswith('🈲') and not line_strip.startswith('(<') and not line_strip.startswith('(>') and line_strip:
                    intro_lines.append(line_strip)
        if name:
            return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                    'alias_suggestion': alias_suggestion, 'height': height, 'weight': weight,
                    'cup': cup, 'introduction': "\n".join(intro_lines).strip(),
                    'time_slots': time_slots_str if time_slots_str is not None else ""}
    except Exception as e: logger.error(f"處理舊格式區塊時出錯: {block_lines}", exc_info=True); return None
    return None

# ============================================================
# --- 函數 2: 解析新的 "茶湯會" 格式 (格式 B) ---
# (parse_chatanghui_schedule 保持不變)
# ============================================================
def parse_chatanghui_schedule(text):
    """
    解析 "茶湯會休閒會館" 格式的 LINE 文字班表。
    返回與 parse_line_schedule 相同結構的列表。
    修正了區塊分割邏輯。
    """
    results = []
    lines = text.strip().split('\n')
    current_block_lines = []
    block_start_pattern = r'^[(\s]*(?:[\w\s]+|\S+)[)\s]*【.+?】\s*\d+'

    for line in lines:
        line_strip = line.strip()
        if not line_strip: continue

        is_start_line = re.match(block_start_pattern, line_strip)
        if is_start_line:
            if current_block_lines:
                parsed = process_chatanghui_block(current_block_lines) # 調用處理函數
                if parsed: results.append(parsed)
            current_block_lines = [line_strip]
        elif current_block_lines:
            current_block_lines.append(line_strip)

    if current_block_lines:
        parsed = process_chatanghui_block(current_block_lines) # 處理最後一個區塊
        if parsed: results.append(parsed)

    return results

# --- process_chatanghui_block (包含方案一修正介紹收集) ---
def process_chatanghui_block(block_lines):
    """
    處理單個 "茶湯會休閒會館" 格式的美容師區塊。
    更靈活地處理時段、身材、介紹、禁忌行的順序。
    按原始順序收集所有非結構化信息行作為介紹。
    """
    if not block_lines: return None

    name = None; original_name_text = ""; alias_suggestion = None; fee = None
    time_slots_str = "" # 初始化為空
    height = None; weight = None; cup = None
    other_lines = [] # 用於收集所有其他行
    name_pattern_in_intro = r'【.+?】'

    # 標記某類信息是否已找到
    time_found = False
    size_found = False

    line_index = 0
    try:
        # 1. 處理第一行 (名字、費用、別名)
        first_line = block_lines[line_index]
        name_match = re.search(r'【(.+?)】', first_line)
        if name_match:
            name = name_match.group(1).strip(); original_name_text = f"【{name}】"
            fee_match = re.search(r'】\s*(\d+)', first_line)
            if fee_match:
                try: fee = int(fee_match.group(1)) * 100
                except ValueError: logger.warning(f"Chatanghui Parser: 無法解析費用數字 '{fee_match.group(1)}'")
            alias_match = re.search(r'】\s*\d+\s*[\(（](.+?)[\)）]', first_line)
            if alias_match:
                alias_raw = alias_match.group(1).strip()
                if alias_raw.startswith("原"): alias_suggestion = alias_raw[1:].strip()
                else: alias_suggestion = alias_raw
        else: logger.warning(f"Chatanghui Parser: 無法從第一行解析名字: {first_line}"); return None
        line_index += 1

        # 2. 循環處理後續所有行，靈活匹配，並收集其他行
        while line_index < len(block_lines):
            current_line = block_lines[line_index].strip()

            # a. 檢查是否是下一區塊的開始行
            if re.search(name_pattern_in_intro, current_line) and line_index > 0:
                 logger.debug(f"停止處理茶湯會區塊，因為行 '{current_line}' 包含名字模式")
                 break

            is_processed_structurally = False

            # b. 嘗試匹配時段 (如果還沒找到)
            if not time_found:
                if current_line == '🈵️' or current_line == '🈵':
                    time_slots_str = "預約滿"; time_found = True; is_processed_structurally = True
                elif current_line.startswith('人到再約') or current_line.startswith('人到在約'):
                    time_slots_str = "人到再約"; time_found = True; is_processed_structurally = True
                    # 將括號信息也加入 other_lines (保持方案一)
                    extra_info_match = re.search(r'[\(（](.*?)[\)）]', current_line)
                    if extra_info_match: other_lines.append(f"(備註: {extra_info_match.group(1).strip()})")

                elif re.search(r'\d', current_line): # 嘗試匹配數字時段
                    raw_slots = re.findall(r'\d+', current_line)
                    processed_slots = []
                    valid_time_line = False
                    for s in raw_slots:
                        try:
                            s_corrected = s[:2] if len(s) > 2 else s; num = int(s_corrected)
                            internal_value = -1
                            if 12 <= num <= 23: internal_value = num
                            elif num == 24: internal_value = 100
                            elif 0 <= num <= 5: internal_value = num + 100
                            if internal_value != -1: processed_slots.append(internal_value); valid_time_line = True
                        except ValueError: logger.warning(f"Chatanghui Parser: 時段行 '{current_line}' 中無法轉換數字 '{s}'")
                    if valid_time_line:
                         processed_slots = sorted(list(set(processed_slots)))
                         time_slots_str = ".".join(map(str, processed_slots)) if processed_slots else ""
                         time_found = True; is_processed_structurally = True
                         print(f"    找到時段: {time_slots_str} (來自行: '{current_line}')")

            # c. 嘗試匹配身材 (如果還沒找到 且 未被處理為時段)
            # 注意：茶湯會格式的身材分隔符可能是 '/' 或 '.'，需要兼容
            if not size_found and not is_processed_structurally:
                size_match_slash = re.match(r'^(\d{3})\s*/\s*(\d{2,3})\s*/\s*([A-Za-z\+\-]+)', current_line)
                size_match_dot = re.match(r'^(\d{3})\s*\.\s*(\d{2,3})\s*\.\s*([A-Za-z\+\-]+)', current_line)
                size_match = size_match_slash or size_match_dot

                if size_match:
                    try: height = int(size_match.group(1))
                    except ValueError: pass
                    try: weight = int(size_match.group(2))
                    except ValueError: pass
                    cup = size_match.group(3).strip(); size_found = True
                    is_processed_structurally = True
                    print(f"    找到身材: {height}/{weight}/{cup} (來自行: '{current_line}')")

            # d. 如果未被結構化處理，則加入 other_lines (介紹/禁忌)
            if not is_processed_structurally and current_line:
                other_lines.append(current_line)
                print(f"    收集到其他行: '{current_line}'")

            line_index += 1 # 處理下一行

        # 直接合併所有收集到的其他行作為介紹
        full_introduction = "\n".join(other_lines).strip()

        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': alias_suggestion, 'height': height, 'weight': weight,
                'cup': cup, 'introduction': full_introduction,
                'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"處理茶湯會區塊時出錯: {block_lines}", exc_info=True)
        return None

# ============================================================
# --- 函數 3: 解析新的 "芯苑館" 格式 (格式 C) ---
# ============================================================
def parse_xinyuan_schedule(text):
    """
    解析 "芯苑館" 格式的 LINE 文字班表。
    返回與 parse_line_schedule 相同結構的列表。
    """
    results = []
    lines = text.strip().split('\n')
    current_block_lines = []
    block_start_pattern = r'^\s*《\s*\d+\s*》' # 芯苑館區塊開始模式

    for line in lines:
        line_strip = line.strip()
        if not line_strip: continue

        is_start_line = re.match(block_start_pattern, line_strip)
        if is_start_line:
            if current_block_lines:
                parsed = process_xinyuan_block(current_block_lines) # <--- 調用芯苑館的處理函數
                if parsed: results.append(parsed)
            current_block_lines = [line_strip]
        elif current_block_lines:
            current_block_lines.append(line_strip)

    if current_block_lines:
        parsed = process_xinyuan_block(current_block_lines) # <--- 調用芯苑館的處理函數
        if parsed: results.append(parsed)

    return results

# --- *** 修正了 process_xinyuan_block 中 "人到再約" 的處理 *** ---
def process_xinyuan_block(block_lines):
    """
    處理單個 "芯苑館" 格式的美容師區塊。
    更靈活地處理時段、身材、介紹、禁忌行的順序。
    修正了身材行在介紹行之後無法被識別的問題。
    修正了 "人到再約" 後的時間範圍處理。
    """
    if not block_lines: return None

    fee = None; name = None; original_name_text = ""; alias_suggestion = None
    time_slots_str = ""; height = None; weight = None; cup = None
    other_lines = [] # 用於收集所有非結構化行
    # --- 用於判斷區塊結束的模式 ---
    xinyuan_block_start_pattern = r'^\s*《\s*\d+\s*》'

    # 標記信息是否已找到
    time_found = False
    size_found = False

    line_index = 0
    try:
        # 1. 處理第一行 (費用、名字、可能的身材)
        first_line = block_lines[line_index]
        original_name_text = first_line

        fee_match = re.search(r'《\s*(\d+)\s*》', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100 # 單位假設是百元
            except ValueError: logger.warning(f"Xinyuan Parser: 無法解析費用 '{fee_match.group(1)}'")

        name_part = re.sub(r'^\s*《\s*\d+\s*》\s*(\(new\))?\s*', '', first_line).strip()
        size_match_in_first = re.search(r'(\d{3}\.\d{2,3}\.[A-Za-z\+\-]+)', name_part)

        if size_match_in_first:
            name = name_part[:size_match_in_first.start()].strip()
            size_str = size_match_in_first.group(1)
            parts = size_str.split('.')
            if len(parts) == 3:
                try: height = int(parts[0])
                except ValueError: pass
                try: weight = int(parts[1])
                except ValueError: pass
                cup = parts[2].strip(); size_found = True
        else:
             name_part_cleaned = re.sub(r'[^\w\s]+$', '', name_part).strip()
             name = name_part_cleaned

        if not name: logger.warning(f"Xinyuan Parser: 無法從 '{first_line}' 解析名字"); return None
        line_index += 1

        # 2. 循環處理後續所有行
        while line_index < len(block_lines):
            current_line = block_lines[line_index].strip()

            # a. 檢查是否是下一區塊的開始行
            if re.match(xinyuan_block_start_pattern, current_line):
                 logger.debug(f"停止處理芯苑區塊，遇到下一區塊開始行: '{current_line}'")
                 break

            is_processed_structurally = False

            # b. 嘗試匹配時段 (如果還沒找到)
            if not time_found:
                if current_line == '🈵️' or current_line == '🈵':
                    time_slots_str = "預約滿"; time_found = True; is_processed_structurally = True
                # --- *** 修改：處理 "人到再約" 及其時間範圍 *** ---
                elif current_line.startswith('人到再約') or current_line.startswith('人到在約'):
                    time_display = "人到再約"
                    extra_info_match = re.search(r'[\(（](.*?)[\)）]', current_line)
                    if extra_info_match:
                        time_range = extra_info_match.group(1).strip()
                        time_display = f"人到再約 ({time_range})"
                    time_slots_str = time_display # time_slots_str 包含完整信息
                    time_found = True; is_processed_structurally = True
                    print(f"    找到時段: {time_slots_str} (來自行: '{current_line}')")
                # --- *** 修改結束 *** ---
                elif re.search(r'\d', current_line): # 嘗試匹配數字時段 (用 - 分隔)
                    cleaned_time_info = re.sub(r'[^\d-]+', '', current_line)
                    slots = cleaned_time_info.split('-')
                    processed_slots = []
                    valid_time_line = False
                    for s in slots:
                        s_num_part = re.search(r'\d+', s)
                        if s_num_part:
                            s_val = s_num_part.group(0)
                            try:
                                s_corrected = s_val[:2] if len(s_val) > 2 else s_val; num = int(s_corrected)
                                internal_value = -1
                                if 12 <= num <= 23: internal_value = num
                                elif num == 24: internal_value = 100
                                elif 0 <= num <= 5: internal_value = num + 100
                                if internal_value != -1: processed_slots.append(internal_value); valid_time_line = True
                            except ValueError: logger.warning(f"Xinyuan Parser: 無法轉換時段數字 '{s_val}' in '{current_line}'")
                    if valid_time_line:
                         processed_slots = sorted(list(set(processed_slots)))
                         time_slots_str = ".".join(map(str, processed_slots)) if processed_slots else ""
                         time_found = True; is_processed_structurally = True
                         print(f"    找到時段: {time_slots_str} (來自行: '{current_line}')")

            # c. 嘗試匹配身材 (如果還沒找到 且 未被處理為時段)
            if not size_found and not is_processed_structurally:
                size_match = re.match(r'^(\d{3})\s*\.\s*(\d{2,3})\s*\.\s*([A-Za-z\+\-]+)', current_line)
                if size_match:
                    try: height = int(size_match.group(1))
                    except ValueError: pass
                    try: weight = int(size_match.group(2))
                    except ValueError: pass
                    cup = size_match.group(3).strip(); size_found = True
                    is_processed_structurally = True
                    print(f"    找到身材: {height}/{weight}/{cup} (來自行: '{current_line}')")

            # d. 如果未被結構化處理，則加入 other_lines
            if not is_processed_structurally and current_line:
                other_lines.append(current_line)
                print(f"    收集到其他行: '{current_line}'")

            line_index += 1 # 處理下一行

        full_introduction = "\n".join(other_lines).strip()

        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': None, # 此格式無別名
                'height': height, 'weight': weight, 'cup': cup,
                'introduction': full_introduction, # 合併了介紹和禁忌
                'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"處理芯苑館區塊時出錯: {block_lines}", exc_info=True)
        return None

# --- utils.py 文件結束 ---