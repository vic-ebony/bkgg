# D:\bkgg\mybackend\mybackend\urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # --- *** 修改這一行，添加 namespace='myapp' *** ---
    path('', include('myapp.urls', namespace='myapp')),
    # ---------------------------------------------
    # --- 包含 schedule_parser 的 URLs (保持不變) ---
    path('schedule-admin/', include('schedule_parser.urls', namespace='schedule_parser')),
]

# --- Media 路徑配置 (保持不變) ---
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)