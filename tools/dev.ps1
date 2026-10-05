# Menjalankan versi pengembangan dari sumber (data & konfigurasi terpisah dari exe operator).
# Pakai:  powershell -File tools\dev.ps1          -> jalankan aplikasi [DEV]
#         powershell -File tools\dev.ps1 -Uji     -> jalankan pytest saja
param([switch]$Uji)
Set-Location (Split-Path $PSScriptRoot)
if ($Uji) { python -m pytest tests -q; exit $LASTEXITCODE }
$env:JADWAL_DEV = "1"
python run.py
