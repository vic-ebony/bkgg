# D:\bkgg\mybackend\myapp\urls.py (完整版 - 新增搶約專區的 URL)

from django.urls import path
from . import views # 確保導入 views

app_name = 'myapp' # 建議定義

urlpatterns = [
    # --- 初始頁面視圖 (只渲染頁面) ---
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

    # --- 搜尋 AJAX URL ---
    path('ajax/search_beauticians/', views.ajax_search_beauticians, name='ajax_search_beauticians'),

    # --- 新增：每日班表的獨立 AJAX URL ---
    path('ajax/daily_schedule/', views.ajax_get_daily_schedule, name='ajax_get_daily_schedule'),

    # --- 新增：搶約專區的 AJAX URLs --- NEW ---
    path('ajax/pre_booking_dates/', views.ajax_get_pre_booking_dates, name='ajax_get_pre_booking_dates'),
    path('ajax/pre_booking_slots/', views.ajax_get_pre_booking_slots, name='ajax_get_pre_booking_slots'),
    # --- ---

    # --- 新增：其他常用列表的獨立 AJAX URLs (取代 home view 的 fetch 參數) ---
    # 注意：這些路徑可能與你原有的部分重複，請確保每個功能只有一個 URL
    # 如果你原本就有這些路徑，那這裡不需要再加，只需確保 JS 使用它們
    path('ajax/pending/', views.ajax_get_pending_list, name='ajax_get_pending_list'),
    path('ajax/my_notes/', views.ajax_get_my_notes, name='ajax_get_my_notes'),
    path('ajax/latest_reviews/', views.ajax_get_latest_reviews, name='ajax_get_latest_reviews'),
    path('ajax/recommendations/', views.ajax_get_recommendations, name='ajax_get_recommendations'),

    # --- Admin Merge URL is handled by admin.py get_urls ---
]