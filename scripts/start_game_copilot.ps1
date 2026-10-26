# PowerShell One-Click Runner for Raphael AI Gaming Copilot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "    « 智恵之王 » RAPHAEL AI GAMING COPILOT (TENSURA)     " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "[*] Memulai Raphael Copilot untuk Assetto Corsa Competizione & Minecraft..." -ForegroundColor Green

$venvPython = ".\venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "[!] Virtual environment tidak ditemukan di .\venv. Mencoba python default..." -ForegroundColor Yellow
    $venvPython = "python"
}

& $venvPython scripts/start_game_copilot.py $args
