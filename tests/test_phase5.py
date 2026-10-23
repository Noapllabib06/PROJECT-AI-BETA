"""Verification test script for Phase 5 (17 Consolidated Tools & Codebase Indexer)."""
import os
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.tools import get_all_tools, register_all_tools
from src.tools.web_search import search_wikipedia
from src.tools.code_executor import create_file, read_file, list_directory, delete_file, git_status
from src.tools.api_tool import save_credential, get_credential, list_credentials, delete_credential
from src.tools.custom_tool import calculate, get_datetime, save_memory, search_memory, take_screenshot
from scripts.build_index import build_codebase_index


def run_tests():
    print("--- 1. Testing Tool Definitions Master List ---")
    all_tools = get_all_tools()
    print(f"Total tools registered: {len(all_tools)}")
    assert len(all_tools) >= 17, f"Expected >= 17 tools, got {len(all_tools)}"
    tool_names = [t["name"] for t in all_tools]
    print(f"Tools list: {tool_names}")
    print("[PASS] Master tool list verified.")

    print("\n--- 2. Testing Web & Wikipedia Tool ---")
    wiki_res = asyncio.run(search_wikipedia("Indonesia"))
    assert "Indonesia" in wiki_res
    print(f"[PASS] Wikipedia search verified (snippet: {wiki_res[:60]}...)")

    print("\n--- 3. Testing Code & File Tools ---")
    test_filename = "data/raw/phase5_test.txt"
    create_res = create_file(f"{test_filename}|Unit testing phase 5 content")
    assert "Berhasil membuat file" in create_res

    read_res = read_file(test_filename)
    assert "Unit testing phase 5 content" in read_res

    list_res = list_directory("data/raw")
    assert "phase5_test.txt" in list_res

    delete_res = delete_file(test_filename)
    assert "Berhasil menghapus" in delete_res

    git_res = git_status()
    assert "Git Status" in git_res
    print("[PASS] File operations & Git status verified.")

    print("\n--- 4. Testing API & Encrypted Credential Vault ---")
    save_res = save_credential("github_test: user_noap|token_secret_12345")
    assert "AES-256" in save_res

    get_res = get_credential("github_test")
    assert "user_noap" in get_res
    assert "token_secret_12345" in get_res

    list_cred = list_credentials()
    assert "github_test" in list_cred

    delete_cred = delete_credential("github_test")
    assert delete_cred is True
    print("[PASS] Encrypted credential vault operations verified.")

    print("\n--- 5. Testing Custom Tools (Math, Datetime, Memory, Screenshot) ---")
    calc_res = calculate("(12 * 8) + 4")
    assert "100" in calc_res

    time_res = get_datetime()
    assert "Waktu Sistem Sekarang" in time_res

    mem_save = save_memory("Naufal menyukai kopi arabika")
    assert "Ingatan Berhasil Disimpan" in mem_save

    mem_search = search_memory("kopi kesukaan")
    assert "arabika" in mem_search.lower()

    shot_res = take_screenshot()
    assert "Tangkapan Layar Berhasil Diambil" in shot_res
    print("[PASS] Custom tools verified.")

    print("\n--- 6. Testing Standalone Codebase Indexer (build_index.py) ---")
    sample_dir = Path("config")
    indexed = build_codebase_index(str(sample_dir))
    assert indexed > 0
    print(f"[PASS] Codebase indexer indexed {indexed} chunks from {sample_dir}.")

    print("\n>>> FASE 5 VERIFIKASI BERHASIL 100% <<<")


if __name__ == "__main__":
    run_tests()
