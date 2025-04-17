# D:\bkgg\mybackend\schedule_parser\urls.py
from django.urls import path
from . import views

app_name = 'schedule_parser'

urlpatterns = [
    # 指向班表解析視圖
    path('parse/', views.parse_schedule_view, name='parse_schedule'),
    # 未來可以添加其他管理功能的 URL
]