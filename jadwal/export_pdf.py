"""Ekspor PDF: Daftar Beban Mengajar (hal. 1) dan Jadwal Pelajaran (hal. 2).

Tata letak mengikuti PDF sekolah (koordinat diukur dari berkas aslinya):
- Hal. 1: Legal potret 612x1008 pt.
- Hal. 2: 936x612 pt (13x8,5 inci), lima hari dalam dua kelompok: Selasa|Rabu|Kamis
  di atas, Senin|Jumat|panel waktu Jumat di bawah.
Jumlah kelas, guru, dan jam boleh berubah; lebar kolom menyesuaikan.
"""
from __future__ import annotations

import base64
import io
import os
from typing import Dict, List, Optional

from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .model import Proyek, Penugasan

# ------------------------------------------------------------------- font
_FONT_DIRS = [os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts")]
_FONTS = {}


def _find(*names):
    for d in _FONT_DIRS:
        for n in names:
            f = os.path.join(d, n)
            if os.path.exists(f):
                return f
    return None


def _register():
    if _FONTS:
        return
    spec = {
        "Tahoma": ("tahoma.ttf", "Helvetica"),
        "Tahoma-Bold": ("tahomabd.ttf", "Helvetica-Bold"),
        "Arial-Bold": ("arialbd.ttf", "Helvetica-Bold"),
        "Calibri-Bold": ("calibrib.ttf", "arialbd.ttf"),
    }
    for name, (ttf, fallback) in spec.items():
        path = _find(ttf)
        if path is None and fallback.endswith(".ttf"):
            path = _find(fallback)
        if path:
            pdfmetrics.registerFont(TTFont(name, path))
            _FONTS[name] = name
        else:
            _FONTS[name] = fallback


def F(name: str) -> str:
    _register()
    return _FONTS[name]


def _img(b64: str) -> Optional[ImageReader]:
    if not b64:
        return None
    try:
        return ImageReader(io.BytesIO(base64.b64decode(b64)))
    except Exception:
        return None


def _rgb(hexcol: Optional[str], default=(1, 1, 1)):
    if not hexcol:
        return default
    h = hexcol.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


RED = (1, 0, 0)
BLACK = (0, 0, 0)
HEAD_BLUE = (0.863, 0.902, 0.941)
GRAY = (0.749, 0.749, 0.749)
LINE = 0.3
K = 0.35            # tinggi huruf kapital ~ 0.7 -> garis dasar = tengah + 0.35*ukuran


class Pen:
    """Pembantu menggambar dengan sistem koordinat atas-kiri (seperti PDF asli)."""

    def __init__(self, c: canvas.Canvas, w: float, h: float):
        self.c, self.w, self.h = c, w, h

    def rect(self, x0, y0, x1, y1, fill=None, stroke=True, lw=LINE):
        c = self.c
        c.setLineWidth(lw)
        if fill is not None:
            c.setFillColorRGB(*fill)
        c.rect(x0, self.h - y1, x1 - x0, y1 - y0, stroke=1 if stroke else 0,
               fill=1 if fill is not None else 0)

    def line(self, x0, y0, x1, y1, lw=LINE):
        self.c.setLineWidth(lw)
        self.c.line(x0, self.h - y0, x1, self.h - y1)

    def text(self, x, ycenter, s, font, size, color=BLACK, anchor="c", space=0.0):
        """Teks dengan pusat vertikal di ycenter; anchor c/l/r terhadap x."""
        if s is None or s == "":
            return
        c = self.c
        c.setFillColorRGB(*color)
        c.setFont(F(font), size)
        wid = pdfmetrics.stringWidth(s, F(font), size) + space * max(len(s) - 1, 0)
        if anchor == "c":
            x = x - wid / 2
        elif anchor == "r":
            x = x - wid
        t = c.beginText(x, self.h - (ycenter + K * size))
        t.setFont(F(font), size)
        t.setCharSpace(space)
        t.textOut(s)
        c.drawText(t)

    def vtext(self, xcenter, ycenter, s, font, size, color=BLACK, baseline_x=None):
        """Teks diputar 90 derajat (dibaca dari bawah ke atas), dipusatkan.

        baseline_x: bila diberikan, dipakai sebagai garis dasar (x) alih-alih
        memusatkan secara horizontal.
        """
        c = self.c
        c.saveState()
        c.setFillColorRGB(*color)
        wid = pdfmetrics.stringWidth(s, F(font), size)
        bx = baseline_x if baseline_x is not None else xcenter + K * size
        c.translate(bx, self.h - ycenter)
        c.rotate(90)
        t = c.beginText(-wid / 2, 0)
        t.setFont(F(font), size)
        t.setCharSpace(0)
        t.textOut(s)
        c.drawText(t)
        c.restoreState()

    def btext(self, x, baseline, s, font, size, color=BLACK, anchor="c"):
        """Teks dengan garis dasar (y) eksplisit."""
        if not s:
            return
        wid = pdfmetrics.stringWidth(s, F(font), size)
        if anchor == "c":
            x -= wid / 2
        elif anchor == "r":
            x -= wid
        c = self.c
        c.setFillColorRGB(*color)
        t = c.beginText(x, self.h - baseline)
        t.setFont(F(font), size)
        t.setCharSpace(0)
        t.textOut(s)
        c.drawText(t)

    def image(self, img, x0, y0, x1, y1):
        if img is not None:
            self.c.drawImage(img, x0, self.h - y1, x1 - x0, y1 - y0, mask="auto")


def _kode_font(kode: str):
    """Kode satu angka dicetak Tahoma, selainnya Arial (mengikuti cetakan asli)."""
    if len(kode) == 1 and kode.isdigit():
        return "Tahoma-Bold"
    return "Arial-Bold"


# =============================================================== HALAMAN 1
_P1 = dict(w=612.0, h=1008.0, x_no=51.5, x_nama=67.7, x_kode=171.2, x_bid=204.8,
           x_bbt=319.6, x_cls0=342.8, x_cls1=537.7, x_wali1=573.5, x_ket1=596.7,
           y_head=149.7, y_band=160.0, y_row0=234.7, row_h=14.4)


def _col_edges(x0, x1, n):
    """Tepi kolom kelas. Dua kolom pertama sedikit lebih lebar (seperti aslinya)."""
    if n <= 0:
        return [x0, x1]
    wts = [1.16 if i < 2 and n >= 3 else 1.0 for i in range(n)]
    tot = sum(wts)
    edges, acc = [x0], 0.0
    for w in wts:
        acc += w
        edges.append(x0 + (x1 - x0) * acc / tot)
    return edges


def _total(a: Penugasan) -> int:
    return sum(a.beban.values())


def _ket_range(a: Penugasan, n: int):
    d = a.ket_dari if a.ket_dari is not None else min(3, max(n - 1, 0))
    e = a.ket_sampai if a.ket_sampai is not None else max(n - 3, d)
    return max(0, min(d, n - 1)), max(0, min(e, n - 1))


def draw_beban(c: canvas.Canvas, p: Proyek):
    g = _P1
    c.setPageSize((g["w"], g["h"]))
    pen = Pen(c, g["w"], g["h"])
    n = len(p.kelas)
    edges = _col_edges(g["x_cls0"], g["x_cls1"], n)
    m = p.meta

    pen.image(_img(m.kop_png), 51.0, 11.2, 574.0, 92.4)
    cx = 332.7
    pen.text(330.4, 102.9, m.judul_beban, "Tahoma-Bold", 14.4)
    pen.text(cx, 117.9, m.judul_beban2, "Tahoma-Bold", 9.2)
    pen.text(cx, 131.8, f"SEMESTER {m.semester} TAHUN PELAJARAN {m.tahun}", "Tahoma-Bold", 13.0)

    top, band, y0 = g["y_head"], g["y_band"], g["y_row0"]
    xs = [g["x_no"], g["x_nama"], g["x_kode"], g["x_bid"], g["x_bbt"], g["x_cls0"]]
    # ---- kepala tabel
    for a, b in zip(xs[:4], xs[1:5]):
        pen.rect(a, top, b, y0, fill=(1, 1, 1))
    pen.rect(g["x_bbt"], top, g["x_cls0"], band, fill=(1, 1, 1))
    pen.rect(g["x_bbt"], band, g["x_cls0"], y0, fill=(1, 1, 1))
    pen.rect(g["x_cls0"], top, g["x_cls1"], band, fill=(1, 1, 1))
    for i in range(n):
        pen.rect(edges[i], band, edges[i + 1], y0, fill=HEAD_BLUE)
        pen.vtext((edges[i] + edges[i + 1]) / 2, (band + y0) / 2, p.kelas[i].nama, "Tahoma-Bold", 9.2)
    pen.rect(g["x_cls1"], top, g["x_wali1"], y0, fill=(1, 1, 1))
    pen.rect(g["x_wali1"], top, g["x_ket1"], y0, fill=(1, 1, 1))
    mid = (top + y0) / 2
    pen.text(g["x_no"] + 0.7, mid, "NO.", "Tahoma", 9.2, anchor="l")
    pen.text(g["x_nama"] - 0.7, mid, " NAMA GURU", "Tahoma-Bold", 9.2, anchor="l")
    pen.text((g["x_kode"] + g["x_bid"]) / 2, mid, "KODE", "Tahoma-Bold", 9.2)
    pen.text((g["x_bid"] + g["x_bbt"]) / 2, mid, "BIDANG STUDI", "Tahoma-Bold", 9.2)
    pen.text((g["x_bbt"] + g["x_cls0"]) / 2, (top + band) / 2, "BBT", "Tahoma-Bold", 9.2)
    pen.text((g["x_bbt"] + g["x_cls0"]) / 2, (band + y0) / 2, "JAM", "Tahoma-Bold", 7.8)
    pen.text((g["x_cls0"] + g["x_cls1"]) / 2 + 0.5, (top + band) / 2, "KELAS", "Tahoma-Bold", 9.2)
    pen.vtext((g["x_cls1"] + g["x_wali1"]) / 2, (band + y0) / 2 + 0.1, "WALI KELAS", "Tahoma-Bold", 9.2)
    pen.text((g["x_wali1"] + g["x_ket1"]) / 2 - 1.0, mid, "KET", "Tahoma-Bold", 7.8)

    # ---- baris data
    rows = list(p.penugasan)
    nrow = len(rows)
    row_h = g["row_h"]
    avail = 1008.0 - 135.0 - y0          # sisakan ruang untuk tanda tangan
    if nrow * row_h > avail:
        row_h = max(9.0, avail / nrow)
    scale = row_h / g["row_h"]

    # kelompok guru berurutan (sel NO & nama digabung)
    groups: List[List[int]] = []
    for i, a in enumerate(rows):
        if groups and rows[groups[-1][0]].guru == a.guru and not a.nama_tampil \
                and not rows[groups[-1][0]].nama_tampil:
            groups[-1].append(i)
        else:
            groups.append([i])
    # baris dengan nama_tampil tidak bergabung dengan baris lain
    group_of = {}
    for gi, grp in enumerate(groups):
        for i in grp:
            group_of[i] = gi
    wali_row: Dict[int, str] = {}        # indeks baris -> nama kelas yang diwalikan
    for k in p.kelas:
        if not k.wali:
            continue
        cand = [i for i, a in enumerate(rows) if a.guru == k.wali]
        if not cand:
            continue
        pick = next((i for i in cand if rows[i].beban.get(k.id, 0) > 0), cand[0])
        wali_row[pick] = (wali_row.get(pick, "") + " " + k.nama).strip()

    def ry(i):
        return y0 + i * row_h

    for i, a in enumerate(rows):
        ya, yb = ry(i), ry(i) + row_h
        yc = (ya + yb) / 2
        guru = p.guru_by_id(a.guru)
        special = _rgb(a.fill_baris) if a.fill_baris else None
        pen.rect(g["x_bid"], ya, g["x_bbt"], yb,
                 fill=_rgb(a.fill_mapel) if a.fill_mapel else (special or (1, 1, 1)))
        pen.rect(g["x_kode"], ya, g["x_bid"], yb,
                 fill=special if special else (_rgb(a.warna) if a.kode else (1, 1, 1)))
        # BBT
        bbt_fill = special or (1, 1, 1)
        if a.bbt_gabung and i > 0:
            pen.rect(g["x_bbt"], ya, g["x_cls0"], yb, fill=bbt_fill, stroke=False)
            pen.line(g["x_bbt"], ya, g["x_bbt"], yb)
            pen.line(g["x_cls0"], ya, g["x_cls0"], yb)
        else:
            pen.rect(g["x_bbt"], ya, g["x_cls0"], yb, fill=bbt_fill)
        # matriks kelas
        kd, ke = _ket_range(a, n)
        for j in range(n):
            if a.keterangan and kd <= j <= ke:
                continue                                  # digambar sebagai sel gabungan
            v = a.beban.get(p.kelas[j].id)
            if special:
                fill = special
            elif v is None:
                fill = BLACK
            else:
                fill = (1, 1, 1)
            pen.rect(edges[j], ya, edges[j + 1], yb, fill=fill)
        if a.keterangan:
            pen.rect(edges[kd], ya, edges[ke + 1], yb, fill=special or (1, 1, 1))
        # wali
        wtxt = wali_row.get(i, "")
        wfill = special or (1, 1, 1 if wtxt else 0)
        if special:
            wf = special
        else:
            wf = (1, 1, 1) if wtxt else GRAY
        pen.rect(g["x_cls1"], ya, g["x_wali1"], yb, fill=wf)
        ketfill = special or (1, 1, 1)
        pen.rect(g["x_wali1"], ya, g["x_ket1"], yb, fill=ketfill)

        # isi sel
        if a.mapel:
            size = a.ukuran_mapel or 7.8
            pen.text((g["x_bid"] + g["x_bbt"]) / 2, yc, a.mapel, "Tahoma-Bold", size)
        if a.kode:
            kf = _kode_font(a.kode)
            ks = 7.8 if a.kode in ("1", "2") else 9.2
            pen.text((g["x_kode"] + g["x_bid"]) / 2, yc - 1.5, a.kode, kf, ks)
        colr = RED if a.merah else BLACK
        for j in range(n):
            v = a.beban.get(p.kelas[j].id, 0)
            if v > 0:
                pen.text((edges[j] + edges[j + 1]) / 2, yc, str(v),
                         "Tahoma-Bold" if a.merah else "Tahoma", 7.8, colr)
        if a.keterangan:
            kd, _ke = _ket_range(a, n)
            geser = a.ket_geser if a.ket_geser is not None else 2.1
            pen.text(edges[kd] + geser, yc, a.keterangan.strip(), "Tahoma-Bold", 9.2, anchor="l")
        if wtxt:
            pen.text((g["x_cls1"] + g["x_wali1"]) / 2, yc, wtxt, "Tahoma-Bold", 11.8)
        tot = a.ket_manual if a.ket_manual is not None else _total(a)
        if tot:
            pen.text((g["x_wali1"] + g["x_ket1"]) / 2, yc, str(tot), "Tahoma-Bold", 10.4,
                     RED if a.ket_merah else BLACK)

    # teks BBT (setelah semua sel agar sel gabungan tidak tertimpa)
    for i, a in enumerate(rows):
        if a.bbt is not None and not (a.bbt_gabung and i > 0):
            by1 = ry(i + 1) + row_h if i + 1 < nrow and rows[i + 1].bbt_gabung else ry(i) + row_h
            pen.text((g["x_bbt"] + g["x_cls0"]) / 2, (ry(i) + by1) / 2, str(a.bbt),
                     "Tahoma-Bold", 9.2)

    # NO & nama (sel digabung per guru)
    no = 0
    last_guru = None
    for gi, grp in enumerate(groups):
        ya, yb = ry(grp[0]), ry(grp[-1]) + row_h
        yc = (ya + yb) / 2
        a0 = rows[grp[0]]
        guru = p.guru_by_id(a0.guru)
        if a0.guru != last_guru:
            no += 1
        nomor_baru = a0.guru != last_guru
        last_guru = a0.guru
        special = _rgb(a0.fill_baris) if a0.fill_baris else None
        nama = a0.nama_tampil or (guru.nama if guru else "")
        nfill = _rgb(guru.fill_nama) if guru and guru.fill_nama else (special or (1, 1, 1))
        pen.rect(g["x_nama"], ya, g["x_kode"], yb, fill=nfill)
        pen.text(g["x_nama"] + 1.7, yc, nama, "Tahoma", 7.8, anchor="l")
    # kolom NO: gabungkan semua baris milik guru yang sama (termasuk nama_tampil)
    i = 0
    no = 0
    while i < nrow:
        j = i
        while j + 1 < nrow and rows[j + 1].guru == rows[i].guru:
            j += 1
        no += 1
        guru = p.guru_by_id(rows[i].guru)
        ya, yb = ry(i), ry(j) + row_h
        pen.rect(g["x_no"], ya, g["x_nama"], yb,
                 fill=_rgb(guru.fill_no) if guru and guru.fill_no else (1, 1, 1))
        pen.text((g["x_no"] + g["x_nama"]) / 2 + 0.5, (ya + yb) / 2, str(no), "Tahoma", 7.8)
        i = j + 1

    # bingkai luar tebal
    ybot = y0 + nrow * row_h
    pen.rect(g["x_no"], top, g["x_ket1"], ybot, fill=None, lw=0.5)

    # tanda tangan
    t = m.beban_ttd
    sy = ybot + 16.8
    pen.text(474.4, sy + 5.6, t.get("tempat_tanggal", ""), "Tahoma", 9.2, anchor="l")
    pen.image(_img(m.ttd_png), 456.3, sy + 17.0, 545.5, sy + 68.4)
    if t.get("jabatan"):      # digambar setelah gambar tanda tangan agar tidak tertutup
        pen.text(457.5, sy + 14.2, t["jabatan"], "Tahoma-Bold", 7.0, anchor="l")
    pen.btext(457.5, sy + 71.4, t.get("nama", ""), "Calibri-Bold", 7.8, anchor="l")
    wid = pdfmetrics.stringWidth(t.get("nama", ""), F("Calibri-Bold"), 7.8)
    pen.line(457.5, sy + 74.3, 457.5 + wid, sy + 74.3, lw=0.5)
    pen.btext(457.5, sy + 81.6, t.get("nip", ""), "Calibri-Bold", 7.8, anchor="l")
    c.showPage()


# =============================================================== HALAMAN 2
_X = {"Senin": (56.6, 350.5), "Selasa": (56.6, 350.5), "Rabu": (354.7, 635.3),
      "Jumat": (354.7, 635.3), "Kamis": (635.3, 893.2)}
_NO_X0, _NO_X1, _WK_X1 = 9.9, 20.5, 56.6
JUDUL_HARI = {"Senin": "S  E  N  I  N", "Selasa": "S   E   LASA", "Rabu": "R A B U",
              "Kamis": "K A M I S", "Jumat": "J  U  M ' A  T"}
_PANEL = (635.3, 653.6, 893.2)
# Tepi kolom 14 kelas pada cetakan asli (lebar kolom tidak seragam). Dipakai bila
# jumlah kelas 14; selain itu kolom dibagi rata.
_E_SEL = [56.7, 76.9, 97.1, 117.5, 138.7, 159.9, 183.3, 210.0, 228.6, 249.6, 269.4, 289.6,
          310.0, 329.2, 350.4]
_E_RAB = [354.8, 373.8, 395.2, 414.4, 433.6, 452.6, 475.8, 495.6, 516.8, 536.6, 557.6, 575.2,
          599.2, 615.2, 635.2]
_E_KAM = [635.2, 653.6, 672.9, 693.9, 712.9, 732.9, 750.6, 770.9, 789.9, 809.7, 826.1, 843.9,
          860.9, 877.1, 893.1]
_E14 = {"Senin": _E_SEL, "Selasa": _E_SEL, "Rabu": _E_RAB, "Jumat": _E_RAB, "Kamis": _E_KAM}


def _edges_hari(hari: str, n: int):
    x0, x1 = _X[hari]
    if n == 14:
        e = list(_E14[hari])
        e[0], e[-1] = x0, x1
        return e
    return [x0 + (x1 - x0) * i / n for i in range(n + 1)] if n else [x0, x1]


def _day_rows(p: Proyek, hari: str):
    return p.hari[hari]["baris"]


def _expand(rows):
    """Baris cetak: blok & tutup berjam -> dua baris cetak (satu per JP)."""
    out = []
    for r in rows:
        if r["t"] == "blok":
            out.append(("jp", r, 0))
            out.append(("jp", r, 1))
        elif r["t"] == "tutup" and r.get("jam"):
            for k in range(len(r["jam"])):
                out.append(("tutup_jp", r, k))
        else:
            out.append((r["t"], r, 0))
    return out


def _cell_fill(p: Proyek, by_kode, kodes: List[str]):
    if not kodes:
        return (1, 1, 1)
    a = by_kode.get(kodes[-1].upper())
    return _rgb(a.warna) if a else (1, 1, 1)


def draw_jadwal(c: canvas.Canvas, p: Proyek):
    W, H = 936.0, 612.0
    c.setPageSize((W, H))
    pen = Pen(c, W, H)
    n = len(p.kelas)
    by_kode = p.penugasan_by_kode()
    m = p.meta
    for i, line in enumerate(m.jadwal_judul[:3]):
        pen.btext(435.1 if i == 0 else 451.6, 23.4 + 9.2 * i, line, "Tahoma-Bold", 7.0)

    groups = [
        dict(days=["Selasa", "Rabu", "Kamis"], title=(43.4, 51.8), labels=(51.8, 64.1),
             rows=64.1, top=True),
        dict(days=["Senin", "Jumat", None], title=(222.7, 234.9), labels=(234.9, 247.3),
             rows=247.3, top=False),
    ]
    rh = 12.2
    # tinggi baris bila jumlah baris lebih banyak dari bawaan
    maxrows = [max(len(_expand(_day_rows(p, d))) for d in gr["days"] if d) for gr in groups]
    need = (maxrows[0] + maxrows[1]) * rh + 43.4 + 8.4 + 12.4 + 12.2 + 12.2 + 12.2 + 40
    if need > H - 30:
        rh = rh * (H - 30 - 140) / ((maxrows[0] + maxrows[1]) * rh)

    for gr_i, gr in enumerate(groups):
        lay = [_expand(_day_rows(p, d)) if d else [] for d in gr["days"]]
        nr = max(len(x) for x in lay)
        ref = lay[0]                        # susunan baris acuan (kolom waktu kiri)
        y_rows = gr["rows"] if gr_i == 0 else gr["rows"]
        yb = y_rows + nr * rh
        # ---- sumbu kiri (NO, WAKTU)
        t0, t1 = gr["title"]
        l0, l1 = gr["labels"]
        if gr["top"]:
            pen.rect(_NO_X0, t0, _WK_X1, t1, fill=(1, 1, 1))
            pen.rect(_NO_X0, l0, _NO_X1, l1, fill=(1, 1, 1))
            pen.rect(_NO_X1, l0, _WK_X1, l1, fill=(1, 1, 1))
            pen.btext(38.4, 48.7, "WAKTU", "Calibri-Bold", 5.4)
            pen.btext(14.2, 55.0, "NO", "Calibri-Bold", 4.8)
            pen.btext(38.6, 60.5, "KELAS", "Calibri-Bold", 7.0)
        else:
            pen.rect(_NO_X0, t0, _NO_X1, t1, fill=(1, 1, 1))
            pen.rect(_NO_X1, t0, _WK_X1, t1, fill=(1, 1, 1))
            pen.rect(_NO_X0, l0, _WK_X1, l1, fill=(1, 1, 1))
            pen.btext(15.2, t0 + 8.15, "NO", "Calibri-Bold", 5.4)
            pen.btext(38.6, t0 + 8.15, "WAKTU", "Calibri-Bold", 5.4)
            pen.btext(33.4, l0 + 7.75, "KELAS", "Calibri-Bold", 5.4)
        top = gr["top"]
        for k, (kind, r, h) in enumerate(ref):
            ya, yb2 = y_rows + k * rh, y_rows + (k + 1) * rh
            if kind in ("jp", "tutup_jp"):
                pen.rect(_NO_X0, ya, _NO_X1, yb2, fill=(1, 1, 1))
                pen.rect(_NO_X1, ya, _WK_X1, yb2, fill=(1, 1, 1))
                jam = r["jam"][h] if h < len(r["jam"]) else ""
                w = r["waktu"][h] if h < len(r["waktu"]) else ""
                base = yb2 - 1.6 if top else ya + 5.5
                pen.btext(15.6, base, str(jam), "Calibri-Bold", 5.4)
                pen.btext(38.5, base, w, "Calibri-Bold", 5.4)
            else:
                pen.rect(_NO_X0, ya, _WK_X1, yb2, fill=(1, 1, 1))
                base = yb2 - 1.4 if top else ya + 5.7
                pen.btext(33.2, base, r.get("waktu", ""), "Tahoma-Bold", 5.4, RED)

        # ---- blok hari
        for di, hari in enumerate(gr["days"]):
            if hari is None:
                _draw_panel(pen, p, gr, nr, rh)
                continue
            x0, x1 = _X[hari]
            edges = _edges_hari(hari, n)
            fs = 6.6 if gr["top"] else 5.4
            pen.rect(x0, t0, x1, t1, fill=(1, 1, 1))
            judul = p.hari[hari].get("judul") or JUDUL_HARI.get(hari, " ".join(hari.upper()))
            if gr["top"]:
                pen.btext((x0 + x1) / 2, t0 + 7.5, judul, "Tahoma-Bold", 7.0)
            else:
                pen.btext((x0 + x1) / 2, t0 + 7.9, judul, "Tahoma-Bold", 5.4)
            for i in range(n):
                pen.rect(edges[i], l0, edges[i + 1], l1, fill=HEAD_BLUE)
                pen.vtext(0, (l0 + l1) / 2, p.kelas[i].nama, "Tahoma-Bold", fs,
                          baseline_x=edges[i] + (8.4 if gr["top"] else 7.0))
            my = lay[di]
            blk_i = 0
            k = 0
            while k < nr:
                if k >= len(my):
                    k += 1
                    continue
                kind, r, h = my[k]
                ya, yb2 = y_rows + k * rh, y_rows + (k + 1) * rh
                if kind == "info":
                    fill = _rgb(r.get("warna")) if r.get("warna") else (1, 1, 1)
                    mergeto = max(n - 2, 1)
                    pen.rect(edges[0], ya, edges[mergeto], yb2, fill=fill)
                    for i in range(mergeto, n):
                        pen.rect(edges[i], ya, edges[i + 1], yb2, fill=fill)
                    colr = BLACK if r.get("warna") else RED
                    sz = 5.4 if r.get("warna") else 4.8
                    pen.btext((edges[0] + edges[mergeto]) / 2, ya + (6.2 if gr["top"] else 5.7),
                              r["label"], "Tahoma-Bold", sz, colr)
                elif kind == "jeda":
                    pen.rect(x0, ya, x1, yb2, fill=(1, 1, 1))
                    if r.get("label"):
                        pen.text((x0 + x1) / 2, (ya + yb2) / 2, r["label"], "Tahoma-Bold", 5.4)
                elif kind in ("tutup", "tutup_jp"):
                    pen.rect(x0, ya, x1, yb2, fill=BLACK)
                elif kind == "jp" and h == 0:
                    bid = r["id"]
                    for i in range(n):
                        kid = p.kelas[i].id
                        jp = p.get_cell(hari, bid, kid)
                        same = jp[0] == jp[1]
                        for half in (0, 1):
                            ya2 = y_rows + (k + half) * rh
                            kodes = jp[half]
                            pen.rect(edges[i], ya2, edges[i + 1], ya2 + rh,
                                     fill=_cell_fill(p, by_kode, kodes), stroke=False)
                            txt = "/".join(kodes)
                            if txt:
                                fnt = _kode_font(txt)
                                pen.text((edges[i] + edges[i + 1]) / 2, ya2 + rh / 2, txt, fnt, 5.4)
                        # tiap JP adalah sel sendiri (garis tengah selalu ada, seperti aslinya)
                        pen.rect(edges[i], ya, edges[i + 1], ya + rh, fill=None)
                        pen.rect(edges[i], ya + rh, edges[i + 1], ya + 2 * rh, fill=None)
                k += 1
        # separator hitam Selasa|Rabu (kiri) dan Senin|Jumat
        pen.rect(350.4, gr["title"][0], 354.7, y_rows + nr * rh, fill=BLACK, stroke=False)
    # --- tanda tangan
    t = m.jadwal_ttd
    pen.text(438.8, 362.7, t.get("tempat_tanggal", ""), "Tahoma", 5.4, anchor="l")
    pen.text(447.9, 374.7, t.get("jabatan", ""), "Tahoma-Bold", 5.4, anchor="l")
    pen.image(_img(m.ttd_png), 448.8, 378.7, 497.0, 405.0)
    pen.text(458.9, 406.0, t.get("nama", ""), "Tahoma-Bold", 3.8, anchor="l")
    pen.text(457.9, 410.9, t.get("nip", ""), "Tahoma-Bold", 3.8, anchor="l")
    c.showPage()


def _draw_panel(pen: Pen, p: Proyek, gr, nr, rh):
    """Panel waktu Jumat (kanan-bawah)."""
    x0, x1, x2 = _PANEL
    t0, t1 = gr["title"]
    l0, l1 = gr["labels"]
    y_rows = gr["rows"]
    pen.rect(x0, t0, x1, t1, fill=(1, 1, 1))
    pen.rect(x1, t0, x2, t1, fill=(1, 1, 1))
    pen.rect(x0, l0, x2, l1, fill=(1, 1, 1))
    pen.btext(x0 + 1.5, t0 + 5.55, "NO", "Calibri-Bold", 5.4, anchor="l")
    pen.btext(757.4, t0 + 5.55, "WAKTU", "Calibri-Bold", 5.4)
    pen.btext(764.3, l0 + 7.75, "KELAS", "Calibri-Bold", 5.4)
    lay = _expand(_day_rows(p, "Jumat"))
    for k, (kind, r, h) in enumerate(lay):
        ya, yb = y_rows + k * rh, y_rows + (k + 1) * rh
        if kind == "jp":
            pen.rect(x0, ya, x1, yb, fill=(1, 1, 1))
            pen.rect(x1, ya, x2, yb, fill=(1, 1, 1))
            pen.btext(x0 + 1.5, ya + 5.5, str(r["jam"][h]), "Calibri-Bold", 5.4, anchor="l")
            pen.btext(655.0, ya + 7.4, r["waktu"][h], "Calibri-Bold", 5.4, anchor="l")
        elif kind in ("info", "jeda"):
            pen.rect(x0, ya, x2, yb, fill=(1, 1, 1))
            pen.btext(764.2, ya + 7.8, r.get("waktu", ""), "Tahoma-Bold", 5.4, RED)
        elif kind in ("tutup", "tutup_jp"):
            pen.rect(x0, ya, x2, yb, fill=(1, 1, 1))
            pen.btext(764.2, ya + 7.4, r.get("label", ""), "Calibri-Bold", 5.4, RED)


# ================================================================== API
def export_pdf(p: Proyek, path: str, halaman=("beban", "jadwal")):
    c = canvas.Canvas(path, pagesize=(612, 1008))
    c.setTitle("Jadwal dan Kode Guru")
    for h in halaman:
        if h == "beban":
            draw_beban(c, p)
        elif h == "jadwal":
            draw_jadwal(c, p)
    c.save()
