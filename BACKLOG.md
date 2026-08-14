# Fitur Backlog (Eksperimen / Ide Masa Depan)

## Pemutar Media Terintegrasi (YouTube Mini Player)
**Status**: Disimpan untuk eksperimen di masa depan.
**Deskripsi**: 
Memungkinkan pemutaran musik atau video YouTube secara langsung di dalam antarmuka UI Jarvis (menggunakan `<iframe>` atau mini player) daripada membuka tab browser eksternal. 
**Tujuan**: 
Menghemat penggunaan RAM secara signifikan karena Jarvis menggunakan Electron (yang sudah memiliki basis Chromium) sehingga menghindari beban membuka proses browser sistem penuh seperti Chrome/Edge, serta memberikan pengalaman pengguna yang lebih *seamless*.
**Tugas Terkait**:
- Merombak tool `play_music` dan `play_video` untuk mengembalikan respons UI khusus (seperti memicu event IPC).
- Menambahkan komponen pemutar melayang (floating player) di UI `index.html` / `renderer.js`.
