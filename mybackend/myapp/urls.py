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
    path('add_review/', views.add_review, name='add_review'), # GET for list, POST for submit

    # --- 待約相關 ---
    path('add_pending/', views.add_pending_appointment, name='add_pending'),
    path('remove_pending/', views.remove_pending, name='remove_pending'),

    # --- 筆記相關 ---
    path('add_note/', views.add_note, name='add_note'),
    path('delete_note/', views.delete_note, name='delete_note'),
    path('update_note/', views.update_note, name='update_note'),

    # --- 限時動態心得相關 ---
    path('add_story_review/', views.add_story_review, name='add_story_review'), # POST only
    path('ajax/active_stories/', views.ajax_get_active_stories, name='ajax_get_active_stories'),
    path('ajax/story_detail/<int:story_id>/', views.ajax_get_story_detail, name='ajax_get_story_detail'),

    # --- 其他獨立的 AJAX URLs ---
    path('ajax/weekly_schedule/', views.ajax_get_weekly_schedule, name='ajax_get_weekly_schedule'),
    path('ajax/hall_of_fame/', views.ajax_get_hall_of_fame, name='ajax_get_hall_of_fame'),
    path('ajax/add_feedback/', views.add_review_feedback, name='add_review_feedback'), # For feedback

    # --- 個人檔案 AJAX URL ---
    path('ajax/profile_data/', views.ajax_get_profile_data, name='ajax_get_profile_data'),

    # --- 新增的搜尋 AJAX URL ---
    path('ajax/search_beauticians/', views.ajax_search_beauticians, name='ajax_search_beauticians'),
    # --- ------------------- ---

    # --- 如果你需要上傳圖片班表的功能，取消註釋下面這行 ---
    # path('upload_schedule_image/', views.upload_schedule_image_view, name='upload_schedule_image'),

    # --- Admin Merge URL is handled by admin.py get_urls ---
]