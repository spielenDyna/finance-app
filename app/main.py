"""API dan server web Finance App."""
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import auth, db, inventory, report

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Finance App", lifespan=lifespan)
auth.pasang(app)
app.include_router(auth.router)


@app.exception_handler(sqlite3.IntegrityError)
def _integrity(_: Request, exc: sqlite3.IntegrityError):
    msg = str(exc)
    if "UNIQUE" in msg:
        pesan = "Nama sudah dipakai."
    elif "FOREIGN KEY" in msg:
        pesan = "Data ini masih dipakai oleh transaksi atau resep lain, jadi tidak bisa dihapus."
    else:
        pesan = msg
    return JSONResponse(status_code=400, content={"detail": pesan})


def rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params)]


def hapus(conn, tabel, id_):
    if conn.execute(f"DELETE FROM {tabel} WHERE id = ?", (id_,)).rowcount == 0:
        raise HTTPException(404, "Data tidak ditemukan.")


def ubah(conn, sql, params):
    if conn.execute(sql, params).rowcount == 0:
        raise HTTPException(404, "Data tidak ditemukan.")


# ---------- Bahan ----------
class BahanIn(BaseModel):
    nama: str = Field(min_length=1)
    satuan: str = Field(min_length=1)


@app.get("/api/bahan")
def list_bahan():
    with db.session() as c:
        return rows(c, "SELECT *, stok * harga_rata AS nilai FROM bahan ORDER BY nama")


@app.post("/api/bahan")
def add_bahan(b: BahanIn):
    with db.session() as c:
        cur = c.execute("INSERT INTO bahan (nama, satuan) VALUES (?, ?)", (b.nama.strip(), b.satuan.strip()))
        return {"id": cur.lastrowid}


@app.put("/api/bahan/{id_}")
def edit_bahan(id_: int, b: BahanIn):
    with db.session() as c:
        c.execute("UPDATE bahan SET nama = ?, satuan = ? WHERE id = ?", (b.nama.strip(), b.satuan.strip(), id_))
        return {"ok": True}


@app.delete("/api/bahan/{id_}")
def del_bahan(id_: int):
    with db.session() as c:
        hapus(c, "bahan", id_)
        return {"ok": True}


@app.get("/api/bahan/{id_}/mutasi")
def mutasi_bahan(id_: int):
    with db.session() as c:
        return rows(c, "SELECT * FROM mutasi WHERE bahan_id = ? ORDER BY id", (id_,))


# ---------- Produk & resep ----------
class ResepIn(BaseModel):
    bahan_id: int
    qty: float = Field(gt=0)


class ProdukIn(BaseModel):
    nama: str = Field(min_length=1)
    harga_jual: float = Field(ge=0)
    resep: list[ResepIn] = []


@app.get("/api/produk")
def list_produk():
    with db.session() as c:
        produk = rows(c, "SELECT * FROM produk ORDER BY nama")
        for p in produk:
            p["resep"] = rows(
                c,
                """SELECT r.bahan_id, r.qty, b.nama, b.satuan, b.harga_rata, r.qty * b.harga_rata AS biaya
                   FROM resep r JOIN bahan b ON b.id = r.bahan_id WHERE r.produk_id = ?""",
                (p["id"],),
            )
            p["hpp_saat_ini"] = sum(r["biaya"] for r in p["resep"])
        return produk


def simpan_resep(c, produk_id, resep):
    c.execute("DELETE FROM resep WHERE produk_id = ?", (produk_id,))
    c.executemany(
        "INSERT INTO resep (produk_id, bahan_id, qty) VALUES (?, ?, ?)",
        [(produk_id, r.bahan_id, r.qty) for r in resep],
    )


@app.post("/api/produk")
def add_produk(p: ProdukIn):
    with db.session() as c:
        cur = c.execute("INSERT INTO produk (nama, harga_jual) VALUES (?, ?)", (p.nama.strip(), p.harga_jual))
        simpan_resep(c, cur.lastrowid, p.resep)
        inventory.rebuild(c)
        return {"id": cur.lastrowid}


@app.put("/api/produk/{id_}")
def edit_produk(id_: int, p: ProdukIn):
    with db.session() as c:
        c.execute("UPDATE produk SET nama = ?, harga_jual = ? WHERE id = ?", (p.nama.strip(), p.harga_jual, id_))
        simpan_resep(c, id_, p.resep)
        inventory.rebuild(c)
        return {"ok": True}


@app.delete("/api/produk/{id_}")
def del_produk(id_: int):
    with db.session() as c:
        hapus(c, "produk", id_)
        return {"ok": True}


# ---------- Pembelian bahan ----------
class PembelianIn(BaseModel):
    tanggal: date
    bahan_id: int
    qty: float = Field(gt=0)
    total: float = Field(ge=0)
    pemasok: str = ""
    catatan: str = ""


@app.get("/api/pembelian")
def list_pembelian():
    with db.session() as c:
        return rows(
            c,
            """SELECT p.*, b.nama AS bahan, b.satuan, p.total / p.qty AS harga_satuan
               FROM pembelian p JOIN bahan b ON b.id = p.bahan_id ORDER BY p.tanggal DESC, p.id DESC""",
        )


@app.post("/api/pembelian")
def add_pembelian(p: PembelianIn):
    with db.session() as c:
        cur = c.execute(
            "INSERT INTO pembelian (tanggal, bahan_id, qty, total, pemasok, catatan) VALUES (?, ?, ?, ?, ?, ?)",
            (p.tanggal.isoformat(), p.bahan_id, p.qty, p.total, p.pemasok, p.catatan),
        )
        inventory.rebuild(c)
        return {"id": cur.lastrowid}


@app.put("/api/pembelian/{id_}")
def edit_pembelian(id_: int, p: PembelianIn):
    with db.session() as c:
        ubah(c, "UPDATE pembelian SET tanggal = ?, bahan_id = ?, qty = ?, total = ?, pemasok = ?, catatan = ? WHERE id = ?",
             (p.tanggal.isoformat(), p.bahan_id, p.qty, p.total, p.pemasok, p.catatan, id_))
        inventory.rebuild(c)
        return {"ok": True}


@app.delete("/api/pembelian/{id_}")
def del_pembelian(id_: int):
    with db.session() as c:
        hapus(c, "pembelian", id_)
        inventory.rebuild(c)
        return {"ok": True}


# ---------- Penjualan ----------
class ItemIn(BaseModel):
    produk_id: int
    qty: float = Field(gt=0)
    harga: float = Field(ge=0)


class PenjualanIn(BaseModel):
    tanggal: date
    pemesan: str = ""
    metode: str = "Transfer"
    catatan: str = ""
    items: list[ItemIn] = Field(min_length=1)


@app.get("/api/penjualan")
def list_penjualan():
    with db.session() as c:
        jual = rows(c, "SELECT * FROM penjualan ORDER BY tanggal DESC, id DESC")
        for j in jual:
            j["items"] = rows(
                c,
                """SELECT pi.*, pr.nama AS produk FROM penjualan_item pi JOIN produk pr ON pr.id = pi.produk_id
                   WHERE pi.penjualan_id = ?""",
                (j["id"],),
            )
            j["total"] = sum(i["qty"] * i["harga"] for i in j["items"])
            j["hpp"] = sum(i["qty"] * i["hpp_unit"] for i in j["items"])
        return jual


@app.post("/api/penjualan")
def add_penjualan(p: PenjualanIn):
    with db.session() as c:
        cur = c.execute(
            "INSERT INTO penjualan (tanggal, pemesan, metode, catatan) VALUES (?, ?, ?, ?)",
            (p.tanggal.isoformat(), p.pemesan, p.metode, p.catatan),
        )
        c.executemany(
            "INSERT INTO penjualan_item (penjualan_id, produk_id, qty, harga) VALUES (?, ?, ?, ?)",
            [(cur.lastrowid, i.produk_id, i.qty, i.harga) for i in p.items],
        )
        inventory.rebuild(c)
        return {"id": cur.lastrowid}


@app.put("/api/penjualan/{id_}")
def edit_penjualan(id_: int, p: PenjualanIn):
    with db.session() as c:
        ubah(c, "UPDATE penjualan SET tanggal = ?, pemesan = ?, metode = ?, catatan = ? WHERE id = ?",
             (p.tanggal.isoformat(), p.pemesan, p.metode, p.catatan, id_))
        c.execute("DELETE FROM penjualan_item WHERE penjualan_id = ?", (id_,))
        c.executemany(
            "INSERT INTO penjualan_item (penjualan_id, produk_id, qty, harga) VALUES (?, ?, ?, ?)",
            [(id_, i.produk_id, i.qty, i.harga) for i in p.items],
        )
        inventory.rebuild(c)
        return {"ok": True}


@app.delete("/api/penjualan/{id_}")
def del_penjualan(id_: int):
    with db.session() as c:
        hapus(c, "penjualan", id_)
        inventory.rebuild(c)
        return {"ok": True}


# ---------- Beban ----------
class BebanIn(BaseModel):
    tanggal: date
    kategori: str = Field(min_length=1)
    jumlah: float = Field(gt=0)
    catatan: str = ""


@app.get("/api/kategori-beban")
def kategori_beban():
    with db.session() as c:
        dipakai = [r["kategori"] for r in c.execute("SELECT DISTINCT kategori FROM beban")]
    return sorted(set(db.KATEGORI_BEBAN) | set(dipakai))


@app.get("/api/beban")
def list_beban():
    with db.session() as c:
        return rows(c, "SELECT * FROM beban ORDER BY tanggal DESC, id DESC")


@app.post("/api/beban")
def add_beban(b: BebanIn):
    with db.session() as c:
        cur = c.execute(
            "INSERT INTO beban (tanggal, kategori, jumlah, catatan) VALUES (?, ?, ?, ?)",
            (b.tanggal.isoformat(), b.kategori.strip(), b.jumlah, b.catatan),
        )
        return {"id": cur.lastrowid}


@app.put("/api/beban/{id_}")
def edit_beban(id_: int, b: BebanIn):
    with db.session() as c:
        ubah(c, "UPDATE beban SET tanggal = ?, kategori = ?, jumlah = ?, catatan = ? WHERE id = ?",
             (b.tanggal.isoformat(), b.kategori.strip(), b.jumlah, b.catatan, id_))
        return {"ok": True}


@app.delete("/api/beban/{id_}")
def del_beban(id_: int):
    with db.session() as c:
        hapus(c, "beban", id_)
        return {"ok": True}


# ---------- Stok opname ----------
class OpnameIn(BaseModel):
    tanggal: date
    bahan_id: int
    qty_aktual: float = Field(ge=0)
    catatan: str = ""


@app.get("/api/opname")
def list_opname():
    with db.session() as c:
        return rows(
            c,
            """SELECT o.*, b.nama AS bahan, b.satuan FROM opname o JOIN bahan b ON b.id = o.bahan_id
               ORDER BY o.tanggal DESC, o.id DESC""",
        )


@app.post("/api/opname")
def add_opname(o: OpnameIn):
    with db.session() as c:
        cur = c.execute(
            "INSERT INTO opname (tanggal, bahan_id, qty_aktual, catatan) VALUES (?, ?, ?, ?)",
            (o.tanggal.isoformat(), o.bahan_id, o.qty_aktual, o.catatan),
        )
        inventory.rebuild(c)
        return {"id": cur.lastrowid}


@app.put("/api/opname/{id_}")
def edit_opname(id_: int, o: OpnameIn):
    with db.session() as c:
        ubah(c, "UPDATE opname SET tanggal = ?, bahan_id = ?, qty_aktual = ?, catatan = ? WHERE id = ?",
             (o.tanggal.isoformat(), o.bahan_id, o.qty_aktual, o.catatan, id_))
        inventory.rebuild(c)
        return {"ok": True}


@app.delete("/api/opname/{id_}")
def del_opname(id_: int):
    with db.session() as c:
        hapus(c, "opname", id_)
        inventory.rebuild(c)
        return {"ok": True}


# ---------- Laporan ----------
@app.get("/api/laporan/laba-rugi")
def laporan_laba_rugi(dari: date, sampai: date):
    with db.session() as c:
        return report.laba_rugi(c, dari.isoformat(), sampai.isoformat())


@app.get("/api/laporan/detail")
def laporan_detail(pos: str, key: str, dari: date, sampai: date):
    with db.session() as c:
        return report.detail(c, pos, key, dari.isoformat(), sampai.isoformat())


# ---------- UI ----------
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))
