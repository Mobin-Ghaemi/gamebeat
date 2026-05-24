from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_index, name='index'),
    path('users/', views.user_list, name='users'),
    path('users/<int:user_id>/ban/', views.user_toggle_ban, name='user_ban'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('posts/', views.post_list, name='posts'),
    path('posts/bulk-delete/', views.post_bulk_delete, name='post_bulk_delete'),
    path('posts/<int:post_id>/delete/', views.post_delete, name='post_delete'),
    path('posts/<int:post_id>/', views.post_detail, name='post_detail'),
    path('comments/', views.comment_list, name='comments'),
    path('comments/bulk-delete/', views.comment_bulk_delete, name='comment_bulk_delete'),
    path('comments/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
    path('hashtags/', views.hashtag_list, name='hashtags'),
    path('hashtags/<int:hashtag_id>/delete/', views.hashtag_delete, name='hashtag_delete'),
    path('games/', views.game_list, name='games'),
    path('games/add/', views.game_add, name='game_add'),
    path('games/<int:game_id>/edit/', views.game_edit, name='game_edit'),
    path('games/<int:game_id>/delete/', views.game_delete, name='game_delete'),
]
