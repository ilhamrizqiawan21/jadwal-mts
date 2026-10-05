"""Ukur kotak tinta (pt) pada daerah tertentu di PDF asli vs hasil. ukur.py hal nama:x0,y0,x1,y1 ..."""
import sys, PIL.Image as I
s = 150 / 72
def bbox(path, x0, y0, x1, y1, thr=110):
    im = I.open(path).convert("L"); w, h = im.size
    px = im.load(); xs = []; ys = []
    for y in range(int((y0 + .4) * s), min(int((y1 - .4) * s), h)):
        for x in range(int((x0 + .4) * s), min(int((x1 - .4) * s), w)):
            if px[x, y] < thr: xs.append(x); ys.append(y)
    return [round(v / s, 1) for v in (min(xs), min(ys), max(xs), max(ys))] if xs else None
pg = sys.argv[1]
for arg in sys.argv[2:]:
    name, r = arg.split(":"); x0, y0, x1, y1 = map(float, r.split(","))
    a = bbox(f"ref/orig_p{pg}.png", x0, y0, x1, y1); b = bbox(f"ref/hasil_p{pg}.png", x0, y0, x1, y1)
    d = [round(q - w, 1) for q, w in zip(b, a)] if a and b else None
    print(f"{name:12s} asli={a} hasil={b} selisih={d}")
