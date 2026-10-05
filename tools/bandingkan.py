"""Render hasil ekspor & PDF asli ke PNG untuk dibandingkan (alat bantu uji)."""
import os, sys, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
import pymupdf
from jadwal import model as M, export_pdf as E

os.makedirs("ref", exist_ok=True)
asli = r"C:\Users\ilham\Downloads\JADWAL DAN KODE GURU 2025-2026.pdf"
p = M.load("data/contoh-ganjil-2025-2026.jadwal")
E.export_pdf(p, "ref/hasil.pdf")
a, b = pymupdf.open(asli), pymupdf.open("ref/hasil.pdf")
for i in (0, 1):
    a[i].get_pixmap(dpi=150).save(f"ref/orig_p{i+1}.png")
    b[i].get_pixmap(dpi=150).save(f"ref/hasil_p{i+1}.png")
    # selisih piksel (merah = beda)
    import PIL.Image as I, PIL.ImageChops as C
    x, y = I.open(f"ref/orig_p{i+1}.png").convert("RGB"), I.open(f"ref/hasil_p{i+1}.png").convert("RGB")
    d = C.difference(x, y).convert("L").point(lambda v: 255 if v > 60 else 0)
    print("halaman", i + 1, "piksel beda:", sum(1 for v in d.getdata() if v) , "/", d.size[0]*d.size[1])
    d.save(f"ref/selisih_p{i+1}.png")
