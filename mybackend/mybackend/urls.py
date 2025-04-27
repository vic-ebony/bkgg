# D:\bkgg\mybackend\mybackend\urls.py (完整版 - 已加入靜態文件處理)

from django.contrib import admin
from django.urls import path, include
from django.conf import settings         # 導入 settings 以便讀取 DEBUG 和靜態/媒體設定
from django.conf.urls.static import static # 導入 static 輔助函數

urlpatterns = [
    # Django Admin 後台路徑
    path('admin/', admin.site.urls),

    # 包含 myapp 的 URL 配置，並指定命名空間為 'myapp'
    # 所有來自 myapp/urls.py 的 URL 都會掛載在根路徑 ('') 下
    path('', include('myapp.urls', namespace='myapp')),

    # 包含 schedule_parser App 的 URL 配置，掛載在 /schedule-admin/ 路徑下
    # 並指定命名空間為 'schedule_parser'
    path('schedule-admin/', include('schedule_parser.urls', namespace='schedule_parser')),

    # 如果你的 chat App 未來有需要處理的 HTTP 請求 (例如顯示歷史記錄頁面)，
    # 你可以在這裡添加類似的 include 語句：
    # path('chat/', include('chat.urls', namespace='chat')),
]

# --- 開發模式 (DEBUG=True) 下的額外 URL 配置 ---
# 這個區塊只在 settings.py 中的 DEBUG 設定為 True 時生效
if settings.DEBUG:
    # 1. 添加處理靜態文件 (STATIC_URL) 的路由
    #    這使得開發伺服器能夠找到並提供位於 STATICFILES_DIRS 或 App 內部 static/ 目錄的靜態文件
    #    注意：伺服器查找靜態文件的主要機制是 findstatic，這行主要是確保 /static/ 路徑被路由系統識別
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    #    (雖然 document_root 指向 STATIC_ROOT，但在 DEBUG 模式下，開發伺服器
    #     通常會優先使用 findstatic 的查找結果，而不是直接從 STATIC_ROOT 提供)

    # 2. 添加處理媒體文件 (MEDIA_URL) 的路由
    #    這使得開發伺服器能夠提供用戶上傳的文件 (存放在 MEDIA_ROOT 目錄中)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# --- 開發模式 URL 配置結束 ---

# 注意：在生產環境 (DEBUG=False) 中，你不應該使用 Django 來提供靜態文件和媒體文件。
#       通常會由 Nginx, Apache 或其他專門的 Web 伺服器直接處理這些文件的請求，
#       因此上面的 if settings.DEBUG: 區塊在生產環境中不會生效。