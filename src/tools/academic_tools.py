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
    """Detects meeting number (e.g. P01, P2, Pertemuan 3, Minggu 4) from filename or text."""
    pattern = re.compile(r"(?:pertemuan|meeting|minggu|sesi|p)[_\-\s]?0?([1-9]|1[0-6])(?=[^0-9a-zA-Z]|$)", re.IGNORECASE)
    match = pattern.search(filename_or_text)
    if match:
        num = int(match.group(1))
        return f"P{num:02d}"
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
    }
]
