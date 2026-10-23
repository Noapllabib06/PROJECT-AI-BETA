# JARVIS AI Agent

Sistem asisten desktop lokal berbasis Ollama, Node.js (Electron), dan Python (FastAPI).

## Kapabilitas

- **Pemrosesan Bahasa Lokal:** Menggunakan model Ollama (`qwen2.5:7b`) untuk pemrosesan teks lokal (offline).
- **Analisis Visi:** Menganalisis input gambar menggunakan model `llava:7b`.
- **Eksekusi Alat Otomatis:** Sistem dapat memilih dan mengeksekusi modul fungsi secara dinamis berdasarkan konteks instruksi pengguna.
- **Manajemen Memori (RAG):** Mengekstrak, menyimpan, dan mencari informasi konteks jangka panjang dari dokumen dan histori obrolan.
- **Interaksi Eksternal:** Mendukung pencarian web, ekstraksi data situs web, kontrol YouTube, pengamatan layar, dan operasi sistem file.

## Limitasi

- **Beban Komputasi Perangkat Keras:** Menjalankan model bahasa besar (LLM) dan pemrosesan vektor secara lokal membutuhkan memori RAM yang signifikan (minimal 16GB) dan daya komputasi yang tinggi.
- **Ketergantungan Arsitektur Ganda:** Memerlukan dua environment yang berjalan bersamaan secara sinkron (Node.js untuk logika utama/UI dan Python untuk server memori RAG).
- **Stabilitas Pengenalan Suara:** Input suara (Speech-to-Text) belum sepenuhnya stabil pada environment antarmuka saat ini.

## Instalasi dan Pemasangan

**Prasyarat:** Node.js v18+, Python 3.10+, dan Ollama (dengan model `qwen2.5:7b` dan `llava:7b`).

```bash
# 1. Kloning repositori
git clone https://github.com/Noapllabib06/Project-AI.git
cd Project-AI

# 2. Instalasi Dependensi
npm install
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## Panduan Penggunaan

Gunakan skrip eksekusi simultan untuk menjalankan server memori dan antarmuka secara bersamaan:

```bash
npm run dev
```

Untuk detail mengenai arsitektur, daftar lengkap dependensi, penjelasan kapabilitas, dan pemecahan masalah, silakan baca [GUIDE.md](GUIDE.md).
