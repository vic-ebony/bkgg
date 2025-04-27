# D:\bkgg\mybackend\mybackend\settings.py (完整版 - 已加入 Channels 設定)

from pathlib import Path
import os # 確保導入 os 模組

# 建立專案根目錄
BASE_DIR = Path(__file__).resolve().parent.parent

# --- 安全性設定 ---
SECRET_KEY = 'django-insecure-z9g%)2p(#qec$mk+wtn(4pz$twzn$lo7s%j(z*&ll0xdnz+qx8' # 提示：生產環境請務必更換為強密鑰並保密
DEBUG = True # 提示：生產環境請務必設為 False
ALLOWED_HOSTS = ['*'] # 提示：生產環境請設定為你允許的域名

# --- 已安裝的應用程式 ---
INSTALLED_APPS = [
    'daphne',           # 如果你使用 Daphne 作為 ASGI 伺服器，建議放在前面
    'channels',         # Django Channels
    # --- 你現有的其他 App ---
    'myapp',
    'rest_framework',
    'schedule_parser',
    'solo',
    'appointments',
    'chat',             # 新增的 chat App
    # --- Django 預設 App ---
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# --- 中間件 ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# --- 根 URL 配置 ---
ROOT_URLCONF = 'mybackend.urls'

# --- 模板設定 ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # 專案層級模板資料夾位置
        'APP_DIRS': True, # 允許 Django 在每個 App 的 templates/ 目錄下尋找模板
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# --- WSGI/ASGI 應用設定 ---
WSGI_APPLICATION = 'mybackend.wsgi.application' # 保留 WSGI 設定
ASGI_APPLICATION = 'mybackend.asgi.application' # <<<--- 指定 ASGI 應用入口點 (必要)

# --- Channel Layers 設定 (必要) ---
# 使用記憶體作為 Channel Layer (適合開發，無需 Redis)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}
# --- (如果你要用 Redis，請註解掉上面的 InMemory 設定，並取消下面區塊的註解) ---
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {
#             "hosts": [("127.0.0.1", 6379)], # 確認 Redis 地址和端口
#         },
#     },
# }

# --- 資料庫設定 ---
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydatabase',
        'USER': '31628',
        'PASSWORD': 'gl4au6PW!!!!', # 提示：敏感資訊不建議直接寫在程式碼中
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# --- 密碼驗證器 ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# --- 國際化設定 ---
LANGUAGE_CODE = 'zh-hant' # 繁體中文
TIME_ZONE = 'Asia/Taipei' # 亞洲/台北時區
USE_I18N = True           # 啟用國際化
USE_TZ = True             # 啟用時區支持

# --- 靜態檔案設定 (Static files - CSS, JavaScript, Images) ---
STATIC_URL = 'static/' # 訪問靜態檔案的 URL 前綴
# 額外尋找靜態檔案的目錄 (除了 App 內的 static/)
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"), # 指向專案根目錄下的 'static' 資料夾
]
# `collectstatic` 收集靜態檔案的目標目錄 (生產環境用)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles_collected')

# --- MEDIA 設定 (使用者上傳的檔案) ---
MEDIA_URL = '/media/' # 訪問媒體檔案的 URL 前綴
MEDIA_ROOT = BASE_DIR / 'media' # 儲存媒體檔案的實際路徑

# --- 主鍵類型設定 ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- 登入相關設定 ---
LOGIN_URL = 'myapp:login' # 指定登入頁面的 URL 名稱 (請確認與你的 urls.py 一致)
# LOGIN_REDIRECT_URL = '/' # (可選) 登入成功後重定向的 URL
# LOGOUT_REDIRECT_URL = '/' # (可選) 登出成功後重定向的 URL

# --- (可選) 日誌設定 ---
# 可以根據需要配置更詳細的日誌記錄
# LOGGING = { ... }