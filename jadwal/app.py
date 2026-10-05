"""Jendela utama aplikasi Jadwal Pelajaran."""
from __future__ import annotations

import json
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

from . import checks, model as M, theme
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
        self._restore_geometry()
        self.minsize(900, 560)
        theme.apply(self)
        self._logo = self._muat_logo()
        if self._logo:
            self.iconphoto(True, self._logo)       # ikon jendela & bilah tugas
        self._alert_job = None
        self._grp_open = {checks.ERROR: True, checks.WARN: True, checks.INFO: False}
        self._issue_map = {}
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

    def _muat_logo(self, bagi: int = 1):
        """Logo madrasah (img/logo.png). Hanya kosmetik: bila berkas hilang, aplikasi tetap jalan."""
        try:
            im = tk.PhotoImage(master=self, file=resource(os.path.join("img", "logo.png")))
        except tk.TclError:
            return None
        return im.subsample(bagi) if bagi > 1 else im

    # ------------------------------------------------- ukuran jendela & zoom
    def _restore_geometry(self):
        """Pulihkan ukuran/posisi jendela terakhir (dijaga agar tetap berada di dalam layar)."""
        self.geometry("1320x760")
        g = self.cfg.get("geometry")
        m = re.fullmatch(r"(\d+)x(\d+)([+-]\d+)([+-]\d+)", g) if isinstance(g, str) else None
        if m:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            w = min(max(int(m[1]), 900), sw)
            h = min(max(int(m[2]), 560), sh)
            x = min(max(int(m[3]), 0), sw - w)
            y = min(max(int(m[4]), 0), sh - h)
            self.geometry(f"{w}x{h}+{x}+{y}")
        if self.cfg.get("maximized"):
            self.after_idle(lambda: self.state("zoomed"))

    def _save_window_state(self):
        zoomed = self.state() == "zoomed"
        self.cfg["maximized"] = zoomed
        if not zoomed:
            self.cfg["geometry"] = self.geometry()
        if self.gv.auto_fit:
            self.cfg.pop("zoom", None)
        else:
            self.cfg["zoom"] = round(self.gv.zoom, 2)
        save_config(self.cfg)

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
        top.pack(fill="x", padx=10, pady=(10, 0))
        def tombol(text, cmd, tip, style="Tool.TButton", **kw):
            b = ttk.Button(top, text=text, style=style, command=cmd, **kw)
            b.pack(side="left", padx=(0, 6) if style.startswith("Accent") else 0)
            theme.Tooltip(b, tip)
            return b

        def pemisah():
            ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=4, pady=3)

        tombol("Simpan", self.save, "Simpan berkas  (Ctrl+S)", style="Accent.TButton")
        pemisah()
        tombol("Urungkan", self.undo, "Urungkan perubahan terakhir  (Ctrl+Z)")
        tombol("Ulangi", self.redo, "Ulangi perubahan yang diurungkan  (Ctrl+Y)")
        pemisah()
        tombol("Ekspor PDF", self.export_pdf, "Buat PDF siap cetak (hal. 1 beban + hal. 2 jadwal)")
        tombol("Ekspor Excel", self.export_xlsx, "Buat berkas Excel dengan format yang sama")
        pemisah()
        tombol("–", lambda: self.gv.set_zoom(self.gv.zoom - 0.1), "Perkecil kisi jadwal", width=3)
        ttk.Label(top, text="Zoom", foreground=theme.MUTED).pack(side="left", padx=2)
        tombol("+", lambda: self.gv.set_zoom(self.gv.zoom + 0.1), "Perbesar kisi jadwal", width=3)
        self.file_lbl = ttk.Label(top, text="", foreground=theme.MUTED)
        self.file_lbl.pack(side="right", padx=6)

        # lencana status: ringkasan jadwal, diperbarui tiap perubahan (menggantikan banner penuh)
        self.chips = ttk.Frame(self)
        self.chips.pack(fill="x", padx=10, pady=(8, 0))
        self.chip_err = theme.chip(self.chips, "", theme.ERR_FG, theme.ERR_BG, self.show_issues)
        self.chip_ok = theme.chip(self.chips, "", theme.OK_FG, theme.OK_BG, self.show_issues)
        self.chip_warn = theme.chip(self.chips, "", theme.WARN_FG, theme.WARN_BG, self.show_issues)
        self.chip_info = theme.chip(self.chips, "", theme.INFO_FG, theme.INFO_BG, self.show_issues)
        for c in (self.chip_err, self.chip_ok, self.chip_warn, self.chip_info):
            theme.Tooltip(c, "Klik untuk membuka daftar masalah")

        # notifikasi bentrok baru: kartu melayang di kanan atas, hilang sendiri
        self.banner = tk.Label(self, text="", justify="left", anchor="w", padx=14, pady=9, wraplength=460,
                               font=(FONT, 10, "bold"), cursor="hand2", bg=theme.WARN_BG, fg="#6B3F00",
                               highlightthickness=1, highlightbackground="#F0B35A")
        self.banner.bind("<Button-1>", lambda e: (self.hide_toast(), self.show_issues()))

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(8, 10))

        # tab jadwal = kisi + panel kanan
        jf = ttk.Frame(self.nb)
        self.nb.add(jf, text="  Jadwal  ")
        pw = ttk.PanedWindow(jf, orient="horizontal")
        pw.pack(fill="both", expand=True)
        self.gv = GridView(pw, self)
        if isinstance(self.cfg.get("zoom"), (int, float)):
            self.gv.auto_fit = False
            self.gv.zoom = max(0.5, min(1.8, float(self.cfg["zoom"])))
        pw.add(self.gv, weight=5)
        self.side = ttk.Notebook(pw)
        pw.add(self.side, weight=1)
        self._build_side()
        self._welcome_parent = jf
        self.welcome = None            # dibangun saat pertama kali dibutuhkan (proyek kosong)
        # posisi pembatas diatur sekali, begitu panel sudah punya lebar sebenarnya
        # (bukan lewat pewaktu tetap, yang bisa berjalan sebelum jendela selesai tersusun)
        self._sash_set = False

        def _atur_pembatas(e):
            if not self._sash_set and pw.winfo_width() > 700:
                self._sash_set = True
                pw.sashpos(0, pw.winfo_width() - 350)
        pw.bind("<Configure>", _atur_pembatas)

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
        sb.pack(fill="x", padx=10, pady=(0, 8))
        self.hint = tk.Label(sb, text="", anchor="w", font=(FONT, 10), bg=theme.BG, fg=theme.TEXT)
        self.hint.pack(side="left", fill="x", expand=True)
        self.info = ttk.Label(sb, text="", foreground=theme.MUTED)
        self.info.pack(side="right")

    def _build_welcome(self, parent) -> tk.Frame:
        """Layar sambutan di atas tab Jadwal; tampil hanya selama proyek masih kosong."""
        w = tk.Frame(parent, bg=theme.BG)
        k = theme.card(w, padding=28)
        k.outer.place(relx=0.5, rely=0.4, anchor="center")
        self._logo_kecil = self._muat_logo(3)
        if self._logo_kecil:
            ttk.Label(k, image=self._logo_kecil, style="Card.TLabel").grid(
                row=0, column=2, rowspan=6, sticky="ne", padx=(28, 0))
        ttk.Label(k, text="Mulai menyusun jadwal", style="CardTitle.TLabel", font=(FONT, 15, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(k, style="CardMuted.TLabel", wraplength=460, justify="left",
                  text="Proyek ini masih kosong. Isi data dasarnya dulu, lalu kisi jadwal siap diisi.").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 14))
        langkah = (("1", "Tambah kelas", lambda: self.nb.select(self.tab_kelas)),
                   ("2", "Tambah guru", lambda: self.nb.select(self.tab_guru)),
                   ("3", "Isi beban mengajar", lambda: self.nb.select(self.tab_beban)),
                   ("4", "Isi judul & tanda tangan", lambda: self.nb.select(self.tab_set)))
        for i, (no, teks, cmd) in enumerate(langkah, start=2):
            ttk.Label(k, text=no, style="CardTitle.TLabel", foreground=theme.ACCENT, font=(FONT, 11, "bold")).grid(
                row=i, column=0, sticky="w", pady=3, padx=(0, 10))
            ttk.Button(k, text=teks, command=cmd, width=26).grid(row=i, column=1, sticky="w", pady=3)
        ttk.Separator(k).grid(row=6, column=0, columnspan=2, sticky="ew", pady=14)
        ttk.Button(k, text="Buka berkas yang sudah ada…", style="Accent.TButton", command=self.open_file).grid(
            row=7, column=0, columnspan=2, sticky="w")
        return w

    def _update_welcome(self):
        p = self.store.p
        if not (p.kelas or p.guru or p.penugasan):
            if self.welcome is None:
                self.welcome = self._build_welcome(self._welcome_parent)
            self.welcome.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.welcome.lift()
        elif self.welcome is not None:
            self.welcome.place_forget()

    def _build_side(self):
        # --- masalah
        mf = ttk.Frame(self.side)
        self.side.add(mf, text="Masalah")
        cari = ttk.Frame(mf)
        cari.pack(fill="x", padx=4, pady=(6, 4))
        ttk.Label(cari, text="Cari", foreground=theme.MUTED).pack(side="left", padx=(2, 6))
        self.q_issue = tk.StringVar()
        ttk.Entry(cari, textvariable=self.q_issue).pack(side="left", fill="x", expand=True)
        self.q_issue.trace_add("write", lambda *a: self.fill_issues())
        self.tv_issue = ttk.Treeview(mf, columns=(), show="tree", selectmode="browse")
        self.tv_issue.column("#0", width=300, stretch=True)
        sb = ttk.Scrollbar(mf, command=self.tv_issue.yview)
        sb.pack(side="right", fill="y")
        self.tv_issue.pack(side="left", fill="both", expand=True)
        self.tv_issue.configure(yscrollcommand=sb.set)
        hf = (FONT, 10, "bold")
        self.tv_issue.tag_configure("error", foreground=theme.ERR_FG)
        self.tv_issue.tag_configure("warn", foreground=theme.WARN_FG)
        self.tv_issue.tag_configure("info", foreground=theme.INFO_FG)
        self.tv_issue.tag_configure("ok", foreground=theme.OK_FG)
        for t, bg in (("error", theme.ERR_BG), ("warn", theme.WARN_BG), ("info", theme.INFO_BG)):
            self.tv_issue.tag_configure("h_" + t, background=bg, font=hf)
        self.tv_issue.bind("<Double-1>", self._issue_jump)
        self.tv_issue.bind("<<TreeviewSelect>>", self._issue_select)
        self.tv_issue.bind("<<TreeviewOpen>>", lambda e: self._grp_toggle(True))
        self.tv_issue.bind("<<TreeviewClose>>", lambda e: self._grp_toggle(False))
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
        self._update_chips(n_err, n_warn, n_info)
        self._update_welcome()
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

    def _update_chips(self, n_err: int, n_warn: int, n_info: int):
        """Lencana ringkasan di bawah toolbar; hanya yang relevan yang ditampilkan."""
        for c in (self.chip_err, self.chip_ok, self.chip_warn, self.chip_info):
            c.pack_forget()
        if n_err:
            self.chip_err.config(text=f"✖  {n_err} masalah harus diperbaiki")
            self.chip_err.pack(side="left", padx=(0, 6))
        else:
            self.chip_ok.config(text="✔  Tidak ada bentrok")
            self.chip_ok.pack(side="left", padx=(0, 6))
        if n_warn:
            self.chip_warn.config(text=f"⚠  {n_warn} peringatan")
            self.chip_warn.pack(side="left", padx=(0, 6))
        if n_info:
            self.chip_info.config(text=f"{n_info} jam belum terpasang")
            self.chip_info.pack(side="left", padx=(0, 6))

    GRUP = ((checks.ERROR, "✖  Harus diperbaiki"), (checks.WARN, "⚠  Peringatan"),
            (checks.INFO, "Belum lengkap"))

    def fill_issues(self):
        """Daftar masalah dikelompokkan per tingkat; 'Belum lengkap' (paling banyak) tertutup."""
        tv = self.tv_issue
        tv.delete(*tv.get_children())
        self._issue_map = {}
        q = self.q_issue.get().strip().lower()
        semua = self.store.hasil.masalah
        for tingkat, judul in self.GRUP:
            items = [m for m in semua if m.tingkat == tingkat and
                     (not q or q in (m.pesan + " " + m.ringkas).lower())]
            if not items:
                continue
            gid = "g:" + tingkat
            tv.insert("", "end", iid=gid, text=f"{judul}  ({len(items)})", tags=("h_" + tingkat,),
                      open=bool(q) or self._grp_open[tingkat])
            for m in items:
                iid = f"m{len(self._issue_map)}"
                self._issue_map[iid] = m
                tv.insert(gid, "end", iid=iid, text=m.ringkas or m.pesan, tags=(tingkat,))
        if not semua:
            tv.insert("", "end", iid="ok", text="✔  Tidak ada masalah", tags=("ok",))
        elif not tv.get_children():
            tv.insert("", "end", iid="none", text="Tidak ada yang cocok", tags=("info",))

    def _grp_toggle(self, terbuka: bool):
        sel = self.tv_issue.focus()
        if sel.startswith("g:") and not self.q_issue.get().strip():
            self._grp_open[sel[2:]] = terbuka

    def show_issues(self):
        self.nb.select(0)
        self.side.select(0)

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
        baris = [m.pesan.replace("BENTROK: ", "") for m in masalah[:2]]
        if len(masalah) > 2:
            baris.append(f"…dan {len(masalah) - 2} lainnya")
        self.banner.config(text="⚠  PERUBAHAN INI MENIMBULKAN MASALAH BARU\n" + "\n".join(baris))
        self.banner.place(relx=1.0, x=-16, y=60, anchor="ne")
        self.banner.lift()
        self.show_hint((masalah[0].pesan, True))
        if self._alert_job:
            self.after_cancel(self._alert_job)
        self._alert_job = self.after(8000, self.hide_toast)

    def hide_toast(self):
        if self._alert_job:
            self.after_cancel(self._alert_job)
            self._alert_job = None
        self.banner.place_forget()

    def _issue_select(self, e):
        sel = self.tv_issue.selection()
        m = self._issue_map.get(sel[0]) if sel else None
        if m:
            self.show_hint((m.pesan, m.tingkat == checks.ERROR))

    def _issue_jump(self, e):
        sel = self.tv_issue.selection()
        m = self._issue_map.get(sel[0]) if sel else None
        if m and m.sel:
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
        self._save_window_state()
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
