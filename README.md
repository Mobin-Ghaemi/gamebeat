# GameBeat Community Platform

## شروع سریع

```bash
git clone <repo-url>
cd gamebeat
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

همین. روی همه سیستم‌ها (macOS، Linux، Windows) کار می‌کنه.

> **macOS در ایران**: `manage.py` خودکار یه fix اجرا می‌کنه که مشکل
> timeout سرورهای Apple رو حل می‌کنه. نیازی به کار اضافه نیست.

---

## Docker (اختیاری ولی توصیه‌شده برای تیم)

```bash
cp .env.example .env
docker compose up
```

→ http://localhost:8000

---

## دیپلوی روی لیارا

```bash
npm install -g @liara/cli
liara login
liara deploy --app YOUR_APP_NAME --port 8000
```

**در پنل لیارا این Disk ها رو بساز:**
- نام `media` — mount روی `/app/media`
- نام `db` — mount روی `/app/db`

**متغیرهای محیطی در پنل لیارا:**
```
DJANGO_SECRET_KEY=یه-کلید-تصادفی-بلند
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourapp.liara.run
DB_DIR=/app/db
```

---

## دستورات رایج

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic

# با Docker:
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

---

## ساختار پروژه

| فولدر | توضیح |
|-------|-------|
| `community/` | فید، پروفایل گیمری، پست، LFG |
| `account/` | ورود، ثبت‌نام، اشتراک |
| `gamenet/` | مدیریت گیم‌نت |
| `dashboard/` | پنل ادمین |
| `static/` | CSS، JS، فونت |
| `media/` | آپلودهای کاربران |
