"""System Knowledge, Capabilities Introspection, and Dynamic Tool Catalog for JARVIS.

Provides dynamic, modular self-awareness for JARVIS:
- Identity, architecture, and persona
- Comprehensive capabilities overview
- System limitations and boundaries
- Dynamic registry-driven tool catalog that auto-updates whenever new tools are added
"""

import sys
import platform
from typing import Dict, Any, List
from config.settings import settings, get_logger
from src.memory.memory_store import memory_store

logger = get_logger("SystemInfoTool")


def get_jarvis_capabilities(query: str = "") -> str:
    """Returns a dynamic, comprehensive report of JARVIS's identity, capabilities,

    limitations, and all registered tools dynamically fetched from the tool registry.
    """
    logger.info("Generating dynamic capabilities report for JARVIS...")

    # 1. Fetch all tools dynamically from the registry to ensure 100% modularity
    from src.tools import get_all_tools
    all_tools = get_all_tools()
    total_tools = len(all_tools)

    # 2. Categorize tools dynamically based on functional domain
    CATEGORY_MAPPING = {
        "🌐 Pencarian Web & Riset": [
            "search_web", "search_wikipedia", "read_webpage",
            "research_and_summarize", "search_youtube", "open_youtube_channel",
            "play_music", "play_video"
        ],
        "💻 Kontrol Sistem, Aplikasi & Kode": [
            "open_app", "open_website", "control_volume", "create_file",
            "read_file", "git_operation", "ingest_codebase",
            "read_github_repo", "read_github_file", "clone_and_ingest_github"
        ],
        "🔒 Komunikasi & Kredensial Terenkripsi": [
            "check_email", "save_credential"
        ],
        "🧠 Second Brain & Memori Semantik (Obsidian + ChromaDB)": [
            "process_second_brain_pipeline", "ingest_with_markitdown", "search_second_brain",
            "save_memory", "search_memory"
        ],
        "👁️ Visi Komputer, Dokumen & Kepenulisan": [
            "take_screenshot", "ocr_image", "parse_document", "draft_content"
        ],
        "🔢 Utilitas, Matematika & Waktu": [
            "calculate", "get_datetime"
        ],
        "ℹ️ Metakognisi & Informasi Sistem": [
            "get_jarvis_capabilities"
        ]
    }

    categorized_tools: Dict[str, List[Dict[str, Any]]] = {cat: [] for cat in CATEGORY_MAPPING}
    categorized_tools["🛠️ Alat Tambahan & Ekstensi Kustom"] = []

    handled_names = set()
    for cat_name, tool_names in CATEGORY_MAPPING.items():
        for tool in all_tools:
            t_name = tool.get("name", "")
            if t_name in tool_names:
                categorized_tools[cat_name].append(tool)
                handled_names.add(t_name)

    # Any newly added tools that don't belong to predefined lists automatically go to Custom/Additional
    for tool in all_tools:
        t_name = tool.get("name", "")
        if t_name not in handled_names:
            categorized_tools["🛠️ Alat Tambahan & Ekstensi Kustom"].append(tool)

    # 3. Format dynamic tool catalog
    catalog_sections = []
    for category_name, tools in categorized_tools.items():
        if not tools:
            continue
        catalog_sections.append(f"### {category_name} ({len(tools)} Tool)")
        for t in tools:
            name = t.get("name", "")
            desc = t.get("description", "Tidak ada deskripsi.")
            catalog_sections.append(f"- **`{name}`**: {desc}")
        catalog_sections.append("")

    tools_catalog_text = "\n".join(catalog_sections)

    # 4. Gather runtime environment metadata
    active_model = settings.llm.default_model
    provider = settings.llm.provider
    num_ctx = settings.llm.num_ctx
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # 5. Build full comprehensive report
    report = f"""# 🤖 Profil, Kemampuan, & Limitasi JARVIS

Halo! Saya adalah **JARVIS** (*Just A Rather Very Intelligent System*), asisten kecerdasan buatan otonom pribadi yang dirancang khusus untuk membantu Anda dalam riset, otomasi sistem operasi, analisis kode, pengolahan dokumen, dan manajemen tugas cerdas.

---

## 🏛️ Arsitektur & Identitas Sistem
- **Engine**: 100% Modular Python AI Agent Architecture.
- **Model Aktif**: `{active_model}` via `{provider.upper()}` (Context Window: {num_ctx} token).
- **Environment**: Python {python_ver} di atas platform `{os_info}`.
- **Multi-Agent Pipeline**:
  1. **Task Router**: Mengklasifikasikan niat pengguna dan memilih subset tool paling hemat token.
  2. **Planner Agent**: Memecah perintah kompleks (multi-step) menjadi sub-tugas terstruktur.
  3. **Tool Agent**: Mengeksekusi aksi secara aman dengan proteksi error dan *timeout*.
  4. **Supervisor Agent**: Memvalidasi skema (Pydantic v2), melakukan *self-correction feedback loop*, dan membersihkan jawaban akhir.
  5. **Hybrid RAG Memory**: Memadukan pencarian semantik vektor (FAISS/TurboVec) dan leksikal (BM25Okapi) dengan *Reciprocal Rank Fusion* (RRF).

---

## ⚡ Kemampuan Utama (What I Can Do)
1. **Pencarian Web & Riset Real-Time**: Menjelajahi Google, DuckDuckGo, Wikipedia, dan YouTube untuk mendapatkan informasi terkini melampaui *training cutoff*.
2. **Otomasi Sistem & File**: Membuka aplikasi desktop (Kalkulator, Notepad, VS Code, Spotify), mengontrol volume audio sistem, serta membuat, membaca, dan mengedit file langsung di komputer Anda.
3. **Analisis Kode & Git**: Membaca struktur proyek (*codebase ingest*), meninjau file repositori, dan menjalankan operasi Git (`status`, `diff`, `log`, `commit`).
4. **Keamanan Kredensial & Email**: Menyimpan password atau token secara aman menggunakan enkripsi standar industri AES-GCM serta membaca kotak masuk email (IMAP) tanpa mengekspos rahasia.
5. **Visi Komputer (OCR) & Dokumen**: Mengambil tangkapan layar (*screenshot*), membaca teks dari gambar menggunakan Neural Vision OCR, serta mengekstrak teks dari berkas PDF, DOCX, dan TXT.
6. **Memori Jangka Panjang Terpadu**: Mengingat preferensi, fakta penting, dan riwayat instruksi Anda secara permanen.

---

## ⚠️ Limitasi & Batasan (System Limitations)
1. **Hak Akses Sistem Operasi**: Saya beroperasi di bawah hak akses akun pengguna lokal Anda. Saya tidak dapat memodifikasi sistem yang dilindungi hak administrator tanpa izin eksplisit.
2. **Ketergantungan Internet untuk Data Web**: Untuk informasi *real-time* (berita hari ini, harga saham, cuaca), saya membutuhkan koneksi internet aktif. Jika internet terputus, saya hanya dapat mengandalkan memori lokal dan pengetahuan dasar model.
3. **Kapasitas Hardware Lokal**: Kecepatan pemrosesan dan panjang penalaran dipengaruhi oleh kapasitas GPU/CPU dan VRAM perangkat komputer Anda.
4. **Validasi Output & Self-Correction**: Saya menghasilkan aksi berbasis instruksi JSON terstruktur. Jika terjadi ketidaksesuaian format, sistem secara mandiri melakukan percobaan ulang (*retry*) maksimal 3 kali sebelum memberikan respon langsung.
5. **Kerahasiaan Kredensial**: Saya tidak akan pernah menampilkan kata sandi yang telah dienkripsi secara terbuka di layar chat demi menjaga keamanan privasi Anda.

---

## 🛠️ Daftar Lengkap Tool Aktif ({total_tools} Tool Terdaftar)
Sistem tool saya bersifat **sepenuhnya modular**. Setiap kali ada tool baru yang didaftarkan ke sistem, katalog ini akan **otomatis diperbarui** tanpa perlu konfigurasi ulang:

{tools_catalog_text}
💡 *Jika Anda membutuhkan bantuan spesifik dengan salah satu kemampuan di atas, cukup tanyakan langsung kepada saya!*
"""
    return report.strip()


TOOL_DEFINITIONS = [
    {
        "name": "get_jarvis_capabilities",
        "description": "Menampilkan penjelasan lengkap mengenai identitas JARVIS, arsitektur sistem, kemampuan utama, limitasi/batasan, serta daftar dinamis seluruh tool aktif beserta kegunaannya.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Kueri spesifik tentang kemampuan atau limitasi (opsional)"
                }
            }
        },
        "handler": get_jarvis_capabilities
    }
]
