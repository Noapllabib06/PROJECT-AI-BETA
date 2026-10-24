# 📚 Direktori Materi Kuliah (Academic Knowledge Base)

Direktori ini digunakan untuk menyimpan seluruh berkas materi kuliah Anda (PDF, DOCX, PPTX, TXT). JARVIS akan secara otomatis membaca, mengindeks, dan mengorganisasi materi per-mata kuliah dan per-pertemuan ke dalam memori RAG lokal.

## 📂 Struktur Rekomendasi:
Letakkan berkas per folder mata kuliah seperti contoh di bawah ini:

```text
data/kuliah/
├── Sistem_Operasi/
│   ├── Silabus.pdf
│   ├── P01_Pengantar_Sistem_Operasi.pdf
│   ├── P02_Proses_dan_Thread.pdf
│   ├── P03_Penjadwalan_CPU.pdf
│   └── Tugas_1.pdf
├── Kecerdasan_Buatan/
│   ├── P01_Konsep_AI_dan_Agen.pdf
│   ├── P02_Algoritma_Pencarian.pdf
│   └── P03_Machine_Learning_Dasar.pdf
└── [Nama_Mata_Kuliah_Lainnya]/
    └── ...
```

## 💡 Konvensi Penamaan Berkas:
* Sertakan kode pertemuan seperti `P01`, `P02`, `Pertemuan_1`, `P3` di nama berkas agar JARVIS dapat mengidentifikasi nomor pertemuan secara otomatis.
* Format berkas yang didukung: `.pdf`, `.docx`, `.pptx`, `.txt`, `.md`.
