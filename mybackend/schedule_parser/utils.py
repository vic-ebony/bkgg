# D:\bkgg\mybackend\schedule_parser\utils.py
import re

def parse_line_schedule(text):
    """
    解析 LINE 文字班表。
    返回一個列表，每個元素是一個包含解析信息的字典，
    或者在塊無效時返回 None。
    """
    results = []
    current_animal_block = []
    lines = text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line: continue # 跳過空行

        # 檢查是否是新區塊的開始 (以 '(數字)' 開頭)
        # 改進正則表達式以處理可能的空格
        if re.match(r'^\(\s*\d+\s*\)', line):
            # 處理上一個區塊（如果存在）
            if current_animal_block:
                parsed = process_animal_block(current_animal_block)
                if parsed: results.append(parsed)
            # 開始新區塊
            current_animal_block = [line]
        elif current_animal_block: # 如果在區塊內，添加到當前塊
            current_animal_block.append(line)

    # 處理文件末尾的最後一個區塊
    if current_animal_block:
        parsed = process_animal_block(current_animal_block)
        if parsed: results.append(parsed)

    return results

def process_animal_block(block_lines):
    """處理單個美容師的文字區塊"""
    if not block_lines: return None

    fee = None
    name = None
    original_name_text = ""
    alias_suggestion = None # 從括號提取的別名建議
    height = None
    weight = None
    cup = None
    intro_lines = []
    time_slots_str = None

    try:
        # 1. 處理第一行
        first_line = block_lines[0]

        # 提取費用
        fee_match = re.search(r'^\(\s*(\d+)\s*\)', first_line)
        if fee_match:
            try: fee = int(fee_match.group(1)) * 100
            except ValueError: pass

        # 提取名字部分 (在 ')' 和 '👙' 之間)
        name_part_match = re.search(r'\)\s*(.*?)\s*👙', first_line)
        if name_part_match:
            original_name_text = name_part_match.group(1).strip()
            # 提取主要名字 (括號前)
            main_name_match = re.match(r'^([^\(（\s]+)', original_name_text) # 匹配到第一個空格或括號前
            if main_name_match:
                name = main_name_match.group(1).strip()
                # 嘗試提取括號內的別名建議
                alias_match = re.search(r'[\(（](.+?)[\)）]', original_name_text)
                if alias_match:
                    alias_suggestion = alias_match.group(1).strip()
                    if alias_suggestion.startswith("原"):
                         alias_suggestion = alias_suggestion[1:].strip()
            else: # 如果名字部分不含括號
                name = original_name_text

        # 提取身材
        size_match = re.search(r'(\d{3})\s*/\s*(\d{2,3})\s*/\s*([A-Za-z\+\-]+)', first_line)
        if size_match:
            try: height = int(size_match.group(1))
            except ValueError: pass
            try: weight = int(size_match.group(2))
            except ValueError: pass
            cup = size_match.group(3).strip()

        # 2. 處理後續行
        time_found = False
        for line in block_lines[1:]:
            line_strip = line.strip()
            if line_strip.startswith('⏰'):
                time_info = line_strip.replace('⏰', '').strip()
                if time_info == '🈵':
                    time_slots_str = "預約滿"
                elif time_info == '人到再約' or time_info.startswith('人道'):
                    time_slots_str = "人到再約"
                elif not time_info: # 處理 ⏰ 後面是空的情況
                    time_slots_str = "" # 或 None，根據你的偏好
                else:
                    # 提取數字，兼容頓號、空格、點
                    slots = re.findall(r'\d{1,2}', time_info)
                    processed_slots = []
                    for s in slots:
                        try:
                            num = int(s)
                            # 處理跨夜，並確保在合理範圍內
                            if 0 <= num <= 5:
                                processed_slots.append(num + 24)
                            elif 6 <= num <= 24:
                                 processed_slots.append(num)
                            # 忽略其他不合理數字
                        except ValueError: continue
                    # 對提取到的數字小時進行排序並格式化
                    processed_slots.sort()
                    time_slots_str = ".".join(map(str, processed_slots))
                time_found = True
                # 找到時間後可以停止收集介紹，但繼續循環以防萬一還有時間行？
                # 通常一個區塊只有一行時間，可以考慮 break
                # break
            elif not time_found: # 收集介紹 (排除特殊行)
                if not line_strip.startswith('🈲') and not line_strip.startswith('(<') and not line_strip.startswith('(>') and line_strip:
                    intro_lines.append(line_strip)

        # 只有成功解析出名字才返回結果
        if name:
            return {
                'parsed_fee': fee,
                'name': name,
                'original_name_text': original_name_text,
                'alias_suggestion': alias_suggestion,
                'height': height,
                'weight': weight,
                'cup': cup,
                'introduction': "\n".join(intro_lines).strip(),
                'time_slots': time_slots_str if time_slots_str is not None else "" # 確保返回字串
            }
    except Exception as e:
        print(f"Error processing block: {block_lines} -> {e}")
        # 可以選擇記錄錯誤或返回 None
        return None # 解析塊出錯則跳過

    return None # 如果連名字都沒解析出來，返回 None