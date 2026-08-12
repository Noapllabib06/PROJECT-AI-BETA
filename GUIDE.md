# JARVIS AI - Panduan Pengguna

Dokumentasi arsitektur dan panduan teknis operasional.

## Arsitektur Sistem

Sistem beroperasi melalui dua komponen utama:
- **Frontend & Agent Engine (Node.js/Electron):** Menangani antarmuka, manajemen proses, dan routing logika LLM.
- **Memory Server (Python FastAPI):** Menangani Retrieval-Augmented Generation (RAG) untuk penyimpanan dan pencarian vektor.

### Struktur Direktori

```text
project-root/
├── src/
│   ├── engine/        # Logika Agent, Prompt, dan Context Manager
│   ├── gui/           # Antarmuka pengguna (HTML/CSS/JS)
│   ├── tools/         # Modul aksi eksternal (Web, Sistem, File)
│   ├── utils/         # Modul utilitas (Logger, Credential Manager)
│   ├── main.js        # Entry point Electron
│   └── preload.js     # Script isolasi IPC
├── local_memory.py    # Server FastAPI (RAG)
├── package.json       # Konfigurasi dependensi Node.js
├── text_metadata.pkl  # Penyimpanan data teks
└── test_rag.py        # Skrip pengujian memori
```

## Persyaratan Lingkungan

- Node.js LTS
- Python 3.10+
- Ollama aktif dengan model `qwen2.5:7b`

### Setup Dependensi Python Khusus RAG

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install numpy sentence-transformers turbovec fastapi uvicorn pydantic
```

## Prosedur Eksekusi

**Metode Simultan:**
Jalankan perintah berikut di root direktori untuk memulai server Python dan Electron secara bersamaan:
```bash
npm run dev
```

**Metode Terpisah:**
1. Server Memori (Terminal 1): `.\.venv\Scripts\python.exe local_memory.py`
2. Aplikasi Utama (Terminal 2): `npm start`

## Daftar Modul Fungsional

- **Web & Media:** Pencarian web, ekstraksi data web, otomatisasi browser.
- **Sistem & File:** Manipulasi file lokal (baca/tulis), navigasi direktori.
- **Memori (RAG):** Ekstraksi teks, embedding (`all-MiniLM-L6-v2`), kompresi vektor, dan semantic search.
- **Kredensial:** Manajemen penyimpanan kredensial tersandi secara lokal.

## Pemecahan Masalah

- **Gagal eksekusi `search_knowledge`:** Layanan `local_memory.py` belum berjalan di port 8000.
- **Waktu respon lambat:** Penurunan performa akibat spesifikasi RAM tidak memadai atau beban VRAM.
- **Karakter tidak terbaca/crash:** Terminal tidak mendukung output UTF-8.