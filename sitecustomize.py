"""
sitecustomize.py - Patches importlib to bypass macOS com.apple.provenance timeout
"""
import importlib.abc
import importlib._bootstrap_external as _ext

_orig_get_data = _ext.FileLoader.get_data

def _patched_get_data(self, path):
    try:
        # Try the original first
        import _io
        with _io.FileIO(path, 'r') as f:
            return f.read()
    except OSError:
        # Fallback: use regular open() which bypasses provenance check
        with open(path, 'rb') as f:
            return f.read()

_ext.FileLoader.get_data = _patched_get_data
