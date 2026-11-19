"""Laporan laba rugi beserta rumus dan rincian sumber angkanya."""
import sqlite3

SELISIH_PERSEDIAAN = "Selisih persediaan (stok opname)"


def rp(x: float) -> str:
    s = f"{abs(x):,.0f}".replace(",", ".")
    return f"-Rp{s}" if x < 0 else f"Rp{s}"


def laba_rugi(conn: sqlite3.Connection, dari: str, sampai: str) -> dict:
    per = (dari, sampai)

    penjualan = [
        dict(r)
        for r in conn.execute(
            """SELECT pr.id AS produk_id, pr.nama AS produk,
                      SUM(pi.qty) AS qty,
                      SUM(pi.qty * pi.harga) AS pendapatan,
                      SUM(pi.qty * pi.hpp_unit) AS hpp,
                      (SELECT COUNT(*) FROM resep r WHERE r.produk_id = pr.id) AS jml_bahan
               FROM penjualan_item pi
               JOIN penjualan p ON p.id = pi.penjualan_id
               JOIN produk pr ON pr.id = pi.produk_id
               WHERE p.tanggal BETWEEN ? AND ?
               GROUP BY pr.id ORDER BY pendapatan DESC""",
            per,
        )
    ]
    total_pendapatan = sum(r["pendapatan"] for r in penjualan)
    total_hpp = sum(r["hpp"] for r in penjualan)
    laba_kotor = total_pendapatan - total_hpp

    beban = [
        dict(r)
        for r in conn.execute(
            """SELECT kategori, SUM(jumlah) AS jumlah, COUNT(*) AS n FROM beban
               WHERE tanggal BETWEEN ? AND ? GROUP BY kategori ORDER BY jumlah DESC""",
            per,
        )
    ]
    selisih = conn.execute(
        "SELECT COALESCE(SUM(nilai), 0) AS v, COUNT(*) AS n FROM opname WHERE tanggal BETWEEN ? AND ? AND selisih != 0",
        per,
    ).fetchone()
    if selisih["n"]:
        # nilai opname negatif = barang hilang/rusak = beban
        beban.append({"kategori": SELISIH_PERSEDIAAN, "jumlah": -selisih["v"], "n": selisih["n"]})
    total_beban = sum(b["jumlah"] for b in beban)
    laba_bersih = laba_kotor - total_beban

    peringatan = [
        f"Produk '{r['produk']}' belum punya resep, jadi HPP-nya dihitung Rp0."
        for r in penjualan
        if r["jml_bahan"] == 0
    ]
    for r in conn.execute("SELECT nama, stok, satuan FROM bahan WHERE stok < -1e-9"):
        peringatan.append(
            f"Stok '{r['nama']}' minus ({r['stok']:g} {r['satuan']}). Catat pembelian yang belum masuk agar HPP akurat."
        )

    def rincian_rumus(items, key):
        return " + ".join(rp(i[key]) for i in items) or "Rp0"

    return {
        "periode": {"dari": dari, "sampai": sampai},
        "pendapatan": {
            "total": total_pendapatan,
            "rincian": [
                {"key": r["produk_id"], "nama": r["produk"], "qty": r["qty"], "jumlah": r["pendapatan"]}
                for r in penjualan
            ],
            "rumus": "Jumlah (qty x harga jual) seluruh item penjualan",
            "hitungan": f"{rincian_rumus(penjualan, 'pendapatan')} = {rp(total_pendapatan)}",
        },
        "hpp": {
            "total": total_hpp,
            "rincian": [
                {"key": r["produk_id"], "nama": r["produk"], "qty": r["qty"], "jumlah": r["hpp"]}
                for r in penjualan
            ],
            "rumus": "Jumlah (qty terjual x HPP per unit); HPP per unit = jumlah (takaran bahan x harga rata-rata bahan)",
            "hitungan": f"{rincian_rumus(penjualan, 'hpp')} = {rp(total_hpp)}",
        },
        "laba_kotor": {
            "total": laba_kotor,
            "rumus": "Pendapatan - HPP",
            "hitungan": f"{rp(total_pendapatan)} - {rp(total_hpp)} = {rp(laba_kotor)}",
            "margin": (laba_kotor / total_pendapatan * 100) if total_pendapatan else 0,
        },
        "beban": {
            "total": total_beban,
            "rincian": [{"key": b["kategori"], "nama": b["kategori"], "qty": b["n"], "jumlah": b["jumlah"]} for b in beban],
            "rumus": "Jumlah beban operasional per kategori + selisih stok opname (kehilangan/kerusakan)",
            "hitungan": f"{rincian_rumus(beban, 'jumlah')} = {rp(total_beban)}",
        },
        "laba_bersih": {
            "total": laba_bersih,
            "rumus": "Laba kotor - Beban operasional",
            "hitungan": f"{rp(laba_kotor)} - {rp(total_beban)} = {rp(laba_bersih)}",
            "margin": (laba_bersih / total_pendapatan * 100) if total_pendapatan else 0,
        },
        "peringatan": peringatan,
    }


def detail(conn: sqlite3.Connection, pos: str, key: str, dari: str, sampai: str) -> list[dict]:
    """Daftar transaksi sumber untuk satu baris laporan."""
    per = (dari, sampai)
    if pos in ("pendapatan", "hpp"):
        rows = conn.execute(
            """SELECT p.id AS penjualan_id, p.tanggal, p.pemesan, pi.qty, pi.harga, pi.hpp_unit
               FROM penjualan_item pi JOIN penjualan p ON p.id = pi.penjualan_id
               WHERE pi.produk_id = ? AND p.tanggal BETWEEN ? AND ? ORDER BY p.tanggal, p.id""",
            (int(key), *per),
        )
        out = []
        for r in rows:
            if pos == "pendapatan":
                jumlah = r["qty"] * r["harga"]
                rumus = f"{r['qty']:g} x {rp(r['harga'])}"
            else:
                jumlah = r["qty"] * r["hpp_unit"]
                rumus = f"{r['qty']:g} x {rp(r['hpp_unit'])}"
            out.append(
                {"tanggal": r["tanggal"], "keterangan": f"#{r['penjualan_id']} {r['pemesan'] or ''}".strip(),
                 "rumus": rumus, "jumlah": jumlah}
            )
        if pos == "hpp":
            # tampilkan komposisi resep supaya HPP per unit bisa ditelusuri
            for r in conn.execute(
                """SELECT b.nama, b.satuan, r.qty FROM resep r JOIN bahan b ON b.id = r.bahan_id
                   WHERE r.produk_id = ?""",
                (int(key),),
            ):
                out.append({"tanggal": "", "keterangan": f"Resep: {r['nama']}", "rumus": f"{r['qty']:g} {r['satuan']} per unit", "jumlah": None})
        return out

    if pos == "beban":
        if key == SELISIH_PERSEDIAAN:
            rows = conn.execute(
                """SELECT o.tanggal, b.nama, b.satuan, o.qty_sistem, o.qty_aktual, o.selisih, o.nilai
                   FROM opname o JOIN bahan b ON b.id = o.bahan_id
                   WHERE o.tanggal BETWEEN ? AND ? AND o.selisih != 0 ORDER BY o.tanggal""",
                per,
            )
            return [
                {"tanggal": r["tanggal"], "keterangan": r["nama"],
                 "rumus": f"(aktual {r['qty_aktual']:g} - sistem {r['qty_sistem']:g}) {r['satuan']} x harga rata",
                 "jumlah": -r["nilai"]}
                for r in rows
            ]
        rows = conn.execute(
            "SELECT tanggal, catatan, jumlah FROM beban WHERE kategori = ? AND tanggal BETWEEN ? AND ? ORDER BY tanggal",
            (key, *per),
        )
        return [{"tanggal": r["tanggal"], "keterangan": r["catatan"] or "", "rumus": "", "jumlah": r["jumlah"]} for r in rows]

    return []
