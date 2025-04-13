# urls.py
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

    # --- NEW AJAX URLs ---
    # (These URLs will be called by JavaScript when opening the corresponding modals)
    path('ajax/pending/', views.ajax_get_pending_list, name='ajax_get_pending_list'),
    path('ajax/notes/', views.ajax_get_my_notes, name='ajax_get_my_notes'),
    path('ajax/latest-reviews/', views.ajax_get_latest_reviews, name='ajax_get_latest_reviews'),
    path('ajax/recommendations/', views.ajax_get_recommendations, name='ajax_get_recommendations'),
    # --- End NEW AJAX URLs ---

    # path('my_notes/', views.my_notes, name='my_notes'), # Can likely be removed if modal is sufficient
    # path('my_notes_json/', views.my_notes_json, name='my_notes_json'), # Keep if modal uses it (Seems unused now)
]