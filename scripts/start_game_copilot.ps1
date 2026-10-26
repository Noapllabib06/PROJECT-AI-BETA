# PowerShell One-Click Runner for Raphael AI Gaming Copilot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "    « 智恵之王 » RAPHAEL AI GAMING COPILOT (TENSURA)     " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "[*] Mode: Pure Voice Spotter (Radio Engineer Helm Asli - 0% Gangguan Layar)" -ForegroundColor Green
Write-Host "[*] Memulai Raphael Copilot untuk Assetto Corsa Competizione & Minecraft..." -ForegroundColor Green

$venvPython = ".\venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[!] Virtual environment tidak ditemukan di .\venv. Mencoba python default..." -ForegroundColor Yellow
    $venvPython = "python"
}

try {
    & $venvPython scripts/start_game_copilot.py $args
} finally {
    Write-Host "[*] Raphael Copilot selesai." -ForegroundColor Cyan
}
