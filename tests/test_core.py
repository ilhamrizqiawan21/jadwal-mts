import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from jadwal import model as M, checks as C, export_pdf as E

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "contoh-ganjil-2025-2026.jadwal")


def mini():
    p = M.Proyek()
    for n in ("7A", "7B", "7C"):
        p.kelas.append(M.Kelas(p.new_id("c"), n))
    ga = M.Guru(p.new_id("g"), "Guru A")
    gb = M.Guru(p.new_id("g"), "Guru B")
    p.guru += [ga, gb]
    k = [x.id for x in p.kelas]
    # Guru A memegang dua kode (8A, 8B): satu guru, dua mapel
    p.penugasan += [
        M.Penugasan(p.new_id("a"), ga.id, "8A", "IPA", "#FF0000", beban={k[0]: 2, k[1]: 2}),
        M.Penugasan(p.new_id("a"), ga.id, "8B", "TIK", "#00FF00", beban={k[2]: 2}),
        M.Penugasan(p.new_id("a"), gb.id, "9", "PKN", "#0000FF", beban={k[0]: 2, k[1]: 2, k[2]: 2}),
    ]
    return p, k, ga, gb


def test_parse_cell():
    ks = {"26A", "24A", "6", "3/15A", "3"}
    assert M.parse_cell("26a", ks) == ["26A"]
    assert M.parse_cell("24A/6", ks) == ["24A", "6"]
    assert M.parse_cell("3/15A", ks) == ["3/15A"]
    assert M.parse_cell("3/15A/6", ks) == ["3/15A", "6"]
    assert M.parse_cell("zzz", ks) == ["ZZZ"]
    assert M.parse_cell("", ks) == []
    assert M.parse_cell_jp("13|23", {"13", "23"}) == [["13"], ["23"]]
    assert M.parse_cell_jp("13", {"13"}) == [["13"], ["13"]]


def test_bentrok_satu_guru_dua_kode():
    p, k, ga, gb = mini()
    p.set_cell("Senin", "B1", k[0], ["8A"])
    p.set_cell("Senin", "B1", k[2], ["8B"])      # guru sama, kode beda, kelas beda
    h = C.periksa(p)
    assert any(m.jenis == "bentrok" for m in h.masalah)
    assert ("Senin", "B1", k[0]) in h.per_sel and ("Senin", "B1", k[2]) in h.per_sel


def test_tidak_bentrok_beda_jp():
    p, k, ga, gb = mini()
    p.set_cell("Senin", "B1", k[0], ["8A"], ["9"])
    p.set_cell("Senin", "B1", k[1], ["9"], ["8A"])   # JP berbeda -> tidak bentrok
    h = C.periksa(p)
    assert not any(m.jenis == "bentrok" for m in h.masalah)


def test_jam_diminta_kosong():
    p, k, ga, gb = mini()
    ga.tidak_bisa = {"Selasa": ["B2"]}
    p.set_cell("Selasa", "B2", k[0], ["8A"])
    h = C.periksa(p)
    assert any(m.jenis == "tidak_bisa" for m in h.masalah)


def test_kode_asing_dan_beban():
    p, k, ga, gb = mini()
    p.set_cell("Senin", "B1", k[0], ["XX"])
    assert any(m.jenis == "kode_asing" for m in C.periksa(p).masalah)
    p.set_cell("Senin", "B1", k[0], ["8A"])
    p.set_cell("Senin", "B2", k[0], ["8A"])
    p.set_cell("Selasa", "B1", k[0], ["8A"])       # 6 JP > beban 2 JP
    assert any(m.jenis == "beban_lebih" for m in C.periksa(p).masalah)


def test_kode_ganda_kapasitas():
    p, k, ga, gb = mini()
    gc = M.Guru(p.new_id("g"), "Guru C")
    p.guru.append(gc)
    p.penugasan.append(M.Penugasan(p.new_id("a"), gc.id, "9", "PKN", "#0000FF", beban={k[0]: 2}))
    p.set_cell("Senin", "B1", k[0], ["9"])
    p.set_cell("Senin", "B1", k[1], ["9"])          # dua pemegang kode -> boleh dua kelas
    h = C.periksa(p)
    assert not any(m.jenis == "bentrok" for m in h.masalah)
    assert any(m.jenis == "kode_ganda" for m in h.masalah)
    p.set_cell("Senin", "B1", k[2], ["9"])          # tiga kelas > dua pemegang
    assert any(m.jenis == "bentrok" for m in C.periksa(p).masalah)


def test_preview():
    p, k, ga, gb = mini()
    p.set_cell("Senin", "B1", k[0], ["8A"])
    msgs = C.preview(p, "Senin", "B1", k[1], [["8B"], ["8B"]])
    assert msgs and "BENTROK" in msgs[0]


def test_simpan_muat(tmp_path):
    p = M.load(SAMPLE)
    f = str(tmp_path / "a.jadwal")
    M.save(p, f)
    q = M.load(f)
    assert q.to_dict() == p.to_dict()


def test_contoh_menemukan_bentrok_nyata():
    h = C.periksa(M.load(SAMPLE))
    assert any(m.jenis == "bentrok" and "SHINTA" in m.pesan for m in h.masalah)


def test_ekspor_pdf_variasi(tmp_path):
    pymupdf = pytest.importorskip("pymupdf")
    p = M.load(SAMPLE)
    f = str(tmp_path / "x.pdf")
    E.export_pdf(p, f)
    d = pymupdf.open(f)
    assert len(d) == 2
    assert (round(d[0].rect.width), round(d[0].rect.height)) == (612, 1008)
    assert (round(d[1].rect.width), round(d[1].rect.height)) == (936, 612)
    # kelas ditambah, guru banyak
    p.kelas.append(M.Kelas(p.new_id("c"), "9F"))
    for i in range(30):
        g = M.Guru(p.new_id("g"), f"Guru {i}")
        p.guru.append(g)
        p.penugasan.append(M.Penugasan(p.new_id("a"), g.id, f"X{i}", "MAPEL", "#CCCCCC"))
    E.export_pdf(p, f)
    assert len(pymupdf.open(f)) == 2
    # kelas dikurangi
    p.kelas = p.kelas[:3]
    E.export_pdf(p, f)
    assert len(pymupdf.open(f)) == 2


def test_save_gagal_tidak_meninggalkan_tmp(tmp_path, monkeypatch):
    p, *_ = mini()
    f = str(tmp_path / "x.jadwal")
    monkeypatch.setattr(M.os, "replace", lambda *a: (_ for _ in ()).throw(OSError("terkunci")))
    with pytest.raises(OSError):
        M.save(p, f)
    assert [x.name for x in tmp_path.iterdir()] == []


def test_format_lebih_baru_ditolak():
    d = M.Proyek().to_dict()
    d["format"] = M.FORMAT_VERSION + 1
    with pytest.raises(ValueError):
        M.Proyek.from_dict(d)


def test_edit_error_mengembalikan_data():
    from jadwal.store import Store
    p, k, *_ = mini()
    s = Store(p)
    with pytest.raises(RuntimeError):
        with s.edit() as pp:
            pp.kelas.clear()
            raise RuntimeError("x")
    assert len(s.p.kelas) == 3 and not s.undo_stack and not s.dirty
