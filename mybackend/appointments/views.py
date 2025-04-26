# D:\bkgg\mybackend\appointments\views.py
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.admin.views.decorators import staff_member_required

# 你可以根據需要增加視圖，例如儀表板
# @staff_member_required
# def dashboard(request):
#     # 查詢預約數據等
#     return render(request, 'appointments/dashboard.html', {})

def index(request):
    # 只是為了讓這個檔案不完全是空的
    return HttpResponse("這裡是 Appointments App 的基礎頁面。")