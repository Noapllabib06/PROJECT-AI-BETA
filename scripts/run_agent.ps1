# scripts/run_agent.ps1
# Script peluncur JARVIS AI Agent untuk Windows (PowerShell)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Pastikan working directory berada di root repository
$PROJECT_ROOT = Split-Path -Parent $PSScriptRoot
if ($PROJECT_ROOT -and (Test-Path $PROJECT_ROOT)) {
    Set-Location -Path $PROJECT_ROOT
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         🤖 JARVIS AI Agent - Python Architecture        " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$VENV_PYTHON = Join-Path $PWD "venv\Scripts\python.exe"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Host "[!] Virtual environment tidak ditemukan di .\venv\." -ForegroundColor Yellow
    Write-Host "[*] Membuat virtual environment baru menggunakan Python 3.11..." -ForegroundColor Yellow
    py -3.11 -m venv venv
    if (-not (Test-Path $VENV_PYTHON)) {
        python -m venv venv
    }
    Write-Host "[*] Menginstall dependensi requirements.txt..." -ForegroundColor Yellow
    & (Join-Path $PWD "venv\Scripts\pip.exe") install -r requirements.txt
}

Write-Host "[*] Menjalankan server JARVIS di http://localhost:8000 ..." -ForegroundColor Green
& $VENV_PYTHON -m src.app.main $args
