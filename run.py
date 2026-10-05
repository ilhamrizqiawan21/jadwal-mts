"""Titik masuk aplikasi Jadwal Pelajaran."""
import os
import sys


def _lapor(pesan: str):
    """Tampilkan error awal ke operator (belum ada jendela utama)."""
    import tkinter as tk
    from tkinter import messagebox
    r = tk.Tk()
    r.withdraw()
    messagebox.showerror("Jadwal Pelajaran", pesan, parent=r)
    r.destroy()


def main():
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    from jadwal import model as M
    from jadwal.app import App, load_config, resource
    from jadwal.store import Store

    cfg = load_config()
    last = cfg.get("last")
    proyek, path = None, None
    if last and os.path.exists(last):
        try:
            proyek, path = M.load(last), last
        except Exception as ex:
            _lapor(f"Berkas terakhir tidak bisa dibuka:\n{last}\n\n{ex}\n\n"
                   f"Berkas tidak diubah. Aplikasi dibuka dengan data contoh; "
                   f"simpan ke nama lain agar tidak menimpa berkas tadi.")
    if proyek is None:
        sample = resource(os.path.join("data", "contoh-ganjil-2025-2026.jadwal"))
        try:
            proyek = M.load(sample) if os.path.exists(sample) else M.Proyek()
        except Exception as ex:
            _lapor(f"Data contoh tidak bisa dibaca, memulai dengan proyek kosong:\n{ex}")
            proyek = M.Proyek()
    app = App(Store(proyek, path))
    app.mainloop()


if __name__ == "__main__":
    main()
