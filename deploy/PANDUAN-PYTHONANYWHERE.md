# Panduan PythonAnywhere (akun gratis)

Hasil akhir: `https://USERNAME.pythonanywhere.com` dengan HTTPS dan login password.
Aplikasi memakai Flask (WSGI), yang didukung langsung oleh PythonAnywhere.

## 1. Daftar
Buat akun **Beginner (gratis)** di https://www.pythonanywhere.com. Username menjadi bagian alamat.

## 2. Ambil kode dari GitHub
Di **Consoles > Bash**:

    cd ~ && git clone https://github.com/spielenDyna/finance-app.git

Update berikutnya: `cd ~/finance-app && git pull`, lalu klik **Reload** di tab Web.
Jika paket di `requirements.txt` berubah, jalankan juga `workon fa && pip install -r requirements.txt`.

## 3. Virtualenv
Masih di Bash console (samakan versi Python dengan yang dipilih di tab Web, mis. 3.12):

    mkvirtualenv fa --python=python3.12
    pip install -r ~/finance-app/requirements.txt

## 4. Buat password login
    cd ~/finance-app && python atur_password.py

(Atau, jika ingin membawa data dari PC, unggah `data/keuangan.db` dan `data/login.json` ke `~/finance-app/data/`.)

## 5. Buat web app
Tab **Web** > **Add a new web app** > **Manual configuration** > pilih versi Python yang sama.
- **Virtualenv**: `/home/USERNAME/.virtualenvs/fa`
- **WSGI configuration file**: klik link-nya, hapus isinya, tempel isi `deploy/pythonanywhere_wsgi.py`
  (ganti `USERNAME`), simpan.
- Klik **Reload**, lalu buka `https://USERNAME.pythonanywhere.com`.

Error? Lihat **Error log** di tab Web.

## Fitur foto struk (OCR)
1. Buat API key di https://console.anthropic.com (beri batas pengeluaran bulanan kecil).
2. Di file WSGI tab Web, tambahkan di bawah `sys.path` dua baris ini (isi key Anda):

        import os
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."

   Key hanya ada di file WSGI di server, jangan dimasukkan ke git.
3. Klik **Reload**. Di tab Pembelian Bahan akan ada kartu "Isi dari foto struk".

Foto tidak disimpan: dikecilkan di browser, dikirim ke Anthropic untuk dibaca, lalu dibuang.
Hasil bacaan selalu Anda periksa dulu sebelum masuk ke database. Model default `claude-haiku-5-5`
(ubah lewat variabel `STRUK_MODEL` bila perlu).

## Catatan
- Akun gratis: app tidur jika tidak di-*extend*; klik tombol **Run until 3 months from today**
  di tab Web setiap beberapa bulan.
- Data SQLite ada di `~/finance-app/data/`. Backup rutin: unduh file itu dari tab Files.
- Akun gratis hanya boleh mengakses internet lewat daftar putih; app ini tidak butuh akses keluar.
