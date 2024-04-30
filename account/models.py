from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
import uuid
import jdatetime
import random
import string

class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='کاربر')
    body = models.TextField(verbose_name='توضیحات')
    slug = models.SlugField(unique=True, max_length=150, blank=True) 
    created = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated = models.DateTimeField(auto_now=True, verbose_name='تاریخ اخرین ویرایش')

    def __str__(self):
        return f'{self.user} - {self.updated}'

    def save(self, *args, **kwargs):
        if not self.slug: 
            base_slug = slugify(self.user.username)  
            random_code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))  # ایجاد کد رندم
            unique_slug = f'{base_slug}-{random_code}'  
            self.slug = unique_slug
        super().save(*args, **kwargs)
