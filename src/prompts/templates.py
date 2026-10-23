"""Template generators and dynamic few-shot builders for JARVIS.

Migrated from:
- src/engine/prompt.js
- src/engine/json_validator.js
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from src.prompts.system_prompts import (
    PERSONA,
    TOOL_DECISION_RULES,
    GENERAL_ANSWER_RULES,
    NEGATIVE_EXAMPLES,
)

TOOL_EXAMPLES: Dict[str, str] = {
    "search_memory": """✅ (cari ingatan / masa lalu):
User: "apa makanan kesukaan saya yang kemarin kubilang?"
Assistant: {"tool": "search_memory", "query": "makanan kesukaan"}""",

    "save_memory": """✅ (simpan ingatan / fakta):
User: "tolong ingat kalau makanan kesukaan saya ayam goreng"
Assistant: {"tool": "save_memory", "query": "makanan kesukaan saya ayam goreng"}

❌ (JANGAN simpan password/kredensial pakai save_memory):
User: "simpan kredensial gmail, username x@gmail.com, password xxxx"
Assistant: {"tool": "save_credential", "query": "..."}""",

    "save_credential": """✅ (simpan kredensial / password / login):
User: "simpan password fb saya: 123456"  
Assistant: {"tool": "save_credential", "query": "facebook: 123456"}""",

    "search_web": """✅ (cari info real-time / artikel / berita via Google & web):
User: "tolong cari di internet terkait contoh essay anti korupsi"
Assistant: {"tool": "search_web", "query": "contoh esai anti korupsi"}

User: "siapa presiden indonesia saat ini ya jarvis?"
Assistant: {"tool": "search_web", "query": "Presiden Indonesia saat ini"}""",

    "search_wikipedia": """✅ (cari ensiklopedia / definisi konsep / sejarah / biografi tokoh):
User: "apa itu anarkisme dan sejarahnya?"
Assistant: {"tool": "search_wikipedia", "query": "Anarkisme"}""",

    "search_youtube": """✅ (cari konten YouTube):
User: "putar tutorial volumetrik Blender"
Assistant: {"tool": "search_youtube", "query": "tutorial volumetrik Blender"}""",

    "open_website": """✅ (buka situs):
User: "buka youtube"
Assistant: {"tool": "open_website", "query": "youtube"}""",

    "play_music": """✅ (putar musik):
User: "putar lagu bohemian rhapsody"
Assistant: {"tool": "play_music", "query": "bohemian rhapsody"}""",

    "play_video": """✅ (putar video):
User: "putar tutorial react js"
Assistant: {"tool": "play_video", "query": "tutorial react js"}""",

    "create_file": """✅ (buat file):
User: "buat catatan judulnya belanja"
Assistant: {"tool": "create_file", "query": "belanja.txt|..."}""",

    "read_file": """✅ (baca file):
User: "baca isi main.js"
Assistant: {"tool": "read_file", "query": "./src/main.js"}""",

    "research_and_summarize": """✅ (riset mendalam):
User: "riset perkembangan AI 2024"
Assistant: {"tool": "research_and_summarize", "query": "perkembangan AI 2024"}""",

    "ingest_codebase": """✅ (analisis project):
User: "analisis struktur project ini"
Assistant: {"tool": "ingest_codebase", "query": "./src"}""",

    "read_webpage": """✅ (baca artikel online):
User: "baca artikel ini https://example.com"
Assistant: {"tool": "read_webpage", "query": "https://example.com"}""",

    "open_youtube_channel": """✅ (buka channel YouTube langsung):
User: "buka youtube channel MiawAug"
Assistant: {"tool": "open_youtube_channel", "query": "MiawAug"}""",

    "open_app": """✅ (buka aplikasi desktop lokal):
User: "buka kalkulator"
Assistant: {"tool": "open_app", "query": "kalkulator"}""",

    "control_volume": """✅ (atur volume sistem):
User: "naikkan volume"
Assistant: {"tool": "control_volume", "query": "naikkan volume"}""",

    "take_screenshot": """✅ (ambil screenshot layar):
User: "screenshot layar saya"
Assistant: {"tool": "take_screenshot", "query": ""}""",

    "check_email": """✅ (cek email biasa):
User: "cek email saya"
Assistant: {"tool": "check_email", "query": ""}

✅ (baca ISI PENUH dari email spesifik):
User: "Tampilkan isi email dari paimon pada 14/8/2026"
Assistant: {"tool": "check_email", "sender": "paimon", "date": "14/8/2026"}""",
}


def build_few_shot_examples(tool_names: Optional[List[str]] = None) -> str:
    """Builds relevant few-shot examples dynamically based on filtered tools."""
    names = tool_names or list(TOOL_EXAMPLES.keys())
    matched = [TOOL_EXAMPLES[n] for n in names if n in TOOL_EXAMPLES]
    all_examples = matched + [NEGATIVE_EXAMPLES]
    return "🔍 **CONTOH PENGGUNAAN TOOL:**\n\n" + "\n\n".join(all_examples)


def build_tools_description(tools: List[Dict[str, Any]]) -> str:
    """Formats list of available tools into structured system prompt section."""
    if not tools:
        return ""

    lines = ["🛠️ **TOOL YANG TERSEDIA SAAT INI:**\n"]
    for i, tool in enumerate(tools, 1):
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")
        params = tool.get("parameters", {}).get("properties", {})
        param_names = ", ".join(params.keys()) if params else "(tidak ada parameter)"

        lines.append(f"{i}. **{name}** — {desc}")
        lines.append(f"   - Parameter: {param_names}\n")

    return "\n".join(lines)


def build_system_prompt(
    relevant_tools: Optional[List[Dict[str, Any]]] = None,
    facts: Optional[List[str]] = None,
    conversation_context: str = ""
) -> str:
    """Compiles complete dynamic system prompt for JARVIS."""
    current_time_str = datetime.now().strftime("%A, %d %B %Y %H:%M:%S WIB")

    tools_list = relevant_tools or []
    tool_names = [t.get("name", "") for t in tools_list]

    tools_section = build_tools_description(tools_list)
    few_shot_section = build_few_shot_examples(tool_names)

    facts_section = ""
    if facts:
        facts_items = "\n".join(f"- {f}" for f in facts)
        facts_section = f"💡 **FAKTA TENTANG PENGGUNA:**\n{facts_items}"

    parts = [
        PERSONA,
        facts_section,
        f"Waktu sistem: {current_time_str}.",
        f"[STATUS]: {conversation_context}" if conversation_context else "",
        TOOL_DECISION_RULES,
        tools_section,
        few_shot_section,
        "💡 **PILIHAN TINDAKAN:** Jika butuh tool, keluarkan JSON: {\"tool\": \"nama_tool\", \"query\": \"...\"}. Jika ingin menjawab langsung (chat), keluarkan: {\"tool\": \"chat\", \"query\": \"jawaban langsung\"}.",
        "⛔ **DILARANG KERAS:** Menambahkan teks naratif di luar JSON saat memilih tool. HANYA output format JSON yang valid."
    ]

    return "\n\n".join(p for p in parts if p.strip())


def build_error_feedback_prompt(ai_output: str, error_message: str) -> str:
    """Generates structured error feedback to force self-correction upon invalid JSON output."""
    return f"""⚠️ OUTPUT TIDAK VALID. Silakan perbaiki:

Error: {error_message}

Output Anda sebelumnya yang salah:
{ai_output}

Format yang BENAR (HANYA JSON ATAU ARRAY OF JSON, TANPA teks penjelasan):
[{{"tool": "nama_tool", "query": "nilai_kueri"}}]

Contoh Chat Biasa (tanpa tool):
{{"tool": "chat", "query": "jawaban langsung Anda di sini"}}

Contoh Eksekusi Tool:
{{"tool": "search_web", "query": "topik pencarian"}}

ATURAN PERBAIKAN:
1. HANYA keluarkan JSON valid, jangan tambahkan pembuka atau penutup markdown selain JSON.
2. Jangan tinggalkan trailing commas.
3. Coba lagi sekarang dengan format yang benar."""
