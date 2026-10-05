# Membangun JadwalPelajaran.exe (satu berkas, tanpa jendela konsol)
Set-Location (Split-Path $PSScriptRoot)
python tools\buat_ikon.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name JadwalPelajaran `
  --icon "img\logo.ico" `
  --add-data "data\contoh-ganjil-2025-2026.jadwal;data" `
  --add-data "img\logo.png;img" `
  --exclude-module numpy --exclude-module pymupdf --exclude-module pytest `
  --exclude-module unittest --exclude-module pydoc `
  run.py
