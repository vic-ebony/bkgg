# D:\bkgg\mybackend\myapp\admin.py (完整版 - 新增 PreBookingSlotAdmin)

from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse, path
from django.http import HttpResponseRedirect
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.apps import apps # <<<--- 導入 apps
import logging # <<<--- 導入 logging

# --- merge_transfer_animal_view import ---
try:
    from .views import merge_transfer_animal_view
except ImportError:
    merge_transfer_animal_view = None
    print("WARNING: merge_transfer_animal_view not found in myapp.views. Merge action may fail.")

# --- solo admin import ---
try:
    from solo.admin import SingletonModelAdmin
    DJANGO_SOLO_INSTALLED = True
except ImportError:
    SingletonModelAdmin = admin.ModelAdmin
    DJANGO_SOLO_INSTALLED = False

# --- Get models using apps.get_model ---
# Do this after imports and before they are used in register or inline
UserProfile = apps.get_model('myapp', 'UserProfile')
Hall = apps.get_model('myapp', 'Hall')
Animal = apps.get_model('myapp', 'Animal')
Review = apps.get_model('myapp', 'Review')
PendingAppointment = apps.get_model('myapp', 'PendingAppointment')
Note = apps.get_model('myapp', 'Note')
Announcement = apps.get_model('myapp', 'Announcement')
StoryReview = apps.get_model('myapp', 'StoryReview')
WeeklySchedule = apps.get_model('myapp', 'WeeklySchedule')
UserTitleRule = apps.get_model('myapp', 'UserTitleRule')
ReviewFeedback = apps.get_model('myapp', 'ReviewFeedback')
PreBookingSlot = apps.get_model('myapp', 'PreBookingSlot') # <<<--- 新增獲取 PreBookingSlot
SiteConfiguration = apps.get_model('myapp', 'SiteConfiguration')
# --- ---


# --- UserProfile Inline Admin ---
class UserProfileInline(admin.StackedInline):
    model = UserProfile # Now UserProfile is defined above
    can_delete = False
    verbose_name_plural = '使用者檔案 (慾望幣)'
    fk_name = 'user'
    fields = ('desire_coins',)
    readonly_fields = ()
# --- ---

# --- User Admin (Updated) ---
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff',
                    'get_desire_coins_display')
    list_select_related = ('profile',)

    @admin.display(description='慾望幣', ordering='profile__desire_coins')
    def get_desire_coins_display(self, instance):
        logger = logging.getLogger(__name__) # Get logger if needed
        try:
            if hasattr(instance, 'profile') and instance.profile:
                return instance.profile.desire_coins
            else:
                 # Fallback fetch if profile wasn't prefetched
                 profile = UserProfile.objects.filter(user=instance).first()
                 return profile.desire_coins if profile else 0
        except Exception as e:
             logger.warning(f"Error getting desire coins for {instance.username}: {e}")
             return '錯誤'
    # --- ---

# Unregister and re-register User with the updated UserAdmin
# Ensure User is unregistered before registering again if UserAdmin is redefined
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass # Ignore if it wasn't registered before (e.g., during initial setup)
admin.site.register(User, UserAdmin)
# --- User Admin 結束 ---


# --- Hall Admin ---
@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_active', 'is_visible', 'schedule_format_type')
    list_filter = ('is_active', 'is_visible', 'schedule_format_type')
    list_editable = ('order', 'is_active', 'is_visible')
    search_fields = ('name', 'address')
    fieldsets = (
        (None, {'fields': ('name', 'order', 'address')}),
        ('狀態與可見性', {'fields': ('is_active', 'is_visible')}),
        ('班表與解析', {'fields': ('schedule_format_type',)}),
    )
# --- Hall Admin 結束 ---


# --- Animal Admin ---
@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ('name', 'hall_display', 'fee', 'is_active', 'is_featured', 'aliases_display', 'order')
    list_filter = ('is_featured', 'hall__is_active', 'hall', 'is_active', 'is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer')
    search_fields = ('name', 'introduction', 'hall__name', 'aliases')
    list_editable = ('is_active', 'is_featured', 'order')
    fieldsets = (
        (None, {'fields': ('name', 'hall', 'is_active', 'order', 'photo')}),
        ('基本資料', {'fields': ('height', 'weight', 'cup_size', 'fee'), 'classes': ('collapse',)}),
        ('標籤與狀態', {'fields': ('is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer', 'is_featured')}),
        ('介紹與別名', {'fields': ('introduction', 'aliases')}),
        ('舊時段(參考)', {'fields': ('time_slot',), 'classes': ('collapse',)}),
        ('時間戳', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    autocomplete_fields = ['hall']
    list_select_related = ('hall',)
    readonly_fields = ('created_at', 'updated_at')
    actions = ['merge_transfer_animal']

    def get_urls(self):
        urls = super().get_urls()
        if merge_transfer_animal_view:
            custom_urls = [
                path(
                    '<int:animal_id>/merge-transfer/',
                    self.admin_site.admin_view(merge_transfer_animal_view),
                    name='myapp_animal_merge_transfer'
                )
            ]
            return custom_urls + urls
        return urls

    @admin.display(description='館別', ordering='hall__name')
    def hall_display(self, obj):
        if obj.hall:
            status_parts = []
            if not obj.hall.is_active: status_parts.append("已停用")
            if obj.hall.is_active and not obj.hall.is_visible: status_parts.append("前端隱藏")
            status_indicator = f" ({', '.join(status_parts)})" if status_parts else ""
            return f"{obj.hall.name}{status_indicator}"
        return "未分館"

    @admin.display(description='別名/曾用名')
    def aliases_display(self, obj):
         if isinstance(obj.aliases, list):
            display_aliases = [str(a) for a in obj.aliases[:3]]
            suffix = '...' if len(obj.aliases) > 3 else ''
            return ", ".join(display_aliases) + suffix
         elif isinstance(obj.aliases, str):
             return obj.aliases[:30] + ('...' if len(obj.aliases) > 30 else '')
         return obj.aliases

    @admin.action(description='合併/轉移選定的美容師資料')
    def merge_transfer_animal(self, request, queryset):
        if not merge_transfer_animal_view:
            self.message_user(request, "合併視圖未正確載入，無法執行操作。", messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())

        if queryset.count() != 1:
            self.message_user(request, "請只選擇一位美容師進行合併/轉移操作。", messages.WARNING)
            return HttpResponseRedirect(request.get_full_path())
        selected_animal = queryset.first()
        animal_id = selected_animal.id
        try:
            intermediate_url = reverse('admin:myapp_animal_merge_transfer', args=[animal_id])
            return HttpResponseRedirect(intermediate_url)
        except Exception as e:
            self.message_user(request, f"無法導向合併頁面，請檢查URL配置或視圖導入: {e}", messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())
# --- Animal Admin 結束 ---


# --- Review Admin ---
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_filter = ('approved', 'reward_granted', 'animal__hall__is_active', 'animal__hall', 'animal', 'user')
    list_display = ('animal', 'user', 'created_at', 'approved', 'approved_at', 'reward_granted')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall')
    date_hierarchy = 'approved_at'
    readonly_fields = ('created_at', 'approved_at', 'reward_granted')
# --- Review Admin 結束 ---


# --- PendingAppointment Admin ---
@admin.register(PendingAppointment)
class PendingAppointmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'added_at')
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal')
    search_fields = ('user__username', 'animal__name', 'animal__hall__name')
    list_select_related = ('user', 'animal', 'animal__hall')
# --- PendingAppointment Admin 結束 ---


# --- Note Admin ---
@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'updated_at')
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_select_related = ('user', 'animal', 'animal__hall')
    readonly_fields = ('created_at', 'updated_at')
# --- Note Admin 結束 ---


# --- Announcement Admin ---
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'content_summary', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'content')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    fields = ('title', 'content', 'is_active', 'created_at', 'updated_at')

    def content_summary(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_summary.short_description = '內容摘要'
# --- Announcement Admin 結束 ---


# --- StoryReview Admin ---
@admin.register(StoryReview)
class StoryReviewAdmin(admin.ModelAdmin):
    list_display = ('animal', 'user', 'created_at', 'approved', 'approved_at', 'expires_at', 'is_story_active_display', 'reward_granted')
    list_filter = ('approved', 'reward_granted', 'animal__hall__is_active', 'animal__hall', 'animal', 'user')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'approved_at', 'expires_at', 'reward_granted')
    fieldsets = (
        (None, {'fields': ('animal', 'user', 'approved', 'reward_granted')}),
        ('內容 (同心得)', {'fields': ('age', 'looks', 'face', 'temperament', 'physique', 'cup', 'cup_size', 'skin_texture', 'skin_color', 'music', 'music_price', 'sports', 'sports_price', 'scale', 'content')}),
        ('時間戳', {'fields': ('created_at', 'approved_at', 'expires_at'), 'classes': ('collapse',)}),
    )

    @admin.display(boolean=True, description='目前有效')
    def is_story_active_display(self, obj):
        # Make sure the StoryReview model has the 'is_active' property defined
        return obj.is_active if hasattr(obj, 'is_active') else False
# --- StoryReview Admin 結束 ---


# --- WeeklySchedule Admin ---
@admin.register(WeeklySchedule)
class WeeklyScheduleAdmin(admin.ModelAdmin):
    list_display = ('hall', 'order', 'schedule_image_preview', 'updated_at')
    list_filter = ('hall__is_active', 'hall',)
    search_fields = ('hall__name',)
    readonly_fields = ('updated_at',)
    list_select_related = ('hall',)
    autocomplete_fields = ['hall']
    list_editable = ('order',)
    fields = ('hall', 'schedule_image', 'order', 'updated_at')

    @admin.display(description='班表圖片預覽')
    def schedule_image_preview(self, obj):
        if obj.schedule_image:
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px;" />', obj.schedule_image.url)
        return "無圖片"
# --- WeeklySchedule Admin 結束 ---


# --- UserTitleRule Admin ---
@admin.register(UserTitleRule)
class UserTitleRuleAdmin(admin.ModelAdmin):
    list_display = ('title_name', 'min_review_count', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title_name',)
    list_editable = ('min_review_count', 'is_active',)
    fieldsets = ( (None, {'fields': ('title_name', 'min_review_count', 'is_active')}), )
# --- UserTitleRule Admin 結束 ---


# --- ReviewFeedback Admin ---
@admin.register(ReviewFeedback)
class ReviewFeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_target_review_display', 'feedback_type', 'created_at')
    list_filter = ('feedback_type', 'created_at')
    search_fields = ('user__username', 'review__id', 'story_review__id')
    list_select_related = ('user', 'review', 'story_review', 'review__animal', 'story_review__animal')
    readonly_fields = ('user', 'review', 'story_review', 'feedback_type', 'created_at')

    @admin.display(description='目標心得', ordering='review__id')
    def get_target_review_display(self, obj):
        if obj.review: user_name = obj.review.user.username if obj.review.user else "未知用戶"; return f"一般心得 #{obj.review.id} (作者: {user_name})"
        elif obj.story_review: user_name = obj.story_review.user.username if obj.story_review.user else "未知用戶"; return f"限時動態 #{obj.story_review.id} (作者: {user_name})"
        return "N/A"
# --- ReviewFeedback Admin 結束 ---


# --- PreBookingSlot Admin (搶約專區時段管理) --- NEW ---
@admin.register(PreBookingSlot)
class PreBookingSlotAdmin(admin.ModelAdmin):
    list_display = ('animal_display', 'date', 'time_slots', 'updated_at')
    list_filter = ('date', 'animal__hall__is_active', 'animal__hall', 'animal__is_active')
    search_fields = ('animal__name', 'time_slots', 'date__isoformat') # 允許搜尋 YYYY-MM-DD
    autocomplete_fields = ['animal']
    date_hierarchy = 'date'
    list_select_related = ('animal', 'animal__hall')
    ordering = ('-date', 'animal__name')
    fields = ('animal', 'date', 'time_slots', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='美容師 (館別)', ordering='animal__name')
    def animal_display(self, obj):
        hall_name = obj.animal.hall.name if obj.animal.hall else '未分館'
        hall_status = ""
        if obj.animal.hall and not obj.animal.hall.is_active: hall_status = " (館停用)"
        animal_status = "" if obj.animal.is_active else " (停用)"
        return f"{obj.animal.name}{animal_status} ({hall_name}{hall_status})"
# --- PreBookingSlot Admin 結束 ---


# --- SiteConfiguration Admin ---
if DJANGO_SOLO_INSTALLED:
    admin.site.register(SiteConfiguration, SingletonModelAdmin)
else:
    @admin.register(SiteConfiguration)
    class SiteConfigurationAdmin(admin.ModelAdmin):
         pass
# --- SiteConfiguration Admin 結束 ---