#!/usr/bin/env python
"""
GameBeat manage.py
Auto-patches .pyc files to unchecked_hash mode before Django starts.
Fixes macOS com.apple.provenance AMFI timeout (Apple servers blocked in Iran).
"""
import os
import sys


def _patch_pyc_files():
    """
    Patch .pyc files once per hour — result cached in .pyc_patched timestamp.
    On macOS only. Silent everywhere else.
    """
    if sys.platform != "darwin":
        return

    import struct
    import time

    base_dir = os.path.dirname(os.path.abspath(__file__))
    stamp_file = os.path.join(base_dir, ".pyc_patched")

    # Skip if patched within the last hour
    try:
        if time.time() - os.path.getmtime(stamp_file) < 3600:
            return
    except OSError:
        pass

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
                return
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
    search_paths = []

    # .venv / venv / env inside project
    for venv_name in (".venv", "venv", "env"):
        venv_lib = os.path.join(base_dir, venv_name, "lib")
        if os.path.isdir(venv_lib):
            for entry in os.listdir(venv_lib):
                sp = os.path.join(venv_lib, entry, "site-packages")
                if os.path.isdir(sp):
                    search_paths.append(sp)

    # system site-packages
    try:
        search_paths.extend(site.getsitepackages())
    except AttributeError:
        pass

    # project directory
    search_paths.append(base_dir)

    for base in search_paths:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs
                       if d not in {".venv", "venv", "env", ".git", "staticfiles", "media"}]
            if "__pycache__" not in root:
                continue
            for f in files:
                if f.endswith(".pyc"):
                    _patch(os.path.join(root, f))

    # Write timestamp so next startup skips this
    try:
        with open(stamp_file, "w") as f:
            f.write(str(time.time()))
    except OSError:
        pass


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
