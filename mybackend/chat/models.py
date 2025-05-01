# D:\bkgg\mybackend\chat\models.py (修改後 - 新增 reply_to 欄位)

from django.db import models
from django.conf import settings # 用於引用設定中的 AUTH_USER_MODEL
from django.utils import timezone

class ChatMessage(models.Model):
    # 關聯到發送訊息的用戶
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, # 當用戶被刪除時，訊息中的 user 欄位設為 NULL
        null=True,                 # 允許 user 欄位為 NULL (配合 SET_NULL)
        blank=True,                # Admin 中允許為空
        related_name='chat_messages', # 反向查詢名稱
        verbose_name="發送者"
    )
    # 儲存訊息內容
    message = models.TextField("訊息內容")
    # 自動記錄訊息創建時間，並建立索引以優化查詢
    timestamp = models.DateTimeField("時間戳", default=timezone.now, db_index=True) # 使用 default=timezone.now

    # --- 新增：回覆的訊息 ---
    reply_to = models.ForeignKey(
        'self',                    # 指向 ChatMessage 模型本身
        on_delete=models.SET_NULL, # 如果原始訊息被刪除，回覆訊息的 reply_to 欄位設為 NULL
        null=True,                 # 允許為 NULL (表示不是回覆訊息)
        blank=True,                # Admin 中允許為空
        related_name='replies',    # 反向查詢名稱，可以透過 msg.replies 找到所有回覆它的訊息
        verbose_name="回覆的訊息"
    )
    # -----------------------

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
        reply_indicator = "[回覆] " if self.reply_to else ""
        return f'{reply_indicator}{username} ({time_str}): {self.message[:30]}...'

    # --- 新增：方法來獲取被引用的訊息摘要 (用於 Consumer) ---
    @staticmethod
    def get_quoted_message_details(message_id):
        """
        根據 message_id 獲取用於引用的訊息詳情。
        返回包含 username 和 message snippet 的字典，如果找不到則返回 None。
        """
        try:
            original_msg = ChatMessage.objects.select_related('user').get(id=message_id)
            username = original_msg.user.first_name or original_msg.user.username if original_msg.user else "未知用戶"
            # 截斷訊息，例如最多顯示 30 個字
            snippet = (original_msg.message[:30] + '...') if len(original_msg.message) > 30 else original_msg.message
            return {
                'username': username,
                'message': snippet
            }
        except ChatMessage.DoesNotExist:
            logger.warning(f"Attempted to quote non-existent message with ID: {message_id}")
            return None
        except Exception as e:
            logger.error(f"Error fetching quoted message details for ID {message_id}: {e}", exc_info=True)
            return None
    # -----------------------------------------------------