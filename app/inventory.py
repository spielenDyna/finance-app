"""Perhitungan persediaan dan HPP dengan metode rata-rata tertimbang (moving average).

Semua transaksi (pembelian, penjualan, stok opname) diputar ulang secara kronologis
setiap kali ada perubahan data. Dengan begitu, transaksi yang diinput mundur tanggal
atau dihapus tetap menghasilkan stok, harga rata-rata, dan HPP yang benar.

Urutan dalam satu tanggal: pembelian -> penjualan -> stok opname.

Rumus:
  Harga rata-rata baru = (stok lama x harga rata lama + total pembelian) / (stok lama + qty beli)
  HPP per unit produk  = jumlah (takaran bahan x harga rata bahan saat itu)
  Selisih opname       = qty aktual - qty sistem;  nilai = selisih x harga rata
"""
import sqlite3

URUTAN = {"beli": 0, "jual": 1, "opname": 2}


def rebuild(conn: sqlite3.Connection) -> None:
    bahan = {r["id"]: {"stok": 0.0, "rata": 0.0} for r in conn.execute("SELECT id FROM bahan")}
    resep: dict[int, list[tuple[int, float]]] = {}
    for r in conn.execute("SELECT produk_id, bahan_id, qty FROM resep"):
        resep.setdefault(r["produk_id"], []).append((r["bahan_id"], r["qty"]))

    events = []
    for r in conn.execute("SELECT * FROM pembelian"):
        events.append((r["tanggal"], URUTAN["beli"], r["id"], "beli", r))
    for r in conn.execute(
        "SELECT pi.*, p.tanggal FROM penjualan_item pi JOIN penjualan p ON p.id = pi.penjualan_id"
    ):
        events.append((r["tanggal"], URUTAN["jual"], r["id"], "jual", r))
    for r in conn.execute("SELECT * FROM opname"):
        events.append((r["tanggal"], URUTAN["opname"], r["id"], "opname", r))
    events.sort(key=lambda e: (e[0], e[1], e[2]))

    conn.execute("DELETE FROM mutasi")
    mutasi = []

    def catat(tgl, bid, jenis, ref, qty, nilai):
        b = bahan[bid]
        mutasi.append((tgl, bid, jenis, ref, qty, nilai, b["stok"], b["rata"]))

    for tgl, _, _, jenis, r in events:
        if jenis == "beli":
            b = bahan[r["bahan_id"]]
            stok_baru = b["stok"] + r["qty"]
            if b["stok"] <= 0 or stok_baru <= 0:
                # stok kosong/minus: harga rata mengikuti pembelian terbaru
                b["rata"] = r["total"] / r["qty"] if r["qty"] else b["rata"]
            else:
                b["rata"] = (b["stok"] * b["rata"] + r["total"]) / stok_baru
            b["stok"] = stok_baru
            catat(tgl, r["bahan_id"], "beli", f"pembelian:{r['id']}", r["qty"], r["total"])

        elif jenis == "jual":
            hpp_unit = 0.0
            for bid, takaran in resep.get(r["produk_id"], []):
                b = bahan[bid]
                pakai = takaran * r["qty"]
                hpp_unit += takaran * b["rata"]
                b["stok"] -= pakai
                catat(tgl, bid, "pakai", f"penjualan:{r['penjualan_id']}", -pakai, -pakai * b["rata"])
            conn.execute("UPDATE penjualan_item SET hpp_unit = ? WHERE id = ?", (hpp_unit, r["id"]))

        else:  # opname
            b = bahan[r["bahan_id"]]
            sistem = b["stok"]
            selisih = r["qty_aktual"] - sistem
            nilai = selisih * b["rata"]
            b["stok"] = r["qty_aktual"]
            conn.execute(
                "UPDATE opname SET qty_sistem = ?, selisih = ?, nilai = ? WHERE id = ?",
                (sistem, selisih, nilai, r["id"]),
            )
            catat(tgl, r["bahan_id"], "opname", f"opname:{r['id']}", selisih, nilai)

    conn.executemany(
        "INSERT INTO mutasi (tanggal, bahan_id, jenis, ref, qty, nilai, stok_setelah, harga_rata_setelah)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        mutasi,
    )
    for bid, b in bahan.items():
        conn.execute("UPDATE bahan SET stok = ?, harga_rata = ? WHERE id = ?", (b["stok"], b["rata"], bid))
