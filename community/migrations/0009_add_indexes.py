from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0008_profile_platforms'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='post',
            index=models.Index(fields=['author', '-created_at'], name='post_author_created_idx'),
        ),
        migrations.AddIndex(
            model_name='post',
            index=models.Index(fields=['is_public', '-created_at'], name='post_public_created_idx'),
        ),
        migrations.AddIndex(
            model_name='post',
            index=models.Index(fields=['-created_at'], name='post_created_idx'),
        ),
        migrations.AddIndex(
            model_name='gamebacklog',
            index=models.Index(fields=['user', 'status'], name='backlog_user_status_idx'),
        ),
        migrations.AddIndex(
            model_name='gamebacklog',
            index=models.Index(fields=['user', 'is_favorite'], name='backlog_user_fav_idx'),
        ),
        migrations.AddIndex(
            model_name='gamebacklog',
            index=models.Index(fields=['user', '-updated_at'], name='backlog_user_updated_idx'),
        ),
        migrations.AddIndex(
            model_name='follow',
            index=models.Index(fields=['follower'], name='follow_follower_idx'),
        ),
        migrations.AddIndex(
            model_name='follow',
            index=models.Index(fields=['following'], name='follow_following_idx'),
        ),
    ]
