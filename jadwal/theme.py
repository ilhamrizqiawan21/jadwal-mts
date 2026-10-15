"""Tema tampilan aplikasi (hanya gaya ttk; tidak memengaruhi isi cetakan/ekspor).

Gagasan tampilan: "meja kerja madrasah". Bilah atas gelap (tinta) memegang identitas
dan tindakan utama; di bawahnya permukaan terang, dan kisi jadwal diletakkan seperti
selembar kertas di atas meja. Aksen hijau diambil dari logo madrasah (#00AA51),
bukan warna bawaan, supaya aplikasi terasa milik sekolah ini.

Sengaja ringan: satu kali konfigurasi gaya saat mulai, tanpa gambar, tanpa pustaka
tambahan, tanpa pewaktu/animasi. Warna dipusatkan di sini supaya mudah diubah.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont, ttk

# --------------------------------------------------------------------- huruf
# Segoe UI membawa data (angka & kode guru: paling mudah dibaca pada ukuran kecil).
# Bahnschrift — huruf papan petunjuk bawaan Windows — membawa judul dan label:
# jadwal pada dasarnya papan jadwal, dan huruf sempitnya hemat tempat pada kisi.
FONT = "Segoe UI"
_UI_PILIHAN = ("Bahnschrift SemiBold", "Segoe UI Semibold", "Segoe UI")
_COND_PILIHAN = ("Bahnschrift Condensed", "Bahnschrift", "Segoe UI")
FONT_UI = FONT       # judul, label, tombol  (diisi saat apply())
FONT_COND = FONT     # judul hari pada kisi


def _pilih_font(root: tk.Misc, pilihan) -> str:
    """Huruf pertama yang benar-benar terpasang. Mesin tanpa Bahnschrift tetap rapi."""
    try:
        ada = set(tkfont.families(root))
    except tk.TclError:
        return pilihan[-1]
    return next((f for f in pilihan if f in ada), pilihan[-1])


# ---------------------------------------------------------------------- palet
INK = "#0E2A21"          # bilah atas (tinta hijau gelap)
INK_SOFT = "#1B3A30"     # sorot di bilah atas
INK_LINE = "#2B5546"     # pemisah di bilah atas
INK_TEXT = "#FFFFFF"
INK_MUTED = "#9DBBAE"

BG = "#E9EDE9"           # latar jendela (meja)
SURFACE = "#FFFFFF"      # permukaan (tabel, kolom isian, kartu)
SUBTLE = "#F2F6F3"       # isian redup: kepala tabel, baris selang-seling
BORDER = "#D2DAD4"
BORDER_SOFT = "#E4E9E5"
TEXT = "#14241E"
MUTED = "#5F6F68"
ACCENT = "#00A651"       # hijau logo madrasah
ACCENT_DK = "#00843F"
ACCENT_LT = "#E2F4EA"
HOVER = "#DEE6E0"
SELECT = "#CBEBD8"
SHADOW = "#CFD7D1"       # bayangan tipis di bawah kertas/kartu

# kisi jadwal (kanvas): garis lembut, judul berwarna, jam tutup abu gelap (bukan hitam pekat)
GRID_EDGE = "#8FA39A"       # tepi blok/judul
GRID_LINE = "#C3CEC7"       # garis antar sel
GRID_HEAD = "#EDF2EE"       # judul kelas & sumbu waktu
GRID_DAY = "#D4EDE0"        # judul hari
GRID_REST = "#EFF3F0"       # baris istirahat
GRID_CLOSED = "#2C3A34"     # jam tidak dipakai
GRID_BAND = "#5FBF8C"       # sorot baris/kolom sel terpilih
BAD = "#D92D20"             # sel bentrok

ERR_FG, ERR_BG = "#B42318", "#FCE8E5"
WARN_FG, WARN_BG = "#8A5200", "#FBEFD6"
INFO_FG, INFO_BG = "#4A5C55", "#E5EBE7"
OK_FG, OK_BG = "#0A7A42", "#DFF3E7"


def apply(root: tk.Misc):
    """Pasang tema ke seluruh aplikasi. Aman dipanggil sekali sebelum widget dibuat."""
    global FONT_UI, FONT_COND
    FONT_UI = _pilih_font(root, _UI_PILIHAN)
    FONT_COND = _pilih_font(root, _COND_PILIHAN)

    for name, size in (("TkDefaultFont", 10), ("TkTextFont", 10), ("TkMenuFont", 10),
                       ("TkHeadingFont", 10), ("TkCaptionFont", 10), ("TkFixedFont", 10)):
        try:
            f = tkfont.nametofont(name)
            f.configure(family=FONT if name != "TkFixedFont" else f.cget("family"), size=size)
        except tk.TclError:
            pass
    root.option_add("*Font", "TkDefaultFont")
    root.configure(background=BG)

    s = ttk.Style(root)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass

    s.configure(".", background=BG, foreground=TEXT, bordercolor=BORDER, lightcolor=BG, darkcolor=BG,
                troughcolor=BG, focuscolor=BG, font="TkDefaultFont")
    s.configure("TFrame", background=BG)
    s.configure("TLabel", background=BG, foreground=TEXT)
    s.configure("TSeparator", background=BORDER)
    s.configure("TLabelframe", background=BG, bordercolor=BORDER, relief="solid")
    s.configure("TLabelframe.Label", background=BG, foreground=MUTED, font=(FONT_UI, 9))

    _tombol(s)
    _isian(s)
    _tab(s)
    _tabel(s)
    _gulir(s)
    s.configure("TPanedwindow", background=BG)
    s.configure("Sash", sashthickness=8, background=BG)
    apply_cards(s)


def _tombol(s: ttk.Style):
    """Tiga tingkat tombol: utama (hijau penuh), biasa (putih bergaris), alat (datar)."""
    s.configure("TButton", padding=(13, 6), relief="solid", borderwidth=1, background=SURFACE, foreground=TEXT,
                bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE, anchor="center", font=(FONT_UI, 10))
    s.map("TButton",
          background=[("pressed", HOVER), ("active", SUBTLE), ("disabled", BG)],
          foreground=[("disabled", MUTED)],
          bordercolor=[("focus", ACCENT), ("pressed", ACCENT), ("active", MUTED)])

    s.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF", bordercolor=ACCENT,
                lightcolor=ACCENT, darkcolor=ACCENT, font=(FONT_UI, 10))
    s.map("Accent.TButton",
          background=[("pressed", ACCENT_DK), ("active", ACCENT_DK), ("disabled", BORDER)],
          bordercolor=[("pressed", ACCENT_DK), ("active", ACCENT_DK), ("disabled", BORDER)],
          lightcolor=[("active", ACCENT_DK)], darkcolor=[("active", ACCENT_DK)],
          foreground=[("disabled", "#FFFFFF")])

    s.configure("Tool.TButton", padding=(10, 6), relief="flat", background=BG, bordercolor=BG,
                lightcolor=BG, darkcolor=BG, foreground=TEXT, font=(FONT_UI, 10))
    s.map("Tool.TButton", background=[("pressed", SELECT), ("active", HOVER)],
          bordercolor=[("active", HOVER), ("pressed", SELECT)],
          lightcolor=[("active", HOVER)], darkcolor=[("active", HOVER)])

    # tombol di dalam bilah atas yang gelap
    s.configure("Ink.TFrame", background=INK)
    s.configure("Ink.TLabel", background=INK, foreground=INK_TEXT)
    s.configure("InkMuted.TLabel", background=INK, foreground=INK_MUTED, font=(FONT, 9))
    s.configure("InkTitle.TLabel", background=INK, foreground=INK_TEXT, font=(FONT_UI, 14))
    s.configure("Ink.TButton", padding=(12, 6), relief="flat", borderwidth=0, background=INK,
                foreground="#DCEAE3", bordercolor=INK, lightcolor=INK, darkcolor=INK, font=(FONT_UI, 10))
    s.map("Ink.TButton",
          background=[("pressed", INK_LINE), ("active", INK_SOFT), ("disabled", INK)],
          lightcolor=[("active", INK_SOFT), ("pressed", INK_LINE)],
          darkcolor=[("active", INK_SOFT), ("pressed", INK_LINE)],
          bordercolor=[("active", INK_SOFT), ("pressed", INK_LINE)],
          foreground=[("active", "#FFFFFF"), ("disabled", "#4E6B5F")])
    s.configure("InkAccent.TButton", background=ACCENT, foreground="#FFFFFF", bordercolor=ACCENT,
                lightcolor=ACCENT, darkcolor=ACCENT, padding=(16, 6), font=(FONT_UI, 10))
    s.map("InkAccent.TButton",
          background=[("pressed", ACCENT_DK), ("active", "#00B85A"), ("disabled", INK_SOFT)],
          lightcolor=[("active", "#00B85A")], darkcolor=[("active", "#00B85A")],
          bordercolor=[("active", "#00B85A"), ("pressed", ACCENT_DK), ("disabled", INK_SOFT)],
          foreground=[("disabled", "#5E7A6D")])

    # saklar pilihan (mis. "Seperti cetakan" / "Per hari")
    s.configure("Toolbutton", padding=(12, 5), background=SUBTLE, bordercolor=SUBTLE, lightcolor=SUBTLE,
                darkcolor=SUBTLE, relief="flat", foreground=MUTED, font=(FONT_UI, 10))
    s.map("Toolbutton", background=[("selected", SURFACE), ("active", HOVER)],
          lightcolor=[("selected", SURFACE)], darkcolor=[("selected", SURFACE)],
          foreground=[("selected", ACCENT_DK), ("active", TEXT)],
          bordercolor=[("selected", BORDER), ("active", HOVER)])


def _isian(s: ttk.Style):
    for w in ("TEntry", "TCombobox", "TSpinbox"):
        s.configure(w, fieldbackground=SURFACE, background=SURFACE, bordercolor=BORDER,
                    lightcolor=SURFACE, darkcolor=SURFACE, padding=5, arrowcolor=MUTED,
                    insertcolor=TEXT, selectbackground=SELECT, selectforeground=TEXT)
        s.map(w, bordercolor=[("focus", ACCENT), ("hover", MUTED)], lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)], arrowcolor=[("active", ACCENT_DK)])
    s.map("TCombobox", fieldbackground=[("readonly", SURFACE)], selectbackground=[("readonly", SURFACE)],
          selectforeground=[("readonly", TEXT)])
    for w in ("TCheckbutton", "TRadiobutton"):
        s.configure(w, background=BG, indicatorcolor=SURFACE, bordercolor=BORDER)
        s.map(w, background=[("active", BG)], indicatorcolor=[("selected", ACCENT)],
              bordercolor=[("selected", ACCENT), ("focus", ACCENT)])


def _tab(s: ttk.Style):
    """Tab utama: garis hijau tegas di bawah tab terpilih (bukan kotak bersambung)."""
    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 2, 0, 0))
    s.configure("TNotebook.Tab", padding=(16, 9), background=BG, foreground=MUTED, borderwidth=0,
                lightcolor=BG, darkcolor=BG, bordercolor=BG, font=(FONT_UI, 10))
    s.map("TNotebook.Tab",
          background=[("selected", SURFACE), ("active", HOVER)],
          foreground=[("selected", ACCENT_DK), ("active", TEXT)],
          lightcolor=[("selected", ACCENT)], darkcolor=[("selected", SURFACE)],
          bordercolor=[("selected", SURFACE)],
          expand=[("selected", (0, 0, 0, 0))])
    # garis aksen ditempatkan di sisi ATAS tab terpilih
    s.layout("TNotebook.Tab", [("Notebook.tab", {"sticky": "nswe", "children": [
        ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
            ("Notebook.label", {"side": "top", "sticky": ""})]})]})])


def _tabel(s: ttk.Style):
    s.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, rowheight=29,
                borderwidth=0, bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE)
    s.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", TEXT)])
    s.configure("Treeview.Heading", background=SUBTLE, foreground=MUTED, relief="flat", padding=(8, 8),
                font=(FONT_UI, 9), bordercolor=BORDER_SOFT, lightcolor=SUBTLE, darkcolor=SUBTLE)
    s.map("Treeview.Heading", background=[("active", HOVER)], foreground=[("active", TEXT)])
    s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])    # tanpa garis fokus


def _gulir(s: ttk.Style):
    """Bilah gulir ramping: hanya jalur + gagang, tanpa tombol panah."""
    for orient, sisi in (("Vertical", "ns"), ("Horizontal", "ew")):
        s.layout(f"{orient}.TScrollbar", [(f"{orient}.Scrollbar.trough", {"sticky": sisi, "children": [
            (f"{orient}.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        s.configure(f"{orient}.TScrollbar", background="#C2CCC5", troughcolor=BG, bordercolor=BG,
                    lightcolor="#C2CCC5", darkcolor="#C2CCC5", arrowsize=11, relief="flat", gripcount=0)
        s.map(f"{orient}.TScrollbar", background=[("active", "#9BAAA1"), ("pressed", "#7C8D84")])


def apply_cards(s: ttk.Style):
    """Gaya kartu (panel putih berbingkai) untuk tab Pengaturan & layar sambutan."""
    s.configure("Card.TFrame", background=SURFACE)
    s.configure("Card.TLabel", background=SURFACE, foreground=TEXT)
    s.configure("CardTitle.TLabel", background=SURFACE, foreground=TEXT, font=(FONT_UI, 11))
    s.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED)
    s.configure("Muted.TLabel", background=BG, foreground=MUTED)
    s.configure("Section.TLabel", background=BG, foreground=TEXT, font=(FONT_UI, 11))
    # tombol langkah pada layar sambutan: teks rata kiri, dibaca sebagai daftar
    s.configure("Step.TButton", anchor="w", padding=(14, 8), background=SURFACE, bordercolor=BORDER)
    s.map("Step.TButton", background=[("active", SUBTLE), ("pressed", HOVER)],
          bordercolor=[("active", MUTED), ("focus", ACCENT)])
    s.configure("StepAccent.TButton", anchor="w", padding=(14, 8), background=ACCENT, foreground="#FFFFFF",
                bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT, font=(FONT_UI, 10))
    s.map("StepAccent.TButton", background=[("pressed", ACCENT_DK), ("active", ACCENT_DK)],
          bordercolor=[("pressed", ACCENT_DK), ("active", ACCENT_DK)],
          lightcolor=[("active", ACCENT_DK)], darkcolor=[("active", ACCENT_DK)])
    s.configure("Bar.TFrame", background=SURFACE)
    s.configure("Bar.TLabel", background=SURFACE, foreground=MUTED)
    s.configure("Bar.TButton", padding=(10, 6), relief="flat", background=SURFACE, bordercolor=SURFACE,
                lightcolor=SURFACE, darkcolor=SURFACE, foreground=TEXT, font=(FONT_UI, 10))
    s.map("Bar.TButton", background=[("pressed", SELECT), ("active", SUBTLE)],
          lightcolor=[("active", SUBTLE)], darkcolor=[("active", SUBTLE)],
          bordercolor=[("active", SUBTLE), ("pressed", SELECT)])
    s.configure("BarAccent.TButton", background=ACCENT, foreground="#FFFFFF", bordercolor=ACCENT,
                lightcolor=ACCENT, darkcolor=ACCENT, padding=(13, 6), font=(FONT_UI, 10))
    s.map("BarAccent.TButton",
          background=[("pressed", ACCENT_DK), ("active", ACCENT_DK), ("disabled", BORDER)],
          lightcolor=[("active", ACCENT_DK)], darkcolor=[("active", ACCENT_DK)],
          bordercolor=[("pressed", ACCENT_DK), ("active", ACCENT_DK), ("disabled", BORDER)])


# ------------------------------------------------------------------- bentuk
def round_rect(c: tk.Canvas, x0, y0, x1, y1, r, **kw):
    """Persegi bersudut tumpul pada kanvas (ttk tidak punya sudut tumpul)."""
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
           x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
    return c.create_polygon(pts, smooth=True, **kw)


class Pill(tk.Canvas):
    """Lencana status bersudut bulat: titik warna + teks. Mengukur lebarnya sendiri."""

    def __init__(self, parent, fg: str, bg: str, dot: str = "", command=None, bar_bg: str = BG):
        super().__init__(parent, bg=bar_bg, highlightthickness=0, bd=0, height=26, width=10)
        self.fg, self.bg, self.dot, self.cmd = fg, bg, dot or fg, command
        self._font = tkfont.Font(family=FONT_UI, size=10)
        if command:
            self.configure(cursor="hand2")
            self.bind("<Button-1>", lambda e: command())

    def set_text(self, text: str):
        self.delete("all")
        pad, d = 12, 7
        w = pad + (d + 8 if self.dot else 0) + self._font.measure(text) + pad
        self.configure(width=w, height=26)
        round_rect(self, 0, 0, w - 1, 25, 12, fill=self.bg, outline="")
        x = pad
        if self.dot:
            self.create_oval(x, 9, x + d, 9 + d, fill=self.dot, outline="")
            x += d + 8
        self.create_text(x, 13, text=text, anchor="w", fill=self.fg, font=self._font)


def card(parent: tk.Misc, title: str = "", padding=16) -> ttk.Frame:
    """Kartu: bayangan tipis + bingkai + isi putih. Kembalikan frame isi."""
    outer = tk.Frame(parent, bg=SHADOW)                      # lapis bawah = bayangan 1 px
    mid = tk.Frame(outer, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
    mid.pack(fill="both", expand=True, padx=(0, 1), pady=(0, 1))
    inner = ttk.Frame(mid, style="Card.TFrame", padding=padding)
    inner.pack(fill="both", expand=True)
    if title:
        ttk.Label(inner, text=title, style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
    inner.outer = outer           # bingkai luar: dipakai untuk grid()/pack()
    return inner


def toolbar(parent: tk.Misc, note: str = "") -> ttk.Frame:
    """Bilah alat putih dengan garis bawah tipis — pemisah antara tindakan dan isi.

    `note` menambah baris penjelas di bawah tombol, masih di permukaan putih yang sama.
    """
    wrap = tk.Frame(parent, bg=BORDER_SOFT)
    bar = ttk.Frame(wrap, style="Bar.TFrame", padding=(12, 8))
    bar.pack(fill="x")
    if note:
        ket = ttk.Frame(wrap, style="Bar.TFrame", padding=(12, 0, 12, 9))
        ket.pack(fill="x")
        ttk.Label(ket, text=note, style="Bar.TLabel", wraplength=900, justify="left").pack(anchor="w")
    tk.Frame(wrap, bg=BORDER_SOFT, height=1).pack(fill="x")
    bar.outer = wrap
    return bar


class Tooltip:
    """Petunjuk singkat saat kursor diam di atas widget. Pewaktu hanya jalan saat kursor di atasnya."""

    def __init__(self, widget: tk.Misc, text: str, delay: int = 500):
        self.w, self.text, self.delay = widget, text, delay
        self._job = None
        self._tip = None
        widget.bind("<Enter>", self._enter, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _enter(self, e=None):
        self._hide()
        self._job = self.w.after(self.delay, self._show)

    def _show(self):
        self._job = None
        if not self.w.winfo_exists():
            return
        self._tip = tk.Toplevel(self.w)
        self._tip.wm_overrideredirect(True)
        x, y = self.w.winfo_rootx() + 8, self.w.winfo_rooty() + self.w.winfo_height() + 6
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=self.text, bg=INK, fg="#EAF3EE", padx=10, pady=6,
                 font=(FONT, 9)).pack()

    def _hide(self, e=None):
        if self._job:
            self.w.after_cancel(self._job)
            self._job = None
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
