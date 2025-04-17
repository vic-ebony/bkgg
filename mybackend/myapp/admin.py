# D:\bkgg\mybackend\myapp\admin.py
from django.contrib import admin
from django.utils.html import format_html # 用於圖片預覽
# --- 從 .models 導入所有需要註冊的 model ---
from .models import Hall, Animal, Review, PendingAppointment, Note, Announcement, StoryReview, WeeklySchedule
# --- (如果 DailyScheduleAdmin 移到這裡，也要導入) ---
# from schedule_parser.models import DailySchedule

@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'is_active', 'is_visible')
    list_filter = ('is_active', 'is_visible')
    list_editable = ('order', 'is_active', 'is_visible')
    search_fields = ('name',)
    fields = ('name', 'order', 'is_active', 'is_visible')

@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ('name', 'hall_display', 'fee', 'is_active', 'aliases_display', 'order') # 加入 aliases_display
    list_filter = ('hall__is_active', 'hall', 'is_active', 'is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer')
    search_fields = ('name', 'introduction', 'hall__name', 'aliases') # 加入別名搜索
    list_editable = ('is_active', 'order')
    fieldsets = (
        (None, {
            'fields': ('name', 'hall', 'is_active', 'order', 'photo')
        }),
        ('基本資料', {
            'fields': ('height', 'weight', 'cup_size', 'fee'),
            'classes': ('collapse',)
        }),
        ('標籤', {
            'fields': ('is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer'),
        }),
        ('介紹與別名', { # aliases 在這裡編輯
            'fields': ('introduction', 'aliases'),
        }),
        ('舊時段(參考)', { # 標示 time_slot 為舊的
            'fields': ('time_slot',),
            'classes': ('collapse',)
        }),
         ('時間戳', { # 顯示自動時間
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    autocomplete_fields = ['hall']
    list_select_related = ('hall',)
    readonly_fields = ('created_at', 'updated_at') # 時間戳設為唯讀

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
        # 處理 JSONField 列表或其他格式
        if isinstance(obj.aliases, list):
            # 只顯示前幾個，避免列表過長
            display_aliases = [str(a) for a in obj.aliases[:3]] # 最多顯示3個
            suffix = '...' if len(obj.aliases) > 3 else ''
            return ", ".join(display_aliases) + suffix
        elif isinstance(obj.aliases, str): # 兼容舊的 CharField 存儲
             return obj.aliases[:30] + ('...' if len(obj.aliases) > 30 else '') # 截斷過長字串
        return obj.aliases # 其他情況直接顯示


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    # ... (保持不變或按需調整)
    list_filter = ('approved', 'animal__hall__is_active', 'animal__hall', 'animal', 'user')
    list_display = ('animal', 'user', 'created_at', 'approved')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

@admin.register(PendingAppointment)
class PendingAppointmentAdmin(admin.ModelAdmin):
    # ... (保持不變或按需調整)
    list_display = ('user', 'animal', 'added_at')
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal')
    search_fields = ('user__username', 'animal__name', 'animal__hall__name')
    list_select_related = ('user', 'animal', 'animal__hall')


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    # ... (保持不變或按需調整)
    list_display = ('user', 'animal', 'updated_at')
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_select_related = ('user', 'animal', 'animal__hall')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    # ... (保持不變或按需調整)
    list_display = ('title', 'content_summary', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'content')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    fields = ('title', 'content', 'is_active', 'created_at', 'updated_at')

    def content_summary(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_summary.short_description = '內容摘要'

@admin.register(StoryReview)
class StoryReviewAdmin(admin.ModelAdmin):
    # ... (保持不變或按需調整)
    list_display = ('animal', 'user', 'created_at', 'approved', 'approved_at', 'expires_at', 'is_story_active_display')
    list_filter = ('approved', 'animal__hall__is_active', 'animal__hall', 'animal', 'user')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'approved_at', 'expires_at') # 審核時間和過期時間應由信號控制
    fieldsets = (
        (None, {'fields': ('animal', 'user', 'approved')}),
        ('內容 (同心得)', {'fields': ('age', 'looks', 'face', 'temperament', 'physique', 'cup', 'cup_size', 'skin_texture', 'skin_color', 'music', 'music_price', 'sports', 'sports_price', 'scale', 'content')}),
        ('時間戳', {'fields': ('created_at', 'approved_at', 'expires_at'), 'classes': ('collapse',)}),
    )

    @admin.display(boolean=True, description='目前有效')
    def is_story_active_display(self, obj):
        return obj.is_active

@admin.register(WeeklySchedule)
class WeeklyScheduleAdmin(admin.ModelAdmin):
    # ... (保持不變或按需調整)
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