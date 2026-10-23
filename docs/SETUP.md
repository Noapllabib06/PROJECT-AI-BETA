# 🛠️ Panduan Instalasi & Pengaturan (SETUP) - JARVIS AI Agent v2.0

Dokumen ini menjelaskan langkah-langkah instalasi, konfigurasi, dan eksekusi JARVIS AI Agent dengan arsitektur 100% modular Python.

---

## 📋 Prasyarat Sistem

1. **Python 3.11 (64-bit)**
   - Pastikan Python 3.11 terpasang pada sistem:
     ```bash
     python --version # atau: py -3.11 --version
     ```
2. **Ollama (Local LLM Runtime)**
   - Unduh dan pasang Ollama dari [ollama.com](https://ollama.com/).
   - Unduh model lokal default:
     ```bash
     ollama pull llama3.2:latest
     # atau
     ollama pull qwen2.5:7b
     ```
3. **Tesseract OCR (Opsional untuk Vision/OCR)**
   - Windows: [UB-Mannheim Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
   - Linux: `sudo apt-get install tesseract-ocr tesseract-ocr-ind`

---

## 🚀 Langkah Instalasi Cepat

### 1. Buat Virtual Environment
Gunakan Python 3.11 untuk membuat environment lokal terisolasi:

```powershell
# Windows (PowerShell)
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependensi Python
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Konfigurasi Lingkungan (.env)
Salin berkas contoh konfigurasi:
```bash
cp .env.example .env
```
Sesuaikan parameter jika diperlukan (misalnya `PORT=8000`, API keys cloud opsional).

---

## ▶️ Cara Menjalankan JARVIS

### 1. Menggunakan Script Otomatis
- **Windows (PowerShell):**
  ```powershell
  .\scripts\run_agent.ps1
  ```
- **Linux / macOS:**
  ```bash
  chmod +x scripts/run_agent.sh
  ./scripts/run_agent.sh
  ```

### 2. Menjalankan via Python Langsung
```bash
# Menjalankan Server & Membuka Browser Otomatis
python -m src.app.main

# Menjalankan Server Saja (Headless Mode)
python -m src.app.main --headless --port 8000

# Menjalankan Mode Desktop Window (jika pywebview terpasang)
python -m src.app.main --desktop
```

Akses antarmuka GUI modern di browser Anda pada:
👉 **`http://localhost:8000`**

---

## 🧪 Menjalankan Pengujian (Testing)

Jalankan seluruh rangkaian pengujian unit dan integrasi otomatis:

```bash
# Menjalankan seluruh test suite
pytest tests/ -v

# Menjalankan evaluasi benchmark
python scripts/evaluate.py
```

---

## 🐳 Menjalankan dengan Docker

```bash
# Build dan jalankan container JARVIS beserta Ollama
docker compose up -d

# Periksa status log
docker compose logs -f jarvis-agent
```
