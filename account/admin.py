from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Subscription, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'پروفایل'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user', 'service_type', 'duration', 'start_date', 'end_date', 'is_active', 'is_expired']
    list_filter = ['service_type', 'duration', 'is_active', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at']
    
    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = 'منقضی شده'


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
