from django.db import migrations


DEFAULT_MISSIONS = [
    # (title, description, event, target, reward, icon, order)
    ('ورود روزانه', 'امروز سر زدی — جایزه‌ت رو بگیر!', 'login', 1, 10, 'bi-calendar-check', 1),
    ('یه پست بذار', 'یک پست توی فید منتشر کن', 'post', 1, 15, 'bi-pencil-square', 2),
    ('۳ تا کامنت بذار', 'روی پست‌های گیمرها کامنت بذار', 'comment', 3, 15, 'bi-chat-dots', 3),
    ('یه گیمر دنبال کن', 'یک گیمر جدید رو فالو کن', 'follow', 1, 10, 'bi-person-plus', 4),
    ('۵ تا واکنش بده', 'به پست‌های گیمرها واکنش نشون بده', 'react', 5, 10, 'bi-heart-fill', 5),
    ('به یه LFG بپیوند', 'به یک پارتی LFG ملحق شو', 'lfg_join', 1, 20, 'bi-people-fill', 6),
]


def seed_missions(apps, schema_editor):
    DailyMission = apps.get_model('community', 'DailyMission')
    for title, desc, event, target, reward, icon, order in DEFAULT_MISSIONS:
        DailyMission.objects.get_or_create(
            title=title,
            defaults={
                'description': desc,
                'event': event,
                'target_count': target,
                'reward_zarban': reward,
                'icon': icon,
                'order': order,
                'is_active': True,
            },
        )


def unseed_missions(apps, schema_editor):
    DailyMission = apps.get_model('community', 'DailyMission')
    DailyMission.objects.filter(title__in=[m[0] for m in DEFAULT_MISSIONS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0047_dailymission_dailymissionprogress'),
    ]

    operations = [
        migrations.RunPython(seed_missions, unseed_missions),
    ]
