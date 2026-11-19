#!/usr/bin/env bash
# Memasang Finance App di server Ubuntu (Oracle Cloud Always Free) lengkap dengan HTTPS.
# Pakai:  bash deploy/setup.sh namaanda.duckdns.org
# Jalankan sebagai user biasa (ubuntu), bukan root. Skrip memakai sudo seperlunya.
set -euo pipefail

DOMAIN="${1:?Pakai: bash deploy/setup.sh namaanda.duckdns.org}"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_USER="$(id -un)"

echo "==> Memasang paket sistem"
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-venv sqlite3 curl gpg debian-keyring debian-archive-keyring apt-transport-https iptables-persistent

if ! command -v caddy >/dev/null 2>&1; then
  echo "==> Memasang Caddy (HTTPS otomatis)"
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y caddy
fi

echo "==> Menyiapkan lingkungan Python"
cd "$APP_DIR"
python3 -m venv .venv
.venv/bin/pip install --quiet -r requirements.txt
mkdir -p data backup

if [ ! -f data/login.json ]; then
  echo "==> Buat password login aplikasi"
  .venv/bin/python atur_password.py
fi

echo "==> Memasang layanan systemd"
sudo tee /etc/systemd/system/finance-app.service >/dev/null <<EOF
[Unit]
Description=Finance App
After=network.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now finance-app
sudo systemctl restart finance-app

echo "==> Mengatur Caddy untuk $DOMAIN"
sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
$DOMAIN {
    reverse_proxy 127.0.0.1:8765
}
EOF
sudo systemctl restart caddy

echo "==> Membuka port 80 dan 443 di firewall server"
for port in 80 443; do
  sudo iptables -C INPUT -m state --state NEW -p tcp --dport "$port" -j ACCEPT 2>/dev/null \
    || sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport "$port" -j ACCEPT
done
sudo netfilter-persistent save

echo "==> Memasang backup harian (simpan 14 hari terakhir)"
CRON_LINE="30 2 * * * cd $APP_DIR && sqlite3 data/keuangan.db \".backup backup/keuangan-\$(date +\\%F).db\" && find backup -name 'keuangan-*.db' -mtime +14 -delete"
( crontab -l 2>/dev/null | grep -v 'backup/keuangan-' ; echo "$CRON_LINE" ) | crontab -

echo
echo "Selesai. Buka https://$DOMAIN setelah DNS DuckDNS mengarah ke server ini."
echo "Cek status:  sudo systemctl status finance-app caddy"
