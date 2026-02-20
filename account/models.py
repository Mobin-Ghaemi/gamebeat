from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Subscription(models.Model):
    """مدل اشتراک برای خدمات مختلف گیمینگ"""
    SUBSCRIPTION_TYPES = [
        ('gamenet', 'گیم‌نت'),
        ('future_service1', 'خدمت آینده ۱'),
        ('future_service2', 'خدمت آینده ۲'),
    ]
    
    SUBSCRIPTION_DURATIONS = [
        ('1_month', '۱ ماهه'),
        ('3_months', '۳ ماهه'),
        ('6_months', '۶ ماهه'),
        ('1_year', '۱ ساله'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    service_type = models.CharField(max_length=50, choices=SUBSCRIPTION_TYPES, verbose_name='نوع خدمت')
    duration = models.CharField(max_length=20, choices=SUBSCRIPTION_DURATIONS, verbose_name='مدت اشتراک')
    start_date = models.DateTimeField(default=timezone.now, verbose_name='تاریخ شروع')
    end_date = models.DateTimeField(verbose_name='تاریخ پایان')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'اشتراک'
        verbose_name_plural = 'اشتراک‌ها'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username} - {self.get_service_type_display()}'
    
    @property
    def is_expired(self):
        return timezone.now() > self.end_date


class UserProfile(models.Model):
    """پروفایل کاربر برای اطلاعات اضافی"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name='کاربر')
    phone = models.CharField(max_length=15, blank=True, null=True, verbose_name='شماره تماس')
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True, verbose_name='تصویر پروفایل')
    date_of_birth = models.DateField(blank=True, null=True, verbose_name='تاریخ تولد')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    
    class Meta:
        verbose_name = 'پروفایل کاربر'
        verbose_name_plural = 'پروفایل‌های کاربران'
    
    def __str__(self):
        return f'پروفایل {self.user.username}'
