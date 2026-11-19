# Panduan Oracle Cloud Always Free

Hasil akhirnya: Finance App berjalan 24 jam di `https://namaanda.duckdns.org`, gratis,
dengan HTTPS dan login password. PC Anda tidak perlu menyala.

## 1. Buat akun Oracle Cloud
1. Daftar di https://www.oracle.com/cloud/free/ dan pilih **Home Region** yang dekat
   (misalnya Singapore). Region ini tidak bisa diganti setelah akun dibuat.
2. Pendaftaran meminta kartu kredit/debit untuk verifikasi. Kartu tidak ditagih selama
   Anda hanya memakai sumber daya Always Free.

## 2. Buat server (VM)
1. Menu **Compute > Instances > Create instance**.
2. **Image**: Ubuntu 24.04 (atau 22.04).
3. **Shape**: pilih yang berlabel *Always Free eligible*:
   - `VM.Standard.E2.1.Micro` (AMD, 1 GB RAM) cukup untuk app ini dan biasanya tersedia.
   - `VM.Standard.A1.Flex` (ARM) lebih besar, tetapi sering kehabisan kapasitas.
4. **SSH keys**: pilih *Generate a key pair* lalu **unduh private key** dan simpan baik-baik.
5. Buat instance, lalu catat **Public IP address**-nya.

## 3. Buka port 80 dan 443 di jaringan Oracle
Menu instance > **Subnet** > **Default Security List** > **Add Ingress Rules**:
- Source CIDR `0.0.0.0/0`, protocol TCP, destination port `80`
- Source CIDR `0.0.0.0/0`, protocol TCP, destination port `443`

(Firewall di dalam server dibuka otomatis oleh skrip.)

## 4. Buat alamat tetap gratis (DuckDNS)
1. Masuk ke https://www.duckdns.org, lalu buat subdomain, misalnya `tokoku`.
2. Isi kolom **current ip** dengan Public IP server, lalu klik **update ip**.
3. Alamat Anda menjadi `tokoku.duckdns.org`.

## 5. Kirim aplikasi ke server
Di PowerShell pada PC Anda (ganti path key dan IP):

```powershell
cd "d:\Finance App"
tar --exclude=.venv --exclude=data --exclude=__pycache__ --exclude=.pytest_cache -czf "$env:TEMP\finance-app.tar.gz" .
scp -i "C:\path\ke\ssh-key.key" "$env:TEMP\finance-app.tar.gz" ubuntu@IP-SERVER:~/
ssh -i "C:\path\ke\ssh-key.key" ubuntu@IP-SERVER
```

Setelah masuk ke server:

```bash
mkdir -p ~/finance-app && tar -xzf ~/finance-app.tar.gz -C ~/finance-app
cd ~/finance-app
bash deploy/setup.sh tokoku.duckdns.org
```

Skrip akan meminta Anda membuat password login, lalu memasang semuanya.
Setelah selesai, buka `https://tokoku.duckdns.org` (sertifikat HTTPS dibuat otomatis
dalam beberapa detik pertama).

## 6. Pindahkan data lama (opsional)
Data tidak ikut terkirim pada langkah 5. Untuk membawa data dari PC, hentikan app di PC lalu:

```powershell
scp -i "C:\path\ke\ssh-key.key" "d:\Finance App\data\keuangan.db" ubuntu@IP-SERVER:~/finance-app/data/
```

```bash
sudo systemctl restart finance-app
```

## Perawatan
- **Backup**: skrip membuat salinan harian di `~/finance-app/backup/` (14 hari terakhir).
  Folder itu berada di server yang sama, jadi sesekali unduh ke PC:
  `scp -i KEY ubuntu@IP-SERVER:~/finance-app/backup/* "d:\backup-keuangan\"`
- **Ganti password**: `cd ~/finance-app && .venv/bin/python atur_password.py`, lalu
  `sudo systemctl restart finance-app`.
- **Perbarui kode**: kirim ulang arsip seperti langkah 5, ekstrak (folder `data` tidak
  tertimpa), lalu `sudo systemctl restart finance-app`.
- **Log/masalah**: `sudo journalctl -u finance-app -n 50` dan `sudo journalctl -u caddy -n 50`.

## Hal yang perlu diwaspadai
- Oracle dapat **menghentikan instance Always Free yang dianggap menganggur** (pemakaian CPU,
  jaringan, dan memori sangat rendah selama 7 hari). Jika terjadi, nyalakan lagi dari
  konsol. Mengubah akun ke *Pay As You Go* menghindarinya dan tetap gratis selama dalam batas
  Always Free, tetapi itu keputusan Anda.
- Jangan membuat sumber daya berbayar secara tidak sengaja. Pilih hanya yang berlabel
  *Always Free eligible*.
- Alamat IP publik tidak berubah selama instance tidak dihapus. Kalau berubah, perbarui di DuckDNS.
