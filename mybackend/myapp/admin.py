# admin.py
from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
# --- Import WeeklySchedule ---
from .models import Animal, Hall, Review, PendingAppointment, Note, Announcement, StoryReview, WeeklySchedule
from django.utils.html import format_html # Import format_html for image preview

@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    list_editable = ('order',) # Allow editing order in list view
    # --- START: Add search_fields required by autocomplete ---
    search_fields = ('name',) # Define fields to search for autocomplete
    # --- END: Add search_fields ---

@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    # --- 修改 list_display ---
    list_display = ('name', 'hall', 'size_display', 'fee', 'is_active', 'is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer', 'order') # 加入 is_recommended
    # --- 修改 list_filter ---
    list_filter = ('hall', 'is_active', 'is_recommended', 'is_hidden_edition', 'is_exclusive', 'is_hot', 'is_newcomer') # 加入 is_recommended
    search_fields = ('name', 'introduction')
    list_editable = ('is_active', 'order') # Allow editing status and order
    # --- 修改 fieldsets ---
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
    # Consider adding autocomplete_fields if Hall list gets long
    autocomplete_fields = ['hall'] # Make hall selection easier


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('animal', 'user', 'created_at', 'approved')
    list_filter = ('approved', 'animal', 'user') # Put approved first
    search_fields = ('content', 'user__username', 'animal__name')
    list_editable = ('approved',)
    list_select_related = ('animal', 'user') # Optimize queries
    date_hierarchy = 'created_at' # Add date navigation
    # Add readonly fields for non-editable info
    readonly_fields = ('created_at',)


@admin.register(PendingAppointment)
class PendingAppointmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'added_at')
    list_filter = ('user', 'animal')
    search_fields = ('user__username', 'animal__name')
    list_select_related = ('user', 'animal')


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'updated_at') # Show updated_at
    list_filter = ('user', 'animal')
    search_fields = ('content', 'user__username', 'animal__name')
    list_select_related = ('user', 'animal')
    readonly_fields = ('created_at', 'updated_at')


# --- Register New Announcement Admin ---
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

# --- START: Register StoryReview Admin ---
@admin.register(StoryReview)
class StoryReviewAdmin(admin.ModelAdmin):
    list_display = ('animal', 'user', 'created_at', 'approved', 'approved_at', 'expires_at', 'is_story_active_display')
    list_filter = ('approved', 'animal__hall', 'animal', 'user')
    search_fields = ('content', 'user__username', 'animal__name')
    list_editable = ('approved',)
    list_select_related = ('animal', 'user', 'animal__hall')
    date_hierarchy = 'created_at'
    # Make fields managed by signal read-only in admin detail view
    readonly_fields = ('created_at', 'approved_at', 'expires_at')

    # Define fields shown in the detail/edit view
    fieldsets = (
        (None, {'fields': ('animal', 'user', 'approved')}),
        ('內容 (同心得)', {'fields': ('age', 'looks', 'face', 'temperament', 'physique', 'cup', 'cup_size', 'skin_texture', 'skin_color', 'music', 'music_price', 'sports', 'sports_price', 'scale', 'content')}),
        ('時間戳', {'fields': ('created_at', 'approved_at', 'expires_at')}),
    )

    @admin.display(boolean=True, description='目前有效')
    def is_story_active_display(self, obj):
        return obj.is_active

    # Note: The pre_save signal in models.py now handles setting
    # approved_at and expires_at automatically when 'approved' is changed.
    # The save_model override is generally not needed for this specific logic anymore
    # unless you have more complex admin-specific actions during save.

# --- END: Register StoryReview Admin ---


# --- START: Register WeeklySchedule Admin ---
@admin.register(WeeklySchedule)
class WeeklyScheduleAdmin(admin.ModelAdmin):
    list_display = ('hall', 'schedule_image_preview', 'updated_at')
    list_filter = ('hall',)
    search_fields = ('hall__name',) # Search by hall name
    readonly_fields = ('updated_at',)
    list_select_related = ('hall',) # Optimize query for hall name
    autocomplete_fields = ['hall'] # Easier hall selection

    fields = ('hall', 'schedule_image', 'updated_at') # Define field order in detail view

    @admin.display(description='班表預覽')
    def schedule_image_preview(self, obj):
        if obj.schedule_image:
            # Display a small thumbnail in the admin list view
            return format_html('<img src="{}" style="max-height: 100px; max-width: 100px;" />', obj.schedule_image.url)
        return "無圖片"
# --- END: Register WeeklySchedule Admin ---