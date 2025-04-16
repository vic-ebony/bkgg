# models.py
# (No changes to existing imports)
from django.db import models
from django.conf import settings
from django.utils import timezone # Import timezone
from django.db.models.signals import pre_save # Import pre_save signal
from django.dispatch import receiver # Import receiver
from datetime import timedelta # Import timedelta
# --- START: Q object for complex lookups ---
from django.db.models import Q
# --- END: Q object ---
# --- START: Import ValidationError for model cleaning ---
from django.core.exceptions import ValidationError
# --- END: Import ValidationError ---

class Hall(models.Model):
    name = models.CharField("館別名稱", max_length=100)
    order = models.PositiveIntegerField("排序", default=0) # Add order field
    is_active = models.BooleanField("啟用中", default=True, db_index=True) # True=啟用, False=停用(裝修/關店)
    # --- START: 新增 is_visible 欄位 ---
    is_visible = models.BooleanField(
        "前端顯示",
        default=True,
        db_index=True,
        help_text="勾選此項，該館別按鈕才會顯示在前端頁面。取消勾選可隱藏按鈕，但不影響後台操作或資料關聯。"
    )
    # --- END: 新增 is_visible 欄位 ---

    class Meta:
        # 排序: 先按啟用狀態(啟用在前), 再按 order, 最後按 name
        # is_visible 不影響主要排序邏輯，主要由 is_active 和 order 控制
        ordering = ['-is_active', 'order', 'name']

    def __str__(self):
        # 在後台列表或選擇器中顯示狀態
        status_parts = []
        if self.is_active:
            status_parts.append("啟用")
            if not self.is_visible:
                status_parts.append("前端隱藏")
        else:
            status_parts.append("停用")
        status_str = ", ".join(status_parts)
        return f"{self.name} ({status_str})"

    # --- START: 新增 clean 方法 ---
    # 確保 is_active=False 時，is_visible 也必須是 False
    def clean(self):
        if not self.is_active and self.is_visible:
            # 如果館別被設為停用，則強制設為前端不顯示
            self.is_visible = False
            # 可以選擇性地拋出 ValidationError 提醒使用者，但這裡直接修正更友好
            # raise ValidationError({'is_visible': '已停用的館別不能設定為前端顯示。'})
    # --- END: 新增 clean 方法 ---

    def save(self, *args, **kwargs):
        # 在儲存前執行 clean 方法
        self.clean()
        super().save(*args, **kwargs)

# --- Animal Model 保持不變 ---
# Animal 的顯示和查詢邏輯依賴於 Hall 的 is_active，不受 is_visible 影響
class Animal(models.Model):
    name = models.CharField("動物名稱", max_length=100)
    height = models.IntegerField("身高", blank=True, null=True)
    weight = models.IntegerField("體重", blank=True, null=True)
    cup_size = models.CharField("罩杯", max_length=5, blank=True, null=True) # Allow more chars like 'A+'
    fee = models.IntegerField("台費", blank=True, null=True)
    time_slot = models.CharField(
        "時段",
        max_length=200,
        blank=True,
        help_text="請輸入時段，每個時段用 '.' 隔開，例如：12.13.14.15.16.17.18.19.20"
    )
    hall = models.ForeignKey(
        Hall,
        verbose_name="館別",
        on_delete=models.SET_NULL, # 如果館別刪除，美容師不會跟著刪除，hall欄位變null
        null=True, blank=True,
        related_name='animals'
    )
    photo = models.ImageField("照片", upload_to='animal_photos/', blank=True, null=True)
    is_newcomer = models.BooleanField("新人", default=False)
    is_hot = models.BooleanField("熱門", default=False)
    is_exclusive = models.BooleanField("獨家", default=False)
    is_hidden_edition = models.BooleanField("隱藏版", default=False)
    is_recommended = models.BooleanField("推薦", default=False) # Add recommended flag
    is_active = models.BooleanField("啟用中", default=True) # Add active flag (美容師本身是否啟用)
    order = models.PositiveIntegerField("排序", default=0) # Add order field
    introduction = models.TextField("介紹", blank=True, null=True)

    class Meta:
        # 排序: 先按館別排序(館別自身排序已包含 is_active), 再按美容師排序, 最後按名字
        ordering = ['hall__order', 'order', 'name'] # 這裡不需要改

    def __str__(self):
        # 顯示館別名稱，如果沒有則顯示 '未分館'
        hall_name = self.hall.name if self.hall else '未分館'
        # 加上館別啟用/停用狀態
        hall_status = ""
        if self.hall:
             hall_status = "" if self.hall.is_active else " (館別停用)"
             # 注意: 這裡不顯示前端隱藏狀態，因為動物列表主要關心功能性狀態
        return f"{hall_name}{hall_status} - {self.name}"

    @property
    def size_display(self):
        parts = []
        if self.height: parts.append(str(self.height))
        if self.weight: parts.append(str(self.weight))
        if self.cup_size: parts.append(self.cup_size)
        return ".".join(parts) if parts else ""

# --- Review Model 保持不變 ---
class Review(models.Model):
    animal = models.ForeignKey(Animal, related_name="reviews", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    age = models.PositiveIntegerField("年紀", null=True, blank=True)
    LOOKS_CHOICES = [ ('S級 (一見難忘)', 'S級 (一見難忘)'), ('A級 (出眾)', 'A級 (出眾)'), ('B級 (優異)', 'B級 (優異)'), ('C級 (中上)', 'C級 (中上)'), ('D級 (大眾)', 'D級 (大眾)'), ('E級 (較平凡)', 'E級 (較平凡)'), ]
    looks = models.CharField("顏值", max_length=20, choices=LOOKS_CHOICES, blank=True, null=True)
    face = models.CharField("臉蛋", max_length=100, blank=True, null=True) # Consider ManyToManyField or TagsField
    temperament = models.CharField("氣質", max_length=100, blank=True, null=True) # Consider ManyToManyField or TagsField
    PHYSIQUE_CHOICES = [ ('骨感', '骨感'), ('瘦', '瘦'), ('瘦有肉', '瘦有肉'), ('標準', '標準'), ('曲線迷人', '曲線迷人'), ('瘦偏肉', '瘦偏肉'), ('微肉', '微肉'), ('棉花糖', '棉花糖'), ]
    physique = models.CharField("體態", max_length=20, choices=PHYSIQUE_CHOICES, blank=True, null=True)
    CUP_CHOICES = [ ('天然', '天然'), ('醫美', '醫美'), ('自體醫美', '自體醫美'), ('不確定', '不確定'), ]
    cup = models.CharField("罩杯類型", max_length=20, choices=CUP_CHOICES, blank=True, null=True)
    cup_size = models.CharField("罩杯大小", max_length=5, blank=True, null=True) # Increased length
    SKIN_TEXTURE_CHOICES = [ ('絲滑', '絲滑'), ('還不錯', '還不錯'), ('正常', '正常'), ('普通', '普通'), ]
    skin_texture = models.CharField("膚質", max_length=20, choices=SKIN_TEXTURE_CHOICES, blank=True, null=True)
    SKIN_COLOR_CHOICES = [ ('白皙', '白皙'), ('偏白', '偏白'), ('正常黃', '正常黃'), ('偏黃', '偏黃'), ('健康黑', '健康黑'), ]
    skin_color = models.CharField("膚色", max_length=20, choices=SKIN_COLOR_CHOICES, blank=True, null=True)
    MUSIC_CHOICES = [ ('未詢問', '未詢問'), ('無此服務', '無此服務'), ('可加值', '可加值 (費用待填)'), ('自談', '可加值 (自談)'), ]
    music = models.CharField("音樂", max_length=20, choices=MUSIC_CHOICES, blank=True, null=True)
    music_price = models.CharField("音樂價格", max_length=20, blank=True, null=True) # Changed to CharField for flexibility ('私談' etc.)
    SPORTS_CHOICES = [ ('未詢問', '未詢問'), ('無此服務', '無此服務'), ('可加值', '可加值 (費用待填)'), ('自談', '可加值 (自談)'), ('體含音', '體含音'), ]
    sports = models.CharField("體育", max_length=20, choices=SPORTS_CHOICES, blank=True, null=True)
    sports_price = models.CharField("體育價格", max_length=20, blank=True, null=True) # Changed to CharField
    scale = models.CharField("尺度", max_length=100, blank=True, null=True) # Consider ManyToManyField or TagsField
    content = models.TextField("心得", blank=True, null=True)
    created_at = models.DateTimeField("建立時間", default=timezone.now) # Use default=timezone.now
    approved = models.BooleanField("已審核", default=False)

    class Meta:
        ordering = ['-created_at'] # Default order

    def __str__(self):
        return f"Review of {self.animal.name} by {self.user.username}"

# --- PendingAppointment Model 保持不變 ---
class PendingAppointment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pending_appointments')
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='pending_users')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'animal') # Prevent duplicates
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} - {self.animal.name}"

# --- Note Model 保持不變 ---
class Note(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notes')
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField("筆記內容", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("user", "animal"),)
        ordering = ['-updated_at']

    def __str__(self):
        return f"Note for {self.animal.name} by {self.user.username}"

# --- Announcement Model 保持不變 ---
class Announcement(models.Model):
    title = models.CharField("標題", max_length=200, blank=True, null=True)
    content = models.TextField("公告內容")
    is_active = models.BooleanField("啟用中", default=True, db_index=True) # Index for faster lookup
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        ordering = ['-created_at'] # Show newest first
        verbose_name = "公告"
        verbose_name_plural = "公告"

    def __str__(self):
        return self.title or f"公告 #{self.id}"

# --- StoryReview Model 保持不變 ---
class StoryReview(models.Model):
    animal = models.ForeignKey(Animal, related_name="story_reviews", on_delete=models.CASCADE, verbose_name="動物")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='story_reviews', verbose_name="用戶")
    age = models.PositiveIntegerField("年紀", null=True, blank=True)
    looks = models.CharField("顏值", max_length=20, choices=Review.LOOKS_CHOICES, blank=True, null=True)
    face = models.CharField("臉蛋", max_length=100, blank=True, null=True)
    temperament = models.CharField("氣質", max_length=100, blank=True, null=True)
    physique = models.CharField("體態", max_length=20, choices=Review.PHYSIQUE_CHOICES, blank=True, null=True)
    cup = models.CharField("罩杯類型", max_length=20, choices=Review.CUP_CHOICES, blank=True, null=True)
    cup_size = models.CharField("罩杯大小", max_length=5, blank=True, null=True)
    skin_texture = models.CharField("膚質", max_length=20, choices=Review.SKIN_TEXTURE_CHOICES, blank=True, null=True)
    skin_color = models.CharField("膚色", max_length=20, choices=Review.SKIN_COLOR_CHOICES, blank=True, null=True)
    music = models.CharField("音樂", max_length=20, choices=Review.MUSIC_CHOICES, blank=True, null=True)
    music_price = models.CharField("音樂價格", max_length=20, blank=True, null=True)
    sports = models.CharField("體育", max_length=20, choices=Review.SPORTS_CHOICES, blank=True, null=True)
    sports_price = models.CharField("體育價格", max_length=20, blank=True, null=True)
    scale = models.CharField("尺度", max_length=100, blank=True, null=True)
    content = models.TextField("心得內容", blank=True, null=True)
    created_at = models.DateTimeField("提交時間", default=timezone.now)
    approved = models.BooleanField("已審核", default=False, db_index=True)
    approved_at = models.DateTimeField("審核時間", null=True, blank=True, db_index=True)
    expires_at = models.DateTimeField("過期時間", null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-approved_at', '-created_at'] # Show approved first, then newest submitted
        verbose_name = "限時動態心得"
        verbose_name_plural = "限時動態心得"

    def __str__(self):
        return f"Story Review for {self.animal.name} by {self.user.username} ({'Approved' if self.approved else 'Pending'})"

    @property
    def is_active(self):
        """Checks if the story is approved and not expired."""
        return self.approved and self.expires_at and timezone.now() < self.expires_at

    @property
    def remaining_time_display(self):
        """Returns a user-friendly string of the remaining time."""
        if not self.is_active:
            return "已過期"
        now = timezone.now()
        remaining = self.expires_at - now
        total_seconds = int(remaining.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0: return f"{hours}小時"
        elif minutes > 0: return f"{minutes}分鐘"
        else: return "即將過期"

# --- Signal for StoryReview 保持不變 ---
@receiver(pre_save, sender=StoryReview)
def set_story_approval_times(sender, instance, **kwargs):
    try:
        original_instance = sender.objects.get(pk=instance.pk)
        approved_changed = original_instance.approved != instance.approved
    except sender.DoesNotExist:
        approved_changed = instance.approved

    if instance.approved and approved_changed:
        if not instance.approved_at:
            instance.approved_at = timezone.now()
            instance.expires_at = instance.approved_at + timedelta(hours=24)
    elif not instance.approved and approved_changed:
        instance.approved_at = None
        instance.expires_at = None

# --- WeeklySchedule Model 保持不變 ---
# WeeklySchedule 的顯示邏輯依賴 Hall 的 is_active，不受 is_visible 影響
class WeeklySchedule(models.Model):
    hall = models.ForeignKey(
        Hall,
        on_delete=models.CASCADE,
        verbose_name="館別",
        related_name='weekly_schedules' # Changed related_name to plural
    )
    schedule_image = models.ImageField(
        "班表圖片",
        upload_to='weekly_schedules/', # Store images in media/weekly_schedules/
        help_text="請上傳班表圖片",
    )
    order = models.PositiveIntegerField(
        "排序",
        default=0,
        help_text="用於排序同一個館別的多張班表圖片，數字越小越前面"
    )
    updated_at = models.DateTimeField("最後更新時間", auto_now=True)

    class Meta:
        # 排序: 先按館別排序(繼承Hall的排序), 再按班表自身排序
        ordering = ['hall__order', 'hall__name', 'order']
        verbose_name = "每週班表圖片" # Adjusted verbose name slightly
        verbose_name_plural = "每週班表圖片"

    def __str__(self):
        local_time_str = timezone.localtime(self.updated_at).strftime('%Y-%m-%d %H:%M') if self.updated_at else '未知時間'
        image_name = self.schedule_image.name.split('/')[-1] if self.schedule_image else '無圖片'
        # 在字串表示中也加上館別啟用/停用狀態 (不顯示前端隱藏狀態)
        hall_status = ""
        if self.hall:
             hall_status = "" if self.hall.is_active else " (館別停用)"
        return f"{self.hall.name}{hall_status} - 班表 {self.order} ({image_name}) - 更新於 {local_time_str}"