from django.db.models.signals import post_save
from django.dispatch import receiver


def _auto_unlock(user, trigger, current_value):
    """
    Checks all AchievementDefinitions with the given trigger whose target
    has been reached, and unlocks any levels the user doesn't have yet.
    """
    from .models import AchievementDefinition, Achievement, Notification
    from .models import ZarbanWallet, ZarbanTransaction

    defs = AchievementDefinition.objects.filter(
        trigger=trigger,
        is_active=True,
        target__lte=current_value,
        target__gt=0,
    ).order_by('ach_type', 'level')

    for defn in defs:
        already = Achievement.objects.filter(
            user=user,
            achievement_type=defn.ach_type,
            level=defn.level,
        ).exists()
        if already:
            continue

        Achievement.objects.create(
            user=user,
            achievement_type=defn.ach_type,
            level=defn.level,
            title=defn.title,
            description=defn.description,
            icon=defn.icon,
        )

        if defn.reward_zarban:
            wallet = ZarbanWallet.get_or_create_for(user)
            wallet.balance += defn.reward_zarban
            wallet.save(update_fields=['balance', 'updated_at'])
            ZarbanTransaction.objects.create(
                wallet=wallet,
                amount=defn.reward_zarban,
                tx_type=ZarbanTransaction.TX_CREDIT,
                reason=f'دستاورد: {defn.title} — سطح {defn.level}',
            )

        level_txt = f' (سطح {defn.level})' if defn.level > 1 else ''
        Notification.objects.create(
            recipient=user,
            sender=user,
            notif_type='zarban',
            custom_text=f'🏆 دستاورد جدید باز کردی: {defn.title}{level_txt}',
        )


@receiver(post_save, sender='community.Follow')
def on_follow_created(sender, instance, created, **kwargs):
    if not created:
        return
    target_user = instance.following
    count = sender.objects.filter(following=target_user).count()
    _auto_unlock(target_user, 'followers', count)


@receiver(post_save, sender='community.Post')
def on_post_created(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import Post
    count = Post.objects.filter(author=instance.author).count()
    _auto_unlock(instance.author, 'posts', count)


@receiver(post_save, sender='community.Comment')
def on_comment_created(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import Comment
    count = Comment.objects.filter(author=instance.author).count()
    _auto_unlock(instance.author, 'comments', count)


@receiver(post_save, sender='community.PostReaction')
def on_reaction_created(sender, instance, created, **kwargs):
    if not created:
        return
    from .models import PostReaction
    post_author = instance.post.author
    count = PostReaction.objects.filter(post__author=post_author).count()
    _auto_unlock(post_author, 'reactions_received', count)
