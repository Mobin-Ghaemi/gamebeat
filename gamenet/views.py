from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count, F, DecimalField, ExpressionWrapper, Prefetch, Value, CharField
from django.db import models, transaction
from django.db.models.functions import Coalesce
from django.utils.text import slugify
from contextlib import nullcontext
from decimal import Decimal
from datetime import timedelta
from collections import OrderedDict
import random
import json

from .models import (
    Device, Game, Session, Tournament, TournamentParticipant, 
    TournamentMatch, DailyReport, GameNet, Product, ProductCategory, Order, OrderItem
)
from .forms import (
    DeviceForm, GameForm, StartSessionForm, TournamentForm, 
    ParticipantForm, GameNetForm, GameNetSettingsForm, ProductForm, ProductCategoryForm
)
from .decorators import gamenet_subscription_required, gamenet_subscription_required_api
from account.models import Subscription


# ==================== GameNet Dashboard ====================

@gamenet_subscription_required
def dashboard(request):
    """داشبورد اصلی GameNet"""
    gamenet, created = GameNet.objects.get_or_create(
        owner=request.user,
        defaults={
            'name': f'GameNet {request.user.username}',
            'slug': slugify(f'gamenet-{request.user.username}', allow_unicode=True),
            'is_active': True
        }
    )
    
    # آمار کلی
    total_devices = Device.objects.filter(gamenet=gamenet).count()
    active_sessions = Session.objects.filter(device__gamenet=gamenet, is_active=True).count()
    available_devices = Device.objects.filter(gamenet=gamenet, status='available').count()
    today_sessions = Session.objects.filter(
        device__gamenet=gamenet, 
        start_time__date=timezone.now().date()
    ).count()
    
    # درآمد امروز
    today_income = Session.objects.filter(
        device__gamenet=gamenet,
        start_time__date=timezone.now().date(),
        is_active=False
    ).aggregate(total=Sum('total_cost'))['total'] or Decimal('0')
    
    # جلسات فعال
    active_sessions_list = Session.objects.filter(
        device__gamenet=gamenet, 
        is_active=True
    ).order_by('start_time')
    
    # دستگاه‌ها
    devices = Device.objects.filter(gamenet=gamenet).prefetch_related('sessions')
    
    # ساخت دیتای جلسات فعال برای جاوااسکریپت
    active_sessions_data = {}
    for session in active_sessions_list:
        active_sessions_data[session.device_id] = {
            'session_id': session.id,
            'start_time': session.start_time.isoformat(),
            'hourly_rate': float(session.hourly_rate),
            'extra_controllers': session.extra_controllers,
            'controller_rate': float(session.extra_controller_rate),
        }
    
    context = {
        'gamenet': gamenet,
        'total_devices': total_devices,
        'active_sessions': active_sessions,
        'available_devices': available_devices,
        'today_sessions': today_sessions,
        'today_income': today_income,
        'active_sessions_list': active_sessions_list,
        'active_sessions_json': json.dumps(active_sessions_data),
        'devices': devices,
        'subscription': request.gamenet_subscription
    }
    
    return render(request, 'gamenet/dashboard.html', context)


# ==================== GameNet Settings ====================

@gamenet_subscription_required
def gamenet_settings(request):
    """تنظیمات گیم‌نت"""
    from .models import GameNetImage
    
    gamenet = get_object_or_404(GameNet, owner=request.user)
    images = GameNetImage.objects.filter(gamenet=gamenet)
    
    if request.method == 'POST':
        action = request.POST.get('action', 'save_settings')
        
        if action == 'save_settings':
            form = GameNetSettingsForm(request.POST, request.FILES, instance=gamenet)
            if form.is_valid():
                form.save()
                messages.success(request, 'تنظیمات گیم‌نت با موفقیت ذخیره شد!')
                return redirect('gamenet:gamenet_settings')
            else:
                messages.error(request, 'خطا در ذخیره تنظیمات. لطفاً فیلدها را بررسی کنید.')
        
        elif action == 'save_pricing':
            extra_controller_price = request.POST.get('extra_controller_price', 0)
            try:
                gamenet.extra_controller_price = Decimal(str(extra_controller_price))
                gamenet.save()
                messages.success(request, 'تنظیمات قیمت‌گذاری با موفقیت ذخیره شد!')
            except:
                messages.error(request, 'خطا در ذخیره قیمت. لطفاً مقدار معتبر وارد کنید.')
            return redirect('gamenet:gamenet_settings')
        
        elif action == 'upload_images':
            uploaded_files = request.FILES.getlist('gallery_images')
            for img in uploaded_files:
                GameNetImage.objects.create(
                    gamenet=gamenet,
                    image=img,
                    order=images.count()
                )
            messages.success(request, f'{len(uploaded_files)} تصویر با موفقیت آپلود شد!')
            return redirect('gamenet:gamenet_settings')
    
    else:
        form = GameNetSettingsForm(instance=gamenet)
    
    return render(request, 'gamenet/gamenet_settings.html', {
        'gamenet': gamenet,
        'form': form,
        'images': images
    })


@require_POST
@gamenet_subscription_required
def delete_gamenet_image(request, image_id):
    """حذف تصویر گالری"""
    from .models import GameNetImage
    
    gamenet = get_object_or_404(GameNet, owner=request.user)
    image = get_object_or_404(GameNetImage, pk=image_id, gamenet=gamenet)
    image.delete()
    
    return JsonResponse({'success': True})


# ==================== Device Views ====================

@gamenet_subscription_required
def device_list(request):
    """لیست دستگاه‌ها"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    devices = Device.objects.filter(gamenet=gamenet)
    return render(request, 'gamenet/device_list.html', {
        'gamenet': gamenet,
        'devices': devices
    })


@gamenet_subscription_required  
def device_create(request):
    """ایجاد دستگاه جدید"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    
    if request.method == 'POST':
        form = DeviceForm(request.POST, gamenet=gamenet)
        if form.is_valid():
            device = form.save(commit=False)
            device.gamenet = gamenet
            device.save()
            form.save_m2m()  # Save many-to-many relationships (games)
            messages.success(request, 'دستگاه جدید با موفقیت اضافه شد!')
            return redirect('gamenet:device_list')
        else:
            messages.error(request, 'خطا در ثبت دستگاه. لطفا اطلاعات را بررسی کنید.')
    else:
        form = DeviceForm(gamenet=gamenet)
    return render(request, 'gamenet/device_form.html', {
        'gamenet': gamenet,
        'form': form,
        'title': 'اضافه کردن دستگاه جدید'
    })


@gamenet_subscription_required
def device_edit(request, pk):
    """ویرایش دستگاه"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    device = get_object_or_404(Device, pk=pk, gamenet=gamenet)
    
    if request.method == 'POST':
        form = DeviceForm(request.POST, instance=device, gamenet=gamenet)
        if form.is_valid():
            form.save()
            messages.success(request, 'دستگاه با موفقیت ویرایش شد!')
            return redirect('gamenet:device_list')
    else:
        form = DeviceForm(instance=device, gamenet=gamenet)
    return render(request, 'gamenet/device_form.html', {
        'gamenet': gamenet,
        'form': form,
        'title': 'ویرایش دستگاه',
        'device': device
    })


@gamenet_subscription_required
def device_delete(request, pk):
    """حذف دستگاه"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    device = get_object_or_404(Device, pk=pk, gamenet=gamenet)
    if request.method == 'POST':
        device.delete()
        messages.success(request, 'دستگاه حذف شد!')
        return redirect('gamenet:device_list')
    return render(request, 'gamenet/device_confirm_delete.html', {
        'gamenet': gamenet,
        'device': device
    })


# ==================== Session Views ====================

@gamenet_subscription_required
def start_session(request, device_id):
    """شروع جلسه برای دستگاه"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    device = get_object_or_404(Device, pk=device_id, gamenet=gamenet)
    
    if device.status != 'available':
        messages.error(request, 'این دستگاه در حال حاضر آزاد نیست!')
        return redirect('gamenet:dashboard')
    
    if request.method == 'POST':
        form = StartSessionForm(request.POST)
        if form.is_valid():
            # ساخت دستی Session چون StartSessionForm یک forms.Form است نه ModelForm
            session = Session.objects.create(
                device=device,
                customer_name=form.cleaned_data.get('customer_name', 'مشتری'),
                customer_phone=form.cleaned_data.get('customer_phone', ''),
                notes=form.cleaned_data.get('notes', ''),
                start_time=timezone.now(),
                hourly_rate=device.hourly_rate,
                extra_controller_rate=gamenet.extra_controller_price,
                is_active=True
            )
            
            device.status = 'occupied'
            device.save()
            
            messages.success(request, f'جلسه برای {device.name} شروع شد!')
            return redirect('gamenet:session_detail', session_id=session.id)
    else:
        form = StartSessionForm()
    
    return render(request, 'gamenet/start_session.html', {
        'gamenet': gamenet,
        'device': device,
        'form': form
    })


@require_POST
@gamenet_subscription_required
def stop_session(request, session_id):
    """پایان جلسه"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet, is_active=True)
    
    session.end_time = timezone.now()
    session.is_active = False
    
    # محاسبه قیمت نهایی
    session.total_cost = session.calculate_cost()
    session.save()
    
    # آزاد کردن دستگاه
    device = session.device
    device.status = 'available'
    device.save()
    
    messages.success(request, f'جلسه {session.customer_name} پایان یافت. مبلغ نهایی: {session.total_cost:,} تومان')
    return redirect('gamenet:dashboard')


@gamenet_subscription_required
def session_detail(request, session_id):
    """جزئیات جلسه"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet)
    return render(request, 'gamenet/session_detail.html', {
        'gamenet': gamenet,
        'session': session
    })


@gamenet_subscription_required
def session_list(request):
    """لیست جلسات"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    try:
        sessions = (
            Session.objects
            .filter(device__gamenet=gamenet)
            .select_related('device')
            .only(
                'id', 'device_id', 'start_time', 'end_time', 'is_active',
                'total_cost', 'hourly_rate', 'customer_name', 'customer_phone'
            )
            .order_by('-start_time')[:500]
        )
    except Exception:
        messages.error(request, 'بارگذاری جلسات با مشکل مواجه شد. لطفاً دوباره تلاش کنید.')
        sessions = Session.objects.none()

    return render(request, 'gamenet/session_list.html', {
        'gamenet': gamenet,
        'sessions': sessions
    })


@require_POST
@gamenet_subscription_required_api
def delete_session_api(request, session_id):
    """حذف جلسه از طریق API"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet)
        
        # حذف جلسه
        session.delete()
        
        return JsonResponse({
            'success': True,
            'message': 'جلسه با موفقیت حذف شد'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ==================== Game Views ====================

@gamenet_subscription_required
def game_list(request):
    """لیست بازی‌ها"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    games = Game.objects.filter(gamenet=gamenet).order_by('-created_at')
    total_games = games.count()
    games_with_image = games.filter(image__isnull=False).exclude(image='').count()
    games_with_genre = games.exclude(genre='').count()
    added_today = games.filter(created_at__date=timezone.localdate()).count()
    genre_counts = list(
        games.exclude(genre='')
        .values('genre')
        .annotate(total=Count('id'))
        .order_by('-total', 'genre')[:8]
    )

    return render(request, 'gamenet/game_list.html', {
        'gamenet': gamenet,
        'games': games,
        'total_games': total_games,
        'games_with_image': games_with_image,
        'games_with_genre': games_with_genre,
        'added_today': added_today,
        'genre_counts': genre_counts,
    })


@gamenet_subscription_required
def game_create(request):
    """ایجاد بازی جدید"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    
    if request.method == 'POST':
        form = GameForm(request.POST, request.FILES)
        if form.is_valid():
            game = form.save(commit=False)
            game.gamenet = gamenet
            game.save()
            messages.success(request, 'بازی جدید اضافه شد!')
            return redirect('gamenet:game_list')
    else:
        form = GameForm()
    return render(request, 'gamenet/game_form.html', {
        'gamenet': gamenet,
        'form': form,
        'title': 'اضافه کردن بازی جدید'
    })


# ==================== Reports ====================

@gamenet_subscription_required
def reports(request):
    """گزارشات"""
    from django.core.paginator import Paginator
    
    gamenet = get_object_or_404(GameNet, owner=request.user)
    today = timezone.now().date()
    
    # گزارش امروز
    today_sessions = Session.objects.filter(
        device__gamenet=gamenet,
        start_time__date=today,
        is_active=False
    )
    today_income = today_sessions.aggregate(total=Sum('total_cost'))['total'] or Decimal('0')
    today_count = today_sessions.count()
    
    # محاسبه ساعات امروز
    today_hours = 0
    for session in today_sessions:
        if session.end_time:
            duration_seconds = (session.end_time - session.start_time).total_seconds()
            today_hours += duration_seconds / 3600
    
    # گزارش هفته جاری
    week_start = today - timedelta(days=today.weekday())
    week_sessions = Session.objects.filter(
        device__gamenet=gamenet,
        start_time__date__gte=week_start,
        is_active=False
    )
    week_income = week_sessions.aggregate(total=Sum('total_cost'))['total'] or Decimal('0')
    week_count = week_sessions.count()
    
    # گزارش ماه جاری
    month_sessions = Session.objects.filter(
        device__gamenet=gamenet,
        start_time__year=today.year,
        start_time__month=today.month,
        is_active=False
    )
    month_income = month_sessions.aggregate(total=Sum('total_cost'))['total'] or Decimal('0')
    month_count = month_sessions.count()
    
    # کل درآمد
    all_sessions = Session.objects.filter(
        device__gamenet=gamenet,
        is_active=False
    )
    total_income = all_sessions.aggregate(total=Sum('total_cost'))['total'] or Decimal('0')
    total_count = all_sessions.count()

    # درآمد ناخالص/خالص (کل) با احتساب بوفه
    order_items_all = OrderItem.objects.filter(order__gamenet=gamenet).exclude(order__status='cancelled')
    buffet_revenue_total = order_items_all.aggregate(total=Sum('total_price'))['total'] or Decimal('0')
    buffet_cost_total = order_items_all.aggregate(
        total=Sum(ExpressionWrapper(F('purchase_price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=0)))
    )['total'] or Decimal('0')
    gross_income_total = total_income + buffet_revenue_total
    net_income_total = total_income + (buffet_revenue_total - buffet_cost_total)
    
    # پراستفاده‌ترین دستگاه‌ها
    top_devices = Device.objects.filter(gamenet=gamenet).annotate(
        session_count=Count('sessions', filter=models.Q(sessions__is_active=False)),
        total_revenue=Sum('sessions__total_cost', filter=models.Q(sessions__is_active=False))
    ).order_by('-session_count')[:5]
    
    # ساعات استفاده امروز به تفکیک دستگاه
    device_hours_today = []
    for device in Device.objects.filter(gamenet=gamenet):
        device_sessions_today = Session.objects.filter(
            device=device,
            start_time__date=today,
            is_active=False
        )
        hours = 0
        for session in device_sessions_today:
            if session.end_time:
                duration_seconds = (session.end_time - session.start_time).total_seconds()
                hours += duration_seconds / 3600
        if hours > 0:
            device_hours_today.append({
                'device': device,
                'hours': hours,
            })
    device_hours_today.sort(key=lambda x: x['hours'], reverse=True)
    
    # درآمد هفته جاری برای نمودار (شنبه تا جمعه)
    persian_days = {
        'Saturday': 'شنبه',
        'Sunday': 'یکشنبه',
        'Monday': 'دوشنبه',
        'Tuesday': 'سه‌شنبه',
        'Wednesday': 'چهارشنبه',
        'Thursday': 'پنجشنبه',
        'Friday': 'جمعه',
    }
    
    # پیدا کردن شنبه این هفته (شروع هفته فارسی)
    # در Python: Monday=0, Tuesday=1, ..., Saturday=5, Sunday=6
    today_weekday = today.weekday()  # 0=Monday, 5=Saturday, 6=Sunday
    
    # محاسبه فاصله تا شنبه
    if today_weekday == 5:  # امروز شنبه است
        days_since_saturday = 0
    elif today_weekday == 6:  # امروز یکشنبه است
        days_since_saturday = 1
    else:  # دوشنبه تا جمعه
        days_since_saturday = today_weekday + 2
    
    week_saturday = today - timedelta(days=days_since_saturday)
    
    # ایجاد لیست روزها از شنبه تا جمعه
    daily_stats = []
    for i in range(7):  # شنبه=0 تا جمعه=6
        day = week_saturday + timedelta(days=i)
        
        day_sessions = Session.objects.filter(
            device__gamenet=gamenet,
            start_time__date=day,
            is_active=False
        )
        day_income = day_sessions.aggregate(total=Sum('total_cost'))['total'] or 0
        day_count = day_sessions.count()
        daily_stats.append({
            'date': day,
            'day_name': persian_days.get(day.strftime('%A'), day.strftime('%A')),
            'income': float(day_income),
            'count': day_count,
        })
    
    # محاسبه max برای نمودار
    max_income = max([d['income'] for d in daily_stats]) if daily_stats else 1
    if max_income == 0:
        max_income = 1
    
    # آمار بوفه
    buffet_orders_today = Order.objects.filter(
        gamenet=gamenet,
        created_at__date=today,
        is_paid=True
    )
    buffet_income_today = buffet_orders_today.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    buffet_sales_count_today = buffet_orders_today.count()
    
    buffet_orders_month = Order.objects.filter(
        gamenet=gamenet,
        created_at__year=today.year,
        created_at__month=today.month,
        is_paid=True
    )
    buffet_income_month = buffet_orders_month.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    buffet_sales_count_month = buffet_orders_month.count()
    
    # سود خالص بوفه امروز
    buffet_items_today = OrderItem.objects.filter(
        order__gamenet=gamenet,
        order__created_at__date=today,
        order__is_paid=True,
    ).exclude(order__status='cancelled')
    buffet_profit_today = buffet_items_today.aggregate(
        revenue=Sum('total_price'),
        cost=Sum(ExpressionWrapper(F('purchase_price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=0)))
    )
    buffet_net_today = (buffet_profit_today['revenue'] or Decimal('0')) - (buffet_profit_today['cost'] or Decimal('0'))
    
    # سود خالص بوفه ماهانه
    buffet_items_month = OrderItem.objects.filter(
        order__gamenet=gamenet,
        order__created_at__year=today.year,
        order__created_at__month=today.month,
        order__is_paid=True,
    ).exclude(order__status='cancelled')
    buffet_profit_month = buffet_items_month.aggregate(
        revenue=Sum('total_price'),
        cost=Sum(ExpressionWrapper(F('purchase_price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=0)))
    )
    buffet_net_month = (buffet_profit_month['revenue'] or Decimal('0')) - (buffet_profit_month['cost'] or Decimal('0'))
    
    # پرفروش‌ترین محصولات بوفه (ماه جاری)
    top_products = OrderItem.objects.filter(
        order__gamenet=gamenet,
        order__created_at__year=today.year,
        order__created_at__month=today.month,
        order__is_paid=True,
    ).exclude(order__status='cancelled').values(
        'product__name'
    ).annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('total_price'),
    ).order_by('-total_qty')[:5]
    
    # فروش‌های اخیر بوفه
    recent_buffet_orders = Order.objects.filter(
        gamenet=gamenet,
        is_paid=True,
    ).prefetch_related('items', 'items__product').order_by('-created_at')[:5]
    
    # کرایه‌های اخیر با pagination
    all_recent_sessions = Session.objects.filter(
        device__gamenet=gamenet,
        is_active=False
    ).select_related('device').order_by('-end_time')
    
    paginator = Paginator(all_recent_sessions, 10)  # 10 items per page
    page_number = request.GET.get('page', 1)
    recent_sessions = paginator.get_page(page_number)
    
    # میانگین‌ها
    avg_session_duration = 0
    if month_count > 0:
        total_duration = sum([
            (s.end_time - s.start_time).total_seconds() / 60 
            for s in month_sessions if s.end_time
        ])
        avg_session_duration = int(total_duration / month_count)
    
    context = {
        'gamenet': gamenet,
        'today': today,
        'today_income': today_income,
        'today_count': today_count,
        'today_hours': round(today_hours, 1),
        'week_income': week_income,
        'week_count': week_count,
        'month_income': month_income,
        'month_count': month_count,
        'total_income': total_income,
        'total_count': total_count,
        'gross_income_total': gross_income_total,
        'net_income_total': net_income_total,
        'top_devices': top_devices,
        'device_hours_today': device_hours_today,
        'daily_stats': daily_stats,
        'max_income': max_income,
        'buffet_income_today': buffet_income_today,
        'buffet_income_month': buffet_income_month,
        'buffet_sales_count_today': buffet_sales_count_today,
        'buffet_sales_count_month': buffet_sales_count_month,
        'buffet_net_today': buffet_net_today,
        'buffet_net_month': buffet_net_month,
        'top_products': top_products,
        'recent_buffet_orders': recent_buffet_orders,
        'recent_sessions': recent_sessions,
        'avg_session_duration': avg_session_duration,
    }
    
    return render(request, 'gamenet/reports.html', context)


# ==================== Tournament Views ====================

@gamenet_subscription_required 
def tournament_list(request):
    """لیست تورنومنت‌ها"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    visibility_filter = request.GET.get('visibility', '').strip()
    tournaments = Tournament.objects.filter(gamenet=gamenet).select_related('game')
    if visibility_filter in ('public', 'private'):
        tournaments = tournaments.filter(visibility=visibility_filter)

    total_tournaments = tournaments.count()
    public_count = Tournament.objects.filter(gamenet=gamenet, visibility='public').count()
    private_count = Tournament.objects.filter(gamenet=gamenet, visibility='private').count()

    return render(request, 'gamenet/tournament_list.html', {
        'gamenet': gamenet,
        'tournaments': tournaments,
        'selected_visibility': visibility_filter,
        'total_tournaments': total_tournaments,
        'public_count': public_count,
        'private_count': private_count,
    })


@gamenet_subscription_required
def tournament_create(request):
    """ایجاد تورنومنت جدید"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    
    if request.method == 'POST':
        form = TournamentForm(request.POST, request.FILES, gamenet=gamenet)
        if form.is_valid():
            tournament = form.save(commit=False)
            tournament.gamenet = gamenet
            tournament.save()
            messages.success(request, 'تورنومنت جدید ایجاد شد!')
            return redirect('gamenet:tournament_list')
        messages.error(request, 'لطفا خطاهای فرم را اصلاح کنید.')
    else:
        form = TournamentForm(gamenet=gamenet)
    return render(request, 'gamenet/tournament_form.html', {
        'gamenet': gamenet,
        'form': form,
        'title': 'ایجاد تورنومنت جدید'
    })


@gamenet_subscription_required
def tournament_detail(request, pk):
    """جزئیات تورنومنت"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    tournament = get_object_or_404(Tournament.objects.select_related('game', 'champion'), pk=pk, gamenet=gamenet)
    participants = list(TournamentParticipant.objects.filter(tournament=tournament).order_by('rank', 'registered_at', 'id'))
    matches = list(
        TournamentMatch.objects.filter(tournament=tournament)
        .select_related('participant1', 'participant2', 'winner')
        .order_by('round_number', 'match_number', 'id')
    )
    matches_by_round = OrderedDict()
    for match in matches:
        matches_by_round.setdefault(match.round_number, []).append(match)

    champion = tournament.champion
    if champion is None and tournament.status == 'completed':
        champion = next((match.winner for match in reversed(matches) if match.winner_id), None)

    show_results = tournament.status in ('ongoing', 'completed') and bool(matches)
    remaining_capacity = max(tournament.max_participants - len(participants), 0)

    return render(request, 'gamenet/tournament_detail.html', {
        'gamenet': gamenet,
        'tournament': tournament,
        'participants': participants,
        'participants_count': len(participants),
        'matches_by_round': matches_by_round,
        'show_results': show_results,
        'champion': champion,
        'show_participants_public': tournament.show_participants_public,
        'remaining_capacity': remaining_capacity,
    })


def _normalize_digits(value):
    if value is None:
        return ''
    return str(value).strip().translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))


def _generate_participant_phone(tournament):
    while True:
        candidate = f"m{timezone.now().strftime('%H%M%S%f')}"[-15:]
        if not TournamentParticipant.objects.filter(tournament=tournament, phone=candidate).exists():
            return candidate


def _create_round_matches(tournament, entrants, round_number):
    matches_to_create = []
    match_number = 1
    for index in range(0, len(entrants), 2):
        participant1 = entrants[index]
        participant2 = entrants[index + 1] if index + 1 < len(entrants) else None
        if participant2 is None:
            matches_to_create.append(TournamentMatch(
                tournament=tournament,
                round_number=round_number,
                match_number=match_number,
                participant1=participant1,
                participant2=None,
                winner=participant1,
                status='bye',
            ))
        else:
            matches_to_create.append(TournamentMatch(
                tournament=tournament,
                round_number=round_number,
                match_number=match_number,
                participant1=participant1,
                participant2=participant2,
                status='pending',
            ))
        match_number += 1
    TournamentMatch.objects.bulk_create(matches_to_create)


def _advance_tournament_bracket(tournament):
    changed = False
    while True:
        round_numbers = list(
            TournamentMatch.objects.filter(tournament=tournament)
            .values_list('round_number', flat=True)
            .distinct()
            .order_by('round_number')
        )
        if not round_numbers:
            return changed

        progressed = False
        for round_number in round_numbers:
            round_matches_qs = TournamentMatch.objects.filter(
                tournament=tournament,
                round_number=round_number,
            ).order_by('match_number', 'id')

            if round_matches_qs.filter(winner__isnull=True).exists():
                continue

            winners_ids = [winner_id for winner_id in round_matches_qs.values_list('winner_id', flat=True) if winner_id]
            if not winners_ids:
                continue

            next_round_exists = TournamentMatch.objects.filter(
                tournament=tournament,
                round_number=round_number + 1,
            ).exists()
            if next_round_exists:
                continue

            if len(winners_ids) == 1:
                champion = TournamentParticipant.objects.filter(id=winners_ids[0]).first()
                needs_update = (
                    champion is not None and (
                        tournament.champion_id != champion.id
                        or tournament.status != 'completed'
                        or tournament.registration_open
                    )
                )
                if needs_update:
                    tournament.champion = champion
                    tournament.status = 'completed'
                    tournament.registration_open = False
                    tournament.save(update_fields=['champion', 'status', 'registration_open'])
                    changed = True
                return changed

            winners_map = {
                participant.id: participant
                for participant in TournamentParticipant.objects.filter(id__in=winners_ids)
            }
            ordered_winners = [winners_map[winner_id] for winner_id in winners_ids if winner_id in winners_map]
            if not ordered_winners:
                continue

            _create_round_matches(tournament, ordered_winners, round_number + 1)
            changed = True
            progressed = True
            break

        if not progressed:
            break

    return changed


@gamenet_subscription_required
def tournament_manage(request, pk):
    """مدیریت تورنومنت"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    tournament = get_object_or_404(
        Tournament.objects.select_related('game'),
        pk=pk,
        gamenet=gamenet,
    )

    if request.method == 'POST':
        action = request.POST.get('action', '').strip()
        valid_statuses = {code for code, _ in Tournament.STATUS_CHOICES}
        has_matches = TournamentMatch.objects.filter(tournament=tournament).exists()

        if action == 'update_status':
            new_status = request.POST.get('status', '').strip()
            if new_status not in valid_statuses:
                messages.error(request, 'وضعیت انتخاب‌شده معتبر نیست.')
            else:
                tournament.status = new_status
                tournament.save(update_fields=['status'])
                messages.success(request, 'وضعیت مسابقه با موفقیت به‌روزرسانی شد.')
            return redirect('gamenet:tournament_manage', pk=tournament.pk)

        if action == 'toggle_registration':
            registration_open = request.POST.get('registration_open', '0') in ('1', 'true', 'True', 'on')
            if registration_open and has_matches:
                messages.error(request, 'بعد از شروع براکت، بازکردن ثبت‌نام مجاز نیست.')
            else:
                tournament.registration_open = registration_open
                tournament.save(update_fields=['registration_open'])
                messages.success(request, 'تنظیمات ثبت‌نام ذخیره شد.')
            return redirect('gamenet:tournament_manage', pk=tournament.pk)

        if action == 'toggle_public_participants':
            show_participants_public = request.POST.get('show_participants_public', '0') in ('1', 'true', 'True', 'on')
            tournament.show_participants_public = show_participants_public
            tournament.save(update_fields=['show_participants_public'])
            messages.success(request, 'تنظیمات نمایش عمومی شرکت‌کنندگان ذخیره شد.')
            return redirect('gamenet:tournament_manage', pk=tournament.pk)

        if action == 'create_participant':
            if has_matches:
                messages.error(request, 'بعد از شروع مسابقه، افزودن شرکت‌کننده جدید غیرفعال است.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)
            if tournament.participants_count >= tournament.max_participants:
                messages.error(request, 'ظرفیت مسابقه تکمیل شده است.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)

            name = request.POST.get('name', '').strip()
            phone = _normalize_digits(request.POST.get('phone', ''))
            gamer_tag = request.POST.get('gamer_tag', '').strip()
            paid = request.POST.get('paid', '0') in ('1', 'true', 'True', 'on')

            if not name:
                messages.error(request, 'نام شرکت‌کننده الزامی است.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)

            if not phone:
                phone = _generate_participant_phone(tournament)

            if TournamentParticipant.objects.filter(tournament=tournament, phone=phone).exists():
                messages.error(request, 'این شماره قبلا در مسابقه ثبت شده است.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)

            TournamentParticipant.objects.create(
                tournament=tournament,
                name=name,
                phone=phone,
                gamer_tag=gamer_tag,
                paid=paid,
            )
            messages.success(request, f'{name} به مسابقه اضافه شد.')
            return redirect('gamenet:tournament_manage', pk=tournament.pk)

        if action == 'start_tournament':
            participants = list(TournamentParticipant.objects.filter(tournament=tournament).order_by('registered_at', 'id'))
            if has_matches:
                messages.error(request, 'قرعه‌کشی قبلا انجام شده است.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)
            if len(participants) < 2:
                messages.error(request, 'برای شروع مسابقه حداقل 2 شرکت‌کننده لازم است.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)

            random.shuffle(participants)
            with transaction.atomic():
                _create_round_matches(tournament, participants, round_number=1)
                tournament.status = 'ongoing'
                tournament.registration_open = False
                tournament.champion = None
                tournament.save(update_fields=['status', 'registration_open', 'champion'])
                _advance_tournament_bracket(tournament)
            messages.success(request, 'مسابقه شروع شد و قرعه‌کشی انجام شد.')
            return redirect('gamenet:tournament_manage', pk=tournament.pk)

        if action == 'set_match_winner':
            match_id = request.POST.get('match_id')
            winner_id = request.POST.get('winner_id')
            match = get_object_or_404(TournamentMatch, id=match_id, tournament=tournament)
            if match.status == 'bye':
                messages.info(request, 'این بازی حالت استراحت دارد و برنده آن مشخص است.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)

            winner = TournamentParticipant.objects.filter(id=winner_id, tournament=tournament).first() if winner_id else None
            if winner is None:
                messages.error(request, 'برنده انتخاب‌شده معتبر نیست.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)
            if winner.id not in {match.participant1_id, match.participant2_id}:
                messages.error(request, 'برنده باید یکی از دو طرف بازی باشد.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)

            with transaction.atomic():
                match.winner = winner
                match.status = 'completed'
                match.save(update_fields=['winner', 'status'])
                _advance_tournament_bracket(tournament)

            tournament.refresh_from_db(fields=['status', 'champion'])
            if tournament.status == 'completed' and tournament.champion:
                messages.success(request, f'مسابقه تمام شد. قهرمان: {tournament.champion.name}')
            else:
                messages.success(request, 'برنده بازی ثبت شد.')
            return redirect('gamenet:tournament_manage', pk=tournament.pk)

        if action == 'update_participant':
            participant_id = request.POST.get('participant_id')
            participant = get_object_or_404(TournamentParticipant, pk=participant_id, tournament=tournament)
            rank_raw = _normalize_digits(request.POST.get('rank', ''))
            paid = request.POST.get('paid', '0') in ('1', 'true', 'True', 'on')

            rank_value = None
            if rank_raw:
                try:
                    parsed_rank = int(rank_raw)
                    if parsed_rank <= 0:
                        raise ValueError
                    rank_value = parsed_rank
                except ValueError:
                    messages.error(request, f'رتبه برای {participant.name} معتبر نیست.')
                    return redirect('gamenet:tournament_manage', pk=tournament.pk)

            participant.paid = paid
            participant.rank = rank_value
            participant.save(update_fields=['paid', 'rank'])
            messages.success(request, f'اطلاعات {participant.name} ذخیره شد.')
            return redirect('gamenet:tournament_manage', pk=tournament.pk)

        if action == 'delete_participant':
            if has_matches:
                messages.error(request, 'بعد از شروع مسابقه حذف شرکت‌کننده مجاز نیست.')
                return redirect('gamenet:tournament_manage', pk=tournament.pk)
            participant_id = request.POST.get('participant_id')
            participant = get_object_or_404(TournamentParticipant, pk=participant_id, tournament=tournament)
            participant_name = participant.name
            participant.delete()
            messages.success(request, f'{participant_name} از مسابقه حذف شد.')
            return redirect('gamenet:tournament_manage', pk=tournament.pk)

        if action == 'delete_tournament':
            tournament_name = tournament.name
            tournament.delete()
            messages.success(request, f'مسابقه «{tournament_name}» حذف شد.')
            return redirect('gamenet:tournament_list')

        messages.error(request, 'عملیات نامعتبر است.')
        return redirect('gamenet:tournament_manage', pk=tournament.pk)

    participants = list(
        TournamentParticipant.objects
        .filter(tournament=tournament)
        .order_by('registered_at', 'id')
    )
    participants.sort(key=lambda participant: (participant.rank is None, participant.rank or 10**9, participant.registered_at))

    matches = list(
        TournamentMatch.objects.filter(tournament=tournament)
        .select_related('participant1', 'participant2', 'winner')
        .order_by('round_number', 'match_number', 'id')
    )
    matches_by_round = OrderedDict()
    for match in matches:
        matches_by_round.setdefault(match.round_number, []).append(match)

    champion = tournament.champion
    if champion is None and tournament.status == 'completed':
        champion = next((match.winner for match in reversed(matches) if match.winner_id), None)

    participants_count = len(participants)
    paid_count = sum(1 for p in participants if p.paid)
    ranked_count = sum(1 for p in participants if p.rank)
    remaining_capacity = max(tournament.max_participants - participants_count, 0)

    return render(request, 'gamenet/tournament_manage.html', {
        'gamenet': gamenet,
        'tournament': tournament,
        'participants': participants,
        'participants_count': participants_count,
        'paid_count': paid_count,
        'ranked_count': ranked_count,
        'remaining_capacity': remaining_capacity,
        'status_choices': Tournament.STATUS_CHOICES,
        'matches_by_round': matches_by_round,
        'has_matches': bool(matches),
        'champion': champion,
        'can_add_participant': not bool(matches) and participants_count < tournament.max_participants,
    })


@gamenet_subscription_required
def tournament_register(request, pk):
    """ثبت‌نام در تورنومنت"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    tournament = get_object_or_404(Tournament, pk=pk, gamenet=gamenet)

    if tournament.status != 'upcoming':
        messages.error(request, 'ثبت‌نام فقط برای مسابقات در انتظار امکان‌پذیر است.')
        return redirect('gamenet:tournament_detail', pk=tournament.pk)
    if not tournament.registration_open:
        messages.error(request, 'ثبت‌نام این مسابقه بسته شده است.')
        return redirect('gamenet:tournament_detail', pk=tournament.pk)
    if tournament.participants_count >= tournament.max_participants:
        messages.error(request, 'ظرفیت مسابقه تکمیل شده است.')
        return redirect('gamenet:tournament_detail', pk=tournament.pk)
    
    if request.method == 'POST':
        form = ParticipantForm(request.POST)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.tournament = tournament
            participant.save()
            messages.success(request, 'شرکت‌کننده با موفقیت ثبت شد!')
            return redirect('gamenet:tournament_detail', pk=tournament.pk)
        messages.error(request, 'لطفا اطلاعات شرکت‌کننده را صحیح وارد کنید.')
    else:
        form = ParticipantForm()
    
    return render(request, 'gamenet/tournament_register.html', {
        'gamenet': gamenet,
        'tournament': tournament,
        'form': form
    })


# ==================== Ajax Views ====================

@require_POST
@gamenet_subscription_required
def get_session_time(request):
    """دریافت زمان جلسه فعال برای Ajax"""
    session_id = request.POST.get('session_id')
    if session_id:
        try:
            gamenet = get_object_or_404(GameNet, owner=request.user)
            session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet, is_active=True)
            
            duration = timezone.now() - session.start_time
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            # محاسبه قیمت فعلی بر اساس زمان و دسته‌های اضافی
            hours_decimal = Decimal(total_seconds) / Decimal(3600)
            device_cost = session.hourly_rate * hours_decimal
            controller_cost = Decimal(session.extra_controllers) * session.extra_controller_rate * hours_decimal
            current_cost = device_cost + controller_cost
            
            return JsonResponse({
                'hours': hours,
                'minutes': minutes,
                'seconds': seconds,
                'current_cost': float(current_cost),
                'formatted_time': f'{hours:02d}:{minutes:02d}:{seconds:02d}',
                'formatted_cost': f'{(int(current_cost) // 1000) * 1000:,.0f}',
                'extra_controllers': session.extra_controllers
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    
    return JsonResponse({'error': 'Session not found'}, status=404)


# ==================== Missing Views ====================

@gamenet_subscription_required
def game_edit(request, pk):
    """ویرایش بازی"""
    # This view is not implemented yet
    return redirect('gamenet:game_list')

@gamenet_subscription_required
def game_delete(request, pk):
    """حذف بازی"""
    # This view is not implemented yet
    return redirect('gamenet:game_list')

@gamenet_subscription_required
def tournament_edit(request, pk):
    """ویرایش تورنومنت"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    tournament = get_object_or_404(Tournament, pk=pk, gamenet=gamenet)

    if request.method == 'POST':
        form = TournamentForm(request.POST, request.FILES, instance=tournament, gamenet=gamenet)
        if form.is_valid():
            form.save()
            messages.success(request, 'تورنومنت با موفقیت ویرایش شد!')
            return redirect('gamenet:tournament_detail', pk=tournament.pk)
        messages.error(request, 'لطفا خطاهای فرم را اصلاح کنید.')
    else:
        form = TournamentForm(instance=tournament, gamenet=gamenet)

    return render(request, 'gamenet/tournament_form.html', {
        'gamenet': gamenet,
        'form': form,
        'tournament': tournament,
        'title': 'ویرایش تورنومنت',
    })

def user_dashboard(request):
    """داشبورد کاربر"""
    return render(request, 'gamenet/user_dashboard.html')

def create_gamenet(request):
    """ایجاد گیم‌نت جدید"""
    return render(request, 'gamenet/create_gamenet.html')

def edit_gamenet(request, slug):
    """ویرایش گیم‌نت"""
    return render(request, 'gamenet/edit_gamenet.html', {'gamenet': {'slug': slug}})

def delete_gamenet(request, slug):
    """حذف گیم‌نت"""
    return render(request, 'gamenet/delete_gamenet.html', {'gamenet': {'slug': slug}})

def panel_dashboard(request, slug):
    """داشبورد پنل گیم‌نت"""
    return render(request, 'gamenet/panel_dashboard.html', {'gamenet': {'slug': slug}})

def panel_device_list(request, slug):
    """لیست دستگاه‌ها در پنل"""
    return redirect('gamenet:device_list')

def panel_session_list(request, slug):
    """لیست جلسه‌ها در پنل"""
    return redirect('gamenet:session_list')

def panel_game_list(request, slug):
    """لیست بازی‌ها در پنل"""
    return redirect('gamenet:game_list')

def panel_tournament_list(request, slug):
    """لیست تورنومنت‌ها در پنل"""
    return redirect('gamenet:tournament_list')

def panel_reports(request, slug):
    """گزارشات در پنل"""
    return redirect('gamenet:reports')


# ==================== Quick Session API ====================

@gamenet_subscription_required_api
@gamenet_subscription_required_api
@require_POST
def quick_start_session(request, device_id):
    """شروع سریع جلسه بدون نیاز به فرم"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        device = get_object_or_404(Device, pk=device_id, gamenet=gamenet)
        
        if device.status != 'available':
            return JsonResponse({
                'success': False,
                'error': 'این دستگاه در حال حاضر آزاد نیست!'
            })
        
        # ایجاد جلسه جدید — در صورت ارسال 'start_time' از کلاینت، از آن استفاده کن
        start_time = None
        try:
            # پشتیبانی JSON body
            payload = json.loads(request.body.decode('utf-8') or '{}')
            if payload.get('start_time'):
                start_time = payload.get('start_time')
        except Exception:
            # در صورت عدم توانایی در پارس، از request.POST استفاده کن
            start_time = request.POST.get('start_time') or None

        if start_time:
            # پذیرش ISO یا timestamp میلی‌ثانیه
            from django.utils.dateparse import parse_datetime
            try:
                dt = parse_datetime(start_time)
                if dt is None:
                    # ممکن است timestamp میلی‌ثانیه باشد
                    ts = int(start_time)
                    dt = timezone.datetime.fromtimestamp(ts/1000.0, tz=timezone.get_current_timezone())
                start_dt = dt
            except Exception:
                start_dt = timezone.now()
        else:
            start_dt = timezone.now()

        session = Session.objects.create(
            device=device,
            customer_name='مشتری',
            start_time=start_dt,
            hourly_rate=device.hourly_rate,
            extra_controller_rate=gamenet.extra_controller_price,
            is_active=True
        )
        
        # آپدیت وضعیت دستگاه
        device.status = 'occupied'
        device.save()
        
        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'device_id': device.id,
            'start_time': session.start_time.isoformat(),
            'hourly_rate': float(session.hourly_rate),
            'extra_controller_price': float(gamenet.extra_controller_price)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@gamenet_subscription_required_api
@require_POST
def quick_stop_session(request, session_id):
    """پایان سریع جلسه و نمایش مبلغ"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet, is_active=True)
        
        session.end_time = timezone.now()
        session.is_active = False
        
        # محاسبه مدت زمان
        duration = session.end_time - session.start_time
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        formatted_duration = f'{hours:02d}:{minutes:02d}:{seconds:02d}'
        
        # محاسبه قیمت نهایی
        session.total_cost = session.calculate_cost()
        session.save()
        
        # آزاد کردن دستگاه
        device = session.device
        device.status = 'available'
        device.save()
        
        # نمایش: گرد کردن به هزارتومان (بدون اعشار)
        display_cost = (session.total_cost // 1000) * 1000

        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'device_id': device.id,
            'total_cost': float(session.total_cost),
            'formatted_cost': f'{display_cost:,.0f}',
            'duration': formatted_duration,
            'customer_name': session.customer_name
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@gamenet_subscription_required_api
def get_session_current_cost(request, session_id):
    """دریافت هزینه فعلی جلسه بدون پایان دادن"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet, is_active=True)
        
        # محاسبه هزینه فعلی با فرض end_time = الان
        from django.utils import timezone
        from decimal import Decimal
        
        current_time = timezone.now()
        delta = current_time - session.start_time
        total_seconds = delta.total_seconds()
        
        # بدون حداقل - دقیقاً بر اساس زمان واقعی
        hours = Decimal(total_seconds) / Decimal(3600)
        
        # هزینه اصلی دستگاه
        device_cost = session.hourly_rate * hours
        
        # هزینه دسته‌های اضافی
        controller_cost = Decimal(session.extra_controllers) * session.extra_controller_rate * hours
        
        current_cost = device_cost + controller_cost

        # نمایش: گرد کردن به هزارتومان (بدون اعشار)
        display_cost = (current_cost // 1000) * 1000

        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'device_id': session.device.id,
            'current_cost': float(current_cost),
            'formatted_cost': f'{display_cost:,.0f}',
            'elapsed_seconds': int(total_seconds),
            'hourly_rate': float(session.hourly_rate)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@require_POST
@gamenet_subscription_required
def add_controller(request, session_id):
    """اضافه کردن دسته اضافی به جلسه"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet, is_active=True)
        
        # اضافه کردن یک دسته
        session.extra_controllers += 1
        session.extra_controller_rate = gamenet.extra_controller_price
        session.save()
        
        return JsonResponse({
            'success': True,
            'extra_controllers': session.extra_controllers,
            'controller_rate': float(session.extra_controller_rate)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@require_POST
@gamenet_subscription_required
def remove_controller(request, session_id):
    """کم کردن دسته اضافی از جلسه"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        session = get_object_or_404(Session, pk=session_id, device__gamenet=gamenet, is_active=True)
        
        # کم کردن یک دسته (حداقل صفر)
        if session.extra_controllers > 0:
            session.extra_controllers -= 1
            session.save()
        
        return JsonResponse({
            'success': True,
            'extra_controllers': session.extra_controllers
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@require_POST
@gamenet_subscription_required
def device_update_api(request, device_id):
    """API برای ویرایش دستگاه"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        device = get_object_or_404(Device, pk=device_id, gamenet=gamenet)
        
        data = json.loads(request.body)
        
        # بررسی فیلدهای ضروری
        name = data.get('name', '').strip()
        device_type = data.get('device_type', '')
        number = data.get('number')
        hourly_rate = data.get('hourly_rate')
        
        if not name:
            return JsonResponse({
                'success': False,
                'error': 'نام دستگاه الزامی است'
            })
        
        if not number:
            return JsonResponse({
                'success': False,
                'error': 'شماره دستگاه الزامی است'
            })
        
        if not hourly_rate:
            return JsonResponse({
                'success': False,
                'error': 'قیمت ساعتی الزامی است'
            })
        
        # بررسی تکراری نبودن شماره دستگاه
        if Device.objects.filter(gamenet=gamenet, number=number).exclude(pk=device_id).exists():
            return JsonResponse({
                'success': False,
                'error': 'این شماره دستگاه قبلاً استفاده شده است'
            })
        
        # بروزرسانی دستگاه
        device.name = name
        device.device_type = device_type
        device.number = number
        device.hourly_rate = Decimal(str(hourly_rate))
        device.save()
        
        return JsonResponse({
            'success': True,
            'device': {
                'id': device.id,
                'name': device.name,
                'device_type': device.device_type,
                'number': device.number,
                'hourly_rate': float(device.hourly_rate)
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'فرمت داده نامعتبر است'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


# ==================== Buffet Views ====================

@gamenet_subscription_required
def buffet_dashboard(request):
    """صفحه اصلی بوفه - فروش سریع"""
    gamenet = get_object_or_404(GameNet, owner=request.user)

    products = Product.objects.filter(
        gamenet=gamenet,
        is_active=True,
    ).select_related('category').order_by('category__order', 'name')
    categories = ProductCategory.objects.filter(
        gamenet=gamenet,
        is_active=True,
    ).prefetch_related(
        Prefetch(
            'products',
            queryset=Product.objects.filter(gamenet=gamenet, is_active=True).order_by('name'),
            to_attr='active_products',
        )
    )
    
    # محصولات بدون دسته‌بندی
    uncategorized_products = products.filter(category__isnull=True)
    
    # آمار
    total_products = products.count()
    available_products = products.filter(is_available=True).count()
    
    # سفارشات امروز
    today = timezone.now().date()
    today_orders = Order.objects.filter(gamenet=gamenet, created_at__date=today)
    today_sales = today_orders.filter(is_paid=True).aggregate(total=Sum('total_amount'))['total'] or 0
    today_sales_count = today_orders.filter(is_paid=True).count()
    pending_orders = today_orders.filter(status__in=['pending', 'preparing']).count()
    
    # فروش‌های اخیر (۱۰ تای آخر)
    recent_orders = Order.objects.filter(
        gamenet=gamenet,
        is_paid=True,
    ).prefetch_related('items', 'items__product').order_by('-created_at')[:10]
    
    # سود خالص امروز
    today_items = OrderItem.objects.filter(
        order__gamenet=gamenet,
        order__created_at__date=today,
        order__is_paid=True,
    ).exclude(order__status='cancelled')
    today_profit = today_items.aggregate(
        revenue=Sum('total_price'),
        cost=Sum(ExpressionWrapper(F('purchase_price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=0)))
    )
    today_revenue = today_profit['revenue'] or 0
    today_cost = today_profit['cost'] or 0
    today_net_profit = today_revenue - today_cost
    
    context = {
        'gamenet': gamenet,
        'categories': categories,
        'uncategorized_products': uncategorized_products,
        'total_products': total_products,
        'available_products': available_products,
        'today_sales': today_sales,
        'today_sales_count': today_sales_count,
        'today_net_profit': today_net_profit,
        'pending_orders': pending_orders,
        'recent_orders': recent_orders,
    }
    
    return render(request, 'gamenet/buffet_dashboard.html', context)


@gamenet_subscription_required
def recent_sales_page(request):
    """صفحه فروش‌های اخیر بوفه (آیتم‌محور با صفحه‌بندی)"""
    from django.core.paginator import Paginator

    gamenet = get_object_or_404(GameNet, owner=request.user)

    sales_items_qs = OrderItem.objects.filter(
        order__gamenet=gamenet,
        order__is_paid=True,
    ).exclude(
        order__status='cancelled'
    ).select_related(
        'order', 'product'
    ).order_by('-order__created_at', '-id')

    per_page_raw = request.GET.get('per_page', '25').strip()
    per_page_choices = [10, 25, 50, 100]
    try:
        per_page = int(per_page_raw)
    except (TypeError, ValueError):
        per_page = 25
    if per_page not in per_page_choices:
        per_page = 25

    paginator = Paginator(sales_items_qs, per_page)
    page_number = request.GET.get('page', 1)
    sales_items = paginator.get_page(page_number)
    total_records = paginator.count
    start_record = (sales_items.number - 1) * per_page + 1 if total_records else 0
    end_record = start_record + len(sales_items.object_list) - 1 if total_records else 0

    top_product_by_qty = sales_items_qs.values(
        'product__name'
    ).annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('total_price'),
    ).order_by('-total_qty', '-total_revenue', 'product__name').first()

    top_product_by_revenue = sales_items_qs.values(
        'product__name'
    ).annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('total_price'),
    ).order_by('-total_revenue', '-total_qty', 'product__name').first()

    top_category_by_qty = sales_items_qs.values(
        category_name=Coalesce('product__category__name', Value('بدون دسته‌بندی', output_field=CharField()))
    ).annotate(
        total_qty=Sum('quantity'),
        total_revenue=Sum('total_price'),
    ).order_by('-total_qty', '-total_revenue', 'category_name').first()

    context = {
        'gamenet': gamenet,
        'sales_items': sales_items,
        'per_page': per_page,
        'per_page_choices': per_page_choices,
        'total_records': total_records,
        'start_record': start_record,
        'end_record': end_record,
        'top_product_by_qty': top_product_by_qty,
        'top_product_by_revenue': top_product_by_revenue,
        'top_category_by_qty': top_category_by_qty,
    }
    return render(request, 'gamenet/recent_sales.html', context)


@gamenet_subscription_required
def product_list(request):
    """لیست محصولات"""
    gamenet = get_object_or_404(GameNet, owner=request.user)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'quick_category':
            name = request.POST.get('name', '').strip()
            icon = request.POST.get('icon', '').strip() or 'fas fa-tag'
            color = request.POST.get('color', '').strip() or '#7c3aed'
            raw_order = request.POST.get('order', '')

            if not name:
                messages.error(request, 'نام دسته‌بندی الزامی است.')
                return redirect(f"{reverse('gamenet:product_list')}")

            try:
                order = int(raw_order) if raw_order not in (None, '') else 0
            except (TypeError, ValueError):
                messages.error(request, 'ترتیب نمایش نامعتبر است.')
                return redirect(f"{reverse('gamenet:product_list')}")

            ProductCategory.objects.create(
                gamenet=gamenet,
                name=name,
                icon=icon,
                color=color,
                order=max(0, order),
            )
            messages.success(request, 'دسته‌بندی جدید با موفقیت اضافه شد!')
            return redirect(f"{reverse('gamenet:product_list')}")

        if form_type == 'quick_product':
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip()
            raw_purchase_price = request.POST.get('purchase_price', '').strip()
            raw_sale_price = request.POST.get('sale_price', '').strip()
            raw_stock = request.POST.get('stock', '').strip()
            raw_category_id = request.POST.get('category', '').strip()
            image = request.FILES.get('image')
            is_available = request.POST.get('is_available') == 'on'
            is_active = request.POST.get('is_active') == 'on'

            if not name:
                messages.error(request, 'نام محصول الزامی است.')
                return redirect('gamenet:product_list')

            try:
                purchase_price = Decimal(raw_purchase_price) if raw_purchase_price else Decimal('0')
                sale_price = Decimal(raw_sale_price) if raw_sale_price else Decimal('0')
                stock = int(raw_stock) if raw_stock else 0
                if purchase_price < 0 or sale_price < 0 or stock < 0:
                    raise ValueError
            except (ValueError, TypeError):
                messages.error(request, 'مقادیر قیمت یا موجودی نامعتبر است.')
                return redirect('gamenet:product_list')

            category = None
            if raw_category_id:
                category = ProductCategory.objects.filter(gamenet=gamenet, id=raw_category_id).first()
                if category is None:
                    messages.error(request, 'دسته‌بندی انتخاب‌شده معتبر نیست.')
                    return redirect('gamenet:product_list')

            price = sale_price if sale_price > 0 else purchase_price
            Product.objects.create(
                gamenet=gamenet,
                category=category,
                name=name,
                price=price,
                purchase_price=purchase_price,
                sale_price=sale_price,
                image=image,
                description=description,
                stock=stock,
                is_available=is_available,
                is_active=is_active,
            )
            messages.success(request, 'محصول جدید با موفقیت اضافه شد!')
            return redirect('gamenet:product_list')

    categories = ProductCategory.objects.filter(gamenet=gamenet)
    products = Product.objects.filter(gamenet=gamenet)
    
    # فیلتر بر اساس دسته‌بندی
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    context = {
        'gamenet': gamenet,
        'categories': categories,
        'products': products,
        'selected_category': category_id,
    }
    
    return render(request, 'gamenet/product_list.html', context)


@gamenet_subscription_required
def product_create(request):
    """ایجاد محصول جدید"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, gamenet=gamenet)
        if form.is_valid():
            product = form.save(commit=False)
            product.gamenet = gamenet
            product.save()
            messages.success(request, 'محصول جدید با موفقیت اضافه شد!')
            return redirect('gamenet:product_list')
    else:
        form = ProductForm(gamenet=gamenet)
    
    return render(request, 'gamenet/product_form.html', {
        'gamenet': gamenet,
        'form': form,
        'title': 'افزودن محصول جدید'
    })


@gamenet_subscription_required
def product_edit(request, pk):
    """ویرایش محصول"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    product = get_object_or_404(Product, pk=pk, gamenet=gamenet)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product, gamenet=gamenet)
        if form.is_valid():
            form.save()
            messages.success(request, 'محصول با موفقیت بروزرسانی شد!')
            return redirect('gamenet:product_list')
    else:
        form = ProductForm(instance=product, gamenet=gamenet)
    
    return render(request, 'gamenet/product_form.html', {
        'gamenet': gamenet,
        'form': form,
        'product': product,
        'title': 'ویرایش محصول'
    })


@gamenet_subscription_required
def product_delete(request, pk):
    """حذف محصول"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    product = get_object_or_404(Product, pk=pk, gamenet=gamenet)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'محصول با موفقیت حذف شد!')
        return redirect('gamenet:product_list')
    
    return render(request, 'gamenet/product_confirm_delete.html', {
        'gamenet': gamenet,
        'product': product
    })


@gamenet_subscription_required
def category_list(request):
    """لیست دسته‌بندی‌ها"""
    get_object_or_404(GameNet, owner=request.user)
    return redirect(f"{reverse('gamenet:product_list')}")


@gamenet_subscription_required
@require_POST
def category_quick_create(request):
    """ایجاد سریع دسته‌بندی از صفحه محصولات"""
    gamenet = get_object_or_404(GameNet, owner=request.user)

    name = request.POST.get('name', '').strip()
    icon = request.POST.get('icon', '').strip() or 'fas fa-tag'
    color = request.POST.get('color', '').strip() or '#7c3aed'
    raw_order = request.POST.get('order', '')

    if not name:
        messages.error(request, 'نام دسته‌بندی الزامی است.')
        return redirect(f"{reverse('gamenet:product_list')}")

    try:
        order = int(raw_order) if raw_order not in (None, '') else 0
    except (TypeError, ValueError):
        messages.error(request, 'ترتیب نمایش نامعتبر است.')
        return redirect(f"{reverse('gamenet:product_list')}")

    ProductCategory.objects.create(
        gamenet=gamenet,
        name=name,
        icon=icon,
        color=color,
        order=max(0, order),
    )
    messages.success(request, 'دسته‌بندی جدید با موفقیت اضافه شد!')
    return redirect(f"{reverse('gamenet:product_list')}")


@gamenet_subscription_required
def category_create(request):
    """ایجاد دسته‌بندی جدید"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    
    if request.method == 'POST':
        source = request.POST.get('source', '').strip()
        name = request.POST.get('name', '').strip()
        icon = request.POST.get('icon', '').strip() or 'fas fa-tag'
        color = request.POST.get('color', '#7c3aed').strip() or '#7c3aed'
        raw_order = request.POST.get('order', 0)
        image = request.FILES.get('image')

        try:
            order = int(raw_order) if raw_order not in (None, '') else 0
        except (TypeError, ValueError):
            messages.error(request, 'ترتیب نمایش نامعتبر است.')
            if source == 'product_list':
                return redirect(f"{reverse('gamenet:product_list')}")
            return render(request, 'gamenet/category_form.html', {
                'gamenet': gamenet,
                'title': 'افزودن دسته‌بندی جدید'
            })
        order = max(0, order)
        
        if name:
            ProductCategory.objects.create(
                gamenet=gamenet,
                name=name,
                icon=icon,
                color=color,
                order=order,
                image=image
            )
            messages.success(request, 'دسته‌بندی جدید با موفقیت اضافه شد!')
            return redirect(f"{reverse('gamenet:product_list')}")
        else:
            messages.error(request, 'نام دسته‌بندی الزامی است.')
            if source == 'product_list':
                return redirect(f"{reverse('gamenet:product_list')}")
    
    return render(request, 'gamenet/category_form.html', {
        'gamenet': gamenet,
        'title': 'افزودن دسته‌بندی جدید'
    })


@gamenet_subscription_required
def category_edit(request, pk):
    """ویرایش دسته‌بندی"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    category = get_object_or_404(ProductCategory, pk=pk, gamenet=gamenet)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        icon = request.POST.get('icon', '').strip()
        color = request.POST.get('color', '#7c3aed').strip()
        order = request.POST.get('order', 0)
        image = request.FILES.get('image')
        remove_image = request.POST.get('remove_image') == '1'
        
        if name:
            category.name = name
            category.icon = icon
            category.color = color
            category.order = int(order) if order else 0
            
            if image:
                category.image = image
            elif remove_image:
                category.image = None
            
            category.save()
            messages.success(request, 'دسته‌بندی با موفقیت بروزرسانی شد!')
            return redirect(f"{reverse('gamenet:product_list')}")
        else:
            messages.error(request, 'نام دسته‌بندی الزامی است.')
    
    return render(request, 'gamenet/category_form.html', {
        'gamenet': gamenet,
        'category': category,
        'title': 'ویرایش دسته‌بندی'
    })


@gamenet_subscription_required
def category_delete(request, pk):
    """حذف دسته‌بندی"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    category = get_object_or_404(ProductCategory, pk=pk, gamenet=gamenet)
    
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'دسته‌بندی با موفقیت حذف شد!')
        return redirect(f"{reverse('gamenet:product_list')}")
    
    return render(request, 'gamenet/category_confirm_delete.html', {
        'gamenet': gamenet,
        'category': category
    })


# ==================== Buffet API ====================


def _create_order_with_locked_stock(*, gamenet, items, order_kwargs, use_atomic=True):
    """ایجاد سفارش و کسر موجودی به شکل اتمیک (all-or-nothing)."""
    if not items:
        raise ValueError('سبد خرید خالی است')

    normalized_items = []
    for item in items:
        try:
            product_id = int(item.get('product_id'))
            quantity = int(item.get('quantity', 1))
        except (TypeError, ValueError, AttributeError):
            raise ValueError('آیتم سفارش نامعتبر است')

        if quantity <= 0:
            raise ValueError('تعداد محصول باید حداقل ۱ باشد')

        normalized_items.append({
            'product_id': product_id,
            'quantity': quantity,
        })

    requested_quantities = {}
    for item in normalized_items:
        pid = item['product_id']
        requested_quantities[pid] = requested_quantities.get(pid, 0) + item['quantity']

    product_ids = set(requested_quantities.keys())
    atomic_context = transaction.atomic() if use_atomic else nullcontext()

    with atomic_context:
        products = Product.objects.select_for_update().filter(
            gamenet=gamenet,
            pk__in=product_ids,
        )
        products_by_id = {product.id: product for product in products}

        if len(products_by_id) != len(product_ids):
            raise ValueError('یکی از محصولات انتخاب‌شده معتبر نیست')

        for product_id, requested_qty in requested_quantities.items():
            product = products_by_id[product_id]
            if product.stock < requested_qty:
                raise ValueError(
                    f'موجودی {product.name} کافی نیست. موجودی فعلی: {product.stock}'
                )

        order = Order.objects.create(gamenet=gamenet, **order_kwargs)
        total = Decimal('0')
        sold_items = []

        for item in normalized_items:
            product = products_by_id[item['product_id']]
            quantity = item['quantity']
            sale_price = product.sale_price or product.price
            purchase_price = product.purchase_price or Decimal('0')
            line_total = sale_price * quantity

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                purchase_price=purchase_price,
                unit_price=sale_price,
                total_price=line_total,
            )

            product.stock -= quantity
            if product.stock == 0:
                product.is_available = False
            product.save()

            total += line_total
            sold_items.append(f'{quantity}x {product.name}')

        order.total_amount = total
        order.save()

    return order, total, sold_items

@require_POST
@gamenet_subscription_required
def product_toggle_availability(request, pk):
    """تغییر وضعیت موجودی محصول"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        product = get_object_or_404(Product, pk=pk, gamenet=gamenet)
        
        product.is_available = not product.is_available
        product.save()
        
        return JsonResponse({
            'success': True,
            'is_available': product.is_available
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@require_POST
@gamenet_subscription_required
def product_update_stock(request, pk):
    """بروزرسانی موجودی محصول"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        product = get_object_or_404(Product, pk=pk, gamenet=gamenet)
        
        data = json.loads(request.body)
        new_stock = data.get('stock', 0)
        
        product.stock = max(0, int(new_stock))
        product.save()
        
        return JsonResponse({
            'success': True,
            'stock': product.stock
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@require_POST
@gamenet_subscription_required
def create_order(request):
    """ایجاد سفارش جدید"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        data = json.loads(request.body)
        
        items = data.get('items', [])
        device_id = data.get('device_id')
        session_id = data.get('session_id')
        customer_name = data.get('customer_name', '')
        
        if not items:
            return JsonResponse({
                'success': False,
                'error': 'سبد خرید خالی است'
            })

        order, total, _ = _create_order_with_locked_stock(
            gamenet=gamenet,
            items=items,
            order_kwargs={
                'device_id': device_id if device_id else None,
                'session_id': session_id if session_id else None,
                'customer_name': customer_name,
            },
        )
        
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'total_amount': float(total)
        })
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@require_POST
@gamenet_subscription_required
def update_order_status(request, order_id):
    """بروزرسانی وضعیت سفارش"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        order = get_object_or_404(Order, pk=order_id, gamenet=gamenet)
        
        data = json.loads(request.body)
        new_status = data.get('status')
        
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save()
            
            return JsonResponse({
                'success': True,
                'status': order.status
            })
        
        return JsonResponse({
            'success': False,
            'error': 'وضعیت نامعتبر است'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@require_POST
@gamenet_subscription_required
def quick_sell(request):
    """فروش سریع از بوفه"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        data = json.loads(request.body)
        
        items = data.get('items', [])
        if not items:
            return JsonResponse({'success': False, 'error': 'سبد خرید خالی است'})

        order, total, sold_items = _create_order_with_locked_stock(
            gamenet=gamenet,
            items=items,
            order_kwargs={
                'status': 'delivered',
                'is_paid': True,
            },
        )
        
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'total_amount': float(total),
            'items_summary': '، '.join(sold_items),
        })
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@gamenet_subscription_required
def get_products_api(request):
    """دریافت لیست محصولات موجود برای API"""
    gamenet = get_object_or_404(GameNet, owner=request.user)
    products = Product.objects.filter(gamenet=gamenet, is_active=True).filter(stock__gt=0)
    categories = ProductCategory.objects.filter(gamenet=gamenet, is_active=True)
    
    products_data = []
    for product in products:
        products_data.append({
            'id': product.id,
            'name': product.name,
            'price': float(product.sale_price or product.price),
            'category_id': product.category_id if product.category else None,
            'category_name': product.category.name if product.category else None,
            'image': product.image.url if product.image else None,
            'stock': product.stock,
            'is_available': product.stock > 0,
        })
    
    categories_data = []
    for cat in categories:
        categories_data.append({
            'id': cat.id,
            'name': cat.name,
            'icon': cat.icon,
            'color': cat.color,
        })
    
    return JsonResponse({
        'success': True,
        'products': products_data,
        'categories': categories_data,
    })


@require_POST
@gamenet_subscription_required
def end_session_with_order(request, session_id):
    """پایان جلسه همراه با ثبت سفارش بوفه"""
    try:
        gamenet = get_object_or_404(GameNet, owner=request.user)
        data = json.loads(request.body)
        order_items = data.get('items', [])

        with transaction.atomic():
            session = get_object_or_404(
                Session.objects.select_for_update(),
                pk=session_id,
                device__gamenet=gamenet,
                is_active=True,
            )

            session.end_time = timezone.now()
            session.is_active = False
            session.total_cost = session.calculate_cost()
            session.save()

            device = get_object_or_404(
                Device.objects.select_for_update(),
                pk=session.device_id,
                gamenet=gamenet,
            )
            device.status = 'available'
            device.save()

            buffet_total = Decimal('0')
            if order_items:
                _, buffet_total, _ = _create_order_with_locked_stock(
                    gamenet=gamenet,
                    items=order_items,
                    order_kwargs={
                        'session': session,
                        'device': device,
                        'customer_name': session.customer_name,
                        'status': 'delivered',
                        'is_paid': True,
                    },
                    use_atomic=False,
                )

            session_cost = session.total_cost
            grand_total = session_cost + buffet_total

            duration_seconds = int((session.end_time - session.start_time).total_seconds())
            hours = duration_seconds // 3600
            minutes = (duration_seconds % 3600) // 60
            seconds = duration_seconds % 60
            duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            return JsonResponse({
                'success': True,
                'session_cost': float(session_cost),
                'buffet_cost': float(buffet_total),
                'total_cost': float(grand_total),
                'duration': duration_formatted,
                'formatted_session_cost': f"{int(session_cost):,}",
                'formatted_buffet_cost': f"{int(buffet_total):,}",
                'formatted_total': f"{int(grand_total):,}",
            })
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
