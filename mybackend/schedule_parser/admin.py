# D:\bkgg\mybackend\schedule_parser\admin.py
from django.contrib import admin
from .models import DailySchedule

@admin.register(DailySchedule)
class DailyScheduleAdmin(admin.ModelAdmin):
    list_display = ('hall', 'animal', 'time_slots', 'updated_at')
    list_filter = ('hall', 'updated_at') # 可以按館別和更新時間過濾
    search_fields = ('animal__name', 'hall__name', 'time_slots') # 方便搜索
    list_select_related = ('hall', 'animal') # 優化查詢性能
    readonly_fields = ('updated_at',)
    list_per_page = 50 # 每頁顯示更多條目
    date_hierarchy = 'updated_at' # 添加日期導航