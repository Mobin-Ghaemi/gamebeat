#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""
    # اگر کاربر بیرون از هر virtualenv باشد،
    # به‌صورت خودکار با وِنوِ پروژه اجرا شود.
    # اما اگر از قبل یک virtualenv فعال باشد (مثل env/)،
    # همان محیط فعلی حفظ شود.
    project_root = Path(__file__).resolve().parent
    preferred_python = project_root / '.venv' / 'bin' / 'python'
    in_virtualenv = getattr(sys, "base_prefix", sys.prefix) != sys.prefix
    if preferred_python.exists() and not in_virtualenv:
        preferred_venv = (project_root / '.venv').resolve()
        current_prefix = Path(getattr(sys, "prefix", "")).resolve()
        if current_prefix != preferred_venv:
            os.execv(
                str(preferred_python),
                [str(preferred_python), str(Path(__file__).resolve()), *sys.argv[1:]],
            )

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
