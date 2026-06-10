"""
Management command: send_profile_view_digest

هر شب اجرا می‌شه — به کاربران غیرپریمیوم که دیروز بازدیدکننده داشتن
یک نوتیف خلاصه می‌فرسته با لینک به صفحه who_viewed_me (که تار نشون میده).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count

from community.models import ProfileView, Notification, GamerProfile
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'نوتیف شبانه بازدید پروفایل برای کاربران غیرپریمیوم'

    def handle(self, *args, **options):
        yesterday_start = timezone.now() - timedelta(days=1)
        yesterday_start = yesterday_start.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end   = yesterday_start + timedelta(days=1)

        # پیدا کردن کاربرانی که دیروز بازدید داشتن
        views = (
            ProfileView.objects
            .filter(viewed_at__range=(yesterday_start, yesterday_end), notified=False)
            .values('viewed_user')
            .annotate(cnt=Count('id'))
        )

        sent = 0
        for item in views:
            user_id = item['viewed_user']
            count   = item['cnt']

            try:
                user    = User.objects.get(pk=user_id)
                profile = GamerProfile.objects.get(user=user)
            except (User.DoesNotExist, GamerProfile.DoesNotExist):
                continue

            # پریمیوم‌ها نوتیف آنی دارن — این digest برای غیرپریمیوم
            if profile.is_premium:
                continue

            # نوتیف قبلی همین روز رو چک کن (تکراری نفرست)
            already = Notification.objects.filter(
                recipient=user,
                notif_type='view_digest',
                created_at__gte=yesterday_start,
            ).exists()
            if already:
                continue

            Notification.objects.create(
                recipient=user,
                sender=None,
                notif_type='view_digest',
                custom_text=f'👁️ دیروز {count} نفر پروفایل شما را مشاهده کردند',
            )
            sent += 1

        # نوتیف‌شده‌ها رو mark کن
        ProfileView.objects.filter(
            viewed_at__range=(yesterday_start, yesterday_end)
        ).update(notified=True)

        self.stdout.write(self.style.SUCCESS(f'✓ {sent} نوتیف خلاصه ارسال شد'))
