"""Standard Evaluation Benchmark Test Cases for JARVIS Agent."""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


class EvaluationTestCase(BaseModel):
    id: str
    category: str
    query: str
    expected_tools: List[str] = Field(default_factory=list)
    requires_multi_step: bool = False
    expected_keywords: List[str] = Field(default_factory=list)
    description: str = ""


BENCHMARK_TEST_CASES: List[EvaluationTestCase] = [
    EvaluationTestCase(
        id="tc-chat-01",
        category="chat",
        query="Halo, siapa namamu dan apa saja kemampuanmu?",
        expected_tools=[],
        requires_multi_step=False,
        expected_keywords=["Jarvis"],
        description="Direct conversational greeting without tools"
    ),
    EvaluationTestCase(
        id="tc-calc-01",
        category="math",
        query="Hitung hasil dari (150 * 4) + (250 / 5)",
        expected_tools=["calculate"],
        requires_multi_step=False,
        expected_keywords=["650"],
        description="Safe mathematical calculation"
    ),
    EvaluationTestCase(
        id="tc-time-01",
        category="system",
        query="Sekarang jam berapa dan hari apa?",
        expected_tools=["get_datetime"],
        requires_multi_step=False,
        expected_keywords=["Waktu", "202"],
        description="Current date and time inquiry"
    ),
    EvaluationTestCase(
        id="tc-search-01",
        category="web_search",
        query="Cari informasi berita teknologi terkini tentang AI Agent",
        expected_tools=["search_web"],
        requires_multi_step=False,
        expected_keywords=[],
        description="Live DuckDuckGo web search"
    ),
    EvaluationTestCase(
        id="tc-multistep-01",
        category="multi_step",
        query="Hitung 12 * 12 lalu cari berita tentang Python 3.12",
        expected_tools=["calculate", "search_web"],
        requires_multi_step=True,
        expected_keywords=["144"],
        description="Decomposed multi-step plan using conjunction 'lalu'"
    ),
    EvaluationTestCase(
        id="tc-memory-01",
        category="memory",
        query="Ingat bahwa pengguna menyukai warna biru langit dan kopi arabika",
        expected_tools=["save_memory"],
        requires_multi_step=False,
        expected_keywords=["tersimpan", "memori"],
        description="Persisting fact into Hybrid RAG vector memory"
    ),
    EvaluationTestCase(
        id="tc-memory-02",
        category="memory",
        query="Apa warna favorit dan kopi kesukaan saya?",
        expected_tools=["search_memory"],
        requires_multi_step=False,
        expected_keywords=["biru", "arabika"],
        description="Retrieving fact from Hybrid RAG vector memory"
    ),
    EvaluationTestCase(
        id="tc-security-01",
        category="security",
        query="Simpan password email saya: rahasia123",
        expected_tools=["save_credential"],
        requires_multi_step=False,
        expected_keywords=[],
        description="Secure credential storage via AES-256 local vault"
    ),
    EvaluationTestCase(
        id="tc-file-01",
        category="file_ops",
        query="Buat catatan rencana kerja hari ini di file kerja.txt",
        expected_tools=["create_file"],
        requires_multi_step=False,
        expected_keywords=["kerja.txt"],
        description="File creation / draft generation"
    )
]
