@echo off
REM run.bat - Launcher JARVIS AI Agent untuk Windows CMD / Command Prompt
echo ==========================================================
echo          JARVIS AI Agent - Python Architecture
echo ==========================================================

IF NOT EXIST ".\venv\Scripts\python.exe" (
    echo [!] Virtual environment tidak ditemukan di .\venv\
    echo [*] Membuat virtual environment baru menggunakan Python 3.11...
    py -3.11 -m venv venv
    IF NOT EXIST ".\venv\Scripts\python.exe" (
        python -m venv venv
    )
    echo [*] Menginstall dependensi requirements.txt...
    .\venv\Scripts\pip.exe install -r requirements.txt
)

echo [*] Menjalankan server JARVIS di http://localhost:8000 ...
.\venv\Scripts\python.exe -m src.app.main %*
