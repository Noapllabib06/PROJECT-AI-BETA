#!/usr/bin/env bash
# scripts/run_agent.sh
# Script peluncur JARVIS AI Agent untuk Linux / macOS

set -e

echo -e "\033[1;36m==========================================================\033[0m"
echo -e "\033[1;36m         🤖 JARVIS AI Agent - Python Architecture        \033[0m"
echo -e "\033[1;36m==========================================================\033[0m"

VENV_PYTHON="./venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo -e "\033[1;33m[!] Virtual environment tidak ditemukan di ./venv/.\033[0m"
    echo -e "\033[1;33m[*] Membuat virtual environment baru...\033[0m"
    python3 -m venv venv
    echo -e "\033[1;33m[*] Menginstall dependensi requirements.txt...\033[0m"
    ./venv/bin/pip install -r requirements.txt
fi

echo -e "\033[1;32m[*] Menjalankan server JARVIS...\033[0m"
$VENV_PYTHON -m src.app.main "$@"
