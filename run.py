"""Jalankan Finance App lalu buka di browser."""
import threading
import webbrowser

from waitress import serve

from app import auth

HOST, PORT = "127.0.0.1", 8765

if __name__ == "__main__":
    if auth.muat_konfigurasi() is None:
        import atur_password
        atur_password.main()
    from app.main import app

    threading.Timer(1.5, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    serve(app, host=HOST, port=PORT)
