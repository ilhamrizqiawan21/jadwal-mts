"""Cari area dengan selisih terbesar antara hasil dan PDF asli (alat uji)."""
import sys, numpy as np, PIL.Image as I
pg = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
a = np.asarray(I.open(f"ref/orig_p{pg}.png").convert("L")).astype(int)
b = np.asarray(I.open(f"ref/hasil_p{pg}.png").convert("L")).astype(int)
d = (abs(a - b) > 80)
s = 150 / 72
T = int(18 * s)
res = []
for y in range(0, d.shape[0] - T, T):
    for x in range(0, d.shape[1] - T, T):
        v = d[y:y+T, x:x+T].sum()
        if v > 40:
            res.append((v, round(x / s), round(y / s)))
res.sort(reverse=True)
print(len(res), "tile berselisih")
for v, x, y in res[:n]:
    print(f"  x={x:4d} y={y:4d} piksel={v}")
