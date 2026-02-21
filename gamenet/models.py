from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
import math


class SubscriptionPlan(models.Model):
    """پلن‌های اشتراک"""
    name = models.CharField(max_length=100, verbose_name="نام پلن")
    slug = models.SlugField(unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="قیمت (تومان)")
    duration_days = models.PositiveIntegerField(verbose_name="مدت (روز)")
    max_devices = models.PositiveIntegerField(default=10, verbose_name="حداکثر دستگاه")
    max_tournaments = models.PositiveIntegerField(default=5, verbose_name="حداکثر مسابقه در ماه")
    features = models.TextField(blank=True, verbose_name="ویژگی‌ها")
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False, verbose_name="محبوب")
    
    class Meta:
        verbose_name = "پلن اشتراک"
        verbose_name_plural = "پلن‌های اشتراک"
        ordering = ['price']

    def __str__(self):
        return self.name


class GameNet(models.Model):
    """مدل گیم‌نت - هر کاربر می‌تواند یک گیم‌نت داشته باشد"""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='gamenets', verbose_name="مالک")
    name = models.CharField(max_length=200, verbose_name="نام گیم‌نت")
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, verbose_name="توضیحات")
    address = models.TextField(blank=True, verbose_name="آدرس")
    phone = models.CharField(max_length=15, blank=True, verbose_name="تلفن")
    logo = models.ImageField(upload_to='gamenets/logos/', blank=True, null=True, verbose_name="لوگو")
    
    # تنظیمات قیمت‌گذاری
    extra_controller_price = models.DecimalField(
        max_digits=10, decimal_places=0, default=0, 
        verbose_name="قیمت دسته اضافی (تومان/ساعت)"
    )
    ps4_controller_price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="قیمت دسته PS4 اضافی (تومان/ساعت)",
    )
    ps5_controller_price = models.DecimalField(
        max_digits=10,
        decimal_places=0,
        default=0,
        verbose_name="قیمت دسته PS5 اضافی (تومان/ساعت)",
    )
    
    is_active = models.BooleanField(default=False, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "گیم‌نت"
        verbose_name_plural = "گیم‌نت‌ها"

    def __str__(self):
        return self.name

    @property
    def active_subscription(self):
        from django.utils import timezone
        return self.subscriptions.filter(
            is_active=True,
            end_date__gte=timezone.now()
        ).first()

    @property
    def is_subscription_active(self):
        return self.active_subscription is not None


class GameNetImage(models.Model):
    """تصاویر گالری گیم‌نت"""
    gamenet = models.ForeignKey(GameNet, on_delete=models.CASCADE, related_name='images', verbose_name="گیم‌نت")
    image = models.ImageField(upload_to='gamenets/gallery/', verbose_name="تصویر")
    title = models.CharField(max_length=100, blank=True, verbose_name="عنوان")
    is_primary = models.BooleanField(default=False, verbose_name="تصویر اصلی")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تصویر گیم‌نت"
        verbose_name_plural = "تصاویر گیم‌نت"
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.gamenet.name} - {self.title or 'تصویر'}"


class Subscription(models.Model):
    """اشتراک گیم‌نت"""
    gamenet = models.ForeignKey(GameNet, on_delete=models.CASCADE, related_name='subscriptions', verbose_name="گیم‌نت")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, verbose_name="پلن")
    start_date = models.DateTimeField(verbose_name="تاریخ شروع")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ پایان")
    amount_paid = models.DecimalField(max_digits=12, decimal_places=0, verbose_name="مبلغ پرداختی")
    is_active = models.BooleanField(default=True)
    payment_ref = models.CharField(max_length=100, blank=True, verbose_name="کد پیگیری")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "اشتراک"
        verbose_name_plural = "اشتراک‌ها"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.gamenet.name} - {self.plan.name}"


class Game(models.Model):
    """مدل بازی‌ها"""
    gamenet = models.ForeignKey(GameNet, on_delete=models.CASCADE, related_name='games', verbose_name="گیم‌نت")
    name = models.CharField(max_length=100, verbose_name="نام بازی")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    genre = models.CharField(max_length=50, verbose_name="ژانر", blank=True)
    image = models.ImageField(upload_to='games/', blank=True, null=True, verbose_name="تصویر بازی")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "بازی"
        verbose_name_plural = "بازی‌ها"

    def __str__(self):
        return self.name


class Device(models.Model):
    """مدل دستگاه/سیستم"""
    STATUS_CHOICES = [
        ('available', 'آزاد'),
        ('occupied', 'در حال استفاده'),
        ('maintenance', 'در حال تعمیر'),
    ]
    
    DEVICE_TYPES = [
        ('pc', 'کامپیوتر'),
        ('ps4', 'PS4'),
        ('ps5', 'PS5'),
        ('xbox', 'Xbox'),
        ('vr', 'VR'),
    ]

    gamenet = models.ForeignKey(GameNet, on_delete=models.CASCADE, related_name='devices', verbose_name="گیم‌نت")
    number = models.PositiveIntegerField(verbose_name="شماره دستگاه")
    name = models.CharField(max_length=100, verbose_name="نام دستگاه")
    device_type = models.CharField(max_length=20, choices=DEVICE_TYPES, default='pc', verbose_name="نوع دستگاه")
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="قیمت ساعتی (تومان)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available', verbose_name="وضعیت")
    games = models.ManyToManyField(Game, blank=True, verbose_name="بازی‌های موجود")
    specs = models.TextField(blank=True, verbose_name="مشخصات فنی")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "دستگاه"
        verbose_name_plural = "دستگاه‌ها"
        ordering = ['number']
        unique_together = ['gamenet', 'number']

    def __str__(self):
        return f"دستگاه #{self.number} - {self.name}"


class Session(models.Model):
    """مدل جلسه استفاده از دستگاه"""
    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('completed', 'پایان یافته'),
        ('cancelled', 'لغو شده'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='sessions', verbose_name="دستگاه")
    customer_name = models.CharField(max_length=100, blank=True, verbose_name="نام مشتری")
    customer_phone = models.CharField(max_length=15, blank=True, verbose_name="شماره تلفن مشتری")
    start_time = models.DateTimeField(verbose_name="زمان شروع")
    end_time = models.DateTimeField(null=True, blank=True, verbose_name="زمان پایان")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="قیمت ساعتی")
    total_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="هزینه کل")
    
    # دسته‌های اضافی
    extra_controllers = models.PositiveIntegerField(default=0, verbose_name="تعداد دسته اضافی")
    extra_controller_rate = models.DecimalField(
        max_digits=10, decimal_places=0, default=0, 
        verbose_name="قیمت دسته اضافی (تومان/ساعت)"
    )
    
    notes = models.TextField(blank=True, verbose_name="یادداشت")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "جلسه"
        verbose_name_plural = "جلسات"
        ordering = ['-start_time']

    def __str__(self):
        return f"جلسه دستگاه #{self.device.number} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def calculate_duration_minutes(self):
        """محاسبه مدت زمان به دقیقه"""
        if self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() / 60)
        return 0

    def calculate_cost(self):
        """محاسبه هزینه بر اساس زمان و دسته‌های اضافی"""
        if self.end_time:
            delta = self.end_time - self.start_time
            total_seconds = delta.total_seconds()
            # بدون حداقل - دقیقاً بر اساس زمان واقعی
            hours = Decimal(total_seconds) / Decimal(3600)
            
            # هزینه اصلی دستگاه
            device_cost = self.hourly_rate * hours
            
            # هزینه دسته‌های اضافی
            controller_cost = Decimal(self.extra_controllers) * self.extra_controller_rate * hours
            
            return device_cost + controller_cost
        return Decimal('0')


class Tournament(models.Model):
    """مدل مسابقات"""
    STATUS_CHOICES = [
        ('upcoming', 'در انتظار'),
        ('ongoing', 'در حال برگزاری'),
        ('completed', 'پایان یافته'),
        ('cancelled', 'لغو شده'),
    ]
    VISIBILITY_CHOICES = [
        ('public', 'پابلیک'),
        ('private', 'خصوصی'),
    ]

    gamenet = models.ForeignKey(GameNet, on_delete=models.CASCADE, related_name='tournaments', verbose_name="گیم‌نت")
    name = models.CharField(max_length=200, verbose_name="نام مسابقه")
    game = models.ForeignKey(Game, on_delete=models.CASCADE, verbose_name="بازی")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    start_date = models.DateTimeField(verbose_name="تاریخ شروع")
    end_date = models.DateTimeField(null=True, blank=True, verbose_name="تاریخ پایان")
    entry_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="هزینه ورودی")
    prize_pool = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="جایزه کل")
    max_participants = models.PositiveIntegerField(default=16, verbose_name="حداکثر شرکت‌کنندگان")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming', verbose_name="وضعیت")
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='public', verbose_name="نوع دسترسی")
    registration_open = models.BooleanField(default=True, verbose_name="ثبت‌نام باز است")
    show_participants_public = models.BooleanField(default=True, verbose_name="نمایش عمومی شرکت‌کنندگان")
    champion = models.ForeignKey(
        'TournamentParticipant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='champion_in_tournaments',
        verbose_name="قهرمان",
    )
    image = models.ImageField(upload_to='tournaments/', blank=True, null=True, verbose_name="تصویر")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "مسابقه"
        verbose_name_plural = "مسابقات"
        ordering = ['-start_date']

    def __str__(self):
        return self.name

    @property
    def participants_count(self):
        return self.participants.count()


class TournamentParticipant(models.Model):
    """مدل شرکت‌کنندگان مسابقه"""
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='participants', verbose_name="مسابقه")
    name = models.CharField(max_length=100, verbose_name="نام")
    phone = models.CharField(max_length=15, verbose_name="شماره تلفن")
    gamer_tag = models.CharField(max_length=50, blank=True, verbose_name="آیدی گیمری")
    registered_at = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=False, verbose_name="پرداخت شده")
    rank = models.PositiveIntegerField(null=True, blank=True, verbose_name="رتبه")

    class Meta:
        verbose_name = "شرکت‌کننده"
        verbose_name_plural = "شرکت‌کنندگان"
        unique_together = ['tournament', 'phone']

    def __str__(self):
        return f"{self.name} - {self.tournament.name}"


class TournamentMatch(models.Model):
    """مسابقات مرحله‌ای تورنومنت"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('completed', 'پایان یافته'),
        ('bye', 'استراحت'),
    ]

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='matches', verbose_name="مسابقه")
    round_number = models.PositiveIntegerField(verbose_name="شماره دور")
    match_number = models.PositiveIntegerField(verbose_name="شماره بازی")
    participant1 = models.ForeignKey(
        TournamentParticipant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_participant1',
        verbose_name="شرکت‌کننده 1",
    )
    participant2 = models.ForeignKey(
        TournamentParticipant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matches_as_participant2',
        verbose_name="شرکت‌کننده 2",
    )
    winner = models.ForeignKey(
        TournamentParticipant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_tournament_matches',
        verbose_name="برنده",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "بازی تورنومنت"
        verbose_name_plural = "بازی‌های تورنومنت"
        ordering = ['round_number', 'match_number', 'id']
        unique_together = ['tournament', 'round_number', 'match_number']

    def __str__(self):
        return f"{self.tournament.name} | دور {self.round_number} | بازی {self.match_number}"


class DailyReport(models.Model):
    """مدل گزارش روزانه"""
    gamenet = models.ForeignKey(GameNet, on_delete=models.CASCADE, related_name='reports', verbose_name="گیم‌نت")
    date = models.DateField(verbose_name="تاریخ")
    total_sessions = models.PositiveIntegerField(default=0, verbose_name="تعداد جلسات")
    total_revenue = models.DecimalField(max_digits=12, decimal_places=0, default=0, verbose_name="درآمد کل")
    total_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="ساعت کل")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "گزارش روزانه"
        verbose_name_plural = "گزارش‌های روزانه"
        ordering = ['-date']
        unique_together = ['gamenet', 'date']

    def __str__(self):
        return f"گزارش {self.date} - {self.gamenet.name}"


# ==================== Buffet Models ====================

class ProductCategory(models.Model):
    """دسته‌بندی محصولات بوفه"""
    gamenet = models.ForeignKey(GameNet, on_delete=models.CASCADE, related_name='product_categories', verbose_name="گیم‌نت")
    name = models.CharField(max_length=100, verbose_name="نام دسته")
    icon = models.CharField(max_length=50, blank=True, default='', verbose_name="آیکون")
    image = models.ImageField(upload_to='categories/', blank=True, null=True, verbose_name="تصویر")
    color = models.CharField(max_length=20, default='#7c3aed', verbose_name="رنگ")
    order = models.PositiveIntegerField(default=0, verbose_name="ترتیب")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "دسته‌بندی محصول"
        verbose_name_plural = "دسته‌بندی محصولات"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name
    
    @property
    def display_icon(self):
        """نمایش آیکون یا تصویر"""
        if self.image:
            return None  # Use image instead
        return self.icon if self.icon else 'fas fa-box'


class Product(models.Model):
    """محصولات بوفه"""
    gamenet = models.ForeignKey(GameNet, on_delete=models.CASCADE, related_name='products', verbose_name="گیم‌نت")
    category = models.ForeignKey(ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', verbose_name="دسته‌بندی")
    name = models.CharField(max_length=100, verbose_name="نام محصول")
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="قیمت (تومان)")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=0, default=0, blank=True, null=True, verbose_name="قیمت خرید (تومان)")
    sale_price = models.DecimalField(max_digits=10, decimal_places=0, default=0, blank=True, null=True, verbose_name="قیمت عرضه (تومان)")
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="تصویر")
    description = models.TextField(blank=True, verbose_name="توضیحات")
    stock = models.PositiveIntegerField(default=0, verbose_name="موجودی")
    is_available = models.BooleanField(default=True, verbose_name="موجود")
    is_active = models.BooleanField(default=True, verbose_name="فعال")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"
        ordering = ['category__order', 'name']

    def __str__(self):
        display_price = self.sale_price or self.price
        return f"{self.name} - {display_price:,} تومان"


class Order(models.Model):
    """سفارشات بوفه"""
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('preparing', 'در حال آماده‌سازی'),
        ('ready', 'آماده'),
        ('delivered', 'تحویل داده شده'),
        ('cancelled', 'لغو شده'),
    ]
    
    gamenet = models.ForeignKey(GameNet, on_delete=models.CASCADE, related_name='orders', verbose_name="گیم‌نت")
    session = models.ForeignKey('Session', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name="جلسه")
    device = models.ForeignKey('Device', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="دستگاه")
    customer_name = models.CharField(max_length=100, blank=True, verbose_name="نام مشتری")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="وضعیت")
    total_amount = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="مبلغ کل")
    notes = models.TextField(blank=True, verbose_name="یادداشت")
    is_paid = models.BooleanField(default=False, verbose_name="پرداخت شده")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "سفارش"
        verbose_name_plural = "سفارشات"
        ordering = ['-created_at']

    def __str__(self):
        return f"سفارش #{self.id} - {self.total_amount:,} تومان"

    def calculate_total(self):
        """محاسبه مجموع سفارش"""
        total = sum(item.total_price for item in self.items.all())
        self.total_amount = total
        self.save()
        return total


class OrderItem(models.Model):
    """آیتم‌های سفارش"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="سفارش")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="محصول")
    quantity = models.PositiveIntegerField(default=1, verbose_name="تعداد")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name="قیمت خرید")
    unit_price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="قیمت واحد")
    total_price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="قیمت کل")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "آیتم سفارش"
        verbose_name_plural = "آیتم‌های سفارش"

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
