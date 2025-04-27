# D:\bkgg\mybackend\chat\admin.py (新檔案)

from django.contrib import admin
from .models import ChatMessage # 導入模型

@admin.register(ChatMessage) # 註冊模型到 Admin
class ChatMessageAdmin(admin.ModelAdmin):
    # 在列表頁顯示的欄位
    list_display = ('user', 'message_summary', 'timestamp')
    # 可以用來篩選的欄位
    list_filter = ('timestamp', 'user')
    # 可以搜尋的欄位
    search_fields = ('message', 'user__username')
    # 設定為唯讀的欄位 (不允許在 Admin 中修改)
    readonly_fields = ('user', 'message', 'timestamp')
    # 每頁顯示的記錄數量
    list_per_page = 50

    # 自訂一個顯示訊息摘要的方法
    @admin.display(description='訊息摘要')
    def message_summary(self, obj):
        # 只顯示訊息的前 50 個字符
        return obj.message[:50] + ('...' if len(obj.message) > 50 else '')

    # 禁止在 Admin 後台新增聊天記錄
    def has_add_permission(self, request):
        return False

    # 禁止在 Admin 後台修改聊天記錄
    def has_change_permission(self, request, obj=None):
        return False
        # 如果需要允許修改，可以返回 True，但不建議

    # 允許刪除 (如果需要禁止刪除，可以覆寫 has_delete_permission)
    # def has_delete_permission(self, request, obj=None):
    #     return False # 返回 False 來禁止刪除