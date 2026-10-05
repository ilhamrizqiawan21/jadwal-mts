"""Tema tampilan aplikasi (hanya gaya ttk; tidak memengaruhi isi cetakan/ekspor).

Sengaja ringan: satu kali konfigurasi gaya saat mulai, tanpa gambar, tanpa pustaka
tambahan, tanpa pewaktu/animasi. Warna dipusatkan di sini supaya mudah diubah.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont, ttk

FONT = "Segoe UI"

# palet
BG = "#F4F6FA"          # latar jendela
SURFACE = "#FFFFFF"     # permukaan (tabel, kolom isian)
BORDER = "#D3D9E3"
TEXT = "#1F2937"
MUTED = "#667085"
ACCENT = "#2457D6"
ACCENT_DK = "#1B44AB"
ACCENT_LT = "#E4ECFD"
HOVER = "#E8ECF4"
SELECT = "#CFE0FF"

ERR_FG, ERR_BG = "#B42318", "#FDE8E6"
WARN_FG, WARN_BG = "#9A5B00", "#FFF1D6"
INFO_FG, INFO_BG = "#475467", "#EAECF0"
OK_FG, OK_BG = "#1A7A3E", "#E3F5E9"


def apply(root: tk.Misc):
    """Pasang tema ke seluruh aplikasi. Aman dipanggil sekali sebelum widget dibuat."""
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
    s.configure("TLabelframe.Label", background=BG, foreground=MUTED)

    # tombol
    s.configure("TButton", padding=(12, 5), relief="raised", borderwidth=1, background=SURFACE, foreground=TEXT,
                bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE, anchor="center")
    s.map("TButton",
          background=[("pressed", SELECT), ("active", HOVER), ("disabled", BG)],
          foreground=[("disabled", MUTED)],
          bordercolor=[("focus", ACCENT), ("active", BORDER)])
    s.configure("Accent.TButton", background=ACCENT, foreground="#FFFFFF", bordercolor=ACCENT,
                lightcolor=ACCENT, darkcolor=ACCENT, font=(FONT, 10, "bold"))
    s.map("Accent.TButton",
          background=[("pressed", ACCENT_DK), ("active", ACCENT_DK), ("disabled", BORDER)],
          bordercolor=[("pressed", ACCENT_DK), ("active", ACCENT_DK)],
          foreground=[("disabled", "#FFFFFF")])
    s.configure("Tool.TButton", padding=(9, 5), relief="flat", background=BG, bordercolor=BG, lightcolor=BG, darkcolor=BG)
    s.map("Tool.TButton", background=[("pressed", SELECT), ("active", HOVER)],
          bordercolor=[("active", HOVER), ("pressed", SELECT)])
    s.configure("Toolbutton", padding=(10, 4), background=BG, bordercolor=BG, lightcolor=BG, darkcolor=BG,
                relief="flat")
    s.map("Toolbutton", background=[("selected", ACCENT_LT), ("active", HOVER)],
          foreground=[("selected", ACCENT)], bordercolor=[("selected", ACCENT_LT), ("active", HOVER)])

    # kolom isian
    for w in ("TEntry", "TCombobox", "TSpinbox"):
        s.configure(w, fieldbackground=SURFACE, background=SURFACE, bordercolor=BORDER,
                    lightcolor=SURFACE, darkcolor=SURFACE, padding=4, arrowcolor=MUTED)
        s.map(w, bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)],
              darkcolor=[("focus", ACCENT)])
    s.map("TCombobox", fieldbackground=[("readonly", SURFACE)], selectbackground=[("readonly", SURFACE)],
          selectforeground=[("readonly", TEXT)])
    s.configure("TCheckbutton", background=BG)
    s.configure("TRadiobutton", background=BG)
    s.map("TCheckbutton", background=[("active", BG)])
    s.map("TRadiobutton", background=[("active", BG)])

    # tab
    s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(2, 4, 2, 0))
    s.configure("TNotebook.Tab", padding=(14, 7), background=BG, foreground=MUTED, borderwidth=0,
                lightcolor=BG, darkcolor=BG, bordercolor=BG)
    s.map("TNotebook.Tab",
          background=[("selected", SURFACE), ("active", HOVER)],
          foreground=[("selected", ACCENT), ("active", TEXT)],
          lightcolor=[("selected", SURFACE)], bordercolor=[("selected", BORDER)],
          expand=[("selected", (0, 0, 0, 0))])

    # tabel & daftar
    s.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=TEXT, rowheight=25,
                borderwidth=1, bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE)
    s.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", TEXT)])
    s.configure("Treeview.Heading", background="#EDF0F6", foreground=TEXT, relief="flat", padding=(6, 5),
                font=(FONT, 9, "bold"), bordercolor=BORDER, lightcolor="#EDF0F6", darkcolor="#EDF0F6")
    s.map("Treeview.Heading", background=[("active", HOVER)])
    s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])    # tanpa garis fokus

    # bilah gulir tipis
    for orient in ("Vertical", "Horizontal"):
        s.configure(f"{orient}.TScrollbar", background="#C3CAD6", troughcolor=BG, bordercolor=BG,
                    lightcolor="#C3CAD6", darkcolor="#C3CAD6", arrowsize=12, relief="flat")
        s.map(f"{orient}.TScrollbar", background=[("active", "#9AA4B5"), ("pressed", "#7F8AA0")])
    s.configure("TPanedwindow", background=BG)
    s.configure("Sash", sashthickness=6, background=BG)
    apply_cards(s)


def chip(parent: tk.Misc, text: str, fg: str, bg: str, command=None) -> tk.Label:
    """Label kecil berwarna (lencana status)."""
    lb = tk.Label(parent, text=text, fg=fg, bg=bg, padx=9, pady=3, font=(FONT, 9, "bold"),
                  cursor="hand2" if command else "")
    if command:
        lb.bind("<Button-1>", lambda e: command())
    return lb


def apply_cards(s: ttk.Style):
    """Gaya kartu (panel putih berbingkai) untuk tab Pengaturan & layar sambutan."""
    s.configure("Card.TFrame", background=SURFACE)
    s.configure("Card.TLabel", background=SURFACE, foreground=TEXT)
    s.configure("CardTitle.TLabel", background=SURFACE, foreground=TEXT, font=(FONT, 11, "bold"))
    s.configure("CardMuted.TLabel", background=SURFACE, foreground=MUTED)
    s.configure("Muted.TLabel", background=BG, foreground=MUTED)


def card(parent: tk.Misc, title: str = "", padding=14) -> ttk.Frame:
    """Kartu: bingkai tipis + isi putih. Kembalikan frame isi (tempat menaruh widget)."""
    outer = tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
    inner = ttk.Frame(outer, style="Card.TFrame", padding=padding)
    inner.pack(fill="both", expand=True)
    if title:
        ttk.Label(inner, text=title, style="CardTitle.TLabel", font=(FONT, 11, "bold")).grid(row=0, column=0, columnspan=4,
                                                                    sticky="w", pady=(0, 8))
    inner.outer = outer           # bingkai luar: dipakai untuk grid()/pack()
    return inner


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
        tk.Label(self._tip, text=self.text, bg="#1F2937", fg="#FFFFFF", padx=8, pady=4,
                 font=(FONT, 9)).pack()

    def _hide(self, e=None):
        if self._job:
            self.w.after_cancel(self._job)
            self._job = None
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None
