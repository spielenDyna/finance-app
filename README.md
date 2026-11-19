# Finance App

Aplikasi pencatatan keuangan usaha (satu usaha): penjualan, pembelian bahan, beban,
persediaan, HPP, dan laporan laba rugi yang menampilkan rumus serta transaksi sumbernya.

## Menjalankan
Klik dua kali `Jalankan.bat`. Saat pertama kali, file ini menyiapkan lingkungan Python
lalu membuka `http://127.0.0.1:8765` di browser.

Data tersimpan di `data/keuangan.db` (SQLite). Untuk backup, salin file tersebut.

## Alur pemakaian
1. **Bahan & Stok**: daftarkan bahan baku dan satuannya (gram, ml, pcs).
2. **Produk & Resep**: daftarkan produk, harga jual, dan takaran bahan per 1 unit.
3. **Pembelian Bahan**: catat setiap belanja bahan. Stok dan harga rata-rata akan ter-update.
4. **Penjualan**: catat pesanan. HPP dihitung otomatis dari resep.
5. **Beban**: biaya operasional selain bahan baku (kemasan, ongkir, listrik, dll.).
6. **Stok Opname**: masukkan hasil hitung fisik. Selisihnya menjadi beban.
7. **Laba Rugi**: pilih periode, lalu klik baris rincian untuk melihat sumber angkanya.

## Rumus
- Harga rata-rata bahan = (stok lama × harga rata lama + total beli) ÷ (stok lama + qty beli)
- HPP per unit = Σ (takaran bahan × harga rata-rata bahan pada tanggal penjualan)
- Laba kotor = Pendapatan − HPP
- Laba bersih = Laba kotor − Beban operasional (termasuk selisih stok opname)

Semua transaksi persediaan diputar ulang secara kronologis setiap kali data berubah,
jadi input mundur tanggal atau penghapusan tetap menghasilkan angka yang benar.

## Pengembangan
```
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest
```

## Login
Saat pertama kali dijalankan, aplikasi meminta Anda membuat password. Password disimpan
sebagai hash di `data/login.json`. Untuk mengganti password, jalankan
`.venv\Scripts\python atur_password.py`. Mengganti password juga mengeluarkan semua sesi yang aktif.

## Akses dari luar (Cloudflare Tunnel, gratis)
1. Pasang cloudflared sekali saja: `winget install --id Cloudflare.cloudflared`
2. Jalankan `Jalankan.bat`, lalu di jendela lain jalankan `Tunnel.bat`.
3. Buka alamat `https://xxxx.trycloudflare.com` yang muncul di jendela Tunnel dari HP atau komputer mana pun.

Catatan: alamat versi gratis (`trycloudflare.com`) berubah setiap Tunnel dijalankan ulang.
PC harus tetap menyala dan kedua jendela harus terbuka. Untuk alamat tetap, perlu domain sendiri
yang dikelola di Cloudflare (named tunnel).
