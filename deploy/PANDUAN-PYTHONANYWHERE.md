# Panduan PythonAnywhere (akun gratis)

Hasil akhir: `https://USERNAME.pythonanywhere.com` dengan HTTPS dan login password.
PythonAnywhere memakai WSGI, jadi FastAPI dibungkus dengan `a2wsgi`.

## 1. Daftar
Buat akun **Beginner (gratis)** di https://www.pythonanywhere.com. Username menjadi bagian alamat.

## 2. Unggah kode
Di PC, zip isi folder proyek **tanpa** `.venv`, `data`, `__pycache__`, `.pytest_cache`.
Di PythonAnywhere: tab **Files** > Upload `finance-app.zip` ke `/home/USERNAME/`, lalu buka **Consoles > Bash**:

    cd ~ && mkdir finance-app && cd finance-app && unzip ../finance-app.zip

## 3. Virtualenv
Masih di Bash console (samakan versi Python dengan yang dipilih di tab Web, mis. 3.12):

    mkvirtualenv fa --python=python3.12
    pip install -r ~/finance-app/requirements.txt a2wsgi

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

## Catatan
- Akun gratis: app tidur jika tidak di-*extend*; klik tombol **Run until 3 months from today**
  di tab Web setiap beberapa bulan.
- Data SQLite ada di `~/finance-app/data/`. Backup rutin: unduh file itu dari tab Files.
- Akun gratis hanya boleh mengakses internet lewat daftar putih; app ini tidak butuh akses keluar.
