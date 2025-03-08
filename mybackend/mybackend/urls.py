"""
URL configuration for mybackend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from myapp.views import home  # 匯入 home view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/animals/', include('myapp.urls')),  # 假設你的 API URL 在 myapp/urls.py 中定義
    path('', home, name='home'),  # 設定空路徑為首頁
]


