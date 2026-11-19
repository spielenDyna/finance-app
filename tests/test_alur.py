"""Uji alur lengkap: pembelian -> penjualan -> beban -> opname -> laporan laba rugi."""
import os
import tempfile

import pytest

os.environ["FINANCE_DB"] = os.path.join(tempfile.mkdtemp(), "uji.db")

from app import auth  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def c():
    auth.simpan_password("uji-rahasia")
    with app.test_client() as client:
        assert client.post("/api/login", json={"password": "uji-rahasia"}).status_code == 200
        yield client


def post(c, path, body):
    r = c.post(path, json=body)
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["id"]


def test_alur_lengkap(c):
    selada = post(c, "/api/bahan", {"nama": "Selada", "satuan": "gram"})
    ayam = post(c, "/api/bahan", {"nama": "Ayam", "satuan": "gram"})
    salad = post(c, "/api/produk", {
        "nama": "Salad Ayam", "harga_jual": 25000,
        "resep": [{"bahan_id": selada, "qty": 100}, {"bahan_id": ayam, "qty": 50}],
    })

    post(c, "/api/pembelian", {"tanggal": "2026-09-01", "bahan_id": selada, "qty": 1000, "total": 20000})
    post(c, "/api/pembelian", {"tanggal": "2026-09-01", "bahan_id": ayam, "qty": 1000, "total": 60000})
    # 2 salad @ HPP 100*20 + 50*60 = 5.000
    post(c, "/api/penjualan", {"tanggal": "2026-09-02", "pemesan": "Nadira",
                               "items": [{"produk_id": salad, "qty": 2, "harga": 25000}]})
    # harga rata selada = (800*20 + 30.000) / 1.800 = 25,5556
    post(c, "/api/pembelian", {"tanggal": "2026-09-03", "bahan_id": selada, "qty": 1000, "total": 30000})
    post(c, "/api/penjualan", {"tanggal": "2026-09-04", "pemesan": "Emil",
                               "items": [{"produk_id": salad, "qty": 1, "harga": 25000}]})
    post(c, "/api/beban", {"tanggal": "2026-09-05", "kategori": "Kemasan", "jumlah": 5000})
    # stok sistem ayam 850, aktual 800 -> hilang 50 g x 60 = 3.000
    post(c, "/api/opname", {"tanggal": "2026-09-06", "bahan_id": ayam, "qty_aktual": 800})

    lr = c.get("/api/laporan/laba-rugi", query_string={"dari": "2026-09-01", "sampai": "2026-09-30"}).get_json()
    hpp = 10000 + (100 * 46000 / 1800 + 3000)
    assert lr["pendapatan"]["total"] == 75000
    assert lr["hpp"]["total"] == pytest.approx(hpp)
    assert lr["laba_kotor"]["total"] == pytest.approx(75000 - hpp)
    assert lr["beban"]["total"] == pytest.approx(8000)
    assert lr["laba_bersih"]["total"] == pytest.approx(75000 - hpp - 8000)
    assert lr["peringatan"] == []

    bahan = {b["nama"]: b for b in c.get("/api/bahan").get_json()}
    assert bahan["Selada"]["stok"] == pytest.approx(1700)
    assert bahan["Ayam"]["stok"] == pytest.approx(800)

    # transaksi mundur tanggal: pembelian ayam sebelum semua transaksi mengubah HPP penjualan lama
    post(c, "/api/pembelian", {"tanggal": "2026-08-31", "bahan_id": ayam, "qty": 1000, "total": 40000})
    lr2 = c.get("/api/laporan/laba-rugi", query_string={"dari": "2026-09-01", "sampai": "2026-09-30"}).get_json()
    assert lr2["hpp"]["total"] < lr["hpp"]["total"]

    # drill-down
    det = c.get("/api/laporan/detail", query_string={"pos": "hpp", "key": salad, "dari": "2026-09-01", "sampai": "2026-09-30"}).get_json()
    assert any("Resep" in d["keterangan"] for d in det)

    # edit transaksi
    pj = c.get("/api/penjualan").get_json()
    emil = next(p for p in pj if p["pemesan"] == "Emil")
    r = c.put(f"/api/penjualan/{emil['id']}", json={
        "tanggal": "2026-09-04", "pemesan": "Emil", "metode": "Cash",
        "items": [{"produk_id": salad, "qty": 3, "harga": 24000}]})
    assert r.status_code == 200, r.get_data(as_text=True)
    lr3 = c.get("/api/laporan/laba-rugi", query_string={"dari": "2026-09-01", "sampai": "2026-09-30"}).get_json()
    assert lr3["pendapatan"]["total"] == 50000 + 72000
    bahan = {b["nama"]: b for b in c.get("/api/bahan").get_json()}
    assert bahan["Selada"]["stok"] == pytest.approx(2000 - 500)

    bb = c.get("/api/beban").get_json()[0]
    assert c.put(f"/api/beban/{bb['id']}", json={**bb, "jumlah": 7000}).status_code == 200
    lr4 = c.get("/api/laporan/laba-rugi", query_string={"dari": "2026-09-01", "sampai": "2026-09-30"}).get_json()
    assert lr4["beban"]["total"] == pytest.approx(lr3["beban"]["total"] - 5000 + 7000)

    pb = next(p for p in c.get("/api/pembelian").get_json() if p["tanggal"] == "2026-09-03")
    assert c.put(f"/api/pembelian/{pb['id']}", json={**pb, "qty": 500}).status_code == 200
    assert {b["nama"]: b for b in c.get("/api/bahan").get_json()}["Selada"]["stok"] == pytest.approx(1000)

    op = c.get("/api/opname").get_json()[0]
    assert c.put(f"/api/opname/{op['id']}", json={**op, "qty_aktual": 1500}).status_code == 200
    assert {b["nama"]: b for b in c.get("/api/bahan").get_json()}["Ayam"]["stok"] == pytest.approx(1500)  # opname jadi transaksi terakhir

    assert c.put("/api/beban/9999", json={**bb}).status_code == 404

    # produk yang sudah terjual tidak bisa dihapus
    r = c.delete(f"/api/produk/{salad}")
    assert r.status_code == 400
