"""Potong area (pt) dari PDF asli & hasil, tempel atas-bawah. potong.py hal x0 y0 x1 y1 [skala]"""
import sys, PIL.Image as I
pg, x0, y0, x1, y1 = sys.argv[1], *map(float, sys.argv[2:6])
k = float(sys.argv[6]) if len(sys.argv) > 6 else 4
s = 150 / 72
box = tuple(int(v * s) for v in (x0, y0, x1, y1))
a = I.open(f"ref/orig_p{pg}.png").crop(box); b = I.open(f"ref/hasil_p{pg}.png").crop(box)
a = a.resize((int(a.width * k / 2), int(a.height * k / 2)), I.LANCZOS)
b = b.resize(a.size, I.LANCZOS)
m = I.new("RGB", (a.width, a.height * 2 + 6), "red"); m.paste(a, (0, 0)); m.paste(b, (0, a.height + 6)); m.save("ref/potong.png")
