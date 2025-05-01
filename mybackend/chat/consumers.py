# D:\bkgg\mybackend\chat\consumers.py (修改後 - 處理和發送引用資訊)

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async # <--- 必須導入
from django.utils import timezone
from django.conf import settings
import logging

# --- 導入我們的聊天模型 ---
from .models import ChatMessage # <--- 導入模型

logger = logging.getLogger(__name__)

# --- 定義要加載的歷史訊息數量 ---
HISTORY_MESSAGE_COUNT = 20 # 可以根據需要調整

class ChatConsumer(AsyncWebsocketConsumer):
    """
    處理全域聊天室的 WebSocket 連接，包含訊息儲存、歷史記錄加載和引用回覆。
    """
    async def connect(self):
        logger.info(">>> ChatConsumer connect method started.")
        self.user = self.scope["user"]
        logger.info(f">>> User attempting connect: {self.user}")

        if not self.user.is_authenticated:
            logger.warning(">>> Unauthenticated user detected. Closing connection.")
            await self.close()
            return

        self.room_group_name = 'global_chat'
        self.username = self.user.first_name or self.user.username
        logger.info(f">>> User '{self.username}' authenticated. Joining group '{self.room_group_name}'.")

        # 加入群組
        try:
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            logger.info(f">>> Successfully added channel {self.channel_name} to group {self.room_group_name}.")
        except Exception as e:
             logger.error(f">>> ERROR adding channel to group: {e}", exc_info=True)
             await self.close()
             return

        # 接受連接
        try:
             await self.accept()
             logger.info(f">>> WebSocket connection ACCEPTED for user '{self.username}'.")
        except Exception as e:
             logger.error(f">>> ERROR accepting WebSocket connection: {e}", exc_info=True)
             # 嘗試從群組中移除
             await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
             return

        # --- 連接成功後，加載並發送歷史訊息 ---
        logger.info(f">>> Fetching recent chat history for user '{self.username}'...")
        try:
            # (可選) 發送一個系統訊息提示正在加載歷史
            await self.send(text_data=json.dumps({
                'type': 'system',
                'message': '--- 載入最近訊息 ---',
                'timestamp': timezone.now().isoformat(),
                # 'message_id': None # 系統訊息通常沒有 ID
            }))

            recent_messages = await self.fetch_recent_messages()
            # 按照時間順序 (舊到新) 發送歷史訊息
            for msg_data in recent_messages:
                 await self.send(text_data=json.dumps(msg_data))

            logger.info(f">>> Sent {len(recent_messages)} history messages to user '{self.username}'.")

            # (可選) 發送一個系統訊息提示歷史加載完畢
            await self.send(text_data=json.dumps({
                'type': 'system',
                'message': '--- 訊息結束 ---',
                'timestamp': timezone.now().isoformat(),
                # 'message_id': None
            }))

        except Exception as e:
            logger.error(f">>> ERROR fetching/sending chat history for user '{self.username}': {e}", exc_info=True)
        # --- 歷史訊息處理結束 ---


        # 向群組廣播用戶加入訊息 (放在發送歷史之後，這樣其他人才會看到加入訊息)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_system_message',
                'message': f"{self.username} 加入了聊天室。"
                # 'message_id': None # 系統訊息
            }
        )

    async def disconnect(self, close_code):
        # ... (disconnect 方法保持不變) ...
        if hasattr(self, 'user') and self.user.is_authenticated:
            logger.info(f"User '{self.username}' (ID: {self.user.id}) disconnected from chat group '{self.room_group_name}'. Code: {close_code}")
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_system_message',
                    'message': f"{self.username} 離開了聊天室。"
                    # 'message_id': None # 系統訊息
                }
            )
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        if not self.user.is_authenticated:
            logger.warning("Received message from unauthenticated connection. Ignoring.")
            return

        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get('message', '').strip()
            reply_to_id = text_data_json.get('reply_to_id') # <--- 獲取回覆 ID

            if message:
                logger.debug(f"Received message from '{self.username}': '{message}' (Reply to: {reply_to_id})")

                # --- 將訊息儲存到資料庫 ---
                saved_message = await self.save_chat_message(self.user, message, reply_to_id) # <--- 傳遞 reply_to_id
                if not saved_message:
                    logger.error(f"Failed to save message from {self.username}. Aborting broadcast.")
                    # 可以選擇向發送者發送錯誤訊息
                    await self.send(text_data=json.dumps({
                        'type': 'system',
                        'message': '錯誤：訊息儲存失敗，無法發送。',
                        'timestamp': timezone.now().isoformat()
                    }))
                    return
                # --------------------------

                # 準備廣播數據
                broadcast_data = {
                    'type': 'chat_user_message',
                    'message_id': saved_message.id, # <--- 發送儲存後的訊息 ID
                    'message': message,
                    'username': self.username,
                    'user_id': self.user.id,
                    'timestamp': saved_message.timestamp.isoformat() # 使用儲存後的時間戳
                }

                # --- 如果是回覆，附加引用信息 ---
                if saved_message.reply_to_id:
                    quoted_details = await self.get_quoted_message_details(saved_message.reply_to_id)
                    if quoted_details:
                        broadcast_data['reply_to_id'] = saved_message.reply_to_id
                        broadcast_data['quoted_username'] = quoted_details['username']
                        broadcast_data['quoted_message_text'] = quoted_details['message']
                    else:
                         # 如果原始訊息找不到了，可以選擇不包含引用信息或發送特定標記
                         logger.warning(f"Could not find original message {saved_message.reply_to_id} to quote for message {saved_message.id}")
                         # broadcast_data['reply_to_id'] = saved_message.reply_to_id
                         # broadcast_data['quoted_username'] = "原始訊息"
                         # broadcast_data['quoted_message_text'] = "[已刪除]"
                # -----------------------------

                # 向群組廣播訊息
                await self.channel_layer.group_send(
                    self.room_group_name,
                    broadcast_data # <--- 發送包含 ID 和引用資訊的數據
                )
            else:
                logger.debug(f"Received empty message from '{self.username}'. Ignoring.")

        except json.JSONDecodeError:
            logger.warning(f"Received invalid JSON from WebSocket: {text_data}")
        except Exception as e:
            logger.error(f"Error processing received message from '{self.username}': {e}", exc_info=True)

    # --- 訊息處理方法 ---
    async def chat_system_message(self, event):
        message = event['message']
        timestamp = event.get('timestamp', timezone.now().isoformat())
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': message,
            'timestamp': timestamp,
            'message_id': event.get('message_id') # 通常為 None
        }))

    async def chat_user_message(self, event):
        """處理從 group_send 過來的用戶訊息事件"""
        await self.send(text_data=json.dumps({
            'type': 'user',
            'message_id': event['message_id'], # <--- 包含 message_id
            'message': event['message'],
            'username': event['username'],
            'user_id': event['user_id'],
            'timestamp': event['timestamp'],
            # --- 如果是回覆，包含引用信息 ---
            'reply_to_id': event.get('reply_to_id'),
            'quoted_username': event.get('quoted_username'),
            'quoted_message_text': event.get('quoted_message_text'),
            # -----------------------------
        }))

    # --- 修改：從資料庫讀取歷史訊息的方法，包含引用處理 ---
    @database_sync_to_async
    def fetch_recent_messages(self):
        """
        異步地從資料庫獲取最近的 N 條聊天訊息，包含引用資訊。
        """
        messages_data = []
        try:
            # 查詢最近的 N 條訊息，按時間倒序排列，並預先加載 user 和 reply_to.user
            # 使用 prefetch_related 來優化 ForeignKey 的反向查找 (如果需要顯示誰回覆了某條訊息)
            # 使用 select_related 來優化 ForeignKey 的正向查找 (user, reply_to)
            recent_messages_qs = ChatMessage.objects.select_related(
                'user', 'reply_to', 'reply_to__user' # 優化 reply_to 的 user 查找
            ).order_by('-timestamp')[:HISTORY_MESSAGE_COUNT]

            # 將查詢結果轉換為列表並反轉，得到按時間正序排列的訊息
            recent_messages_list = reversed(list(recent_messages_qs))

            for msg in recent_messages_list:
                # 格式化每條訊息
                username = msg.user.first_name or msg.user.username if msg.user else "未知用戶"
                msg_entry = {
                    'type': 'user', # 歷史訊息也標記為 user 類型
                    'message_id': msg.id, # <--- 添加 message_id
                    'message': msg.message,
                    'username': username,
                    'user_id': msg.user.id if msg.user else None,
                    'timestamp': msg.timestamp.isoformat()
                }

                # --- 處理引用的訊息 ---
                if msg.reply_to: # 檢查 reply_to 是否存在
                    replied_to_msg = msg.reply_to # 因為 select_related，這裡不會再觸發 DB 查詢
                    if replied_to_msg:
                        quoted_username = replied_to_msg.user.first_name or replied_to_msg.user.username if replied_to_msg.user else "未知用戶"
                        # 截斷訊息
                        quoted_snippet = (replied_to_msg.message[:30] + '...') if len(replied_to_msg.message) > 30 else replied_to_msg.message
                        msg_entry['reply_to_id'] = replied_to_msg.id
                        msg_entry['quoted_username'] = quoted_username
                        msg_entry['quoted_message_text'] = quoted_snippet
                    else:
                         # 理論上 select_related 後 reply_to 不會是 None，但以防萬一
                         logger.warning(f"History message {msg.id} has reply_to_id {msg.reply_to_id} but reply_to object is None.")
                # -----------------------

                messages_data.append(msg_entry)

            logger.debug(f"Fetched {len(messages_data)} recent messages from DB.")
        except Exception as e:
            logger.error(f"Error fetching recent messages: {e}", exc_info=True)
            # 出錯時返回空列表，避免影響連接
            messages_data = []
        return messages_data

    # --- 修改：儲存訊息到資料庫的方法，包含 reply_to ---
    @database_sync_to_async
    def save_chat_message(self, user, message, reply_to_id=None):
        """
        異步地將聊天訊息儲存到資料庫，包含處理 reply_to_id。
        返回儲存的 ChatMessage 物件，如果失敗則返回 None。
        """
        try:
            reply_to_instance = None
            if reply_to_id:
                try:
                    reply_to_instance = ChatMessage.objects.get(id=reply_to_id)
                except ChatMessage.DoesNotExist:
                    logger.warning(f"User {user.username} tried to reply to non-existent message ID {reply_to_id}. Storing message without reply.")
                    reply_to_id = None # 清除無效的 ID

            # 創建訊息，確保時間戳由 default=timezone.now 生成
            new_message = ChatMessage.objects.create(
                user=user,
                message=message,
                reply_to=reply_to_instance # 傳遞查詢到的實例或 None
            )
            logger.debug(f"Saved message from {user.username} to DB (ID: {new_message.id}, Reply to: {reply_to_id}).")
            return new_message # 返回創建的物件
        except Exception as e:
            logger.error(f"Failed to save chat message for {user.username}: {e}", exc_info=True)
            return None # 失敗時返回 None

    # --- 新增：從資料庫獲取引用訊息詳情的方法 (已移至 Model 中作為靜態方法) ---
    @database_sync_to_async
    def get_quoted_message_details(self, message_id):
        """
        異步地獲取引用訊息的詳情。
        使用模型的靜態方法。
        """
        return ChatMessage.get_quoted_message_details(message_id)

# --- Consumer 結束 ---