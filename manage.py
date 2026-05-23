#!/usr/bin/env python
"""
GameBeat manage.py
Auto-patches .pyc files to unchecked_hash mode before Django starts.
This fixes the macOS com.apple.provenance AMFI timeout issue (Iran + Apple servers blocked).
"""
import os
import sys


def _patch_pyc_files():
    """
    Convert all timestamp-based .pyc files to unchecked_hash mode.
    In unchecked_hash mode Python loads bytecode WITHOUT reading the source .py file,
    which bypasses the macOS AMFI security check that times out in Iran.
    Only runs on macOS (darwin). Silent on all other platforms.
    """
    if sys.platform != "darwin":
        return

    import struct
    try:
        import importlib.util
        MAGIC = importlib.util.MAGIC_NUMBER
    except Exception:
        return

    def _patch(path):
        try:
            with open(path, "rb") as f:
                data = f.read()
            if len(data) < 16 or data[:4] != MAGIC:
                return
            flags = struct.unpack("<I", data[4:8])[0]
            if flags == 1:
                return  # already unchecked_hash
            if flags == 3:
                new_data = data[:4] + struct.pack("<I", 1) + data[8:]
            elif flags == 0:
                new_data = data[:4] + struct.pack("<I", 1) + b"\x00" * 8 + data[16:]
            else:
                return
            with open(path, "wb") as f:
                f.write(new_data)
        except OSError:
            pass

    import site
    search_paths = list(site.getsitepackages()) + [os.path.dirname(os.path.abspath(__file__))]

    for base in search_paths:
        for root, dirs, files in os.walk(base):
            # skip venv / hidden dirs inside project
            dirs[:] = [d for d in dirs if d not in {".venv", "env", ".git", "staticfiles"}]
            if "__pycache__" not in root:
                continue
            for f in files:
                if f.endswith(".pyc"):
                    _patch(os.path.join(root, f))


# ── Patch BEFORE any Django import ──────────────────────────────────────────
_patch_pyc_files()


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gamebeat.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn\'t import Django. Are you sure it\'s installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
