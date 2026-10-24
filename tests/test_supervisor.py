"""Tests for SupervisorAgent cleaning, trace emission, and dummy link sanitization."""

import pytest
from src.agents.supervisor_agent import SupervisorAgent


def test_clean_answer_text_removes_dummy_links():
    supervisor = SupervisorAgent()
    
    sample_text = """### Ringkasan Inti
Tentu saja, saya bisa menyimpan file PDF dan mengindeksnya ke dalam sistem memori RAG lokal Anda.

### 📌 Poin Kunci & Penjelasan
- **Ekstraksi Teks**: PDF diproses menggunakan library MarkItDown menjadi Markdown.
- **Penyimpanan Vektor**: Teks disimpan ke dalam database vektor lokal (TurboVec / ChromaDB).

### 🔗 Tautan Sumber & Referensi
- [🔗 Sumber: Panduan PDF RAG](https://example.com/pdf-rag)
- [🔗 Sumber: Dokumentasi](http://www.example.org/docs)
"""

    cleaned, corrections = supervisor.clean_answer_text(sample_text)
    
    assert "example.com" not in cleaned
    assert "example.org" not in cleaned
    assert "Tautan Sumber & Referensi" not in cleaned
    assert "Ekstraksi Teks" in cleaned
    assert any("dummy links" in c for c in corrections)
    assert any("empty source & reference" in c for c in corrections)


def test_clean_answer_preserves_real_links():
    supervisor = SupervisorAgent()
    
    sample_text = """### Ringkasan Inti
Berikut informasi dari Wikipedia mengenai Python.

### 🔗 Tautan Sumber & Referensi
- [🔗 Sumber: Wikipedia - Python](https://id.wikipedia.org/wiki/Python_(bahasa_pemrograman))
"""

    cleaned, corrections = supervisor.clean_answer_text(sample_text)
    
    assert "https://id.wikipedia.org/wiki/Python" in cleaned
    assert "Tautan Sumber & Referensi" in cleaned


def test_clean_answer_text_removes_negative_source_disclaimers():
    supervisor = SupervisorAgent()

    sample_text = """### Ringkasan Inti
Direktori materi kuliah Cloud Computing berhasil diproses.

Tautan Sumber & Referensi

Tidak ada tautan sumber yang tersedia dari hasil eksekusi tool pencarian web dalam hal ini. Jika Anda membutuhkan informasi lebih lanjut tentang penginggrasan materi kuliah, Anda dapat merujuk ke dokumentasi sistem.
"""

    cleaned, corrections = supervisor.clean_answer_text(sample_text)

    assert "Tautan Sumber & Referensi" not in cleaned
    assert "Tidak ada tautan sumber" not in cleaned
    assert "Direktori materi kuliah Cloud Computing berhasil diproses." in cleaned
    assert any("negative boilerplate" in c for c in corrections)

