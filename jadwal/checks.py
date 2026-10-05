"""Pengecekan jadwal: bentrok guru, jam yang diminta kosong, kode asing, beban JP.

Dijalankan ulang setiap kali sel berubah, supaya operator langsung diberi tahu
(sebelumnya baru ketahuan setelah jadwal diterbitkan).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .model import HARI, Proyek

Sel = Tuple[str, str, str]          # (hari, id_blok, id_kelas)

ERROR, WARN, INFO = "error", "warn", "info"


@dataclass
class Masalah:
    jenis: str                      # bentrok | tidak_bisa | kode_asing | beban_lebih |
    #                                 beban_kurang | kode_ganda
    tingkat: str
    pesan: str
    sel: List[Sel] = field(default_factory=list)
    guru: str = ""


@dataclass
class Hasil:
    masalah: List[Masalah] = field(default_factory=list)
    per_sel: Dict[Sel, List[Masalah]] = field(default_factory=dict)
    terpasang: Dict[Tuple[str, str], int] = field(default_factory=dict)  # (kode,kelas)->JP

    def jumlah(self, tingkat: str) -> int:
        return sum(1 for m in self.masalah if m.tingkat == tingkat)

    def ada_error(self) -> bool:
        return self.jumlah(ERROR) > 0


def label_waktu(p: Proyek, hari: str, blok_id: str, half: int | None = None) -> str:
    for r in p.hari[hari]["baris"]:
        if r["t"] == "blok" and r["id"] == blok_id:
            jam = r["jam"]
            if half is not None and half < len(jam):
                return f"{hari} jam ke-{jam[half]}"
            return f"{hari} jam ke-{'-'.join(str(j) for j in jam)}"
    return f"{hari} {blok_id}"


def periksa(p: Proyek) -> Hasil:
    h = Hasil()
    by_kode = p.penugasan_by_kode()
    nama_kelas = {k.id: k.nama for k in p.kelas}
    guru_nama = {g.id: g.nama for g in p.guru}

    def tambah(m: Masalah):
        h.masalah.append(m)
        for s in m.sel:
            h.per_sel.setdefault(s, []).append(m)

    # kode ganda (dua baris beban memakai kode yang sama)
    seen = defaultdict(list)
    for a in p.penugasan:
        if a.kode:
            seen[a.kode.upper()].append(a)
    for kode, lst in seen.items():
        gids = {a.guru for a in lst}
        if len(lst) > 1 and len(gids) > 1:
            names = ", ".join(guru_nama.get(g, "?") for g in sorted(gids))
            tambah(Masalah("kode_ganda", WARN,
                           f"Kode {kode} dipakai oleh lebih dari satu guru ({names}); "
                           f"pengecekan memakai guru pertama.", guru=lst[0].guru))

    # kode yang dipegang >1 guru (mis. PJOK putra/putri): kapasitas = jumlah pemegang
    holders = {k: {a.guru for a in lst} for k, lst in seen.items()}
    kapasitas: Dict[str, int] = {}

    # kumpulkan pemakaian guru per slot JP
    pakai: Dict[Tuple[str, str, int, str], List[Tuple[str, str]]] = defaultdict(list)
    cnt: Dict[Tuple[str, str], int] = defaultdict(int)
    cells_of: Dict[Tuple[str, str], List[Sel]] = defaultdict(list)
    kelas_ids = {k.id for k in p.kelas}
    urut_kelas = {k.id: i for i, k in enumerate(p.kelas)}
    for hari in HARI:
        for blok_id, row in p.jadwal.get(hari, {}).items():
            for kid, jp in row.items():
                if kid not in kelas_ids:
                    continue
                sel = (hari, blok_id, kid)
                for half in (0, 1):
                    for kode in jp[half]:
                        a = by_kode.get(kode.upper())
                        if a is None:
                            continue
                        pemegang = holders.get(kode.upper(), {a.guru})
                        gkey = a.guru if len(pemegang) == 1 else "kode:" + kode.upper()
                        kapasitas[gkey] = len(pemegang)
                        pakai[(hari, blok_id, half, gkey)].append((kid, kode))
                        cnt[(kode.upper(), kid)] += 1
                        if sel not in cells_of[(kode.upper(), kid)]:
                            cells_of[(kode.upper(), kid)].append(sel)
                known = {c.upper() for c in jp[0] + jp[1]}
                for kode in sorted(known):
                    if kode not in by_kode:
                        tambah(Masalah(
                            "kode_asing", ERROR,
                            f"Kode \"{kode}\" tidak ada di Beban Mengajar "
                            f"({label_waktu(p, hari, blok_id)}, kelas {nama_kelas[kid]}).",
                            [sel]))
    h.terpasang = dict(cnt)

    # bentrok: guru yang sama di dua kelas pada JP yang sama
    done = set()
    for (hari, blok_id, half, gid), lst in pakai.items():
        kelas_unik = sorted({k for k, _ in lst}, key=urut_kelas.__getitem__)
        if len(kelas_unik) > kapasitas.get(gid, 1):
            key = (hari, blok_id, gid, tuple(kelas_unik))
            if key in done:
                continue
            done.add(key)
            kn = " dan ".join(nama_kelas[k] for k in kelas_unik)
            kodes = sorted({c for _, c in lst})
            tambah(Masalah(
                "bentrok", ERROR,
                f"BENTROK: {guru_nama.get(gid, 'kode ' + gid[5:] + ' (dipegang beberapa guru)')} "
                f"(kode {', '.join(kodes)}) mengajar di "
                f"{kn} sekaligus pada {label_waktu(p, hari, blok_id, half)}.",
                [(hari, blok_id, k) for k in kelas_unik], "" if gid.startswith("kode:") else gid))

    # jam yang diminta kosong oleh guru (mengajar di tempat lain)
    for hari, per_blok in ((hh, p.jadwal.get(hh, {})) for hh in HARI):
        for blok_id, row in per_blok.items():
            for kid, jp in row.items():
                if kid not in kelas_ids:
                    continue
                gids = set()
                for kode in jp[0] + jp[1]:
                    a = by_kode.get(kode.upper())
                    if a:
                        gids.add((a.guru, kode.upper()))
                for gid, kode in sorted(gids):
                    g = p.guru_by_id(gid)
                    if g and blok_id in g.tidak_bisa.get(hari, []):
                        tambah(Masalah(
                            "tidak_bisa", ERROR,
                            f"{g.nama} meminta jam ini kosong ({label_waktu(p, hari, blok_id)}) "
                            f"tetapi ditempatkan di kelas {nama_kelas[kid]} (kode {kode}).",
                            [(hari, blok_id, kid)], gid))

    # beban JP per kode per kelas (hanya untuk kode yang punya beban per kelas)
    for a in p.penugasan:
        if not a.kode or not a.beban:
            continue
        if by_kode.get(a.kode.upper()) is not a:
            continue
        sama = [x for x in seen[a.kode.upper()] if x.beban]
        for k in p.kelas:
            target = max(x.beban.get(k.id, 0) for x in sama)
            ada = cnt.get((a.kode.upper(), k.id), 0)
            if ada == target:
                continue
            g = guru_nama.get(a.guru, "?")
            if ada > target:
                tambah(Masalah(
                    "beban_lebih", ERROR,
                    f"Kelebihan jam: kode {a.kode} ({g}) di {k.nama} terpasang {ada} JP, "
                    f"bebannya {target} JP.",
                    cells_of.get((a.kode.upper(), k.id), []), a.guru))
            else:
                tambah(Masalah(
                    "beban_kurang", INFO,
                    f"Belum lengkap: kode {a.kode} ({g}) di {k.nama} baru {ada} dari "
                    f"{target} JP.", [], a.guru))
    return h


def preview(p: Proyek, hari: str, blok_id: str, kid: str, jp) -> List[str]:
    """Peringatan langsung saat operator mengetik (sebelum sel disimpan)."""
    by_kode = p.penugasan_by_kode()
    nama_kelas = {k.id: k.nama for k in p.kelas}
    out: List[str] = []
    row = p.jadwal.get(hari, {}).get(blok_id, {})
    seen = set()
    for half in (0, 1):
        for kode in jp[half]:
            a = by_kode.get(kode.upper())
            if not a:
                continue
            g = p.guru_by_id(a.guru)
            gname = g.nama if g else "?"
            for k2, other in row.items():
                if k2 == kid or (a.guru, k2) in seen:
                    continue
                if any(by_kode.get(c.upper()) and by_kode[c.upper()].guru == a.guru for c in other[half]):
                    seen.add((a.guru, k2))
                    out.append(f"BENTROK: {gname} sudah mengajar di {nama_kelas.get(k2, '?')} "
                               f"pada {label_waktu(p, hari, blok_id)}")
            if g and blok_id in g.tidak_bisa.get(hari, []):
                msg = f"{gname} meminta jam ini kosong"
                if msg not in out:
                    out.append(msg)
    return out
