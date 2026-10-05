import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from jadwal import model as M
from jadwal.app import App
from jadwal.store import Store
p = M.load("data/contoh-ganjil-2025-2026.jadwal")
app = App(Store(p, None)); app.update()
gv = app.gv
kid = lambda n: next(k.id for k in app.store.p.kelas if k.nama == n)
# kosongkan sel lalu isi dengan kode yang menimbulkan bentrok
before = app.store.hasil.jumlah("error")
gv.select(("Senin", "B2", kid("7A"))); gv.start_edit(initial="1"); gv.editor.insert("end", "2A")
gv.update()
print("petunjuk:", app.hint.cget("text"))
gv._finish_edit(0, 1); app.update()
print("sel:", app.store.p.get_cell("Senin", "B2", kid("7A")), "-> pilih", gv.sel[1], gv.sel[2] == kid("7A"))
# sel 7B sama jam: isi kode guru yang sama (12A di 8D) -> bentrok
gv.select(("Senin", "B2", kid("7B"))); gv.start_edit(initial="12A")
print("petunjuk:", app.hint.cget("text"), "| merah:", app.hint.cget("fg"))
gv._finish_edit(0, 0); app.update()
print("banner:", app.banner.cget("text")[:90])
print("error sebelum/sesudah:", before, app.store.hasil.jumlah("error"))
app.undo(); app.update()
print("setelah undo:", app.store.p.get_cell("Senin", "B2", kid("7B")), app.store.hasil.jumlah("error"))
# ketik 2 kode pecah kelas & beda JP
gv.select(("Rabu", "B3", kid("9E"))); gv.set_cell_text(gv.sel, "24A/6"); print(app.store.p.get_cell("Rabu", "B3", kid("9E")))
gv.set_cell_text(gv.sel, "13|23"); print(app.store.p.get_cell("Rabu", "B3", kid("9E")))
# tambah kelas lalu cek gambar & ekspor
with app.store.edit() as pp: pp.kelas.append(M.Kelas(pp.new_id("c"), "9F"))
app.update(); print("kelas:", len(app.store.p.kelas), "sel grid:", len(gv.cells))
app.destroy(); print("OK")
