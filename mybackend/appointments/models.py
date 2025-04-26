# D:\bkgg\mybackend\appointments\models.py
# --- 完整程式碼 (加入 hall ForeignKey) ---

from django.db import models
from django.conf import settings
from django.utils import timezone
from myapp.models import Animal, Hall # <<<--- 導入 Hall 模型 ---<<<

class Appointment(models.Model):
    """
    預約/現場服務記錄模型。
    """
    STATUS_CHOICES = [
        ('requested', '客詢問預約'),
        ('pending_confirmation', '待店家確認'),
        ('confirmed_waiting', '預約完成待進店'),
        ('checked_in', '客已到店'),
        ('completed', '客結束'),
        ('rejected_by_customer', '客看台未上'),
        ('cancelled_customer', '客取消'),
        ('no_reply_customer', '客未回覆'),
        ('cancelled_salon', '店家/美容師取消'),
        ('no_show_customer', '客未到'),
    ]

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name="客戶/會員",
        help_text="選擇進行預約或服務的客戶帳號"
    )
    # --- 加入 Hall ForeignKey ---
    hall = models.ForeignKey(
        Hall,
        on_delete=models.PROTECT, # 保護館別不被輕易刪除
        verbose_name="館別",
        null=False, # <<<--- 資料庫層面不允許 NULL
        blank=False,# <<<--- 在 Admin 表單中此欄位變為必填
        help_text="選擇此預約/看台發生的館別。"
    )
    # --- -------------------- ---
    beautician = models.ForeignKey(
        Animal,
        on_delete=models.PROTECT,
        verbose_name="美容師 (可選)",
        limit_choices_to={'is_active': True},
        null=True,  # 允許資料庫中為 NULL
        blank=True, # 允許在 Admin 表單中為空 (用於現場看台)
        help_text="選擇提供服務的美容師。若是『現場看台』，此欄留空。"
    )
    appointment_datetime = models.DateTimeField(
        "預約/服務時間",
        help_text="預約開始時間 或 現場服務/看台實際發生時間"
    )
    status = models.CharField(
        "記錄狀態",
        max_length=30,
        choices=STATUS_CHOICES,
        default='requested',
        db_index=True,
        help_text="追蹤記錄的目前進度"
    )
    status_updated_at = models.DateTimeField(
        "狀態最後更新時間",
        auto_now=True,
        help_text="此狀態最後一次被更新的時間"
    )
    is_walk_in = models.BooleanField(
        "現場看台",
        default=False,
        db_index=True,
        help_text="勾選此項表示此記錄為客人『現場看台』或『現場順上』，而非提前預約特定美容師。"
    )
    customer_notes = models.TextField("客戶備註 (來自LINE/現場)", blank=True, help_text="記錄客戶提出的原始需求或特殊要求")
    admin_notes = models.TextField("內部備註 (管理員用)", blank=True, help_text="管理員內部溝通或記錄")
    confirmation_notes = models.TextField("確認/回報備註", blank=True, help_text="記錄與店家確認的結果或回報訊息")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='created_appointments',
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="記錄建立者", help_text="登打此筆記錄的管理員帳號"
    )
    created_at = models.DateTimeField("記錄建立時間", auto_now_add=True, editable=False)
    updated_at = models.DateTimeField("記錄最後更新時間", auto_now=True, editable=False)

    class Meta:
        ordering = ['-appointment_datetime']
        verbose_name = "預約/現場記錄"
        verbose_name_plural = "預約/現場記錄"
        indexes = [
            models.Index(fields=['appointment_datetime', 'status']),
            models.Index(fields=['is_walk_in', 'status']),
            models.Index(fields=['hall', 'appointment_datetime']), # 加入館別索引
            models.Index(fields=['beautician', 'status']),
        ]

    def __str__(self):
        record_type = ""
        beautician_info = ""
        hall_name = self.hall.name if self.hall else "未知館別" # 直接從 hall 獲取

        if self.is_walk_in:
            if self.beautician: record_type = "現場順上"; beautician_info = self.beautician.name
            else: record_type = "現場看台"; beautician_info = "(待定)"
        else:
            if self.beautician: record_type = "預約"; beautician_info = self.beautician.name
            else: record_type = "預約(異常)"; beautician_info = "(未指定!)"

        try: customer_name = self.customer.get_full_name() or self.customer.username if self.customer else "未知客戶"
        except AttributeError: customer_name = f"客戶ID:{self.customer_id}" if self.customer_id else "未知客戶"

        time_str = timezone.localtime(self.appointment_datetime).strftime('%Y-%m-%d %H:%M') if self.appointment_datetime else '未定時間'
        status_display_name = self.get_status_display()
        # 在字串中加入館別
        return f"{time_str} - {hall_name} - {customer_name} {record_type} {beautician_info} ({status_display_name})"

    @property
    def is_cancelable_by_customer(self):
        allowed_statuses = ['requested', 'pending_confirmation', 'confirmed_waiting']
        if not self.is_walk_in and self.status in allowed_statuses and self.appointment_datetime:
            now = timezone.now(); two_hours_before = self.appointment_datetime - timezone.timedelta(hours=2); return now < two_hours_before
        return False

    @property
    def is_upcoming_or_active(self):
        active_statuses = ['requested', 'pending_confirmation', 'confirmed_waiting', 'checked_in']
        if self.status in active_statuses and self.appointment_datetime: return self.appointment_datetime > (timezone.now() - timezone.timedelta(hours=3))
        return False

    @property
    def time_until_appointment(self):
        if self.appointment_datetime and self.appointment_datetime > timezone.now(): return self.appointment_datetime - timezone.now()
        return None