"""Second Brain Autonomous Agent Tool Suite.

Orchestrates:
1. Microsoft MarkItDown for universal document & web ingestion.
2. Obsidian Local REST API (with local filesystem fallback) for knowledge graph notes.
3. ChromaDB PersistentClient for long-term semantic RAG indexing.
4. Autonomous 5-Step SOP pipeline: INGEST -> SYNTHESIZE -> STORE -> EMBED -> REPORT.
"""

import os
import re
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx

from config.settings import settings, get_logger

logger = get_logger("SecondBrain")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ==========================================
# 1. INGEST: Microsoft MarkItDown Parser
# ==========================================

def ingest_with_markitdown(source: str) -> str:
    """Extracts arbitrary documents (PDF, Word, PPTX, XLSX) or web URLs into clean Markdown."""
    clean_src = source.strip()
    logger.info(f"MarkItDown ingesting from source: '{clean_src}'")

    # Check if source is a GitHub URL -> route to specialized GitHub reader
    if "github.com/" in clean_src.lower():
        try:
            from src.tools.github_tool import read_github_repo
            import asyncio
            return asyncio.run(read_github_repo(clean_src))
        except Exception as e:
            logger.debug(f"GitHub reader delegation note: {e}")

    try:
        from markitdown import MarkItDown
        md = MarkItDown()

        # If it's a web URL, download first to a temp file or convert
        if clean_src.startswith("http://") or clean_src.startswith("https://"):
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.get(clean_src, headers=headers)
                resp.raise_for_status()
                
                # Check content type
                content_type = resp.headers.get("content-type", "").lower()
                suffix = ".html"
                if "pdf" in content_type:
                    suffix = ".pdf"
                elif "docx" in content_type or "word" in content_type:
                    suffix = ".docx"

                temp_path = BASE_DIR / "data" / "raw" / f"temp_ingest_{int(datetime.now().timestamp())}{suffix}"
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                temp_path.write_bytes(resp.content)

                try:
                    result = md.convert(str(temp_path))
                    text_content = result.text_content
                finally:
                    if temp_path.exists():
                        temp_path.unlink()

                return text_content.strip()

        # Local file path
        local_path = Path(clean_src)
        if not local_path.is_absolute():
            local_path = BASE_DIR / local_path

        if not local_path.exists():
            return f"❌ Berkas lokal tidak ditemukan: `{clean_src}`"

        result = md.convert(str(local_path))
        return result.text_content.strip()

    except Exception as e:
        logger.error(f"MarkItDown conversion error: {e}")
        # Resilient fallback: read as plain text
        try:
            p = Path(clean_src)
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass
        return f"❌ Gagal mengekstrak konten dengan MarkItDown: {str(e)}"


# ==========================================
# 2. SYNTHESIZE: Note Formatting & Entity Linking
# ==========================================

def synthesize_obsidian_note(
    raw_content: str,
    title: str,
    source: str,
    tags: Optional[List[str]] = None
) -> str:
    """Formats note with YAML frontmatter, bullet points, and [[WikiLink]] entities."""
    tags_list = tags or ["second_brain", "knowledge"]
    tags_yaml = ", ".join(f"[[{t.strip().lstrip('#')}]]" for t in tags_list)
    today = datetime.now().strftime("%Y-%m-%d")

    # Entity pattern detection for automatic Obsidian bidirectional linking
    entity_keywords = [
        "Python", "JavaScript", "TypeScript", "FastAPI", "React", "Node.js", "Electron",
        "ChromaDB", "MarkItDown", "Obsidian", "Ollama", "Docker", "Git", "GitHub",
        "Machine Learning", "Deep Learning", "Artificial Intelligence", "AI Agent",
        "RAG", "LLM", "Qwen", "Llama", "Mistral", "Vector Database", "Knowledge Graph"
    ]

    body = raw_content.strip()

    # Convert known technical entities into [[Entity]] backlinks if not already linked
    for entity in entity_keywords:
        pattern = rf"(?<!\[\[)\b{re.escape(entity)}\b(?!\]\])"
        body = re.sub(pattern, f"[[{entity}]]", body, count=3, flags=re.IGNORECASE)

    # Convert paragraphs into structured bullet points if not already bulleted
    lines = body.splitlines()
    bulleted_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            bulleted_lines.append("")
        elif stripped.startswith("#") or stripped.startswith("-") or stripped.startswith("*") or stripped.startswith(">"):
            bulleted_lines.append(stripped)
        else:
            bulleted_lines.append(f"- {stripped}")

    formatted_content = "\n".join(bulleted_lines)

    frontmatter = (
        "---\n"
        f'title: "{title}"\n'
        f'date: "{today}"\n'
        f"tags: [{tags_yaml}]\n"
        f'source: "{source}"\n'
        "---\n\n"
    )

    header = f"# {title}\n\n"
    meta_info = f"> [!NOTE]\n> **Sumber:** {source} | **Diindeks:** {today}\n\n"

    return frontmatter + header + meta_info + formatted_content


# ==========================================
# 3. STORE: Obsidian Local REST API + Vault Fallback
# ==========================================

async def store_to_obsidian(
    filename: str,
    note_markdown: str,
    folder: str = "Second Brain"
) -> Dict[str, Any]:
    """Saves note via Obsidian Local REST API with automatic local vault fallback."""
    safe_filename = "".join(c for c in filename if c not in '<>:"/\\|?*').strip()
    if not safe_filename.endswith(".md"):
        safe_filename += ".md"

    vault_rel_path = f"{folder}/{safe_filename}" if folder else safe_filename

    base_url = (getattr(settings.second_brain, "obsidian_base_url", "http://127.0.0.1:27124") or "http://127.0.0.1:27124").rstrip("/")
    api_key = getattr(settings.second_brain, "obsidian_api_key", None) or os.getenv("OBSIDIAN_API_KEY")

    headers = {"Content-Type": "text/markdown"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # 1. Attempt Obsidian Local REST API
    encoded_path = urllib.parse.quote(vault_rel_path)
    url = f"{base_url}/vault/{encoded_path}"
    logger.info(f"Attempting to write to Obsidian Local REST API: {url}")

    try:
        async with httpx.AsyncClient(timeout=4.0, verify=False) as client:
            resp = await client.put(url, headers=headers, content=note_markdown.encode("utf-8"))
            if resp.status_code in [200, 201, 204]:
                logger.info(f"Successfully stored note via Obsidian Local REST API: {vault_rel_path}")
                return {
                    "success": True,
                    "mode": "obsidian_api",
                    "path": vault_rel_path,
                    "url": url,
                    "message": f"Catatan berhasil disimpan ke Obsidian Vault via REST API: `{vault_rel_path}`"
                }
    except Exception as e:
        logger.warning(f"Obsidian Local REST API unreachable ({e}). Using local vault fallback...")

    # 2. Resilient Fallback: Direct Local Vault Directory
    vault_dir = BASE_DIR / getattr(settings.second_brain, "obsidian_vault_path", "data/second_brain/vault")
    target_dir = vault_dir / folder if folder else vault_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / safe_filename

    target_file.write_text(note_markdown, encoding="utf-8")
    logger.info(f"Stored note in local vault directory: {target_file}")

    return {
        "success": True,
        "mode": "vault_filesystem",
        "path": str(target_file),
        "message": f"Catatan disimpan ke Vault direktori lokal: `{target_file}` (Aplikasi Obsidian dapat langsung membukanya)."
    }


# ==========================================
# 4. EMBED: ChromaDB Vector Semantic Storage
# ==========================================

def embed_to_chromadb(
    title: str,
    content: str,
    source: str,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Chunks and embeds note content into local ChromaDB 'second_brain' collection."""
    import chromadb

    persist_dir = str(BASE_DIR / getattr(settings.second_brain, "chroma_persist_dir", "data/second_brain/chromadb"))
    collection_name = getattr(settings.second_brain, "chroma_collection", "second_brain")

    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    # Chunk content into ~600 character blocks
    chunk_size = 600
    chunk_overlap = 100
    clean_text = re.sub(r"^---[\s\S]*?---\n*", "", content).strip()  # Strip frontmatter for pure semantics

    chunks = []
    start = 0
    while start < len(clean_text):
        end = start + chunk_size
        chunk = clean_text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += (chunk_size - chunk_overlap)

    if not chunks:
        chunks = [clean_text or title]

    today = datetime.now().strftime("%Y-%m-%d")
    tag_str = ", ".join(tags or ["knowledge"])

    doc_ids = []
    documents = []
    metadatas = []

    safe_title_id = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:30]
    timestamp = int(datetime.now().timestamp())

    for idx, chunk in enumerate(chunks):
        chunk_id = f"sb_{safe_title_id}_{timestamp}_{idx}"
        doc_ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "title": title,
            "source": source,
            "date": today,
            "tags": tag_str,
            "chunk_index": idx,
            "total_chunks": len(chunks)
        })

    collection.upsert(
        ids=doc_ids,
        documents=documents,
        metadatas=metadatas
    )

    logger.info(f"Upserted {len(chunks)} chunks into ChromaDB '{collection_name}' collection.")
    return {
        "success": True,
        "collection": collection_name,
        "chunks_indexed": len(chunks),
        "total_documents": collection.count()
    }


def search_second_brain(query: str, top_k: int = 4) -> str:
    """Semantic vector search across stored notes in ChromaDB."""
    import chromadb

    persist_dir = str(BASE_DIR / getattr(settings.second_brain, "chroma_persist_dir", "data/second_brain/chromadb"))
    collection_name = getattr(settings.second_brain, "chroma_collection", "second_brain")

    if not Path(persist_dir).exists():
        return "🧠 **Second Brain masih kosong.** Belum ada catatan yang diindeks ke ChromaDB."

    try:
        client = chromadb.PersistentClient(path=persist_dir)
        collection = client.get_or_create_collection(name=collection_name)

        if collection.count() == 0:
            return "🧠 **Second Brain masih kosong.** Belum ada catatan yang tersimpan."

        results = collection.query(
            query_texts=[query.strip()],
            n_results=min(top_k, collection.count())
        )

        formatted = []
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0] if "distances" in results else [0.0] * len(docs)

        for doc, meta, dist in zip(docs, metas, distances):
            t = meta.get("title", "Catatan")
            s = meta.get("source", "N/A")
            d = meta.get("date", "")
            tags = meta.get("tags", "")
            similarity = max(0.0, 1.0 - (dist if dist is not None else 0.5))

            formatted.append(
                f"### 📝 [[{t}]] *(Relevansi: {similarity:.1%})*\n"
                f"- **Sumber:** {s} | **Tanggal:** {d} | **Tags:** `{tags}`\n\n"
                f"{doc}\n"
            )

        return f"🧠 **Hasil Penelusuran Second Brain (ChromaDB):**\n\n" + "\n---\n".join(formatted)

    except Exception as e:
        logger.error(f"Search second brain error: {e}")
        return f"❌ Gagal mencari di Second Brain: {str(e)}"


# ==========================================
# 5. SOP PIPELINE: Autonomous Orchestration
# ==========================================

async def process_second_brain_pipeline(
    source: str,
    title: Optional[str] = None,
    tags: Optional[str] = None
) -> str:
    """Autonomous 5-step SOP: INGEST -> SYNTHESIZE -> STORE -> EMBED -> REPORT."""
    clean_src = source.strip()
    logger.info(f"Starting Second Brain SOP for: {clean_src}")

    # Derive sensible title if none provided
    note_title = title.strip() if title and title.strip() else ""
    if not note_title:
        if clean_src.startswith("http"):
            parsed = urllib.parse.urlparse(clean_src)
            path_parts = [p for p in parsed.path.split("/") if p]
            note_title = path_parts[-1].replace("-", " ").replace("_", " ").title() if path_parts else parsed.netloc
        else:
            note_title = Path(clean_src).stem.replace("-", " ").replace("_", " ").title()

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else ["second_brain", "knowledge"]

    # STEP 1: INGEST
    extracted_md = ingest_with_markitdown(clean_src)
    if extracted_md.startswith("❌"):
        return f"❌ **Tahap Ingest Gagal:** {extracted_md}"

    # STEP 2: SYNTHESIZE
    synthesized_note = synthesize_obsidian_note(
        raw_content=extracted_md,
        title=note_title,
        source=clean_src,
        tags=tag_list
    )

    # STEP 3: STORE (Obsidian)
    obsidian_res = await store_to_obsidian(
        filename=note_title,
        note_markdown=synthesized_note,
        folder="Second Brain"
    )

    # STEP 4: EMBED (ChromaDB)
    chroma_res = embed_to_chromadb(
        title=note_title,
        content=synthesized_note,
        source=clean_src,
        tags=tag_list
    )

    # STEP 5: REPORT
    return (
        f"🎉 **Operasi Second Brain Selesai!**\n\n"
        f"### 📋 Rincian Eksekusi:\n"
        f"- 📝 **Judul Catatan:** `[[{note_title}]]`\n"
        f"- 🌐 **Sumber Asal:** {clean_src}\n"
        f"- 🏷️ **Tags:** {', '.join(f'`{t}`' for t in tag_list)}\n"
        f"- 🗄️ **Penyimpanan Obsidian:** {obsidian_res.get('message')}\n"
        f"- 🧠 **Indeksasi ChromaDB:** Berhasil menyimpan {chroma_res.get('chunks_indexed')} potongan teks (Total koleksi: {chroma_res.get('total_documents')} dokumen).\n\n"
        f"Catatan ini sekarang tersedia di antarmuka graf Obsidian dan memori semantik RAG JARVIS."
    )


# ==========================================
# Tool Definitions for Registry
# ==========================================

TOOL_DEFINITIONS = [
    {
        "name": "process_second_brain_pipeline",
        "description": "Menjalankan pipeline otonom 5 langkah (INGEST -> SYNTHESIZE -> STORE -> EMBED -> REPORT) untuk meriset dokumen/URL, menyimpannya ke Obsidian Vault dengan format frontmatter + [[WikiLink]], dan mengindeksnya ke ChromaDB.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "URL situs web, URL GitHub, atau path file dokumen lokal (PDF/DOCX/TXT)"
                },
                "title": {
                    "type": "string",
                    "description": "Judul catatan (opsional, otomatis dibuat jika kosong)"
                },
                "tags": {
                    "type": "string",
                    "description": "Daftar tag dipisahkan koma (contoh: 'ai, machine-learning, notes')"
                }
            },
            "required": ["source"]
        },
        "handler": process_second_brain_pipeline
    },
    {
        "name": "ingest_with_markitdown",
        "description": "Mengekstrak dan mengonversi konten berkas lokal (PDF, Word DOCX, PPTX, XLSX) atau URL web menjadi Markdown bersih menggunakan Microsoft MarkItDown.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Path berkas atau URL halaman web"
                }
            },
            "required": ["source"]
        },
        "handler": ingest_with_markitdown
    },
    {
        "name": "search_second_brain",
        "description": "Mencari dan menelusuri memori semantik catatan masa lalu di Second Brain (ChromaDB) untuk menjawab pertanyaan berbasis RAG.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Topik atau pertanyaan yang ingin dicari di Second Brain"
                }
            },
            "required": ["query"]
        },
        "handler": search_second_brain
    }
]
