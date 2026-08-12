# Panduan Teknis JARVIS AI

Dokumentasi lengkap mengenai arsitektur, instalasi, dependensi, dan operasional sistem.

## Arsitektur Sistem

- **Frontend & Agent Engine (Node.js/Electron):** Menangani antarmuka visual (UI), manajemen siklus hidup proses, dan logika pengambilan keputusan agen AI.
- **Memory Server (Python FastAPI):** Menangani Retrieval-Augmented Generation (RAG), perhitungan vektor embedding, dan penyimpanan data semantik.

## Instalasi Pemasangan

### 1. Persyaratan Lingkungan
- Node.js LTS (v18 atau lebih baru)
- Python 3.10 atau lebih baru
- Ollama (Model yang ditarik: `qwen2.5:7b` dan `llava:7b`)

### 2. Pemasangan Dependensi Node.js
Jalankan perintah berikut di direktori root proyek:
```bash
npm install
```
**Daftar Dependensi Terpasang (Node.js):**
- `electron`: Framework antarmuka desktop.
- `langchain` & `@langchain/ollama`: Integrasi kerangka kerja dan antarmuka model bahasa.
- `axios`, `cheerio`, `duck-duck-scrape`, `googlethis`: Modul pengambilan data dan pencarian web.
- `imap-simple`, `mailparser`: Modul koneksi dan ekstraksi data email.
- `play-dl`: Modul pencarian dan pemutaran media YouTube.
- `screenshot-desktop`: Modul penangkapan citra layar (vision data).
- `concurrently`: Utilitas eksekusi multisesi.

### 3. Pemasangan Dependensi Python (Server Memori)
Disarankan menggunakan environment virtual untuk isolasi pustaka:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install fastapi uvicorn sentence-transformers faiss-cpu numpy turbovec pydantic
```
**Daftar Dependensi Terpasang (Python):**
- `fastapi`, `uvicorn`: Framework server API berkinerja tinggi.
- `sentence-transformers`, `numpy`: Transformasi teks menjadi struktur matriks dan vektor.
- `faiss-cpu`, `turbovec`: Basis data indeks vektor dan metode pencarian semantik (Similarity Search).

## Panduan Penggunaan

Sistem terdiri dari dua entitas yang harus beroperasi secara paralel.

**Cara Eksekusi (Otomatis via NPM):**
Metode direkomendasikan yang telah terkonfigurasi di dalam ekosistem *package.json*:
```bash
npm run dev
```

**Cara Eksekusi (Manual):**
Jika diperlukan untuk proses debugging terpisah, buka dua sesi terminal:
1. Jalankan Server Memori: `.\venv\Scripts\python.exe -m uvicorn local_memory:app --port 8000`
2. Jalankan UI & Agen Utama: `npx electron src/main.js`

## Kapabilitas Sistem

Sistem modular ini dilengkapi dengan kapabilitas fungsional spesifik:

- **Modul Web:** Mampu melakukan pencarian parameter via mesin pencari, serta mengakses dan merangkum struktur DOM (Document Object Model) suatu halaman situs.
- **Modul File Lokal:** Membaca isi berkas dokumen, menulis atau menimpa log berkas, dan menavigasi direktori penyimpanan pengguna.
- **Modul Multimedia:** Mencari metadata spesifik dari video YouTube dan melakukan kontrol jendela pemutaran media.
- **Modul Vision:** Menangkap citra layar aktif atau menganalisis file gambar (.jpg/.png) yang diunggah pengguna untuk dianalisis oleh modul *llava*.
- **Modul Memori (RAG):** Menyimpan artefak percakapan sebagai fakta persisten, serta mereduksi dokumen panjang menjadi indeks vektor (384-dimensi) untuk keperluan pencarian konteks di percakapan mendatang.
- **Modul Kredensial:** Mengelola nama pengguna dan kata sandi web dalam format terenkripsi menggunakan pengunci perangkat keras spesifik secara luring.

## Limitasi dan Troubleshooting

- **Latensi Respon (Beban Perangkat Keras):** Karena pemrosesan tidak bertumpu pada cloud, latensi respons sistem secara langsung bergantung pada kecepatan RAM dan komputasi GPU/CPU komputer pengguna.
- **Koneksi Server (Timeout):** Jika agen AI gagal menggunakan modul memori, pastikan modul server `local_memory.py` berjalan tanpa galat di jaringan lokal pada port `8000`.
- **Anomali Karakter Terminal:** Pencetakan karakter khusus (seperti simbol atau UTF-8 lanjutan) dapat mengalami kegagalan pada antarmuka *Command Prompt* standar Windows. Direkomendasikan menggunakan *Windows Terminal* atau shell terintegrasi *VS Code*.