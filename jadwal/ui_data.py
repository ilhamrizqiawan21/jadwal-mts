"""Tab data: Beban Mengajar, Guru, Kelas, Pengaturan & Jam, dan dialog pendukung.

Semua data (guru, mapel, kelas, penugasan) bisa diubah operator kapan saja;
tidak ada guru/mapel/kelas yang dipatenkan di dalam program.
"""
from __future__ import annotations

import base64
import copy
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Callable, Dict, List, Optional

from . import model as M, theme

FONT = "Segoe UI"


# =============================================================== utilitas dialog
class Dialog(tk.Toplevel):
    """Dasar dialog modal dengan tombol OK/Batal."""

    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.title(title)
        self.transient(parent.winfo_toplevel())
        self.resizable(False, False)
        self.result = None
        self.body = ttk.Frame(self, padding=10)
        self.body.pack(fill="both", expand=True)
        self.bar = ttk.Frame(self, padding=(10, 0, 10, 10))
        self.bar.pack(fill="x")
        ttk.Button(self.bar, text="Batal", command=self.destroy).pack(side="right", padx=4)
        ttk.Button(self.bar, text="OK", command=self._ok).pack(side="right")
        self.bind("<Escape>", lambda e: self.destroy())

    def show(self):
        self.update_idletasks()
        top = self.master.winfo_toplevel()
        x = top.winfo_rootx() + max(20, (top.winfo_width() - self.winfo_width()) // 2)
        y = top.winfo_rooty() + max(20, (top.winfo_height() - self.winfo_height()) // 3)
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.wait_window(self)
        return self.result

    def _ok(self):
        if self.validate():
            self.result = self.collect()
            self.destroy()

    def validate(self) -> bool:
        return True

    def collect(self):
        return True


class FormDialog(Dialog):
    """Dialog formulir sederhana. fields = [(kunci, label, jenis, awal, opsi)]
    jenis: text | combo | check."""

    def __init__(self, parent, title, fields, hint: str = ""):
        super().__init__(parent, title)
        self.fields = fields
        self.vars: Dict[str, tk.Variable] = {}
        r = 0
        if hint:
            ttk.Label(self.body, text=hint, foreground="#555", wraplength=380).grid(
                row=r, column=0, columnspan=2, sticky="w", pady=(0, 6))
            r += 1
        first = None
        for key, label, kind, init, opts in fields:
            ttk.Label(self.body, text=label).grid(row=r, column=0, sticky="w", pady=2, padx=(0, 8))
            if kind == "check":
                v = tk.BooleanVar(value=bool(init))
                w = ttk.Checkbutton(self.body, variable=v)
            elif kind == "combo":
                v = tk.StringVar(value=init or "")
                w = ttk.Combobox(self.body, textvariable=v, values=opts or [], width=34)
            else:
                v = tk.StringVar(value="" if init is None else str(init))
                w = ttk.Entry(self.body, textvariable=v, width=36)
            w.grid(row=r, column=1, sticky="ew", pady=2)
            self.vars[key] = v
            first = first or w
            r += 1
        if first:
            first.focus_set()
        self.bind("<Return>", lambda e: self._ok())

    def collect(self):
        return {k: v.get() for k, v in self.vars.items()}


def _natural(s: str):
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s or "")]


def _int_or_none(s) -> Optional[int]:
    s = str(s).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


class _ListTab(ttk.Frame):
    """Dasar tab dengan daftar + tombol; subkelas mengisi reload()."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

    @property
    def store(self):
        return self.app.store

    @property
    def p(self) -> M.Proyek:
        return self.app.store.p

    def reload(self):
        pass

    # ---- bantuan tampilan daftar (zebra, cari, pulihkan pilihan)
    @staticmethod
    def zebra(tv: ttk.Treeview):
        tv.tag_configure("odd", background="#F6F8FC")
        tv.tag_configure("even", background=theme.SURFACE)

    def search_box(self, parent) -> tk.StringVar:
        """Kotak cari kecil; mengisi ulang daftar tiap ketikan (daftar kecil, murah)."""
        v = tk.StringVar()
        ttk.Label(parent, text="Cari", style="Muted.TLabel").pack(side="left", padx=(2, 4))
        ttk.Entry(parent, textvariable=v, width=22).pack(side="left")
        v.trace_add("write", lambda *a: self.reload())
        return v

    @staticmethod
    def cocok(q: str, *teks: str) -> bool:
        """Semua kata pada q harus ada di salah satu teks (tanpa memedulikan huruf besar/kecil)."""
        if not q:
            return True
        h = " ".join(teks).lower()
        return all(w in h for w in q.lower().split())

    @staticmethod
    def pulihkan(tv: ttk.Treeview, sel):
        """Kembalikan pilihan setelah daftar diisi ulang dan pastikan barisnya tetap terlihat."""
        for i in sel:
            if tv.exists(i):
                tv.selection_set(i)
                tv.see(i)
                return


# ============================================================== BEBAN MENGAJAR
class BebanTab(_ListTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(6, 4), padx=6)
        ttk.Button(bar, text="+ Tambah", style="Accent.TButton", command=self.add).pack(side="left", padx=(0, 6))
        for t, c in (("Ubah", self.edit), ("Duplikat", self.dup), ("Hapus", self.delete),
                     ("▲ Naik", lambda: self.move(-1)), ("▼ Turun", lambda: self.move(1))):
            ttk.Button(bar, text=t, style="Tool.TButton", command=c).pack(side="left", padx=1)
        sf = ttk.Frame(bar)
        sf.pack(side="right", padx=4)
        self.q = self.search_box(sf)
        ttk.Label(self, text="Sel kelas kosong = tidak mengajar (hitam di cetakan). Klik dua kali baris untuk mengubah.",
                  style="Muted.TLabel").pack(anchor="w", padx=10, pady=(0, 4))
        fr = ttk.Frame(self)
        fr.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.tv = ttk.Treeview(fr, show="headings", selectmode="browse")
        vs = ttk.Scrollbar(fr, command=self.tv.yview)
        hs = ttk.Scrollbar(fr, orient="horizontal", command=self.tv.xview)
        self.tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tv.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        fr.rowconfigure(0, weight=1)
        fr.columnconfigure(0, weight=1)
        self.tv.bind("<Double-1>", lambda e: self.edit())
        self.zebra(self.tv)
        self._tags = set()

    def reload(self):
        p = self.p
        sel = self.tv.selection()
        cols = ["no", "guru", "kode", "mapel", "bbt"] + [k.id for k in p.kelas] + ["ket"]
        self.tv["columns"] = cols
        heads = {"no": ("No", 36), "guru": ("Nama Guru", 190), "kode": ("Kode", 50),
                 "mapel": ("Bidang Studi", 170), "bbt": ("BBT", 46), "ket": ("KET", 44)}
        for c in cols:
            if c in heads:
                self.tv.heading(c, text=heads[c][0])
                self.tv.column(c, width=heads[c][1], anchor="w" if c in ("guru", "mapel") else "center", stretch=False)
            else:
                self.tv.heading(c, text=p.kelas_by_id(c).nama)
                self.tv.column(c, width=34, anchor="center", stretch=False)
        self.tv.delete(*self.tv.get_children())
        gnum = {}
        for a in p.penugasan:
            gnum.setdefault(a.guru, len(gnum) + 1)
        q = self.q.get().strip()
        n = 0
        for a in p.penugasan:
            g = p.guru_by_id(a.guru)
            if not self.cocok(q, a.nama_tampil or (g.nama if g else ""), a.kode, a.mapel, a.keterangan):
                continue
            tot = a.ket_manual if a.ket_manual is not None else sum(a.beban.values())
            vals = [gnum[a.guru], (a.nama_tampil or (g.nama if g else "?")), a.kode, a.mapel or a.keterangan,
                    "" if a.bbt is None else a.bbt]
            for k in p.kelas:
                v = a.beban.get(k.id)
                vals.append("" if v is None else v)
            vals.append(tot or "")
            self.tv.insert("", "end", iid=a.id, values=vals, tags=("odd" if n % 2 else "even",))
            n += 1
        self.pulihkan(self.tv, sel)

    def _current(self) -> Optional[M.Penugasan]:
        sel = self.tv.selection()
        if not sel:
            return None
        return next((a for a in self.p.penugasan if a.id == sel[0]), None)

    def add(self):
        if not self.p.kelas:
            messagebox.showinfo("Beban Mengajar", "Tambahkan kelas dulu di tab Kelas.")
            return
        d = PenugasanDialog(self, self.app, None)
        res = d.show()
        if res:
            with self.store.edit() as p:
                res.id = p.new_id("a")
                cur = self._current()
                if cur is not None:
                    p.penugasan.insert(p.penugasan.index(next(x for x in p.penugasan if x.id == cur.id)) + 1, res)
                else:
                    p.penugasan.append(res)

    def edit(self):
        a = self._current()
        if not a:
            return
        d = PenugasanDialog(self, self.app, copy.deepcopy(a))
        res = d.show()
        if res:
            with self.store.edit() as p:
                i = next(i for i, x in enumerate(p.penugasan) if x.id == a.id)
                res.id = a.id
                old_kode = a.kode.upper()
                p.penugasan[i] = res
                if old_kode and old_kode != res.kode.upper():
                    self._rename_code(p, old_kode, res.kode.upper())

    @staticmethod
    def _rename_code(p: M.Proyek, old: str, new: str):
        """Kode diganti: perbarui isi jadwal supaya tidak kehilangan penempatan."""
        if any(x.kode.upper() == old for x in p.penugasan):
            return          # masih dipakai baris lain
        for hari in p.jadwal.values():
            for blok in hari.values():
                for jp in blok.values():
                    for half in jp:
                        for i, c in enumerate(half):
                            if c.upper() == old:
                                half[i] = new

    def dup(self):
        a = self._current()
        if not a:
            return
        with self.store.edit() as p:
            b = copy.deepcopy(a)
            b.id = p.new_id("a")
            b.kode = ""
            i = next(i for i, x in enumerate(p.penugasan) if x.id == a.id)
            p.penugasan.insert(i + 1, b)

    def delete(self):
        a = self._current()
        if not a:
            return
        n = 0
        if a.kode:
            for hari in self.p.jadwal.values():
                for blok in hari.values():
                    for jp in blok.values():
                        if any(c.upper() == a.kode.upper() for c in jp[0] + jp[1]):
                            n += 1
        msg = f"Hapus baris beban kode “{a.kode}”?"
        if n:
            msg += f"\n\nKode ini masih dipakai di {n} sel jadwal (sel tidak dihapus, tetapi akan ditandai merah)."
        if not messagebox.askyesno("Hapus", msg):
            return
        with self.store.edit() as p:
            p.penugasan = [x for x in p.penugasan if x.id != a.id]

    def move(self, d):
        a = self._current()
        if not a:
            return
        with self.store.edit() as p:
            i = next(i for i, x in enumerate(p.penugasan) if x.id == a.id)
            j = i + d
            if 0 <= j < len(p.penugasan):
                p.penugasan[i], p.penugasan[j] = p.penugasan[j], p.penugasan[i]
        if self.tv.exists(a.id):
            self.tv.selection_set(a.id)


class PenugasanDialog(Dialog):
    """Tambah/ubah satu baris beban: guru + kode + mapel + JP per kelas."""

    def __init__(self, parent, app, a: Optional[M.Penugasan]):
        super().__init__(parent, "Baris Beban Mengajar")
        self.app = app
        self.p: M.Proyek = app.store.p
        self.orig = a
        b = self.body
        a = a or M.Penugasan(id="", guru="", warna="#FFFFFF")
        self.a = a
        self.color = a.warna
        names = [g.nama for g in self.p.guru]
        self.v_guru = tk.StringVar(value=(self.p.guru_by_id(a.guru).nama if self.p.guru_by_id(a.guru) else ""))
        self.v_kode = tk.StringVar(value=a.kode)
        mapels = sorted({x.mapel for x in self.p.penugasan if x.mapel}, key=str.lower)
        self.v_mapel = tk.StringVar(value=a.mapel)
        self.v_bbt = tk.StringVar(value="" if a.bbt is None else str(a.bbt))
        self.v_merah = tk.BooleanVar(value=a.merah)
        self.v_ketm = tk.BooleanVar(value=a.ket_merah)
        self.v_gabung = tk.BooleanVar(value=a.bbt_gabung)
        self.v_ket = tk.StringVar(value=a.keterangan)
        self.v_total = tk.StringVar(value="" if a.ket_manual is None else str(a.ket_manual))

        r = 0
        ttk.Label(b, text="Guru").grid(row=r, column=0, sticky="w")
        cb = ttk.Combobox(b, textvariable=self.v_guru, values=names, width=38)
        cb.grid(row=r, column=1, columnspan=5, sticky="ew", pady=2)
        ttk.Label(b, text="(ketik nama baru bila belum ada)", foreground="#777").grid(row=r, column=6, columnspan=3, sticky="w")
        r += 1
        ttk.Label(b, text="Kode").grid(row=r, column=0, sticky="w")
        ttk.Entry(b, textvariable=self.v_kode, width=10).grid(row=r, column=1, sticky="w", pady=2)
        ttk.Label(b, text="Warna").grid(row=r, column=2, sticky="e", padx=(10, 2))
        self.btn_color = tk.Button(b, width=6, bg=self.color, relief="solid", command=self.pick_color)
        self.btn_color.grid(row=r, column=3, sticky="w")
        ttk.Label(b, text="BBT").grid(row=r, column=4, sticky="e", padx=(10, 2))
        ttk.Entry(b, textvariable=self.v_bbt, width=5).grid(row=r, column=5, sticky="w")
        ttk.Checkbutton(b, text="gabung dg baris atas", variable=self.v_gabung).grid(row=r, column=6, columnspan=3, sticky="w")
        r += 1
        ttk.Label(b, text="Bidang studi").grid(row=r, column=0, sticky="w")
        ttk.Combobox(b, textvariable=self.v_mapel, values=mapels, width=38).grid(row=r, column=1, columnspan=5, sticky="ew", pady=2)
        r += 1
        ttk.Label(b, text="JP per kelas", font=(FONT, 9, "bold")).grid(row=r, column=0, columnspan=9, sticky="w", pady=(8, 0))
        r += 1
        self.ent: Dict[str, tk.StringVar] = {}
        per_row = 7
        for i, k in enumerate(self.p.kelas):
            rr, cc = r + (i // per_row) * 2, i % per_row
            ttk.Label(b, text=k.nama).grid(row=rr, column=cc + 1 if False else cc, sticky="n")
            v = tk.StringVar(value="" if a.beban.get(k.id) is None else str(a.beban.get(k.id)))
            ttk.Entry(b, textvariable=v, width=5, justify="center").grid(row=rr + 1, column=cc, padx=2, pady=(0, 4))
            self.ent[k.id] = v
        r += ((len(self.p.kelas) - 1) // per_row + 1) * 2
        ttk.Label(b, text="Kosong = tidak mengajar di kelas itu (sel hitam). 0 = sel putih kosong.",
                  foreground="#777").grid(row=r, column=0, columnspan=9, sticky="w")
        r += 1
        lf = ttk.LabelFrame(b, text="Tampilan cetak (lanjutan)", padding=6)
        lf.grid(row=r, column=0, columnspan=9, sticky="ew", pady=(8, 0))
        ttk.Checkbutton(lf, text="Angka JP merah (tambahan)", variable=self.v_merah).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(lf, text="Total KET merah", variable=self.v_ketm).grid(row=0, column=1, sticky="w", padx=10)
        ttk.Label(lf, text="Total KET manual").grid(row=1, column=0, sticky="w")
        ttk.Entry(lf, textvariable=self.v_total, width=6).grid(row=1, column=1, sticky="w", padx=10)
        ttk.Label(lf, text="Teks keterangan (mis. Cuti …)").grid(row=2, column=0, sticky="w")
        ttk.Entry(lf, textvariable=self.v_ket, width=34).grid(row=2, column=1, sticky="w", padx=10)
        self.bind("<Return>", lambda e: self._ok())
        cb.focus_set()

    def pick_color(self):
        c = colorchooser.askcolor(color=self.color, parent=self, title="Warna kode")
        if c and c[1]:
            self.color = c[1].upper()
            self.btn_color.config(bg=self.color)

    def validate(self) -> bool:
        if not self.v_guru.get().strip():
            messagebox.showwarning("Beban", "Isi nama guru.", parent=self)
            return False
        kode = self.v_kode.get().strip().upper()
        if kode:
            dup = [x for x in self.p.penugasan if x.kode.upper() == kode and (not self.orig or x.id != self.orig.id)]
            if dup:
                g = self.p.guru_by_id(dup[0].guru)
                if not messagebox.askyesno(
                        "Kode ganda", f"Kode {kode} sudah dipakai ({g.nama if g else '?'}).\n"
                                      f"Dua guru dengan kode sama membuat pengecekan bentrok kurang tepat.\nLanjutkan?",
                        parent=self):
                    return False
        for kid, v in self.ent.items():
            t = v.get().strip()
            if t and _int_or_none(t) is None:
                messagebox.showwarning("Beban", f"JP harus angka (kelas {self.p.kelas_by_id(kid).nama}).", parent=self)
                return False
        return True

    def collect(self):
        p = self.p
        a = copy.deepcopy(self.a)
        name = " ".join(self.v_guru.get().split())
        g = next((g for g in p.guru if g.nama.lower() == name.lower()), None)
        if g is None:
            g = M.Guru(p.new_id("g"), name)
            self.new_guru = g
        a.guru = g.id
        a._new_guru = g  # dibuat di dalam store.edit lewat callback di bawah
        a.kode = self.v_kode.get().strip().upper()
        a.mapel = " ".join(self.v_mapel.get().split())
        a.warna = self.color
        a.bbt = _int_or_none(self.v_bbt.get())
        a.bbt_gabung = self.v_gabung.get()
        a.merah, a.ket_merah = self.v_merah.get(), self.v_ketm.get()
        a.keterangan = self.v_ket.get().strip()
        a.ket_manual = _int_or_none(self.v_total.get())
        a.beban = {}
        for kid, v in self.ent.items():
            n = _int_or_none(v.get())
            if n is not None:
                a.beban[kid] = n
        return a

    def show(self):
        res = super().show()
        if res is not None:
            g = res.__dict__.pop("_new_guru", None)
            if g is not None and not self.app.store.p.guru_by_id(g.id):
                # guru baru: daftarkan pada proyek lewat store (ikut undo)
                with self.app.store.edit() as p:
                    p.guru.append(g)
        return res


# ====================================================================== GURU
class GuruTab(_ListTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        left = ttk.Frame(self)
        left.pack(side="left", fill="y", padx=(10, 6), pady=8)
        bar = ttk.Frame(left)
        bar.pack(fill="x")
        ttk.Button(bar, text="+ Tambah", style="Accent.TButton", command=self.add).pack(side="left", padx=(0, 6))
        for t, c in (("Ubah", self.edit), ("Hapus", self.delete),
                     ("▲", lambda: self.move(-1)), ("▼", lambda: self.move(1))):
            ttk.Button(bar, text=t, style="Tool.TButton", width=6 if len(t) > 1 else 3, command=c).pack(side="left", padx=1)
        sf = ttk.Frame(left)
        sf.pack(fill="x", pady=(8, 0))
        self.q = self.search_box(sf)
        self.tv = ttk.Treeview(left, columns=("nama", "ket", "b"), show="headings", selectmode="browse", height=24)
        for c, w, t in (("nama", 250, "Nama guru"), ("ket", 130, "Catatan"), ("b", 56, "Req")):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor="w" if c != "b" else "center", stretch=False)
        self.zebra(self.tv)
        self.tv.pack(fill="y", expand=True, pady=6)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self.show_avail())
        self.tv.bind("<Double-1>", lambda e: self.edit())

        self.right = ttk.LabelFrame(self, text="Jam yang diminta kosong (guru mengajar di tempat lain)", padding=10)
        self.right.pack(side="left", fill="both", expand=True, padx=(6, 10), pady=8)
        self.lbl = ttk.Label(self.right, text="Pilih guru di daftar kiri.", font=(FONT, 10, "bold"))
        self.lbl.pack(anchor="w")
        ttk.Label(self.right, text="Klik kotak untuk menandai jam yang TIDAK bisa diisi guru ini. "
                                   "Menempatkan guru di jam itu akan langsung ditandai merah.",
                  foreground="#555", wraplength=520, justify="left").pack(anchor="w", pady=(2, 8))
        self.matrix = ttk.Frame(self.right)
        self.matrix.pack(anchor="w")
        self.buttons: Dict = {}

    def _current(self) -> Optional[M.Guru]:
        sel = self.tv.selection()
        return self.p.guru_by_id(sel[0]) if sel else None

    def reload(self):
        sel = self.tv.selection()
        self.tv.delete(*self.tv.get_children())
        q = self.q.get().strip()
        i = 0
        for g in self.p.guru:
            if not self.cocok(q, g.nama, g.ket):
                continue
            n = sum(len(v) for v in g.tidak_bisa.values())
            self.tv.insert("", "end", iid=g.id, values=(g.nama, g.ket, n or ""),
                           tags=("odd" if i % 2 else "even",))
            i += 1
        self.pulihkan(self.tv, sel)
        self.show_avail()

    def show_avail(self):
        for w in self.matrix.winfo_children():
            w.destroy()
        g = self._current()
        self.buttons = {}
        if not g:
            self.lbl.config(text="Pilih guru di daftar kiri.")
            return
        self.lbl.config(text=g.nama)
        p = self.p
        for ci, hari in enumerate(M.HARI):
            ttk.Label(self.matrix, text=hari, font=(FONT, 9, "bold")).grid(row=0, column=ci + 1, padx=3, pady=2)
        maxb = max(len(p.blok_list(h)) for h in M.HARI)
        for bi in range(maxb):
            ttk.Label(self.matrix, text=f"Mapel ke-{bi + 1}").grid(row=bi + 1, column=0, sticky="e", padx=4)
            for ci, hari in enumerate(M.HARI):
                bl = p.blok_list(hari)
                if bi >= len(bl):
                    continue
                r = bl[bi]
                on = r["id"] in g.tidak_bisa.get(hari, [])
                txt = f"jam {r['jam'][0]}-{r['jam'][-1]}\n{r['waktu'][0][:5]}"
                b = tk.Button(self.matrix, text=txt, width=11, height=2, relief="solid", bd=1,
                              bg="#F5A3A3" if on else theme.SURFACE, activebackground="#F9C9C9" if on else theme.HOVER,
                              fg=theme.TEXT, font=(FONT, 9),
                              command=lambda h=hari, bid=r["id"]: self.toggle(h, bid))
                b.grid(row=bi + 1, column=ci + 1, padx=2, pady=2)

    def toggle(self, hari, bid):
        g = self._current()
        if not g:
            return
        with self.store.edit() as p:
            gg = p.guru_by_id(g.id)
            lst = gg.tidak_bisa.setdefault(hari, [])
            if bid in lst:
                lst.remove(bid)
            else:
                lst.append(bid)
            if not lst:
                gg.tidak_bisa.pop(hari, None)

    def add(self):
        d = FormDialog(self, "Guru baru", [("nama", "Nama guru", "text", "", None),
                                           ("ket", "Catatan (mis. Cuti)", "text", "", None)]).show()
        if d and d["nama"].strip():
            with self.store.edit() as p:
                g = M.Guru(p.new_id("g"), " ".join(d["nama"].split()), d["ket"].strip())
                p.guru.append(g)
            self.tv.selection_set(g.id) if self.tv.exists(g.id) else None

    def edit(self):
        g = self._current()
        if not g:
            return
        d = FormDialog(self, "Ubah guru", [("nama", "Nama guru", "text", g.nama, None),
                                           ("ket", "Catatan", "text", g.ket, None)]).show()
        if d and d["nama"].strip():
            with self.store.edit() as p:
                gg = p.guru_by_id(g.id)
                gg.nama, gg.ket = " ".join(d["nama"].split()), d["ket"].strip()

    def delete(self):
        g = self._current()
        if not g:
            return
        used = [a for a in self.p.penugasan if a.guru == g.id]
        if used:
            messagebox.showwarning("Hapus guru", f"{g.nama} masih punya {len(used)} baris di Beban Mengajar.\n"
                                                 f"Hapus/pindahkan barisnya dulu.")
            return
        if messagebox.askyesno("Hapus guru", f"Hapus {g.nama}?"):
            with self.store.edit() as p:
                p.guru = [x for x in p.guru if x.id != g.id]
                for k in p.kelas:
                    if k.wali == g.id:
                        k.wali = None

    def move(self, d):
        g = self._current()
        if not g:
            return
        with self.store.edit() as p:
            i = next(i for i, x in enumerate(p.guru) if x.id == g.id)
            j = i + d
            if 0 <= j < len(p.guru):
                p.guru[i], p.guru[j] = p.guru[j], p.guru[i]
        if self.tv.exists(g.id):
            self.tv.selection_set(g.id)


# ===================================================================== KELAS
class KelasTab(_ListTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=6, pady=(6, 4))
        ttk.Button(bar, text="+ Tambah kelas", style="Accent.TButton", command=self.add).pack(side="left", padx=(0, 6))
        for t, c in (("Ubah nama", self.rename), ("Hapus", self.delete),
                     ("◀ Geser kiri", lambda: self.move(-1)), ("Geser kanan ▶", lambda: self.move(1))):
            ttk.Button(bar, text=t, style="Tool.TButton", command=c).pack(side="left", padx=1)
        self.tv = ttk.Treeview(self, columns=("nama", "wali", "jp"), show="headings", selectmode="browse", height=22)
        for c, w, t in (("nama", 100, "Kelas"), ("wali", 300, "Wali kelas"), ("jp", 90, "Total JP")):
            self.tv.heading(c, text=t)
            self.tv.column(c, width=w, anchor="w" if c != "jp" else "center", stretch=False)
        self.zebra(self.tv)
        self.tv.pack(fill="y", padx=10, pady=4, anchor="w")
        wf = ttk.Frame(self)
        wf.pack(fill="x", padx=6)
        ttk.Label(wf, text="Wali kelas terpilih:").pack(side="left")
        self.v_wali = tk.StringVar()
        self.cb = ttk.Combobox(wf, textvariable=self.v_wali, state="readonly", width=40)
        self.cb.pack(side="left", padx=6)
        self.cb.bind("<<ComboboxSelected>>", lambda e: self.set_wali())
        ttk.Label(self, foreground="#555", wraplength=700, justify="left",
                  text="Menambah/menghapus kelas langsung mempengaruhi kisi jadwal dan cetakan. "
                       "Menghapus kelas ikut menghapus isi jadwal & beban kelas itu.").pack(anchor="w", padx=6, pady=8)
        self.tv.bind("<<TreeviewSelect>>", lambda e: self._sync_wali())
        self.tv.bind("<Double-1>", lambda e: self.rename())

    def _current(self) -> Optional[M.Kelas]:
        sel = self.tv.selection()
        return self.p.kelas_by_id(sel[0]) if sel else None

    def reload(self):
        sel = self.tv.selection()
        self.tv.delete(*self.tv.get_children())
        for n, k in enumerate(self.p.kelas):
            g = self.p.guru_by_id(k.wali) if k.wali else None
            jp = sum(a.beban.get(k.id, 0) for a in self.p.penugasan)
            self.tv.insert("", "end", iid=k.id, values=(k.nama, g.nama if g else "—", jp),
                           tags=("odd" if n % 2 else "even",))
        self.cb["values"] = ["(tidak ada)"] + [g.nama for g in self.p.guru]
        self.pulihkan(self.tv, sel)
        self._sync_wali()

    def _sync_wali(self):
        k = self._current()
        g = self.p.guru_by_id(k.wali) if k and k.wali else None
        self.v_wali.set(g.nama if g else "(tidak ada)")

    def set_wali(self):
        k = self._current()
        if not k:
            return
        name = self.v_wali.get()
        g = next((g for g in self.p.guru if g.nama == name), None)
        with self.store.edit() as p:
            p.kelas_by_id(k.id).wali = g.id if g else None

    def add(self):
        d = FormDialog(self, "Kelas baru", [("nama", "Nama kelas (mis. 9F)", "text", "", None)]).show()
        if d and d["nama"].strip():
            with self.store.edit() as p:
                k = M.Kelas(p.new_id("c"), d["nama"].strip().upper())
                p.kelas.append(k)

    def rename(self):
        k = self._current()
        if not k:
            return
        d = FormDialog(self, "Ubah nama kelas", [("nama", "Nama kelas", "text", k.nama, None)]).show()
        if d and d["nama"].strip():
            with self.store.edit() as p:
                p.kelas_by_id(k.id).nama = d["nama"].strip().upper()

    def delete(self):
        k = self._current()
        if not k:
            return
        if not messagebox.askyesno("Hapus kelas", f"Hapus kelas {k.nama} beserta isi jadwal dan beban JP-nya?"):
            return
        with self.store.edit() as p:
            p.kelas = [x for x in p.kelas if x.id != k.id]
            for hari in p.jadwal.values():
                for blok in hari.values():
                    blok.pop(k.id, None)
            for a in p.penugasan:
                a.beban.pop(k.id, None)

    def move(self, d):
        k = self._current()
        if not k:
            return
        with self.store.edit() as p:
            i = next(i for i, x in enumerate(p.kelas) if x.id == k.id)
            j = i + d
            if 0 <= j < len(p.kelas):
                p.kelas[i], p.kelas[j] = p.kelas[j], p.kelas[i]
        if self.tv.exists(k.id):
            self.tv.selection_set(k.id)


# ================================================================ PENGATURAN
class PengaturanTab(_ListTab):
    def __init__(self, master, app):
        super().__init__(master, app)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self.f_meta = ttk.Frame(nb, padding=10)
        self.f_jam = ttk.Frame(nb, padding=10)
        nb.add(self.f_meta, text="  Judul, tanda tangan, kop  ")
        nb.add(self.f_jam, text="  Jam pelajaran per hari  ")
        self._build_meta()
        self._build_jam()

    # ---------------------------------------------------------- meta
    # (kunci, label) per kartu. Kunci dipakai juga oleh _load_meta/apply_meta.
    KARTU_IDENTITAS = [
        ("semester", "Semester"), ("tahun", "Tahun pelajaran"),
        ("judul_beban", "Judul hal. 1 (baris 1)"), ("judul_beban2", "Judul hal. 1 (baris 2)"),
        ("j0", "Judul jadwal (baris 1)"), ("j1", "Judul jadwal (baris 2)"), ("j2", "Judul jadwal (baris 3)"),
    ]
    KARTU_TTD1 = [("b_tt", "Tempat & tanggal"), ("b_jab", "Jabatan"), ("b_nama", "Nama"), ("b_nip", "NIP")]
    KARTU_TTD2 = [("j_tt", "Tempat & tanggal"), ("j_jab", "Jabatan"), ("j_nama", "Nama"), ("j_nip", "NIP")]

    def _build_meta(self):
        f = self.f_meta
        self.mv: Dict[str, tk.StringVar] = {}
        self._meta_loading = False
        self._meta_dirty = False
        f.columnconfigure(0, weight=1, uniform="k")
        f.columnconfigure(1, weight=1, uniform="k")

        def kartu(judul, fields, col, row, rowspan=1):
            k = theme.card(f, judul)
            k.outer.grid(row=row, column=col, rowspan=rowspan, sticky="new",
                         padx=(0, 8) if col == 0 else (8, 0), pady=(0, 10))
            k.columnconfigure(1, weight=1)
            for i, (key, label) in enumerate(fields, start=1):
                ttk.Label(k, text=label, style="Card.TLabel").grid(row=i, column=0, sticky="w", pady=3, padx=(0, 12))
                v = tk.StringVar()
                if key == "semester":
                    w = ttk.Combobox(k, textvariable=v, values=["GANJIL", "GENAP"], width=36)
                else:
                    w = ttk.Entry(k, textvariable=v, width=38)
                w.grid(row=i, column=1, sticky="ew", pady=3)
                w.bind("<Return>", lambda e: self.apply_meta())
                v.trace_add("write", lambda *a: self._meta_changed())
                self.mv[key] = v
            return k

        kartu("Identitas & judul cetakan", self.KARTU_IDENTITAS, 0, 0, rowspan=2)
        kartu("Tanda tangan — Hal. 1 (Beban Mengajar)", self.KARTU_TTD1, 1, 0)
        kartu("Tanda tangan — Jadwal", self.KARTU_TTD2, 1, 1)

        g = theme.card(f, "Gambar cetakan")
        g.outer.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.lbl_kop = ttk.Label(g, text="", style="CardMuted.TLabel")
        self.lbl_ttd = ttk.Label(g, text="", style="CardMuted.TLabel")
        ttk.Button(g, text="Ganti gambar kop…", command=lambda: self.pick_image("kop_png")).grid(
            row=1, column=0, sticky="w", padx=(0, 10))
        self.lbl_kop.grid(row=1, column=1, sticky="w", padx=(0, 24))
        ttk.Button(g, text="Ganti gambar tanda tangan…", command=lambda: self.pick_image("ttd_png")).grid(
            row=1, column=2, sticky="w", padx=(0, 10))
        self.lbl_ttd.grid(row=1, column=3, sticky="w")

        bar = ttk.Frame(f)
        bar.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.btn_apply = ttk.Button(bar, text="Terapkan perubahan", style="Accent.TButton", command=self.apply_meta)
        self.btn_apply.pack(side="left")
        self.lbl_dirty = ttk.Label(bar, text="", style="Muted.TLabel")
        self.lbl_dirty.pack(side="left", padx=12)
        ttk.Label(f, style="Muted.TLabel", wraplength=900, justify="left",
                  text="Tanggal pada cetakan diisi manual di sini (tidak otomatis), "
                       "supaya tidak ikut berganti sendiri.").grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def _meta_changed(self):
        if not self._meta_loading and not self._meta_dirty:
            self._meta_dirty = True
            self.lbl_dirty.config(text="● Ada perubahan yang belum diterapkan", foreground=theme.WARN_FG)

    def _meta_clean(self):
        self._meta_dirty = False
        self.lbl_dirty.config(text="")

    def _load_meta(self):
        m = self.p.meta
        vals = {"semester": m.semester, "tahun": m.tahun, "judul_beban": m.judul_beban,
                "judul_beban2": m.judul_beban2,
                "j0": (m.jadwal_judul + ["", "", ""])[0], "j1": (m.jadwal_judul + ["", "", ""])[1],
                "j2": (m.jadwal_judul + ["", "", ""])[2],
                "b_tt": m.beban_ttd.get("tempat_tanggal", ""), "b_jab": m.beban_ttd.get("jabatan", ""), "b_nama": m.beban_ttd.get("nama", ""),
                "b_nip": m.beban_ttd.get("nip", ""), "j_tt": m.jadwal_ttd.get("tempat_tanggal", ""),
                "j_jab": m.jadwal_ttd.get("jabatan", ""), "j_nama": m.jadwal_ttd.get("nama", ""),
                "j_nip": m.jadwal_ttd.get("nip", "")}
        self._meta_loading = True
        try:
            for k, v in vals.items():
                self.mv[k].set(v)
        finally:
            self._meta_loading = False
        self._meta_clean()
        self.lbl_kop.config(text="terpasang" if m.kop_png else "belum ada")
        self.lbl_ttd.config(text="terpasang" if m.ttd_png else "belum ada")

    def apply_meta(self):
        v = {k: x.get() for k, x in self.mv.items()}
        with self.store.edit() as p:
            m = p.meta
            m.semester, m.tahun = v["semester"].strip(), v["tahun"].strip()
            m.judul_beban, m.judul_beban2 = v["judul_beban"], v["judul_beban2"]
            m.jadwal_judul = [v["j0"], v["j1"], v["j2"]]
            m.beban_ttd = {"tempat_tanggal": v["b_tt"], "jabatan": v["b_jab"], "nama": v["b_nama"], "nip": v["b_nip"]}
            m.jadwal_ttd = {"tempat_tanggal": v["j_tt"], "jabatan": v["j_jab"], "nama": v["j_nama"], "nip": v["j_nip"]}

    def pick_image(self, attr):
        path = filedialog.askopenfilename(filetypes=[("Gambar", "*.png *.jpg *.jpeg")])
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
        except OSError as ex:
            messagebox.showerror("Gambar", str(ex))
            return
        with self.store.edit() as p:
            setattr(p.meta, attr, data)

    # ------------------------------------------------------------- jam
    def _build_jam(self):
        f = self.f_jam
        top = ttk.Frame(f)
        top.pack(fill="x")
        ttk.Label(top, text="Hari:").pack(side="left")
        self.v_hari = tk.StringVar(value=M.HARI[1])
        cb = ttk.Combobox(top, textvariable=self.v_hari, values=M.HARI, state="readonly", width=10)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self.fill_jam())
        for t, c in (("Ubah baris", self.jam_edit), ("Tambah mapel (2 JP)", self.jam_add_blok),
                     ("Hapus baris", self.jam_del), ("▲", lambda: self.jam_move(-1)), ("▼", lambda: self.jam_move(1))):
            ttk.Button(top, text=t, command=c).pack(side="left", padx=2)
        self.tj = ttk.Treeview(f, columns=("jenis", "jam", "waktu", "label"), show="headings", height=14, selectmode="browse")
        for c, w, t in (("jenis", 90, "Jenis"), ("jam", 80, "Jam ke"), ("waktu", 240, "Waktu"), ("label", 220, "Keterangan")):
            self.tj.heading(c, text=t)
            self.tj.column(c, width=w, anchor="w")
        self.tj.pack(fill="x", pady=8)
        self.tj.bind("<Double-1>", lambda e: self.jam_edit())
        self._jam_stale = True
        self.tj.bind("<Map>", lambda e: self._jam_stale and self.fill_jam())
        jf = ttk.Frame(f)
        jf.pack(fill="x")
        ttk.Label(jf, text="Judul nama hari pada cetakan:").pack(side="left")
        self.v_judul = tk.StringVar()
        ttk.Entry(jf, textvariable=self.v_judul, width=24).pack(side="left", padx=6)
        ttk.Button(jf, text="Terapkan", command=self.apply_judul).pack(side="left")
        ttk.Label(f, foreground="#555", wraplength=700, justify="left",
                  text="Satu mapel = 2 JP (satu 'mapel' di sini). Jam, waktu, dan istirahat bisa diubah per hari. "
                       "Menghapus baris mapel ikut menghapus isi jadwal pada jam itu.").pack(anchor="w", pady=8)

    JENIS = {"blok": "Mapel (2 JP)", "info": "Kegiatan", "jeda": "Istirahat", "tutup": "Tidak dipakai"}

    def fill_jam(self):
        self._jam_stale = False
        self.tj.delete(*self.tj.get_children())
        hari = self.v_hari.get()
        for i, r in enumerate(self.p.hari[hari]["baris"]):
            if r["t"] == "blok":
                vals = (self.JENIS["blok"], "-".join(str(j) for j in r["jam"]), "  |  ".join(r["waktu"]), "")
            elif r["t"] == "tutup":
                vals = (self.JENIS["tutup"], "-".join(str(j) for j in r.get("jam", [])), "  |  ".join(r.get("waktu", [])),
                        r.get("label", ""))
            else:
                vals = (self.JENIS[r["t"]], "", r.get("waktu", ""), r.get("label", ""))
            self.tj.insert("", "end", iid=str(i), values=vals)
        from .export_pdf import JUDUL_HARI
        self.v_judul.set(self.p.hari[hari].get("judul") or JUDUL_HARI.get(hari, hari.upper()))

    def reload(self):
        self._load_meta()
        # daftar jam baru diisi saat tabnya terlihat (menghindari impor modul PDF saat mulai)
        if self.tj.winfo_viewable():
            self.fill_jam()
        else:
            self._jam_stale = True

    def _cur_row(self):
        sel = self.tj.selection()
        return int(sel[0]) if sel else None

    def apply_judul(self):
        hari = self.v_hari.get()
        with self.store.edit() as p:
            p.hari[hari]["judul"] = self.v_judul.get()

    def jam_edit(self):
        i = self._cur_row()
        if i is None:
            return
        hari = self.v_hari.get()
        r = self.p.hari[hari]["baris"][i]
        t = r["t"]
        if t == "blok":
            fields = [("jam", "Jam ke (mis. 1,2)", "text", ",".join(str(j) for j in r["jam"]), None),
                      ("w1", "Waktu JP pertama", "text", r["waktu"][0], None),
                      ("w2", "Waktu JP kedua", "text", r["waktu"][1], None)]
        elif t == "tutup":
            fields = [("jam", "Jam ke (mis. 9,10; kosongkan bila tak ada)", "text", ",".join(str(j) for j in r.get("jam", [])), None),
                      ("w1", "Waktu jam pertama", "text", (r.get("waktu") or [""])[0], None),
                      ("w2", "Waktu jam kedua", "text", (r.get("waktu") or ["", ""])[1] if len(r.get("waktu", [])) > 1 else "", None),
                      ("label", "Tulisan (mis. SHOLAT JUM'AT)", "text", r.get("label", ""), None)]
        elif t == "info":
            fields = [("label", "Kegiatan", "text", r["label"], None), ("waktu", "Waktu", "text", r["waktu"], None),
                      ("warna", "Warna latar (mis. #00B050, kosong = putih)", "text", r.get("warna") or "", None)]
        else:
            fields = [("label", "Tulisan (mis. ISTIRAHAT)", "text", r.get("label", ""), None),
                      ("waktu", "Waktu", "text", r.get("waktu", ""), None)]
        d = FormDialog(self, "Ubah baris jam", fields).show()
        if not d:
            return
        with self.store.edit() as p:
            row = p.hari[hari]["baris"][i]
            if t == "blok":
                jam = [int(x) for x in d["jam"].replace(" ", "").split(",") if x.isdigit()]
                if len(jam) == 2:
                    row["jam"] = jam
                row["waktu"] = [d["w1"], d["w2"]]
            elif t == "tutup":
                row["jam"] = [int(x) for x in d["jam"].replace(" ", "").split(",") if x.isdigit()]
                row["waktu"] = [x for x in (d["w1"], d["w2"]) if x][:len(row["jam"])] if row["jam"] else []
                row["label"] = d["label"]
            elif t == "info":
                row["label"], row["waktu"], row["warna"] = d["label"], d["waktu"], d["warna"].strip() or None
            else:
                row["label"], row["waktu"] = d["label"], d["waktu"]

    def jam_add_blok(self):
        hari = self.v_hari.get()
        rows = self.p.hari[hari]["baris"]
        bl = [r for r in rows if r["t"] == "blok"]
        last_jam = max([j for r in bl for j in r["jam"]] or [0])
        d = FormDialog(self, "Tambah mapel (2 JP)", [
            ("w1", "Waktu JP pertama", "text", "", None), ("w2", "Waktu JP kedua", "text", "", None)]).show()
        if not d:
            return
        ids = {r["id"] for r in bl}
        n = 1
        while f"B{n}" in ids:
            n += 1
        with self.store.edit() as p:
            rows = p.hari[hari]["baris"]
            new = {"t": "blok", "id": f"B{n}", "jam": [last_jam + 1, last_jam + 2], "waktu": [d["w1"], d["w2"]]}
            pos = max([i for i, r in enumerate(rows) if r["t"] == "blok"] or [-1]) + 1
            rows.insert(pos, new)

    def jam_del(self):
        i = self._cur_row()
        if i is None:
            return
        hari = self.v_hari.get()
        r = self.p.hari[hari]["baris"][i]
        if r["t"] == "blok":
            n = sum(len(v) for v in self.p.jadwal.get(hari, {}).get(r["id"], {}).values())
            if not messagebox.askyesno("Hapus", f"Hapus mapel jam {r['jam']} hari {hari}?"
                                       + (f"\n{n} sel jadwal ikut terhapus." if n else "")):
                return
        with self.store.edit() as p:
            row = p.hari[hari]["baris"].pop(i)
            if row["t"] == "blok":
                p.jadwal.get(hari, {}).pop(row["id"], None)
                for g in p.guru:
                    if row["id"] in g.tidak_bisa.get(hari, []):
                        g.tidak_bisa[hari].remove(row["id"])

    def jam_move(self, d):
        i = self._cur_row()
        if i is None:
            return
        hari = self.v_hari.get()
        with self.store.edit() as p:
            rows = p.hari[hari]["baris"]
            j = i + d
            if 0 <= j < len(rows):
                rows[i], rows[j] = rows[j], rows[i]
        if self.tj.exists(str(i + d)):
            self.tj.selection_set(str(i + d))


# ============================================================= SEMESTER BARU
class SemesterBaruDialog(Dialog):
    """Membuat berkas semester berikutnya dari jadwal yang sedang dibuka."""

    def __init__(self, app):
        super().__init__(app, "Semester baru dari jadwal ini")
        self.app = app
        m = app.store.p.meta
        b = self.body
        self.v_sem = tk.StringVar(value="GENAP" if m.semester.upper() == "GANJIL" else "GANJIL")
        self.v_th = tk.StringVar(value=m.tahun)
        self.c_guru = tk.BooleanVar(value=True)
        self.c_pen = tk.BooleanVar(value=True)
        self.c_req = tk.BooleanVar(value=True)
        r = 0
        ttk.Label(b, text="Semester").grid(row=r, column=0, sticky="w")
        ttk.Combobox(b, textvariable=self.v_sem, values=["GANJIL", "GENAP"], width=12, state="readonly").grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Label(b, text="Tahun pelajaran").grid(row=r, column=0, sticky="w")
        ttk.Entry(b, textvariable=self.v_th, width=18).grid(row=r, column=1, sticky="w", pady=2)
        r += 1
        ttk.Checkbutton(b, text="Bawa daftar guru", variable=self.c_guru).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        ttk.Checkbutton(b, text="Bawa penugasan guru & beban JP (bisa diubah)", variable=self.c_pen).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        ttk.Checkbutton(b, text="Bawa permintaan jam guru", variable=self.c_req).grid(row=r, column=0, columnspan=2, sticky="w")
        r += 1
        ttk.Label(b, foreground="#555", wraplength=360, justify="left",
                  text="Isi jadwal selalu dikosongkan. Kelas dan jam pelajaran dibawa sebagaimana adanya; "
                       "semua bisa diubah lagi. Tempat & tanggal tanda tangan dikosongkan; isi ulang di tab Pengaturan.").grid(row=r, column=0, columnspan=2, sticky="w", pady=6)
        self.show()

    def collect(self):
        app = self.app
        if not app._confirm_discard():
            return None
        old = app.store.p
        p = old.clone()
        p.jadwal = {}
        m = p.meta
        m.semester, m.tahun = self.v_sem.get(), self.v_th.get().strip()
        th = m.tahun.replace(" ", "")
        # tanggal cetak semester lama tidak boleh terbawa; operator mengisi ulang di Pengaturan
        m.beban_ttd = {**m.beban_ttd, "tempat_tanggal": ""}
        m.jadwal_ttd = {**m.jadwal_ttd, "tempat_tanggal": ""}
        m.jadwal_judul = [f"JADWAL PELAJARAN SEMESTER {m.semester}",
                          (m.jadwal_judul + ["", "", ""])[1], f"TAHUN PELAJARAN {th}"]
        if not self.c_pen.get() or not self.c_guru.get():
            p.penugasan = []
            for k in p.kelas:
                k.wali = k.wali if self.c_guru.get() else None
        if not self.c_guru.get():
            p.guru = []
        if not self.c_req.get():
            for g in p.guru:
                g.tidak_bisa = {}
        app.gv.sel = None
        app.store.replace(p, None)
        app.save_as()
        return True
