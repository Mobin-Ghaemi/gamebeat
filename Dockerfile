FROM python:3.11-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create media dir
RUN mkdir -p /app/media

EXPOSE 8000

# migrate موقع استارت اجرا می‌شود چون دیتابیس روی دیسک mount‌شده (runtime) قرار دارد
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn gamebeat.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --access-logfile -"]
