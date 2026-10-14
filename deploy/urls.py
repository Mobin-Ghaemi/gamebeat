from django.contrib import admin
from django.db import connection
from django.http import JsonResponse
from django.urls import include, path

def health(request):
    with connection.cursor() as c:
        c.execute('SELECT 1')
    return JsonResponse({'status':'ok'})

urlpatterns = [path('healthz/',health),path('admin/',admin.site.urls),path('account/',include('account.urls')),path('gamenet/',include('gamenet.urls')),path('admin-panel/',include('dashboard.urls')),path('',include('community.urls'))]
