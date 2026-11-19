"""Login sederhana: satu password, sesi berbasis cookie yang ditandatangani."""
import hashlib
import hmac
import json
import os
import secrets
import time

from flask import Blueprint, jsonify, redirect, request, send_file

from . import db

COOKIE = "fa_sesi"
MASA_AKTIF = 7 * 24 * 3600  # detik
ITERASI = 200_000
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Halaman yang boleh diakses tanpa login.
PUBLIK = ("/login", "/api/login")

router = Blueprint("auth", __name__)


def _file_login() -> str:
    return os.path.join(os.path.dirname(db.DB_PATH), "login.json")


def muat_konfigurasi():
    """Mengembalikan dict konfigurasi login, atau None jika password belum dibuat."""
    try:
        with open(_file_login(), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERASI).hex()


def simpan_password(password: str) -> None:
    """Menyimpan hash password baru beserta kunci penandatangan sesi."""
    salt = secrets.token_bytes(16)
    cfg = {"salt": salt.hex(), "hash": _hash(password, salt), "secret": secrets.token_hex(32)}
    os.makedirs(os.path.dirname(_file_login()), exist_ok=True)
    with open(_file_login(), "w", encoding="utf-8") as f:
        json.dump(cfg, f)


def cek_password(password: str, cfg: dict) -> bool:
    salt = bytes.fromhex(cfg["salt"])
    return hmac.compare_digest(_hash(password, salt), cfg["hash"])


def _tanda(secret: str, isi: str) -> str:
    return hmac.new(secret.encode("utf-8"), isi.encode("utf-8"), hashlib.sha256).hexdigest()


def buat_token(secret: str) -> str:
    isi = str(int(time.time()) + MASA_AKTIF)
    return f"{isi}.{_tanda(secret, isi)}"


def token_valid(token: str, secret: str) -> bool:
    try:
        isi, tanda = token.split(".", 1)
        return hmac.compare_digest(tanda, _tanda(secret, isi)) and int(isi) > time.time()
    except (ValueError, AttributeError):
        return False


def _aman_cookie() -> bool:
    # Di balik proxy (PythonAnywhere, Cloudflare Tunnel) koneksi luar memakai https.
    return request.headers.get("x-forwarded-proto") == "https" or request.is_secure


def pasang(app):
    """Memasang pemeriksaan login ke semua permintaan."""

    @app.before_request
    def cek_login():
        path = request.path
        if path in PUBLIK:
            return None

        cfg = muat_konfigurasi()
        token = request.cookies.get(COOKIE)
        if cfg and token and token_valid(token, cfg["secret"]):
            return None

        if path.startswith("/api/"):
            return jsonify(detail="Belum login."), 401
        return redirect("/login", code=303)


@router.get("/login")
def halaman_login():
    return send_file(os.path.join(STATIC, "login.html"))


@router.post("/api/login")
def login():
    cfg = muat_konfigurasi()
    if cfg is None:
        return jsonify(detail="Password belum dibuat. Jalankan atur_password.py."), 503
    body = request.get_json(silent=True)
    password = body.get("password") if isinstance(body, dict) else None
    if not isinstance(password, str):
        return jsonify(detail="password: wajib diisi."), 422
    if not cek_password(password, cfg):
        time.sleep(1)  # perlambat tebakan password
        return jsonify(detail="Password salah."), 401

    resp = jsonify(ok=True)
    resp.set_cookie(
        COOKIE,
        buat_token(cfg["secret"]),
        max_age=MASA_AKTIF,
        httponly=True,
        samesite="Lax",
        secure=_aman_cookie(),
    )
    return resp


@router.post("/api/logout")
def logout():
    resp = jsonify(ok=True)
    resp.delete_cookie(COOKIE)
    return resp
