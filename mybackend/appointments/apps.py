# D:\bkgg\mybackend\appointments\apps.py
from django.apps import AppConfig

class AppointmentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'appointments'
    verbose_name = "預約管理系統" # 在 Admin 首頁顯示的名稱