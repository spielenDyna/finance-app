"""Membaca foto struk belanja dengan Claude (vision).

Foto hanya diproses di memori lalu dibuang: tidak ditulis ke disk maupun database.
Hasilnya berupa draf yang harus diperiksa pengguna sebelum disimpan.
"""
import base64
import json
import os

import anthropic

MODEL = os.environ.get("STRUK_MODEL", "claude-haiku-5-5")
MEDIA_DIIZINKAN = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAKS_BYTE = 8 * 1024 * 1024

SKEMA = {
    "type": "object",
    "properties": {
        "tanggal": {"type": "string", "description": "Tanggal transaksi format YYYY-MM-DD, atau string kosong jika tidak terbaca."},
        "pemasok": {"type": "string", "description": "Nama toko/pemasok, atau string kosong."},
        "item": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nama_struk": {"type": "string", "description": "Nama barang persis seperti tercetak di struk."},
                    "jumlah": {"type": "number", "description": "Jumlah yang dibeli seperti tercetak (mis. 2 untuk '2 x')."},
                    "total": {"type": "number", "description": "Total harga baris ini dalam rupiah, setelah diskon baris jika ada. Tanpa titik/koma ribuan."},
                    "bahan_id": {"type": "integer", "description": "id bahan yang paling cocok dari daftar, atau 0 jika tidak ada yang cocok/ragu."},
                    "qty_bahan": {"type": "number", "description": "Jumlah dalam satuan bahan yang dipilih (mis. 2 bungkus @500 g => 1000 untuk bahan bersatuan gram). 0 jika bahan_id 0 atau tidak bisa dihitung pasti."},
                },
                "required": ["nama_struk", "jumlah", "total", "bahan_id", "qty_bahan"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["tanggal", "pemasok", "item"],
    "additionalProperties": False,
}

PETUNJUK = """Kamu membaca foto struk pembelian bahan baku sebuah usaha makanan di Indonesia (umumnya struk minimarket).
Ekstrak tanggal transaksi, nama toko, dan setiap barang yang dibeli.

Aturan:
- Angka rupiah di struk memakai titik sebagai pemisah ribuan (15.000 = 15000).
- "total" adalah jumlah yang dibayar untuk baris itu (harga satuan x jumlah, dikurangi diskon baris bila ada).
- Abaikan baris subtotal, PPN, total belanja, tunai, kembalian, poin, dan donasi/kantong plastik bila bukan bahan.
- Jangan menebak: jika tulisan tidak terbaca, isi string kosong atau 0 dan jangan mengarang barang.
- Cocokkan tiap barang ke daftar bahan di bawah memakai bahan_id. Singkatan struk lazim ("AYM FILLET" = ayam fillet). Jika tidak ada yang jelas cocok, bahan_id = 0.
- Isi qty_bahan hanya bila ukuran/berat tercetak di nama barang atau jumlah sudah dalam satuan bahan itu (mis. "ANDALAN GULA 1KG" x2 untuk bahan 'gram' => 2000). Selain itu 0.

Daftar bahan (id | nama | satuan):
"""


class StrukGagal(Exception):
    """Pesan aman ditampilkan ke pengguna."""

    def __init__(self, pesan: str, status: int = 502):
        super().__init__(pesan)
        self.pesan, self.status = pesan, status


def baca(gambar: bytes, media_type: str, bahan: list[dict]) -> dict:
    if media_type not in MEDIA_DIIZINKAN:
        raise StrukGagal("Format gambar tidak didukung (pakai JPG, PNG, WebP, atau GIF).", 415)
    if not gambar or len(gambar) > MAKS_BYTE:
        raise StrukGagal("Ukuran gambar tidak valid (maks. 8 MB).", 413)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise StrukGagal("ANTHROPIC_API_KEY belum diatur di server.", 503)

    daftar = "\n".join(f"{b['id']} | {b['nama']} | {b['satuan']}" for b in bahan) or "(belum ada bahan)"
    client = anthropic.Anthropic(max_retries=2, timeout=90.0)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            output_config={"format": {"type": "json_schema", "schema": SKEMA}},
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                                 "data": base64.standard_b64encode(gambar).decode("ascii")}},
                    {"type": "text", "text": PETUNJUK + daftar},
                ],
            }],
        )
    except anthropic.AuthenticationError:
        raise StrukGagal("API key Anthropic ditolak. Periksa ANTHROPIC_API_KEY.", 503)
    except anthropic.RateLimitError:
        raise StrukGagal("Layanan OCR sedang sibuk. Coba lagi sebentar lagi.", 429)
    except anthropic.APIConnectionError:
        raise StrukGagal("Tidak bisa menghubungi layanan OCR.", 502)
    except anthropic.APIStatusError as e:
        raise StrukGagal(f"Layanan OCR gagal (kode {e.status_code}).", 502)

    if resp.stop_reason in ("refusal", "max_tokens"):
        raise StrukGagal("Struk tidak bisa dibaca. Coba foto yang lebih jelas.", 422)
    teks = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        hasil = json.loads(teks)
    except json.JSONDecodeError:
        raise StrukGagal("Hasil pembacaan tidak valid. Coba lagi.", 502)

    # bahan_id hanya boleh salah satu id yang kita kirim; selain itu dianggap tidak cocok.
    valid = {b["id"] for b in bahan}
    for it in hasil["item"]:
        if it["bahan_id"] not in valid:
            it["bahan_id"], it["qty_bahan"] = 0, 0
    return hasil
