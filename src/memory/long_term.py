"""Long-term memory layer with Hybrid RAG (Vector + BM25) and user facts store.

Migrated and enhanced from:
- local_memory.py
- src/engine/memory_manager.js
"""

import os
import re
import pickle
import json
from pathlib import Path
from typing import List, Dict, Optional, Any, Union, Sequence, Tuple
import numpy as np
import httpx
from rank_bm25 import BM25Okapi

IdMapIndex: Any = None
faiss: Any = None

try:
    from turbovec import IdMapIndex  # type: ignore
    HAS_TURBOVEC = True
except ImportError:
    HAS_TURBOVEC = False

try:
    import faiss  # type: ignore
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

from config.settings import settings, get_logger

logger = get_logger("LongTermMemory")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
VECTOR_DB_DIR = BASE_DIR / settings.paths.vector_db_dir


class VectorBackend:
    """Abstraction layer over Turbovec or FAISS for ID-mapped vector indexing."""

    def __init__(self, dim: int = 384):
        self.dim = dim
        self.backend_type: str = "none"
        self.index: Any = None
        self.vectors: Dict[int, np.ndarray] = {}

        if HAS_TURBOVEC and IdMapIndex is not None:
            try:
                self.index = IdMapIndex(dim=self.dim)
                self.backend_type = "turbovec"
            except Exception as e:
                logger.warning(f"Failed to init Turbovec: {e}, attempting FAISS...")

        if self.backend_type == "none" and HAS_FAISS and faiss is not None:
            try:
                flat_index = faiss.IndexFlatIP(self.dim)
                self.index = faiss.IndexIDMap2(flat_index)
                self.backend_type = "faiss"
            except Exception as e:
                logger.warning(f"Failed to init FAISS: {e}")

        if self.backend_type == "none":
            # In-memory NumPy fallback
            self.backend_type = "numpy"

        logger.info(f"Vector backend initialized using: {self.backend_type.upper()} (dim={self.dim})")

    def add_with_ids(self, emb: np.ndarray, ids: np.ndarray) -> None:
        emb = np.ascontiguousarray(emb, dtype=np.float32)
        if self.backend_type == "turbovec" and self.index is not None:
            self.index.add_with_ids(emb, ids.astype(np.uint64))
        elif self.backend_type == "faiss" and self.index is not None:
            self.index.add_with_ids(emb, ids.astype(np.int64))
        else:
            for vec, vid in zip(emb, ids):
                self.vectors[int(vid)] = vec

    def search(self, query_emb: np.ndarray, k: int) -> Tuple[np.ndarray, np.ndarray]:
        query_emb = np.ascontiguousarray(query_emb, dtype=np.float32)
        if self.backend_type == "turbovec" and self.index is not None:
            return self.index.search(query_emb, k=k)
        elif self.backend_type == "faiss" and self.index is not None:
            return self.index.search(query_emb, k)
        else:
            if not self.vectors:
                return np.zeros((1, 0)), np.full((1, 0), -1)
            ids = list(self.vectors.keys())
            mat = np.array([self.vectors[i] for i in ids], dtype=np.float32)
            scores = np.dot(mat, query_emb[0])
            sorted_idx = np.argsort(scores)[::-1][:k]
            top_scores = scores[sorted_idx].reshape(1, -1)
            top_ids = np.array([ids[i] for i in sorted_idx], dtype=np.int64).reshape(1, -1)
            return top_scores, top_ids

    def save(self, filepath: Path) -> None:
        if self.backend_type == "turbovec" and self.index is not None:
            self.index.write(str(filepath))
        elif self.backend_type == "faiss" and self.index is not None and faiss is not None:
            faiss.write_index(self.index, str(filepath))
        else:
            with open(filepath, "wb") as f:
                pickle.dump(self.vectors, f)

    def load(self, filepath: Path) -> bool:
        if not filepath.exists():
            return False
        try:
            if self.backend_type == "turbovec" and IdMapIndex is not None:
                self.index = IdMapIndex.load(str(filepath))
                return True
            elif self.backend_type == "faiss" and faiss is not None:
                self.index = faiss.read_index(str(filepath))
                return True
            else:
                with open(filepath, "rb") as f:
                    self.vectors = pickle.load(f)
                return True
        except Exception as e:
            logger.error(f"Failed to load vector index: {e}")
            return False


class EmbeddingClient:
    """Generates embedding vectors via Ollama or fast deterministic local fallback."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text", dim: int = 384):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dim = dim

    def embed_text(self, text: str) -> List[float]:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text}
                )
                if res.status_code == 200:
                    embedding = res.json().get("embedding", [])
                    if len(embedding) == self.dim:
                        return embedding
                    elif len(embedding) > self.dim:
                        return embedding[:self.dim]
                    elif len(embedding) > 0:
                        # Pad with zeros to target dimension
                        return embedding + [0.0] * (self.dim - len(embedding))
        except Exception:
            pass

        # Fast deterministic fallback: Token hashing with L2-normalized projection
        return self._generate_fallback_vector(text)

    def _generate_fallback_vector(self, text: str) -> List[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        words = re.findall(r"\w+", text.lower())
        if not words:
            return vec.tolist()

        for w in words:
            h = abs(hash(w))
            idx = h % self.dim
            sign = 1.0 if (h // self.dim) % 2 == 0 else -1.0
            vec[idx] += sign

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()


class LongTermMemory:
    """Hybrid RAG memory store combining dense vectors, BM25, and user facts."""

    def __init__(self, dim: Optional[int] = None, storage_dir: Optional[Path] = None):
        self.dim = dim or settings.llm.embedding_dim
        self.storage_dir = storage_dir or VECTOR_DB_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.index_file = self.storage_dir / "memory_index.bin"
        self.docs_file = self.storage_dir / "memory_docs.pkl"
        self.facts_file = self.storage_dir / "facts.json"

        self.vector_backend = VectorBackend(dim=self.dim)
        self.embed_client = EmbeddingClient(
            base_url=settings.llm.ollama_base_url,
            model=settings.llm.embedding_model,
            dim=self.dim
        )

        self.documents: Dict[int, Dict[str, Any]] = {}  # {int_id: {"id": str, "text": str, "metadata": dict}}
        self.bm25: Optional[BM25Okapi] = None
        self.current_id = 0

        self.load_from_disk()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())

    def _rebuild_bm25(self) -> None:
        if not self.documents:
            self.bm25 = None
            return

        sorted_docs = [self.documents[i]["text"] for i in range(self.current_id) if i in self.documents]
        tokenized_corpus = [self._tokenize(doc) for doc in sorted_docs]
        if tokenized_corpus:
            self.bm25 = BM25Okapi(tokenized_corpus)
        else:
            self.bm25 = None

    def load_from_disk(self) -> None:
        if self.docs_file.exists():
            try:
                with open(self.docs_file, "rb") as f:
                    self.documents = pickle.load(f)
                if self.documents:
                    self.current_id = max(self.documents.keys()) + 1
                self.vector_backend.load(self.index_file)
                self._rebuild_bm25()
                logger.info(f"Memori RAG berhasil dimuat. Total dokumen: {len(self.documents)}")
            except Exception as e:
                logger.error(f"Gagal memuat memori dari disk: {e}")
        else:
            logger.info("Tidak ada memori RAG lama di disk, membuat indeks baru.")

    def save_to_disk(self) -> None:
        try:
            self.vector_backend.save(self.index_file)
            with open(self.docs_file, "wb") as f:
                pickle.dump(self.documents, f)
            logger.debug("Memori RAG berhasil disimpan ke disk.")
        except Exception as e:
            logger.error(f"Gagal menyimpan memori RAG: {e}")

    def add_memory(
        self,
        doc_id: str,
        text: str,
        vector: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        auto_save: bool = True
    ) -> int:
        if not text or not text.strip():
            return -1

        if vector is None or len(vector) != self.dim:
            vector = self.embed_client.embed_text(text)

        emb = np.array([vector], dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        internal_id = self.current_id
        ids = np.array([internal_id], dtype=np.uint64)

        self.vector_backend.add_with_ids(emb, ids)
        self.documents[internal_id] = {
            "id": doc_id,
            "text": text,
            "metadata": metadata or {}
        }
        self.current_id += 1

        if auto_save:
            self._rebuild_bm25()
            self.save_to_disk()
        return internal_id

    def add_documents(self, documents: Sequence[Union[str, Dict[str, Any]]]) -> int:
        count = 0
        for doc in documents:
            if isinstance(doc, str):
                self.add_memory(doc_id=f"doc_{self.current_id}", text=doc, auto_save=False)
                count += 1
            elif isinstance(doc, dict):
                text = doc.get("text") or doc.get("content", "")
                doc_id = doc.get("id", f"doc_{self.current_id}")
                meta = doc.get("metadata", {})
                if text:
                    self.add_memory(doc_id=doc_id, text=text, metadata=meta, auto_save=False)
                    count += 1
        if count > 0:
            self._rebuild_bm25()
            self.save_to_disk()
        return count

    def search_memory(
        self,
        query_text: str,
        query_vector: Optional[List[float]] = None,
        top_k: int = 3,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        if not self.documents:
            return []

        if query_vector is None or len(query_vector) != self.dim:
            query_vector = self.embed_client.embed_text(query_text)

        emb = np.array([query_vector], dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm

        # 1. Vector Search
        search_k = min(max(top_k * 5, 25), len(self.documents))
        vec_scores, vec_indices = self.vector_backend.search(emb, k=search_k)

        # 2. BM25 Search
        bm25_scores = []
        if self.bm25:
            tokenized_query = self._tokenize(query_text)
            bm25_scores = self.bm25.get_scores(tokenized_query)

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores: Dict[int, float] = {}
        K_RRF = 60.0

        for rank, idx in enumerate(vec_indices[0]):
            internal_id = int(idx)
            if internal_id != -1 and internal_id in self.documents:
                rrf_scores[internal_id] = rrf_scores.get(internal_id, 0.0) + (1.0 / (K_RRF + rank + 1))

        if self.bm25 and len(bm25_scores) > 0:
            bm25_sorted_idx = np.argsort(bm25_scores)[::-1][:search_k]
            for rank, internal_id in enumerate(bm25_sorted_idx):
                internal_id = int(internal_id)
                if bm25_scores[internal_id] > 0 and internal_id in self.documents:
                    rrf_scores[internal_id] = rrf_scores.get(internal_id, 0.0) + (1.0 / (K_RRF + rank + 1))

        sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

        results = []
        for internal_id, score in sorted_rrf:
            doc_data = self.documents[internal_id]
            meta = doc_data.get("metadata", {})

            # Filter metadata check
            if filter_metadata:
                match = True
                for f_key, f_val in filter_metadata.items():
                    doc_val = meta.get(f_key)
                    if doc_val is None:
                        match = False
                        break
                    if isinstance(f_val, str) and isinstance(doc_val, str):
                        if f_val.lower() not in doc_val.lower():
                            match = False
                            break
                    elif f_val != doc_val:
                        match = False
                        break
                if not match:
                    continue

            results.append({
                "internal_id": internal_id,
                "id": doc_data["id"],
                "text": doc_data["text"],
                "score": float(score),
                "metadata": meta
            })
            if len(results) >= top_k:
                break

        return results

    # ==========================================
    # Facts Management (from memory_manager.js)
    # ==========================================

    def get_facts(self) -> List[str]:
        if not self.facts_file.exists():
            return []
        try:
            with open(self.facts_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Gagal membaca fakta: {e}")
            return []

    def add_facts(self, new_facts: Union[List[str], str]) -> int:
        if not new_facts:
            return 0
        facts_to_add = [new_facts] if isinstance(new_facts, str) else list(new_facts)
        if not facts_to_add:
            return 0

        current = self.get_facts()
        unique = [f.strip() for f in facts_to_add if f.strip() and f.strip() not in current]
        if not unique:
            return 0

        updated = current + unique
        try:
            with open(self.facts_file, "w", encoding="utf-8") as f:
                json.dump(updated, f, indent=2, ensure_ascii=False)
            logger.info(f"Berhasil menambahkan {len(unique)} fakta baru.")
            return len(unique)
        except Exception as e:
            logger.error(f"Gagal menyimpan fakta: {e}")
            return 0

    def search(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """Convenience alias for search_memory."""
        return self.search_memory(query_text=query, top_k=k)

