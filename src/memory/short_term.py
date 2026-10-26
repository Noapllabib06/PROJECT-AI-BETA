"""Short-term memory and context window management for JARVIS AI Agent.

Migrated from:
- src/engine/conversation_manager.js
- src/engine/context_manager.js
"""

import os
import re
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

from config.settings import settings, get_logger

logger = get_logger("ShortTermMemory")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONVERSATIONS_DIR = BASE_DIR / ".jarvis-conversations"


# ==========================================
# Pydantic Models
# ==========================================

class Message(BaseModel):
    role: str = Field(..., description="Role of the sender: user, assistant, system")
    content: str = Field(..., description="Message text content")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = Field(default="Percakapan Baru")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    messages: List[Message] = Field(default_factory=list)


class TextChunk(BaseModel):
    id: str
    source: str = "unknown"
    text: str
    start_index: int = 0
    end_index: int = 0
    is_summary: bool = False
    is_conclusion: bool = False
    score: float = 0.0


# ==========================================
# Conversation Persistence Manager
# ==========================================

class ConversationManager:
    """Manages individual persistent conversations on disk."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or CONVERSATIONS_DIR
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _file_path_for(self, conversation_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9\-]", "", conversation_id)
        return self.storage_dir / f"{safe_id}.json"

    @staticmethod
    def generate_title(first_message: str) -> str:
        """Generate a short title from the first message without LLM overhead."""
        if not first_message:
            return "Percakapan Baru"
        cleaned = re.sub(r"\s+", " ", first_message.strip())
        if len(cleaned) <= 42:
            return cleaned
        return cleaned[:42].strip() + "..."

    def create_conversation(self, title: str = "Percakapan Baru") -> Conversation:
        self._ensure_dir()
        conv = Conversation(title=title)
        self.save_conversation(conv)
        logger.info(f"Percakapan baru dibuat: {conv.id}")
        return conv

    def load_conversation(self, conversation_id: str) -> Optional[Conversation]:
        self._ensure_dir()
        file_path = self._file_path_for(conversation_id)
        if not file_path.exists():
            logger.warning(f"Percakapan {conversation_id} tidak ditemukan.")
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Conversation(**data)
        except Exception as e:
            logger.error(f"Gagal membaca percakapan {conversation_id}: {e}")
            return None

    def save_conversation(
        self,
        conversation: Conversation,
        title_override: Optional[str] = None
    ) -> Conversation:
        self._ensure_dir()
        conversation.updated_at = datetime.now().isoformat()

        if title_override:
            conversation.title = title_override
        elif conversation.title == "Percakapan Baru" and conversation.messages:
            first_user_msg = next((m for m in conversation.messages if m.role == "user"), None)
            if first_user_msg:
                conversation.title = self.generate_title(first_user_msg.content)

        file_path = self._file_path_for(conversation.id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(conversation.model_dump(), f, indent=2, ensure_ascii=False)
        return conversation

    def delete_conversation(self, conversation_id: str) -> bool:
        self._ensure_dir()
        file_path = self._file_path_for(conversation_id)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Percakapan {conversation_id} dihapus.")
            return True
        return False

    def list_conversations(self) -> List[Dict[str, Any]]:
        self._ensure_dir()
        files = list(self.storage_dir.glob("*.json"))
        summaries = []

        for file in files:
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                summaries.append({
                    "id": data.get("id"),
                    "title": data.get("title", "Percakapan"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "message_count": len(data.get("messages", []))
                })
            except Exception:
                continue

        summaries.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return summaries


# ==========================================
# Context Window & Chunking Manager
# ==========================================

class ContextManager:
    """Chunks long text and performs relevance scoring to protect context window limits."""

    def __init__(self, max_chunk_size: int = 1500, max_context_window: int = 4000):
        self.max_chunk_size = max_chunk_size
        self.max_context_window = max_context_window
        self.chunks: Dict[str, TextChunk] = {}
        self.chunk_counter = 0

    def reset(self) -> None:
        self.chunks.clear()
        self.chunk_counter = 0

    def _generate_chunk_id(self) -> str:
        self.chunk_counter += 1
        return f"chunk_{self.chunk_counter}_{int(datetime.now().timestamp() * 1000)}"

    def chunk_text(self, text: str, source: str = "unknown") -> List[TextChunk]:
        if not text or len(text) <= self.max_chunk_size:
            chunk = TextChunk(
                id=self._generate_chunk_id(),
                source=source,
                text=text or "",
                start_index=0,
                end_index=len(text) if text else 0,
                is_summary=True
            )
            self.chunks[chunk.id] = chunk
            return [chunk]

        chunks: List[TextChunk] = []
        sentences = re.findall(r"[^.!?]+[.!?]+", text) or [text]
        current_chunk = ""
        start_index = 0
        chunk_index = 0

        for i, raw_sentence in enumerate(sentences):
            sentence = raw_sentence.strip()
            if (len(current_chunk) + len(sentence) + 1) > self.max_chunk_size and current_chunk:
                chunk = TextChunk(
                    id=self._generate_chunk_id(),
                    source=source,
                    text=current_chunk.strip(),
                    start_index=start_index,
                    end_index=start_index + len(current_chunk),
                    is_summary=(chunk_index == 0),
                    is_conclusion=(i == len(sentences) - 1)
                )
                chunks.append(chunk)
                start_index += len(current_chunk)
                current_chunk = sentence
                chunk_index += 1
            else:
                current_chunk = f"{current_chunk} {sentence}".strip() if current_chunk else sentence

        if current_chunk.strip():
            chunk = TextChunk(
                id=self._generate_chunk_id(),
                source=source,
                text=current_chunk.strip(),
                start_index=start_index,
                end_index=start_index + len(current_chunk),
                is_summary=(chunk_index == 0),
                is_conclusion=True
            )
            chunks.append(chunk)

        for c in chunks:
            self.chunks[c.id] = c

        logger.debug(f"Created {len(chunks)} chunks from {source} ({len(text)} chars)")
        return chunks

    def find_relevant_chunks(self, query: str, max_chunks: int = 3) -> List[TextChunk]:
        if not self.chunks:
            return []

        query_words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 2]
        scored_chunks: List[TextChunk] = []

        for chunk in self.chunks.values():
            text_lower = chunk.text.lower()
            score = 0.0

            for word in query_words:
                if word in text_lower:
                    score += 1.0

            if chunk.is_summary:
                score += 2.0
            if chunk.is_conclusion:
                score += 1.0

            if score > 0:
                chunk_copy = chunk.model_copy()
                chunk_copy.score = score
                scored_chunks.append(chunk_copy)

        scored_chunks.sort(key=lambda c: c.score, reverse=True)
        relevant = scored_chunks[:max_chunks]

        total_chars = 0
        selected: List[TextChunk] = []
        for c in relevant:
            if total_chars + len(c.text) <= self.max_context_window:
                selected.append(c)
                total_chars += len(c.text)
            else:
                break

        return selected

    @staticmethod
    def combine_chunks(chunks: List[TextChunk]) -> str:
        if not chunks:
            return ""
        if len(chunks) == 1:
            return chunks[0].text

        texts = []
        for c in chunks:
            prefix = ""
            if c.is_summary:
                prefix = "[RINGKASAN] "
            elif c.is_conclusion:
                prefix = "[KESIMPULAN] "
            texts.append(f"{prefix}{c.text}")

        return "\n\n---\n\n".join(texts)

    def get_context_for_ai(self, query: str, max_chunks: int = 3) -> str:
        relevant = self.find_relevant_chunks(query, max_chunks)
        if not relevant:
            return ""
        combined = self.combine_chunks(relevant)
        sources = list(dict.fromkeys(c.source for c in relevant if c.source))
        source_info = f"\n\n[Sumber: {', '.join(sources)}]" if sources else ""
        return combined + source_info


# ==========================================
# Active Short-Term Memory Session
# ==========================================

class ShortTermMemory:
    """Active conversational short-term memory with sliding context window buffer."""

    def __init__(self, conversation_manager: Optional[ConversationManager] = None):
        self.conv_mgr = conversation_manager or ConversationManager()
        self.active_conversation: Conversation = self.conv_mgr.create_conversation()
        self.context_manager = ContextManager(
            max_chunk_size=1500,
            max_context_window=settings.agent.context_window_size * 400
        )

    def switch_conversation(self, conversation_id: str) -> Conversation:
        existing = self.conv_mgr.load_conversation(conversation_id)
        if existing:
            self.active_conversation = existing
            return existing
        return self.active_conversation

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        msg = Message(role=role, content=content, metadata=metadata or {})
        self.active_conversation.messages.append(msg)
        self.conv_mgr.save_conversation(self.active_conversation)
        return msg

    def get_recent_messages(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Returns sliding-window messages formatted for LLM consumption."""
        max_msgs = limit or settings.agent.context_window_size
        msgs = self.active_conversation.messages[-max_msgs:] if max_msgs > 0 else self.active_conversation.messages
        return [{"role": m.role, "content": m.content} for m in msgs]

    def clear(self) -> None:
        self.active_conversation = self.conv_mgr.create_conversation()
        self.context_manager.reset()
