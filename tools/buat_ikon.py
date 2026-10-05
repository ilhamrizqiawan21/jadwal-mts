"""Membuat img/logo.ico (ikon exe) dari logo PNG. Dipanggil oleh bangun.ps1."""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "img", "logo.png")
OUT = os.path.join(ROOT, "img", "logo.ico")


def main():
    if not os.path.exists(SRC):
        sys.exit(f"Logo tidak ditemukan: {SRC}")
    im = Image.open(SRC).convert("RGBA")
    side = max(im.size)                       # logo tidak persegi: beri bidang transparan agar tidak gepeng
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2), im)
    sq.resize((256, 256), Image.LANCZOS).save(
        OUT, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("ikon dibuat:", OUT)


if __name__ == "__main__":
    main()
