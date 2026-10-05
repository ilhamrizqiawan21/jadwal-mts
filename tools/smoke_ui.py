"""Uji asap UI: buka aplikasi dengan contoh, ambil tangkapan layar."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ctypes
try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception: pass
from jadwal import model as M
from jadwal.app import App
from jadwal.store import Store
from PIL import ImageGrab

p = M.load("data/contoh-ganjil-2025-2026.jadwal")
app = App(Store(p, None))
app.geometry("1400x800+0+0")
app.update(); app.update_idletasks()
def shot(name):
    app.update(); time.sleep(0.4); app.update()
    x, y = app.winfo_rootx(), app.winfo_rooty()
    ImageGrab.grab((x, y, x + app.winfo_width(), y + app.winfo_height())).save(f"ref/ui_{name}.png")
app.after(300, lambda: None)
for _ in range(10):
    app.update(); time.sleep(0.1)
shot("jadwal")
app.gv.v_mode.set("hari"); app.gv._mode_changed(); shot("hari")
app.gv.v_mode.set("cetak"); app.gv._mode_changed()
k = ("Selasa", "B1", p.kelas[0].id)
app.gv.select(k)
shot("pilih")
app.nb.select(1); shot("beban")
app.nb.select(2); shot("guru")
app.nb.select(3); shot("kelas")
app.nb.select(4); shot("set")
app.destroy()
print("ok")
