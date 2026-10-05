# Jadwal Pelajaran (Windows)

Aplikasi bantu operator sekolah menyusun jadwal. Hasil ekspor (PDF/Excel) meniru
format "JADWAL DAN KODE GURU" sekolah: hal. 1 Daftar Beban Mengajar, hal. 2 Jadwal.

## Dipakai operator
Jalankan `dist\JadwalPelajaran.exe` (satu berkas, ±45 MB RAM). Berkas data `.jadwal`
disimpan di `Documents\Jadwal Sekolah`, otomatis disimpan tiap menit + cadangan bergilir.

## Pengembang
    pip install reportlab openpyxl pillow pyinstaller pytest
    powershell -File tools\dev.ps1         # jalankan mode [DEV] (data terpisah)
    powershell -File tools\dev.ps1 -Uji    # uji
    python run.py                 # jalankan biasa
    python -m pytest tests -q     # uji
    powershell -File tools\bangun.ps1   # bangun exe

Mode `[DEV]` (`--dev` atau `JADWAL_DEV=1`, hanya dari sumber): berkas di `Documents\Jadwal Sekolah (DEV)`,
konfigurasi di `%APPDATA%\JadwalMTs-dev`, judul jendela diberi `[DEV]`. Exe tidak pernah memakai mode ini.
Bangun exe hanya saat rilis (`tools\bangun.ps1`).

- `jadwal/model.py` data & berkas · `checks.py` bentrok/beban · `export_pdf.py`, `export_xlsx.py` ekspor
- `ui_grid.py` kisi jadwal · `ui_data.py` tab beban/guru/kelas/pengaturan · `app.py` jendela utama
- `tools/extract_seed.py` membaca PDF sekolah menjadi `data/contoh-ganjil-2025-2026.jadwal`
- `tools/bandingkan.py`, `ukur.py`, `petakan_selisih.py`, `potong.py` membandingkan ekspor dengan PDF asli
  (butuh `pymupdf`, `numpy`; hanya untuk pengembangan)
