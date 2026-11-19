"""API dan server web Finance App (Flask)."""
import os
import sqlite3

from flask import Flask, jsonify, request, send_file

from . import auth, db, inventory, report
from .validasi import Galat, angka, bulat, daftar, objek, tanggal, teks

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=STATIC, static_url_path="/static")
app.json.ensure_ascii = False
auth.pasang(app)
app.register_blueprint(auth.router)
db.init_db()


@app.errorhandler(Galat)
def _galat(exc: Galat):
    return jsonify(detail=exc.pesan), exc.status


@app.errorhandler(sqlite3.IntegrityError)
def _integrity(exc: sqlite3.IntegrityError):
    msg = str(exc)
    if "UNIQUE" in msg:
        pesan = "Nama sudah dipakai."
    elif "FOREIGN KEY" in msg:
        pesan = "Data ini masih dipakai oleh transaksi atau resep lain, jadi tidak bisa dihapus."
    else:
        pesan = msg
    return jsonify(detail=pesan), 400


def body() -> dict:
    return objek(request.get_json(silent=True))


def rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params)]


def hapus(conn, tabel, id_):
    if conn.execute(f"DELETE FROM {tabel} WHERE id = ?", (id_,)).rowcount == 0:
        raise Galat("Data tidak ditemukan.", 404)


def ubah(conn, sql, params):
    if conn.execute(sql, params).rowcount == 0:
        raise Galat("Data tidak ditemukan.", 404)


# ---------- Bahan ----------
def baca_bahan(d):
    return teks(d, "nama", wajib=True).strip(), teks(d, "satuan", wajib=True).strip()


@app.get("/api/bahan")
def list_bahan():
    with db.session() as c:
        return jsonify(rows(c, "SELECT *, stok * harga_rata AS nilai FROM bahan ORDER BY nama"))


@app.post("/api/bahan")
def add_bahan():
    nama, satuan = baca_bahan(body())
    with db.session() as c:
        cur = c.execute("INSERT INTO bahan (nama, satuan) VALUES (?, ?)", (nama, satuan))
        return jsonify(id=cur.lastrowid)


@app.put("/api/bahan/<int:id_>")
def edit_bahan(id_):
    nama, satuan = baca_bahan(body())
    with db.session() as c:
        c.execute("UPDATE bahan SET nama = ?, satuan = ? WHERE id = ?", (nama, satuan, id_))
        return jsonify(ok=True)


@app.delete("/api/bahan/<int:id_>")
def del_bahan(id_):
    with db.session() as c:
        hapus(c, "bahan", id_)
        return jsonify(ok=True)


@app.get("/api/bahan/<int:id_>/mutasi")
def mutasi_bahan(id_):
    with db.session() as c:
        return jsonify(rows(c, "SELECT * FROM mutasi WHERE bahan_id = ? ORDER BY id", (id_,)))


# ---------- Produk & resep ----------
def baca_produk(d):
    nama = teks(d, "nama", wajib=True).strip()
    harga = angka(d, "harga_jual", ge=0)
    resep = [(bulat(r, "bahan_id"), angka(r, "qty", gt=0)) for r in daftar(d, "resep")]
    return nama, harga, resep


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
        return jsonify(produk)


def simpan_resep(c, produk_id, resep):
    c.execute("DELETE FROM resep WHERE produk_id = ?", (produk_id,))
    c.executemany(
        "INSERT INTO resep (produk_id, bahan_id, qty) VALUES (?, ?, ?)",
        [(produk_id, bahan_id, qty) for bahan_id, qty in resep],
    )


@app.post("/api/produk")
def add_produk():
    nama, harga, resep = baca_produk(body())
    with db.session() as c:
        cur = c.execute("INSERT INTO produk (nama, harga_jual) VALUES (?, ?)", (nama, harga))
        simpan_resep(c, cur.lastrowid, resep)
        inventory.rebuild(c)
        return jsonify(id=cur.lastrowid)


@app.put("/api/produk/<int:id_>")
def edit_produk(id_):
    nama, harga, resep = baca_produk(body())
    with db.session() as c:
        c.execute("UPDATE produk SET nama = ?, harga_jual = ? WHERE id = ?", (nama, harga, id_))
        simpan_resep(c, id_, resep)
        inventory.rebuild(c)
        return jsonify(ok=True)


@app.delete("/api/produk/<int:id_>")
def del_produk(id_):
    with db.session() as c:
        hapus(c, "produk", id_)
        return jsonify(ok=True)


# ---------- Pembelian bahan ----------
def baca_pembelian(d):
    return (
        tanggal(d, "tanggal"), bulat(d, "bahan_id"), angka(d, "qty", gt=0), angka(d, "total", ge=0),
        teks(d, "pemasok"), teks(d, "catatan"),
    )


@app.get("/api/pembelian")
def list_pembelian():
    with db.session() as c:
        return jsonify(rows(
            c,
            """SELECT p.*, b.nama AS bahan, b.satuan, p.total / p.qty AS harga_satuan
               FROM pembelian p JOIN bahan b ON b.id = p.bahan_id ORDER BY p.tanggal DESC, p.id DESC""",
        ))


@app.post("/api/pembelian")
def add_pembelian():
    v = baca_pembelian(body())
    with db.session() as c:
        cur = c.execute(
            "INSERT INTO pembelian (tanggal, bahan_id, qty, total, pemasok, catatan) VALUES (?, ?, ?, ?, ?, ?)", v
        )
        inventory.rebuild(c)
        return jsonify(id=cur.lastrowid)


@app.put("/api/pembelian/<int:id_>")
def edit_pembelian(id_):
    v = baca_pembelian(body())
    with db.session() as c:
        ubah(c, "UPDATE pembelian SET tanggal = ?, bahan_id = ?, qty = ?, total = ?, pemasok = ?, catatan = ? WHERE id = ?",
             (*v, id_))
        inventory.rebuild(c)
        return jsonify(ok=True)


@app.delete("/api/pembelian/<int:id_>")
def del_pembelian(id_):
    with db.session() as c:
        hapus(c, "pembelian", id_)
        inventory.rebuild(c)
        return jsonify(ok=True)


# ---------- Penjualan ----------
def baca_penjualan(d):
    head = (tanggal(d, "tanggal"), teks(d, "pemesan"), teks(d, "metode", default="Transfer"), teks(d, "catatan"))
    items = [(bulat(i, "produk_id"), angka(i, "qty", gt=0), angka(i, "harga", ge=0)) for i in daftar(d, "items", 1)]
    return head, items


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
        return jsonify(jual)


@app.post("/api/penjualan")
def add_penjualan():
    head, items = baca_penjualan(body())
    with db.session() as c:
        cur = c.execute("INSERT INTO penjualan (tanggal, pemesan, metode, catatan) VALUES (?, ?, ?, ?)", head)
        c.executemany(
            "INSERT INTO penjualan_item (penjualan_id, produk_id, qty, harga) VALUES (?, ?, ?, ?)",
            [(cur.lastrowid, *i) for i in items],
        )
        inventory.rebuild(c)
        return jsonify(id=cur.lastrowid)


@app.put("/api/penjualan/<int:id_>")
def edit_penjualan(id_):
    head, items = baca_penjualan(body())
    with db.session() as c:
        ubah(c, "UPDATE penjualan SET tanggal = ?, pemesan = ?, metode = ?, catatan = ? WHERE id = ?", (*head, id_))
        c.execute("DELETE FROM penjualan_item WHERE penjualan_id = ?", (id_,))
        c.executemany(
            "INSERT INTO penjualan_item (penjualan_id, produk_id, qty, harga) VALUES (?, ?, ?, ?)",
            [(id_, *i) for i in items],
        )
        inventory.rebuild(c)
        return jsonify(ok=True)


@app.delete("/api/penjualan/<int:id_>")
def del_penjualan(id_):
    with db.session() as c:
        hapus(c, "penjualan", id_)
        inventory.rebuild(c)
        return jsonify(ok=True)


# ---------- Beban ----------
def baca_beban(d):
    return (
        tanggal(d, "tanggal"), teks(d, "kategori", wajib=True).strip(), angka(d, "jumlah", gt=0), teks(d, "catatan"),
    )


@app.get("/api/kategori-beban")
def kategori_beban():
    with db.session() as c:
        dipakai = [r["kategori"] for r in c.execute("SELECT DISTINCT kategori FROM beban")]
    return jsonify(sorted(set(db.KATEGORI_BEBAN) | set(dipakai)))


@app.get("/api/beban")
def list_beban():
    with db.session() as c:
        return jsonify(rows(c, "SELECT * FROM beban ORDER BY tanggal DESC, id DESC"))


@app.post("/api/beban")
def add_beban():
    v = baca_beban(body())
    with db.session() as c:
        cur = c.execute("INSERT INTO beban (tanggal, kategori, jumlah, catatan) VALUES (?, ?, ?, ?)", v)
        return jsonify(id=cur.lastrowid)


@app.put("/api/beban/<int:id_>")
def edit_beban(id_):
    v = baca_beban(body())
    with db.session() as c:
        ubah(c, "UPDATE beban SET tanggal = ?, kategori = ?, jumlah = ?, catatan = ? WHERE id = ?", (*v, id_))
        return jsonify(ok=True)


@app.delete("/api/beban/<int:id_>")
def del_beban(id_):
    with db.session() as c:
        hapus(c, "beban", id_)
        return jsonify(ok=True)


# ---------- Stok opname ----------
def baca_opname(d):
    return tanggal(d, "tanggal"), bulat(d, "bahan_id"), angka(d, "qty_aktual", ge=0), teks(d, "catatan")


@app.get("/api/opname")
def list_opname():
    with db.session() as c:
        return jsonify(rows(
            c,
            """SELECT o.*, b.nama AS bahan, b.satuan FROM opname o JOIN bahan b ON b.id = o.bahan_id
               ORDER BY o.tanggal DESC, o.id DESC""",
        ))


@app.post("/api/opname")
def add_opname():
    v = baca_opname(body())
    with db.session() as c:
        cur = c.execute("INSERT INTO opname (tanggal, bahan_id, qty_aktual, catatan) VALUES (?, ?, ?, ?)", v)
        inventory.rebuild(c)
        return jsonify(id=cur.lastrowid)


@app.put("/api/opname/<int:id_>")
def edit_opname(id_):
    v = baca_opname(body())
    with db.session() as c:
        ubah(c, "UPDATE opname SET tanggal = ?, bahan_id = ?, qty_aktual = ?, catatan = ? WHERE id = ?", (*v, id_))
        inventory.rebuild(c)
        return jsonify(ok=True)


@app.delete("/api/opname/<int:id_>")
def del_opname(id_):
    with db.session() as c:
        hapus(c, "opname", id_)
        inventory.rebuild(c)
        return jsonify(ok=True)


# ---------- Laporan ----------
@app.get("/api/laporan/laba-rugi")
def laporan_laba_rugi():
    dari, sampai = tanggal(request.args, "dari"), tanggal(request.args, "sampai")
    with db.session() as c:
        return jsonify(report.laba_rugi(c, dari, sampai))


@app.get("/api/laporan/detail")
def laporan_detail():
    pos, key = request.args.get("pos"), request.args.get("key")
    if pos is None or key is None:
        raise Galat("pos dan key wajib diisi.")
    dari, sampai = tanggal(request.args, "dari"), tanggal(request.args, "sampai")
    with db.session() as c:
        return jsonify(report.detail(c, pos, key, dari, sampai))


# ---------- UI ----------
@app.get("/")
def index():
    return send_file(os.path.join(STATIC, "index.html"))
