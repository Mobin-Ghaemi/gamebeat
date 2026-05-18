from django.urls import path
from . import views

app_name = 'community'

urlpatterns = [
    path('', views.feed, name='feed'),
    path('search/', views.search_gamers, name='search'),
    path('lfg/', views.lfg_board, name='lfg'),
    path('lfg/create/', views.create_lfg, name='create_lfg'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('post/create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/like/', views.toggle_like, name='toggle_like'),
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/me/', views.my_profile_dashboard, name='my_profile'),
    path('profile/<str:username>/', views.gamer_profile, name='profile'),
    path('follow/<str:username>/', views.toggle_follow, name='toggle_follow'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('gaming/connect/', views.connect_gaming_account, name='connect_gaming'),
    path('gaming/disconnect/', views.disconnect_gaming_account, name='disconnect_gaming'),
    path('post/new/', views.create_post_page, name='create_post_page'),
    path('api/hashtags/', views.hashtag_suggest, name='hashtag_suggest'),
    path('api/link-preview/', views.link_preview, name='link_preview'),
    path('hashtag/<str:tag_name>/', views.hashtag_feed, name='hashtag_feed'),
    # Reactions
    path('post/<int:post_id>/react/', views.react_post, name='react_post'),
    path('post/<int:post_id>/reactions/', views.get_post_reactions, name='post_reactions'),
    # Backlog
    path('backlog/add/', views.backlog_add, name='backlog_add'),
    path('backlog/<int:item_id>/update/', views.backlog_update, name='backlog_update'),
    path('backlog/<int:item_id>/remove/', views.backlog_remove, name='backlog_remove'),
    path('backlog/<int:item_id>/favorite/', views.backlog_toggle_favorite, name='backlog_favorite'),
    path('backlog/<str:username>/', views.backlog_list, name='backlog_list'),
    path('games/', views.games_ranking, name='games_ranking'),
    # Notifications
    path('notifications/', views.notifications_list, name='notifications'),
    path('api/notifications/count/', views.notifications_count, name='notifications_count'),
    # Direct Messages
    path('inbox/', views.inbox, name='inbox'),
    path('dm/<str:username>/', views.conversation, name='conversation'),
    path('dm/<str:username>/send/', views.send_message_ajax, name='send_message'),
    path('api/inbox/count/', views.inbox_unread_count, name='inbox_count'),
]
