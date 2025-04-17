# D:\bkgg\mybackend\myapp\templatetags\schedule_filters.py
from django import template
import re
from django.utils.safestring import mark_safe
import html
import logging

register = template.Library()
logger = logging.getLogger(__name__)

@register.filter(name='format_slots', is_safe=True)
def format_slots(value):
    """
    將內部時段字串 (e.g., "14.23.100.101") 轉換為顯示格式 (e.g., "14", "23", "24", "01")。
    處理特殊值如 '預約滿', '人到再約', 空值。
    修正：確保 100 顯示為 24，>100 顯示為 01, 02...
    """
    if value is None: value = ""
    if not isinstance(value, str):
        try: value = str(value)
        except Exception: logger.warning(f"無法轉換 format_slots 輸入 '{value}' 為字串"); return "--"
    value_stripped = value.strip()

    if value_stripped == "預約滿": return mark_safe('<span class="time-slot" style="color: red; font-weight: bold;">預約滿</span>')
    elif value_stripped == "人到再約": return mark_safe('<span class="time-slot" style="color: orange;">人到再約</span>')
    elif not value_stripped: return "" # 或 "--"

    processed_display_slots = []
    # 假設數據庫存儲的是點分隔的內部值 (12-23, 100-105...)，且已排序
    internal_slots = value_stripped.split('.')

    for s in internal_slots:
        s_cleaned = s.strip()
        if not s_cleaned: continue
        try:
            num = int(s_cleaned) # 讀取內部值 (12-23, 100, 101, 102...)

            # --- *** 再次修正：根據內部值轉換為正確的顯示值 *** ---
            display_hour_str = ""
            if 12 <= num <= 23: # 當天時段 12:00 - 23:00
                display_hour_str = f"{num:02d}" # 顯示 "12" - "23"
            elif num == 100:    # 內部值 100 代表 24:00 (或 00:00)
                display_hour_str = "24"   # <--- 直接顯示 "24"
            elif num > 100:     # 內部值 > 100 代表凌晨 01:00, 02:00... (101, 102...)
                hour = num - 100 # 減去偏移量得到實際小時 (1, 2...)
                display_hour_str = f"{hour:02d}" # 顯示 "01", "02"...
            # 忽略其他值 (例如 < 12 或非預期值)
            else:
                logger.warning(f"format_slots 遇到非預期內部值: {num} (來自 '{s_cleaned}')，已忽略")
                continue # 跳過不顯示

            processed_display_slots.append(display_hour_str)
            # --- *** 修正結束 *** ---

        except ValueError:
            logger.warning(f"format_slots 無法轉換內部值數字: '{s_cleaned}'")
            continue

    if not processed_display_slots:
        escaped_value = html.escape(value_stripped)
        logger.warning(f"format_slots 未能從內部值 '{value_stripped}' 解析出有效時段，返回原始值。")
        return mark_safe(f'<span class="time-slot other-status">{escaped_value}</span>')

    # 按從數據庫讀取的順序（已按內部值排序）生成 HTML
    slot_spans = [f'<span class="time-slot">{slot}</span>' for slot in processed_display_slots]
    return mark_safe("".join(slot_spans))

# --- schedule_filters.py 文件結束 ---