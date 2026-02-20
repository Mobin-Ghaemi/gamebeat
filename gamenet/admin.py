from django.contrib import admin
from .models import Game, Device, Session, Tournament, TournamentParticipant, DailyReport, GameNet, GameNetImage, SubscriptionPlan, ProductCategory, Product, Order, OrderItem


@admin.register(GameNet)
class GameNetAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'owner__username']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(GameNetImage)
class GameNetImageAdmin(admin.ModelAdmin):
    list_display = ['gamenet', 'title', 'is_primary', 'order', 'created_at']
    list_filter = ['gamenet', 'is_primary']
    search_fields = ['title', 'gamenet__name']
    list_editable = ['is_primary', 'order']


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'price', 'duration_days', 'max_devices', 'is_active', 'is_popular']
    list_filter = ['is_active', 'is_popular']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['name', 'genre', 'created_at']
    search_fields = ['name', 'genre']
    list_filter = ['genre']


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['number', 'name', 'device_type', 'hourly_rate', 'status']
    list_filter = ['device_type', 'status']
    search_fields = ['name']
    filter_horizontal = ['games']


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['device', 'customer_name', 'start_time', 'end_time', 'total_cost', 'is_active']
    list_filter = ['is_active', 'start_time']
    search_fields = ['customer_name', 'customer_phone']
    date_hierarchy = 'start_time'


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ['name', 'game', 'start_date', 'prize_pool', 'status', 'participants_count']
    list_filter = ['status', 'game']
    search_fields = ['name']
    date_hierarchy = 'start_date'

    def participants_count(self, obj):
        return obj.participants.count()
    participants_count.short_description = 'شرکت‌کنندگان'


@admin.register(TournamentParticipant)
class TournamentParticipantAdmin(admin.ModelAdmin):
    list_display = ['name', 'tournament', 'phone', 'paid', 'rank']
    list_filter = ['tournament', 'paid']
    search_fields = ['name', 'phone', 'gamer_tag']


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_sessions', 'total_revenue', 'total_hours']
    date_hierarchy = 'date'


# ========== Buffet Models ==========
@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'gamenet', 'icon', 'order', 'is_active']
    list_filter = ['gamenet', 'is_active']
    search_fields = ['name']
    list_editable = ['order', 'is_active']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'gamenet', 'price', 'stock', 'is_available', 'is_active']
    list_filter = ['gamenet', 'category', 'is_available', 'is_active']
    search_fields = ['name', 'description']
    list_editable = ['price', 'stock', 'is_available', 'is_active']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'gamenet', 'customer_name', 'total_amount', 'status', 'is_paid', 'created_at']
    list_filter = ['gamenet', 'status', 'is_paid', 'created_at']
    search_fields = ['customer_name']
    date_hierarchy = 'created_at'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'unit_price', 'total_price']
    list_filter = ['product']
