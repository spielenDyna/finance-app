"""Uji fitur foto struk: pembacaan (dengan API dipalsukan) dan penyimpanan massal."""
import os
import tempfile

import pytest

os.environ["FINANCE_DB"] = os.path.join(tempfile.mkdtemp(), "struk.db")

from app import auth, struk  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def c():
    auth.simpan_password("uji-rahasia")
    with app.test_client() as client:
        assert client.post("/api/login", json={"password": "uji-rahasia"}).status_code == 200
        yield client


def test_struk_butuh_login():
    with app.test_client() as anon:
        assert anon.post("/api/struk/baca", data=b"x", content_type="image/jpeg").status_code == 401


def test_tanpa_api_key_ditolak_rapi(c, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = c.post("/api/struk/baca", data=b"abc", content_type="image/jpeg")
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.get_json()["detail"]


def test_format_bukan_gambar_ditolak(c):
    r = c.post("/api/struk/baca", data=b"abc", content_type="application/pdf")
    assert r.status_code == 415


def test_baca_membersihkan_bahan_id_tak_dikenal(c, monkeypatch):
    sel = c.post("/api/bahan", json={"nama": "Gula", "satuan": "gram"}).get_json()["id"]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "palsu")

    class Blok:
        type = "text"
        text = ('{"tanggal":"2026-11-01","pemasok":"Toko A","item":['
                f'{{"nama_struk":"GULA 1KG","jumlah":2,"total":30000,"bahan_id":{sel},"qty_bahan":2000}},'
                '{"nama_struk":"X","jumlah":1,"total":5000,"bahan_id":999,"qty_bahan":5}]}')

    class Resp:
        content = [Blok()]
        stop_reason = "end_turn"

    class Klien:
        class messages:
            @staticmethod
            def create(**kw):
                assert kw["model"] and kw["messages"][0]["content"][0]["type"] == "image"
                return Resp()

    monkeypatch.setattr(struk.anthropic, "Anthropic", lambda **kw: Klien())
    r = c.post("/api/struk/baca", data=b"\xff\xd8gambar", content_type="image/jpeg")
    assert r.status_code == 200
    item = r.get_json()["item"]
    assert item[0]["bahan_id"] == sel and item[0]["qty_bahan"] == 2000
    assert item[1]["bahan_id"] == 0 and item[1]["qty_bahan"] == 0


def test_simpan_banyak_dengan_bahan_baru(c):
    gula = next(b["id"] for b in c.get("/api/bahan").get_json() if b["nama"] == "Gula")
    r = c.post("/api/pembelian/banyak", json={
        "tanggal": "2026-11-01", "pemasok": "Toko A",
        "items": [{"bahan_id": gula, "qty": 2000, "total": 30000},
                  {"bahan_baru": {"nama": "Telur", "satuan": "butir"}, "qty": 10, "total": 25000}]})
    assert r.status_code == 200 and len(r.get_json()["ids"]) == 2
    bahan = {b["nama"]: b for b in c.get("/api/bahan").get_json()}
    assert bahan["Gula"]["stok"] >= 2000 and bahan["Telur"]["stok"] == 10
    ids = set(r.get_json()["ids"])
    baru = [p for p in c.get("/api/pembelian").get_json() if p["id"] in ids]
    assert len(baru) == 2 and all(p["pemasok"] == "Toko A" for p in baru)


def test_simpan_banyak_gagal_tidak_menyimpan_sebagian(c):
    sebelum = len(c.get("/api/pembelian").get_json())
    r = c.post("/api/pembelian/banyak", json={
        "tanggal": "2026-11-02",
        "items": [{"bahan_baru": {"nama": "Susu", "satuan": "ml"}, "qty": 1, "total": 1000},
                  {"bahan_id": 99999, "qty": 1, "total": 1000}]})
    assert r.status_code == 400
    assert len(c.get("/api/pembelian").get_json()) == sebelum
    assert "Susu" not in {b["nama"] for b in c.get("/api/bahan").get_json()}
