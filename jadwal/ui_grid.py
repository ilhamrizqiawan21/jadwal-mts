"""Kisi jadwal di layar. Susunan sama dengan cetakan: Selasa|Rabu|Kamis di atas,
Senin|Jumat|waktu Jumat di bawah. Operator mengetik kode guru langsung di sel,
seperti di Excel; bentrok langsung ditandai merah."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional, Tuple

from . import checks, model as M

HEAD = "#DCE6F0"
FONT = "Segoe UI"


def _expand(rows):
    out = []
    for r in rows:
        if r["t"] == "blok":
            out.append(("blok", r))
            out.append(("blok", r))          # satu mapel = dua baris JP
        elif r["t"] == "tutup" and r.get("jam"):
            out.append(("tutup", r))
            out.append(("tutup", r))
        else:
            out.append((r["t"], r))
    return out


class GridView(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.zoom = 1.0
        self.auto_fit = True
        self.sel: Optional[Tuple[str, str, str]] = None
        self.hl_guru: Optional[str] = None            # id guru yang disorot
        self.cells: Dict[Tuple[str, str, str], Tuple[float, float, float, float]] = {}
        self.editor: Optional[tk.Entry] = None
        self.clip: Optional[str] = None

        self.mode = "cetak"                           # cetak | hari
        self.day = "Selasa"
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 3))
        self.v_mode = tk.StringVar(value=self.mode)
        ttk.Label(bar, text="Tampilan:").pack(side="left", padx=(2, 4))
        for text, val in (("Seperti cetakan", "cetak"), ("Per hari (lebih besar)", "hari")):
            ttk.Radiobutton(bar, text=text, value=val, variable=self.v_mode, style="Toolbutton",
                            command=self._mode_changed).pack(side="left", padx=1)
        self.day_bar = ttk.Frame(bar)
        self.v_day = tk.StringVar(value=self.day)
        for h in M.HARI:
            ttk.Radiobutton(self.day_bar, text=h, value=h, variable=self.v_day, style="Toolbutton",
                            command=self._day_changed).pack(side="left", padx=1)
        self.canvas = tk.Canvas(self, background="white", highlightthickness=0, takefocus=1)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.vbar.grid(row=1, column=1, sticky="ns")
        self.hbar.grid(row=2, column=0, sticky="ew")
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        c = self.canvas
        c.bind("<Button-1>", self._click)
        c.bind("<Double-Button-1>", lambda e: self.start_edit())
        c.bind("<Button-3>", self._context)
        c.bind("<Key>", self._key)
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 * (e.delta // 120), "units"))
        c.bind("<Shift-MouseWheel>", lambda e: c.xview_scroll(-1 * (e.delta // 120), "units"))
        c.bind("<Configure>", lambda e: self.auto_fit and self.after_idle(self.fit_zoom))
        c.bind("<Control-c>", lambda e: self.copy())
        c.bind("<Control-v>", lambda e: self.paste())
        c.bind("<Control-x>", lambda e: (self.copy(), self.clear_cell()))

    # ------------------------------------------------------------------ util
    @property
    def store(self):
        return self.app.store

    @property
    def p(self) -> M.Proyek:
        return self.app.store.p

    def set_zoom(self, z: float):
        self.auto_fit = False
        self.zoom = max(0.5, min(1.8, z))
        self.redraw()

    def _mode_changed(self):
        self.mode = self.v_mode.get()
        if self.mode == "hari":
            self.day_bar.pack(side="left", padx=(12, 0))
            hr = self.sel[0] if self.sel else None
            if hr:
                self.day = hr
                self.v_day.set(hr)
        else:
            self.day_bar.pack_forget()
        self.auto_fit = True
        self.zoom = 0
        self.fit_zoom()
        self.redraw()

    def _day_changed(self):
        self.day = self.v_day.get()
        if self.sel and self.sel[0] != self.day:
            self.sel = None
        self.redraw()

    def fit_zoom(self):
        """Sesuaikan zoom agar tampilan muat selebar jendela."""
        n = max(len(self.p.kelas), 1)
        if self.mode == "hari":
            need = 22 + 74 + n * 30 + 20
            hi = 2.0
        else:
            need = 22 + 74 + 3 * n * 30 + 160 + 20
            hi = 1.3
        w = self.canvas.winfo_width()
        if w > 100:
            z = max(0.5, min(hi, w / need))
            if abs(z - self.zoom) > 0.02:
                self.zoom = z
                self.redraw()

    def kelas_ids(self) -> List[str]:
        return [k.id for k in self.p.kelas]

    # -------------------------------------------------------------- gambar
    def redraw(self):
        c = self.canvas
        self._cancel_edit()
        c.delete("all")
        self.cells = {}
        self._max_x = 0
        p, z = self.p, self.zoom
        n = len(p.kelas)
        cw, rh = 30 * z, 16 * z
        ax_no, ax_wk = 22 * z, 74 * z
        gap = 5 * z
        th, lh = 18 * z, 20 * z
        fs = max(6, min(13, int(8 * z)))
        fb = (FONT, fs, "bold")
        hasil = self.store.hasil
        by_kode = p.penugasan_by_kode()
        bad_cells: Dict = {}
        for m in hasil.masalah:
            if m.tingkat == checks.ERROR:
                for s in m.sel:
                    bad_cells[s] = m
        hl_kodes = set()
        hl_block: Dict[str, List[str]] = {}
        if self.hl_guru:
            for a in p.penugasan:
                if a.guru == self.hl_guru and a.kode:
                    hl_kodes.add(a.kode.upper())
            g = p.guru_by_id(self.hl_guru)
            if g:
                hl_block = g.tidak_bisa

        if self.mode == "hari":
            groups = [([self.day], True)]
        else:
            groups = [(["Selasa", "Rabu", "Kamis"], True), (["Senin", "Jumat", None], False)]
        y = 4.0
        block_w = n * cw
        for days, top in groups:
            lays = [_expand(p.hari[d]["baris"]) if d else [] for d in days]
            nr = max(len(x) for x in lays)
            ref = lays[0]
            # judul & label kelas ditempatkan di atas tiap blok
            x_blocks = []
            x = ax_no + ax_wk
            for d in days:
                x_blocks.append(x)
                x += (block_w if d else 160 * z) + gap
            ytop_rows = y + th + lh
            # sumbu kiri
            c.create_rectangle(0, y, ax_no + ax_wk, y + th + lh, fill=HEAD, outline="#888")
            c.create_text(ax_no + ax_wk / 2, y + (th + lh) / 2, text="NO   WAKTU", font=(FONT, fs - 1, "bold"))
            for k, (kind, r) in enumerate(ref):
                ya = ytop_rows + k * rh
                c.create_rectangle(0, ya, ax_no + ax_wk, ya + rh, fill="white", outline="#aaa")
                if kind == "blok":
                    pass
            # nomor jam & waktu (per JP)
            k = 0
            while k < len(ref):
                kind, r = ref[k]
                ya = ytop_rows + k * rh
                if kind == "blok":
                    for h in (0, 1):
                        yy = ytop_rows + (k + h) * rh
                        c.create_text(ax_no / 2, yy + rh / 2, text=str(r["jam"][h]), font=(FONT, fs - 1))
                        c.create_text(ax_no + ax_wk / 2, yy + rh / 2, text=r["waktu"][h], font=(FONT, fs - 1))
                    k += 2
                    continue
                if kind == "tutup":
                    h = 0 if (k == 0 or ref[k - 1][1] is not r) else 1
                    if r.get("jam") and h < len(r["jam"]):
                        c.create_text(ax_no / 2, ya + rh / 2, text=str(r["jam"][h]), font=(FONT, fs - 1))
                        c.create_text(ax_no + ax_wk / 2, ya + rh / 2, text=r["waktu"][h], font=(FONT, fs - 1))
                else:
                    c.create_text((ax_no + ax_wk) / 2, ya + rh / 2, text=r.get("waktu", ""),
                                  fill="#c00000", font=(FONT, fs - 1, "bold"))
                k += 1
            # blok hari
            for di, hari in enumerate(days):
                x0 = x_blocks[di]
                if hari is None:
                    self._panel(x0, y, th, lh, rh, ytop_rows, nr, fs, z)
                    continue
                c.create_rectangle(x0, y, x0 + block_w, y + th, fill="white", outline="#888")
                c.create_text(x0 + block_w / 2, y + th / 2, text=hari.upper(), font=(FONT, fs + 1, "bold"))
                for i, k_ in enumerate(p.kelas):
                    xa = x0 + i * cw
                    c.create_rectangle(xa, y + th, xa + cw, y + th + lh, fill=HEAD, outline="#888")
                    c.create_text(xa + cw / 2, y + th + lh / 2, text=k_.nama, font=fb)
                lay = lays[di]
                k = 0
                while k < nr:
                    if k >= len(lay):
                        k += 1
                        continue
                    kind, r = lay[k]
                    ya = ytop_rows + k * rh
                    if kind == "info":
                        fill = r.get("warna") or "white"
                        c.create_rectangle(x0, ya, x0 + block_w, ya + rh, fill=fill, outline="#888")
                        c.create_text(x0 + block_w / 2, ya + rh / 2, text=r["label"],
                                      fill="black" if r.get("warna") else "#c00000", font=(FONT, fs - 1, "bold"))
                    elif kind == "jeda":
                        c.create_rectangle(x0, ya, x0 + block_w, ya + rh, fill="#f4f4f4", outline="#aaa")
                        c.create_text(x0 + block_w / 2, ya + rh / 2, text=r.get("label", ""), font=(FONT, fs - 1, "bold"))
                    elif kind == "tutup":
                        c.create_rectangle(x0, ya, x0 + block_w, ya + rh, fill="black", outline="black")
                    elif kind == "blok":
                        bid = r["id"]
                        for i, k_ in enumerate(p.kelas):
                            xa = x0 + i * cw
                            self._cell(hari, bid, k_.id, xa, ya, xa + cw, ya + 2 * rh, by_kode,
                                       bad_cells, hl_kodes, fs)
                        if hari in () or (self.hl_guru and r["id"] in hl_block.get(hari, [])):
                            pass
                        if self.hl_guru and r["id"] in hl_block.get(hari, []):
                            c.create_rectangle(x0, ya, x0 + block_w, ya + 2 * rh, fill="#ff6666",
                                               stipple="gray50", outline="#cc0000", width=1)
                        k += 2
                        continue
                    k += 1
            y = ytop_rows + nr * rh + 10 * z
            self._max_x = max(self._max_x, x_blocks[-1] + (160 * z))
        c.configure(scrollregion=(0, 0, self._max_x + 10, y))
        self._draw_selection()

    def _panel(self, x0, y, th, lh, rh, ytop_rows, nr, fs, z):
        """Waktu Jumat (panel kanan-bawah pada cetakan)."""
        c = self.canvas
        w = 160 * z
        c.create_rectangle(x0, y, x0 + w, y + th + lh, fill=HEAD, outline="#888")
        c.create_text(x0 + w / 2, y + (th + lh) / 2, text="JAM JUM'AT", font=(FONT, fs, "bold"))
        k = 0
        for kind, r in _expand(self.p.hari["Jumat"]["baris"]):
            ya = ytop_rows + k * rh
            c.create_rectangle(x0, ya, x0 + w, ya + rh, fill="white", outline="#aaa")
            if kind == "blok":
                pass
            k += 1
        k = 0
        lay = _expand(self.p.hari["Jumat"]["baris"])
        while k < len(lay):
            kind, r = lay[k]
            ya = ytop_rows + k * rh
            if kind == "blok":
                for h in (0, 1):
                    c.create_text(x0 + 6 * z, ytop_rows + (k + h) * rh + rh / 2, anchor="w",
                                  text=f"{r['jam'][h]}   {r['waktu'][h]}", font=(FONT, fs - 1))
                k += 2
                continue
            if kind in ("info", "jeda"):
                c.create_text(x0 + w / 2, ya + rh / 2, text=r.get("waktu", ""), fill="#c00000",
                              font=(FONT, fs - 1, "bold"))
            elif kind == "tutup":
                c.create_text(x0 + w / 2, ya + rh / 2, text=r.get("label", ""), fill="#c00000",
                              font=(FONT, fs - 1, "bold"))
            k += 1

    def _cell(self, hari, bid, kid, x0, y0, x1, y1, by_kode, bad, hl_kodes, fs):
        c = self.canvas
        jp = self.p.get_cell(hari, bid, kid)
        self.cells[(hari, bid, kid)] = (x0, y0, x1, y1)
        ym = (y0 + y1) / 2
        halves = [(y0, y1)] if jp[0] == jp[1] else [(y0, ym), (ym, y1)]
        for h, (ya, yb) in enumerate(halves):
            kodes = jp[h]
            fill = "white"
            if kodes:
                a = by_kode.get(kodes[-1].upper())
                fill = a.warna if a else "#ffd9d9"
            c.create_rectangle(x0, ya, x1, yb, fill=fill, outline="#999")
            txt = M.cell_text(kodes)
            if txt:
                unknown = any(k.upper() not in by_kode for k in kodes)
                size = fs if len(txt) <= 4 else max(6, fs - 1)
                c.create_text((x0 + x1) / 2, (ya + yb) / 2, text=txt,
                              fill="#cc0000" if unknown else "black", font=(FONT, size, "bold"))
        if (hari, bid, kid) in bad:
            c.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y1 - 1, outline="#e60000", width=2)
            c.create_polygon(x1 - 8, y0 + 1, x1 - 1, y0 + 1, x1 - 1, y0 + 8, fill="#e60000", outline="")
        if hl_kodes and any(k.upper() in hl_kodes for k in jp[0] + jp[1]):
            c.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y1 - 1, outline="#7a1fa2", width=2, dash=(3, 2))

    def _draw_selection(self):
        c = self.canvas
        c.delete("sel")
        if self.sel and self.sel in self.cells:
            hari, bid, kid = self.sel
            x0, y0, x1, y1 = self.cells[self.sel]
            # sorot baris (jam yang sama) dan kolom (kelas yang sama) pada hari itu, supaya
            # mudah dilacak seperti di Excel. Hanya dua garis tipis; tidak menggambar ulang kisi.
            baris = [v for k, v in self.cells.items() if k[0] == hari and k[1] == bid]
            kolom = [v for k, v in self.cells.items() if k[0] == hari and k[2] == kid]
            for band in (baris, kolom):
                if len(band) > 1:
                    c.create_rectangle(min(b[0] for b in band), min(b[1] for b in band),
                                       max(b[2] for b in band), max(b[3] for b in band),
                                       outline="#6F9BF0", width=2, tags="sel")
            c.create_rectangle(x0, y0, x1, y1, outline="#1a5fd0", width=3, tags="sel")

    # --------------------------------------------------------------- pilihan
    def _cell_at(self, x, y):
        for key, (x0, y0, x1, y1) in self.cells.items():
            if x0 <= x < x1 and y0 <= y < y1:
                return key
        return None

    def select(self, key, scroll=True):
        if key is not None and key not in self.cells:
            return
        self.sel = key
        self._draw_selection()
        if key and scroll:
            self._scroll_into_view(key)
        self.app.on_select(key)

    def _scroll_into_view(self, key):
        x0, y0, x1, y1 = self.cells[key]
        c = self.canvas
        sr = c.cget("scrollregion").split()
        if len(sr) < 4:
            return
        W, H = float(sr[2]), float(sr[3])
        vx0, vx1 = c.canvasx(0), c.canvasx(c.winfo_width())
        vy0, vy1 = c.canvasy(0), c.canvasy(c.winfo_height())
        if x0 < vx0 + 5:
            c.xview_moveto(max(0, (x0 - 60) / W))
        elif x1 > vx1 - 5:
            c.xview_moveto(min(1, (x1 - c.winfo_width() + 60) / W))
        if y0 < vy0 + 5:
            c.yview_moveto(max(0, (y0 - 40) / H))
        elif y1 > vy1 - 5:
            c.yview_moveto(min(1, (y1 - c.winfo_height() + 40) / H))

    def _click(self, e):
        self.canvas.focus_set()
        self._commit_edit()
        key = self._cell_at(self.canvas.canvasx(e.x), self.canvas.canvasy(e.y))
        if key:
            self.select(key, scroll=False)

    def _context(self, e):
        self._click(e)
        if not self.sel:
            return
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Ubah (F2)", command=self.start_edit)
        m.add_command(label="Salin  Ctrl+C", command=self.copy)
        m.add_command(label="Tempel  Ctrl+V", command=self.paste)
        m.add_command(label="Kosongkan  Del", command=self.clear_cell)
        m.tk_popup(e.x_root, e.y_root)

    # ----------------------------------------------------------- navigasi
    def _blocks(self, hari) -> List[str]:
        return [r["id"] for r in self.p.blok_list(hari)]

    def move(self, dx=0, dy=0):
        if not self.sel:
            first = next(iter(self.cells), None)
            self.select(first)
            return
        hari, bid, kid = self.sel
        ids = self.kelas_ids()
        blocks = self._blocks(hari)
        i = ids.index(kid) if kid in ids else 0
        j = blocks.index(bid) if bid in blocks else 0
        i = max(0, min(len(ids) - 1, i + dx))
        j = max(0, min(len(blocks) - 1, j + dy))
        self.select((hari, blocks[j], ids[i]))

    def _key(self, e):
        k = e.keysym
        if e.state & 0x4 and k.lower() in ("c", "v", "x", "z", "y", "s"):
            return
        nav = {"Left": (-1, 0), "Right": (1, 0), "Up": (0, -1), "Down": (0, 1)}
        if k in nav:
            self.move(*nav[k])
            return "break"
        if k == "Tab":
            self.move(-1 if e.state & 0x1 else 1, 0)
            return "break"
        if k in ("Delete", "BackSpace"):
            self.clear_cell()
            return "break"
        if k == "F2" or k == "Return":
            self.start_edit()
            return "break"
        if e.char and e.char.isprintable() and self.sel:
            self.start_edit(initial=e.char)
            return "break"

    # ------------------------------------------------------------ edit sel
    def start_edit(self, initial: Optional[str] = None):
        if not self.sel or self.sel not in self.cells:
            return
        self._commit_edit()
        x0, y0, x1, y1 = self.cells[self.sel]
        hari, bid, kid = self.sel
        text = initial if initial is not None else M.cell_text_jp(self.p.get_cell(hari, bid, kid))
        e = tk.Entry(self.canvas, font=(FONT, 10, "bold"), justify="center", relief="solid", bd=1)
        e.insert(0, text)
        if initial is None:
            e.select_range(0, "end")
        e.icursor("end")
        w = max(x1 - x0, 90)
        self.canvas.create_window(x0, y0, anchor="nw", window=e, width=w, height=max(y1 - y0, 24),
                                  tags="editor")
        e.focus_set()
        e.bind("<Return>", lambda ev: self._finish_edit(0, 1))
        e.bind("<Tab>", lambda ev: self._finish_edit(1, 0))
        e.bind("<Shift-Tab>", lambda ev: self._finish_edit(-1, 0))
        e.bind("<Escape>", lambda ev: self._cancel_edit(refocus=True))
        e.bind("<Up>", lambda ev: self._finish_edit(0, -1))
        e.bind("<Down>", lambda ev: self._finish_edit(0, 1))
        e.bind("<KeyRelease>", lambda ev: self._hint(e.get()))
        e.bind("<FocusOut>", lambda ev: self._commit_edit())
        self.editor = e
        self._hint(text)

    def _hint(self, text):
        if not self.sel:
            return
        hari, bid, kid = self.sel
        kodes = {k for k in self.p.penugasan_by_kode()}
        jp = M.parse_cell_jp(text, kodes)
        self.app.show_hint(self.hint_for(hari, bid, kid, jp))

    def hint_for(self, hari, bid, kid, jp) -> Tuple[str, bool]:
        """(teks, ada_masalah) untuk baris petunjuk saat mengetik."""
        p = self.p
        by_kode = p.penugasan_by_kode()
        parts, bad = [], []
        seen = set()
        for half in (0, 1):
            for kode in jp[half]:
                if kode in seen:
                    continue
                seen.add(kode)
                a = by_kode.get(kode.upper())
                if not a:
                    bad.append(f'Kode "{kode}" belum ada di Beban Mengajar')
                    continue
                g = p.guru_by_id(a.guru)
                parts.append(f"{kode} = {g.nama if g else '?'} ({a.mapel})")
        bad += checks.preview(p, hari, bid, kid, jp)
        if bad:
            return " | ".join(bad), True
        return "; ".join(parts), False

    def _commit_edit(self):
        e = self.editor
        if e is None:
            return
        self.editor = None
        text = e.get()
        self.canvas.delete("editor")
        e.destroy()
        self.app.show_hint(("", False))
        if self.sel:
            self.set_cell_text(self.sel, text)

    def _finish_edit(self, dx, dy):
        self._commit_edit()
        self.canvas.focus_set()
        self.move(dx, dy)
        return "break"

    def _cancel_edit(self, refocus=False):
        e = self.editor
        if e is None:
            return
        self.editor = None
        self.canvas.delete("editor")
        e.destroy()
        self.app.show_hint(("", False))
        if refocus:
            self.canvas.focus_set()

    # -------------------------------------------------------------- operasi
    def set_cell_text(self, key, text):
        hari, bid, kid = key
        kodes = set(self.p.penugasan_by_kode())
        jp = M.parse_cell_jp(text, kodes)
        if jp == self.p.get_cell(hari, bid, kid):
            return
        before = {(m.jenis, m.pesan) for m in self.store.hasil.masalah if m.tingkat == checks.ERROR}
        with self.store.edit() as p:
            p.set_cell(hari, bid, kid, jp[0], jp[1])
        after = [m for m in self.store.hasil.masalah
                 if m.tingkat == checks.ERROR and (m.jenis, m.pesan) not in before]
        if after:
            self.app.alert(after)

    def clear_cell(self):
        if self.sel:
            self.set_cell_text(self.sel, "")

    def copy(self):
        if self.sel:
            self.clip = M.cell_text_jp(self.p.get_cell(*self.sel))
            try:
                self.clipboard_clear()
                self.clipboard_append(self.clip)
            except tk.TclError:
                pass

    def paste(self):
        if self.sel and self.clip is not None:
            self.set_cell_text(self.sel, self.clip)

    def put_code(self, kode: str):
        """Isi sel terpilih dengan kode (dari daftar kode di panel kanan)."""
        if self.sel:
            self.set_cell_text(self.sel, kode)
            self.move(0, 1)

    def jump_to(self, sel):
        if sel in self.cells:
            self.select(sel)
            self.canvas.focus_set()
