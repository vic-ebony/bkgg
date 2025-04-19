# D:\bkgg\mybackend\myapp\urls.py
from django.urls import path
from . import views # 確保導入 views

app_name = 'myapp' # 建議定義

urlpatterns = [
    # --- Home view 現在處理多種 AJAX 請求 ---
    path('', views.home, name='home'),

    # --- 用戶認證 ---
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # --- 心得相關 ---
    path('add_review/', views.add_review, name='add_review'),

    # --- 待約相關 ---
    path('add_pending/', views.add_pending_appointment, name='add_pending'),
    path('remove_pending/', views.remove_pending, name='remove_pending'),

    # --- 筆記相關 ---
    path('add_note/', views.add_note, name='add_note'),
    path('delete_note/', views.delete_note, name='delete_note'),
    path('update_note/', views.update_note, name='update_note'),

    # --- 限時動態心得相關 ---
    path('add_story_review/', views.add_story_review, name='add_story_review'),
    path('ajax/active_stories/', views.ajax_get_active_stories, name='ajax_get_active_stories'),
    path('ajax/story_detail/<int:story_id>/', views.ajax_get_story_detail, name='ajax_get_story_detail'),

    # --- 其他獨立的 AJAX URLs ---
    path('ajax/weekly_schedule/', views.ajax_get_weekly_schedule, name='ajax_get_weekly_schedule'),
    path('ajax/hall-of-fame/', views.ajax_get_hall_of_fame, name='ajax_get_hall_of_fame'),

    # --- 如果你需要上傳圖片班表的功能，取消註釋下面這行 ---
    # path('upload_schedule_image/', views.upload_schedule_image_view, name='upload_schedule_image'),

    # --- *** 移除之前添加的合併 URL，因為現在由 Admin 的 get_urls 處理 *** ---
    # path('admin/animal/<int:animal_id>/merge-transfer/',
    #      views.merge_transfer_animal_view,
    #      name='myapp_animal_merge_transfer'),
    # --- *** ---
]