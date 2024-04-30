from django.contrib import admin
from . import models
from django.utils.text import slugify


@admin.register(models.Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['user','user_id','slug', 'created', 'updated']
    search_fields = ('user__username','slug',)
    list_filter = ('updated',)
    exclude=('slug',)
