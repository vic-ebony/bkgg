from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload_schedule_image/', views.upload_schedule_image_view, name='upload_schedule_image'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('add_review/', views.add_review, name='add_review'),
    # 若有需要 API，可加上：
    # path('api/animals/', views.AnimalListAPIView.as_view(), name='animal_list_api'),
]
