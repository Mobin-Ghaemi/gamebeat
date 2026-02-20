from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
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
            'entry_fee': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'هزینه ورودی (تومان)'}),
            'prize_pool': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'جایزه کل (تومان)'}),
            'max_participants': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'حداکثر شرکت‌کنندگان'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'visibility': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-file'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.gamenet = kwargs.pop('gamenet', None)
        super().__init__(*args, **kwargs)
        if self.gamenet:
            self.fields['game'].queryset = Game.objects.filter(gamenet=self.gamenet)
        self.fields['end_date'].required = False

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
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
