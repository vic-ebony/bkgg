# D:\bkgg\mybackend\schedule_parser\utils.py
import re
import html
import logging

logger = logging.getLogger(__name__) # 創建 logger

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
        # 1. 處理第一行
        first_line = block_lines[0]
        fee_match = re.search(r'^\(\s*(\d+)\s*\)', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100 # 假設存儲為分
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

        # 2. 處理後續行 (修改時間處理邏輯)
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
                            # --- *** 修改：根據營業時間調整內部值 *** ---
                            internal_value = -1
                            if 12 <= num <= 23: internal_value = num
                            elif num == 24: internal_value = 100 # 24點 -> 100
                            elif 0 <= num <= 5: internal_value = num + 100 # 0-5點 -> 100-105
                            if internal_value != -1: processed_slots.append(internal_value)
                            # --- *** 修改結束 *** ---
                        except ValueError: continue
                    processed_slots.sort() # 排序內部值
                    time_slots_str = ".".join(map(str, processed_slots)) # 存儲內部值
                time_found = True
            elif not time_found: # 收集介紹
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
                parsed = process_chatanghui_block(current_block_lines)
                if parsed: results.append(parsed)
            current_block_lines = [line_strip]
        elif current_block_lines:
            current_block_lines.append(line_strip)

    if current_block_lines:
        parsed = process_chatanghui_block(current_block_lines)
        if parsed: results.append(parsed)

    return results

# --- process_chatanghui_block 修改時間處理邏輯 ---
def process_chatanghui_block(block_lines):
    """
    處理單個 "茶湯會休閒會館" 格式的美容師區塊。
    在收集介紹時，遇到包含 【名字】 模式的行則停止。
    修改了時間解析以生成內部排序值。
    """
    if not block_lines: return None

    name = None; original_name_text = ""; alias_suggestion = None; fee = None
    time_slots_str = ""; height = None; weight = None; cup = None
    introduction_lines = []; forbidden_lines = []
    name_pattern_in_intro = r'【.+?】' # 用於停止介紹收集

    line_index = 0
    try:
        # 1. 處理第一行 (名字、費用、別名) - 邏輯不變
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

        # 2. 處理可能的時段行 (修改時間處理邏輯)
        time_found = False
        if line_index < len(block_lines):
            second_line = block_lines[line_index].strip()
            if second_line == '🈵️' or second_line == '🈵': time_slots_str = "預約滿"; time_found = True
            elif second_line == '人到再約' or second_line.startswith('人道'): time_slots_str = "人到再約"; time_found = True
            elif re.search(r'\d', second_line):
                # --- *** 修改時間處理邏輯以生成內部排序值 *** ---
                raw_slots = re.findall(r'\d+', second_line) # 提取所有數字串
                processed_slots = [] # 存儲內部值 (12-23, 100-105)
                for s in raw_slots:
                    try:
                        s_corrected = s[:2] if len(s) > 2 else s; num = int(s_corrected)
                        internal_value = -1
                        if 12 <= num <= 23: internal_value = num
                        elif num == 24: internal_value = 100 # 24點 -> 100
                        elif 0 <= num <= 5: internal_value = num + 100 # 0-5點 -> 100-105
                        if internal_value != -1: processed_slots.append(internal_value)
                    except ValueError: logger.warning(f"Chatanghui Parser: 時段行 '{second_line}' 中無法轉換數字 '{s}'")
                processed_slots = sorted(list(set(processed_slots))) # 排序內部值
                time_slots_str = ".".join(map(str, processed_slots)) if processed_slots else "" # 存儲內部值
                # --- *** 修改結束 *** ---
                time_found = True
            if time_found: line_index += 1

        # 3. 處理可能的身材行 - 邏輯不變
        size_found = False
        if line_index < len(block_lines):
            current_line = block_lines[line_index].strip()
            size_match = re.match(r'^(\d{3})\s*/\s*(\d{2,3})\s*/\s*([A-Za-z\+\-]+)', current_line)
            if size_match:
                try: height = int(size_match.group(1))
                except ValueError: pass
                try: weight = int(size_match.group(2))
                except ValueError: pass
                cup = size_match.group(3).strip(); size_found = True
                line_index += 1

        # 4. 處理剩餘的行 (介紹和禁忌)，使用 【】 停止收集 - 邏輯不變
        while line_index < len(block_lines):
            remaining_line = block_lines[line_index].strip()
            if re.search(name_pattern_in_intro, remaining_line):
                logger.debug(f"停止收集介紹，因為行 '{remaining_line}' 包含名字模式")
                break
            if remaining_line.startswith('🈲️') or remaining_line.startswith('🈲'):
                forbidden_lines.append(remaining_line)
            elif remaining_line:
                introduction_lines.append(remaining_line)
            line_index += 1

        full_introduction = "\n".join(introduction_lines + forbidden_lines).strip()

        return {'parsed_fee': fee, 'name': name, 'original_name_text': original_name_text,
                'alias_suggestion': alias_suggestion, 'height': height, 'weight': weight,
                'cup': cup, 'introduction': full_introduction, 'time_slots': time_slots_str}

    except Exception as e:
        logger.error(f"處理茶湯會區塊時出錯: {block_lines}", exc_info=True)
        return None

# --- utils.py 文件結束 ---