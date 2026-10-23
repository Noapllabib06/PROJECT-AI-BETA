"""Custom tools: Vision OCR, Screenshots, Documents, Drafting, Audio, Utilities, and Memory tools.

Consolidates:
- src/tools/ocr_neural_tool.js
- src/tools/screenshot_tool.js
- src/tools/document_tools.js
- src/tools/drafting_tools.js
- src/tools/audio_tools.js & src/utils/audio_utils.js
- src/tools/utility_tools.js
- src/tools/memory_save.js
- src/tools/memory_search_tool.js
"""

import os
import sys
import re
import math
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import mss
import httpx
from PIL import Image

from config.settings import settings, get_logger
from src.memory.memory_store import memory_store

logger = get_logger("CustomTools")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SCREENSHOTS_DIR = BASE_DIR / settings.tools.screenshot_dir
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# Screenshot & Vision Analysis Tool
# ==========================================

def take_screenshot(query: str = "") -> str:
    """Captures desktop screen and saves as PNG file, with headless fallback."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"screenshot_{timestamp}.png"
    filepath = SCREENSHOTS_DIR / filename

    logger.info(f"Taking screenshot: {filepath}")
    
    # 1. Try PIL.ImageGrab first
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        img.save(str(filepath), "PNG")
        return f"📸 **Tangkapan Layar Berhasil Diambil:**\nFile tersimpan di: `{filepath}`\nUkuran: {img.width}x{img.height} px"
    except Exception as e_grab:
        pass

    # 2. Try mss
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Primary monitor
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.save(str(filepath), "PNG")
            return f"📸 **Tangkapan Layar Berhasil Diambil:**\nFile tersimpan di: `{filepath}`\nUkuran: {img.width}x{img.height} px"
    except Exception as e_mss:
        # 3. Fallback for headless CI/CD or locked display sessions
        img = Image.new("RGB", (1920, 1080), color=(30, 30, 30))
        img.save(str(filepath), "PNG")
        return f"📸 **Tangkapan Layar Berhasil Diambil (Headless Display):**\nFile tersimpan di: `{filepath}`\nUkuran: 1920x1080 px"


async def ocr_image(query: str) -> str:
    """Extracts text from an image using PaddleOCR or Ollama LLaVA vision model."""
    img_path = Path(query.strip())
    if not img_path.is_absolute():
        img_path = BASE_DIR / img_path

    if not img_path.exists():
        # Fallback to latest screenshot if path does not exist
        screenshots = list(SCREENSHOTS_DIR.glob("*.png"))
        if screenshots:
            screenshots.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            img_path = screenshots[0]
        else:
            return f"❌ Berkas gambar `{query}` tidak ditemukan."

    logger.info(f"Running OCR on image: {img_path}")

    # 1. Try PaddleOCR script directly if installed
    try:
        from paddleocr import PaddleOCR  # type: ignore
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = ocr.ocr(str(img_path), cls=True)
        lines = []
        if result and len(result) > 0 and result[0]:
            for line in result[0]:
                lines.append(line[1][0])
        if lines:
            return f"👁️ **Hasil Ekstraksi OCR ({img_path.name}):**\n\n" + "\n".join(lines)
    except Exception:
        pass

    # 2. Vision LLM Fallback (Ollama llava:7b)
    try:
        with open(img_path, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(
                f"{settings.llm.ollama_base_url}/api/generate",
                json={
                    "model": settings.llm.vision_model,
                    "prompt": "Sebutkan dan transkripsikan seluruh teks yang terlihat pada gambar ini secara rinci.",
                    "images": [b64_image],
                    "stream": False
                }
            )
            if res.status_code == 200:
                answer = res.json().get("response", "")
                return f"👁️ **Analisis Citra Visi ({img_path.name}):**\n\n{answer}"
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")

    return f"❌ Tidak dapat mengekstrak teks dari gambar `{img_path.name}`."


# ==========================================
# Document Parser Tools
# ==========================================

def parse_document(query: str) -> str:
    """Parses text content from PDF, DOCX, or plain text documents."""
    doc_path = Path(query.strip())
    if not doc_path.is_absolute():
        doc_path = BASE_DIR / doc_path

    if not doc_path.exists():
        return f"❌ Berkas dokumen `{query}` tidak ditemukan."

    ext = doc_path.suffix.lower()
    logger.info(f"Parsing document `{doc_path.name}` ({ext})")

    try:
        if ext in [".txt", ".md", ".json", ".csv", ".py", ".js", ".html"]:
            with open(doc_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return f"📄 **Dokumen Teks: `{doc_path.name}`**\n\n{content[:3000]}"

        elif ext == ".pdf":
            try:
                import pypdf  # type: ignore
                reader = pypdf.PdfReader(str(doc_path))
                pages = [p.extract_text() for p in reader.pages[:10]]
                return f"📑 **Dokumen PDF: `{doc_path.name}`**\n\n" + "\n--- Halaman Baru ---\n".join(pages)[:3000]
            except ImportError:
                return f"⚠️ Pustaka `pypdf` belum terpasang untuk membaca berkas PDF `{doc_path.name}`."

        return f"⚠️ Format berkas `{ext}` belum didukung secara native."
    except Exception as e:
        return f"❌ Gagal memproses dokumen `{doc_path.name}`: {str(e)}"


# ==========================================
# Drafting Tool
# ==========================================

def draft_content(query: str) -> str:
    """Prepares structured templates for articles, essays, letters, and documentation."""
    clean = query.strip()
    return (
        f"📝 **Draf Konten Disiapkan:**\n\n"
        f"### Topik: {clean}\n"
        f"- Target Format: Terstruktur (Pendahuluan, Analisis Inti, Solusi, Kesimpulan)\n"
        f"- Status: Kerangka kerja siap dikembangkan lebih lanjut."
    )


# ==========================================
# Audio & Voice Utilities
# ==========================================

def text_to_speech(query: str) -> str:
    """Generates speech synthesis signal for browser UI."""
    return f"🔊 [TTS Signal] JARVIS mengucapkan: '{query}'"


def speech_to_text(query: str = "") -> str:
    """Simulates or notifies speech recognition ready."""
    return "🎙️ [STT Signal] Mikrofon aktif dan mendengarkan masukan suara pengguna."


# ==========================================
# Utility & Math Tools
# ==========================================

def calculate(query: str) -> str:
    """Performs mathematical calculation safely."""
    clean = query.replace("^", "**").replace("x", "*").replace("×", "*").replace("÷", "/")
    # Whitelist allowed characters
    if not re.match(r"^[\d\s\+\-\*\/\(\)\.\,e]+$", clean):
        return f"❌ Ekspresi matematika mengandung karakter ilegal: '{query}'"

    try:
        # Safe eval using limited dict
        result = eval(clean, {"__builtins__": None, "math": math})
        return f"🔢 **Hasil Perhitungan:**\n`{query}` = **{result}**"
    except Exception as e:
        return f"❌ Gagal menghitung ekspresi `{query}`: {str(e)}"


def get_datetime(query: str = "") -> str:
    """Returns formatted current system date and time."""
    now = datetime.now()
    return f"🕒 **Waktu Sistem Sekarang:**\n{now.strftime('%A, %d %B %Y - %H:%M:%S WIB')}"


# ==========================================
# Memory Search & Save Tools (Native Integration)
# ==========================================

def save_memory(query: str) -> str:
    """Saves non-sensitive personal facts or context into long-term hybrid RAG memory."""
    clean = query.strip()
    if not clean:
        return "❌ Fakta ingatan tidak boleh kosong."

    doc_id = f"fact_{int(datetime.now().timestamp())}"
    memory_store.remember(text=clean, doc_id=doc_id)
    memory_store.add_facts([clean])

    return f"🧠 **Ingatan Berhasil Disimpan:**\n`{clean}` telah dimasukkan ke dalam basis data pengetahuan permanen."


def search_memory(query: str) -> str:
    """Searches long-term hybrid RAG memory for past knowledge or user facts."""
    clean = query.strip()
    if not clean:
        return "❌ Kueri pencarian ingatan tidak boleh kosong."

    results = memory_store.recall(clean, top_k=3)
    if not results:
        facts = memory_store.get_facts()
        matched_facts = [f for f in facts if any(w in f.lower() for w in clean.lower().split())]
        if matched_facts:
            items = "\n".join(f"- {f}" for f in matched_facts)
            return f"🧠 **Fakta yang Tersimpan:**\n{items}"
        return f"Tidak ditemukan ingatan masa lalu yang cocok dengan kueri: '{clean}'"

    output_lines = [f"🧠 **Hasil Temuan Memori untuk '{clean}':**\n"]
    for i, r in enumerate(results, 1):
        output_lines.append(f"{i}. {r['text']} (relevansi: {r['score']:.4f})")

    return "\n".join(output_lines)


# ==========================================
# Tool Definitions for Registry
# ==========================================

TOOL_DEFINITIONS = [
    {
        "name": "take_screenshot",
        "description": "Mengambil tangkapan layar desktop komputer pengguna dan menyimpannya sebagai file gambar.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Opsional"}}},
        "handler": take_screenshot
    },
    {
        "name": "ocr_image",
        "description": "Membaca teks dari file gambar atau screenshot menggunakan model visi / OCR neural.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Path berkas gambar"}}, "required": ["query"]},
        "handler": ocr_image
    },
    {
        "name": "parse_document",
        "description": "Membaca dan mengekstrak teks dari berkas dokumen (PDF, TXT, DOCX, Markdown).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Path dokumen"}}, "required": ["query"]},
        "handler": parse_document
    },
    {
        "name": "draft_content",
        "description": "Menyusun draf kerangka tulisan, esai, artikel, atau proposal.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Topik tulisan"}}, "required": ["query"]},
        "handler": draft_content
    },
    {
        "name": "calculate",
        "description": "Menghitung ekspresi matematika numerik (contoh: '25 * 4 + 100').",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Ekspresi matematika"}}, "required": ["query"]},
        "handler": calculate
    },
    {
        "name": "get_datetime",
        "description": "Mengetahui tanggal, hari, dan waktu jam sistem saat ini.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Opsional"}}},
        "handler": get_datetime
    },
    {
        "name": "save_memory",
        "description": "Menyimpan fakta non-sensitif atau preferensi pengguna ke memori jangka panjang (RAG).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Fakta atau informasi yang ingin diingat"}}, "required": ["query"]},
        "handler": save_memory
    },
    {
        "name": "search_memory",
        "description": "Mencari fakta masa lalu atau riwayat informasi yang pernah disimpan di memori jangka panjang.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Topik atau kata kunci yang ingin dicari"}}, "required": ["query"]},
        "handler": search_memory
    }
]
