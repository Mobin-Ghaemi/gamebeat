"""
python manage.py snapshot_leaderboard --period weekly|monthly|yearly

این دستور امتیاز و رتبه همه کاربران فعال در دوره جاری را ذخیره می‌کند.
باید قبل از شروع دوره جدید اجرا شود:
  - هفتگی: یکشنبه شب (آخر هفته) — قبل از ریست دوشنبه
  - ماهانه: آخرین روز ماه
  - سالانه: ۳۱ اسفند
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict


class Command(BaseCommand):
    help = 'Snapshot leaderboard scores for the current period'

    def add_arguments(self, parser):
        parser.add_argument(
            '--period', choices=['weekly', 'monthly', 'yearly'], required=True,
        )

    def handle(self, *args, **options):
        period = options['period']
        now = timezone.now()
        local_now = timezone.localtime(now)
        day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)

        import jdatetime as _jdt
        from datetime import datetime as _dt, time as _time
        from django.utils.timezone import make_aware as _mka

        jnow = _jdt.datetime.fromgregorian(datetime=local_now)
        j_wd = jnow.weekday()   # 0=شنبه … 6=جمعه

        if period == 'weekly':
            since      = day_start - timedelta(days=j_wd)
            period_key = f'{jnow.year}-W{jnow.isocalendar()[1]:02d}'
        elif period == 'monthly':
            j_m1  = _jdt.date(jnow.year, jnow.month, 1).togregorian()
            since = _mka(_dt.combine(j_m1, _time.min))
            period_key = f'{jnow.year}-{jnow.month:02d}'
        else:
            j_y1  = _jdt.date(jnow.year, 1, 1).togregorian()
            since = _mka(_dt.combine(j_y1, _time.min))
            period_key = str(jnow.year)

        self.stdout.write(
            f'→ Snapshotting [{period}] period_key={period_key} since={since.isoformat()}'
        )

        from community.models import (
            GamerProfile, Post, Comment,
            UserSession, ScoreSettings, LeaderboardSnapshot,
        )
        from django.db.models import Count, Q
        from django.db.models.functions import TruncDate

        cfg = ScoreSettings.get()

        # ── پست و کامنت ──
        all_profiles = list(
            GamerProfile.objects
            .select_related('user')
            .annotate(
                db_post_count=Count(
                    'user__posts',
                    filter=Q(user__posts__created_at__gte=since),
                    distinct=True,
                ),
                db_comment_count=Count(
                    'user__comment',
                    filter=Q(user__comment__created_at__gte=since),
                    distinct=True,
                ),
            )
            .filter(Q(db_post_count__gt=0) | Q(db_comment_count__gt=0))
        )

        if not all_profiles:
            self.stdout.write(self.style.WARNING('هیچ کاربر فعالی در این بازه یافت نشد.'))
            return

        all_user_ids = [g.user_id for g in all_profiles]

        # ── روزهای فعال ──
        days_map: dict[int, set] = defaultdict(set)
        pf = Q(author_id__in=all_user_ids) & Q(created_at__gte=since)
        cf = Q(author_id__in=all_user_ids) & Q(created_at__gte=since)
        for row in Post.objects.filter(pf).annotate(d=TruncDate('created_at')).values('author_id', 'd').distinct():
            days_map[row['author_id']].add(row['d'])
        for row in Comment.objects.filter(cf).annotate(d=TruncDate('created_at')).values('author_id', 'd').distinct():
            days_map[row['author_id']].add(row['d'])
        admap = {uid: len(s) for uid, s in days_map.items()}

        # ── ساعات آنلاین ──
        online_map = UserSession.total_seconds_in_period(all_user_ids, since)

        # ── امتیازدهی ──
        entries = []
        for g in all_profiles:
            ad  = admap.get(g.user_id, 0)
            os_ = online_map.get(g.user_id, 0)
            score = int(
                g.db_post_count    * cfg.post_score +
                g.db_comment_count * cfg.comment_score +
                ad                 * cfg.active_day_score +
                (os_ / 3600)       * cfg.online_hour_score
            )
            entries.append({
                'user_id':      g.user_id,
                'score':        score,
                'post_count':   g.db_post_count,
                'comment_count': g.db_comment_count,
                'active_days':  ad,
                'online_secs':  os_,
            })

        entries.sort(key=lambda e: -e['score'])

        saved = 0
        for rank, e in enumerate(entries, 1):
            LeaderboardSnapshot.objects.update_or_create(
                user_id     = e['user_id'],
                period_type = period,
                period_key  = period_key,
                defaults={
                    'rank':          rank,
                    'score':         e['score'],
                    'post_count':    e['post_count'],
                    'comment_count': e['comment_count'],
                    'active_days':   e['active_days'],
                    'online_secs':   e['online_secs'],
                },
            )
            saved += 1

        self.stdout.write(self.style.SUCCESS(
            f'✓ {saved} کاربر برای [{period}] {period_key} ذخیره شد.'
        ))
