"""Validasi isi JSON permintaan (pengganti pydantic)."""
from datetime import date


class Galat(Exception):
    """Kesalahan yang dikirim ke klien sebagai {"detail": pesan}."""

    def __init__(self, pesan: str, status: int = 422):
        super().__init__(pesan)
        self.pesan, self.status = pesan, status


def objek(data):
    if not isinstance(data, dict):
        raise Galat("Isi permintaan harus berupa objek JSON.")
    return data


def teks(d, k, wajib=False, default=""):
    v = d.get(k, default)
    if v is None:
        v = default
    if not isinstance(v, str):
        raise Galat(f"{k}: harus berupa teks.")
    if wajib and not v.strip():
        raise Galat(f"{k}: tidak boleh kosong.")
    return v


def angka(d, k, gt=None, ge=None):
    v = d.get(k)
    if v is None or isinstance(v, bool):
        raise Galat(f"{k}: wajib diisi.")
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise Galat(f"{k}: harus berupa angka.")
    if gt is not None and not v > gt:
        raise Galat(f"{k}: harus lebih besar dari {gt:g}.")
    if ge is not None and not v >= ge:
        raise Galat(f"{k}: tidak boleh kurang dari {ge:g}.")
    return v


def bulat(d, k):
    v = d.get(k)
    if v is None or isinstance(v, bool):
        raise Galat(f"{k}: wajib diisi.")
    try:
        if isinstance(v, float) and v != int(v):
            raise ValueError
        return int(v)
    except (TypeError, ValueError):
        raise Galat(f"{k}: harus berupa bilangan bulat.")


def tanggal(d, k):
    """Mengembalikan tanggal dalam format ISO (YYYY-MM-DD)."""
    v = d.get(k)
    try:
        return date.fromisoformat(v).isoformat()
    except (TypeError, ValueError):
        raise Galat(f"{k}: tanggal tidak valid (format YYYY-MM-DD).")


def daftar(d, k, min_item=0):
    v = d.get(k, [])
    if not isinstance(v, list):
        raise Galat(f"{k}: harus berupa daftar.")
    if len(v) < min_item:
        raise Galat(f"{k}: minimal {min_item} item.")
    return [objek(x) for x in v]
