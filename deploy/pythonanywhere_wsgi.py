"""Isi file WSGI di tab Web PythonAnywhere: salin seluruh isi file ini ke sana,
lalu ganti USERNAME dengan username PythonAnywhere Anda."""
import sys

PROJECT = "/home/USERNAME/finance-app"
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

from app.main import app as application  # noqa: E402,F401

# Fitur foto struk: tempel API key di server saja (JANGAN di-commit ke git).
# Gemini punya tingkat gratis: https://aistudio.google.com/apikey
# import os
# os.environ["GEMINI_API_KEY"] = "AIza..."
# atau (berbayar):
# os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."
