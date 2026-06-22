from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from .models import Subscription, UserProfile
from django.urls import reverse

def _get_community_data(user):
    """اطلاعات community کاربر را برای داشبورد account برمی‌گردونه"""
    try:
        from community.models import GamerProfile, Post, PostLike, Follow
        profile = GamerProfile.objects.filter(user=user).first()
        posts = Post.objects.filter(author=user).select_related(
            'author__gamer_profile'
        ).prefetch_related('likes', 'comments').order_by('-created_at')[:12]
        liked_ids = set(PostLike.objects.filter(user=user).values_list('post_id', flat=True))
        followers_count  = Follow.objects.filter(following=user).count()
        following_count  = Follow.objects.filter(follower=user).count()
        posts_count      = Post.objects.filter(author=user).count()
        return {
            'gamer_profile': profile,
            'recent_posts': posts,
            'liked_ids': liked_ids,
            'followers_count': followers_count,
            'following_count': following_count,
            'posts_count': posts_count,
        }
    except Exception:
        return {}


def home(request):
    """صفحه اصلی سایت"""
    return render(request, 'account/home.html')


def register(request):
    """ثبت نام کاربر جدید"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            login(request, user)
            messages.success(request, 'حساب کاربری شما با موفقیت ایجاد شد!')
            return redirect(reverse('community:onboarding'))
    else:
        form = UserCreationForm()
    return render(request, 'account/register.html', {'form': form})


def user_login(request):
    """ورود کاربر"""
    next_url = request.POST.get('next') or request.GET.get('next', '')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                from django.utils.http import url_has_allowed_host_and_scheme
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                return redirect(reverse('community:feed'))
    else:
        form = AuthenticationForm()
    return render(request, 'account/login.html', {'form': form, 'next': next_url})


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
        'has_active_gamenet': gamenet_subscription and not gamenet_subscription.is_expired,
        **_get_community_data(request.user),
    }
    return render(request, 'account/dashboard.html', context)


@login_required
def purchase_subscription(request, service_type):
    """خرید اشتراک"""
    if service_type not in ['gamenet']:
        messages.error(request, 'خدمت مورد نظر در دسترس نیست!')
        return redirect('account:dashboard')
    if request.method == 'POST':
        duration = request.POST.get('duration')
        if duration not in ['1_month', '3_months', '6_months', '1_year']:
            messages.error(request, 'مدت زمان انتخابی معتبر نیست!')
            return redirect('account:purchase_subscription', service_type=service_type)
        duration_map = {'1_month': 30, '3_months': 90, '6_months': 180, '1_year': 365}
        end_date = timezone.now() + timedelta(days=duration_map[duration])
        subscription = Subscription.objects.create(
            user=request.user, service_type=service_type,
            duration=duration, end_date=end_date)
        messages.success(request, f'اشتراک {subscription.get_service_type_display()} با موفقیت فعال شد!')
        return redirect('account:dashboard')
    return render(request, 'account/purchase_subscription.html', {'service_type': service_type})


@login_required
def profile(request):
    """ریدایرکت به پروفایل community"""
    return redirect(reverse('community:profile', kwargs={'username': request.user.username}))


def pricing(request):
    """صفحه قیمت‌گذاری"""
    return render(request, 'gamenet/pricing.html')
