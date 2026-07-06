from django.contrib.auth.models import User
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from dashboard.models import Game

from .models import Channel, Club, Hashtag, Post


class StaticViewSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'daily'
    priority = 0.8

    def items(self):
        return [
            'community:feed',
            'community:lfg',
            'community:leaderboard',
            'community:games_ranking',
            'community:clubs_list',
            'community:premium_info',
        ]

    def location(self, item):
        return reverse(item)


class PublicProfileSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return (
            User.objects
            .filter(gamer_profile__is_private=False)
            .select_related('gamer_profile')
            .order_by('-gamer_profile__updated_at', 'id')
        )

    def location(self, item):
        return reverse('community:profile', kwargs={'username': item.username})

    def lastmod(self, item):
        return getattr(item.gamer_profile, 'updated_at', item.date_joined)


class PublicPostSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return (
            Post.objects
            .filter(is_public=True, is_approved=True)
            .select_related('author')
            .order_by('-updated_at', '-created_at', 'id')
        )

    def location(self, item):
        return reverse('community:post_detail', kwargs={'post_id': item.pk})

    def lastmod(self, item):
        return item.updated_at or item.created_at


class GameSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Game.objects.filter(is_active=True)

    def location(self, item):
        return reverse('community:game_detail', kwargs={'game_id': item.pk})

    def lastmod(self, item):
        return item.updated_at or item.created_at


class ClubSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Club.objects.filter(is_public=True).order_by('-created_at', 'id')

    def location(self, item):
        return reverse('community:club_detail', kwargs={'slug': item.slug})

    def lastmod(self, item):
        return item.created_at


class ChannelSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'daily'
    priority = 0.7

    def items(self):
        return Channel.objects.filter(is_public=True).order_by('-updated_at', 'id')

    def location(self, item):
        return reverse('community:channel_view', kwargs={'channel_username': item.username})

    def lastmod(self, item):
        return item.updated_at


class HashtagSitemap(Sitemap):
    protocol = 'https'
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Hashtag.objects.filter(is_approved=True, post_count__gt=0).order_by('-post_count', 'id')

    def location(self, item):
        return reverse('community:hashtag_feed', kwargs={'tag_name': item.name})

    def lastmod(self, item):
        return item.created_at
