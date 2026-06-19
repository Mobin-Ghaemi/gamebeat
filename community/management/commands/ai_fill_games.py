# -*- coding: utf-8 -*-
"""
پر کردن نام فارسی و پلتفرم بازی‌ها با کمک AI (AvalAI).
اجرا:
    python manage.py ai_fill_games                # همه‌ی بازی‌ها
    python manage.py ai_fill_games --missing-only  # فقط بازی‌های بدون نام فارسی (صرفه‌جویی هزینه)
"""
from django.core.management.base import BaseCommand
from dashboard.models import Game
from community.ai_service import ai_game_info


class Command(BaseCommand):
    help = 'پر کردن name_fa و پلتفرم بازی‌ها با AI'

    def add_arguments(self, parser):
        parser.add_argument('--missing-only', action='store_true',
                            help='فقط بازی‌هایی که name_fa ندارند')
        parser.add_argument('--desc-only', action='store_true',
                            help='فقط بازی‌هایی که توضیح فارسی ندارند')
        parser.add_argument('--resume', action='store_true',
                            help='بازی‌هایی که توضیح فارسی دارند را رد کن (ادامه از جای قبل)')
        parser.add_argument('--limit', type=int, default=0, help='حداکثر تعداد')

    @staticmethod
    def _has_persian(text):
        return any('؀' <= ch <= 'ۿ' for ch in (text or '')[:40])

    def handle(self, *args, **opts):
        qs = Game.objects.all()
        if opts['missing_only']:
            qs = qs.filter(name_fa='')
        if opts['desc_only']:
            qs = qs.filter(description='')
        if opts['limit']:
            qs = qs[:opts['limit']]

        total = name_fa = plat = desc = skipped = 0
        for g in qs:
            # resume: اگر توضیح فارسی دارد، رد کن
            if opts['resume'] and self._has_persian(g.description):
                skipped += 1
                continue
            info = ai_game_info(g.name)
            total += 1
            if not info:
                continue
            changed = []
            if info.get('name_fa'):
                g.name_fa = info['name_fa']
                name_fa += 1
                changed.append('name_fa')
            existing = list(g.platforms or [])
            merged = list(dict.fromkeys(existing + info.get('platforms', [])))
            if merged != existing:
                g.platforms = merged
                plat += 1
                changed.append('platforms')
            if info.get('description'):
                g.description = info['description']
                desc += 1
                changed.append('description')
            if changed:
                g.save(update_fields=changed)
            self.stdout.write(f'  {g.name[:38]:40} {info.get("name_fa","")}')
        self.stdout.write(self.style.SUCCESS(
            f'انجام شد — {total} پردازش | name_fa: {name_fa} | پلتفرم: {plat} | توضیح: {desc} | رد(resume): {skipped}'
        ))
