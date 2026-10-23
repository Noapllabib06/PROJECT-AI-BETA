"""Unit tests for Second Brain Autonomous Agent (MarkItDown, Obsidian, ChromaDB)."""

import os
import shutil
import asyncio
from pathlib import Path
import pytest

from src.tools.second_brain import (
    synthesize_obsidian_note,
    store_to_obsidian,
    embed_to_chromadb,
    search_second_brain,
    ingest_with_markitdown,
    process_second_brain_pipeline
)
from src.workflows.task_router import TaskRouter

BASE_DIR = Path(__file__).resolve().parent.parent


def test_synthesize_obsidian_note():
    raw_content = "Python is an interpreted programming language used heavily in Machine Learning."
    title = "Pengenalan Python"
    source = "https://example.com/python"
    tags = ["python", "ai"]

    note = synthesize_obsidian_note(raw_content, title, source, tags)

    assert "---" in note
    assert 'title: "Pengenalan Python"' in note
    assert "source: \"https://example.com/python\"" in note
    assert "[[python]]" in note or "[[ai]]" in note
    assert "[[Python]]" in note
    assert "[[Machine Learning]]" in note
    assert "- " in note  # Bullet points


def test_store_to_obsidian_filesystem_fallback():
    title = "Test Note Obsidian"
    content = "# Test Note\n- Point 1\n- Point 2"

    result = asyncio.run(store_to_obsidian(title, content, folder="TestFolder"))
    assert result["success"] is True
    assert "path" in result
    assert "Catatan" in result["message"]


def test_embed_and_search_chromadb():
    title = "Quantum Computing Basics"
    content = "Quantum computing uses qubits and superposition to solve complex cryptographic problems."
    source = "doc_source"
    tags = ["quantum", "physics"]

    embed_res = embed_to_chromadb(title, content, source, tags)
    assert embed_res["success"] is True
    assert embed_res["chunks_indexed"] >= 1

    search_res = search_second_brain("qubits and superposition")
    assert "Quantum Computing Basics" in search_res
    assert "qubits" in search_res.lower()


def test_ingest_with_markitdown_local_file(tmp_path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("Markdown conversion test content using MarkItDown.", encoding="utf-8")

    extracted = ingest_with_markitdown(str(test_file))
    assert "Markdown conversion test content" in extracted


def test_process_second_brain_pipeline(tmp_path):
    test_file = tmp_path / "research_topic.txt"
    test_file.write_text("Docker enables containerization for scalable microservices in Node.js and Python.", encoding="utf-8")

    report = asyncio.run(process_second_brain_pipeline(
        source=str(test_file),
        title="Riset Docker",
        tags="docker,devops"
    ))

    assert "Operasi Second Brain Selesai" in report
    assert "[[Riset Docker]]" in report

    # Verify searchable in ChromaDB
    search_res = search_second_brain("containerization microservices")
    assert "Riset Docker" in search_res


def test_task_router_routes_second_brain():
    router = TaskRouter()
    mock_tools = [
        {"name": "process_second_brain_pipeline", "description": "Second brain pipeline"},
        {"name": "search_second_brain", "description": "Search notes"},
        {"name": "search_web", "description": "Web search"}
    ]

    selected, scores = router.route_tools("tolong simpan artikel ini ke second brain saya", mock_tools)
    selected_names = [t["name"] for t in selected]
    assert "process_second_brain_pipeline" in selected_names

    selected2, _ = router.route_tools("cari di obsidian catatan tentang python", mock_tools)
    selected2_names = [t["name"] for t in selected2]
    assert "search_second_brain" in selected2_names
