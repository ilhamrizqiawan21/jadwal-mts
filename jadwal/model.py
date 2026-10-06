"""Model data jadwal: kelas, guru, penugasan (kode), struktur jam, dan isi jadwal.

Semua yang bisa berubah antar semester (kelas, guru, mapel, penugasan guru ke
kode/mapel, jam) adalah DATA di berkas proyek, bukan konstanta di program.
"""
from __future__ import annotations

import copy
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field, asdict, fields
from typing import Dict, List, Optional

FORMAT_VERSION = 1
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"]


# ----------------------------------------------------------------- struktur jam
def _blok(bid, jam, waktu):
    return {"t": "blok", "id": bid, "jam": jam, "waktu": waktu}


def _jeda(label, waktu):
    return {"t": "jeda", "label": label, "waktu": waktu}


def _info(label, waktu, warna=None):
    return {"t": "info", "label": label, "waktu": waktu, "warna": warna}


def _tutup(jam, waktu, label=""):
    return {"t": "tutup", "jam": jam, "waktu": waktu, "label": label}


def default_hari() -> Dict[str, dict]:
    """Struktur jam KBM bawaan. Senin–Rabu 07.00–14.00, Kamis 07.00–15.00,
    Jumat 07.00–10.45 (JP 40 menit, Jumat 35 menit; ishoma/istirahat menyerap selisih).

    t = jenis baris: info (Tadarus/Upacara), blok (1 mapel = 2 JP), jeda
    (istirahat/ishoma), tutup (jam tidak dipakai, dicetak hitam).
    """
    def hari_biasa(kamis=False):
        rows = [
            _info("TADARUS AL-QUR'AN", "06.30-07.00"),
            _blok("B1", [1, 2], ["07.00-07.40", "07.40-08.20"]),
            _blok("B2", [3, 4], ["08.20-09.00", "09.00-09.40"]),
            _jeda("ISTIRAHAT", "09.40 - 10.00"),
            _blok("B3", [5, 6], ["10.00-10.40", "10.40-11.20"]),
            _jeda("", "11.20-12.40"),
            _blok("B4", [7, 8], ["12.40-13.20", "13.20-14.00"]),
        ]
        if kamis:
            rows.append(_blok("B5", [9, 10], ["14.00-14.30", "14.30-15.00"]))
        else:
            rows.append(_tutup([9, 10], ["14.00-14.30", "14.30-15.00"]))
        return rows

    senin = [
        _info("UPACARA", "06.30-07.00", "#CCCC00"),
        _blok("B1", [1, 2], ["07.20-08.00", "08.00-08.40"]),
        _blok("B2", [3, 4], ["08.40-09.20", "09.20-10.00"]),
        _jeda("ISTIRAHAT", "10.00-10.20"),
        _blok("B3", [5, 6], ["10.20-11.00", "11.00-11.40"]),
        _jeda("", "11.40-12.40"),
        _blok("B4", [7, 8], ["12.40-13.20", "13.20-14.00"]),
    ]
    jumat = [
        _info("TADARUS AL-QUR'AN", "06.30-07.00", "#00B050"),
        _blok("B1", [1, 2], ["07.00-07.35", "07.35-08.10"]),
        _blok("B2", [3, 4], ["08.10-08.45", "08.45-09.20"]),
        _jeda("ISTIRAHAT", "09.20-09.35"),
        _blok("B3", [5, 6], ["09.35-10.10", "10.10-10.45"]),
        _tutup([], [], "SHOLAT JUM'AT"),
    ]
    return {
        "Senin": {"baris": senin},
        "Selasa": {"baris": hari_biasa()},
        "Rabu": {"baris": hari_biasa()},
        "Kamis": {"baris": hari_biasa(kamis=True)},
        "Jumat": {"baris": jumat},
    }


def _buat(cls, d: dict):
    """Buat dataclass dari dict; field yang tidak dikenal (mis. dari versi aplikasi
    lain dengan format sama) diabaikan, bukan membuat berkas gagal dibuka."""
    dikenal = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in d.items() if k in dikenal})


# --------------------------------------------------------------------- entitas
@dataclass
class Kelas:
    id: str
    nama: str
    wali: Optional[str] = None          # id guru


@dataclass
class Guru:
    id: str
    nama: str
    ket: str = ""                        # catatan bebas (mis. "Cuti Melahirkan")
    # permintaan jam: {hari: [id_blok,...]} blok yang TIDAK bisa diisi guru ini
    tidak_bisa: Dict[str, List[str]] = field(default_factory=dict)
    fill_no: Optional[str] = None        # warna sel NO pada cetakan hal. 1
    fill_nama: Optional[str] = None      # warna sel nama pada cetakan hal. 1


@dataclass
class Penugasan:
    """Satu baris pada Daftar Beban Mengajar: guru + kode + mapel + JP per kelas.

    Kode (mis. 4A, 4B) menandai satu guru yang mengampu lebih dari satu mapel.
    Penugasan guru ke mapel TIDAK dipatenkan: bebas diubah tiap semester.
    """
    id: str
    guru: str                            # id guru
    kode: str = ""
    mapel: str = ""
    warna: str = "#FFFFFF"
    bbt: Optional[int] = None            # kolom BBT JAM
    bbt_gabung: bool = False             # BBT digabung dengan baris di atasnya
    # id kelas -> JP/minggu. Kelas tak tercantum = sel hitam (tidak mengajar);
    # nilai 0 = sel putih kosong (seperti pada cetakan sekolah).
    beban: Dict[str, int] = field(default_factory=dict)
    merah: bool = False                  # angka dicetak merah (tambahan/insidental)
    ket_merah: bool = False              # total JP kolom KET dicetak merah
    nama_tampil: str = ""                # bila diisi: nama di baris ini dicetak sendiri
    keterangan: str = ""                 # teks melintang di kolom kelas ("CUTI ...")
    ket_dari: Optional[int] = None       # kolom kelas pertama sel gabungan keterangan
    ket_sampai: Optional[int] = None     # kolom kelas terakhir (inklusif)
    ket_geser: Optional[float] = None    # jarak teks dari tepi kiri sel gabungan (pt)
    fill_baris: Optional[str] = None     # warna seluruh baris (mis. cuti/yayasan)
    fill_mapel: Optional[str] = None
    ket_manual: Optional[int] = None     # menimpa total JP di kolom KET
    ukuran_mapel: Optional[float] = None  # ukuran huruf kolom bidang studi


@dataclass
class Meta:
    """Identitas & teks cetakan. Semua isian bebas diubah operator; bawaannya kosong
    (data sekolah tertentu hanya ada di berkas proyek, bukan di program)."""
    sekolah: str = ""
    semester: str = "GANJIL"
    tahun: str = ""
    judul_beban: str = ""
    judul_beban2: str = ""
    jadwal_judul: List[str] = field(default_factory=lambda: ["", "", ""])
    beban_ttd: Dict[str, str] = field(default_factory=lambda: {
        "tempat_tanggal": "", "jabatan": "", "nama": "", "nip": ""})
    jadwal_ttd: Dict[str, str] = field(default_factory=lambda: {
        "tempat_tanggal": "", "jabatan": "", "nama": "", "nip": ""})
    kop_png: str = ""                    # base64 gambar kop (JPEG/PNG)
    ttd_png: str = ""                    # base64 gambar tanda tangan


@dataclass
class Proyek:
    meta: Meta = field(default_factory=Meta)
    kelas: List[Kelas] = field(default_factory=list)
    guru: List[Guru] = field(default_factory=list)
    penugasan: List[Penugasan] = field(default_factory=list)
    hari: Dict[str, dict] = field(default_factory=default_hari)
    # jadwal[hari][id_blok][id_kelas] = [kode_jp1, kode_jp2], masing-masing daftar
    # kode. Biasanya kedua JP sama (satu mapel = 2 JP). Lebih dari satu kode pada
    # satu JP = kelas dibagi dua kelompok siswa pada jam yang sama.
    jadwal: Dict[str, Dict[str, Dict[str, List[List[str]]]]] = field(default_factory=dict)
    seq: int = 0

    # ------------------------------------------------------------ id & indeks
    def new_id(self, prefix: str) -> str:
        self.seq += 1
        return f"{prefix}{self.seq}"

    def kelas_by_id(self, kid):
        return next((k for k in self.kelas if k.id == kid), None)

    def guru_by_id(self, gid):
        return next((g for g in self.guru if g.id == gid), None)

    def penugasan_by_kode(self) -> Dict[str, Penugasan]:
        out = {}
        for p in self.penugasan:
            if p.kode and p.kode.upper() not in out:
                out[p.kode.upper()] = p
        return out

    def blok_list(self, hari: str):
        return [r for r in self.hari[hari]["baris"] if r["t"] == "blok"]

    # ------------------------------------------------------------- isi jadwal
    def get_cell(self, hari, blok, kelas) -> List[List[str]]:
        """[kode_jp1, kode_jp2]; kosong -> [[], []]."""
        v = self.jadwal.get(hari, {}).get(blok, {}).get(kelas)
        if not v:
            return [[], []]
        return [list(v[0]), list(v[1])]

    def set_cell(self, hari, blok, kelas, jp1: List[str], jp2: Optional[List[str]] = None):
        jp2 = list(jp1) if jp2 is None else list(jp2)
        d = self.jadwal.setdefault(hari, {}).setdefault(blok, {})
        if jp1 or jp2:
            d[kelas] = [list(jp1), jp2]
        else:
            d.pop(kelas, None)

    # --------------------------------------------------------------- simpan
    def to_dict(self) -> dict:
        d = asdict(self)
        d["format"] = FORMAT_VERSION
        return d

    @staticmethod
    def from_dict(d: dict) -> "Proyek":
        versi = d.get("format", 1)
        if not isinstance(versi, int) or versi > FORMAT_VERSION:
            raise ValueError(
                f"Berkas dibuat oleh versi aplikasi yang lebih baru (format {versi}, "
                f"aplikasi ini mendukung sampai {FORMAT_VERSION}). Perbarui aplikasi.")
        p = Proyek()
        p.meta = _buat(Meta, {**asdict(Meta()), **d.get("meta", {})})
        p.kelas = [_buat(Kelas, k) for k in d.get("kelas", [])]
        p.guru = [_buat(Guru, g) for g in d.get("guru", [])]
        p.penugasan = [_buat(Penugasan, x) for x in d.get("penugasan", [])]
        p.hari = d.get("hari") or default_hari()
        p.jadwal = d.get("jadwal", {})
        p.seq = d.get("seq", 0)
        return p

    def clone(self) -> "Proyek":
        return Proyek.from_dict(copy.deepcopy(self.to_dict()))


# --------------------------------------------------------------- penguraian sel
def parse_cell(teks: str, kodes: set) -> List[str]:
    """Ubah teks ketikan operator menjadi daftar kode.

    Contoh: "26A" -> ["26A"]; "24A/6" -> ["24A","6"]; "3/15A" -> ["3/15A"]
    bila "3/15A" memang sebuah kode. Kode tak dikenal tetap disimpan apa adanya
    (ditandai merah di tampilan) supaya operator tidak kehilangan ketikan.
    """
    t = re.sub(r"\s+", "", (teks or "").upper())
    if not t:
        return []
    if t in kodes:
        return [t]
    tokens = [x for x in re.split(r"[/,+;]", t) if x]
    out, i = [], 0
    while i < len(tokens):
        for j in range(len(tokens), i, -1):
            cand = "/".join(tokens[i:j])
            if cand in kodes:
                out.append(cand)
                i = j
                break
        else:
            out.append(tokens[i])
            i += 1
    return out


def parse_cell_jp(teks: str, kodes: set) -> List[List[str]]:
    """Teks sel -> [jp1, jp2]. Pemisah '|' memisahkan JP pertama dan kedua."""
    parts = (teks or "").split("|")
    a = parse_cell(parts[0], kodes)
    b = parse_cell(parts[1], kodes) if len(parts) > 1 else list(a)
    return [a, b]


def cell_text(kodes: List[str]) -> str:
    return "/".join(kodes)


def cell_text_jp(jp: List[List[str]]) -> str:
    a, b = cell_text(jp[0]), cell_text(jp[1])
    return a if a == b else f"{a}|{b}"


# ----------------------------------------------------------- baca/tulis berkas
def save(p: Proyek, path: str, backups: int = 30):
    """Simpan atomik + simpan cadangan bergilir di folder 'cadangan'."""
    data = json.dumps(p.to_dict(), ensure_ascii=False, indent=1)
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        if os.path.exists(path) and backups:
            bdir = os.path.join(folder, "cadangan")
            os.makedirs(bdir, exist_ok=True)
            base = os.path.splitext(os.path.basename(path))[0]
            stamp = time.strftime("%Y%m%d-%H%M%S")
            try:
                with open(path, "rb") as src, \
                        open(os.path.join(bdir, f"{base}-{stamp}.jadwal"), "wb") as dst:
                    dst.write(src.read())
                pola = re.compile(re.escape(base) + r"-\d{8}-\d{6}\.jadwal")
                olds = sorted(x for x in os.listdir(bdir) if pola.fullmatch(x))
                for x in olds[:-backups]:
                    os.remove(os.path.join(bdir, x))
            except OSError:
                pass
        os.replace(tmp, path)
    except BaseException:
        # jangan tinggalkan berkas .tmp bila penulisan/penggantian gagal
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def load(path: str) -> Proyek:
    with open(path, "r", encoding="utf-8") as f:
        return Proyek.from_dict(json.load(f))
