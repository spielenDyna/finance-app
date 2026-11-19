"""Isi file WSGI di tab Web PythonAnywhere: salin seluruh isi file ini ke sana,
lalu ganti USERNAME dengan username PythonAnywhere Anda."""
import sys

PROJECT = "/home/USERNAME/finance-app"
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

from a2wsgi import ASGIMiddleware  # noqa: E402

from app import db  # noqa: E402
from app.main import app as asgi_app  # noqa: E402

db.init_db()  # lifespan FastAPI tidak berjalan di WSGI, jadi skema dibuat di sini
application = ASGIMiddleware(asgi_app)
