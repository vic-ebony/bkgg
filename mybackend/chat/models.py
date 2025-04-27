# D:\bkgg\mybackend\chat\models.py (新檔案)

from django.db import models
from django.conf import settings # 用於引用設定中的 AUTH_USER_MODEL
from django.utils import timezone

class ChatMessage(models.Model):
    # 關聯到發送訊息的用戶
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # 當用戶被刪除時，訊息中的 user 欄位設為 NULL
                                   # 也可以用 models.CASCADE，這樣用戶刪除時訊息也會被刪除
        null=True,                 # 允許 user 欄位為 NULL (配合 SET_NULL)
        blank=True,                # Admin 中允許為空 (雖然程式碼不應創建 user 為空的訊息)
        related_name='chat_messages', # 反向查詢名稱
        verbose_name="發送者"
    )
    # 儲存訊息內容
    message = models.TextField("訊息內容")
    # 自動記錄訊息創建時間，並建立索引以優化查詢
    timestamp = models.DateTimeField("時間戳", auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['timestamp'] # 預設按時間戳升序排列 (舊的在前)
        verbose_name = "聊天訊息"
        verbose_name_plural = "聊天訊息記錄" # Admin 後台顯示的名稱

    def __str__(self):
        # 格式化時間為本地時間
        local_time = timezone.localtime(self.timestamp)
        time_str = local_time.strftime("%Y-%m-%d %H:%M")
        # 處理用戶可能已被刪除的情況
        username = self.user.username if self.user else "已刪除用戶"
        # 返回一個簡短的描述
        return f'{username} ({time_str}): {self.message[:30]}...'