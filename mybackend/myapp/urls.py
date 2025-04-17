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

    # --- 其他獨立的 AJAX URLs (大部分已合併到 home) ---
    # path('ajax/pending/', views.ajax_get_pending_list, name='ajax_get_pending_list'),      # 已合併
    # path('ajax/notes/', views.ajax_get_my_notes, name='ajax_get_my_notes'),          # 已合併
    # path('ajax/latest-reviews/', views.ajax_get_latest_reviews, name='ajax_get_latest_reviews'), # <<<--- 已合併，刪除
    # path('ajax/recommendations/', views.ajax_get_recommendations, name='ajax_get_recommendations'), # <<<--- 已合併，刪除

    # --- 保留仍然獨立的視圖 URL ---
    path('ajax/weekly_schedule/', views.ajax_get_weekly_schedule, name='ajax_get_weekly_schedule'), # 保留，view 獨立
    path('ajax/hall-of-fame/', views.ajax_get_hall_of_fame, name='ajax_get_hall_of_fame'),    # 保留，view 獨立

    # --- 如果你需要上傳圖片班表的功能，取消註釋下面這行 ---
    # path('upload_schedule_image/', views.upload_schedule_image_view, name='upload_schedule_image'),
]