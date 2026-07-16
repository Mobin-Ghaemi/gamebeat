from django.contrib import admin
from django.utils.html import format_html
from .models import GamerProfile, Post, PostLike, Comment, Follow, LFGPost, LFGFeedback, Achievement
from .models import Challenge, Club, ClubMember, ClubPost, ActivityLog, ScoreSettings
from .models import DailyMission, DailyMissionProgress, MissionDay
from .models import AchievementDefinition, GameReview, Report
from .models import TomanWallet, TomanWalletTransaction, SteamMarketListing


@admin.register(MissionDay)
class MissionDayAdmin(admin.ModelAdmin):
    list_display = ('day_number', 'label', 'is_active')
    list_editable = ('label', 'is_active')
    ordering = ('day_number',)


@admin.register(DailyMission)
class DailyMissionAdmin(admin.ModelAdmin):
    list_display = ('title', 'day', 'event', 'target_count', 'reward_zarban', 'is_active', 'order')
    list_editable = ('target_count', 'reward_zarban', 'is_active', 'order')
    list_filter = ('event', 'is_active', 'day')
    search_fields = ('title',)


@admin.register(DailyMissionProgress)
class DailyMissionProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'mission', 'date', 'progress', 'claimed')
    list_filter = ('date', 'claimed', 'mission')
    search_fields = ('user__username',)
    date_hierarchy = 'date'

admin.site.register(Post)
admin.site.register(PostLike)
admin.site.register(Comment)
admin.site.register(Follow)
@admin.register(LFGPost)
class LFGPostAdmin(admin.ModelAdmin):
    list_display = ('game_name', 'author', 'platform', 'skill_level', 'current_players', 'max_players', 'is_approved', 'is_active', 'created_at')
    list_editable = ('is_approved', 'is_active')
    list_filter = ('is_approved', 'is_active', 'platform', 'skill_level', 'voice_required')
    search_fields = ('game_name', 'author__username', 'description', 'contact')
    date_hierarchy = 'created_at'


@admin.register(LFGFeedback)
class LFGFeedbackAdmin(admin.ModelAdmin):
    list_display = ('lfg_post', 'reviewer', 'reviewee', 'result', 'is_reviewed', 'created_at')
    list_editable = ('is_reviewed',)
    list_filter = ('result', 'is_reviewed')
    search_fields = ('lfg_post__game_name', 'reviewer__username', 'reviewee__username', 'note')
    date_hierarchy = 'created_at'


@admin.register(GameReview)
class GameReviewAdmin(admin.ModelAdmin):
    list_display = ('game_name', 'user', 'rating', 'is_approved', 'is_featured', 'created_at')
    list_editable = ('is_approved', 'is_featured')
    list_filter = ('is_approved', 'is_featured', 'rating')
    search_fields = ('game_name', 'user__username', 'body')
    date_hierarchy = 'created_at'
@admin.register(AchievementDefinition)
class AchievementDefinitionAdmin(admin.ModelAdmin):
    list_display       = ('order', 'icon_preview', 'title', 'ach_type', 'description', 'reward_zarban', 'is_active')
    list_editable      = ('title', 'description', 'reward_zarban', 'is_active', 'order')
    list_display_links = ('ach_type',)
    ordering           = ('order',)
    search_fields      = ('title', 'ach_type')
    list_filter        = ('is_active',)
    fields             = ('ach_type', 'title', 'description', 'icon', 'reward_zarban', 'is_active', 'order')

    def icon_preview(self, obj):
        return format_html('<i class="bi {}" style="font-size:1.3rem;color:#a78bfa;"></i>', obj.icon)
    icon_preview.short_description = '🎨'


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display  = ('user', 'achievement_type', 'title', 'earned_at')
    list_filter   = ('achievement_type',)
    search_fields = ('user__username', 'title')
    date_hierarchy = 'earned_at'
    readonly_fields = ('earned_at',)
admin.site.register(ActivityLog)
admin.site.register(Club)
admin.site.register(ClubMember)
admin.site.register(ClubPost)
admin.site.register(TomanWallet)
admin.site.register(TomanWalletTransaction)
admin.site.register(SteamMarketListing)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'target_type', 'target_summary', 'reporter', 'reason', 'status', 'created_at')
    list_editable = ('status',)
    list_filter = ('target_type', 'reason', 'status', 'created_at')
    search_fields = ('reporter__username', 'target_user__username', 'details', 'admin_note', 'post__content', 'comment__content', 'message__content')
    readonly_fields = ('reporter', 'target_type', 'post', 'comment', 'target_user', 'message', 'reason', 'details', 'created_at')
    date_hierarchy = 'created_at'

    @admin.display(description='مورد گزارش')
    def target_summary(self, obj):
        target = obj.post or obj.comment or obj.target_user or obj.message
        return str(target)[:80] if target else '-'


@admin.register(GamerProfile)
class GamerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'display_name', 'is_verified', 'rank', 'created_at')
    list_editable = ('is_verified',)
    list_filter = ('is_verified', 'rank', 'platform')
    search_fields = ('user__username', 'nickname')


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ('title', 'challenge_type', 'start_date', 'end_date', 'is_active')
    list_filter = ('challenge_type', 'is_active')
    search_fields = ('title',)


@admin.register(ScoreSettings)
class ScoreSettingsAdmin(admin.ModelAdmin):
    """
    Singleton admin — فقط یک ردیف قابل ویرایش است.
    دکمه‌های Add و Delete حذف شده‌اند.
    """
    fieldsets = (
        ('💓 ضریب ضربان لیدربورد', {
            'description': (
                'این مقادیر در محاسبه رتبه‌بندی لیدربورد استفاده می‌شوند. '
                'تغییرات بلافاصله اعمال می‌شود.'
            ),
            'fields': ('post_score', 'comment_score', 'active_day_score'),
        }),
        ('اطلاعات', {
            'fields': ('updated_at',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('updated_at',)

    def formula_preview(self, obj):
        return format_html(
            '<span style="font-size:1rem; font-weight:700;">'
            '📝 پست × <b style="color:#fb923c;">{}</b> &nbsp;|&nbsp; '
            '💬 کامنت × <b style="color:#fb923c;">{}</b> &nbsp;|&nbsp; '
            '📅 روز فعال × <b style="color:#a78bfa;">{}</b>'
            '</span>',
            obj.post_score, obj.comment_score, obj.active_day_score,
        )
    formula_preview.short_description = 'فرمول فعلی'

    list_display = ('formula_preview', 'updated_at')

    # ── Singleton: جلوگیری از Add و Delete ──
    def has_add_permission(self, request):
        return not ScoreSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_object(self, request, object_id, *args, **kwargs):
        # همیشه pk=1 برگردان
        return ScoreSettings.get()

    def changelist_view(self, request, extra_context=None):
        # اگر رکورد وجود دارد مستقیم به صفحه ویرایش برو
        obj, _ = ScoreSettings.objects.get_or_create(pk=1)
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(
            reverse('admin:community_scoresettings_change', args=[obj.pk])
        )
