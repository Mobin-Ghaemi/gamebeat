from django.urls import path
from . import views

app_name = 'account'

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.profile, name='profile'),
    path('pricing/', views.pricing, name='pricing'),
    path('purchase/<str:service_type>/', views.purchase_subscription, name='purchase_subscription'),
]