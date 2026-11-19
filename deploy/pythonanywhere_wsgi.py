"""Isi file WSGI di tab Web PythonAnywhere: salin seluruh isi file ini ke sana,
lalu ganti USERNAME dengan username PythonAnywhere Anda."""
import sys

PROJECT = "/home/USERNAME/finance-app"
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

from app.main import app as application  # noqa: E402,F401
