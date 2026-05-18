from django.contrib import admin
from .models import GamerProfile, Post, PostLike, Comment, Follow, LFGPost, Achievement

admin.site.register(GamerProfile)
admin.site.register(Post)
admin.site.register(PostLike)
admin.site.register(Comment)
admin.site.register(Follow)
admin.site.register(LFGPost)
admin.site.register(Achievement)
