# D:\bkgg\mybackend\myapp\admin.py
from django.contrib import admin, messages
from django.utils.html import format_html
# --- *** 導入 path *** ---
from django.urls import reverse, path
# --- *** ---
from django.http import HttpResponseRedirect
# --- 從 .models 導入所有需要註冊的 model ---
from .models import Hall, Animal, Review, PendingAppointment, Note, Announcement, StoryReview, WeeklySchedule
# --- *** 從 .views 導入合併視圖 *** ---
from .views import merge_transfer_animal_view
# --- *** ---

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

@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ('name', 'hall_display', 'fee', 'is_active', 'aliases_display', 'order')
    list_filter = ('hall__is_active', 'hall', 'is_active', 'is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer')
    search_fields = ('name', 'introduction', 'hall__name', 'aliases')
    list_editable = ('is_active', 'order')
    fieldsets = (
        (None, {'fields': ('name', 'hall', 'is_active', 'order', 'photo')}),
        ('基本資料', {'fields': ('height', 'weight', 'cup_size', 'fee'), 'classes': ('collapse',)}),
        ('標籤', {'fields': ('is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer')}),
        ('介紹與別名', {'fields': ('introduction', 'aliases')}),
        ('舊時段(參考)', {'fields': ('time_slot',), 'classes': ('collapse',)}),
        ('時間戳', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
    autocomplete_fields = ['hall']
    list_select_related = ('hall',)
    readonly_fields = ('created_at', 'updated_at')
    actions = ['merge_transfer_animal'] # 註冊合併/轉移操作

    # --- *** 添加 get_urls 方法以註冊自定義 Admin URL *** ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:animal_id>/merge-transfer/', # 路徑相對於 /admin/myapp/animal/
                self.admin_site.admin_view(merge_transfer_animal_view), # 使用 admin_view 包裹視圖
                name='myapp_animal_merge_transfer' # URL 名稱，用於 reverse
            )
        ]
        return custom_urls + urls
    # --- *** ---

    @admin.display(description='館別', ordering='hall__name')
    def hall_display(self, obj):
        # ... (保持不變) ...
        if obj.hall:
            status_parts = []
            if not obj.hall.is_active: status_parts.append("已停用")
            if obj.hall.is_active and not obj.hall.is_visible: status_parts.append("前端隱藏")
            status_indicator = f" ({', '.join(status_parts)})" if status_parts else ""
            return f"{obj.hall.name}{status_indicator}"
        return "未分館"

    @admin.display(description='別名/曾用名')
    def aliases_display(self, obj):
        # ... (保持不變) ...
         if isinstance(obj.aliases, list):
            display_aliases = [str(a) for a in obj.aliases[:3]]
            suffix = '...' if len(obj.aliases) > 3 else ''
            return ", ".join(display_aliases) + suffix
         elif isinstance(obj.aliases, str):
             return obj.aliases[:30] + ('...' if len(obj.aliases) > 30 else '')
         return obj.aliases

    # --- 合併/轉移操作 ---
    @admin.action(description='合併/轉移選定的美容師資料')
    def merge_transfer_animal(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "請只選擇一位美容師進行合併/轉移操作。", messages.WARNING)
            return HttpResponseRedirect(request.get_full_path())

        selected_animal = queryset.first()
        animal_id = selected_animal.id

        try:
            # --- *** 使用 Admin 命名空間反向解析在 get_urls 中定義的 URL *** ---
            intermediate_url = reverse('admin:myapp_animal_merge_transfer', args=[animal_id])
            # --- *** ---
            return HttpResponseRedirect(intermediate_url)
        except Exception as e:
            self.message_user(request, f"無法導向合併頁面，請檢查URL配置或視圖導入: {e}", messages.ERROR)
            return HttpResponseRedirect(request.get_full_path())

# --- 其他 Admin 註冊 (保持不變) ---
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_filter = ('approved', 'animal__hall__is_active', 'animal__hall', 'animal', 'user')
    list_display = ('animal', 'user', 'created_at', 'approved')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

@admin.register(PendingAppointment)
class PendingAppointmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'added_at')
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal')
    search_fields = ('user__username', 'animal__name', 'animal__hall__name')
    list_select_related = ('user', 'animal', 'animal__hall')

@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'updated_at')
    list_filter = ('user', 'animal__hall__is_active', 'animal__hall', 'animal')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_select_related = ('user', 'animal', 'animal__hall')
    readonly_fields = ('created_at', 'updated_at')

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

@admin.register(StoryReview)
class StoryReviewAdmin(admin.ModelAdmin):
    list_display = ('animal', 'user', 'created_at', 'approved', 'approved_at', 'expires_at', 'is_story_active_display')
    list_filter = ('approved', 'animal__hall__is_active', 'animal__hall', 'animal', 'user')
    search_fields = ('content', 'user__username', 'animal__name', 'animal__hall__name')
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'approved_at', 'expires_at')
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

# --- 如果 DailyScheduleAdmin 在這裡定義，也保持不變 ---
# ...