from django.contrib import admin
from .models import Animal, Hall, Review, PendingAppointment

@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
    list_display = ('name', 'time_slot', 'size_display', 'fee', 'hall', 'is_exclusive', 'is_hot', 'is_newcomer')
    search_fields = ('name', 'height', 'weight', 'cup_size', 'time_slot')
    fields = (
        'name', 
        'height', 
        'weight', 
        'cup_size', 
        'fee', 
        'time_slot', 
        'hall', 
        'is_exclusive', 
        'is_hot', 
        'is_newcomer', 
        'introduction',
        'photo'
    )

@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('animal', 'user', 'created_at', 'approved')
    list_filter = ('animal', 'user', 'approved')
    search_fields = ('content',)
    list_editable = ('approved',)

@admin.register(PendingAppointment)
class PendingAppointmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'animal', 'added_at')
    list_filter = ('user', 'animal')
