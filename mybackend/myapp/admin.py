# D:\bkgg\mybackend\myapp\admin.py
from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse, path
from django.http import HttpResponseRedirect
from .models import (
    Hall, Animal, Review, PendingAppointment, Note, Announcement,
    StoryReview, WeeklySchedule, UserTitleRule, ReviewFeedback,
    UserProfile, SiteConfiguration
)
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .views import merge_transfer_animal_view

# --- 導入 django-solo admin (如果使用) ---
try:
    from solo.admin import SingletonModelAdmin
    DJANGO_SOLO_INSTALLED = True
except ImportError:
    SingletonModelAdmin = admin.ModelAdmin # Fallback
    DJANGO_SOLO_INSTALLED = False
# --- ---


# --- *** 修改 UserProfile Inline Admin (顯示上限) *** ---
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = '使用者檔案 (次數與上限)'
    fk_name = 'user'
    # 顯示剩餘和最大上限
    fields = ('pending_list_limit', 'max_pending_limit', 'notes_limit', 'max_notes_limit')
    # 將最大上限設為唯讀，因為它應該由獎勵機制自動管理
    readonly_fields = ('max_pending_limit', 'max_notes_limit')
# --- *** UserProfile Inline Admin 修改結束 *** ---

# --- User Admin (加入上限顯示) ---
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff',
                    'get_pending_limit_display', 'get_notes_limit_display') # 修改顯示欄位
    list_select_related = ('profile',) # 保持不變

    @admin.display(description='待約 (剩餘/上限)') # 修改描述
    def get_pending_limit_display(self, instance):
        try:
            # 同時顯示剩餘和上限
            return f"{instance.profile.pending_list_limit} / {instance.profile.max_pending_limit}"
        except UserProfile.DoesNotExist:
            return 'N/A'

    @admin.display(description='筆記 (剩餘/上限)') # 修改描述
    def get_notes_limit_display(self, instance):
         try:
             # 同時顯示剩餘和上限
             return f"{instance.profile.notes_limit} / {instance.profile.max_notes_limit}"
         except UserProfile.DoesNotExist:
             return 'N/A'

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

# --- Hall Admin (保持不變) ---
@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_active', 'is_visible', 'schedule_format_type')
    list_filter = ('is_active', 'is_visible', 'schedule_format_type')
    list_editable = ('order', 'is_active', 'is_visible')
    search_fields = ('name',)
    fieldsets = (
        (None, {'fields': ('name', 'order')}),
        ('狀態與可見性', {'fields': ('is_active', 'is_visible')}),
        ('班表與解析', {'fields': ('schedule_format_type',)}),
    )

# --- Animal Admin (保持不變) ---
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
        custom_urls = [
            path(
                '<int:animal_id>/merge-transfer/',
                self.admin_site.admin_view(merge_transfer_animal_view),
                name='myapp_animal_merge_transfer'
            )
        ]
        return custom_urls + urls

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

# --- Review Admin (保持不變) ---
# ... (與之前相同，保持不變) ...
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_filter = ('approved', 'reward_granted', 'animal__hall__is_active', 'animal__hall', 'animal', 'user')
    list_display = ('animal', 'user', 'created_at', 'approved', 'approved_at', 'reward_granted')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall')
    date_hierarchy = 'approved_at'
    readonly_fields = ('created_at', 'approved_at', 'reward_granted')


# --- PendingAppointment Admin (保持不變) ---
# ... (與之前相同，保持不變) ...
@admin.register(PendingAppointment)
class PendingAppointmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'added_at')
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal')
    search_fields = ('user__username', 'animal__name', 'animal__hall__name')
    list_select_related = ('user', 'animal', 'animal__hall')


# --- Note Admin (保持不變) ---
# ... (與之前相同，保持不變) ...
@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'updated_at')
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_select_related = ('user', 'animal', 'animal__hall')
    readonly_fields = ('created_at', 'updated_at')


# --- Announcement Admin (保持不變) ---
# ... (與之前相同，保持不變) ...
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


# --- StoryReview Admin (保持不變) ---
# ... (與之前相同，保持不變) ...
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
        return obj.is_active


# --- WeeklySchedule Admin (保持不變) ---
# ... (與之前相同，保持不變) ...
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


# --- UserTitleRule Admin (保持不變) ---
# ... (與之前相同，保持不變) ...
@admin.register(UserTitleRule)
class UserTitleRuleAdmin(admin.ModelAdmin):
    list_display = ('title_name', 'min_review_count', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title_name',)
    list_editable = ('min_review_count', 'is_active',)
    fieldsets = (
        (None, {'fields': ('title_name', 'min_review_count', 'is_active')}),
    )


# --- ReviewFeedback Admin (保持不變) ---
# ... (與之前相同，保持不變) ...
@admin.register(ReviewFeedback)
class ReviewFeedbackAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_target_review_display', 'feedback_type', 'created_at')
    list_filter = ('feedback_type', 'created_at')
    search_fields = ('user__username', 'review__id', 'story_review__id')
    list_select_related = ('user', 'review', 'story_review', 'review__animal', 'story_review__animal')
    readonly_fields = ('user', 'review', 'story_review', 'feedback_type', 'created_at')

    @admin.display(description='目標心得', ordering='review__id')
    def get_target_review_display(self, obj):
        if obj.review:
            user_name = obj.review.user.username if obj.review.user else "未知用戶"
            return f"一般心得 #{obj.review.id} (作者: {user_name})"
        elif obj.story_review:
            user_name = obj.story_review.user.username if obj.story_review.user else "未知用戶"
            return f"限時動態 #{obj.story_review.id} (作者: {user_name})"
        return "N/A"


# --- 註冊 SiteConfiguration Admin (保持不變) ---
if DJANGO_SOLO_INSTALLED:
    admin.site.register(SiteConfiguration, SingletonModelAdmin)
else:
    @admin.register(SiteConfiguration)
    class SiteConfigurationAdmin(admin.ModelAdmin):
         pass
# --- 註冊結束 (保持不變) ---