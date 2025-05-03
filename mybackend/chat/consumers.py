# D:\bkgg\mybackend\chat\consumers.py (V_Final_Corrected - 使用 'message' 欄位)

import json
import logging
from datetime import timedelta
from collections import defaultdict

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.utils import timezone
from asgiref.sync import sync_to_async
from django.db.models import Count, Q # 確保 Q 被導入

# --- 模型和工具函數導入 (修改為你的實際路徑) ---
try:
    # 假設模型和工具函數都在 'myapp' app 中
    from myapp.models import Review, StoryReview, UserTitleRule
    from myapp.utils import get_user_title_from_count
    # 導入 ChatMessage 模型
    from chat.models import ChatMessage # 使用你提供的正確路徑
    MODELS_IMPORTED = True
    logger = logging.getLogger(__name__)
    logger.info("Successfully imported models and utils for chat consumer.")
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"FATAL: Error importing models/utils in chat/consumers.py: {e}. Chat functionality might be limited.", exc_info=True)
    MODELS_IMPORTED = False
    def get_user_title_from_count(count): return None
    ChatMessage = None # Define as None if import fails
# --- ------------------------------------ ---

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get('user')
        if not self.user or not self.user.is_authenticated:
            logger.warning("Unauthenticated user connection attempt denied.")
            await self.close()
            return

        self.room_group_name = 'public_chat' # Or your group logic
        logger.info(f"User {self.user.username} connecting to group '{self.room_group_name}'.")

        try:
            await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        except Exception as e:
             logger.error(f"Error adding user {self.user.username} to group '{self.room_group_name}': {e}", exc_info=True)
             await self.close()
             return

        await self.accept()
        logger.info(f"User {self.user.username} connected successfully.")
        await self.send_recent_messages() # Send history upon connection

    async def disconnect(self, close_code):
        logger.info(f"User {self.user.username if hasattr(self, 'user') and self.user else 'Unknown'} disconnecting (Code: {close_code}).")
        if hasattr(self, 'room_group_name') and self.room_group_name:
            try:
                await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            except Exception as e:
                logger.error(f"Error removing user from group '{self.room_group_name}': {e}", exc_info=True)

    # --- 異步獲取用戶稱號 ---
    @sync_to_async
    def _get_user_title(self, user):
        if not MODELS_IMPORTED or not user or not user.is_authenticated: return None
        try:
            review_count = Review.objects.filter(user=user, approved=True).count()
            story_review_count = StoryReview.objects.filter(user=user, approved=True).count()
            total_count = review_count + story_review_count
            return get_user_title_from_count(total_count)
        except Exception as e:
            logger.error(f"Error calculating title for user {user.username}: {e}", exc_info=True)
            return None
    # --- ------------------- ---

    # --- 異步獲取引用信息 (使用 'message' 欄位) ---
    @sync_to_async
    def _get_quoted_message_info(self, message_id):
        """獲取被引用訊息的用戶名和文本片段"""
        if not ChatMessage: return None
        try:
            message = ChatMessage.objects.select_related('user').get(pk=message_id)
            username = message.user.first_name or message.user.username if message.user else '未知用戶'
            # *** 使用正確的 'message' 欄位 ***
            raw_text = message.message or '' # <--- 使用 'message'
            # *** ------------------------ ***
            text_snippet = ' '.join(raw_text.splitlines())
            text_snippet = (text_snippet[:30] + '...') if len(text_snippet) > 30 else text_snippet
            logger.debug(f"Quote info found: User='{username}', Snippet='{text_snippet}'")
            return {'username': username, 'text': text_snippet}
        except ChatMessage.DoesNotExist:
            logger.warning(f"Quoted message ID {message_id} not found.")
            return None
        except Exception as e:
            logger.error(f"Error fetching quoted message info for ID {message_id}: {e}", exc_info=True)
            return None
    # --- ------------------------------------ ---

    # --- 異步保存訊息到數據庫 (使用 'message' 欄位) ---
    @sync_to_async
    def _save_message_to_db(self, user, content, reply_to_id=None):
        """保存聊天訊息到數據庫"""
        if not ChatMessage: return None
        try:
            reply_to_instance = None
            if reply_to_id:
                try:
                    reply_to_instance = ChatMessage.objects.get(pk=reply_to_id)
                except ChatMessage.DoesNotExist:
                    logger.warning(f"Cannot save reply: Original message ID {reply_to_id} not found.")
                    reply_to_id = None # Option: Save without reply link

            # *** 使用正確的 'message' 欄位名 ***
            message = ChatMessage.objects.create(
                user=user,
                message=content, # <--- 使用 'message'
                reply_to=reply_to_instance
            )
            # *** ------------------------ ***
            logger.info(f"Saved message ID {message.id} for user {user.username}")
            return message
        except Exception as e:
            logger.error(f"Error saving message for user {user.username}: {e}", exc_info=True)
            return None
    # --- ------------------------------- ---

    async def receive(self, text_data):
        if not self.user or not self.user.is_authenticated: return
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            logger.debug(f"Received data from {self.user.username}: {text_data_json}")

            if message_type == 'request_recent_messages':
                 logger.info(f"User {self.user.username} requested recent messages.")
                 await self.send_recent_messages()
                 return

            # --- 處理普通聊天訊息 ---
            message_content = text_data_json.get('message', '').strip()
            reply_to_id = text_data_json.get('reply_to_id')

            if message_content:
                user_title = await self._get_user_title(self.user)

                quoted_username = None; quoted_message_text = None
                if reply_to_id:
                    quoted_info = await self._get_quoted_message_info(reply_to_id)
                    if quoted_info:
                        quoted_username = quoted_info.get('username')
                        quoted_message_text = quoted_info.get('text')

                # --- 保存新訊息到數據庫 ---
                new_message_instance = await self._save_message_to_db(self.user, message_content, reply_to_id)
                message_id_for_broadcast = new_message_instance.id if new_message_instance else f"live_{timezone.now().timestamp()}"
                # --- -------------------- ---
                timestamp_for_broadcast = timezone.now().isoformat()

                message_data = {
                    'type': 'user',
                    'message_id': message_id_for_broadcast,
                    'message': message_content,
                    'username': self.user.first_name or self.user.username,
                    'user_id': self.user.id,
                    'timestamp': timestamp_for_broadcast,
                    'user_title': user_title,
                    'reply_to_id': reply_to_id,
                    'quoted_username': quoted_username,
                    'quoted_message_text': quoted_message_text,
                }

                # --- 廣播訊息 ---
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {'type': 'broadcast_message', 'message_data': message_data}
                )
                logger.info(f"Message from {self.user.username} broadcasted.")
            else:
                 logger.warning(f"Received empty message from {self.user.username}.")

        except json.JSONDecodeError: logger.error(f"Failed to decode JSON: {text_data}", exc_info=True)
        except KeyError as e: logger.error(f"Missing key in JSON: {e}. Data: {text_data}", exc_info=True)
        except Exception as e: logger.error(f"Error in receive: {e}. Data: {text_data}", exc_info=True)

    async def broadcast_message(self, event):
        message_data = event.get('message_data')
        if message_data:
            try:
                await self.send(text_data=json.dumps(message_data))
            except Exception as e:
                 logger.error(f"Error sending message in broadcast_message: {e}", exc_info=True)

    # --- 獲取歷史訊息 (使用 'message' 欄位) ---
    @sync_to_async
    def _get_recent_messages_from_db_with_titles(self, limit=50):
        """獲取最近的聊天記錄，並為每個發言者附加稱號。"""
        if not MODELS_IMPORTED or not ChatMessage: return []
        logger.info(f"Fetching recent messages with titles (limit {limit})...")
        try:
            # --- 1. 獲取最近的訊息 ---
            recent_messages_qs = ChatMessage.objects.order_by('-timestamp').select_related('user', 'reply_to', 'reply_to__user')[:limit]
            recent_messages = list(recent_messages_qs)
            # --- -------------------- ---
            if not recent_messages: return []

            # --- 2. 提取用戶 ID ---
            user_ids = {msg.user.id for msg in recent_messages if msg.user}
            # --- ---------------- ---

            # --- 3. 批量計算稱號 ---
            user_titles_map = {}
            if user_ids:
                try:
                    review_counts = Review.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(count=Count('id'))
                    story_counts = StoryReview.objects.filter(user_id__in=user_ids, approved=True).values('user_id').annotate(count=Count('id'))
                    user_total_counts = defaultdict(int)
                    for item in review_counts: user_total_counts[item['user_id']] += item['count']
                    for item in story_counts: user_total_counts[item['user_id']] += item['count']
                    for user_id in user_ids:
                        total_count = user_total_counts.get(user_id, 0)
                        user_titles_map[user_id] = get_user_title_from_count(total_count)
                    logger.debug(f"Bulk calculated titles for history: {user_titles_map}")
                except Exception as e:
                    logger.error(f"Error calculating titles in bulk for history: {e}", exc_info=True)
            # --- ----------------- ---

            # --- 4. 格式化訊息 (使用 'message' 欄位) ---
            formatted_messages = []
            for msg in reversed(recent_messages): # 從舊到新
                user_title = user_titles_map.get(msg.user.id) if msg.user else None
                username = msg.user.first_name or msg.user.username if msg.user else '未知用戶'

                # --- 處理引用信息 (使用 'message' 欄位) ---
                quoted_username = None; quoted_message_text = None; reply_to_id = None
                if msg.reply_to:
                    reply_to_id = msg.reply_to.id
                    quoted_username = msg.reply_to.user.first_name or msg.reply_to.user.username if msg.reply_to.user else '未知用戶'
                    # *** 使用正確的 'message' 欄位 ***
                    raw_quote_text = msg.reply_to.message or '' # <--- 使用 'message'
                    # *** ------------------------ ---
                    temp_snippet = ' '.join(raw_quote_text.splitlines())
                    quoted_message_text = (temp_snippet[:30] + '...') if len(temp_snippet) > 30 else temp_snippet
                # --- --------------------------------- ---

                formatted_messages.append({
                    'type': 'user',
                    'message_id': msg.id,
                    # *** 使用正確的 'message' 欄位 ***
                    'message': msg.message, # <--- 使用 'message'
                    # *** ------------------------ ---
                    'username': username,
                    'user_id': msg.user.id if msg.user else None,
                    'timestamp': msg.timestamp.isoformat(),
                    'user_title': user_title,
                    'reply_to_id': reply_to_id,
                    'quoted_username': quoted_username,
                    'quoted_message_text': quoted_message_text,
                })
            logger.info(f"Formatted {len(formatted_messages)} historical messages.")
            return formatted_messages
        except Exception as e:
             logger.error(f"Error in _get_recent_messages_from_db_with_titles: {e}", exc_info=True)
             return []
    # --- ---------------------------------------- ---

    async def send_recent_messages(self):
        """異步調用獲取並發送歷史訊息的函數"""
        logger.info(f"Sending recent messages to {self.user.username}...")
        try:
            formatted_messages = await self._get_recent_messages_from_db_with_titles()
            await self.send(text_data=json.dumps({
                'type': 'message_history',
                'messages': formatted_messages
            }))
            logger.info(f"Sent message_history ({len(formatted_messages)} messages) to {self.user.username}")
        except Exception as e:
            logger.error(f"Error in send_recent_messages for {self.user.username}: {e}", exc_info=True)
            try:
                await self.send(text_data=json.dumps({
                    'type': 'system', 'message': '載入歷史訊息時發生錯誤。',
                    'timestamp': timezone.now().isoformat()
                }))
            except Exception: pass
    # --- -------------------------- ---