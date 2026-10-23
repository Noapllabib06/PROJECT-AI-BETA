"""Task Router and Intent Classifier for dynamic tool subset selection in JARVIS.

Migrated and upgraded from:
- SemanticRouter & Intent heuristics in src/engine/agent.js
"""

import re
from typing import List, Dict, Set, Optional, Tuple, Any
from config.settings import get_logger

logger = get_logger("TaskRouter")

# ==========================================
# Keyword Matchers & Regex Patterns
# ==========================================

SENSITIVE_CONTENT_PATTERN = re.compile(
    r"\b(?:password|kredensial|credential|kata\s*sandi|sandi|api[_\s]?key|token|secret|rahasia|pin|save_credential)\b",
    re.IGNORECASE
)

PUBLIC_FACT_KEYWORDS = [
    "presiden", "wakil presiden", "menteri", "gubernur", "walikota", "bupati",
    "ceo", "direktur utama", "ketua umum", "kapolri", "panglima",
    "harga", "kurs", "nilai tukar", "saham", "inflasi", "bursa",
    "undang-undang", "undang undang", "uu", "omnibus", "hukum", "pasal", "peraturan",
    "tokoh", "biografi", "profil", "siapa itu", "siapakah"
]

TIME_SENSITIVE_KEYWORDS = [
    "saat ini", "sekarang", "terbaru", "terkini", "hari ini"
]

SELF_STATE_PATTERNS = [
    re.compile(r"\b(?:kamu|anda|jarvis|lu|kau)\b.*\b(?:sedang|lagi|lakukan|ngapain|status|kabar|bisa apa|kemampuan)\b", re.IGNORECASE),
    re.compile(r"\b(?:sedang|lagi)\s+(?:apa|ngapain|lakukan)\b", re.IGNORECASE),
    re.compile(r"\bstatus\s+(?:kamu|anda|jarvis|sistem)\b", re.IGNORECASE),
    re.compile(r"\b(?:siapa|tentang|profil)\s+(?:kamu|anda|jarvis)\b", re.IGNORECASE),
    re.compile(r"\b(?:apa\s+saja\s+yang\s+kamu\s+bisa|bisa\s+apa\s+saja|apa\s+kemampuanmu|kemampuan\s+kamu|daftar\s+tool)\b", re.IGNORECASE)
]

# Explicit Tool Keyword Mappings (High Precision)
TOOL_KEYWORD_RULES: Dict[str, List[str]] = {
    "get_jarvis_capabilities": [
        "apa saja yang kamu bisa", "apa kemampuanmu", "kemampuan kamu", "bisa apa saja",
        "bisa apa", "fitur kamu", "fitur jarvis", "apa yang bisa kamu lakukan",
        "siapa kamu", "tentang dirimu", "tentang jarvis", "jelaskan tentang dirimu",
        "daftar tool", "tool apa saja", "kegunaan tool", "tool yang kamu punya",
        "daftar kemampuan", "limitasi kamu", "apa batasanmu", "apa kelemahanmu",
        "informasi sistem", "profil jarvis", "arsitektur jarvis", "what can you do", "list tools"
    ],
    "save_credential": ["simpan password", "simpan kredensial", "catat password", "password akun", "simpan kata sandi"],
    "check_email": ["cek email", "baca email", "email baru", "cek inbox", "cek gmail", "email dari", "isi email"],
    "take_screenshot": ["screenshot", "tangkapan layar", "capture layar", "tangkap layar", "ambil foto layar"],
    "search_youtube": ["cari youtube", "cari video", "cari konten youtube", "video tutorial", "cari musik", "cari lagu"],
    "play_music": [
        "putar lagu", "putar musik", "play music", "play lagu", "mainkan lagu",
        "setel lagu", "setel musik", "dengarkan lagu", "dengarkan musik",
        "putar ", "setel ", "play ", "dengarkan ", "mainkan ",
        "youtube music", "yt music", "lagu"
    ],
    "play_video": ["putar video", "putar tutorial", "play video", "tonton video", "tonton tutorial"],
    "open_app": ["buka aplikasi", "buka kalkulator", "buka notepad", "buka spotify", "buka discord", "buka vscode", "buka task manager"],
    "open_website": ["buka situs", "buka website", "buka web", "buka link", "kunjungi situs", "buka youtube", "buka google"],
    "control_volume": ["volume", "naikkan volume", "turunkan volume", "mute", "unmute", "besarkan suara", "kecilkan suara"],
    "search_wikipedia": [
        "apa itu", "sejarah", "biografi", "siapakah", "definisi", "arti dari", "ensiklopedia",
        "undang-undang", "undang undang", "uu", "omnibus", "hukum", "pasal", "peraturan", "tokoh"
    ],
    "search_web": [
        "cari web", "cari berita", "berita", "info terkini", "harga", "kurs", "cuaca", "gempa",
        "berita hari ini", "update", "terbaru", "siapa itu"
    ],
    "research_and_summarize": ["riset mendalam", "riset dan ringkas", "analisis mendalam"],
    "ingest_codebase": ["analisis project", "analisis codebase", "analisis struktur project", "ingest kode"],
    "create_file": ["buat file", "buat catatan", "tulis file", "simpan file", "bikin file"],
    "read_file": ["baca file", "baca isi file", "baca kode", "lihat isi file"],
    "read_webpage": ["baca artikel", "baca webpage", "baca halaman web", "baca link ini"],
    "search_memory": ["ingatan", "makanan kesukaan", "fakta masa lalu", "apa yang kukatakan", "pernah kubilang", "ingat tidak"],
    "save_memory": ["ingat kalau", "ingat bahwa", "ingat ya", "tolong ingat", "simpan fakta"],
    "process_second_brain_pipeline": [
        "second brain", "simpan ke obsidian", "catat ke obsidian", "masukkan ke second brain",
        "simpan ke vault", "catat ke vault", "rangkum ke obsidian", "arsip ke obsidian"
    ],
    "ingest_with_markitdown": ["ekstrak markitdown", "baca pdf", "baca docx", "ekstrak dokumen"],
    "search_second_brain": ["cari di second brain", "cari di catatan", "cari di obsidian", "cari di vault"],
    "read_github_repo": ["baca github", "baca repo", "analisis github", "pelajari repo", "cek github", "github.com/"],
    "read_github_file": ["baca file github", "lihat kode github", "baca kode github"],
    "clone_and_ingest_github": ["clone github", "kloning repo", "ingest github", "pelajari repo github"]
}


class TaskRouter:
    """Classifies user intent and routes query to the optimal minimal tool subset."""

    @staticmethod
    def is_sensitive(text: str) -> bool:
        """Checks if text contains credentials or secret data requiring secure handling."""
        if not text:
            return False
        return bool(SENSITIVE_CONTENT_PATTERN.search(text))

    @staticmethod
    def requires_forced_web_search(user_input: str) -> bool:
        """Determines if query strictly requires live web data rather than static memory."""
        if not user_input:
            return False
        lower = user_input.lower()

        # Don't force web search if user is talking about JARVIS state/persona
        if any(p.search(lower) for p in SELF_STATE_PATTERNS):
            return False

        # Public facts that change frequently (e.g., current president, exchange rates)
        if any(kw in lower for kw in PUBLIC_FACT_KEYWORDS):
            return True

        # Time-sensitive queries
        if any(kw in lower for kw in TIME_SENSITIVE_KEYWORDS):
            if re.search(r"\b(?:nama saya|hobi saya|siapa saya|ingat|bicara|ngobrol|halo|hai)\b", lower):
                return False
            if re.search(r"\b(?:siapa|berita|apa itu|kejadian|skor|pertandingan|cuaca|gempa)\b", lower):
                return True

        return False

    def route_tools(
        self,
        user_input: str,
        available_tools: List[Dict[str, Any]],
        max_tools: int = 5
    ) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
        """Identifies relevant tools for the user query, returning filtered tool definitions and score map."""
        if not user_input or not available_tools:
            return [], {}

        lower = user_input.lower()
        selected_tool_names: Set[str] = set()
        scores: Dict[str, float] = {}

        # 1. Check for sensitive credential storage
        if self.is_sensitive(user_input) and re.search(r"\b(?:simpan|catat|buat|taruh)\b", lower):
            selected_tool_names.add("save_credential")
            scores["save_credential"] = 1.0

        # 2. Check for explicit keyword rules
        for tool_name, keywords in TOOL_KEYWORD_RULES.items():
            for kw in keywords:
                if kw in lower:
                    selected_tool_names.add(tool_name)
                    scores[tool_name] = max(scores.get(tool_name, 0.0), 0.95)
                    break

        # 2.1 Media / Music Intent Detection (e.g. "putar sunshine", "play coldplay", "lagu OneRepublic")
        if re.search(r"\b(?:putar|play|setel|dengarkan|mainkan|lagu|musik|song|track|audio)\b", lower):
            if re.search(r"\b(?:video|tutorial|film|trailer|klip)\b", lower):
                selected_tool_names.add("play_video")
                scores["play_video"] = max(scores.get("play_video", 0.0), 0.98)
            else:
                selected_tool_names.add("play_music")
                scores["play_music"] = max(scores.get("play_music", 0.0), 0.98)

        # Precedence: if play_music or play_video is detected, suppress open_website unless an explicit URL/domain is given
        if ("play_music" in selected_tool_names or "play_video" in selected_tool_names) and "open_website" in selected_tool_names:
            if not any(domain_ext in lower for domain_ext in [".com", ".org", ".net", ".io", ".id", "http://", "https://"]):
                selected_tool_names.remove("open_website")
                scores.pop("open_website", None)

        # 3. Forced web search check
        if self.requires_forced_web_search(user_input):
            selected_tool_names.add("search_web")
            scores["search_web"] = max(scores.get("search_web", 0.0), 0.90)

        # 4. Token overlap scoring against tool definitions
        query_words = set(re.findall(r"\w+", lower))
        for tool in available_tools:
            t_name = tool.get("name", "")
            t_desc = tool.get("description", "").lower()
            desc_words = set(re.findall(r"\w+", t_desc))
            overlap = query_words.intersection(desc_words)

            if len(overlap) >= 2 and t_name not in selected_tool_names:
                score = len(overlap) * 0.15
                if score >= 0.30:
                    selected_tool_names.add(t_name)
                    scores[t_name] = round(score, 3)

        # 5. Fallback for unclassified queries
        if not selected_tool_names:
            if any(p.search(lower) for p in SELF_STATE_PATTERNS) or re.search(r"\b(?:bisa apa|fitur|kemampuan|kemampuanmu|limitasi|batasan)\b", lower):
                selected_tool_names.add("get_jarvis_capabilities")
                scores["get_jarvis_capabilities"] = 0.85
            else:
                # Default to web search & encyclopedia so the agent can discover any topic/name
                selected_tool_names.add("search_web")
                selected_tool_names.add("search_wikipedia")
                scores["search_web"] = 0.70
                scores["search_wikipedia"] = 0.65

        # Limit to top max_tools
        sorted_names = sorted(selected_tool_names, key=lambda n: scores.get(n, 0.0), reverse=True)[:max_tools]
        filtered_tools = [t for t in available_tools if t.get("name") in sorted_names]

        logger.debug(f"Routed tools for query '{user_input[:40]}...': {[t.get('name') for t in filtered_tools]}")
        return filtered_tools, scores
