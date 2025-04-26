# D:\bkgg\mybackend\settings.py
from pathlib import Path
import os # <<<--- 確保導入 os 模組

# 建立專案根目錄
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-z9g%)2p(#qec$mk+wtn(4pz$twzn$lo7s%j(z*&ll0xdnz+qx8'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'myapp',           # 你的應用程式
    'rest_framework',  # Django REST Framework
    'schedule_parser',
    'solo',            # Django-solo App
    'appointments',    # 新增的預約 App
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'mybackend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # 模板資料夾位置
        'APP_DIRS': True,
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

WSGI_APPLICATION = 'mybackend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydatabase',
        'USER': '31628',
        'PASSWORD': 'gl4au6PW!!!!',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# --- 國際化設定 ---
LANGUAGE_CODE = 'zh-hant' # 繁體中文
TIME_ZONE = 'Asia/Taipei' # 亞洲/台北時區
USE_I18N = True           # 啟用國際化
USE_TZ = True             # 啟用時區支持

# --- 靜態檔案設定 (Static files - CSS, JavaScript, Images) ---
# https://docs.djangoproject.com/en/5.0/howto/static-files/

# 瀏覽器訪問靜態檔案時使用的 URL 前綴
STATIC_URL = 'static/'

# 告訴 Django 去哪些額外的目錄尋找靜態檔案 (除了每個 App 下的 static/ 目錄外)
# 這裡指向專案根目錄下的 'static' 資料夾
STATICFILES_DIRS = [
    # BASE_DIR / 'static', # pathlib 語法
    os.path.join(BASE_DIR, "static"), # 使用 os.path.join 更通用
]

# --- 新增：STATIC_ROOT 設定 ---
# 執行 `collectstatic` 指令時，所有靜態檔案會被收集到這個目錄下
# 這個路徑通常用於生產環境部署，指向伺服器上提供靜態檔案的根目錄
# 在開發環境中設定它也能讓 collectstatic 指令正常運行
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles_collected') # 目標資料夾名稱可以自訂
# --- ---------------------- ---


# --- MEDIA 設定 (用於使用者上傳的檔案) ---
# 瀏覽器訪問使用者上傳檔案時使用的 URL 前綴
MEDIA_URL = '/media/'
# 伺服器上儲存使用者上傳檔案的實際目錄路徑
MEDIA_ROOT = BASE_DIR / 'media' # 使用 pathlib 語法
# MEDIA_ROOT = os.path.join(BASE_DIR, 'media') # 或者用 os.path.join

# --- ---

# --- 主鍵類型設定 ---
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'