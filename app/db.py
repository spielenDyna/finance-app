"""Koneksi dan skema database SQLite."""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.environ.get(
    "FINANCE_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "keuangan.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS bahan (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL UNIQUE,
    satuan TEXT NOT NULL,
    -- dihitung ulang oleh inventory.rebuild()
    stok REAL NOT NULL DEFAULT 0,
    harga_rata REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS produk (
    id INTEGER PRIMARY KEY,
    nama TEXT NOT NULL UNIQUE,
    harga_jual REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS resep (
    produk_id INTEGER NOT NULL REFERENCES produk(id) ON DELETE CASCADE,
    bahan_id INTEGER NOT NULL REFERENCES bahan(id),
    qty REAL NOT NULL,
    PRIMARY KEY (produk_id, bahan_id)
);

CREATE TABLE IF NOT EXISTS pembelian (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    bahan_id INTEGER NOT NULL REFERENCES bahan(id),
    qty REAL NOT NULL,
    total REAL NOT NULL,
    pemasok TEXT,
    catatan TEXT
);

CREATE TABLE IF NOT EXISTS penjualan (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    pemesan TEXT,
    metode TEXT,
    catatan TEXT
);

CREATE TABLE IF NOT EXISTS penjualan_item (
    id INTEGER PRIMARY KEY,
    penjualan_id INTEGER NOT NULL REFERENCES penjualan(id) ON DELETE CASCADE,
    produk_id INTEGER NOT NULL REFERENCES produk(id),
    qty REAL NOT NULL,
    harga REAL NOT NULL,
    -- HPP per unit pada saat penjualan, dihitung ulang oleh inventory.rebuild()
    hpp_unit REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS beban (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    kategori TEXT NOT NULL,
    jumlah REAL NOT NULL,
    catatan TEXT
);

CREATE TABLE IF NOT EXISTS opname (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    bahan_id INTEGER NOT NULL REFERENCES bahan(id),
    qty_aktual REAL NOT NULL,
    catatan TEXT,
    -- dihitung ulang oleh inventory.rebuild()
    qty_sistem REAL NOT NULL DEFAULT 0,
    selisih REAL NOT NULL DEFAULT 0,
    nilai REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS mutasi (
    id INTEGER PRIMARY KEY,
    tanggal TEXT NOT NULL,
    bahan_id INTEGER NOT NULL,
    jenis TEXT NOT NULL,          -- beli | pakai | opname
    ref TEXT NOT NULL,            -- mis. pembelian:3, penjualan:7
    qty REAL NOT NULL,            -- + masuk, - keluar
    nilai REAL NOT NULL,          -- + masuk, - keluar (rupiah)
    stok_setelah REAL NOT NULL,
    harga_rata_setelah REAL NOT NULL
);
"""

KATEGORI_BEBAN = [
    "Kemasan",
    "Transport/Ongkir",
    "Listrik & Air",
    "Gas",
    "Sewa",
    "Gaji/Upah",
    "Promosi",
    "Peralatan kecil",
    "Lain-lain",
]


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with session() as conn:
        conn.executescript(SCHEMA)
