"""Ekstrak data contoh dari PDF 'JADWAL DAN KODE GURU 2025-2026.pdf' menjadi
berkas proyek (.jadwal) yang dipakai untuk uji & contoh awal.

Alat bantu pengembang, tidak ikut dikemas ke aplikasi.
Pemakaian:  python tools/extract_seed.py <pdf> <keluaran.jadwal>
"""
import base64
import json
import sys
import warnings

warnings.filterwarnings("ignore")
import pymupdf  # noqa: E402

ROW0 = 234.7          # y atas baris pertama tabel beban (hal. 1)
ROWH = 14.4
NROWS = 35
TEACHER_ROWS = [2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1,
                1, 1, 1, 1, 1, 1, 2, 1, 1]
# baris yang BBT-nya digabung vertikal dengan baris di atasnya (lihat PDF)
BBT_MERGE_ROWS = {5, 24}            # indeks baris (0-based)
LIGHT_BLUE = (0.57, 0.8, 0.86)

X_NAME, X_KODE, X_BIDANG, X_BBT, X_CLS0, X_CLS1, X_WALI, X_KET = (
    67.7, 171.2, 204.8, 319.6, 342.8, 537.7, 573.5, 596.7)


def hexcol(c):
    return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in c)


def fill_at(drawings, x, y):
    got = None
    for d in drawings:
        r = d["rect"]
        if d.get("fill") and r[0] <= x <= r[2] and r[1] <= y <= r[3] \
                and (r[2] - r[0]) > 3 and (r[3] - r[1]) > 3:
            got = d["fill"]
    return got


def spans(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip():
                    out.append((s, l["dir"]))
    return out


def parse_beban(page):
    dr = page.get_drawings()
    sp = spans(page)
    # kelas dari label rotasi di header
    labels = sorted(
        [(s["bbox"][0], s["text"]) for s, d in sp
         if abs(d[1] + 1) < 0.01 and 185 < s["bbox"][1] < 210
         and X_CLS0 < s["bbox"][0] < X_CLS1],
        key=lambda t: t[0])
    classes = [t for _, t in labels]
    n = len(classes)
    from jadwal.export_pdf import _col_edges
    edges = _col_edges(X_CLS0, X_CLS1, n)
    rows = []
    for i in range(NROWS):
        y0 = ROW0 + i * ROWH
        y1 = y0 + ROWH
        yc = (y0 + y1) / 2
        row = dict(i=i, name="", kode="", bidang="", bbt=None, load={}, merah=False,
                   span="", wali="", ket="", ket_red=False, kode_fill=None,
                   bidang_fill=None, name_fill=None)
        for s, d in sp:
            bx = s["bbox"]
            cy = (bx[1] + bx[3]) / 2
            if not (y0 + 1 <= cy <= y1 - 1) or d[0] < 0.5:
                continue
            cx = (bx[0] + bx[2]) / 2
            t = s["text"].strip()
            red = s["color"] == 0xFF0000
            if cx < X_KODE:
                continue  # nama guru ditangani terpisah (sel nama bisa digabung)
            elif X_KODE <= cx < X_BIDANG:
                row["kode"] = t
            elif X_BIDANG <= cx < X_BBT:
                row["bidang"] = (row["bidang"] + " " + t).strip()
            elif X_BBT <= cx < X_CLS0:
                try:
                    row["bbt"] = int(t)
                except ValueError:
                    pass
            elif X_CLS0 <= cx < X_CLS1:
                if t.isdigit() and bx[2] - bx[0] < 12:
                    f = fill_at(dr, cx, cy)
                    if f is not None and sum(f) == 0:
                        continue          # angka tersembunyi (teks hitam di sel hitam)
                    k = max(i for i in range(n) if edges[i] <= cx)
                    row["load"][classes[k]] = int(t)
                    if red:
                        row["merah"] = True
                else:
                    row["span"] = (row["span"] + " " + t).strip()
            elif X_CLS1 <= cx < X_WALI:
                row["wali"] = t
            elif cx >= X_WALI:
                row["ket"] = t
                row["ket_red"] = red
        for j in range(n):
            if classes[j] in row["load"]:
                continue
            cxm = (edges[j] + edges[j + 1]) / 2
            f = fill_at(dr, cxm, yc)
            if (f is None or sum(f) > 2.9) and not row["span"] and i not in (0, 1, 3, 23, 28):
                row["load"][classes[j]] = 0     # sel putih kosong
        row["size"] = next((round(s["size"], 1) for s, d in sp
                            if X_BIDANG <= (s["bbox"][0] + s["bbox"][2]) / 2 < X_BBT
                            and y0 + 1 <= (s["bbox"][1] + s["bbox"][3]) / 2 <= y1 - 1), 7.8)
        row["kode_fill"] = fill_at(dr, 188, yc)
        row["bidang_fill"] = fill_at(dr, 215, y0 + 2)
        row["name_fill"] = fill_at(dr, 100, y0 + 2)
        rows.append(row)
    return classes, rows


def parse_names(page):
    """Nama guru per kelompok baris (sel nama bisa digabung beberapa baris)."""
    sp = spans(page)
    names = []
    idx = 0
    for n in TEACHER_ROWS:
        y0 = ROW0 + idx * ROWH
        y1 = y0 + n * ROWH
        parts = [s for s, d in sp
                 if 66 <= s["bbox"][0] < 170 and d[0] > 0.5
                 and y0 + 1 <= (s["bbox"][1] + s["bbox"][3]) / 2 <= y1 - 1]
        parts.sort(key=lambda s: (round(s["bbox"][1]), s["bbox"][0]))
        names.append(parts)
        idx += n
    return names


def parse_jadwal(page, kodes):
    """Baca isi sel jadwal dari hal. 2 -> {hari: {id_blok: {idx_kelas: [kode]}}}"""
    sp = spans(page)
    top = sorted([s["bbox"] for s, d in sp
                  if abs(d[1] + 1) < 0.01 and 50 < s["bbox"][1] < 56
                  and s["font"].startswith("Tahoma")], key=lambda b: b[0])
    bot = sorted([s["bbox"] for s, d in sp
                  if abs(d[1] + 1) < 0.01 and 235 < s["bbox"][1] < 240
                  and s["font"].startswith("Tahoma")], key=lambda b: b[0])
    assert len(top) == 42 and len(bot) == 28, (len(top), len(bot))
    centers = {"top": [(b[0] + b[2]) / 2 for b in top],
               "bot": [(b[0] + b[2]) / 2 for b in bot]}
    top_days = ["Selasa", "Rabu", "Kamis"]
    bot_days = ["Senin", "Jumat"]
    blocks_top = {"B1": (76.3, 100.7), "B2": (100.7, 125.1), "B3": (137.4, 161.8),
                  "B4": (174.0, 198.4), "B5": (198.4, 222.8)}
    blocks_bot = {"B1": (259.4, 283.8), "B2": (283.8, 308.2), "B3": (320.4, 344.8),
                  "B4": (357.0, 381.4)}
    res = {}
    for s, d in sp:
        if d[0] < 0.5 or s["font"].startswith("Calibri") or s["color"] == 0xFF0000:
            continue
        bx = s["bbox"]
        cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2
        if cx < 57:
            continue
        for grp, blocks, days, name in ((centers["top"], blocks_top, top_days, "top"),
                                        (centers["bot"], blocks_bot, bot_days, "bot")):
            hit = [k for k, (a, b) in blocks.items() if a <= cy < b]
            if not hit or (name == "top" and cy < 76.3) or (name == "bot" and cy < 259.4):
                continue
            if name == "bot" and cx > 640:
                continue
            j = min(range(len(grp)), key=lambda i: abs(grp[i] - (cx - 4)))
            hari, kls = days[j // 14], j % 14
            text = s["text"].strip()
            a, b = blocks[hit[0]]
            half = 0 if cy < (a + b) / 2 else 1
            slot = res.setdefault(hari, {}).setdefault(hit[0], {}).setdefault(kls, [None, None])
            slot[half] = text
    return res


def hexcol(c):
    return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in c)


def build(pdf):
    from jadwal import model as M
    doc = pymupdf.open(pdf)
    classes, rows = parse_beban(doc[0])
    names = parse_names(doc[0])
    pr = M.Proyek()
    for c in classes:
        pr.kelas.append(M.Kelas(pr.new_id("c"), c))
    cid = {k.nama: k.id for k in pr.kelas}
    # guru
    row_i = 0
    gid_of_row = {}
    for gi, n in enumerate(TEACHER_ROWS):
        parts = names[gi]
        # nama utama = teks pertama kelompok (baris kedua milik Lina berbeda)
        nm = " ".join(x["text"].strip() for x in parts if x["text"].strip())
        g = M.Guru(pr.new_id("g"), nm)
        pr.guru.append(g)
        for r in range(n):
            gid_of_row[row_i + r] = g.id
        row_i += n
    # nama Lina: dua baris berbeda -> satu guru + nama_tampil
    lina = pr.guru[0]
    lina.nama = "Dra.Hj.LINA NURHASANAH"
    lina.fill_no = "#00B0F0"
    pr.guru[1].fill_no = "#19D360"
    pr.guru[1].fill_nama = "#FFFF00"
    pr.guru[2].fill_no = "#FABF8F"
    for g in pr.guru:
        g.nama = " ".join(g.nama.split())
    lina.nama = "Dra.Hj.LINA NURHASANAH"
    # penugasan
    for r in rows:
        i = r["i"]
        fill = r["kode_fill"]
        warna = hexcol(fill) if fill else "#FFFFFF"
        p = M.Penugasan(pr.new_id("a"), gid_of_row[i], kode=r["kode"],
                        mapel=r["bidang"], warna=warna, bbt=r["bbt"])
        p.beban = {cid[k]: v for k, v in r["load"].items()}
        p.merah = r["merah"]
        if r["ket"].isdigit() and int(r["ket"]) != sum(r["load"].values()) and i != 1:
            p.ket_manual = int(r["ket"])
        p.ket_merah = r["ket_red"]
        p.keterangan = r["span"]
        if i == 3:
            p.ket_dari, p.ket_sampai, p.ket_geser = 0, 13, 59.3
        elif i == 23:
            p.ket_dari, p.ket_sampai, p.ket_geser = 3, 8, 2.1
        elif i == 28:
            p.ket_dari, p.ket_sampai, p.ket_geser = 3, 11, 2.1
        if r["size"] != 7.8:
            p.ukuran_mapel = r["size"]
        if i == 0:
            p.warna, p.fill_baris, p.nama_tampil = "#FFFF00", "#FFFF00", "Dra. Hj. LINA NURHASANAH"
        if i in (1, 3, 23, 28):
            p.fill_baris = "#92CDDC"
            if i != 1:
                p.warna = "#92CDDC"
        if i == 1:
            p.warna, p.ket_manual = "#00B0F0", 24   # warna di jadwal; baris tetap biru muda
        if i == 2:
            p.fill_mapel = "#19D360"
        if i == 3 and False:
            pass
        pr.penugasan.append(p)
    # BBT yang digabung vertikal (lihat PDF): Matematika 5/6 dan PJOK 27
    pr.penugasan[6].bbt, pr.penugasan[7].bbt, pr.penugasan[7].bbt_gabung = 4, 4, True
    pr.penugasan[29].bbt, pr.penugasan[30].bbt, pr.penugasan[30].bbt_gabung = 2, 2, True
    # wali kelas
    for r in rows:
        if r["wali"] in cid:
            pr.kelas_by_id(cid[r["wali"]]).wali = gid_of_row[r["i"]]
    # logo & ttd
    import base64 as b64
    for im in doc[0].get_images():
        data = doc.extract_image(im[0])
        if data["width"] == 1000:
            pr.meta.kop_png = b64.b64encode(data["image"]).decode()
        else:
            pr.meta.ttd_png = b64.b64encode(data["image"]).decode()
    # jadwal
    kodes = {p.kode.upper() for p in pr.penugasan if p.kode}
    raw = parse_jadwal(doc[1], kodes)
    for hari, bl in raw.items():
        valid = {r["id"] for r in pr.blok_list(hari)}
        for blok, cells in bl.items():
            if blok not in valid:
                continue
            for k, (ta, tb) in cells.items():
                ta = ta if ta is not None else tb
                tb = tb if tb is not None else ta
                pr.set_cell(hari, blok, pr.kelas[k].id, M.parse_cell(ta, kodes),
                            M.parse_cell(tb, kodes))
    return pr


def main(pdf, out):
    from jadwal import model as M
    pr = build(pdf)
    if out:
        M.save(pr, out, backups=0)
        print("tersimpan:", out)
    for hari in M.HARI:
        n = sum(len(v) for v in pr.jadwal.get(hari, {}).values())
        print(hari, "sel terisi:", n)


if __name__ == "__main__":
    sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
