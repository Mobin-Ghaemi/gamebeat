#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""
    # اگر کاربر با پایتون اشتباه manage.py را اجرا کند،
    # به‌صورت خودکار با وِنوِ پروژه اجرا شود.
    project_root = Path(__file__).resolve().parent.parent
    preferred_python = project_root / '.venv' / 'bin' / 'python'
    if preferred_python.exists():
        current = Path(sys.executable).resolve()
        preferred = preferred_python.resolve()
        if current != preferred:
            os.execv(str(preferred), [str(preferred), str(Path(__file__).resolve()), *sys.argv[1:]])

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gamebeat.settings')

    # سرعت اجرای runserver در این پروژه با autoreload پایین است (به‌خصوص با فولدرهای حجیم).
    # برای اجرای سریع‌تر، به‌صورت پیش‌فرض autoreload غیرفعال می‌شود.
    if len(sys.argv) > 1 and sys.argv[1] == 'runserver' and '--noreload' not in sys.argv:
        sys.argv.append('--noreload')

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
