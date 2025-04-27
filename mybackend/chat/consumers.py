# D:\bkgg\mybackend\chat\consumers.py (完整版 - 包含儲存和加載歷史記錄)

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
    處理全域聊天室的 WebSocket 連接，包含訊息儲存和歷史記錄加載。
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
                'timestamp': timezone.now().isoformat()
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
                'timestamp': timezone.now().isoformat()
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

            if message:
                logger.debug(f"Received message from '{self.username}': '{message}'")

                # --- 將訊息儲存到資料庫 ---
                # 這次我們【需要】儲存，所以取消註解並確保方法存在
                await self.save_chat_message(self.user, message)
                # --------------------------

                # 向群組廣播訊息
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_user_message',
                        'message': message,
                        'username': self.username,
                        'user_id': self.user.id,
                        'timestamp': timezone.now().isoformat()
                    }
                )
            else:
                logger.debug(f"Received empty message from '{self.username}'. Ignoring.")

        except json.JSONDecodeError:
            logger.warning(f"Received invalid JSON from WebSocket: {text_data}")
        except Exception as e:
            logger.error(f"Error processing received message from '{self.username}': {e}", exc_info=True)

    # --- 訊息處理方法 (保持不變) ---
    async def chat_system_message(self, event):
        message = event['message']
        timestamp = event.get('timestamp', timezone.now().isoformat())
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': message,
            'timestamp': timestamp
        }))

    async def chat_user_message(self, event):
        message = event['message']
        username = event['username']
        user_id = event['user_id']
        timestamp = event.get('timestamp', timezone.now().isoformat())
        await self.send(text_data=json.dumps({
            'type': 'user',
            'message': message,
            'username': username,
            'user_id': user_id,
            'timestamp': timestamp
        }))

    # --- 新增：從資料庫讀取歷史訊息的方法 ---
    @database_sync_to_async
    def fetch_recent_messages(self):
        """
        異步地從資料庫獲取最近的 N 條聊天訊息。
        """
        messages_data = []
        try:
            # 查詢最近的 N 條訊息，按時間倒序排列，並預先加載關聯的 user 對象
            recent_messages_qs = ChatMessage.objects.select_related('user').order_by('-timestamp')[:HISTORY_MESSAGE_COUNT]

            # 將查詢結果轉換為列表並反轉，得到按時間正序排列的訊息
            recent_messages_list = reversed(list(recent_messages_qs))

            for msg in recent_messages_list:
                # 格式化每條訊息，使其與 live message 格式一致
                username = msg.user.first_name or msg.user.username if msg.user else "未知用戶"
                messages_data.append({
                    'type': 'user', # 歷史訊息也標記為 user 類型
                    'message': msg.message,
                    'username': username,
                    'user_id': msg.user.id if msg.user else None, # 如果用戶已刪除，ID 為 None
                    'timestamp': msg.timestamp.isoformat()
                })
            logger.debug(f"Fetched {len(messages_data)} recent messages from DB.")
        except Exception as e:
            logger.error(f"Error fetching recent messages: {e}", exc_info=True)
            # 出錯時返回空列表，避免影響連接
            messages_data = []
        return messages_data

    # --- 修改：儲存訊息到資料庫的方法 (確保它存在) ---
    @database_sync_to_async
    def save_chat_message(self, user, message):
        """
        異步地將聊天訊息儲存到資料庫。
        """
        try:
            ChatMessage.objects.create(user=user, message=message)
            logger.debug(f"Saved message from {user.username} to DB.")
        except Exception as e:
            logger.error(f"Failed to save chat message for {user.username}: {e}", exc_info=True)

# --- Consumer 結束 ---