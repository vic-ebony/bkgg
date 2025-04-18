# D:\bkgg\mybackend\schedule_parser\utils.py
import re
import html
import logging

logger = logging.getLogger(__name__) # 創建 logger

# --- Word to Digit Mapping ---
WORD_TO_DIGIT = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, # Add more if needed
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
    '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
}

# ============================================================
# --- 函數 1: 解析舊的 LINE 格式 (格式 A) ---
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
        original_name_text = first_line # 記錄原始第一行
        fee_match = re.search(r'^\(\s*(\d+)\s*\)', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100
            except ValueError: pass
        # 修改名字提取：從 ')' 後面開始，直到 👙 或行尾
        name_part_match = re.search(r'\)\s*(.*?)(?:\s*👙|$)', first_line)
        if name_part_match:
            original_name_text_part = name_part_match.group(1).strip()
            # 嘗試提取括號內的別名
            alias_match = re.search(r'[\(（](.+?)[\)）]', original_name_text_part)
            if alias_match:
                alias_content = alias_match.group(1).strip()
                if alias_content.startswith("原"):
                    alias_suggestion = alias_content[1:].strip()
                else:
                    alias_suggestion = alias_content # 如果不是以 "原" 開頭，也記錄下來
                # 從原始名字部分移除別名括號
                name = re.sub(r'[\(（].+?[\)）]', '', original_name_text_part).strip()
            else:
                # 沒有括號別名，直接使用
                name = original_name_text_part

            # 如果名字為空（可能只有別名），嘗試使用別名作為名字
            if not name and alias_suggestion:
                 name = alias_suggestion
                 alias_suggestion = None # 因為它被用作名字了
        else: # 如果連名字部分都匹配不到
             name = None # 或設置一個預設值，或根據後續邏輯決定

        # 身材提取
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
                            elif num == 24: internal_value = 100 # 24點 -> 內部 100
                            elif 0 <= num <= 5: internal_value = num + 100 # 0-5點 -> 內部 100-105
                            if internal_value != -1: processed_slots.append(internal_value)
                        except ValueError: continue
                    processed_slots.sort() # 排序
                    time_slots_str = ".".join(map(str, processed_slots))
                time_found = True
            elif not time_found: # 只有在還沒找到時間行時，才加入介紹
                 # 排除特定標誌開頭的行，並且確保行不為空
                 if not line_strip.startswith('🈲') and not line_strip.startswith('(<') and not line_strip.startswith('(>') and line_strip:
                     intro_lines.append(line_strip)
            elif time_found and line_strip: # 如果找到時間後還有非空行，也可能是介紹的一部分
                 if not line_strip.startswith('🈲') and not line_strip.startswith('(<') and not line_strip.startswith('(>'):
                     intro_lines.append(line_strip)

        if name: # 確保解析到了名字才返回結果
            # 返回時將 alias_suggestion 設為 None (如果舊格式需要別名則保留)
            return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                    'alias_suggestion': alias_suggestion, 'height': height, 'weight': weight, # 保留舊格式可能需要的別名
                    'cup': cup, 'introduction': "\n".join(intro_lines).strip(),
                    'time_slots': time_slots_str if time_slots_str is not None else ""} # 確保 time_slots 有值
    except Exception as e:
        logger.error(f"處理舊格式區塊時出錯: {block_lines}", exc_info=True)
        return None
    return None # 如果沒有名字或其他錯誤，返回 None

# ============================================================
# --- 函數 2: 解析新的 "茶湯會" 格式 (格式 B) ---
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
    # 修改區塊開始模式：名字用【】包圍，後面可能跟著數字費用
    block_start_pattern = r'^[(\s]*(?:[\w\s]+|\S+)[)\s]*【.+?】\s*\d+' # 稍微放寬開頭，主要靠【名字】費用 識別

    for line in lines:
        line_strip = line.strip()
        if not line_strip: continue # 跳過空行

        # 判斷是否為新區塊的開始行
        is_start_line = re.match(block_start_pattern, line_strip)

        if is_start_line:
            # 如果當前有正在處理的區塊，先處理掉
            if current_block_lines:
                parsed = process_chatanghui_block(current_block_lines) # 調用處理函數
                if parsed: results.append(parsed)
            # 開始新的區塊
            current_block_lines = [line_strip]
        elif current_block_lines:
            # 如果不是開始行，且當前有區塊，則添加到當前區塊
            current_block_lines.append(line_strip)

    # 處理最後一個區塊
    if current_block_lines:
        parsed = process_chatanghui_block(current_block_lines) # 處理最後一個區塊
        if parsed: results.append(parsed)

    return results

def process_chatanghui_block(block_lines):
    """
    處理單個 "茶湯會休閒會館" 格式的美容師區塊。
    更靈活地處理時段、身材、介紹、禁忌行的順序。
    按原始順序收集所有非結構化信息行作為介紹。
    """
    if not block_lines: return None

    name = None; original_name_text = ""; alias_suggestion = None; fee = None
    time_slots_str = "" # 初始化為空字串
    height = None; weight = None; cup = None
    other_lines = [] # 用於收集所有其他行 (介紹、禁忌等)
    name_pattern_in_intro = r'【.+?】' # 用於判斷是否意外讀到下個人的名字行

    # 標記某類信息是否已找到
    time_found = False
    size_found = False

    line_index = 0
    try:
        # 1. 處理第一行 (包含名字【XXX】和費用)
        first_line = block_lines[line_index]
        original_name_text = first_line # 記錄原始第一行

        name_match = re.search(r'【(.+?)】', first_line)
        if name_match:
            name = name_match.group(1).strip()
            # 費用通常在名字後面
            fee_match = re.search(r'】\s*(\d+)', first_line)
            if fee_match:
                try:
                    fee = int(fee_match.group(1)) * 100
                except ValueError:
                    logger.warning(f"Chatanghui Parser: 無法解析費用數字 '{fee_match.group(1)}'")
            # 嘗試提取緊跟費用後的別名 (原XXX) - 茶湯會格式可能需要保留別名
            alias_match = re.search(r'】\s*\d+\s*[\(（](.+?)[\)）]', first_line)
            if alias_match:
                 alias_raw = alias_match.group(1).strip()
                 if alias_raw.startswith("原"):
                     alias_suggestion = alias_raw[1:].strip()
                 else:
                     alias_suggestion = alias_raw # 非 "原" 開頭也記錄
        else:
            # 如果第一行找不到【名字】，可能格式有變，記錄警告並返回
            logger.warning(f"Chatanghui Parser: 無法從第一行解析名字: {first_line}")
            return None # 或者嘗試從後續行解析，但目前策略是基於第一行

        line_index += 1 # 移到下一行

        # 2. 循環處理後續所有行，靈活匹配，並收集其他行
        while line_index < len(block_lines):
            current_line = block_lines[line_index].strip()

            # a. 檢查是否意外讀入了下一個區塊的開始行 (包含【名字】模式)
            #    (避免把下個人的名字行當成介紹)
            if re.search(name_pattern_in_intro, current_line) and line_index > 0:
                 logger.debug(f"停止處理茶湯會區塊，因為行 '{current_line}' 包含名字模式，可能是下一個區塊的開始")
                 break # 停止處理當前區塊

            is_processed_structurally = False # 標記當前行是否被識別為結構化信息

            # b. 嘗試匹配時段 (如果還沒找到)
            if not time_found:
                # 完全匹配 "🈵️" 或 "🈵"
                if current_line == '🈵️' or current_line == '🈵':
                    time_slots_str = "預約滿"
                    time_found = True
                    is_processed_structurally = True
                # 匹配 "人到再約" 或 "人到在約"，可能帶括號說明
                elif current_line.startswith('人到再約') or current_line.startswith('人到在約'):
                    time_display = "人到再約" # 基礎狀態字串
                    extra_info_match = re.search(r'[\(（](.*?)[\)）]', current_line)
                    if extra_info_match:
                        other_lines.append(f"(備註: {extra_info_match.group(1).strip()})") # 作為備註加入介紹
                    time_slots_str = time_display # 設置 time_slots_str 為 "人到再約"
                    time_found = True
                    is_processed_structurally = True
                # 嘗試匹配包含數字的時段行
                elif re.search(r'\d', current_line): # 只要包含數字就可能是時段行
                    raw_slots = re.findall(r'\d+', current_line)
                    processed_slots = []
                    valid_time_line = False
                    for s in raw_slots:
                        try:
                            s_corrected = s[:2] if len(s) > 2 else s
                            num = int(s_corrected)
                            internal_value = -1
                            if 12 <= num <= 23: internal_value = num
                            elif num == 24: internal_value = 100
                            elif 0 <= num <= 5: internal_value = num + 100
                            if internal_value != -1:
                                processed_slots.append(internal_value)
                                valid_time_line = True
                        except ValueError: pass
                    if valid_time_line:
                         processed_slots = sorted(list(set(processed_slots))) # 去重並排序
                         time_slots_str = ".".join(map(str, processed_slots)) if processed_slots else ""
                         time_found = True
                         is_processed_structurally = True


            # c. 嘗試匹配身材 (如果還沒找到 且 未被處理為時段)
            if not size_found and not is_processed_structurally:
                size_match_slash = re.match(r'^\s*(\d{3})\s*/\s*(\d{2,3})\s*/\s*([A-Za-z\+\-]+)\s*$', current_line)
                size_match_dot = re.match(r'^\s*(\d{3})\s*\.\s*(\d{2,3})\s*\.\s*([A-Za-z\+\-]+)\s*$', current_line)
                size_match = size_match_slash or size_match_dot
                if size_match:
                    try: height = int(size_match.group(1))
                    except ValueError: pass
                    try: weight = int(size_match.group(2))
                    except ValueError: pass
                    cup = size_match.group(3).strip()
                    size_found = True
                    is_processed_structurally = True


            # d. 如果當前行未被識別為時段或身材，且不為空，則加入 other_lines
            if not is_processed_structurally and current_line:
                other_lines.append(current_line)


            line_index += 1 # 處理下一行

        # 3. 將收集到的所有 other_lines 合併為介紹文本
        full_introduction = "\n".join(other_lines).strip()

        # 4. 返回結果字典
        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': alias_suggestion, 'height': height, 'weight': weight, # 保留茶湯會可能需要的別名
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
    block_start_pattern = r'^\s*《\s*\d+\s*》' # 芯苑館區塊開始模式 《 數字 》

    for line in lines:
        line_strip = line.strip()
        if not line_strip: continue # 跳過空行

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

def process_xinyuan_block(block_lines):
    """
    處理單個 "芯苑館" 格式的美容師區塊。
    更靈活地處理時段、身材、介紹、禁忌行的順序。
    修正了 "人到再約" 後的時間範圍處理。
    """
    if not block_lines: return None

    fee = None; name = None; original_name_text = ""; alias_suggestion = None # 芯苑格式似乎不明顯有別名
    time_slots_str = ""; height = None; weight = None; cup = None
    other_lines = [] # 收集所有非結構化行
    xinyuan_block_start_pattern = r'^\s*《\s*\d+\s*》' # 用於判斷區塊結束

    # 標記信息是否已找到
    time_found = False
    size_found = False

    line_index = 0
    try:
        # 1. 處理第一行 (費用、名字、可能的身材)
        first_line = block_lines[line_index]
        original_name_text = first_line # 記錄原始第一行

        # 提取費用
        fee_match = re.search(r'《\s*(\d+)\s*》', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100
            except ValueError: logger.warning(f"Xinyuan Parser: 無法解析費用 '{fee_match.group(1)}'")

        # 提取名字部分：去掉費用標籤、(new)標籤，直到可能的身材信息或行尾
        name_part = re.sub(r'^\s*《\s*\d+\s*》\s*(\(new\))?\s*', '', first_line).strip()

        # 嘗試在名字部分結尾處查找身材信息 (格式: 168.45.C)
        size_match_in_first = re.search(r'(\d{3}\.\d{2,3}\.[A-Za-z\+\-]+)$', name_part) # $確保在結尾

        if size_match_in_first:
            # 如果找到，名字是身材信息之前的部分
            name = name_part[:size_match_in_first.start()].strip()
            # 解析身材
            size_str = size_match_in_first.group(1)
            parts = size_str.split('.')
            if len(parts) == 3:
                try: height = int(parts[0])
                except ValueError: pass
                try: weight = int(parts[1])
                except ValueError: pass
                cup = parts[2].strip()
                size_found = True
        else:
             # 如果第一行末尾沒有身材信息，則整個 name_part 視為名字 (可能需要清理末尾非字母數字)
             # 清理掉末尾可能的符號或表情符號
             name_part_cleaned = re.sub(r'[^\w\s]+$', '', name_part).strip()
             name = name_part_cleaned

        if not name:
             logger.warning(f"Xinyuan Parser: 無法從 '{first_line}' 解析名字")
             return None # 如果連名字都解析不到，則此區塊無效

        line_index += 1 # 移到下一行

        # 2. 循環處理後續所有行
        while line_index < len(block_lines):
            current_line = block_lines[line_index].strip()

            # a. 檢查是否是下一區塊的開始行
            if re.match(xinyuan_block_start_pattern, current_line):
                 break # 停止處理當前區塊

            is_processed_structurally = False # 標記當前行是否被識別為結構化信息

            # b. 嘗試匹配時段 (如果還沒找到)
            if not time_found:
                if current_line == '🈵️' or current_line == '🈵':
                    time_slots_str = "預約滿"
                    time_found = True
                    is_processed_structurally = True
                elif current_line.startswith('人到再約') or current_line.startswith('人到在約'):
                    time_display = "人到再約"
                    extra_info_match = re.search(r'[\(（](.*?)[\)）]', current_line)
                    if extra_info_match:
                        other_lines.append(f"(備註: {extra_info_match.group(1).strip()})")
                    time_slots_str = time_display # 設置為 "人到再約"
                    time_found = True
                    is_processed_structurally = True
                elif re.search(r'\d', current_line): # 只要包含數字就可能是時段行
                    cleaned_time_info = re.sub(r'[^\d-]+', '', current_line)
                    slots = cleaned_time_info.split('-') # 按 '-' 分割
                    processed_slots = []; valid_time_line = False
                    for s in slots:
                        s_num_part = re.search(r'\d+', s) # 提取數字部分
                        if s_num_part:
                            s_val = s_num_part.group(0)
                            try:
                                s_corrected = s_val[:2] if len(s_val) > 2 else s_val
                                num = int(s_corrected)
                                internal_value = -1
                                if 12 <= num <= 23: internal_value = num
                                elif num == 24: internal_value = 100
                                elif 0 <= num <= 5: internal_value = num + 100
                                if internal_value != -1:
                                    processed_slots.append(internal_value); valid_time_line = True
                            except ValueError: pass # 忽略無法轉換的數字
                    if valid_time_line:
                         processed_slots = sorted(list(set(processed_slots))) # 去重並排序
                         time_slots_str = ".".join(map(str, processed_slots)) if processed_slots else ""
                         time_found = True
                         is_processed_structurally = True


            # c. 嘗試匹配身材 (如果第一行沒找到 且 未被處理為時段)
            if not size_found and not is_processed_structurally:
                size_match = re.match(r'^\s*(\d{3})\s*\.\s*(\d{2,3})\s*\.\s*([A-Za-z\+\-]+)\s*$', current_line)
                if size_match:
                    try: height = int(size_match.group(1))
                    except ValueError: pass
                    try: weight = int(size_match.group(2))
                    except ValueError: pass
                    cup = size_match.group(3).strip()
                    size_found = True
                    is_processed_structurally = True


            # d. 如果未被結構化處理，則加入 other_lines
            if not is_processed_structurally and current_line:
                other_lines.append(current_line)

            line_index += 1 # 處理下一行

        # 3. 合併介紹文本
        full_introduction = "\n".join(other_lines).strip()

        # 4. 返回結果
        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': None, # 芯苑格式不明顯有別名
                'height': height, 'weight': weight, 'cup': cup,
                'introduction': full_introduction, 'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"處理芯苑館區塊時出錯: {block_lines}", exc_info=True)
        return None

# ============================================================
# --- 函數 4: 解析新的 "手中情" 格式 (格式 D) ---
# ============================================================
def parse_shouzhongqing_schedule(text):
    """
    解析 "手中情" 格式的 LINE 文字班表。
    返回與 parse_line_schedule 相同結構的列表。
    """
    results = []
    lines = text.strip().split('\n')
    current_block_lines = []
    # 手中情區塊開始模式：(數字)
    block_start_pattern = r'^\(\s*\d+\s*\)'

    for line in lines:
        line_strip = line.strip()
        if not line_strip: continue # 跳過空行

        if re.match(block_start_pattern, line_strip):
            if current_block_lines:
                parsed = process_shouzhongqing_block(current_block_lines) # <--- 調用手中情的處理函數
                if parsed: results.append(parsed)
            current_block_lines = [line_strip]
        elif current_block_lines:
            current_block_lines.append(line_strip)

    if current_block_lines:
        parsed = process_shouzhongqing_block(current_block_lines) # <--- 調用手中情的處理函數
        if parsed: results.append(parsed)

    return results

def process_shouzhongqing_block(block_lines):
    """處理單個 "手中情" 格式的美容師區塊"""
    if not block_lines: return None

    fee = None; name = None; original_name_text = ""; alias_suggestion = None
    time_slots_str = ""; height = None; weight = None; cup = None
    other_lines = [] # 收集所有非結構化行
    shouzhongqing_block_start_pattern = r'^\(\s*\d+\s*\)' # 用於判斷區塊結束
    # 別名模式：匹配 (原XXX) 或 (85XXX) 等 - 手中情格式可能需要保留別名
    alias_pattern = r'[\(（](原.+?|85.+?)[\)）]'

    # 標記信息是否已找到
    time_found = False
    size_found = False

    line_index = 0
    try:
        # 1. 處理第一行 (費用、名字、別名、可能的身材)
        first_line = block_lines[line_index]
        original_name_text = first_line # 記錄原始第一行

        # 提取費用
        fee_match = re.search(r'^\(\s*(\d+)\s*\)', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100
            except ValueError: logger.warning(f"Shouzhongqing Parser: 無法解析費用 '{fee_match.group(1)}'")

        # 提取名字部分：從 ')' 後面開始，直到 👙 或行尾
        name_part_match = re.search(r'\)\s*(.*?)(?:\s*👙|$)', first_line)
        if name_part_match:
            name_part = name_part_match.group(1).strip()

            # 嘗試從名字部分提取別名
            alias_match = re.search(alias_pattern, name_part)
            if alias_match:
                 alias_content = alias_match.group(1).strip()
                 if alias_content.startswith("原"):
                      alias_suggestion = alias_content[1:].strip()
                 else:
                      alias_suggestion = alias_content # 非 "原" 開頭也算別名
                 name = re.sub(alias_pattern, '', name_part).strip()
            else:
                name = name_part

            if not name and alias_suggestion:
                 name = alias_suggestion
                 alias_suggestion = None

            # 嘗試在第一行結尾處查找身材信息 (在 👙 後面，格式: 168 / 45 / C)
            size_match_in_first = re.search(r'👙\s*(\d{3})\s*/\s*(\d{2,3})\s*/\s*([A-Za-z\+\-]+)', first_line)
            if size_match_in_first:
                try: height = int(size_match_in_first.group(1))
                except ValueError: pass
                try: weight = int(size_match_in_first.group(2))
                except ValueError: pass
                cup = size_match_in_first.group(3).strip()
                size_found = True
        else:
             logger.warning(f"Shouzhongqing Parser: 無法從 '{first_line}' 解析名字部分")
             name = None # 設為 None

        if not name:
             logger.warning(f"Shouzhongqing Parser: 無法從 '{first_line}' 解析名字")
             return None # 名字是必須的

        line_index += 1 # 移到下一行

        # 2. 循環處理後續所有行
        while line_index < len(block_lines):
            current_line = block_lines[line_index].strip()

            # a. 檢查是否是下一區塊的開始行
            if re.match(shouzhongqing_block_start_pattern, current_line):
                 break # 停止處理當前區塊

            is_processed_structurally = False # 標記當前行是否被識別為結構化信息

            # b. 嘗試匹配時段 (如果還沒找到，以 ⏰ 開頭)
            if not time_found and current_line.startswith('⏰'):
                time_info = current_line.replace('⏰', '').strip()
                if time_info == '🈵' or time_info == '🈵️':
                    time_slots_str = "預約滿"
                elif time_info == '人到再約':
                    time_slots_str = "人到再約"
                elif not time_info: # 可能是空的 ⏰
                    time_slots_str = ""
                else:
                    slots = re.findall(r'\d+', time_info) # 直接提取所有數字
                    processed_slots = []
                    for s in slots:
                        try:
                            num = int(s); internal_value = -1
                            if 12 <= num <= 23: internal_value = num
                            elif num == 24: internal_value = 100
                            elif 0 <= num <= 5: internal_value = num + 100
                            if internal_value != -1: processed_slots.append(internal_value)
                        except ValueError: pass
                    processed_slots = sorted(list(set(processed_slots))) # 去重並排序
                    time_slots_str = ".".join(map(str, processed_slots)) if processed_slots else ""
                time_found = True
                is_processed_structurally = True


            # c. 嘗試匹配身材 (如果第一行沒找到 且 未被處理為時段)
            if not size_found and not is_processed_structurally:
                size_match = re.match(r'^\s*(\d{3})\s*/\s*(\d{2,3})\s*/\s*([A-Za-z\+\-]+)\s*$', current_line)
                if size_match:
                    try: height = int(size_match.group(1))
                    except ValueError: pass
                    try: weight = int(size_match.group(2))
                    except ValueError: pass
                    cup = size_match.group(3).strip()
                    size_found = True
                    is_processed_structurally = True


            # d. 如果未被結構化處理，則加入 other_lines
            if not is_processed_structurally and current_line:
                # 檢查介紹行中是否包含別名，如果第一行沒找到，則記錄
                if not alias_suggestion:
                    alias_match_intro = re.search(alias_pattern, current_line)
                    if alias_match_intro:
                        alias_content = alias_match_intro.group(1).strip()
                        if alias_content.startswith("原"):
                            alias_suggestion = alias_content[1:].strip()
                        else:
                            alias_suggestion = alias_content
                other_lines.append(current_line)

            line_index += 1 # 處理下一行

        # 3. 合併介紹文本
        full_introduction = "\n".join(other_lines).strip()

        # 4. 返回結果
        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': alias_suggestion, 'height': height, 'weight': weight, # 保留手中情可能需要的別名
                'cup': cup, 'introduction': full_introduction,
                'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"處理手中情區塊時出錯: {block_lines}", exc_info=True)
        return None

# ============================================================
# --- 函數 5: 解析新的 "寶可夢" 格式 (格式 F) ---
# ============================================================
def parse_pokemon_schedule(text):
    """
    解析 "寶可夢" 格式的 LINE 文字班表。
    返回與 parse_line_schedule 相同結構的列表。
    """
    results = []
    lines = text.strip().split('\n')
    current_block_lines = []
    # 寶可夢區塊開始模式：以 (數字) 開頭，允許包含 🆕 或其他符號
    block_start_pattern = r'^\s*(?:🆕|new|\(new\))?\s*\(\s*\d+\s*\)' # 更寬鬆的匹配開頭

    for line in lines:
        line_strip = line.strip()
        if not line_strip: continue # 跳過空行

        if re.match(block_start_pattern, line_strip):
            if current_block_lines:
                parsed = process_pokemon_block(current_block_lines) # <--- 調用寶可夢的處理函數
                if parsed: results.append(parsed)
            current_block_lines = [line_strip]
        elif current_block_lines:
            current_block_lines.append(line_strip)

    if current_block_lines:
        parsed = process_pokemon_block(current_block_lines) # <--- 調用寶可夢的處理函數
        if parsed: results.append(parsed)

    return results

def process_pokemon_block(block_lines):
    """處理單個 "寶可夢" 格式的美容師區塊"""
    if not block_lines: return None

    fee = None; name = None; original_name_text = ""; alias_suggestion = None
    time_slots_str = ""; height = None; weight = None; cup = None
    other_lines = [] # 收集所有非結構化行
    pokemon_block_start_pattern = r'^\s*(?:🆕|new|\(new\))?\s*\(\s*\d+\s*\)'
    # 別名模式 - 寶可夢格式可能需要保留別名
    alias_pattern = r'[\(（](原.+?|85.+?|茶湯會.+?)[\)）]'

    # 標記信息是否已找到
    time_found = False
    size_found = False

    line_index = 0
    try:
        # 1. 處理第一行 (費用、名字、別名、可能的身材)
        first_line = block_lines[line_index]
        original_name_text = first_line # 記錄原始第一行

        fee_match = re.search(r'\(\s*(\d+)\s*\)', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100
            except ValueError: logger.warning(f"Pokemon Parser: 無法解析費用 '{fee_match.group(1)}'")

        name_part = re.sub(r'^\s*(?:🆕|new|\(new\))?\s*\(\s*\d+\s*\)\s*', '', first_line).strip()
        size_match_in_first = re.search(r'(\d{3}\s*\.\s*\d{2,3}\s*\.\s*[A-Za-z\+\-]+)', name_part)

        if size_match_in_first:
            name = name_part[:size_match_in_first.start()].strip()
            size_str = size_match_in_first.group(1)
            parts = re.split(r'\s*\.\s*', size_str) # 用點分割，允許空格
            if len(parts) == 3:
                try: height = int(parts[0])
                except ValueError: pass
                try: weight = int(parts[1])
                except ValueError: pass
                cup = parts[2].strip()
                size_found = True
        else:
             alias_match = re.search(alias_pattern, name_part)
             if alias_match:
                 alias_content = alias_match.group(1).strip()
                 if alias_content.startswith("原"):
                      alias_suggestion = alias_content[1:].strip()
                 else:
                      alias_suggestion = alias_content
                 name = re.sub(alias_pattern, '', name_part).strip()
             else:
                 name = re.sub(r'[^\w\s]+$', '', name_part).strip()

        if not name and alias_suggestion:
            name = alias_suggestion
            alias_suggestion = None

        if not name:
             logger.warning(f"Pokemon Parser: 無法從 '{first_line}' 解析名字")
             return None # 名字是必須的

        line_index += 1 # 移到下一行

        # 2. 循環處理後續所有行
        while line_index < len(block_lines):
            current_line = block_lines[line_index].strip()

            if re.match(pokemon_block_start_pattern, current_line):
                 break # 停止處理當前區塊

            is_processed_structurally = False # 標記當前行是否被識別為結構化信息

            # b. 嘗試匹配時段 (如果還沒找到，以 🈳 開頭 或 單獨為 🈵)
            if not time_found:
                if current_line.startswith('🈳'):
                    time_info = current_line.replace('🈳', '').strip()
                    if time_info == '🈵' or time_info == '🈵️':
                        time_slots_str = "預約滿"
                    elif not time_info: # 可能是空的 🈳
                        time_slots_str = ""
                    else:
                        slots = re.findall(r'\d+', time_info) # 直接提取所有數字
                        processed_slots = []
                        for s in slots:
                            try:
                                num = int(s); internal_value = -1
                                if 12 <= num <= 23: internal_value = num
                                elif num == 24: internal_value = 100
                                elif 0 <= num <= 5: internal_value = num + 100
                                if internal_value != -1: processed_slots.append(internal_value)
                            except ValueError: pass
                        processed_slots = sorted(list(set(processed_slots))) # 去重並排序
                        time_slots_str = ".".join(map(str, processed_slots)) if processed_slots else ""
                    time_found = True
                    is_processed_structurally = True
                elif current_line == '🈵' or current_line == '🈵️': # 處理單獨的 🈵 行
                     time_slots_str = "預約滿"
                     time_found = True
                     is_processed_structurally = True


            # c. 嘗試匹配身材 (如果第一行沒找到 且 未被處理為時段)
            if not size_found and not is_processed_structurally:
                size_match = re.match(r'^\s*(\d{3})\s*\.\s*(\d{2,3})\s*\.\s*([A-Za-z\+\-]+)\s*$', current_line)
                if size_match:
                    try: height = int(size_match.group(1))
                    except ValueError: pass
                    try: weight = int(size_match.group(2))
                    except ValueError: pass
                    cup = size_match.group(3).strip()
                    size_found = True
                    is_processed_structurally = True


            # d. 如果未被結構化處理，則加入 other_lines
            if not is_processed_structurally and current_line:
                 # 檢查介紹行中是否包含別名，如果第一行沒找到，則記錄
                 if not alias_suggestion:
                     alias_match_intro = re.search(alias_pattern, current_line)
                     if alias_match_intro:
                         alias_content = alias_match_intro.group(1).strip()
                         if alias_content.startswith("原"):
                             alias_suggestion = alias_content[1:].strip()
                         else:
                             alias_suggestion = alias_content
                 other_lines.append(current_line)


            line_index += 1 # 處理下一行

        # 3. 合併介紹文本
        full_introduction = "\n".join(other_lines).strip()

        # 4. 返回結果
        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': alias_suggestion, 'height': height, 'weight': weight, # 保留寶可夢可能需要的別名
                'cup': cup, 'introduction': full_introduction,
                'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"處理寶可夢區塊時出錯: {block_lines}", exc_info=True)
        return None


# ============================================================
# --- *** 函數 6: 解析新的 "愛寶館" 格式 (格式 G - Aibao) *** ---
# ============================================================
# --- *** 使用優化後的 parse_aibao_schedule *** ---
def parse_aibao_schedule(text):
    """
    解析 "愛寶館" 格式的 LINE 文字班表。
    返回與 parse_line_schedule 相同結構的列表。
    採用更健壯的區塊分割邏輯。
    """
    results = []
    lines = text.strip().split('\n')
    if not lines:
        return results

    # 愛寶區塊開始模式：(數字) 或 (new)(數字)，考慮前後空格和全半形括號
    block_start_pattern = r'^\s*(?:\(new\)|（new）)?\s*[\(（]\s*\d+\s*[\)）]'
    start_indices = []

    # 1. 找到所有區塊開始行的索引
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if not line_strip: continue # 跳過空行
        if re.match(block_start_pattern, line_strip):
            start_indices.append(i)

    if not start_indices:
        logger.warning("Aibao Parser: No block start lines found using pattern: %s", block_start_pattern)
        # 作為備用，嘗試一個更簡單的模式，僅查找行首的 (數字) 或 （數字）
        block_start_pattern_fallback = r'^\s*[\(（]\s*\d+\s*[\)）]'
        for i, line in enumerate(lines):
             line_strip = line.strip()
             if not line_strip: continue
             if re.match(block_start_pattern_fallback, line_strip):
                  start_indices.append(i)
        if not start_indices:
             logger.error("Aibao Parser: Still no block start lines found even with fallback pattern.")
             return results # 如果還是找不到，返回空

    # 2. 根據開始行索引分割區塊
    num_blocks = len(start_indices)
    for i in range(num_blocks):
        start_index = start_indices[i]
        # 結束索引是下一個開始行的索引，或者是列表的末尾
        end_index = start_indices[i+1] if (i + 1) < num_blocks else len(lines)

        # 獲取當前區塊的所有行 (從 start_index 到 end_index 之前)
        current_block_lines = [lines[j] for j in range(start_index, end_index)]

        # 過濾掉純粹的空行或只有空格的行
        current_block_lines_cleaned = [line for line in current_block_lines if line.strip()]

        if current_block_lines_cleaned:
            parsed = process_aibao_block(current_block_lines_cleaned) # <--- 調用愛寶館的處理函數
            if parsed:
                results.append(parsed)
            else:
                logger.warning(f"Aibao Parser: Failed to process block starting at line {start_index+1}: {current_block_lines_cleaned[0] if current_block_lines_cleaned else 'EMPTY'}")
        else:
            logger.debug(f"Aibao Parser: Skipping empty block found between lines {start_index} and {end_index}")

    return results

# --- process_aibao_block 函數 (移除括號清理，別名視為介紹) ---
def process_aibao_block(block_lines):
    """處理單個 "愛寶館" 格式的美容師區塊（移除括號清理，別名視為介紹）"""
    if not block_lines: return None

    fee = None; name = None; original_name_text = ""; # No alias_suggestion needed
    time_slots_str = ""; height = None; weight = None; cup = None
    other_lines = [] # 收集介紹行

    # Patterns
    size_pattern_for_match = r'\(?\s*(\d{3})\s*[./\s]\s*(\d{2,3})\s*[./\s]\s*([A-Za-z\+\-]+)\s*\)?' # Adjusted to handle space/dot/slash
    # Patterns to check if a line *only* contains specific info
    size_only_pattern = r'^\s*' + r'\(?\s*\d{3}\s*[./\s]\s*\d{2,3}\s*[./\s]\s*[A-Za-z\+\-]+\s*\)?' + r'\s*$'
    time_only_pattern = r'^\s*(?:🈵+|[\d\.\s]+)\s*$'

    # Flags
    time_found = False
    size_found = False # Tracks if size info has been found *anywhere* in the block

    try:
        # 1. Process First Line (Fee, Name, Potential Time)
        first_line = block_lines[0].strip()
        original_name_text = first_line

        fee_match = re.search(r'[\(（]\s*(\d+)\s*[\)）]', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100
            except ValueError: logger.warning(f"Aibao Parser: Cannot parse fee '{fee_match.group(1)}' from '{first_line}'")

        content_part = re.sub(r'^\s*(?:\(new\)|（new）)?\s*[\(（]\s*\d+\s*[\)）]\s*', '', first_line).strip()
        time_match = re.search(r'((?:[\d]+\.?)+|🈵+)\s*$', content_part)

        if time_match:
            name_part = content_part[:time_match.start()].strip()
            time_info = time_match.group(1).strip()
            if '🈵' in time_info:
                 time_slots_str = "預約滿"
            else:
                 slots = re.findall(r'\d+', time_info)
                 processed_slots = []; valid_time_line_f1 = False
                 for s in slots:
                     try:
                         num = int(s); internal_value = -1
                         if 12 <= num <= 23: internal_value = num
                         elif num == 24: internal_value = 100
                         elif 0 <= num <= 11: internal_value = num + 100
                         if internal_value != -1: processed_slots.append(internal_value); valid_time_line_f1 = True
                     except ValueError: pass
                 if valid_time_line_f1:
                      processed_slots.sort(); time_slots_str = ".".join(map(str, processed_slots))
                 else: time_slots_str = ""
            time_found = True
            name = re.sub(r'\W+$', '', name_part).strip()
        else:
            name_part = content_part.strip()
            name = re.sub(r'\W+$', '', name_part).strip()

        if not name:
             logger.warning(f"Aibao Parser: Could not parse name from first line: '{first_line}'")

        # 2. Process Subsequent Lines
        for i in range(1, len(block_lines)):
            current_line = block_lines[i].strip()
            if not current_line: continue

            # --- Reset flags for the current line ---
            contains_time_this_line = False
            contains_size_this_line = False
            is_only_time = False
            is_only_size = False
            local_size_match_obj = None # Store the match object for this line

            # --- Check Time ---
            if not time_found:
                is_time_line = False # Local flag for this line
                if '🈵' in current_line:
                    time_slots_str = "預約滿"; time_found = True; is_time_line = True
                elif re.match(r'^[\d\.\s]+$', current_line):
                    slots = re.findall(r'\d+', current_line)
                    processed_slots = []; valid_time_line_sub = False
                    for s in slots:
                        try:
                            num = int(s); internal_value = -1
                            if 12 <= num <= 23: internal_value = num
                            elif num == 24: internal_value = 100
                            elif 0 <= num <= 11: internal_value = num + 100
                            if internal_value != -1: processed_slots.append(internal_value); valid_time_line_sub = True
                        except ValueError: pass
                    if valid_time_line_sub:
                        processed_slots.sort(); time_slots_str = ".".join(map(str, processed_slots)); time_found = True; is_time_line = True
                    else: time_slots_str = ""
                if is_time_line:
                    contains_time_this_line = True
                    if re.match(time_only_pattern, current_line):
                        is_only_time = True

            # --- Check Size ---
            local_size_match = re.search(size_pattern_for_match, current_line)
            if local_size_match:
                contains_size_this_line = True
                local_size_match_obj = local_size_match # Store match object
                if not size_found: # Store globally if first time
                    try: height = int(local_size_match.group(1))
                    except ValueError: pass
                    try: weight = int(local_size_match.group(2))
                    except ValueError: pass
                    cup = local_size_match.group(3).strip()
                    size_found = True
                if re.match(size_only_pattern, current_line):
                    is_only_size = True

            # --- Alias Check Removed ---

            # --- Decide if line contributes to Introduction ---
            # Now, only exclude lines that are purely time or purely size
            is_purely_structural_line = is_only_time or is_only_size

            if not is_purely_structural_line:
                # This line contains introduction text, potentially mixed with size.
                intro_text_candidate = current_line

                # Remove the matched *size* part if it was found ON THIS LINE and mixed with intro
                if contains_size_this_line and local_size_match_obj and not is_only_size:
                    intro_text_candidate = intro_text_candidate.replace(local_size_match_obj.group(0), '')

                # Clean up remaining whitespace and artifacts like empty brackets
                intro_text_candidate = intro_text_candidate.strip()
                intro_text_candidate = re.sub(r'\(\s*\)', '', intro_text_candidate) # Remove ()
                intro_text_candidate = re.sub(r'（\s*）', '', intro_text_candidate) # Remove （）
                intro_text_candidate = re.sub(r'\(\s+\)', '', intro_text_candidate) # Remove ( )
                intro_text_candidate = re.sub(r'（\s+）', '', intro_text_candidate) # Remove （ ）
                # *** REMOVED the lines that removed leading/trailing brackets unconditionally ***
                intro_text_candidate = intro_text_candidate.strip() # Strip again after potential removals


                # Add to introduction list if there's meaningful text left
                if intro_text_candidate:
                    other_lines.append(intro_text_candidate)


        # 3. Finalize and Return
        full_introduction = "\n".join(other_lines).strip()

        # Always return alias_suggestion as None for Aibao format now
        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': None, # Explicitly None
                'height': height, 'weight': weight,
                'cup': cup, 'introduction': full_introduction,
                'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"Error processing Aibao block: {block_lines}", exc_info=True)
        return None


# ============================================================
# --- *** 函數 7: 解析新的 "含香館" 格式 (格式 H - Hanxiang) *** ---
# ============================================================
def parse_hanxiang_schedule(text):
    """
    解析 "含香館" 格式的 LINE 文字班表。
    使用與 Aibao 類似的健壯區塊分割邏輯。
    """
    results = []
    lines = text.strip().split('\n')
    if not lines:
        return results

    # 含香區塊開始模式：(數字) 或 🆕(數字)，考慮前後空格和全半形括號
    block_start_pattern = r'^\s*(?:🆕)?\s*[\(（]\s*\d+\s*[\)）]'
    start_indices = []

    # 1. 找到所有區塊開始行的索引
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if not line_strip: continue
        if re.match(block_start_pattern, line_strip):
            start_indices.append(i)

    if not start_indices:
        logger.error("Hanxiang Parser: No block start lines found.")
        return results

    # 2. 根據開始行索引分割區塊
    num_blocks = len(start_indices)
    for i in range(num_blocks):
        start_index = start_indices[i]
        end_index = start_indices[i+1] if (i + 1) < num_blocks else len(lines)
        current_block_lines = [lines[j] for j in range(start_index, end_index)]
        current_block_lines_cleaned = [line for line in current_block_lines if line.strip()]

        if current_block_lines_cleaned:
            parsed = process_hanxiang_block(current_block_lines_cleaned) # <--- 調用含香館的處理函數
            if parsed:
                results.append(parsed)
            else:
                logger.warning(f"Hanxiang Parser: Failed to process block starting at line {start_index+1}: {current_block_lines_cleaned[0] if current_block_lines_cleaned else 'EMPTY'}")
        else:
            logger.debug(f"Hanxiang Parser: Skipping empty block found between lines {start_index} and {end_index}")

    return results

# --- process_hanxiang_block 函數 (修正版：保留 ◆) ---
def process_hanxiang_block(block_lines):
    """處理單個 "含香館" 格式的美容師區塊（修正版：保留 ◆）"""
    if not block_lines or len(block_lines) < 2: # 至少需要第一行和最後時段行
        logger.warning(f"Hanxiang Parser: Block too short or empty: {block_lines}")
        return None

    fee = None; name = None; original_name_text = ""; alias_suggestion = None
    time_slots_str = ""; height = None; weight = None; cup = None
    intro_lines = []

    # 別名模式: (地點 名字) e.g., (寶可夢 小羽), (紐約 秘書)
    alias_pattern = r'[\(（]([\u4e00-\u9fa5\w]+\s+[^）\)]+)[\)）]'
    # 身材模式: XXX/XX/X 或 XXX.XX.X (允許空格和括號)
    size_pattern = r'\(?\s*(\d{3})\s*[./]\s*(\d{2,3})\s*[./]\s*([A-Za-z\+\(\)]+)\s*\)?' # 加入對括號的兼容性

    try:
        # 1. Process First Line (Fee, Name, Size, Alias)
        first_line = block_lines[0].strip()
        original_name_text = first_line

        fee_match = re.search(r'[\(（]\s*(\d+)\s*[\)）]', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100
            except ValueError: logger.warning(f"Hanxiang Parser: Cannot parse fee '{fee_match.group(1)}' from '{first_line}'")

        # Extract content after fee and potential 🆕 tag
        content_after_fee = re.sub(r'^\s*(?:🆕)?\s*[\(（]\s*\d+\s*[\)）]\s*', '', first_line).strip()

        # Try to extract alias from the end first
        alias_match = re.search(alias_pattern + r'\s*$', content_after_fee)
        name_and_size_part = content_after_fee # Default
        if alias_match:
            alias_full_text = alias_match.group(1).strip()
            parts = alias_full_text.split(maxsplit=1)
            if len(parts) == 2:
                 known_prefixes = ["寶可夢", "紐約", "芯苑", "85"] # 可擴展
                 if parts[0] in known_prefixes: alias_suggestion = parts[1]
                 else: alias_suggestion = parts[1] # Assume second part is alias name
            else: alias_suggestion = alias_full_text
            name_and_size_part = content_after_fee[:alias_match.start()].strip()

        # Try to extract size from the remaining part
        size_match = re.search(size_pattern, name_and_size_part)
        name_part = name_and_size_part # Default
        if size_match:
            try: height = int(size_match.group(1))
            except ValueError: pass
            try: weight = int(size_match.group(2))
            except ValueError: pass
            cup_raw = size_match.group(3).strip(); cup = re.sub(r'[\(\)]', '', cup_raw) # Clean brackets from cup
            # Remove size part to get name
            name_part = name_and_size_part[:size_match.start()].strip() + name_and_size_part[size_match.end():].strip()
            name_part = name_part.strip() # Clean spaces left

        # Clean name: remove trailing non-word characters (like potential emojis)
        name = re.sub(r'[^\w\s]+$', '', name_part).strip()

        if not name:
             logger.warning(f"Hanxiang Parser: Could not parse name from first line: '{first_line}' (after processing fee/alias/size)")

        # 2. Process Middle Lines (Introduction)
        # Iterate from the second line up to the second-to-last line
        for i in range(1, len(block_lines) - 1):
            line = block_lines[i].strip() # Strip surrounding whitespace only
            if line:
                # Directly append the stripped line, keeping the leading ◆
                intro_lines.append(line) # *** Keep the line as is ***

        # 3. Process Last Line (Time)
        last_line = block_lines[-1].strip()
        if '🈵' in last_line:
            time_slots_str = "預約滿"
        elif re.match(r'^[\d\.\s]+$', last_line): # Check if it looks like time slots
            slots = re.findall(r'\d+', last_line)
            processed_slots = []
            valid_time_line_last = False
            for s in slots:
                try:
                    num = int(s); internal_value = -1
                    if 12 <= num <= 23: internal_value = num
                    elif num == 24: internal_value = 100
                    elif 0 <= num <= 11: internal_value = num + 100
                    if internal_value != -1: processed_slots.append(internal_value); valid_time_line_last = True
                except ValueError: pass
            if valid_time_line_last:
                 processed_slots.sort(); time_slots_str = ".".join(map(str, processed_slots))
            else: time_slots_str = "" # If parsing fails, set to empty
        else:
            time_slots_str = "" # If last line is not recognized as time, set to empty
            logger.warning(f"Hanxiang Parser: Last line not recognized as time: '{last_line}'")
            # Optionally, add the last line to intro if it wasn't time?
            intro_lines.append(last_line) # Append directly without lstrip

        # 4. Finalize and Return
        full_introduction = "\n".join(intro_lines).strip()

        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': alias_suggestion, # Hanxiang has aliases
                'height': height, 'weight': weight,
                'cup': cup, 'introduction': full_introduction,
                'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"Error processing Hanxiang block: {block_lines}", exc_info=True)
        return None


# ============================================================
# --- *** 函數 8: 解析新的 "潘朵拉" 格式 (格式 P - Pandora) *** ---
# ============================================================
def parse_pandora_schedule(text):
    """
    解析 "潘朵拉" 格式的 LINE 文字班表。
    使用與 Aibao/Hanxiang 類似的健壯區塊分割邏輯。
    """
    results = []
    lines = text.strip().split('\n')
    if not lines:
        return results

    # 潘朵拉區塊開始模式：【數字】，前面可能有 emoji
    # Allow potential emojis before the block start pattern
    block_start_pattern = r'^\s*(?:[\U0001F300-\U0001FAFF\s]+)?\s*【\s*\d+\s*】' # Allow emojis/spaces before 【】
    start_indices = []

    # 1. 找到所有區塊開始行的索引
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if not line_strip: continue
        if re.match(block_start_pattern, line_strip):
            start_indices.append(i)
        # Handle edge case where a block might start without the initial emoji line becoming intro
        elif i > 0 and re.match(r'^\s*【\s*\d+\s*】', line_strip) and not re.match(block_start_pattern, lines[i-1].strip()):
             # If this line starts with 【】 but the previous wasn't a start, consider this a start
             start_indices.append(i)


    if not start_indices:
        logger.error("Pandora Parser: No block start lines found using pattern: %s", block_start_pattern)
        return results # Return empty if no blocks found

    # *** REMOVED the faulty refinement logic ***

    # 2. 根據開始行索引分割區塊
    num_blocks = len(start_indices)
    for i in range(num_blocks):
        start_index = start_indices[i]
        end_index = start_indices[i+1] if (i + 1) < num_blocks else len(lines)
        current_block_lines = [lines[j] for j in range(start_index, end_index)]
        current_block_lines_cleaned = [line for line in current_block_lines if line.strip()]

        if current_block_lines_cleaned:
            parsed = process_pandora_block(current_block_lines_cleaned) # <--- 調用潘朵拉的處理函數
            if parsed:
                results.append(parsed)
            else:
                logger.warning(f"Pandora Parser: Failed to process block starting at line {start_index+1}: {current_block_lines_cleaned[0] if current_block_lines_cleaned else 'EMPTY'}")
        else:
            logger.debug(f"Pandora Parser: Skipping empty block found between lines {start_index} and {end_index}")

    return results

# --- process_pandora_block 函數 (v7: 再次修正名字清理) ---
def process_pandora_block(block_lines):
    """處理單個 "潘朵拉" 格式的美容師區塊 (v7: 再次修正名字清理)"""
    if not block_lines or len(block_lines) < 2: # Need at least first line and time line
        logger.warning(f"Pandora Parser: Block too short or empty: {block_lines}")
        return None

    fee = None; name = None; original_name_text = ""; alias_suggestion = None
    time_slots_str = ""; height = None; weight = None; cup = None
    potential_intro_parts = [] # Collect potential intro fragments

    # Patterns
    size_pattern = r'\(?\s*(\d{3})\s*[./\s]\s*(\d{2,3})\s*[./\s]\s*([A-Za-z\+\(\)]+)\s*\)?'
    specific_alias_pattern = r'[\(（](?:(原)\s*|([\u4e00-\u9fa5\w]+)\s+)([^）\)]+)[\)）]'
    desc_pattern = r'<([^>]+)>'
    service_tag_pattern = r'約\s*(\([\w\s]+\)|\（[\w\s]+\）)(\s*\([\w\s]+\)|\s*（[\w\s]+\）)*'
    emoji_placeholder_pattern = r'[\(（]\s*emoji\s*[\)）]' # For cleaning like (emoji)
    # General bracket pattern for cleaning name part, including specific cases like (v)(i)(p)
    general_bracket_pattern_for_name_cleaning = r'\s*[\(（][^)）>]*[\)）]\s*'


    found_size_str = None
    found_alias_str = None

    try:
        # 1. Process First Line - Get Fee and Initial Content
        first_line = block_lines[0].strip(); original_name_text = first_line

        fee_match = re.search(r'【\s*(\d+)\s*】', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100
            except ValueError: logger.warning(f"Pandora Parser: Cannot parse fee '{fee_match.group(1)}' from '{first_line}'")

        content_after_fee = re.sub(r'^\s*(?:[\U0001F300-\U0001FAFF\s]+)?\s*【\s*\d+\s*】\s*', '', first_line).strip()

        # --- v7 Name Extraction: Match initial CJK/Letters/Digits ---
        name_part = ""
        remainder_first_line = content_after_fee # Default if no name match
        # Match initial sequence of CJK chars, English letters, OR digits
        name_match = re.match(r'^([\u4e00-\u9fffA-Za-z0-9]+)', content_after_fee)
        if name_match:
             name_part = name_match.group(1).strip() # Extract the core name part
             remainder_first_line = content_after_fee[name_match.end():].strip() # Get everything after
        else: # Fallback if name doesn't start with expected characters
             logger.warning(f"Pandora Parser: Name doesn't start with expected chars in: '{content_after_fee}'. Trying split by space.")
             parts = content_after_fee.split(maxsplit=1)
             if parts:
                 name_part = parts[0] # Assume first part is name
                 if len(parts) > 1: remainder_first_line = parts[1]
             else: # If content_after_fee was empty or un-splittable
                  name_part = ""
                  remainder_first_line = content_after_fee


        # Clean the extracted name_part vigorously
        name = name_part.strip()
        name = re.sub(r'[\U0001F300-\U0001FAFF]', '', name).strip() # Clean standard emojis
        # *** Clean ANY bracketed content from the potential name part ***
        name = re.sub(general_bracket_pattern_for_name_cleaning, '', name).strip()
        name = re.sub(r'[^\w]+$', '', name).strip() # Clean trailing non-word chars

        if not name:
             logger.error(f"Pandora Parser: Failed to extract name for block: '{first_line}'")
             # Consider fallback using alias later if needed

        # 2. Process Last Line - Get Time
        last_line = block_lines[-1].strip()
        time_slots_str = ""
        last_line_is_time = False
        trailing_intro_last_line = ""

        if last_line.startswith('🈳') or last_line.startswith('🈵'):
            last_line_is_time = True
            time_marker = '🈳' if last_line.startswith('🈳') else '🈵'
            content_after_marker = last_line.replace(time_marker, '', 1).strip()
            if time_marker == '🈵':
                time_slots_str = "預約滿"
                trailing_intro_last_line = content_after_marker
            else: # Starts with 🈳
                time_match_last = re.match(r'([\d\.\s]+)', content_after_marker)
                if time_match_last:
                    time_part = time_match_last.group(1)
                    slots = re.findall(r'\d+', time_part)
                    processed_slots = []; valid_time_line_last = False
                    for s in slots:
                         try:
                             num = int(s); internal_value = -1
                             if 12 <= num <= 23: internal_value = num
                             elif num == 24: internal_value = 100
                             elif 0 <= num <= 11: internal_value = num + 100
                             if internal_value != -1: processed_slots.append(internal_value); valid_time_line_last = True
                         except ValueError: pass
                    if valid_time_line_last:
                         processed_slots.sort(); time_slots_str = ".".join(map(str, processed_slots))
                    trailing_intro_last_line = content_after_marker[time_match_last.end():].strip()
                else: # Starts with 🈳 but no numbers
                    trailing_intro_last_line = content_after_marker
                    logger.warning(f"Pandora Parser: Last line starts with 🈳 but no valid time found: '{last_line}'")
        else: # Last line not time
            logger.warning(f"Pandora Parser: Last line not recognized as time line: '{last_line}'")


        # 3. Collect All Potential Intro Lines (including remainder of first line)
        all_potential_intro_text = remainder_first_line + "\n" + "\n".join(block_lines[1:-1])
        if not last_line_is_time: all_potential_intro_text += "\n" + last_line
        elif trailing_intro_last_line: all_potential_intro_text += "\n" + trailing_intro_last_line
        all_potential_intro_text = all_potential_intro_text.strip()

        # 4. Globally Find First Size and Specific Alias within potential intro text
        size_match_global = re.search(size_pattern, all_potential_intro_text)
        if size_match_global:
             try: height = int(size_match_global.group(1))
             except ValueError: pass
             try: weight = int(size_match_global.group(2))
             except ValueError: pass
             cup_raw = size_match_global.group(3).strip(); cup = re.sub(r'[\(\)]', '', cup_raw)
             found_size_str = size_match_global.group(0) # Store the exact string found

        alias_match_global = re.search(specific_alias_pattern, all_potential_intro_text)
        if alias_match_global:
            is_original = alias_match_global.group(1)
            location = alias_match_global.group(2)
            alias_name_part = alias_match_global.group(3).strip()
            if is_original or (location and location in ["芯苑", "含香", "寶可夢", "紐約", "85"]):
                 alias_suggestion = alias_name_part
                 found_alias_str = alias_match_global.group(0) # Store the exact alias string found


        # 5. Build Final Introduction (Cleaned)
        final_intro_text = all_potential_intro_text

        # Remove the globally found size and alias strings
        try:
            if found_size_str: final_intro_text = final_intro_text.replace(found_size_str, '')
        except TypeError: pass # Ignore if None
        try:
            if found_alias_str: final_intro_text = final_intro_text.replace(found_alias_str, '')
        except TypeError: pass # Ignore if None


        # Process description tags <...>
        processed_intro_parts = []
        temp_intro_text = ""
        # Split carefully, handle potential nested or broken tags less likely now
        parts = re.split(r'(<[^>]+>)', final_intro_text)
        for part in parts:
            if not part: continue
            desc_match_part = re.match(r'<([^>]+)>', part)
            if desc_match_part:
                desc_content = desc_match_part.group(1).strip()
                if desc_content:
                    if temp_intro_text: processed_intro_parts.append(temp_intro_text.strip())
                    temp_intro_text = "" # Reset
                    processed_intro_parts.append(desc_content)
            else:
                temp_intro_text += part
        if temp_intro_text: processed_intro_parts.append(temp_intro_text.strip())

        # Rebuild intro, clean emojis and empty brackets/lines
        cleaned_intro_lines = []
        emoji_placeholder_pattern_intro = r'[\(（]\s*emoji\s*[\)）]' # Specific pattern for intro cleaning
        for line in processed_intro_parts:
             cleaned_line = re.sub(r'[\U0001F300-\U0001FAFF]', '', line).strip()
             cleaned_line = re.sub(emoji_placeholder_pattern_intro, '', cleaned_line, flags=re.IGNORECASE).strip()
             cleaned_line = re.sub(r'\(\s*\)|（\s*）|\(\s+\)|（\s+）', '', cleaned_line).strip()
             if cleaned_line:
                 # Remove potential remaining "約 (...)" tags if they weren't cleaned before
                 cleaned_line = re.sub(service_tag_pattern, '', cleaned_line).strip()
                 # Remove potential vip tags like (v)(i)(p) from intro text
                 cleaned_line = re.sub(r'(\([a-zA-Z]\))+', '', cleaned_line).strip()
                 if cleaned_line:
                     cleaned_intro_lines.append(cleaned_line)

        full_introduction = "\n".join(cleaned_intro_lines)


        # Fallback for name if still not found
        if not name and alias_suggestion:
             name = alias_suggestion
             alias_suggestion = None # Used as name, so clear suggestion


        # Return dictionary, ensuring name exists if possible
        if name:
            return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                    'alias_suggestion': alias_suggestion,
                    'height': height, 'weight': weight,
                    'cup': cup, 'introduction': full_introduction,
                    'time_slots': time_slots_str}
        else:
             logger.warning(f"Pandora Parser: Failed to determine name for block starting with: '{original_name_text}'")
             return None

    except Exception as e:
        logger.error(f"Error processing Pandora block: {block_lines}", exc_info=True)
        return None


# ============================================================
# --- *** 函數 9: 解析新的 "王妃館" 格式 (格式 W - Wangfei) *** ---
# ============================================================
def parse_wangfei_schedule(text):
    """
    解析 "王妃館" 格式的 LINE 文字班表。
    跳過開頭的注意事項，然後使用健壯的區塊分割。
    """
    results = []
    lines = text.strip().split('\n')
    if not lines: return results

    start_parsing_index = 0
    # 王妃區塊開始模式: 名字(非空格開頭) + 空格 + 2位數字費用
    block_start_pattern = r'^\s*([^\s]+(?:\s+[^\s]+)*?)\s+(\d{2})\s*$' # Allow spaces in name
    # 找到第一個符合區塊開始模式的行，之前的都跳過
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if re.match(block_start_pattern, line_strip):
            start_parsing_index = i
            logger.info(f"Wangfei Parser: Found first block start at line {i+1}: '{line_strip}'")
            break
    else: # No block start found at all
        logger.error("Wangfei Parser: No block start pattern found in the entire text.")
        return results

    # Find all block start indices from the parsing start point
    start_indices = []
    for i in range(start_parsing_index, len(lines)):
        line_strip = lines[i].strip()
        if not line_strip: continue
        if re.match(block_start_pattern, line_strip):
            start_indices.append(i)

    if not start_indices:
         logger.error("Wangfei Parser: No block start indices identified after skipping header.")
         return results

    # Split blocks based on indices
    num_blocks = len(start_indices)
    for i in range(num_blocks):
        start_index = start_indices[i]
        end_index = start_indices[i+1] if (i + 1) < num_blocks else len(lines)
        current_block_lines = [lines[j] for j in range(start_index, end_index)]
        current_block_lines_cleaned = [line for line in current_block_lines if line.strip()]

        if current_block_lines_cleaned:
            parsed = process_wangfei_block(current_block_lines_cleaned)
            if parsed:
                results.append(parsed)
            else:
                logger.warning(f"Wangfei Parser: Failed to process block starting at line {start_index+1}: {current_block_lines_cleaned[0] if current_block_lines_cleaned else 'EMPTY'}")
        else:
            logger.debug(f"Wangfei Parser: Skipping empty block found between lines {start_index} and {end_index}")

    return results


def process_wangfei_block(block_lines):
    """處理單個 "王妃館" 格式的美容師區塊"""
    if not block_lines or len(block_lines) < 2: # Name/Fee line + Time line minimum
        logger.warning(f"Wangfei Parser: Block too short or empty: {block_lines}")
        return None

    fee = None; name = None; original_name_text = ""; alias_suggestion = None # No alias expected
    time_slots_str = ""; height = None; weight = None; cup = None # No size expected
    intro_lines = []

    try:
        # 1. Process First Line (Name Fee)
        first_line = block_lines[0].strip()
        original_name_text = first_line # Record the raw first line

        # Match name (non-space chars, allowing spaces within name) followed by space(s) and 2 digits fee
        match = re.match(r'^(.+?)\s+(\d{2})\s*$', first_line) # Use non-greedy match for name
        if match:
            name = match.group(1).strip()
            try:
                fee = int(match.group(2)) * 100
            except ValueError:
                 logger.warning(f"Wangfei Parser: Cannot parse fee '{match.group(2)}' from '{first_line}'")
        else:
            logger.warning(f"Wangfei Parser: Could not parse name/fee from first line: '{first_line}'")
            # Fallback: assume everything before last space(s) + digits is name
            parts = first_line.rsplit(maxsplit=1)
            if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 2:
                 name = parts[0].strip()
                 try: fee = int(parts[1]) * 100
                 except ValueError: pass
                 logger.info(f"Wangfei Parser: Using fallback name/fee parsing for '{first_line}'")
            elif first_line: # If no fee found, maybe just name?
                 name = first_line
                 logger.warning(f"Wangfei Parser: Only name found on first line? '{first_line}'")
            else:
                 return None # Cannot proceed without a name

        # 2. Process Middle Lines (Introduction)
        # Lines between first and last are intro
        for i in range(1, len(block_lines) - 1):
            line = block_lines[i].strip()
            if line:
                intro_lines.append(line)

        # 3. Process Last Line (Time)
        last_line = block_lines[-1].strip()
        if last_line.startswith('⏰'):
            time_info = last_line.replace('⏰', '').strip()
            if '🈵' in time_info: # Handle cases like ⏰🈵
                time_slots_str = "預約滿"
            elif not time_info: # Handle empty ⏰
                 time_slots_str = ""
            else:
                # Time slots separated by '、'
                slots = re.findall(r'\d+', time_info) # Find all numbers
                processed_slots = []
                valid_time_line_last = False
                for s in slots:
                    try:
                        num = int(s); internal_value = -1
                        if 12 <= num <= 23: internal_value = num
                        elif num == 24: internal_value = 100
                        elif 0 <= num <= 11: internal_value = num + 100
                        if internal_value != -1: processed_slots.append(internal_value); valid_time_line_last = True
                    except ValueError: pass
                if valid_time_line_last:
                    processed_slots.sort(); time_slots_str = ".".join(map(str, processed_slots))
                else: time_slots_str = "" # Parsing failed
        else:
             logger.warning(f"Wangfei Parser: Last line does not start with ⏰: '{last_line}'")
             # Treat as intro?
             intro_lines.append(last_line)


        # 4. Finalize and Return
        full_introduction = "\n".join(intro_lines).strip()

        # Wangfei format doesn't have alias, height, weight, cup
        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': None,
                'height': None, 'weight': None,
                'cup': None, 'introduction': full_introduction,
                'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"Error processing Wangfei block: {block_lines}", exc_info=True)
        return None

# ============================================================
# --- *** 函數 10: 解析新的 "樂鑽館" 格式 (格式 L - Lezuan) *** ---
# ============================================================
def parse_lezuan_schedule(text):
    """
    解析 "樂鑽館" 格式的 LINE 文字班表。
    """
    results = []
    lines = text.strip().split('\n')
    if not lines: return results

    # 樂鑽區塊開始模式: 名字 (可能含空格) + 空格 + (費用)單
    # Fee part: (digit/word)(digit)單 e.g., (2)(9)單 or (three)(3)單
    block_start_pattern = r'^\s*([^\s\(（]+(?:\s+[^\s\(（]+)*?)\s+[\(（](?:[\w\d\u4e00-\u9fa5]+)[\)）][\(（]\d+[\)）]單'
    start_indices = []

    # 1. Find all block start indices
    for i, line in enumerate(lines):
        line_strip = line.strip()
        if not line_strip: continue
        if re.match(block_start_pattern, line_strip):
            start_indices.append(i)

    if not start_indices:
        logger.error("Lezuan Parser: No block start lines found using pattern: %s", block_start_pattern)
        return results

    # 2. Split blocks based on indices
    num_blocks = len(start_indices)
    for i in range(num_blocks):
        start_index = start_indices[i]
        end_index = start_indices[i+1] if (i + 1) < num_blocks else len(lines)
        current_block_lines = [lines[j] for j in range(start_index, end_index)]
        current_block_lines_cleaned = [line for line in current_block_lines if line.strip()]

        if current_block_lines_cleaned:
            parsed = process_lezuan_block(current_block_lines_cleaned)
            if parsed:
                results.append(parsed)
            else:
                logger.warning(f"Lezuan Parser: Failed to process block starting at line {start_index+1}: {current_block_lines_cleaned[0] if current_block_lines_cleaned else 'EMPTY'}")
        else:
             logger.debug(f"Lezuan Parser: Skipping empty block found between lines {start_index} and {end_index}")

    return results

def process_lezuan_block(block_lines):
    """處理單個 "樂鑽館" 格式的美容師區塊"""
    if len(block_lines) < 2: # Need at least Name/Fee line and Time line
        logger.warning(f"Lezuan Parser: Block too short: {block_lines}")
        return None

    fee = None; name = None; original_name_text = ""; alias_suggestion = None
    time_slots_str = ""; height = None; weight = None; cup = None
    intro_lines = []

    # Pattern to extract name and fee parts from the first line
    first_line_pattern = r'^\s*(.+?)\s+[\(（]([\w\d\u4e00-\u9fa5]+)[\)）][\(（](\d+)[\)）]單'
    # Pattern for the time line (flexible with emoji)
    time_line_pattern = r'^\s*(?:\(clock\)|⏰|🕛|🕐|🕑|🕒|🕓|🕔|🕕|🕖|🕗|🕘|🕙|🕚|🕧)\s*(.*)'


    try:
        # 1. Process First Line (Name, Fee)
        first_line = block_lines[0].strip()
        original_name_text = first_line # Keep raw line
        match = re.match(first_line_pattern, first_line)
        if match:
            name = match.group(1).strip()
            fee_part1_str = match.group(2).lower() # e.g., "2" or "three" or "三"
            fee_part2_str = match.group(3) # e.g., "9" or "3"

            try:
                # Convert first part (word or digit)
                digit1 = -1
                if fee_part1_str.isdigit():
                    digit1 = int(fee_part1_str)
                elif fee_part1_str in WORD_TO_DIGIT:
                    digit1 = WORD_TO_DIGIT[fee_part1_str]

                # Convert second part (must be digit)
                digit2 = int(fee_part2_str)

                if 0 <= digit1 <= 9 and 0 <= digit2 <= 9: # Basic validation
                    fee = (digit1 * 10 + digit2) * 100
                else:
                     logger.warning(f"Lezuan Parser: Invalid fee digits parsed ({digit1}, {digit2}) from '{first_line}'")
            except (ValueError, KeyError) as e:
                logger.warning(f"Lezuan Parser: Error parsing fee parts ('{fee_part1_str}', '{fee_part2_str}') from '{first_line}': {e}")
        else:
            logger.error(f"Lezuan Parser: Failed to match name/fee pattern on first line: '{first_line}'")
            # Fallback: Try to take the first word as name?
            parts = first_line.split()
            if parts: name = parts[0]
            else: return None # Cannot proceed

        # 2. Process Second Line (Time)
        time_line_match = re.match(time_line_pattern, block_lines[1].strip())
        if time_line_match:
            time_info = time_line_match.group(1).strip()
            if '🈵' in time_info:
                time_slots_str = "預約滿"
            elif not time_info:
                time_slots_str = ""
            else:
                # Time slots separated by '.'
                slots = re.findall(r'\d+', time_info) # Find all numbers
                processed_slots = []; valid_time_line = False
                for s in slots:
                     try:
                         num = int(s); internal_value = -1
                         if 12 <= num <= 23: internal_value = num
                         elif num == 24: internal_value = 100
                         elif 0 <= num <= 11: internal_value = num + 100
                         if internal_value != -1: processed_slots.append(internal_value); valid_time_line = True
                     except ValueError: pass
                if valid_time_line:
                     processed_slots.sort(); time_slots_str = ".".join(map(str, processed_slots))
                else: time_slots_str = "" # Parsing failed
        else:
             logger.warning(f"Lezuan Parser: Second line does not match time pattern: '{block_lines[1].strip()}'")
             # If time is not on the second line, assume it's intro?
             intro_lines.append(block_lines[1].strip())


        # 3. Process Remaining Lines (Introduction)
        # Start from index 2 (third line)
        for i in range(2, len(block_lines)):
            line = block_lines[i].strip()
            if line:
                intro_lines.append(line)

        # 4. Finalize and Return
        full_introduction = "\n".join(intro_lines).strip()

        # Lezuan format doesn't have alias, height, weight, cup
        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': None,
                'height': None, 'weight': None,
                'cup': None, 'introduction': full_introduction,
                'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"Error processing Lezuan block: {block_lines}", exc_info=True)
        return None


# --- utils.py 文件結束 ---