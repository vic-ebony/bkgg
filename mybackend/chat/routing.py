# D:\bkgg\mybackend\chat\routing.py (新檔案)

from django.urls import re_path
from . import consumers # 稍後會建立 consumers.py

# 定義 WebSocket 的 URL 模式
websocket_urlpatterns = [
    # 將 ws://<你的域名>/ws/chat/ 路徑的連接請求，路由到 ChatConsumer 處理
    re_path(r'^ws/chat/$', consumers.ChatConsumer.as_asgi()),
]