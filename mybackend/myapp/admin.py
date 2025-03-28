from django.contrib import admin
from .models import Animal, Hall, Review

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
        'introduction',  # 新增介紹欄位
        'photo'
    )

@admin.register(Hall)
class HallAdmin(admin.ModelAdmin):
    list_display = ('name',)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('animal', 'user', 'content', 'created_at', 'approved')
    list_filter = ('animal', 'user', 'approved')
    search_fields = ('content',)
    list_editable = ('approved',)  # 允許直接在列表中修改審核狀態
