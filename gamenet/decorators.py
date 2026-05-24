from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from functools import wraps
from account.models import Subscription


def gamenet_subscription_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        active_subscription = Subscription.objects.filter(
            user=request.user, service_type='gamenet', is_active=True).first()
        if not active_subscription or active_subscription.is_expired:
            messages.error(request, 'برای استفاده از GameNet، ابتدا اشتراک تهیه کنید!')
            return redirect('account:purchase_subscription', service_type='gamenet')
        request.gamenet_subscription = active_subscription
        return view_func(request, *args, **kwargs)
    return wrapper


def gamenet_subscription_required_api(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'لطفا ابتدا وارد شوید'}, status=401)
        active_subscription = Subscription.objects.filter(
            user=request.user, service_type='gamenet', is_active=True).first()
        if not active_subscription or active_subscription.is_expired:
            return JsonResponse({'success': False, 'error': 'برای استفاده از GameNet، ابتدا اشتراک تهیه کنید!'}, status=403)
        request.gamenet_subscription = active_subscription
        return view_func(request, *args, **kwargs)
    return wrapper
