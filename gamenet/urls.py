from django.urls import path
from . import views

app_name = 'gamenet'

urlpatterns = [
    # داشبورد اصلی GameNet
    path('', views.dashboard, name='dashboard'),
    
    # تنظیمات گیم‌نت (باید قبل از slug patterns باشد)
    path('settings/', views.gamenet_settings, name='gamenet_settings'),
    path('api/delete-image/<int:image_id>/', views.delete_gamenet_image, name='delete_gamenet_image'),
    
    # گزارشات
    path('reports/', views.reports, name='reports'),
    
    # دستگاه‌ها
    path('devices/', views.device_list, name='device_list'),
    path('devices/create/', views.device_create, name='device_create'),
    path('devices/<int:pk>/edit/', views.device_edit, name='device_edit'),
    path('devices/<int:pk>/delete/', views.device_delete, name='device_delete'),
    
    # جلسات
    path('session/start/<int:device_id>/', views.start_session, name='start_session'),
    path('session/stop/<int:session_id>/', views.stop_session, name='stop_session'),
    path('session/<int:session_id>/', views.session_detail, name='session_detail'),
    path('sessions/', views.session_list, name='session_list'),
    path('api/session-time/', views.get_session_time, name='get_session_time'),
    path('api/quick-start/<int:device_id>/', views.quick_start_session, name='quick_start_session'),
    path('api/quick-stop/<int:session_id>/', views.quick_stop_session, name='quick_stop_session'),
    path('api/session-cost/<int:session_id>/', views.get_session_current_cost, name='get_session_current_cost'),
    path('api/session/<int:session_id>/delete/', views.delete_session_api, name='delete_session_api'),
    
    # API برای دسته اضافی
    path('api/add-controller/<int:session_id>/', views.add_controller, name='add_controller'),
    path('api/remove-controller/<int:session_id>/', views.remove_controller, name='remove_controller'),
    
    # API برای ویرایش دستگاه
    path('api/device-update/<int:device_id>/', views.device_update_api, name='device_update_api'),
    
    # بازی‌ها
    path('games/', views.game_list, name='game_list'),
    path('games/create/', views.game_create, name='game_create'),
    path('games/<int:pk>/edit/', views.game_edit, name='game_edit'),
    path('games/<int:pk>/delete/', views.game_delete, name='game_delete'),
    
    # بوفه
    path('buffet/', views.buffet_dashboard, name='buffet_dashboard'),
    path('buffet/recent-sales/', views.recent_sales_page, name='recent_sales_page'),
    path('recent-sales/', views.recent_sales_page, name='recent_sales'),
    path('buffet/products/', views.product_list, name='product_list'),
    path('buffet/products/create/', views.product_create, name='product_create'),
    path('buffet/products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('buffet/products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('buffet/categories/', views.category_list, name='category_list'),
    path('buffet/categories/quick-create/', views.category_quick_create, name='category_quick_create'),
    path('buffet/categories/create/', views.category_create, name='category_create'),
    path('buffet/categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    path('buffet/categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    
    # API بوفه
    path('api/product/<int:pk>/toggle-availability/', views.product_toggle_availability, name='product_toggle_availability'),
    path('api/product/<int:pk>/update-stock/', views.product_update_stock, name='product_update_stock'),
    path('api/order/create/', views.create_order, name='create_order'),
    path('api/order/quick-sell/', views.quick_sell, name='quick_sell'),
    path('api/order/<int:order_id>/status/', views.update_order_status, name='update_order_status'),
    path('api/products/', views.get_products_api, name='get_products_api'),
    path('api/session/<int:session_id>/end-with-order/', views.end_session_with_order, name='end_session_with_order'),
    
    # تورنومنت‌ها
    path('tournaments/', views.tournament_list, name='tournament_list'),
    path('tournaments/create/', views.tournament_create, name='tournament_create'),
    path('tournaments/<int:pk>/', views.tournament_detail, name='tournament_detail'),
    path('tournaments/<int:pk>/edit/', views.tournament_edit, name='tournament_edit'),
    path('tournaments/<int:pk>/register/', views.tournament_register, name='tournament_register'),
    
    # GameNet management (برای مدیریت گیم‌نت‌ها)
    path('user/dashboard/', views.user_dashboard, name='user_dashboard'),
    path('create/', views.create_gamenet, name='create_gamenet'),
    
    # این‌ها باید آخر باشند چون slug می‌توانند هر چیزی باشند
    path('<slug:slug>/edit/', views.edit_gamenet, name='edit_gamenet'),
    path('<slug:slug>/delete/', views.delete_gamenet, name='delete_gamenet'),
    path('<slug:slug>/', views.panel_dashboard, name='panel_dashboard'),
    path('<slug:slug>/devices/', views.panel_device_list, name='panel_device_list'),
    path('<slug:slug>/sessions/', views.panel_session_list, name='panel_session_list'),
    path('<slug:slug>/games/', views.panel_game_list, name='panel_game_list'),
    path('<slug:slug>/tournaments/', views.panel_tournament_list, name='panel_tournament_list'),
    path('<slug:slug>/reports/', views.panel_reports, name='panel_reports'),
]
