"""Stand-alone Codebase & Document Indexer for JARVIS RAG Memory.

Migrated from:
- src/tools/ingest_codebase.js
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.memory.memory_store import memory_store
from config.settings import get_logger

logger = get_logger("BuildIndex")

IGNORED_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    "archive", "dist", "build", ".jarvis-conversations",
    "data/vector_db", "data/raw"
}

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".json", ".html", ".css", ".md", ".txt",
    ".yaml", ".yml", ".sh", ".ps1", ".toml", ".sql"
}


def chunk_file_content(content: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Splits file content into overlapping chunks for dense RAG retrieval."""
    if len(content) <= chunk_size:
        return [content]

    chunks = []
    start = 0
    while start < len(content):
        end = min(start + chunk_size, len(content))
        chunks.append(content[start:end])
        if end == len(content):
            break
        start += chunk_size - overlap
    return chunks


def build_codebase_index(directory_path: str) -> int:
    """Traverses a directory, chunks source files, and indexes into long-term memory."""
    target_dir = Path(directory_path).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        logger.error(f"Invalid directory path: {directory_path}")
        return 0

    logger.info(f"Starting codebase indexing for: {target_dir}")
    total_indexed = 0
    files_processed = 0

    for root, dirs, files in os.walk(target_dir):
        # Exclude ignored directories in-place
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]

        for file in files:
            file_path = Path(root) / file
            if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue

            try:
                rel_path = file_path.relative_to(BASE_DIR)
            except ValueError:
                rel_path = file_path

            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if not content.strip():
                    continue

                chunks = chunk_file_content(content)
                for i, chunk in enumerate(chunks):
                    doc_id = f"{rel_path}#part_{i+1}"
                    header = f"File: {rel_path} (Bagian {i+1}/{len(chunks)})\n"
                    indexed_text = header + chunk
                    memory_store.remember(
                        text=indexed_text,
                        doc_id=doc_id,
                        metadata={"file": str(rel_path), "chunk": i + 1}
                    )
                    total_indexed += 1

                files_processed += 1
            except Exception as e:
                logger.warn(f"Failed to index file {file_path}: {e}")

    logger.info(f"Indexing completed: {files_processed} files processed, {total_indexed} chunks saved to Vector DB.")
    return total_indexed


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else str(BASE_DIR / "src")
    print(f"Mengindeks direktori: {target}")
    indexed_count = build_codebase_index(target)
    print(f"Selesai! Berhasil mengindeks {indexed_count} potongan kode ke memori RAG.")
