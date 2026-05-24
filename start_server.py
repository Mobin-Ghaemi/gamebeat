#!/usr/bin/env python3
"""
GameBeat startup script.
Run: python3 start_server.py [port]

Automatically patches any TIMESTAMP-based .pyc files to unchecked_hash mode
(bypasses macOS com.apple.provenance AMFI checks that timeout in Iran).
"""
import struct, os, sys
import importlib.util

MAGIC = importlib.util.MAGIC_NUMBER
PROJECT = os.path.dirname(os.path.abspath(__file__))
SITEPACKAGES = '/opt/homebrew/lib/python3.13/site-packages'

def patch_pyc(pyc_path):
    """Patch a .pyc from timestamp/checked_hash mode to unchecked_hash."""
    try:
        with open(pyc_path, 'rb') as f:
            data = f.read()
        if len(data) < 16 or data[:4] != MAGIC:
            return False
        flags = struct.unpack('<I', data[4:8])[0]
        if flags == 1:
            return True  # already OK
        elif flags == 3:
            new_data = data[:4] + struct.pack('<I', 1) + data[8:]
        elif flags == 0:
            new_data = data[:4] + struct.pack('<I', 1) + b'\x00' * 8 + data[16:]
        else:
            return False
        with open(pyc_path, 'wb') as f:
            f.write(new_data)
        return True
    except Exception:
        return False

def patch_all():
    patched = 0
    # Patch project .pyc files
    for root, dirs, files in os.walk(PROJECT):
        dirs[:] = [d for d in dirs if d not in {'.venv','env','.git','staticfiles','.claude'}]
        if '__pycache__' not in root:
            continue
        for f in files:
            if f.endswith('.pyc'):
                if patch_pyc(os.path.join(root, f)):
                    patched += 1
    # Patch site-packages .pyc files
    for root, dirs, files in os.walk(SITEPACKAGES):
        if '__pycache__' not in root:
            continue
        for f in files:
            if f.endswith('.pyc'):
                if patch_pyc(os.path.join(root, f)):
                    patched += 1
    return patched

print("🔧 Patching .pyc files to unchecked_hash mode...", flush=True)
n = patch_all()
print(f"✅ Patched {n} files", flush=True)

# Now run Django
sys.path.insert(0, PROJECT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gamebeat.settings')
from django.core.management import execute_from_command_line

port = sys.argv[1] if len(sys.argv) > 1 else '8000'
print(f"🚀 Starting GameBeat on http://127.0.0.1:{port}/", flush=True)
execute_from_command_line(['manage.py', 'runserver', f'0.0.0.0:{port}'])
