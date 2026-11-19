"""Isi file WSGI di tab Web PythonAnywhere: salin seluruh isi file ini ke sana,
lalu ganti USERNAME dengan username PythonAnywhere Anda."""
import sys

PROJECT = "/home/USERNAME/finance-app"
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

from app.main import app as application  # noqa: E402,F401

# Fitur foto struk: tempel API key Anthropic di server saja (JANGAN di-commit ke git).
# import os
# os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
