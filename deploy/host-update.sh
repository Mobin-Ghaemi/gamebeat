#!/usr/bin/env bash
# Invocation authorizes resetting tracked source changes and a short outage.
set -Eeuo pipefail
umask 077
SOURCE_DIR=${GAMEBEAT_SOURCE_DIR:-/root/gamebeat}
DEPLOY_DIR=${GAMEBEAT_DEPLOY_DIR:-/srv/apps/gamebeat}
cd "$DEPLOY_DIR"
if (( EUID != 0 )); then
    echo 'این دستور باید با دسترسی root یا sudo اجرا شود.' >&2
    exit 1
fi
if (( $# != 0 )); then
    echo 'روش اجرا: ./update — آرگومان اضافی پذیرفته نمی‌شود.' >&2
    exit 1
fi
exec 9>/run/lock/gamebeat-update.lock
flock -n 9 || { echo 'یک به‌روزرسانی دیگر در حال اجراست.' >&2; exit 1; }
release="$DEPLOY_DIR/releases/$(date -u +%Y%m%dT%H%M%SZ)-$$"
install -d -m 0700 "$release"
exec > >(tee -a "$release/update.log") 2>&1
stopped=false
migration_started=false
dc() { docker compose --project-directory "$DEPLOY_DIR" -f "$DEPLOY_DIR/compose.yaml" "$@"; }
candidate() { docker compose --project-directory "$DEPLOY_DIR" -f "$DEPLOY_DIR/compose.yaml" -f "$release/image.json" "$@"; }
restore_wrapper() { install -m 0755 "$DEPLOY_DIR/update-wrapper" "$SOURCE_DIR/update"; }
failure() {
    code=$?
    trap - EXIT
    if (( code != 0 )); then
        set +e
        restore_wrapper
        if "$stopped"; then
            if "$migration_started"; then
                candidate stop web
                echo 'به‌روزرسانی پس از شروع migration شکست خورد؛ وب متوقف می‌ماند.'
                echo 'بازگشت خودکار دیتابیس انجام نشد؛ برای جلوگیری از ناسازگاری، بررسی و بازیابی دستی لازم است.'
            else
                dc up -d --wait --wait-timeout 90 db web
                echo 'برای راه‌اندازی دوباره نسخه قبلی تلاش شد؛ نتیجه را در لاگ بررسی کنید.'
            fi
        else
            echo 'به‌روزرسانی پیش از توقف سرویس شکست خورد؛ سرویس قبلی متوقف نشد.'
        fi
        echo "مسیر گزارش و اطلاعات نسخه قبلی: $release"
    fi
    exit "$code"
}
trap failure EXIT
for command in git docker python3 curl nginx systemctl flock; do command -v "$command" >/dev/null; done
available=$(df -B1 --output=avail "$DEPLOY_DIR" | tail -1 | tr -d ' ')
(( available >= 8589934592 )) || { echo 'حداقل ۸ GiB فضای آزاد لازم است.'; exit 1; }
[[ -f "$DEPLOY_DIR/app.env" && -d "$DEPLOY_DIR/secrets" && -d "$DEPLOY_DIR/deploy-overlay" ]]
dc config -q
nginx -t
[[ $(dc ps --status running --services) == *web* ]] || { echo 'وب فعلی اجرا نیست؛ ابتدا وضعیت سرویس را بررسی کنید.'; exit 1; }
cp -p "$DEPLOY_DIR/compose.yaml" "$release/previous-compose.yaml"
git -C "$SOURCE_DIR" rev-parse HEAD > "$release/previous-commit.txt"
container=$(dc ps -q web)
docker inspect --format '{{.Config.Image}}' "$container" > "$release/previous-image.txt"
branch=$(git -C "$SOURCE_DIR" symbolic-ref --quiet --short HEAD)
echo "دریافت نسخه جدید شاخه $branch ..."
# Interactive credentials are disabled; failure leaves the site running.
GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false SSH_ASKPASS=/bin/false GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=15' git -C "$SOURCE_DIR" fetch origin "$branch"
target=$(git -C "$SOURCE_DIR" rev-parse --verify 'FETCH_HEAD^{commit}')
printf '%s\n' "$target" > "$release/target-commit.txt"
echo 'بازنشانی فایل‌های تحت کنترل Git به نسخه دریافت‌شده ...'
git -C "$SOURCE_DIR" reset --hard "$target"
# These VPS files are managed outside Git so reset cannot remove deployment.
install -d -m 0755 "$SOURCE_DIR/deploy"
cp -a "$DEPLOY_DIR/deploy-overlay/." "$SOURCE_DIR/deploy/"
install -m 0644 "$DEPLOY_DIR/deploy-overlay/dockerignore" "$SOURCE_DIR/.dockerignore"
restore_wrapper
image="gamebeat-web:$(date -u +%Y%m%dT%H%M%SZ)-${target:0:12}-$$"
python3 - "$release/image.json" "$image" <<'PY'
import json,sys
from pathlib import Path
Path(sys.argv[1]).write_text(json.dumps({'services':{'web':{'image':sys.argv[2]}}})+'\n')
PY
echo 'ساخت تصویر و نصب پکیج‌های requirements نسخه جدید؛ سایت هنوز فعال است ...'
docker build --file "$DEPLOY_DIR/deploy-overlay/Dockerfile" --tag "$image" "$SOURCE_DIR"
docker run --rm --network none --memory 512m --cpus 1 --entrypoint pip "$image" freeze > "$release/requirements.lock"
candidate run --rm --no-deps web python manage.py check
echo 'شروع توقف کوتاه وب پیش از migration ...'
stopped=true
dc stop -t 30 web
echo 'راه‌اندازی دوباره PostgreSQL و انتظار برای سلامت آن ...'
dc restart db
dc up -d --wait --wait-timeout 90 db
echo 'اجرای migration نسخه جدید ...'
migration_started=true
candidate run --rm --no-deps web python manage.py migrate --noinput
candidate run --rm --no-deps web python manage.py collectstatic --noinput
echo 'اجرای نسخه جدید و بررسی سلامت ...'
candidate up -d --no-build --force-recreate --wait --wait-timeout 120 web
nginx -t
systemctl reload nginx
curl --noproxy '*' --fail --silent --show-error --max-time 20 http://127.0.0.1:18002/healthz/ > "$release/health.json"
python3 - "$release/health.json" "$DEPLOY_DIR/compose.yaml" "$image" <<'PY'
import json,re,sys,os,tempfile
from pathlib import Path
assert json.loads(Path(sys.argv[1]).read_text()) == {'status':'ok'}, 'Health check failed'
p=Path(sys.argv[2])
text,count=re.subn(r'(?m)(^  web:\n    image: )[^\n]+',lambda m:m[1]+sys.argv[3],p.read_text(),count=1)
if count!=1: raise RuntimeError('Cannot safely update web image in Compose')
fd,temporary=tempfile.mkstemp(dir=p.parent,prefix='.compose-update-')
try:
    with os.fdopen(fd,'w') as stream: stream.write(text)
    os.chmod(temporary,p.stat().st_mode & 0o777)
    os.replace(temporary,p)
finally:
    Path(temporary).unlink(missing_ok=True)
PY
dc config -q
printf '%s\n' "$image" > "$release/deployed-image.txt"
date -u +%FT%TZ > "$release/success.txt"
stopped=false
echo "به‌روزرسانی موفق بود. نسخه: ${target:0:12}"
echo "لاگ و نسخه پکیج‌ها: $release"
