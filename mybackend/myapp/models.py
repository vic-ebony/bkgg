# models.py
from django.db import models
from django.conf import settings
from django.utils import timezone # Import timezone
from django.db.models.signals import pre_save # Import pre_save signal
from django.dispatch import receiver # Import receiver
from datetime import timedelta # Import timedelta

class Hall(models.Model):
    name = models.CharField("館別名稱", max_length=100)
    order = models.PositiveIntegerField("排序", default=0) # Add order field

    class Meta:
        ordering = ['order', 'name'] # Order halls

    def __str__(self):
        return self.name

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
    hall = models.ForeignKey(Hall, verbose_name="館別", on_delete=models.SET_NULL, null=True, blank=True, related_name='animals')
    photo = models.ImageField("照片", upload_to='animal_photos/', blank=True, null=True)
    is_newcomer = models.BooleanField("新人", default=False)
    is_hot = models.BooleanField("熱門", default=False)
    is_exclusive = models.BooleanField("獨家", default=False)
    is_hidden_edition = models.BooleanField("隱藏版", default=False)
    # --- 新增欄位 ---
    is_recommended = models.BooleanField("推薦", default=False) # Add recommended flag
    # --- End 新增欄位 ---
    is_active = models.BooleanField("啟用中", default=True) # Add active flag
    order = models.PositiveIntegerField("排序", default=0) # Add order field
    introduction = models.TextField("介紹", blank=True, null=True)

    class Meta:
        ordering = ['hall__order', 'order', 'name'] # Order animals

    def __str__(self):
        return f"{self.hall.name if self.hall else '未分館'} - {self.name}"

    @property
    def size_display(self):
        parts = []
        if self.height: parts.append(str(self.height))
        if self.weight: parts.append(str(self.weight))
        if self.cup_size: parts.append(self.cup_size)
        return ".".join(parts) if parts else ""

    # Cache approved review count (Optional but good for performance)
    # You would need signals or a periodic task to update this
    # approved_review_count_cached = models.PositiveIntegerField(default=0, editable=False)


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

class PendingAppointment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pending_appointments')
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='pending_users')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'animal') # Prevent duplicates
        ordering = ['-added_at']

    def __str__(self):
        return f"{self.user.username} - {self.animal.name}"

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

# --- New Announcement Model ---
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

# --- START: New StoryReview Model ---
class StoryReview(models.Model):
    animal = models.ForeignKey(Animal, related_name="story_reviews", on_delete=models.CASCADE, verbose_name="動物")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='story_reviews', verbose_name="用戶")

    # Fields copied from Review (adjust verbose_name slightly if needed)
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

    # Story-specific fields
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

        if hours > 0:
            return f"{hours}小時"
        elif minutes > 0:
            return f"{minutes}分鐘"
        else:
            return "即將過期"

# --- Signal to set approved_at and expires_at when approved is set to True ---
@receiver(pre_save, sender=StoryReview)
def set_story_approval_times(sender, instance, **kwargs):
    try:
        # Get the original instance from DB to check if 'approved' changed
        original_instance = sender.objects.get(pk=instance.pk)
        approved_changed = original_instance.approved != instance.approved
    except sender.DoesNotExist:
        # This is a new instance or pk is not set yet
        approved_changed = instance.approved # If new and approved is True, it counts as changed

    if instance.approved and approved_changed:
        # If being approved (and wasn't approved before)
        if not instance.approved_at: # Set times only if not already set
            instance.approved_at = timezone.now()
            instance.expires_at = instance.approved_at + timedelta(hours=24)
    elif not instance.approved and approved_changed:
        # If being un-approved (and was approved before)
        instance.approved_at = None
        instance.expires_at = None
# --- END: New StoryReview Model ---