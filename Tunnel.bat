@echo off
rem Membuka Finance App ke internet lewat Cloudflare Tunnel (gratis).
rem Jalankan Jalankan.bat dulu di jendela lain, lalu jalankan file ini.
cd /d "%~dp0"
where cloudflared >nul 2>nul
if errorlevel 1 (
  echo cloudflared belum terpasang.
  echo Pasang dengan perintah: winget install --id Cloudflare.cloudflared
  echo Setelah itu tutup dan buka lagi jendela ini.
  pause
  goto :eof
)
echo Alamat publik akan muncul di bawah (format https://xxxx.trycloudflare.com).
echo Biarkan jendela ini terbuka selama aplikasi dipakai.
cloudflared tunnel --url http://127.0.0.1:8765
pause
