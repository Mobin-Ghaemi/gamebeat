from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
import re
from .models import Device, Game, Session, Tournament, TournamentParticipant, GameNet, Product, ProductCategory


class UserRegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'class': 'form-input', 'placeholder': 'نام کاربری'})
        self.fields['email'].widget.attrs.update({'class': 'form-input', 'placeholder': 'ایمیل'})
        self.fields['password1'].widget.attrs.update({'class': 'form-input', 'placeholder': 'رمز عبور'})
        self.fields['password2'].widget.attrs.update({'class': 'form-input', 'placeholder': 'تکرار رمز عبور'})


class GameNetForm(forms.ModelForm):
    class Meta:
        model = GameNet
        fields = ['name', 'address', 'phone', 'logo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'نام گیم‌نت شما'}),
            'address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'آدرس گیم‌نت'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'شماره تماس'}),
            'logo': forms.FileInput(attrs={'class': 'form-file'}),
        }


class GameNetSettingsForm(forms.ModelForm):
    """فرم تنظیمات گیم‌نت"""
    class Meta:
        model = GameNet
        fields = ['name', 'description', 'address', 'phone', 'logo', 'extra_controller_price']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': 'نام گیم‌نت شما'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-textarea', 
                'rows': 4, 
                'placeholder': 'توضیحات درباره گیم‌نت شما...'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-textarea', 
                'rows': 2, 
                'placeholder': 'آدرس گیم‌نت'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input', 
                'placeholder': 'شماره تماس'
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-file',
                'accept': 'image/*'
            }),
            'extra_controller_price': forms.NumberInput(attrs={
                'class': 'form-input', 
                'placeholder': 'قیمت دسته اضافی (تومان در ساعت)'
            }),
        }
        labels = {
            'name': 'نام گیم‌نت',
            'description': 'توضیحات',
            'address': 'آدرس',
            'phone': 'شماره تماس',
            'logo': 'لوگو / تصویر',
            'extra_controller_price': 'قیمت دسته اضافی (تومان/ساعت)',
        }


class GameForm(forms.ModelForm):
    class Meta:
        model = Game
        fields = ['name', 'description', 'genre', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'نام بازی'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'توضیحات بازی'}),
            'genre': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'ژانر (مثلاً: اکشن، ورزشی)'}),
            'image': forms.FileInput(attrs={'class': 'form-file'}),
        }


class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ['number', 'name', 'device_type', 'hourly_rate', 'games', 'specs', 'status']
        widgets = {
            'number': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'شماره دستگاه'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'نام دستگاه'}),
            'device_type': forms.Select(attrs={'class': 'form-select'}),
            'hourly_rate': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'قیمت ساعتی (تومان)'}),
            'games': forms.SelectMultiple(attrs={'class': 'form-select-multiple'}),
            'specs': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'مشخصات فنی (CPU, GPU, RAM, ...)'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.gamenet = kwargs.pop('gamenet', None)
        super().__init__(*args, **kwargs)
        if self.gamenet:
            self.fields['games'].queryset = Game.objects.filter(gamenet=self.gamenet)


class StartSessionForm(forms.Form):
    customer_name = forms.CharField(
        max_length=100, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'نام مشتری (اختیاری)'})
    )
    customer_phone = forms.CharField(
        max_length=15, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'شماره تلفن (اختیاری)'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'یادداشت'})
    )


class TournamentForm(forms.ModelForm):
    class Meta:
        model = Tournament
        fields = ['name', 'game', 'description', 'start_date', 'end_date', 'entry_fee', 'prize_pool', 'max_participants', 'status', 'visibility', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'نام مسابقه'}),
            'game': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'توضیحات مسابقه'}),
            'start_date': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
            'entry_fee': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'هزینه ورودی (تومان)'}),
            'prize_pool': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'جایزه کل (تومان)'}),
            'max_participants': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'حداکثر شرکت‌کنندگان'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'visibility': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-file'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.gamenet = kwargs.pop('gamenet', None)
        incoming_data = args[0] if args and args[0] is not None else kwargs.get('data')
        if incoming_data is not None:
            data = incoming_data.copy()
            for field_name in ('entry_fee', 'prize_pool', 'max_participants'):
                raw_value = data.get(field_name, '')
                data[field_name] = self._normalize_numeric_text(raw_value)
            for field_name in ('start_date', 'end_date'):
                raw_value = data.get(field_name, '')
                data[field_name] = self._normalize_date_text(raw_value)
            if args and args[0] is not None:
                args = (data, *args[1:])
            else:
                kwargs['data'] = data
        super().__init__(*args, **kwargs)
        if self.gamenet:
            self.fields['game'].queryset = Game.objects.filter(gamenet=self.gamenet)
        self.fields['end_date'].required = False

    @staticmethod
    def _normalize_numeric_text(raw_value):
        if raw_value is None:
            return ''
        value = str(raw_value).strip()
        value = TournamentForm._normalize_digits_only(value)
        value = value.replace('٬', '').replace(',', '')
        return value

    @staticmethod
    def _normalize_digits_only(raw_value):
        if raw_value is None:
            return ''
        value = str(raw_value).strip()
        value = value.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789'))
        value = value.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
        return value

    @staticmethod
    def _jalali_to_gregorian(j_year, j_month, j_day):
        if not (1 <= j_month <= 12 and 1 <= j_day <= 31):
            raise ValueError('Invalid Jalali date')

        j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
        if j_month <= 6:
            max_day = 31
        elif j_month <= 11:
            max_day = 30
        else:
            max_day = 30
        if j_day > max_day:
            raise ValueError('Invalid Jalali day for month')

        jy = j_year - 979
        jm = j_month - 1
        jd = j_day - 1

        j_day_no = 365 * jy + (jy // 33) * 8 + ((jy % 33 + 3) // 4)
        for i in range(jm):
            j_day_no += j_days_in_month[i]
        j_day_no += jd

        g_day_no = j_day_no + 79
        gy = 1600 + 400 * (g_day_no // 146097)
        g_day_no %= 146097

        leap = True
        if g_day_no >= 36525:
            g_day_no -= 1
            gy += 100 * (g_day_no // 36524)
            g_day_no %= 36524
            if g_day_no >= 365:
                g_day_no += 1
            else:
                leap = False

        gy += 4 * (g_day_no // 1461)
        g_day_no %= 1461

        if g_day_no >= 366:
            leap = False
            g_day_no -= 1
            gy += g_day_no // 365
            g_day_no %= 365

        gd = g_day_no + 1
        g_days_in_month = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        gm = 1
        while gm <= 12 and gd > g_days_in_month[gm]:
            gd -= g_days_in_month[gm]
            gm += 1

        return gy, gm, gd

    @classmethod
    def _normalize_date_text(cls, raw_value):
        value = cls._normalize_digits_only(raw_value)
        if not value:
            return ''
        value = value.replace('/', '-')

        match = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?$', value)
        if not match:
            return value

        year_s, month_s, day_s, hour_s, minute_s, second_s = match.groups()
        year_i = int(year_s)
        month_i = int(month_s)
        day_i = int(day_s)

        if 1300 <= year_i <= 1600:
            try:
                year_i, month_i, day_i = cls._jalali_to_gregorian(year_i, month_i, day_i)
            except ValueError:
                return value

        if hour_s is None:
            return f'{year_i:04d}-{month_i:02d}-{day_i:02d}'

        hour_i = int(hour_s)
        minute_i = int(minute_s or 0)
        second_i = int(second_s or 0)
        return f'{year_i:04d}-{month_i:02d}-{day_i:02d} {hour_i:02d}:{minute_i:02d}:{second_i:02d}'

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        today = timezone.localdate()
        if start_date:
            start_local_date = timezone.localtime(start_date).date() if timezone.is_aware(start_date) else start_date.date()
            if start_local_date < today:
                self.add_error('start_date', 'این تاریخ برای گذشته است. تاریخ شروع باید امروز یا بعد از امروز باشد.')

        if end_date:
            end_local_date = timezone.localtime(end_date).date() if timezone.is_aware(end_date) else end_date.date()
            if end_local_date < today:
                self.add_error('end_date', 'این تاریخ برای گذشته است. تاریخ پایان باید امروز یا بعد از امروز باشد.')

        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'تاریخ پایان نمی‌تواند قبل از تاریخ شروع باشد.')
        return cleaned_data


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = TournamentParticipant
        fields = ['name', 'phone', 'gamer_tag']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'نام و نام خانوادگی'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'شماره تلفن'}),
            'gamer_tag': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'آیدی گیمری (اختیاری)'}),
        }


# ==================== Buffet Forms ====================

class ProductCategoryForm(forms.ModelForm):
    ICON_CHOICES = [
        ('fas fa-coffee', '☕ نوشیدنی گرم'),
        ('fas fa-glass-whiskey', '🥤 نوشیدنی سرد'),
        ('fas fa-cookie-bite', '🍪 تنقلات'),
        ('fas fa-hamburger', '🍔 فست فود'),
        ('fas fa-pizza-slice', '🍕 پیتزا'),
        ('fas fa-ice-cream', '🍨 بستنی'),
        ('fas fa-candy-cane', '🍬 شیرینی'),
        ('fas fa-utensils', '🍽️ غذای اصلی'),
        ('fas fa-box', '📦 سایر'),
    ]
    
    COLOR_CHOICES = [
        ('#7c3aed', '💜 بنفش'),
        ('#ec4899', '💖 صورتی'),
        ('#3b82f6', '💙 آبی'),
        ('#10b981', '💚 سبز'),
        ('#f59e0b', '🧡 نارنجی'),
        ('#ef4444', '❤️ قرمز'),
        ('#6366f1', '💜 نیلی'),
        ('#14b8a6', '💎 فیروزه‌ای'),
    ]
    
    icon = forms.ChoiceField(choices=ICON_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    color = forms.ChoiceField(choices=COLOR_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    
    class Meta:
        model = ProductCategory
        fields = ['name', 'icon', 'color', 'order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'نام دسته‌بندی'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'ترتیب نمایش'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['category', 'name', 'purchase_price', 'sale_price', 'image', 'description', 'stock', 'is_available', 'is_active']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'نام محصول'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'قیمت خرید (تومان)', 'min': '0'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'قیمت عرضه (تومان)', 'min': '0'}),
            'image': forms.FileInput(attrs={'class': 'form-file', 'accept': 'image/*'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'توضیحات محصول'}),
            'stock': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'موجودی'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.gamenet = kwargs.pop('gamenet', None)
        super().__init__(*args, **kwargs)
        if self.gamenet:
            self.fields['category'].queryset = ProductCategory.objects.filter(gamenet=self.gamenet, is_active=True)
        # قیمت‌ها اختیاری هستند — اگر خالی بمانند، default استفاده می‌شود
        self.fields['purchase_price'].required = False
        self.fields['sale_price'].required = False

    def save(self, commit=True):
        product = super().save(commit=False)
        # فیلد price قدیمی را از sale_price پر کن
        if product.sale_price:
            product.price = product.sale_price
        elif product.purchase_price:
            product.price = product.purchase_price
        else:
            product.price = 0
        if commit:
            product.save()
        return product
