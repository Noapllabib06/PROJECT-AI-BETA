"""Tests for Academic Knowledge Base and Multi-Course RAG Suite."""

import pytest
from pathlib import Path
from src.tools.academic_tools import (
    extract_meeting_number,
    chunk_text,
    ingest_course_materials,
    search_course_materials,
    list_enrolled_courses,
    generate_study_quiz,
    summarize_course_materials
)
from src.tools import get_all_tools
from src.workflows.task_router import TaskRouter
from src.memory.memory_store import memory_store


def test_extract_meeting_number():
    assert extract_meeting_number("P01_Pengantar_OS.pdf") == "P01"
    assert extract_meeting_number("Pertemuan_3_Memory_Management.docx") == "P03"
    assert extract_meeting_number("minggu-5-normalisasi.pptx") == "P05"
    assert extract_meeting_number("sesi 12 distributed systems.pdf") == "P12"
    assert extract_meeting_number("P07A.pptx") == "P07A"
    assert extract_meeting_number("P07B.pptx") == "P07B"
    assert extract_meeting_number("silabus_lengkap.pdf") is None


def test_chunk_text():
    sample = "Paragraf satu mengenai OS.\n\nParagraf dua mengenai Process dan Thread.\n\nParagraf tiga mengenai Memory."
    chunks = chunk_text(sample, chunk_size=50, overlap=10)
    assert len(chunks) >= 1
    assert "Paragraf satu" in chunks[0]


def test_academic_ingest_and_filtered_search(tmp_path):
    # Setup temporary course folder
    os_dir = tmp_path / "data" / "kuliah" / "Sistem_Operasi"
    os_dir.mkdir(parents=True, exist_ok=True)
    
    file_p1 = os_dir / "P01_Pengantar_OS.txt"
    file_p1.write_text(
        "Sistem Operasi bertindak sebagai jembatan perantara antara perangkat keras dan pengguna. Contoh kernel: Linux, Windows NT.",
        encoding="utf-8"
    )
    
    file_p2 = os_dir / "P02_Proses_dan_Thread.txt"
    file_p2.write_text(
        "Proses adalah program yang sedang dieksekusi. Thread adalah unit terkecil pemanfaatan CPU di dalam proses. Multithreading meningkatkan performa.",
        encoding="utf-8"
    )

    # Ingest course folder
    report = ingest_course_materials(str(os_dir), course_name="Sistem Operasi")
    assert "Berhasil Diindeks" in report
    assert "Sistem Operasi" in report
    assert "2 berkas" in report

    # Test filtered search on P02
    search_res = search_course_materials(query="apa itu thread", course_name="Sistem Operasi", meeting="P02")
    assert "Sistem Operasi" in search_res
    assert "P02" in search_res
    assert "unit terkecil pemanfaatan CPU" in search_res


def test_summarize_course_materials(tmp_path):
    cloud_dir = tmp_path / "data" / "kuliah" / "Cloud_Computing"
    cloud_dir.mkdir(parents=True, exist_ok=True)

    (cloud_dir / "P01_Intro.txt").write_text("Chapter 01: Introduction to Distributed Systems and Cloud Computing", encoding="utf-8")
    (cloud_dir / "P02_Arch.txt").write_text("Chapter 02: Architectures and Layering Models", encoding="utf-8")

    summary = summarize_course_materials(folder_or_course_name=str(cloud_dir), course_name="Cloud Computing")
    assert "Peta Kurikulum & Materi Lengkap Perkuliahan" in summary
    assert "Cloud Computing" in summary
    assert "P01" in summary
    assert "P02" in summary
    assert "Chapter 01" in summary


def test_task_router_routes_academic_tools():
    router = TaskRouter()
    all_tools = get_all_tools()
    tool_names = [t["name"] for t in all_tools]
    assert "ingest_course_materials" in tool_names
    assert "search_course_materials" in tool_names
    assert "generate_study_quiz" in tool_names
    assert "summarize_course_materials" in tool_names

    # Test search routing
    routed, scores = router.route_tools("bagaimana materi pertemuan 2 Sistem Operasi tentang thread?", all_tools)
    names = [t["name"] for t in routed]
    assert "search_course_materials" in names

    # Test quiz routing
    routed_quiz, _ = router.route_tools("buatkan kuis latihan ujian untuk materi kuliah Sistem Operasi", all_tools)
    quiz_names = [t["name"] for t in routed_quiz]
    assert "generate_study_quiz" in quiz_names

    # Test summarize routing
    routed_sum, _ = router.route_tools("tolong rangkum seluruh materi kuliah Cloud Computing dari p1 sampai akhir", all_tools)
    sum_names = [t["name"] for t in routed_sum]
    assert "summarize_course_materials" in sum_names

