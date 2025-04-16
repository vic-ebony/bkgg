# admin.py
# (原有 import 保持不變)
from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
# --- Import WeeklySchedule ---
from .models import Animal, Hall, Review, PendingAppointment, Note, Announcement, StoryReview, WeeklySchedule
from django.utils.html import format_html # Import format_html for image preview

@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    # --- START: 修改 HallAdmin ---
    # 加入 is_visible 欄位
    list_display = ('name', 'order', 'is_active', 'is_visible') # 加入 is_visible
    list_filter = ('is_active', 'is_visible') # 加入 is_visible 過濾器
    list_editable = ('order', 'is_active', 'is_visible') # 允許在列表頁編輯 is_visible
    search_fields = ('name',)
    # 定義在詳細編輯頁面顯示的欄位順序 (可選，如果希望控制順序)
    fields = ('name', 'order', 'is_active', 'is_visible') # 加入 is_visible
    # --- END: 修改 HallAdmin ---

# --- AnimalAdmin 保持不變，因為隱藏館別不影響動物的後台顯示或過濾邏輯 ---
@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    # 在 Animal 列表中顯示館別名稱，確保可以清楚看到美容師所屬的館別
    list_display = ('name', 'hall_display', 'size_display', 'fee', 'is_active', 'is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer', 'order') # 將 'hall' 改為 'hall_display'
    # 在 Animal 過濾器中加入館別本身是否啟用 (hall__is_active) - is_visible 不影響這裡
    list_filter = ('hall__is_active', 'hall', 'is_active', 'is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer') # 保持 hall__is_active
    search_fields = ('name', 'introduction', 'hall__name') # 加入館別名稱搜尋
    list_editable = ('is_active', 'order') # Allow editing status and order
    fieldsets = (
        (None, {
            'fields': ('name', 'hall', 'is_active', 'order', 'photo')
        }),
        ('基本資料', {
            'fields': ('height', 'weight', 'cup_size', 'fee', 'time_slot'),
            'classes': ('collapse',) # Collapsible section
        }),
        ('標籤', {
            # 在 '標籤' 這個區塊加入 is_recommended
            'fields': ('is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer'),
        }),
        ('介紹', {
            'fields': ('introduction',),
        }),
    )
    autocomplete_fields = ['hall'] # Make hall selection easier
    list_select_related = ('hall',) # 優化查詢

    # 為了在列表顯示館別名稱，並可能標示出館別狀態 (包含 is_visible 狀態)
    @admin.display(description='館別', ordering='hall__name')
    def hall_display(self, obj):
        if obj.hall:
            status_parts = []
            if not obj.hall.is_active:
                status_parts.append("已停用")
            # 如果館別是啟用但不可見, 加上標示
            if obj.hall.is_active and not obj.hall.is_visible:
                 status_parts.append("前端隱藏")

            status_indicator = f" ({', '.join(status_parts)})" if status_parts else ""
            return f"{obj.hall.name}{status_indicator}"
        return "未分館"


# --- ReviewAdmin 保持不變 ---
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    # 在過濾器中加入館別狀態，以便篩選出屬於已停用館別的評論 (is_visible 不影響)
    list_filter = ('approved', 'animal__hall__is_active', 'animal__hall', 'animal', 'user') # 保持 animal__hall__is_active
    list_display = ('animal', 'user', 'created_at', 'approved')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name') # 加入館別名稱搜尋
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall') # Optimize queries
    date_hierarchy = 'created_at' # Add date navigation
    readonly_fields = ('created_at',)


# --- PendingAppointmentAdmin 保持不變 ---
@admin.register(PendingAppointment)
class PendingAppointmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'added_at')
    # 在過濾器中加入館別狀態 (is_visible 不影響)
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal') # 保持 animal__hall__is_active
    search_fields = ('user__username', 'animal__name', 'animal__hall__name') # 加入館別名稱搜尋
    list_select_related = ('user', 'animal', 'animal__hall')


# --- NoteAdmin 保持不變 ---
@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'updated_at') # Show updated_at
    # 在過濾器中加入館別狀態 (is_visible 不影響)
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal') # 保持 animal__hall__is_active
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name') # 加入館別名稱搜尋
    list_select_related = ('user', 'animal', 'animal__hall')
    readonly_fields = ('created_at', 'updated_at')


# --- AnnouncementAdmin 保持不變 ---
@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'content_summary', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'content')
    list_editable = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
    fields = ('title', 'content', 'is_active', 'created_at', 'updated_at')

    def content_summary(self, obj):
        # Show a summary of the content in the list view
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_summary.short_description = '內容摘要'

# --- StoryReviewAdmin 保持不變 ---
@admin.register(StoryReview)
class StoryReviewAdmin(admin.ModelAdmin):
    list_display = ('animal', 'user', 'created_at', 'approved', 'approved_at', 'expires_at', 'is_story_active_display')
    # 在過濾器中加入館別狀態 (is_visible 不影響)
    list_filter = ('approved', 'animal__hall__is_active', 'animal__hall', 'animal', 'user') # 保持 animal__hall__is_active
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name') # 加入館別名稱搜尋
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'approved_at', 'expires_at')
    fieldsets = (
        (None, {'fields': ('animal', 'user', 'approved')}),
        ('內容 (同心得)', {'fields': ('age', 'looks', 'face', 'temperament', 'physique', 'cup', 'cup_size', 'skin_texture', 'skin_color', 'music', 'music_price', 'sports', 'sports_price', 'scale', 'content')}),
        ('時間戳', {'fields': ('created_at', 'approved_at', 'expires_at')}),
    )

    @admin.display(boolean=True, description='目前有效')
    def is_story_active_display(self, obj):
        return obj.is_active

# --- WeeklyScheduleAdmin 保持不變 ---
@admin.register(WeeklySchedule)
class WeeklyScheduleAdmin(admin.ModelAdmin):
    list_display = ('hall', 'order', 'schedule_image_preview', 'updated_at')
    # 在過濾器中加入館別狀態 (is_visible 不影響)
    list_filter = ('hall__is_active', 'hall',) # 保持 hall__is_active
    search_fields = ('hall__name',) # Search by hall name
    readonly_fields = ('updated_at',)
    list_select_related = ('hall',) # Optimize query for hall name
    autocomplete_fields = ['hall'] # Easier hall selection
    list_editable = ('order',)
    fields = ('hall', 'schedule_image', 'order', 'updated_at') # Define field order in detail view

    @admin.display(description='班表圖片預覽') # Changed description slightly
    def schedule_image_preview(self, obj):
        if obj.schedule_image:
            # Display a small thumbnail in the admin list view
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px;" />', obj.schedule_image.url)
        return "無圖片"