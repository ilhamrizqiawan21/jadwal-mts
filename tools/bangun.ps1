# Membangun JadwalPelajaran.exe (satu berkas, tanpa jendela konsol)
Set-Location (Split-Path $PSScriptRoot)
python -m PyInstaller --noconfirm --clean --onefile --windowed --name JadwalPelajaran `
  --add-data "data\contoh-ganjil-2025-2026.jadwal;data" `
  --exclude-module numpy --exclude-module pymupdf --exclude-module pytest `
  --exclude-module unittest --exclude-module pydoc `
  run.py
