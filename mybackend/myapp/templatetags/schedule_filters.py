from django import template
import re
from django.utils.safestring import mark_safe
import html
import logging # 引入 logging

register = template.Library()
logger = logging.getLogger(__name__) # 創建 logger

@register.filter(name='format_slots', is_safe=True) # 直接在裝飾器裡標記 is_safe=True
def format_slots(value):
    """
    將時段字串轉換為格式化的 HTML。
    處理特殊值如 '預約滿', '人到再約', 空值, 以及數字時段 (e.g., '14.15.25')。
    返回包含 HTML span 標籤的字串。
    """
    # 1. 處理 None 和非字串輸入
    if value is None:
        value = "" # 將 None 視為空字串處理
    if not isinstance(value, str):
        try:
            value = str(value) # 嘗試轉換為字串
        except Exception:
             logger.warning(f"無法將 format_slots 的輸入 '{value}' (類型: {type(value)}) 轉換為字串，返回 '--'")
             return "--" # 如果轉換失敗，返回預設值

    value_stripped = value.strip()

    # 2. 處理特殊字串和空字串
    if value_stripped == "預約滿":
        return mark_safe('<span class="time-slot" style="color: red; font-weight: bold;">預約滿</span>') # 使用 mark_safe
    elif value_stripped == "人到再約":
        return mark_safe('<span class="time-slot" style="color: orange;">人到再約</span>') # 使用 mark_safe
    elif not value_stripped:
         # 返回空字串，讓模板決定是否顯示 (或者返回 '--' 如果你想明確顯示)
         return "" # 或者 return "--"
         # return mark_safe('<span class="time-slot" style="color: grey;">未排班</span>')

    # 3. 嘗試處理數字時段
    processed_slots = []
    # 使用更寬鬆的正則，匹配數字或被非數字分隔的數字序列
    # 例如可以處理 "14.15", "16/17", "18點19點"
    possible_slots = re.split(r'[^\d]+', value_stripped) # 用非數字字符分割

    for s in possible_slots:
        s_cleaned = s.strip()
        if not s_cleaned: # 跳過分割產生的空字串
            continue
        try:
            num = int(s_cleaned)
            if 0 <= num <= 23: # 正常小時
                processed_slots.append(f"{num:02d}") # 統一為兩位數
            elif num >= 24: # 處理轉換後的大於等於 24 的值
                 # 假設 24 代表 00, 25 代表 01 ...
                hour = num % 24 # 使用取模更安全
                processed_slots.append(f"{hour:02d}")
            # 可以選擇忽略負數或其他無效情況，或者 log 警告
            # else:
            #     logger.warning(f"在 format_slots 中忽略了無效數字: {num} (來自 '{s_cleaned}')")

        except ValueError:
            # 如果分割出來的部分不是純數字，也忽略
            # logger.debug(f"在 format_slots 中忽略了非數字部分: '{s_cleaned}'")
            continue

    # 4. 如果沒有處理到任何有效的數字時段
    if not processed_slots:
        # 返回轉義後的原始輸入，並用 span 包裹，標記為其他類型
        escaped_value = html.escape(value_stripped)
        logger.warning(f"format_slots 未能從 '{value_stripped}' 解析出數字時段，返回原始值。")
        # 可以給一個通用的 class，例如 "other-status"
        return mark_safe(f'<span class="time-slot other-status">{escaped_value}</span>') # 使用 mark_safe

    # 5. 格式化並返回數字時段的 HTML
    # 為每個處理好的時段添加 span 標籤
    slot_spans = [f'<span class="time-slot">{slot}</span>' for slot in sorted(list(set(processed_slots)))] # 去重並排序
    # 用 div 包裹起來，符合 _animal_table_rows.html 中的 <td class="time-cell"> 結構預期
    # 注意：這裡返回的是內部結構，外部的 <td> 還是需要的
    # (移除外層div，只返回 spans)
    # return mark_safe('<div class="time-cell-inner">' + "".join(slot_spans) + '</div>')
    return mark_safe("".join(slot_spans)) # 只返回 span 的組合

# 注意：不再需要 escapeHTML 函數
# 注意：不再需要在 register.filter 中指定 is_safe=True，因為已經在裝飾器中指定了