"""Uji login: API dan halaman harus terkunci sampai password benar."""
import os
import tempfile

os.environ["FINANCE_DB"] = os.path.join(tempfile.mkdtemp(), "login.db")

from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app.main import app  # noqa: E402


def test_belum_login_ditolak():
    auth.simpan_password("rahasia-123")
    with TestClient(app, follow_redirects=False) as c:
        assert c.get("/api/bahan").status_code == 401
        r = c.get("/")
        assert r.status_code == 303 and r.headers["location"] == "/login"


def test_password_salah_ditolak():
    auth.simpan_password("rahasia-123")
    with TestClient(app) as c:
        assert c.post("/api/login", json={"password": "salah"}).status_code == 401
        assert c.get("/api/bahan").status_code == 401


def test_login_lalu_logout():
    auth.simpan_password("rahasia-123")
    with TestClient(app) as c:
        assert c.post("/api/login", json={"password": "rahasia-123"}).status_code == 200
        assert c.get("/api/bahan").status_code == 200
        assert c.post("/api/logout").status_code == 200
        c.cookies.clear()
        assert c.get("/api/bahan").status_code == 401


def test_token_kedaluwarsa_dan_dipalsukan():
    token = auth.buat_token("kunci")
    assert auth.token_valid(token, "kunci")
    assert not auth.token_valid(token, "kunci-lain")
    isi, _ = token.split(".", 1)
    assert not auth.token_valid(f"{int(isi) - 10**9}.{token.split('.', 1)[1]}", "kunci")


def test_halaman_login_bisa_dibuka():
    with TestClient(app) as c:
        r = c.get("/login")
        assert r.status_code == 200 and "Password" in r.text
