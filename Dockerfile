FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBUG=False \
    DB_DIR=/app/db \
    MEDIA_ROOT=/app/media \
    DJANGO_ALLOWED_HOSTS="localhost 127.0.0.1 .liara.run .gamebeat.ir" \
    DJANGO_CSRF_TRUSTED_ORIGINS="https://*.liara.run https://gamebeat.ir https://www.gamebeat.ir"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Runtime dirs
RUN mkdir -p /app/media /app/db /app/staticfiles

# Collect static files
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# migrate موقع استارت اجرا می‌شود چون دیتابیس روی دیسک mount‌شده (runtime) قرار دارد
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn gamebeat.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --access-logfile - --error-logfile -"]
