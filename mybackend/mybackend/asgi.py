# D:\bkgg\mybackend\mybackend\asgi.py (修改版)

import os
import django # <<<--- 導入 django
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mybackend.settings')

# --- 在導入 App 路由之前，先執行 django.setup() ---
django.setup() # <<<--- 添加這一行
# ---------------------------------------------------

# 現在可以安全地導入 App 的路由了
import chat.routing

# Initialize Django ASGI application (獲取已配置好的 application)
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                chat.routing.websocket_urlpatterns
            )
        )
    ),
})