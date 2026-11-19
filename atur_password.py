"""Membuat atau mengganti password login Finance App.

Dijalankan otomatis oleh Jalankan.bat saat password belum ada,
atau manual: .venv\Scripts\python atur_password.py
Mengganti password juga mengeluarkan semua sesi yang sedang aktif.
"""
import getpass
import sys

from app import auth


def main() -> int:
    print("Atur password untuk masuk ke Finance App.")
    while True:
        pw = getpass.getpass("Password baru (min. 6 karakter): ")
        if len(pw) < 6:
            print("Password terlalu pendek.\n")
            continue
        if pw != getpass.getpass("Ulangi password: "):
            print("Password tidak sama.\n")
            continue
        auth.simpan_password(pw)
        print("Password tersimpan.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
