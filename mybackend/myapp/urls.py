# urls.py
# (No changes to existing imports)
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    # path('upload_schedule_image/', views.upload_schedule_image_view, name='upload_schedule_image'), # Keep if needed
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('add_review/', views.add_review, name='add_review'),
    path('add_pending/', views.add_pending_appointment, name='add_pending'),
    path('remove_pending/', views.remove_pending, name='remove_pending'),
    path('add_note/', views.add_note, name='add_note'),
    path('delete_note/', views.delete_note, name='delete_note'),
    path('update_note/', views.update_note, name='update_note'),

    # --- Story Review URLs ---
    path('add_story_review/', views.add_story_review, name='add_story_review'),
    path('ajax/active_stories/', views.ajax_get_active_stories, name='ajax_get_active_stories'),
    path('ajax/story_detail/<int:story_id>/', views.ajax_get_story_detail, name='ajax_get_story_detail'),

    # --- AJAX URLs for Modals ---
    path('ajax/pending/', views.ajax_get_pending_list, name='ajax_get_pending_list'),
    path('ajax/notes/', views.ajax_get_my_notes, name='ajax_get_my_notes'),
    path('ajax/latest-reviews/', views.ajax_get_latest_reviews, name='ajax_get_latest_reviews'),
    path('ajax/recommendations/', views.ajax_get_recommendations, name='ajax_get_recommendations'),

    # --- START: URL for Weekly Schedule AJAX (No change needed here) ---
    path('ajax/weekly_schedule/', views.ajax_get_weekly_schedule, name='ajax_get_weekly_schedule'),
    # --- END: URL for Weekly Schedule AJAX ---

    # --- START: URL for Hall of Fame AJAX ---
    path('ajax/hall-of-fame/', views.ajax_get_hall_of_fame, name='ajax_get_hall_of_fame'),
    # --- END: URL for Hall of Fame AJAX ---

]