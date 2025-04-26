# D:\bkgg\mybackend\appointments\admin.py
# --- 完整程式碼 (使用最終指定複製格式 V5 並檢查縮排) ---

from django.contrib import admin
from django.utils.html import format_html, escape
from django.utils import timezone
from django.db.models import Q
from .models import Appointment
import json

# --- 自訂篩選器：用於提供更新後狀態的組合選項 ---
class AppointmentProgressFilter(admin.SimpleListFilter):
    title = '記錄進度'
    parameter_name = 'progress_status'

    # --- 確保縮排正確 ---
    def lookups(self, request, model_admin):
        """定義篩選器顯示的選項。"""
        return (
            ('pending_booking', '預約處理中 (客詢問/待確認)'),
            ('waiting_arrival', '待客進店 (預約完成待進店)'),
            ('checked_in', '進行中 (客已到店)'),
            ('completed_rejected', '已結束 (結束/看台未上)'),
            ('cancelled_problem', '異常記錄 (取消/未到/未回覆)'),
        )

    def queryset(self, request, queryset):
        """根據使用者選擇的 lookup 值，修改並返回篩選後的 queryset。"""
        lookup_value = self.value()
        if lookup_value == 'pending_booking':
            return queryset.filter(status__in=['requested', 'pending_confirmation'], is_walk_in=False)
        elif lookup_value == 'waiting_arrival':
            return queryset.filter(status='confirmed_waiting')
        elif lookup_value == 'checked_in':
            return queryset.filter(status='checked_in')
        elif lookup_value == 'completed_rejected':
            return queryset.filter(status__in=['completed', 'rejected_by_customer'])
        elif lookup_value == 'cancelled_problem':
            return queryset.filter(status__in=['cancelled_customer', 'cancelled_salon', 'no_show_customer', 'no_reply_customer'])
        return queryset
    # --- 縮排正確 ---
# --- 自訂篩選器結束 ---


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    """
    預約/現場記錄的管理介面設定。
    """
    list_display = (
        'appointment_datetime_display',
        'hall_display', # 新增館別顯示
        'customer_display',
        'beautician_display', # 現在只顯示名字或(現場看台)
        'is_walk_in_display', # 顯示 "現場看台" 或 "預約"
        'status',             # 原始狀態欄位 (用於編輯)
        'status_display',     # 彩色狀態標籤
        'updated_at_display',
        'time_until_display'  # 顯示剩餘時間
    )

    list_filter = (
        'is_walk_in',           # 按是否現場看台篩選
        AppointmentProgressFilter,# 自訂的進度篩選器
        'hall',                 # 直接按館別篩選
        ('appointment_datetime', admin.DateFieldListFilter), # 按預約日期範圍篩選
    )

    search_fields = (
        'customer__username__icontains',
        'customer__first_name__icontains',
        'customer__last_name__icontains',
        'hall__name__icontains', # 按館別名稱搜尋
        'hall__address__icontains', # 按館別地址搜尋
        'beautician__name__icontains',
        'beautician__aliases__icontains',
        'customer_notes__icontains',
        'admin_notes__icontains',
        'confirmation_notes__icontains'
    )
    list_editable = ('status',)
    list_select_related = ('customer', 'hall', 'beautician', 'created_by') # 加入 hall

    readonly_fields = (
        'created_at',
        'updated_at',
        'created_by',
        'status_updated_at',
        'copyable_confirmation_details',
    )

    fieldsets = (
        ('核心資訊', {
            'fields': (
                'customer',
                'hall',         # 加入館別選擇 (必填)
                'is_walk_in',   # 欄位名改為 "現場看台"
                'beautician',   # 美容師變為可選
                'appointment_datetime',
                'status',
            )
        }),
        ('備註 (可選)', {
            'fields': ('customer_notes', 'admin_notes', 'confirmation_notes'),
            'classes': ('collapse',),
        }),
        ('快速複製 (LINE)', {
             'fields': ('copyable_confirmation_details',),
             'description': '點擊下方按鈕可複製訊息 (適用於預約和現場看台)。'
        }),
        ('系統記錄 (自動)', {
            'fields': ('created_by', 'created_at', 'updated_at', 'status_updated_at'),
            'classes': ('collapse',),
        }),
    )
    autocomplete_fields = ['customer', 'hall', 'beautician'] # 加入 hall
    list_per_page = 25

    # --- 自訂顯示方法 ---
    @admin.display(description='館別', ordering='hall__name')
    def hall_display(self, obj):
        """顯示館別名稱"""
        # --- 確保縮排正確 ---
        return obj.hall.name if obj.hall else "未指定"
        # --- 縮排正確 ---

    @admin.display(description='類型', ordering='is_walk_in')
    def is_walk_in_display(self, obj):
        """顯示文字 "現場看台" 或 "預約" 並加上顏色"""
        # --- 確保縮排正確 ---
        if obj.is_walk_in:
            return format_html('<span style="color: #fd7e14; font-weight: bold;">現場看台</span>')
        else:
            return format_html('<span style="color: #007bff; font-weight: bold;">預約</span>')
        # --- 縮排正確 ---

    # --- 更新：複製按鈕邏輯 (使用最終指定格式 V5) ---
    @admin.display(description="複製預約/看台資訊")
    def copyable_confirmation_details(self, obj):
        """產生包含格式化預約/看台資訊和複製按鈕的 HTML (依照指定格式)"""
        # --- 確保縮排正確 ---
        if not obj or not obj.pk: return "(儲存後才能複製)"
        if not obj.hall: return format_html('<span style="color: red; font-style: italic;"> (請先選擇館別並儲存)</span>')

        appointment_time_str = timezone.localtime(obj.appointment_datetime).strftime('%Y-%m-%d %H:%M') if obj.appointment_datetime else "未定時間"
        admin_name = "動物園"
        hall_name = obj.hall.name
        hall_address = obj.hall.address.strip() if obj.hall.address else ""

        copy_text = ""
        display_text_html = ""
        title = "< 預約完成 >"
        # header2 = "<!---- 注意事項 ---->" # 已移除
        note1 = "# 進店前會稍微檢查手機。"
        note2 = "# 若需取消，請於2小時前告知。"

        幹部行 = f"幹部｜{admin_name}"
        時間行 = f"時間｜{appointment_time_str}"
        地點行_content = f"{hall_address}" if hall_address else ""
        地點行_copy = f"地點｜{地點行_content}" if hall_address else None
        地點行_display = f"地點｜{escape(地點行_content)}" if hall_address else None

        if obj.is_walk_in and not obj.beautician: # 現場看台
            預約行 = f"預約｜{hall_name} - 現場看台"
            copy_text_parts = [title, "", 幹部行, 預約行, 時間行] # 加入空行
            if 地點行_copy: copy_text_parts.append(地點行_copy)
            copy_text_parts.extend(["", note1, note2]) # 現場看台也包含 note1 和 note2
            copy_text = "\n".join(copy_text_parts)

            display_text_parts = [escape(title), "", escape(幹部行), escape(預約行), escape(時間行)] # 加入空行
            if 地點行_display: display_text_parts.append(地點行_display)
            display_text_parts.extend(["", escape(note1), escape(note2)]) # 現場看台也包含 note1 和 note2
            display_text_html = "<br>\n".join(display_text_parts)

        elif not obj.is_walk_in and obj.beautician: # 預約
            beautician_name = obj.beautician.name
            預約行 = f"預約｜{hall_name} - {beautician_name}"
            copy_text_parts = [title, "", 幹部行, 預約行, 時間行] # 加入空行
            if 地點行_copy: copy_text_parts.append(地點行_copy)
            copy_text_parts.extend(["", note1, note2]) # 直接接上注意事項
            copy_text = "\n".join(copy_text_parts)

            display_text_parts = [escape(title), "", escape(幹部行), escape(預約行), escape(時間行)] # 加入空行
            if 地點行_display: display_text_parts.append(地點行_display)
            display_text_parts.extend(["", escape(note1), escape(note2)]) # 直接接上注意事項
            display_text_html = "<br>\n".join(display_text_parts)

        else: # 其他情況
             return format_html('<span style="color: gray; font-style: italic;"> (此類型記錄無需複製標準訊息)</span>')

        js_copy_text = json.dumps(copy_text)
        button_html = format_html('<button type="button" id="copy-btn-{}" onclick=\'copyToClipboard(this, {})\'>複製到剪貼簿</button>', obj.pk, js_copy_text)
        html_output = f"""
<div style="white-space: pre-wrap; background: #f8f9fa; padding: 10px; border: 1px solid #eee; border-radius: 4px; margin-bottom: 5px; font-family: Consolas, 'Courier New', monospace; line-height: 1.5;">{display_text_html}</div>
{button_html}
"""
        return format_html(html_output)
        # --- 縮排正確 ---
    # --- 複製方法更新結束 ---


    @admin.display(description='預約/服務時間', ordering='appointment_datetime')
    def appointment_datetime_display(self, obj):
        # --- 確保縮排正確 ---
        if obj.appointment_datetime:
            return timezone.localtime(obj.appointment_datetime).strftime('%Y-%m-%d %H:%M')
        return '-'
        # --- 縮排正確 ---

    @admin.display(description='狀態標籤', ordering='status')
    def status_display(self, obj):
        # --- 確保縮排正確 ---
        status_map = {
            'requested': ('#6c757d', '客詢問預約'),
            'pending_confirmation': ('#ffc107', '待店家確認'),
            'confirmed_waiting': ('#17a2b8', '預約完成待進店'),
            'checked_in': ('#28a745', '客已到店'),
            'completed': ('#007bff', '客結束'),
            'rejected_by_customer': ('#fd7e14', '客看台未上'),
            'cancelled_customer': ('#6c757d', '客取消'),
            'no_reply_customer': ('#adb5bd', '客未回覆'),
            'cancelled_salon': ('#dc3545', '店家/美容師取消'),
            'no_show_customer': ('#dc3545', '客未到'),
        }
        color, text = status_map.get(obj.status, ('#000000', obj.get_status_display()))
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 6px; border-radius: 4px; font-weight: bold; font-size: 0.9em; white-space: nowrap;">{}</span>',
            color,
            text
        )
        # --- 縮排正確 ---

    @admin.display(description='客戶', ordering='customer')
    def customer_display(self, obj):
        # --- 確保縮排正確 ---
        if obj.customer:
            name = obj.customer.get_full_name() or obj.customer.username
            return name if name else f"ID:{obj.customer.id}"
        return '-'
        # --- 縮排正確 ---

    @admin.display(description='美容師', ordering='beautician')
    def beautician_display(self, obj):
        # --- 確保縮排正確 ---
        if obj.beautician:
            return obj.beautician.name # 只返回名字
        elif obj.is_walk_in:
            return format_html('<span style="color: gray; font-style: italic;">(現場看台)</span>')
        else: # 預約單未指定
            return format_html('<span style="color: red; font-weight: bold;">(未指定!)</span>')
        # --- 縮排正確 ---

    @admin.display(description='最後更新', ordering='updated_at')
    def updated_at_display(self, obj):
        # --- 確保縮排正確 ---
        if obj.updated_at:
            return timezone.localtime(obj.updated_at).strftime('%m-%d %H:%M')
        return '-'
        # --- 縮排正確 ---

    @admin.display(description='剩餘時間', ordering='appointment_datetime')
    def time_until_display(self, obj):
        # --- 確保縮排正確 ---
        now = timezone.now()
        if obj.status == 'confirmed_waiting' and obj.appointment_datetime and obj.appointment_datetime > now:
            delta = obj.appointment_datetime - now
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, _ = divmod(remainder, 60)

            if days >= 7:
                return f"{days} 天"
            elif days > 1:
                return f"{days} 天 {hours} 時"
            elif days == 1:
                return format_html('<span style="color: orange; font-weight: bold;">{} 天 {} 時</span>', days, hours)
            elif hours >= 3:
                return format_html('<span style="color: orange; font-weight: bold;">{} 時 {} 分</span>', hours, minutes)
            elif hours >= 1 or minutes > 15 :
                return format_html('<span style="color: red; font-weight: bold;">{} 時 {} 分</span>', hours, minutes)
            elif minutes >= 0:
                return format_html('<span style="color: red; font-weight: bold;">{} 分</span>', minutes)
            else:
                return format_html('<span style="color: red; font-weight: bold;">即將開始</span>')
        elif obj.status == 'checked_in':
            return format_html('<span style="color: #28a745; font-style: italic;">進行中</span>')
        elif obj.status in ['requested', 'pending_confirmation'] and not obj.is_walk_in and obj.appointment_datetime and obj.appointment_datetime > now:
            return format_html('<span style="color: gray; font-style: italic;">待確認</span>')
        elif obj.status in ['completed', 'cancelled_customer', 'cancelled_salon', 'no_show_customer', 'rejected_by_customer', 'no_reply_customer']:
            return '-'
        elif obj.appointment_datetime and obj.appointment_datetime < now and obj.status not in ['completed', 'cancelled_customer', 'cancelled_salon', 'no_show_customer', 'rejected_by_customer', 'no_reply_customer']:
            return format_html('<span style="color: gray; font-style: italic;">已過期</span>')
        return '-'
        # --- 縮排正確 ---

    # --- 覆寫 Admin 方法 ---
    def save_model(self, request, obj, form, change):
        # --- 確保縮排正確 ---
        if not change and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        # --- 縮排正確 ---

    def get_queryset(self, request):
        # --- 確保縮排正確 ---
        qs = super().get_queryset(request)
        filter_logic = Q(status__in=['requested', 'pending_confirmation'], is_walk_in=False) | \
                       Q(status__in=['confirmed_waiting', 'checked_in'])
        filtered_qs = qs.filter(filter_logic)
        return filtered_qs.select_related('customer', 'hall', 'beautician', 'created_by') # 更新 select_related
        # --- 縮排正確 ---

    class Media:
        # --- 確保縮排正確 ---
        js = ('js/admin_clipboard.js',) # 確保 JS 檔案路徑正確
        # --- 縮排正確 ---