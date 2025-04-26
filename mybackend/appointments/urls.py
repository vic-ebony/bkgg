# D:\bkgg\mybackend\appointments\urls.py
from django.urls import path
from . import views

app_name = 'appointments' # 定義 App 的命名空間

urlpatterns = [
    # path('', views.dashboard, name='dashboard'), # 如果未來有儀表板
    path('', views.index, name='index'), # 基礎路徑
]