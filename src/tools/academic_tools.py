"""Academic Knowledge Base & Multi-Course RAG Tools for JARVIS.

Designed for university students:
- Batch ingests multi-course lecture materials (PDF, DOCX, PPTX, TXT, MD) using MarkItDown.
- Tags every vector chunk with structured metadata: course_name, meeting_number, document_type, filename.
- Provides isolated, filtered retrieval per course and per meeting (zero cross-contamination).
- Generates interactive study quizzes, exam prep summaries, and assignment review guides.
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from config.settings import settings, get_logger
from src.memory.memory_store import memory_store

logger = get_logger("AcademicTools")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_COURSES_DIR = BASE_DIR / "data" / "kuliah"


def extract_meeting_number(filename_or_text: str) -> Optional[str]:
    """Detects meeting number (e.g. P01, P2, Pertemuan 3, P07A, P07B) from filename or text."""
    pattern = re.compile(r"(?:pertemuan|meeting|minggu|sesi|p)[_\-\s]?0?([1-9]|1[0-6])([a-zA-Z])?(?=[^0-9a-zA-Z]|$)", re.IGNORECASE)
    match = pattern.search(filename_or_text)
    if match:
        num = int(match.group(1))
        suffix = match.group(2).upper() if match.group(2) else ""
        return f"P{num:02d}{suffix}"
    return None


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    """Splits text into coherent paragraph-aware chunks for vector storage."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_length = 0

    for para in paragraphs:
        cleaned_para = para.strip()
        if not cleaned_para:
            continue
        words = len(cleaned_para.split())
        if current_length + words > chunk_size and current_chunk:
            chunk_body = "\n\n".join(current_chunk)
            chunks.append(chunk_body)
            # Retain last paragraph for context overlap
            current_chunk = [current_chunk[-1]] if len(current_chunk) > 1 else []
            current_length = len(current_chunk[0].split()) if current_chunk else 0

        current_chunk.append(cleaned_para)
        current_length += words

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    return chunks if chunks else [text]


def ingest_course_materials(folder_or_file_path: str = "", course_name: str = "") -> str:
    """Ingests lecture slides and documents into Academic RAG with course and meeting metadata.

    Args:
        folder_or_file_path: Path to course folder (e.g., 'data/kuliah/Sistem_Operasi') or specific file.
        course_name: Optional explicit name of the course. Auto-detected from directory if omitted.
    """
    raw_input = folder_or_file_path.strip()
    target_path = Path(raw_input) if raw_input else DEFAULT_COURSES_DIR

    # Intelligent multi-layer path resolution:
    if not target_path.is_absolute():
        resolved_at_root = BASE_DIR / target_path
        if resolved_at_root.exists():
            target_path = resolved_at_root
        else:
            # Check under data/kuliah/ with exact name or space-to-underscore
            direct_course_path = DEFAULT_COURSES_DIR / raw_input
            underscore_course_path = DEFAULT_COURSES_DIR / raw_input.replace(" ", "_")

            if direct_course_path.exists():
                target_path = direct_course_path
            elif underscore_course_path.exists():
                target_path = underscore_course_path
            else:
                # Fuzzy match subdirectories under data/kuliah/
                matched_dir = None
                clean_input = re.sub(r"[^a-zA-Z0-9]", "", raw_input.lower())
                if clean_input and DEFAULT_COURSES_DIR.exists():
                    for sub in DEFAULT_COURSES_DIR.iterdir():
                        if sub.is_dir():
                            clean_sub = re.sub(r"[^a-zA-Z0-9]", "", sub.name.lower())
                            if clean_input in clean_sub or clean_sub in clean_input:
                                matched_dir = sub
                                break
                if matched_dir:
                    target_path = matched_dir
                elif not raw_input:
                    target_path = DEFAULT_COURSES_DIR
                else:
                    target_path = resolved_at_root

    if not target_path.exists():
        # Provide helpful guidance with list of existing courses
        existing = [d.name for d in DEFAULT_COURSES_DIR.iterdir() if d.is_dir()] if DEFAULT_COURSES_DIR.exists() else []
        avail_str = ", ".join(f"`{e}`" for e in existing) if existing else "Belum ada folder di data/kuliah/"
        return (
            f"❌ Direktori atau berkas materi kuliah tidak ditemukan di: `{target_path}`.\n"
            f"Pastikan berkas berada di dalam folder `data/kuliah/`.\n"
            f"Folder mata kuliah yang terdeteksi saat ini: {avail_str}."
        )

    # If course_name was empty, derive from target_path folder name if inside data/kuliah
    if not course_name and target_path != DEFAULT_COURSES_DIR:
        course_name = target_path.name.replace("_", " ")

    # Identify files to process
    files_to_process = []
    supported_extensions = {".pdf", ".docx", ".pptx", ".txt", ".md"}

    if target_path.is_file():
        if target_path.suffix.lower() in supported_extensions:
            files_to_process.append(target_path)
    else:
        for ext in supported_extensions:
            files_to_process.extend(target_path.rglob(f"*{ext}"))

    if not files_to_process:
        return f"⚠️ Tidak ditemukan berkas materi kuliah yang didukung (.pdf, .docx, .pptx, .txt, .md) di `{target_path}`."

    # Load MarkItDown parser
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
    except Exception as e:
        logger.error(f"MarkItDown import error: {e}")
        md = None

    total_chunks_stored = 0
    processed_files_count = 0
    course_meetings_found = set()
    batch_docs: List[Dict[str, Any]] = []

    for file_path in files_to_process:
        # Determine course name: explicit, or parent folder name
        derived_course = course_name.strip()
        if not derived_course:
            # If target_path was a folder inside data/kuliah, use that folder's name
            relative = file_path.relative_to(DEFAULT_COURSES_DIR) if DEFAULT_COURSES_DIR in file_path.parents else None
            derived_course = relative.parts[0] if relative and len(relative.parts) > 1 else file_path.parent.name
        
        # Determine meeting number
        meeting_tag = extract_meeting_number(file_path.stem) or "Umum"
        if meeting_tag != "Umum":
            course_meetings_found.add(meeting_tag)

        # Extract text content
        extracted_text = ""
        if md:
            try:
                res = md.convert(str(file_path))
                extracted_text = res.text_content
            except Exception as e:
                logger.warning(f"MarkItDown failed on '{file_path.name}': {e}. Falling back to plain text read.")

        if not extracted_text:
            try:
                extracted_text = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

        if not extracted_text.strip():
            continue

        # Chunk and prepare for batch indexing
        chunks = chunk_text(extracted_text, chunk_size=500, overlap=80)
        for i, chunk in enumerate(chunks, start=1):
            metadata = {
                "source": "academic",
                "course": derived_course.replace("_", " "),
                "meeting": meeting_tag,
                "file_name": file_path.name,
                "chunk_index": i
            }
            doc_id = f"acad_{derived_course[:6]}_{meeting_tag}_{file_path.stem[:8]}_{i}"
            batch_docs.append({
                "id": doc_id,
                "text": f"[{derived_course.replace('_', ' ')} - {meeting_tag} | {file_path.name}]\n{chunk}",
                "metadata": metadata
            })

        processed_files_count += 1

    if batch_docs:
        total_chunks_stored = memory_store.remember_batch(batch_docs)

    sorted_meetings = sorted(list(course_meetings_found))
    meetings_summary = ", ".join(sorted_meetings) if sorted_meetings else "Dokumen umum / Silabus"

    report = f"""✅ **Materi Kuliah Berhasil Diindeks ke Academic Knowledge Base:**
- **Mata Kuliah**: `{course_name.replace('_', ' ') if course_name else 'Multi-Mata Kuliah'}`
- **Total Berkas Diproses**: {processed_files_count} berkas
- **Segmen Vektor Tersimpan**: {total_chunks_stored} chunks (in-memory RAG)
- **Pertemuan Terdeteksi**: {meetings_summary}

💡 *Kini Anda dapat langsung menanyakan materi atau meminta kuis latihan ujian (misal: "Jelaskan materi pertemuan 2 {course_name}" atau "Buatkan kuis latihan {course_name}").*"""
    return report


def search_course_materials(query: str, course_name: str = "", meeting: str = "") -> str:
    """Searches lecture slides, assignments, and notes with course and meeting filters.

    Args:
        query: What concept, topic, or question to look up.
        course_name: Optional course filter to avoid cross-course confusion.
        meeting: Optional meeting tag (e.g. 'P02', 'P03', 'Pertemuan 2').
    """
    clean_query = query.strip()
    filter_dict: Dict[str, Any] = {"source": "academic"}

    if course_name.strip():
        filter_dict["course"] = course_name.strip().replace("_", " ")

    if meeting.strip():
        norm_meeting = extract_meeting_number(meeting) or meeting.strip()
        filter_dict["meeting"] = norm_meeting

    # Search with metadata filtering
    results = memory_store.long_term.search_memory(
        query_text=clean_query,
        top_k=5,
        filter_metadata=filter_dict if len(filter_dict) > 1 else None
    )

    if not results:
        # Fallback to broader search without meeting filter if too strict
        if "meeting" in filter_dict:
            filter_dict.pop("meeting")
            results = memory_store.long_term.search_memory(query_text=clean_query, top_k=5, filter_metadata=filter_dict)

    if not results:
        return f"Tidak ditemukan materi kuliah yang cocok untuk kueri: '{clean_query}'. Pastikan materi kuliah terkait sudah dimasukkan ke `data/kuliah/` dan diindeks."

    response_parts = [f"📚 **Hasil Pencarian Materi Kuliah ({len(results)} segmen paling relevan):**\n"]
    for i, res in enumerate(results, start=1):
        meta = res.get("metadata", {})
        c_name = meta.get("course", "Kuliah")
        m_tag = meta.get("meeting", "-")
        f_name = meta.get("file_name", "Berkas")
        text_snippet = res.get("text", "").strip()

        response_parts.append(f"**[{i}] {c_name} — {m_tag}** (`{f_name}`):")
        response_parts.append(f"> {text_snippet[:600]}...\n")

    return "\n".join(response_parts)


def list_enrolled_courses(query: str = "") -> str:
    """Lists all courses currently detected in data/kuliah/ and indexed in Academic RAG."""
    courses_found = []
    
    # 1. Check filesystem
    if DEFAULT_COURSES_DIR.exists():
        for item in DEFAULT_COURSES_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                files = list(item.glob("*.*"))
                courses_found.append({
                    "name": item.name.replace("_", " "),
                    "folder": item.name,
                    "files_count": len(files)
                })

    if not courses_found:
        return f"Belum ada mata kuliah yang didaftarkan di `{DEFAULT_COURSES_DIR}`. Silakan buat sub-folder per mata kuliah (misal: `data/kuliah/Sistem_Operasi`) lalu letakkan slide PDF di dalamnya."

    output_lines = ["📋 **Daftar Mata Kuliah di Academic Knowledge Base:**\n"]
    for i, c in enumerate(courses_found, start=1):
        output_lines.append(f"{i}. **{c['name']}** — `{c['files_count']} berkas materi` (Folder: `data/kuliah/{c['folder']}`)")

    output_lines.append("\n💡 *Gunakan tool `ingest_course_materials` untuk memperbarui indeks memori setelah menambahkan slide baru.*")
    return "\n".join(output_lines)


def generate_study_quiz(query: str, course_name: str = "", meeting: str = "") -> str:
    """Generates study questions and practice exam problems from indexed course materials."""
    context = search_course_materials(query=query, course_name=course_name, meeting=meeting)
    if "Tidak ditemukan" in context:
        return context

    return f"""📚 **Konteks Materi Kuliah untuk Kuis Latihan:**\n{context}\n
Instruksi Kuis:
Model dipersilakan merumuskan 3-5 soal kuis latihan (Pilihan Ganda & Analisis Kasus) berdasarkan konteks materi di atas, lengkap dengan kunci jawaban dan pembahasan komprehensif."""


def summarize_course_materials(
    folder_or_course_name: str = "",
    meeting_range: str = "",
    focus_topic: str = "",
    course_name: str = ""
) -> str:
    """Produces a comprehensive, holistic summary across all course meetings (P01 to Px),
    synthesizing overarching themes, curriculum progression, and conceptual connections.

    Args:
        folder_or_course_name: Course name or folder path (e.g. 'Cloud Computing' or 'data/kuliah/Cloud_Computing').
        meeting_range: Optional range of meetings (e.g. 'P01-P07', 'semua').
        focus_topic: Optional specific topic to trace across all meetings.
        course_name: Optional explicit name if folder is passed.
    """
    raw_input = (folder_or_course_name or course_name).strip()
    target_path = Path(raw_input) if raw_input else DEFAULT_COURSES_DIR

    # Multi-layer path resolution
    if not target_path.is_absolute():
        resolved_at_root = BASE_DIR / target_path
        if resolved_at_root.exists() and resolved_at_root != BASE_DIR:
            target_path = resolved_at_root
        else:
            direct_course_path = DEFAULT_COURSES_DIR / raw_input
            underscore_course_path = DEFAULT_COURSES_DIR / raw_input.replace(" ", "_")

            if direct_course_path.exists() and raw_input:
                target_path = direct_course_path
            elif underscore_course_path.exists() and raw_input:
                target_path = underscore_course_path
            else:
                matched_dir = None
                clean_input = re.sub(r"[^a-zA-Z0-9]", "", raw_input.lower())
                if clean_input and DEFAULT_COURSES_DIR.exists():
                    for sub in DEFAULT_COURSES_DIR.iterdir():
                        if sub.is_dir():
                            clean_sub = re.sub(r"[^a-zA-Z0-9]", "", sub.name.lower())
                            if clean_input in clean_sub or clean_sub in clean_input:
                                matched_dir = sub
                                break
                if matched_dir:
                    target_path = matched_dir
                elif not raw_input:
                    available = [d for d in DEFAULT_COURSES_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")] if DEFAULT_COURSES_DIR.exists() else []
                    if len(available) == 1:
                        target_path = available[0]
                    else:
                        target_path = DEFAULT_COURSES_DIR
                else:
                    target_path = resolved_at_root

    if not target_path.exists() or target_path == DEFAULT_COURSES_DIR:
        existing = [d.name for d in DEFAULT_COURSES_DIR.iterdir() if d.is_dir()] if DEFAULT_COURSES_DIR.exists() else []
        avail_str = ", ".join(f"`{e}`" for e in existing) if existing else "Belum ada folder di data/kuliah/"
        return (
            f"❌ Direktori mata kuliah `{course_name}` tidak ditemukan.\n"
            f"Folder mata kuliah yang terdeteksi di `data/kuliah/`: {avail_str}."
        )

    resolved_course_name = target_path.name.replace("_", " ")

    # Check for cached manifest
    manifest_file = target_path / "_course_manifest.json"
    manifest_data = {}
    if manifest_file.exists():
        try:
            import json
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            manifest_data = {}

    supported_extensions = {".pdf", ".pptx", ".docx", ".txt", ".md"}
    raw_files = [f for f in target_path.iterdir() if f.is_file() and f.suffix.lower() in supported_extensions and not f.name.startswith(("_", "."))]

    def sort_key(f: Path):
        m = extract_meeting_number(f.stem)
        if not m:
            return (999, "", f.name)
        digits = re.findall(r"\d+", m)
        num = int(digits[0]) if digits else 999
        suffix = m[3:] if len(m) > 3 else ""
        return (num, suffix, f.name)

    files = sorted(raw_files, key=sort_key)
    if not files:
        return f"Mata kuliah `{resolved_course_name}` belum memiliki berkas materi (PDF/PPTX) di `{target_path}`."

    cached_meetings = manifest_data.get("meetings", {})
    updated_meetings = {}

    md = None
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
    except Exception:
        pass

    for file_path in files:
        m_tag = extract_meeting_number(file_path.stem) or "Umum"
        if m_tag in cached_meetings and cached_meetings[m_tag].get("topics"):
            updated_meetings[m_tag] = cached_meetings[m_tag]
            continue

        chapter_title = ""
        key_topics = []
        try:
            extracted_text = ""
            if md:
                res = md.convert(str(file_path))
                extracted_text = res.text_content
            if not extracted_text:
                extracted_text = file_path.read_text(encoding="utf-8", errors="ignore")

            lines = [l.strip() for l in extracted_text.splitlines() if l.strip() and not l.startswith("![") and not l.startswith("<!--")]
            for l in lines[:10]:
                if any(k in l.lower() for k in ["chapter", "bab", "topik", "pengantar", "materi", "introduction", "arsitektur", "architecture"]):
                    chapter_title = l
                    break
            if not chapter_title and lines:
                chapter_title = lines[0]

            for l in lines[1:50]:
                if len(l) > 5 and len(l) < 80 and not l.isdigit() and not l.startswith("http"):
                    if l not in key_topics and len(key_topics) < 5:
                        key_topics.append(l)
        except Exception:
            chapter_title = file_path.stem.replace("_", " ")

        updated_meetings[m_tag] = {
            "file": file_path.name,
            "title": chapter_title or file_path.stem.replace("_", " "),
            "topics": key_topics
        }

    # Save manifest cache
    try:
        import json
        manifest_data = {
            "course": resolved_course_name,
            "total_meetings": len(updated_meetings),
            "meetings": updated_meetings
        }
        manifest_file.write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    meetings_list = []
    for m_tag, info in updated_meetings.items():
        topics_str = ", ".join(info["topics"][:3]) if info.get("topics") else "Konsep fundamental materi"
        meetings_list.append(f"- **{m_tag}** (`{info['file']}`): **{info['title']}**\n  *Fokus Topik*: {topics_str}")

    meetings_block = "\n".join(meetings_list)
    first_m = list(updated_meetings.keys())[0]
    last_m = list(updated_meetings.keys())[-1]

    return f"""📚 **Peta Kurikulum & Materi Lengkap Perkuliahan:**
- **Mata Kuliah**: `{resolved_course_name}`
- **Total Materi Pertemuan**: {len(updated_meetings)} Pertemuan
- **Cakupan**: {first_m} s.d. {last_m}

### 📌 Kronologi & Garis Waktu Pertemuan:
{meetings_block}

---
💡 **Instruksi Rangkuman Terpadu:**
Sintesiskan materi di atas menjadi **SATU RANGKUMAN UTUH YANG MENGALIR DAN BERKESINAMBUNGAN** (Holistic Big-Picture Narrative).
- Kelompokkan ke dalam 4 Pilar Konseptual Utama (Fondasi Filosofis & Arsitektur, Komputasi & Komunikasi Antar-Node, Sinkronisasi & Penamaan, serta Keandalan Skala Besar & Toleransi Kegagalan).
- Jelaskan hubungan sebab-akibat dan benang merah: bagaimana materi pertemuan awal menjadi pondasi bagi materi pertemuan selanjutnya.
- Berikan intisari penting yang harus dikuasai mahasiswa untuk ujian dan pemahaman praktis di dunia industri."""


# ==========================================
# Tool Definitions for Orchestrator Registration
# ==========================================

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "ingest_course_materials",
        "description": "Membaca dan mengindeks berkas materi kuliah (PDF slide, docx, pptx) ke dalam Academic RAG dengan metadata nama mata kuliah dan nomor pertemuan.",
        "handler": lambda query="", **kwargs: ingest_course_materials(
            folder_or_file_path=kwargs.get("folder_or_file_path", query),
            course_name=kwargs.get("course_name", "")
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "folder_or_file_path": {"type": "string", "description": "Folder mata kuliah di data/kuliah atau path berkas spesifik"},
                "course_name": {"type": "string", "description": "Nama mata kuliah"}
            }
        }
    },
    {
        "name": "search_course_materials",
        "description": "Mencari materi kuliah, slide, catatan, atau tugas spesifik per-mata kuliah dan per-pertemuan tanpa tercampur dengan mata kuliah lain.",
        "handler": lambda query="", **kwargs: search_course_materials(
            query=kwargs.get("query", query),
            course_name=kwargs.get("course_name", ""),
            meeting=kwargs.get("meeting", "")
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topik, konsep, atau pertanyaan materi kuliah"},
                "course_name": {"type": "string", "description": "Filter nama mata kuliah (opsional)"},
                "meeting": {"type": "string", "description": "Filter pertemuan (misal: 'P01', 'Pertemuan 2')"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "list_enrolled_courses",
        "description": "Menampilkan daftar seluruh mata kuliah dan jumlah berkas materi yang tersimpan di direktori data/kuliah.",
        "handler": lambda query="", **kwargs: list_enrolled_courses(query),
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "generate_study_quiz",
        "description": "Merumuskan soal kuis latihan ujian (UTS/UAS) dan analisis kasus berdasarkan materi kuliah yang tersimpan di RAG.",
        "handler": lambda query="", **kwargs: generate_study_quiz(
            query=kwargs.get("query", query),
            course_name=kwargs.get("course_name", ""),
            meeting=kwargs.get("meeting", "")
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topik bahasan kuis"},
                "course_name": {"type": "string", "description": "Mata kuliah"},
                "meeting": {"type": "string", "description": "Pertemuan ke-X"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "summarize_course_materials",
        "description": "Merangkum seluruh materi kuliah dari pertemuan awal hingga akhir (P1 s.d. Px) menjadi satu kesatuan narasi holistik yang berkesinambungan tanpa terpecah-pecah.",
        "handler": lambda query="", **kwargs: summarize_course_materials(
            course_name=kwargs.get("course_name", query),
            meeting_range=kwargs.get("meeting_range", ""),
            focus_topic=kwargs.get("focus_topic", "")
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "course_name": {"type": "string", "description": "Nama mata kuliah yang ingin dirangkum (misal: 'Cloud Computing')"},
                "meeting_range": {"type": "string", "description": "Rentang pertemuan opsional (misal: 'P01-P07' atau 'semua')"},
                "focus_topic": {"type": "string", "description": "Topik bahasan khusus yang ingin disorot across semua pertemuan"}
            },
            "required": ["course_name"]
        }
    }
]
