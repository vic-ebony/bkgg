from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload_schedule_image/', views.upload_schedule_image_view, name='upload_schedule_image'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('add_review/', views.add_review, name='add_review'),
    path('add_pending/', views.add_pending_appointment, name='add_pending'),
    path('remove_pending/', views.remove_pending, name='remove_pending'),
]
