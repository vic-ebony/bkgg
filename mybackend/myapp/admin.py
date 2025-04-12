# admin.py
from django.contrib import admin
from .models import Animal, Hall, Review, PendingAppointment, Note, Announcement # Import Announcement

@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    list_editable = ('order',) # Allow editing order in list view

@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    # --- 修改 list_display ---
    list_display = ('name', 'hall', 'size_display', 'fee', 'is_active', 'is_exclusive', 'is_hot', 'is_newcomer', 'is_hidden_edition', 'order') # 加入 is_hidden_edition
    # --- 修改 list_filter ---
    list_filter = ('hall', 'is_active', 'is_exclusive', 'is_hot', 'is_newcomer', 'is_hidden_edition') # 加入 is_hidden_edition
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
            # 在 '標籤' 這個區塊加入 is_hidden_edition
            'fields': ('is_exclusive', 'is_hot', 'is_newcomer', 'is_hidden_edition'),
        }),
        ('介紹', {
            'fields': ('introduction',),
        }),
    )
    # Consider adding autocomplete_fields if Hall list gets long
    # autocomplete_fields = ['hall']


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