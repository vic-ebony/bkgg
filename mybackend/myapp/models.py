# D:\bkgg\mybackend\myapp\models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from django.db import transaction
from django.db.models import Q, Count, F, Case, When, Value
from django.core.exceptions import ValidationError
from datetime import timedelta # <<< 確保導入 timedelta
import logging

# --- 假設你已安裝 django-solo 來管理單例模型 ---
try:
    from solo.models import SingletonModel
    DJANGO_SOLO_INSTALLED = True
except ImportError:
    SingletonModel = models.Model # Fallback if solo is not installed
    DJANGO_SOLO_INSTALLED = False
    print("WARNING: django-solo not installed. SiteConfiguration will not be a singleton.")
# --- ---

logger = logging.getLogger(__name__) # <<< 確保 logger 初始化

# --- Hall Model (保持不變) ---
class Hall(models.Model):
    name = models.CharField("館別名稱", max_length=100)
    order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("啟用中", default=True, db_index=True)
    is_visible = models.BooleanField(
        "前端顯示",
        default=True,
        db_index=True,
        help_text="勾選此項，該館別按鈕才會顯示在前端頁面。取消勾選可隱藏按鈕，但不影響後台操作或資料關聯。"
    )
    SCHEDULE_FORMAT_CHOICES = [
        ('format_a', '格式A (舊LINE格式)'),
        ('chatanghui', '茶湯會格式'),
        ('xinyuan', '芯苑格式'),
        ('shouzhongqing', '手中情格式'),
        ('pokemon', '寶可夢格式'),
        ('aibao', '愛寶格式'),
        ('hanxiang', '含香格式'),
        ('pandora', '潘朵拉格式'),
        ('wangfei', '王妃格式'),
        ('lezuan', '樂鑽格式'),
    ]
    schedule_format_type = models.CharField(
        "班表格式類型",
        max_length=20,
        choices=SCHEDULE_FORMAT_CHOICES,
        default='format_a',
        help_text="指定此館別使用的班表文字格式，以便系統選擇正確的解析器"
    )

    class Meta:
        ordering = ['-is_active', 'order', 'name']
        verbose_name = "館別"
        verbose_name_plural = "館別"

    def __str__(self):
        status_parts = []
        if self.is_active:
            status_parts.append("啟用")
            if not self.is_visible:
                status_parts.append("前端隱藏")
        else:
            status_parts.append("停用")
        format_display = self.get_schedule_format_type_display()
        status_parts.append(f"格式: {format_display}")
        status_str = ", ".join(status_parts)
        return f"{self.name} ({status_str})"

    def clean(self):
        if not self.is_active and self.is_visible:
            self.is_visible = False

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

# --- Animal Model (保持不變) ---
class Animal(models.Model):
    name = models.CharField("姓名", max_length=100, db_index=True)
    hall = models.ForeignKey(
        Hall,
        verbose_name="目前館別",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='animals'
    )
    height = models.IntegerField("身高", blank=True, null=True)
    weight = models.IntegerField("體重", blank=True, null=True)
    cup_size = models.CharField("罩杯", max_length=10, blank=True, null=True)
    fee = models.IntegerField("台費", blank=True, null=True)
    introduction = models.TextField("介紹", blank=True, null=True)
    photo = models.ImageField("照片", upload_to='animal_photos/', blank=True, null=True)
    aliases = models.JSONField(
        "別名/曾用名",
        default=list, blank=True,
        help_text='儲存可能的暱稱或舊名列表 (例如 ["小花", "小花@A店"])'
    )
    time_slot = models.CharField(
        "預設時段(舊)", max_length=200, blank=True,
        help_text="此欄位不再用於顯示每日班表，僅供參考。"
    )
    is_active = models.BooleanField("啟用中", default=True, db_index=True)
    order = models.PositiveIntegerField("排序", default=999)
    is_newcomer = models.BooleanField("新人", default=False)
    is_hot = models.BooleanField("熱門", default=False)
    is_exclusive = models.BooleanField("獨家", default=False)
    is_hidden_edition = models.BooleanField("隱藏版", default=False)
    is_recommended = models.BooleanField("推薦", default=False)
    is_featured = models.BooleanField("設為主打", default=False, db_index=True, help_text="勾選此項，將此美容師顯示在首頁主打區塊（建議只勾選一位）")
    created_at = models.DateTimeField("建立時間", auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ['hall__order', 'order', 'name']
        verbose_name = "美容師"
        verbose_name_plural = "美容師"

    def __str__(self):
        hall_name = self.hall.name if self.hall else '未分館'
        status = "" if self.is_active else " (停用)"
        hall_status = ""
        if self.hall and not self.hall.is_active:
            hall_status = " (館別停用)"
        size_info = self.size_display
        fee_info = f"{self.fee}元" if self.fee is not None else "未填"
        featured_status = " [主打]" if self.is_featured else ""
        return f"{hall_name}{hall_status} - {self.name}{featured_status} (身材:{size_info} | 台費:{fee_info} | ID:{self.pk}){status}"

    @property
    def size_display(self):
        parts = []
        if self.height: parts.append(str(self.height))
        if self.weight: parts.append(str(self.weight))
        if self.cup_size: parts.append(self.cup_size)
        return ".".join(parts) if parts else "未填"

# --- Review Model (保持不變) ---
class Review(models.Model):
    animal = models.ForeignKey(Animal, related_name="reviews", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    age = models.PositiveIntegerField("年紀", null=True, blank=True)
    LOOKS_CHOICES = [ ('S級 (一見難忘)', 'S級 (一見難忘)'), ('A級 (出眾)', 'A級 (出眾)'), ('B級 (優異)', 'B級 (優異)'), ('C級 (中上)', 'C級 (中上)'), ('D級 (大眾)', 'D級 (大眾)'), ('E級 (較平凡)', 'E級 (較平凡)'), ]
    looks = models.CharField("顏值", max_length=20, choices=LOOKS_CHOICES, blank=True, null=True)
    face = models.CharField("臉蛋", max_length=100, blank=True, null=True)
    temperament = models.CharField("氣質", max_length=100, blank=True, null=True)
    PHYSIQUE_CHOICES = [ ('骨感', '骨感'), ('瘦', '瘦'), ('瘦有肉', '瘦有肉'), ('標準', '標準'), ('曲線迷人', '曲線迷人'), ('瘦偏肉', '瘦偏肉'), ('微肉', '微肉'), ('棉花糖', '棉花糖'), ]
    physique = models.CharField("體態", max_length=20, choices=PHYSIQUE_CHOICES, blank=True, null=True)
    CUP_CHOICES = [ ('天然', '天然'), ('醫美', '醫美'), ('自體醫美', '自體醫美'), ('不確定', '不確定'), ]
    cup = models.CharField("罩杯類型", max_length=20, choices=CUP_CHOICES, blank=True, null=True)
    cup_size = models.CharField("罩杯大小", max_length=5, blank=True, null=True)
    SKIN_TEXTURE_CHOICES = [ ('絲滑', '絲滑'), ('還不錯', '還不錯'), ('正常', '正常'), ('普通', '普通'), ]
    skin_texture = models.CharField("膚質", max_length=20, choices=SKIN_TEXTURE_CHOICES, blank=True, null=True)
    SKIN_COLOR_CHOICES = [ ('白皙', '白皙'), ('偏白', '偏白'), ('正常黃', '正常黃'), ('偏黃', '偏黃'), ('健康黑', '健康黑'), ]
    skin_color = models.CharField("膚色", max_length=20, choices=SKIN_COLOR_CHOICES, blank=True, null=True)
    MUSIC_CHOICES = [ ('未詢問', '未詢問'), ('無此服務', '無此服務'), ('可加值', '可加值 (費用待填)'), ('自談', '可加值 (自談)'), ]
    music = models.CharField("音樂", max_length=20, choices=MUSIC_CHOICES, blank=True, null=True)
    music_price = models.CharField("音樂價格", max_length=20, blank=True, null=True)
    SPORTS_CHOICES = [ ('未詢問', '未詢問'), ('無此服務', '無此服務'), ('可加值', '可加值 (費用待填)'), ('自談', '可加值 (自談)'), ('體含音', '體含音'), ]
    sports = models.CharField("體育", max_length=20, choices=SPORTS_CHOICES, blank=True, null=True)
    sports_price = models.CharField("體育價格", max_length=20, blank=True, null=True)
    scale = models.CharField("尺度", max_length=100, blank=True, null=True)
    content = models.TextField("心得", blank=True, null=True)
    created_at = models.DateTimeField("建立時間", default=timezone.now)
    approved = models.BooleanField("已審核", default=False, db_index=True)
    approved_at = models.DateTimeField("審核時間", null=True, blank=True, db_index=True)
    reward_granted = models.BooleanField("已獎勵次數", default=False, help_text="標記此心得是否已觸發增加使用次數")

    class Meta:
        ordering = ['-approved_at', '-created_at']
        verbose_name = "心得評論"
        verbose_name_plural = "心得評論"

    def __str__(self):
        animal_name = self.animal.name if self.animal else "未知美容師"
        user_name = self.user.username if self.user else "未知用戶"
        status = "已審核" if self.approved else "待審核"
        reward_status = "已獎勵" if self.reward_granted else "未獎勵"
        approved_time_str = f"於 {timezone.localtime(self.approved_at).strftime('%Y-%m-%d %H:%M')}" if self.approved_at else ""
        return f"{animal_name} 的心得 (由 {user_name}) - {status}{approved_time_str}, {reward_status}"

# --- PendingAppointment Model (保持不變) ---
class PendingAppointment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pending_appointments')
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='pending_users')
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'animal')
        ordering = ['-added_at']
        verbose_name = "待約項目"
        verbose_name_plural = "待約項目"

    def __str__(self):
        animal_name = self.animal.name if self.animal else "未知美容師"
        user_name = self.user.username if self.user else "未知用戶"
        return f"{user_name} - {animal_name}"

# --- Note Model (保持不變) ---
class Note(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notes')
    animal = models.ForeignKey(Animal, on_delete=models.CASCADE, related_name='notes')
    content = models.TextField("筆記內容", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("user", "animal"),)
        ordering = ['-updated_at']
        verbose_name = "用戶筆記"
        verbose_name_plural = "用戶筆記"

    def __str__(self):
        animal_name = self.animal.name if self.animal else "未知美容師"
        user_name = self.user.username if self.user else "未知用戶"
        return f"Note for {animal_name} by {user_name}"

# --- Announcement Model (保持不變) ---
class Announcement(models.Model):
    title = models.CharField("標題", max_length=200, blank=True, null=True)
    content = models.TextField("公告內容")
    is_active = models.BooleanField("啟用中", default=True, db_index=True)
    created_at = models.DateTimeField("建立時間", auto_now_add=True)
    updated_at = models.DateTimeField("更新時間", auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "公告"
        verbose_name_plural = "公告"

    def __str__(self):
        return self.title or f"公告 #{self.id}"

# --- StoryReview Model (保持不變) ---
class StoryReview(models.Model):
    animal = models.ForeignKey(Animal, related_name="story_reviews", on_delete=models.CASCADE, verbose_name="美容師")
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
    reward_granted = models.BooleanField("已獎勵次數", default=False, help_text="標記此心得是否已觸發增加使用次數")

    class Meta:
        ordering = ['-approved_at', '-created_at']
        verbose_name = "限時動態心得"
        verbose_name_plural = "限時動態心得"

    def __str__(self):
        animal_name = self.animal.name if self.animal else "未知美容師"
        user_name = self.user.username if self.user else "未知用戶"
        status = '已審核' if self.approved else '待審核'
        reward_status = "已獎勵" if self.reward_granted else "未獎勵"
        active_status = "有效" if self.is_active else "無效/過期"
        approved_time_str = f"於 {timezone.localtime(self.approved_at).strftime('%Y-%m-%d %H:%M')}" if self.approved_at else ""
        return f"限時動態: {animal_name} (由 {user_name}) - {status}{approved_time_str}, {reward_status}, {active_status}"

    @property
    def is_active(self):
        return self.approved and self.expires_at and timezone.now() < self.expires_at

    @property
    def remaining_time_display(self):
        if not self.is_active: return "已過期"
        now = timezone.now()
        remaining = self.expires_at - now
        total_seconds = int(remaining.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 0: return f"{hours}小時"
        elif minutes > 0: return f"{minutes}分鐘"
        else: return "即將過期"

# --- WeeklySchedule Model (保持不變) ---
class WeeklySchedule(models.Model):
    hall = models.ForeignKey(Hall, on_delete=models.CASCADE, verbose_name="館別", related_name='weekly_schedules')
    schedule_image = models.ImageField("班表圖片", upload_to='weekly_schedules/', help_text="請上傳班表圖片",)
    order = models.PositiveIntegerField("排序", default=0, help_text="數字越小越前面")
    updated_at = models.DateTimeField("最後更新時間", auto_now=True)

    class Meta:
        ordering = ['hall__order', 'hall__name', 'order']
        verbose_name = "每週班表圖片"
        verbose_name_plural = "每週班表圖片"

    def __str__(self):
        hall_name = self.hall.name if self.hall else "未知館別"
        local_time_str = timezone.localtime(self.updated_at).strftime('%Y-%m-%d %H:%M') if self.updated_at else '未知時間'
        image_name = self.schedule_image.name.split('/')[-1] if self.schedule_image else '無圖片'
        hall_status = ""
        if self.hall and not self.hall.is_active: hall_status = " (館別停用)"
        return f"{hall_name}{hall_status} - 班表 {self.order} ({image_name}) - 更新於 {local_time_str}"

# --- UserTitleRule Model (保持不變) ---
class UserTitleRule(models.Model):
    title_name = models.CharField( "稱號名稱", max_length=50, unique=True, help_text="例如：新手上路、評論達人" )
    min_review_count = models.PositiveIntegerField( "最低心得數", unique=True, help_text="使用者累積的已審核心得總數達到此數量(包含)即可獲得此稱號" )
    is_active = models.BooleanField( "啟用中", default=True, db_index=True, help_text="取消勾選可暫時停用此稱號規則，而不需刪除。" )
    class Meta: ordering = ['-min_review_count']; verbose_name = "使用者稱號規則"; verbose_name_plural = "使用者稱號規則"
    def __str__(self): status = "啟用" if self.is_active else "停用"; return f"{self.title_name} (≥ {self.min_review_count} 篇) - {status}"
    def clean(self):
        if self.min_review_count < 1: self.min_review_count = 1

# --- ReviewFeedback Model (保持不變) ---
class ReviewFeedback(models.Model):
    FEEDBACK_CHOICES = [ ('good_to_have_you', '有你真好'), ('good_looking', '人帥真好'), ]
    user = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_feedback', verbose_name="回饋者" )
    review = models.ForeignKey( Review, on_delete=models.CASCADE, null=True, blank=True, related_name='feedback', verbose_name="一般心得" )
    story_review = models.ForeignKey( StoryReview, on_delete=models.CASCADE, null=True, blank=True, related_name='feedback', verbose_name="限時動態心得" )
    feedback_type = models.CharField( "回饋類型", max_length=20, choices=FEEDBACK_CHOICES, db_index=True )
    created_at = models.DateTimeField("回饋時間", default=timezone.now)
    class Meta: ordering = ['-created_at']; verbose_name = "心得回饋記錄"; verbose_name_plural = "心得回饋記錄"; unique_together = [ ('user', 'review', 'feedback_type'), ('user', 'story_review', 'feedback_type'), ]; indexes = [ models.Index(fields=['review', 'feedback_type']), models.Index(fields=['story_review', 'feedback_type']), ]
    def clean(self):
        if self.review is None and self.story_review is None: raise ValidationError("必須關聯一篇一般心得或限時動態心得。")
        if self.review is not None and self.story_review is not None: raise ValidationError("不能同時關聯一般心得和限時動態心得。")
    def __str__(self): target_type = "一般心得" if self.review else "限時動態"; target_id = self.review.id if self.review else self.story_review.id; user_name = self.user.username if self.user else "未知用戶"; return f"{user_name} 對 {target_type} #{target_id} 給予 '{self.get_feedback_type_display()}' 回饋"

# --- UserProfile Model (包含 max_ 欄位，保持不變) ---
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    pending_list_limit = models.PositiveIntegerField("待約清單剩餘次數", default=10)
    notes_limit = models.PositiveIntegerField("我的筆記剩餘次數", default=10)
    max_pending_limit = models.PositiveIntegerField("待約清單最大上限", default=10, help_text="使用者當前可用的待約總額度")
    max_notes_limit = models.PositiveIntegerField("我的筆記最大上限", default=10, help_text="使用者當前可用的筆記總額度")

    class Meta:
        verbose_name = "使用者檔案"
        verbose_name_plural = "使用者檔案"

    def __str__(self):
        return f"{self.user.username}'s Profile (Pending:{self.pending_list_limit}/{self.max_pending_limit}, Notes:{self.notes_limit}/{self.max_notes_limit})"

# --- SiteConfiguration 模型 (保持不變) ---
class SiteConfiguration(SingletonModel):
    site_logo = models.ImageField("網站 Logo (頁首左上角)", upload_to='site_config/', blank=True, null=True, help_text="建議使用透明背景的 PNG 圖片，高度約 40-50px")

    def __str__(self):
        return "網站設定"

    class Meta:
        verbose_name = "網站設定"
        verbose_name_plural = "網站設定"
# --- SiteConfiguration 模型結束 ---


# --- Signals ---

# 1. 自動創建 UserProfile (初始化 max limit - 保持不變)
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        initial_pending_limit = 10
        initial_notes_limit = 10
        UserProfile.objects.create(
            user=instance,
            pending_list_limit=initial_pending_limit,
            notes_limit=initial_notes_limit,
            max_pending_limit=initial_pending_limit,
            max_notes_limit=initial_notes_limit
        )
        logger.info(f"UserProfile created for {instance.username} with initial limits (Remaining/Max): P={initial_pending_limit}/{initial_pending_limit}, N={initial_notes_limit}/{initial_notes_limit}")

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        try:
            # 確保 Max Limit 至少和 Remaining Limit 一樣大
            if instance.profile.max_pending_limit < instance.profile.pending_list_limit:
                instance.profile.max_pending_limit = instance.profile.pending_list_limit
            if instance.profile.max_notes_limit < instance.profile.notes_limit:
                instance.profile.max_notes_limit = instance.profile.notes_limit
            instance.profile.save()
        except Exception as e:
            logger.error(f"Error saving profile for user {instance.username} in save_user_profile signal: {e}", exc_info=True)
    else:
        # 如果 profile 不存在，調用 create_user_profile 中的邏輯來創建
        create_user_profile(sender=sender, instance=instance, created=True)


# --- *** NEW: 合併 Review 的 pre_save 和獎勵邏輯 *** ---
@receiver(pre_save, sender=Review)
def handle_review_pre_save_and_reward(sender, instance, **kwargs):
    original_instance = None
    try:
        if instance.pk: # Check if it's an update
            original_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        pass # It's a new instance

    # 1. 處理 approved_at
    approved_changed_to_true = False
    if original_instance:
        # Check if approved status changed from False to True
        if not original_instance.approved and instance.approved:
            approved_changed_to_true = True
            if not instance.approved_at: # Only set if not already set (e.g., manual input)
                instance.approved_at = timezone.now()
                logger.info(f"[PRE_SAVE] Review {instance.pk}: Approved status changed to True. Setting approved_at to {instance.approved_at}")
        # Check if approved status changed from True to False
        elif original_instance.approved and not instance.approved:
            instance.approved_at = None # Clear approval time if unapproved
            instance.reward_granted = False # <<< 重置獎勵狀態，如果取消審核
            logger.info(f"[PRE_SAVE] Review {instance.pk}: Approved status changed to False. Clearing approved_at and reward_granted.")
    elif instance.approved: # Handle new instance being created as approved
        approved_changed_to_true = True
        if not instance.approved_at:
            instance.approved_at = timezone.now()
            logger.info(f"[PRE_SAVE] Review (New): Created as approved. Setting approved_at to {instance.approved_at}")

    # 2. *** 處理獎勵邏輯 *** (只有在狀態從 False 變為 True 且未獎勵時執行)
    if approved_changed_to_true and not instance.reward_granted:
        try:
            # 獲取 Profile (不鎖定)
            profile = UserProfile.objects.get(user=instance.user)

            # 準備更新 profile 的 F() 表達式
            profile.pending_list_limit = F('pending_list_limit') + 3
            profile.notes_limit = F('notes_limit') + 3
            profile.max_pending_limit = F('max_pending_limit') + 3
            profile.max_notes_limit = F('max_notes_limit') + 3
            profile.save(update_fields=[
                'pending_list_limit', 'notes_limit',
                'max_pending_limit', 'max_notes_limit'
            ])

            # 標記獎勵已發放 (將在同一個 save 操作中寫入)
            instance.reward_granted = True
            logger.info(f"[PRE_SAVE] Review {instance.pk or '(New)'}: Granting +3 uses (Remaining & Max) to {instance.user.username}. Reward Granted flag set.")

        except UserProfile.DoesNotExist:
            logger.error(f"[PRE_SAVE] UserProfile not found for user {instance.user.username} (ID: {instance.user.id}) when attempting reward for Review {instance.pk or '(New)'}")
            # 獎勵失敗，保持 reward_granted 為 False
        except Exception as e:
            logger.error(f"[PRE_SAVE] Error attempting reward for Review {instance.pk or '(New)'} user {instance.user.username}: {e}", exc_info=True)
            # 獎勵失敗，保持 reward_granted 為 False

# --- *** REMOVED/COMMENTED OUT: Old Review post_save reward signal *** ---
# @receiver(post_save, sender=Review)
# def grant_reward_for_review(sender, instance, created, **kwargs):
#    # ... (Old logic removed) ...
#    pass

# --- *** REMOVED/COMMENTED OUT: Old Review pre_save time setting signal *** ---
# @receiver(pre_save, sender=Review)
# def set_review_approval_time(sender, instance, **kwargs):
#    # ... (Old logic removed) ...
#    pass


# --- *** NEW: 合併 StoryReview 的 pre_save 和獎勵邏輯 *** ---
@receiver(pre_save, sender=StoryReview)
def handle_story_pre_save_and_reward(sender, instance, **kwargs):
    original_instance = None
    try:
        if instance.pk:
            original_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        pass

    # 1. 處理 approved_at 和 expires_at
    approved_changed_to_true = False
    if original_instance:
        if not original_instance.approved and instance.approved:
            approved_changed_to_true = True
            if not instance.approved_at: instance.approved_at = timezone.now()
            # Set expires_at only if approved_at is being set now or already exists
            if instance.approved_at and not instance.expires_at:
                 instance.expires_at = instance.approved_at + timedelta(hours=24)
            logger.info(f"[PRE_SAVE] StoryReview {instance.pk}: Approved change True. Set approved_at: {instance.approved_at}, expires_at: {instance.expires_at}")
        elif original_instance.approved and not instance.approved:
            instance.approved_at = None
            instance.expires_at = None
            instance.reward_granted = False # <<< 重置獎勵狀態
            logger.info(f"[PRE_SAVE] StoryReview {instance.pk}: Approved change False. Cleared times and reward_granted.")
    elif instance.approved: # New instance created as approved
        approved_changed_to_true = True
        if not instance.approved_at: instance.approved_at = timezone.now()
        if instance.approved_at and not instance.expires_at:
             instance.expires_at = instance.approved_at + timedelta(hours=24)
        logger.info(f"[PRE_SAVE] StoryReview (New): Created approved. Set approved_at: {instance.approved_at}, expires_at: {instance.expires_at}")

    # 2. *** 處理獎勵邏輯 *** (只有在從 False 變 True，未獎勵，且未過期時執行)
    # Need to use instance.approved_at because expires_at depends on it being set first
    current_approved_at = instance.approved_at or (timezone.now() if approved_changed_to_true else None)
    current_expires_at = instance.expires_at or (current_approved_at + timedelta(hours=24) if current_approved_at else None)

    is_valid_for_reward = (
        approved_changed_to_true and
        not instance.reward_granted and
        current_expires_at and # Ensure expiry time is calculated
        current_expires_at > timezone.now() # Ensure not expired *now*
    )

    if is_valid_for_reward:
        try:
            profile = UserProfile.objects.get(user=instance.user)
            profile.pending_list_limit = F('pending_list_limit') + 1
            profile.notes_limit = F('notes_limit') + 1
            profile.max_pending_limit = F('max_pending_limit') + 1
            profile.max_notes_limit = F('max_notes_limit') + 1
            profile.save(update_fields=[
                'pending_list_limit', 'notes_limit',
                'max_pending_limit', 'max_notes_limit'
            ])

            instance.reward_granted = True
            logger.info(f"[PRE_SAVE] StoryReview {instance.pk or '(New)'}: Granting +1 uses (Rem & Max) to {instance.user.username}. Reward Granted flag set.")

        except UserProfile.DoesNotExist:
             logger.error(f"[PRE_SAVE] UserProfile not found for user {instance.user.username} (ID: {instance.user.id}) when attempting reward for StoryReview {instance.pk or '(New)'}")
        except Exception as e:
            logger.error(f"[PRE_SAVE] Error attempting reward for StoryReview {instance.pk or '(New)'} user {instance.user.username}: {e}", exc_info=True)
    elif approved_changed_to_true and not instance.reward_granted:
         # If changed to approved but expired or missing expiry, log why no reward
         expiry_status = "Not Set" if not current_expires_at else ("Expired" if current_expires_at <= timezone.now() else "Valid")
         logger.warning(f"[PRE_SAVE] StoryReview {instance.pk or '(New)'}: Approved change True but NO reward granted. Reason: reward_granted={instance.reward_granted}, expiry_status={expiry_status} (Expires: {current_expires_at})")


# --- *** REMOVED/COMMENTED OUT: Old StoryReview pre_save time setting signal *** ---
# @receiver(pre_save, sender=StoryReview)
# def set_story_approval_times(sender, instance, **kwargs):
#     # ... (Old logic removed) ...
#     pass

# --- *** REMOVED/COMMENTED OUT: Old StoryReview post_save reward signal *** ---
# @receiver(post_save, sender=StoryReview)
# def grant_reward_for_story_review(sender, instance, created, **kwargs):
#     # ... (Old logic removed) ...
#     pass

# --- Signals 結束 *** ---