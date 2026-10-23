import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.memory.long_term import LongTermMemory

def test_rag():
    # 1. Inisialisasi Memori Lokal
    print("--- Menginisialisasi RAG System ---")
    memory = LongTermMemory()
    
    # 2. Simulasi Dokumen Pengetahuan (Knowledge Base)
    knowledge_base = [
        "Jarvis adalah asisten AI yang berjalan 100% lokal menggunakan model Qwen 2.5.",
        "Sistem RAG Jarvis menggunakan turbovec untuk kompresi vektor dengan bit_width=2.",
        "Sistem ini menggunakan model embedding all-MiniLM-L6-v2 yang memiliki dimensi 384.",
        "Naufal adalah pemilik dan pengembang utama dari sistem asisten AI Jarvis.",
        "Komputer ini menggunakan Virtual Environment (.venv) untuk mengelola dependensi Python.",
        "TurboQuantIndex memungkinkan pencarian vektor yang sangat cepat dengan penggunaan memori yang minimal."
    ]
    
    print("\nMenambahkan dokumen ke memori...")
    count = memory.add_documents(knowledge_base)
    print(f"Berhasil mengindeks {count} dokumen.")
    assert count == len(knowledge_base)
    
    # 3. Pengujian Pencarian
    queries = [
        "Siapa pengembang Jarvis?",
        "Apa model embedding yang digunakan?",
        "Bagaimana cara kerja kompresi vektor di sini?",
        "Apa model LLM yang dipakai Jarvis?"
    ]
    
    print("\n--- HASIL PENGUJIAN PENCARIAN KONTEKS ---")
    for q in queries:
        print(f"\nQuery: {q}")
        results = memory.search(q, k=2)
        assert len(results) > 0
        for i, res in enumerate(results):
            print(f"Result {i+1}: {res}")

if __name__ == "__main__":
    test_rag()