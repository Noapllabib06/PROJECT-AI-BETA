# JARVIS AI Agent

Lokal Desktop Assistant menggunakan Ollama, Node.js (Electron), dan Python (FastAPI).

## Fitur Utama

- **Chat Lokal:** Ollama (`qwen2.5:7b`).
- **Vision:** Deskripsi gambar menggunakan `llava:7b`.
- **Dynamic Tooling:** Eksekusi alat secara dinamis dan paralel.
- **Memori Jangka Panjang:** Ekstraksi dan penyimpanan fakta (`facts.json`).
- **RAG System:** Pencarian semantik menggunakan FAISS dan `all-MiniLM-L6-v2`.
- **Auto-Compaction:** Peringkasan konteks otomatis.
- **Web & Media:** Pencarian web, scraping, dan interaksi web.

## Kebutuhan Sistem

- RAM Minimal: 16GB
- Node.js v18+
- Python 3.10+
- Ollama terinstal dengan model: `qwen2.5:7b` dan `llava:7b`

## Instalasi dan Eksekusi

```bash
# 1. Kloning repositori
git clone https://github.com/Noapllabib06/Project-AI.git
cd Project-AI

# 2. Instal dependensi Node.js
npm install

# 3. Konfigurasi Python (Untuk fitur RAG)
python -m venv .venv
.venv\Scripts\activate
pip install fastapi uvicorn sentence-transformers faiss-cpu

# 4. Jalankan aplikasi
npm run dev
```

Untuk detail arsitektur dan modul, silakan baca [GUIDE.md](GUIDE.md).
