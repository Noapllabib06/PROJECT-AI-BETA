# pyrefly: ignore [missing-import]
import numpy as np
from turbovec import IdMapIndex
from rank_bm25 import BM25Okapi
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager # <-- PERBAIKAN 1: Import ditambahkan
from pydantic import BaseModel
from typing import List, Optional
import os
import pickle
import re

class MemoryStore:
    def __init__(self, dim=768):
        self.dim = dim
        self.index = IdMapIndex(dim=self.dim)
        self.documents = {}  # { int_id: {"id": str, "text": str} }
        self.bm25 = None
        self.current_id = 0
        self.index_file = "memory_index.bin"
        self.docs_file = "memory_docs.pkl"

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\w+', text.lower())

    def _rebuild_bm25(self):
        if not self.documents:
            self.bm25 = None
            return
        
        # Sort documents by their internal ID to match order
        sorted_docs = [self.documents[i]["text"] for i in range(self.current_id) if i in self.documents]
        tokenized_corpus = [self._tokenize(doc) for doc in sorted_docs]
        if tokenized_corpus:
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None

    def load_from_disk(self):
        if os.path.exists(self.index_file) and os.path.exists(self.docs_file):
            print("Memuat index dan metadata dari disk (tanpa re-embedding)...")
            try:
                self.index = IdMapIndex.load(self.index_file)
                with open(self.docs_file, "rb") as f:
                    self.documents = pickle.load(f)
                
                # Update current_id
                if self.documents:
                    self.current_id = max(self.documents.keys()) + 1
                
                self._rebuild_bm25()
                print(f"[SUCCESS] Memori berhasil dimuat! Tidak perlu re-embed. Total dokumen: {len(self.documents)}")
            except Exception as e:
                print(f"[ERROR] Gagal memuat memori: {e}")
        else:
            print("[INFO] Tidak ada memori lama ditemukan, membuat yang baru.")

    def save_to_disk(self):
        try:
            self.index.write(self.index_file)
            with open(self.docs_file, "wb") as f:
                pickle.dump(self.documents, f)
            print("[SUCCESS] Memori berhasil disimpan secara permanen.")
        except Exception as e:
            print(f"[ERROR] Gagal menyimpan memori: {e}")

    def add_memory(self, doc_id: str, text: str, vector: List[float]):
        if len(vector) != self.dim:
            raise ValueError(f"Dimensi vektor salah. Diharapkan {self.dim}, tapi dapat {len(vector)}")

        emb = np.array([vector], dtype=np.float32)
        internal_id = self.current_id
        
        # turbovec require ids as uint64
        ids = np.array([internal_id], dtype=np.uint64)
        
        # Simpan ke vektor db
        self.index.add_with_ids(emb, ids)
        
        # Simpan metadata
        self.documents[internal_id] = {"id": doc_id, "text": text}
        self.current_id += 1
        
        # Update text search index
        self._rebuild_bm25()
        
        # Persist to disk
        self.save_to_disk()
        return internal_id

    def search_memory(self, query_text: str, query_vector: List[float], top_k: int = 3):
        if not self.documents:
            return []

        # 1. Vector Search
        emb = np.array([query_vector], dtype=np.float32)
        vec_scores, vec_indices = self.index.search(emb, k=top_k*2)
        
        # 2. BM25 Search
        bm25_scores = []
        if self.bm25:
            tokenized_query = self._tokenize(query_text)
            bm25_scores = self.bm25.get_scores(tokenized_query)

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores = {}
        K_RRF = 60
        
        # Rank dari vector
        for rank, (score, idx) in enumerate(zip(vec_scores[0], vec_indices[0])):
            if idx != -1:
                rrf_scores[idx] = rrf_scores.get(idx, 0) + (1.0 / (K_RRF + rank + 1))
                
        # Rank dari BM25
        if self.bm25:
            bm25_sorted_idx = np.argsort(bm25_scores)[::-1][:top_k*2]
            for rank, internal_id in enumerate(bm25_sorted_idx):
                if bm25_scores[internal_id] > 0:
                    rrf_scores[internal_id] = rrf_scores.get(internal_id, 0) + (1.0 / (K_RRF + rank + 1))
                    
        sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for internal_id, score in sorted_rrf[:top_k]:
            if internal_id in self.documents:
                results.append(self.documents[internal_id]["text"])
        
        return results

# Inisialisasi MemoryStore
memory_store = MemoryStore(dim=768)

# PERBAIKAN 2: Lifespan menggunakan fungsi load_from_disk() bawaan class Anda
@asynccontextmanager
async def lifespan(app: FastAPI):
    memory_store.load_from_disk()
    yield 

# PERBAIKAN 3: app dideklarasikan HANYA SATU KALI dengan title dan lifespan
app = FastAPI(title="Local Hybrid RAG Memory API", lifespan=lifespan)

class AddMemoryRequest(BaseModel):
    id: str
    text: str
    vector: List[float]

class SearchMemoryRequest(BaseModel):
    query_text: str
    query_vector: List[float]
    top_k: int = 3

@app.post("/add_memory")
async def api_add_memory(req: AddMemoryRequest):
    try:
        internal_id = memory_store.add_memory(req.id, req.text, req.vector)
        return {"status": "success", "internal_id": internal_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def api_search_memory(req: SearchMemoryRequest):
    try:
        results = memory_store.search_memory(req.query_text, req.query_vector, req.top_k)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("local_memory:app", host="127.0.0.1", port=8000, reload=True)