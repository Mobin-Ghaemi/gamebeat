from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count
from django.utils.text import slugify
from decimal import Decimal
from datetime import timedelta
import json

from .models import (
    Device, Game, Session, Tournament, TournamentParticipant, 
    DailyReport, GameNet
)
from .forms import (
    DeviceForm, GameForm, StartSessionForm, TournamentForm, 
    ParticipantForm, GameNetForm
)
from .decorators import gamenet_subscription_required
from account.models import Subscription


# ==================== GameNet Dashboard ====================

@gamenet_subscription_required
def dashboard(request):
    """داشبورد اصلی GameNet"""
    gamenets = GameNet.objects.filter(owner=request.user)
    
    # اگر کاربر GameNet نداشت، یکی برایش ایجاد کن
    if not gamenets.exists():
        gamenet = GameNet.objects.create(
            name=f"GameNet {request.user.username}",
            owner=request.user,
            slug=slugify(f"gamenet-{request.user.username}", allow_unicode=True),
            is_active=True
        )
        gamenets = [gamenet]
    
    return render(request, 'gamenet/dashboard.html', {
        'gamenets': gamenets,
        'subscription': request.gamenet_subscription
    })


# ==================== GameNet Panel Views ====================

def get_gamenet_or_404(request, gamenet_slug):
    """دریافت گیم‌نت با بررسی دسترسی"""
    gamenet = get_object_or_404(GameNet, slug=gamenet_slug, owner=request.user)
    if not gamenet.is_subscription_active:
        messages.warning(request, 'اشتراک شما منقضی شده است. لطفاً تمدید کنید.')
        return None, redirect('gamenet:buy_subscription', gamenet_id=gamenet.id)
    return gamenet, None


@login_required
def panel_dashboard(request, gamenet_slug):
    """داشبورد پنل گیم‌نت"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    devices = gamenet.devices.all()
    active_sessions = Session.objects.filter(
        device__gamenet=gamenet,
        status='active'
    )
    
    # آمار روز
    today = timezone.now().date()
    today_sessions = Session.objects.filter(
        device__gamenet=gamenet,
        start_time__date=today,
        status='completed'
    )
    today_revenue = today_sessions.aggregate(total=Sum('total_cost'))['total'] or 0
    today_count = today_sessions.count()
    
    # مسابقات آینده
    upcoming_tournaments = gamenet.tournaments.filter(
        status__in=['upcoming', 'ongoing']
    )[:5]
    
    context = {
        'gamenet': gamenet,
        'devices': devices,
        'active_sessions': active_sessions,
        'active_count': active_sessions.count(),
        'available_count': devices.filter(status='available').count(),
        'today_revenue': today_revenue,
        'today_count': today_count,
        'upcoming_tournaments': upcoming_tournaments,
    }
    return render(request, 'gamenet/panel/dashboard.html', context)


# ==================== Device Views ====================

@login_required
def device_list(request, gamenet_slug):
    """لیست دستگاه‌ها"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    devices = gamenet.devices.all()
    return render(request, 'gamenet/panel/device_list.html', {
        'gamenet': gamenet,
        'devices': devices
    })


@login_required
def device_create(request, gamenet_slug):
    """ایجاد دستگاه جدید"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        form = DeviceForm(request.POST, gamenet=gamenet)
        if form.is_valid():
            device = form.save(commit=False)
            device.gamenet = gamenet
            device.save()
            form.save_m2m()
            messages.success(request, 'دستگاه با موفقیت اضافه شد!')
            return redirect('gamenet:device_list', gamenet_slug=gamenet.slug)
    else:
        form = DeviceForm(gamenet=gamenet)
    return render(request, 'gamenet/panel/device_form.html', {
        'gamenet': gamenet,
        'form': form,
        'title': 'افزودن دستگاه جدید'
    })


@login_required
def device_edit(request, gamenet_slug, pk):
    """ویرایش دستگاه"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    device = get_object_or_404(Device, pk=pk, gamenet=gamenet)
    if request.method == 'POST':
        form = DeviceForm(request.POST, instance=device, gamenet=gamenet)
        if form.is_valid():
            form.save()
            messages.success(request, 'دستگاه با موفقیت ویرایش شد!')
            return redirect('gamenet:device_list', gamenet_slug=gamenet.slug)
    else:
        form = DeviceForm(instance=device, gamenet=gamenet)
    return render(request, 'gamenet/panel/device_form.html', {
        'gamenet': gamenet,
        'form': form,
        'title': 'ویرایش دستگاه',
        'device': device
    })


@login_required
def device_delete(request, gamenet_slug, pk):
    """حذف دستگاه"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    device = get_object_or_404(Device, pk=pk, gamenet=gamenet)
    if request.method == 'POST':
        device.delete()
        messages.success(request, 'دستگاه حذف شد!')
        return redirect('gamenet:device_list', gamenet_slug=gamenet.slug)
    return render(request, 'gamenet/panel/device_confirm_delete.html', {
        'gamenet': gamenet,
        'device': device
    })


# ==================== Session Views ====================

@login_required
def start_session(request, gamenet_slug, device_id):
    """شروع جلسه برای دستگاه"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    device = get_object_or_404(Device, pk=device_id, gamenet=gamenet)
    
    if device.status != 'available':
        messages.error(request, 'این دستگاه در حال حاضر آزاد نیست!')
        return redirect('gamenet:panel_dashboard', gamenet_slug=gamenet.slug)
    
    if request.method == 'POST':
        form = StartSessionForm(request.POST)
        if form.is_valid():
            session = Session.objects.create(
                device=device,
                customer_name=form.cleaned_data['customer_name'],
                customer_phone=form.cleaned_data['customer_phone'],
                start_time=timezone.now(),
                hourly_rate=device.hourly_rate,
                notes=form.cleaned_data['notes']
            )
            device.status = 'occupied'
            device.save()
            messages.success(request, f'جلسه برای دستگاه #{device.number} شروع شد!')
            return redirect('gamenet:panel_dashboard', gamenet_slug=gamenet.slug)
    else:
        form = StartSessionForm()
    
    return render(request, 'gamenet/panel/start_session.html', {
        'gamenet': gamenet,
        'form': form,
        'device': device
    })


@login_required
def stop_session(request, gamenet_slug, session_id):
    """پایان جلسه"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet)
    
    if session.status != 'active':
        messages.error(request, 'این جلسه قبلاً پایان یافته است!')
        return redirect('gamenet:panel_dashboard', gamenet_slug=gamenet.slug)
    
    session.end_time = timezone.now()
    session.status = 'completed'
    session.total_cost = session.calculate_cost()
    session.save()
    
    session.device.status = 'available'
    session.device.save()
    
    messages.success(request, f'جلسه پایان یافت. هزینه: {session.total_cost:,.0f} تومان')
    return redirect('gamenet:session_detail', gamenet_slug=gamenet.slug, session_id=session.id)


@login_required
def session_detail(request, gamenet_slug, session_id):
    """جزئیات جلسه"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet)
    return render(request, 'gamenet/panel/session_detail.html', {
        'gamenet': gamenet,
        'session': session
    })


@login_required
def session_list(request, gamenet_slug):
    """لیست جلسات"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    sessions = Session.objects.filter(device__gamenet=gamenet)[:50]
    return render(request, 'gamenet/panel/session_list.html', {
        'gamenet': gamenet,
        'sessions': sessions
    })


@require_POST
@login_required
def get_session_time(request, gamenet_slug):
    """API برای دریافت زمان فعلی جلسه"""
    gamenet = get_object_or_404(GameNet, slug=gamenet_slug, owner=request.user)
    session_id = request.POST.get('session_id')
    session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet)
    
    if session.status != 'active':
        return JsonResponse({'error': 'جلسه فعال نیست'}, status=400)
    
    now = timezone.now()
    delta = now - session.start_time
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    # محاسبه هزینه فعلی
    import math
    minutes_total = total_seconds / 60
    hours_decimal = Decimal(minutes_total) / Decimal(60)
    hours_rounded = math.ceil(float(hours_decimal) * 2) / 2
    current_cost = session.hourly_rate * Decimal(hours_rounded)
    
    return JsonResponse({
        'hours': hours,
        'minutes': minutes,
        'seconds': seconds,
        'total_seconds': total_seconds,
        'current_cost': float(current_cost),
        'formatted_time': f'{hours:02d}:{minutes:02d}:{seconds:02d}',
        'formatted_cost': f'{current_cost:,.0f}'
    })


# ==================== Game Views ====================

@login_required
def game_list(request, gamenet_slug):
    """لیست بازی‌ها"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    games = gamenet.games.all()
    return render(request, 'gamenet/panel/game_list.html', {
        'gamenet': gamenet,
        'games': games
    })


@login_required
def game_create(request, gamenet_slug):
    """ایجاد بازی جدید"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    if request.method == 'POST':
        form = GameForm(request.POST, request.FILES)
        if form.is_valid():
            game = form.save(commit=False)
            game.gamenet = gamenet
            game.save()
            messages.success(request, 'بازی با موفقیت اضافه شد!')
            return redirect('gamenet:game_list', gamenet_slug=gamenet.slug)
    else:
        form = GameForm()
    return render(request, 'gamenet/panel/game_form.html', {
        'gamenet': gamenet,
        'form': form,
        'title': 'افزودن بازی جدید'
    })


# ==================== Reports ====================

@login_required
def reports(request, gamenet_slug):
    """صفحه گزارشات"""
    gamenet, redirect_response = get_gamenet_or_404(request, gamenet_slug)
    if redirect_response:
        return redirect_response
    
    today = timezone.now().date()
    
    # گزارش روزانه
    daily_sessions = Session.objects.filter(
        device__gamenet=gamenet,
        start_time__date=today,
        status='completed'
    )
    daily_revenue = daily_sessions.aggregate(total=Sum('total_cost'))['total'] or 0
    
    # گزارش هفتگی
    week_ago = today - timedelta(days=7)
    weekly_sessions = Session.objects.filter(
        device__gamenet=gamenet,
        start_time__date__gte=week_ago,
        status='completed'
    )
    weekly_revenue = weekly_sessions.aggregate(total=Sum('total_cost'))['total'] or 0
    
    # پر استفاده‌ترین دستگاه‌ها
    top_devices = gamenet.devices.annotate(
        session_count=Count('sessions')
    ).order_by('-session_count')[:5]
    
    context = {
        'gamenet': gamenet,
        'daily_revenue': daily_revenue,
        'daily_count': daily_sessions.count(),
        'weekly_revenue': weekly_revenue,
        'weekly_count': weekly_sessions.count(),
        'top_devices': top_devices,
    }
    return render(request, 'gamenet/panel/reports.html', context)