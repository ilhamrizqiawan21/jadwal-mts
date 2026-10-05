"""Jendela utama aplikasi Jadwal Pelajaran."""
from __future__ import annotations

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from . import checks, model as M
from .store import Store
from .ui_grid import GridView, FONT

# Mode pengembangan (hanya dari sumber, tidak pernah di exe): data & konfigurasi
# dipisah supaya uji coba tidak menyentuh berkas operator.
DEV = not getattr(sys, "frozen", False) and (
    "--dev" in sys.argv or os.environ.get("JADWAL_DEV") == "1")
APP_NAME = "Jadwal Pelajaran" + (" [DEV]" if DEV else "")
EXT = ".jadwal"


def resource(path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, path)


def data_dir() -> str:
    d = os.path.join(os.path.expanduser("~"), "Documents", "Jadwal Sekolah (DEV)" if DEV else "Jadwal Sekolah")
    os.makedirs(d, exist_ok=True)
    return d


def config_path() -> str:
    d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "JadwalMTs-dev" if DEV else "JadwalMTs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "config.json")


def load_config() -> dict:
    try:
        with open(config_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict):
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except OSError:
        pass


class App(tk.Tk):
    def __init__(self, store: Store):
        super().__init__()
        self.store = store
        self.cfg = load_config()
        self.geometry("1320x760")
        self.minsize(900, 560)
        self.option_add("*Font", (FONT, 9))
        try:
            ttk.Style().theme_use("vista")
        except tk.TclError:
            pass
        self._alert_job = None
        self._autosave_gagal = False
        self._build_menu()
        self._build_ui()
        self.store.listeners.append(self.refresh)
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.bind_all("<Control-s>", lambda e: self.save())
        self.bind_all("<Control-z>", lambda e: self.undo())
        self.bind_all("<Control-y>", lambda e: self.redo())
        self.after(60000, self._autosave)
        self.refresh()

    # -------------------------------------------------------------- menu
    def _build_menu(self):
        m = tk.Menu(self)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="Baru (kosong)…", command=self.new_empty)
        f.add_command(label="Semester baru dari jadwal ini…", command=self.new_semester)
        f.add_command(label="Buka…  Ctrl+O", command=self.open_file)
        f.add_separator()
        f.add_command(label="Simpan  Ctrl+S", command=self.save)
        f.add_command(label="Simpan sebagai…", command=self.save_as)
        f.add_separator()
        f.add_command(label="Ekspor PDF (siap cetak)…", command=self.export_pdf)
        f.add_command(label="Ekspor Excel…", command=self.export_xlsx)
        f.add_separator()
        f.add_command(label="Keluar", command=self.quit_app)
        m.add_cascade(label="Berkas", menu=f)
        e = tk.Menu(m, tearoff=0)
        e.add_command(label="Urungkan  Ctrl+Z", command=self.undo)
        e.add_command(label="Ulangi  Ctrl+Y", command=self.redo)
        m.add_cascade(label="Ubah", menu=e)
        v = tk.Menu(m, tearoff=0)
        v.add_command(label="Perbesar", command=lambda: self.gv.set_zoom(self.gv.zoom + 0.1))
        v.add_command(label="Perkecil", command=lambda: self.gv.set_zoom(self.gv.zoom - 0.1))
        v.add_command(label="Sesuaikan lebar jendela", command=lambda: (setattr(self.gv, "auto_fit", True), self.gv.fit_zoom()))
        m.add_cascade(label="Tampilan", menu=v)
        h = tk.Menu(m, tearoff=0)
        h.add_command(label="Cara pakai", command=self.help)
        m.add_cascade(label="Bantuan", menu=h)
        self.config(menu=m)
        self.bind_all("<Control-o>", lambda e: self.open_file())

    # ----------------------------------------------------------------- UI
    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=(6, 0))
        for text, cmd in (("Simpan", self.save), ("Urungkan", self.undo), ("Ulangi", self.redo),
                          ("Ekspor PDF", self.export_pdf), ("Ekspor Excel", self.export_xlsx)):
            ttk.Button(top, text=text, command=cmd).pack(side="left", padx=2)
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(top, text="–", width=3, command=lambda: self.gv.set_zoom(self.gv.zoom - 0.1)).pack(side="left")
        ttk.Label(top, text="Zoom").pack(side="left", padx=2)
        ttk.Button(top, text="+", width=3, command=lambda: self.gv.set_zoom(self.gv.zoom + 0.1)).pack(side="left")
        self.file_lbl = ttk.Label(top, text="", foreground="#555")
        self.file_lbl.pack(side="right", padx=6)

        self.banner = tk.Label(self, text="", anchor="w", padx=10, pady=4, font=(FONT, 10, "bold"),
                               cursor="hand2")
        self.banner.pack(fill="x", padx=6, pady=(6, 0))
        self.banner.bind("<Button-1>", lambda e: self.side.select(0))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)

        # tab jadwal = kisi + panel kanan
        jf = ttk.Frame(self.nb)
        self.nb.add(jf, text="  Jadwal  ")
        pw = ttk.PanedWindow(jf, orient="horizontal")
        pw.pack(fill="both", expand=True)
        self.gv = GridView(pw, self)
        pw.add(self.gv, weight=5)
        self.side = ttk.Notebook(pw)
        pw.add(self.side, weight=1)
        self._build_side()
        self.after(200, lambda: pw.sashpos(0, max(600, self.winfo_width() - 330)))

        from . import ui_data
        self.tab_beban = ui_data.BebanTab(self.nb, self)
        self.nb.add(self.tab_beban, text="  Beban Mengajar  ")
        self.tab_guru = ui_data.GuruTab(self.nb, self)
        self.nb.add(self.tab_guru, text="  Guru & Jam Berhalangan  ")
        self.tab_kelas = ui_data.KelasTab(self.nb, self)
        self.nb.add(self.tab_kelas, text="  Kelas  ")
        self.tab_set = ui_data.PengaturanTab(self.nb, self)
        self.nb.add(self.tab_set, text="  Pengaturan & Jam  ")

        sb = ttk.Frame(self)
        sb.pack(fill="x", padx=6, pady=(0, 6))
        self.hint = tk.Label(sb, text="", anchor="w", font=(FONT, 10))
        self.hint.pack(side="left", fill="x", expand=True)
        self.info = ttk.Label(sb, text="", foreground="#555")
        self.info.pack(side="right")

    def _build_side(self):
        # --- masalah
        mf = ttk.Frame(self.side)
        self.side.add(mf, text="Masalah")
        self.tv_issue = ttk.Treeview(mf, columns=("m",), show="tree", selectmode="browse")
        self.tv_issue.column("#0", width=0, stretch=False)
        self.tv_issue.column("m", width=300)
        self.tv_issue.heading("m", text="")
        self.tv_issue.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(mf, command=self.tv_issue.yview)
        sb.pack(side="right", fill="y")
        self.tv_issue.configure(yscrollcommand=sb.set)
        self.tv_issue.tag_configure("error", foreground="#c00000")
        self.tv_issue.tag_configure("warn", foreground="#a05a00")
        self.tv_issue.tag_configure("info", foreground="#555555")
        self.tv_issue.bind("<Double-1>", self._issue_jump)
        self.tv_issue.bind("<<TreeviewSelect>>", self._issue_select)
        # --- kode
        kf = ttk.Frame(self.side)
        self.side.add(kf, text="Kode guru")
        self.q = tk.StringVar()
        ent = ttk.Entry(kf, textvariable=self.q)
        ent.pack(fill="x", padx=3, pady=3)
        self.q.trace_add("write", lambda *a: self.fill_codes())
        self.tv_code = ttk.Treeview(kf, columns=("kode", "guru", "mapel", "sisa"), show="headings",
                                    selectmode="browse")
        for c, w, t in (("kode", 46, "Kode"), ("guru", 130, "Guru"), ("mapel", 90, "Mapel"), ("sisa", 40, "Sisa")):
            self.tv_code.heading(c, text=t)
            self.tv_code.column(c, width=w, anchor="w" if c != "sisa" else "center")
        ttk.Label(kf, text="Klik kode: sorot guru.  Klik dua kali: isi sel terpilih.",
                  wraplength=280, foreground="#555").pack(side="bottom", anchor="w", padx=3, pady=3)
        sb2 = ttk.Scrollbar(kf, command=self.tv_code.yview)
        sb2.pack(side="right", fill="y")
        self.tv_code.pack(side="left", fill="both", expand=True)
        self.tv_code.configure(yscrollcommand=sb2.set)
        self.tv_code.bind("<<TreeviewSelect>>", self._code_select)
        self.tv_code.bind("<Double-1>", self._code_put)

    # ------------------------------------------------------------- refresh
    def refresh(self):
        p, h = self.store.p, self.store.hasil
        n_err, n_info = h.jumlah(checks.ERROR), h.jumlah(checks.INFO)
        n_warn = h.jumlah(checks.WARN)
        if n_err:
            self.banner.config(text=f"✖  {n_err} masalah harus diperbaiki  (klik untuk melihat)",
                               bg="#ffd6d6", fg="#a00000")
        else:
            extra = f"   ·   {n_info} jam belum terpasang" if n_info else ""
            self.banner.config(text=f"✔  Tidak ada bentrok{extra}", bg="#d9f2dd", fg="#116611")
        if not self.store.dirty:
            self._autosave_gagal = False
        warn = "   ⚠ simpan otomatis gagal" if self._autosave_gagal else ""
        self.file_lbl.config(text=f"{self.store.nama_berkas}{' *' if self.store.dirty else ''}{warn}")
        self.title(f"{APP_NAME} — {self.store.nama_berkas}{' *' if self.store.dirty else ''}")
        self.fill_issues()
        self.fill_codes()
        self.gv.redraw()
        for tab in (self.tab_beban, self.tab_guru, self.tab_kelas, self.tab_set):
            tab.reload()
        self.info.config(text=f"{len(p.kelas)} kelas · {len(p.guru)} guru · {len(p.penugasan)} penugasan")

    def fill_issues(self):
        tv = self.tv_issue
        tv.delete(*tv.get_children())
        order = {checks.ERROR: 0, checks.WARN: 1, checks.INFO: 2}
        self._issues = sorted(self.store.hasil.masalah, key=lambda m: order[m.tingkat])
        for i, m in enumerate(self._issues):
            mark = {"error": "✖ ", "warn": "⚠ ", "info": "• "}[m.tingkat]
            tv.insert("", "end", iid=str(i), values=(mark + m.pesan,), tags=(m.tingkat,))

    def fill_codes(self):
        tv = self.tv_code
        tv.delete(*tv.get_children())
        p = self.store.p
        q = self.q.get().strip().lower()
        kid = self.gv.sel[2] if self.gv.sel else None
        h = self.store.hasil
        seen = set()
        rows = []
        for a in p.penugasan:
            if not a.kode or a.kode.upper() in seen:
                continue
            seen.add(a.kode.upper())
            g = p.guru_by_id(a.guru)
            gn = g.nama if g else "?"
            if q and q not in a.kode.lower() and q not in gn.lower() and q not in a.mapel.lower():
                continue
            sisa = ""
            if kid and a.beban:
                sisa = str(a.beban.get(kid, 0) - h.terpasang.get((a.kode.upper(), kid), 0))
                if a.beban.get(kid) is None:
                    sisa = "–"
            rows.append((a.kode, gn, a.mapel, sisa, a.guru))
        for r in rows:
            tv.insert("", "end", iid=r[0], values=r[:4])
        self._code_guru = {r[0]: r[4] for r in rows}

    # --------------------------------------------------------- interaksi
    def on_select(self, key):
        self.fill_codes()
        if key:
            hari, bid, kid = key
            k = self.store.p.kelas_by_id(kid)
            self.show_hint((f"{hari} · {checks.label_waktu(self.store.p, hari, bid).split(' ', 1)[1]} · "
                            f"kelas {k.nama if k else ''}", False))

    def show_hint(self, hint):
        text, bad = hint
        self.hint.config(text=text, fg="#c00000" if bad else "#333333")

    def alert(self, masalah: List[checks.Masalah]):
        """Peringatan aktif saat sebuah perubahan menimbulkan bentrok baru."""
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            self.bell()
        text = "BENTROK BARU:  " + "   |   ".join(m.pesan.replace("BENTROK: ", "") for m in masalah[:2])
        self.banner.config(text="⚠  " + text, bg="#ff9d00", fg="black")
        self.show_hint((masalah[0].pesan, True))
        if self._alert_job:
            self.after_cancel(self._alert_job)
        self._alert_job = self.after(9000, self.refresh)

    def _issue_select(self, e):
        sel = self.tv_issue.selection()
        if not sel:
            return
        m = self._issues[int(sel[0])]
        self.show_hint((m.pesan, m.tingkat == checks.ERROR))

    def _issue_jump(self, e):
        sel = self.tv_issue.selection()
        if not sel:
            return
        m = self._issues[int(sel[0])]
        if m.sel:
            self.gv.jump_to(m.sel[0])

    def _code_select(self, e):
        sel = self.tv_code.selection()
        if not sel:
            return
        self.gv.hl_guru = self._code_guru.get(sel[0])
        self.gv.redraw()

    def _code_put(self, e):
        sel = self.tv_code.selection()
        if sel:
            self.gv.put_code(sel[0])
            self.gv.canvas.focus_set()

    # --------------------------------------------------------------- file
    def undo(self):
        if not isinstance(self.focus_get(), (tk.Entry, ttk.Entry)):
            self.store.undo()

    def redo(self):
        if not isinstance(self.focus_get(), (tk.Entry, ttk.Entry)):
            self.store.redo()

    def save(self) -> bool:
        if not self.store.path:
            return self.save_as()
        try:
            self.store.save()
        except OSError as ex:
            messagebox.showerror(APP_NAME, f"Gagal menyimpan:\n{ex}")
            return False
        return True

    def save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            initialdir=data_dir(), defaultextension=EXT, filetypes=[("Berkas jadwal", "*" + EXT)],
            initialfile=self._default_name())
        if not path:
            return False
        try:
            self.store.save(path)
        except OSError as ex:
            messagebox.showerror(APP_NAME, f"Gagal menyimpan:\n{ex}")
            return False
        self.cfg["last"] = path
        save_config(self.cfg)
        return True

    def _default_name(self) -> str:
        m = self.store.p.meta
        return f"jadwal-{m.semester.lower()}-{m.tahun.replace(' ', '').replace('/', '-')}{EXT}"

    def _confirm_discard(self) -> bool:
        if not self.store.dirty:
            return True
        r = messagebox.askyesnocancel(APP_NAME, "Ada perubahan yang belum disimpan. Simpan dulu?")
        if r is None:
            return False
        if r:
            return self.save()
        return True

    def open_file(self, path: Optional[str] = None):
        if not self._confirm_discard():
            return
        path = path or filedialog.askopenfilename(initialdir=data_dir(),
                                                  filetypes=[("Berkas jadwal", "*" + EXT)])
        if not path:
            return
        try:
            p = M.load(path)
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Berkas tidak bisa dibuka:\n{ex}")
            return
        self.gv.sel = None
        self.store.replace(p, path)
        self.cfg["last"] = path
        save_config(self.cfg)

    def new_empty(self):
        if not self._confirm_discard():
            return
        p = M.Proyek()
        self.gv.sel = None
        self.store.replace(p, None)

    def new_semester(self):
        from .ui_data import SemesterBaruDialog
        SemesterBaruDialog(self)

    def _autosave(self):
        if self.store.dirty and self.store.path:
            try:
                self.store.save()
                gagal = False
            except OSError as ex:
                gagal = True
                self.show_hint((f"Simpan otomatis GAGAL: {ex}. Simpan manual (Ctrl+S) ke lokasi lain.", True))
            if gagal != self._autosave_gagal:
                self._autosave_gagal = gagal
                self.refresh()
        self.after(60000, self._autosave)

    def quit_app(self):
        if not self._confirm_discard():
            return
        self.destroy()

    # ------------------------------------------------------------- ekspor
    def _warn_before_export(self) -> bool:
        n = self.store.hasil.jumlah(checks.ERROR)
        if n:
            return messagebox.askyesno(
                APP_NAME, f"Masih ada {n} masalah (bentrok/kelebihan jam) di jadwal.\n"
                          f"Tetap diekspor?", icon="warning")
        return True

    def export_pdf(self):
        if not self._warn_before_export():
            return
        from .export_pdf import export_pdf
        m = self.store.p.meta
        path = filedialog.asksaveasfilename(
            initialdir=data_dir(), defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
            initialfile=f"JADWAL DAN KODE GURU {m.tahun.replace(' ', '').replace('/', '-')}.pdf")
        if not path:
            return
        try:
            export_pdf(self.store.p, path)
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Gagal membuat PDF:\n{ex}")
            return
        if messagebox.askyesno(APP_NAME, "PDF tersimpan. Buka sekarang?"):
            os.startfile(path)

    def export_xlsx(self):
        try:
            from .export_xlsx import export_xlsx
        except ImportError:
            messagebox.showinfo(APP_NAME, "Ekspor Excel belum tersedia.")
            return
        if not self._warn_before_export():
            return
        m = self.store.p.meta
        path = filedialog.asksaveasfilename(
            initialdir=data_dir(), defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"JADWAL DAN KODE GURU {m.tahun.replace(' ', '').replace('/', '-')}.xlsx")
        if not path:
            return
        try:
            export_xlsx(self.store.p, path)
        except Exception as ex:
            messagebox.showerror(APP_NAME, f"Gagal membuat Excel:\n{ex}")
            return
        if messagebox.askyesno(APP_NAME, "Excel tersimpan. Buka sekarang?"):
            os.startfile(path)

    def help(self):
        messagebox.showinfo(APP_NAME, (
            "CARA PAKAI (sama seperti di Excel)\n\n"
            "• Klik sel jadwal, ketik kode guru, tekan Enter (turun) atau Tab (kanan).\n"
            "• Dua kode dalam satu sel = kelas dibagi dua kelompok:  24A/6\n"
            "• Dua mapel berbeda pada JP 1 dan JP 2:  13|23\n"
            "• Merah = bentrok / kelebihan jam. Daftar masalah ada di panel kanan.\n"
            "• Tab 'Kode guru' di kanan: klik untuk menyorot guru, klik dua kali untuk mengisi.\n"
            "• Tab 'Guru & Jam Berhalangan': tandai jam yang diminta guru kosong.\n"
            "• Ctrl+Z urungkan · Ctrl+S simpan (otomatis disimpan tiap menit)."))
