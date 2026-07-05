from django.db import migrations


def seed_engagement_missions(apps, schema_editor):
    DailyMission = apps.get_model('community', 'DailyMission')
    missions = [
        {
            'title': 'یک LFG بساز',
            'description': 'برای بازی امروزت دنبال هم‌تیمی بگرد',
            'event': 'lfg_create',
            'target_count': 1,
            'reward_zarban': 12,
            'icon': 'bi-people-fill',
            'order': 20,
        },
        {
            'title': 'هایلایت امروز',
            'description': 'یک کلیپ یا لحظه خوب از بازیت منتشر کن',
            'event': 'highlight',
            'target_count': 1,
            'reward_zarban': 15,
            'icon': 'bi-camera-video-fill',
            'order': 21,
        },
        {
            'title': 'نظر واقعی درباره بازی',
            'description': 'برای یکی از بازی‌ها ریویو بنویس',
            'event': 'review',
            'target_count': 1,
            'reward_zarban': 10,
            'icon': 'bi-star-fill',
            'order': 22,
        },
    ]
    for data in missions:
        DailyMission.objects.get_or_create(
            day=None,
            event=data['event'],
            title=data['title'],
            defaults=data,
        )


def remove_engagement_missions(apps, schema_editor):
    DailyMission = apps.get_model('community', 'DailyMission')
    DailyMission.objects.filter(event__in=['lfg_create', 'highlight', 'review']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0058_gamereview_is_approved_gamereview_is_featured_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_engagement_missions, remove_engagement_missions),
    ]
