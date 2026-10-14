from django.db import connection
from django.http import JsonResponse

class HealthCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path_info != '/healthz/':
            return self.get_response(request)
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            return JsonResponse({'status':'ok'})
        except Exception:
            return JsonResponse({'status':'unavailable'},status=503)
