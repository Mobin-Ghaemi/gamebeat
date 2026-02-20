from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import Subscription, UserProfile


def home(request):
    """صفحه اصلی سایت"""
    return render(request, 'account/home.html')


def register(request):
    """ثبت نام کاربر جدید"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # ایجاد پروفایل کاربر
            UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(request, 'حساب کاربری شما با موفقیت ایجاد شد!')
            return redirect('account:dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'account/register.html', {'form': form})


def user_login(request):
    """ورود کاربر"""
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('account:dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'account/login.html', {'form': form})


def user_logout(request):
    """خروج کاربر"""
    logout(request)
    messages.success(request, 'با موفقیت خارج شدید!')
    return redirect('account:login')


@login_required
def dashboard(request):
    """داشبورد کاربری"""
    user_subscriptions = Subscription.objects.filter(user=request.user)
    gamenet_subscription = user_subscriptions.filter(service_type='gamenet', is_active=True).first()
    
    context = {
        'user_subscriptions': user_subscriptions,
        'gamenet_subscription': gamenet_subscription,
        'has_active_gamenet': gamenet_subscription and not gamenet_subscription.is_expired
    }
    return render(request, 'account/dashboard.html', context)


@login_required
def purchase_subscription(request, service_type):
    """خرید اشتراک"""
    if service_type not in ['gamenet']:  # فعلا فقط gamenet
        messages.error(request, 'خدمت مورد نظر در دسترس نیست!')
        return redirect('account:dashboard')
    
    if request.method == 'POST':
        duration = request.POST.get('duration')
        
        if duration not in ['1_month', '3_months', '6_months', '1_year']:
            messages.error(request, 'مدت زمان انتخابی معتبر نیست!')
            return redirect('account:purchase_subscription', service_type=service_type)
        
        # محاسبه تاریخ پایان
        duration_map = {
            '1_month': 30,
            '3_months': 90,
            '6_months': 180,
            '1_year': 365,
        }
        
        end_date = timezone.now() + timedelta(days=duration_map[duration])
        
        # ایجاد اشتراک جدید
        subscription = Subscription.objects.create(
            user=request.user,
            service_type=service_type,
            duration=duration,
            end_date=end_date
        )
        
        messages.success(request, f'اشتراک {subscription.get_service_type_display()} با موفقیت فعال شد!')
        return redirect('account:dashboard')
    
    return render(request, 'account/purchase_subscription.html', {'service_type': service_type})


@login_required
def profile(request):
    """پروفایل کاربر"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # به‌روزرسانی اطلاعات پروفایل
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        
        profile.phone = request.POST.get('phone', '')
        if 'profile_image' in request.FILES:
            profile.profile_image = request.FILES['profile_image']
        profile.save()
        
        messages.success(request, 'پروفایل شما با موفقیت به‌روزرسانی شد!')
        return redirect('account:profile')
    
    return render(request, 'account/profile.html', {'profile': profile})


def pricing(request):
    """صفحه قیمت‌گذاری"""
    return render(request, 'gamenet/pricing.html')
