"""Unified Memory Store for JARVIS AI Agent.

Combines Short-Term (conversational & context sliding window) and
Long-Term (Hybrid Vector + BM25 RAG + User Facts) natively in Python.
"""

from typing import List, Dict, Optional, Any, Union
from src.memory.short_term import ShortTermMemory, ConversationManager, Message
from src.memory.long_term import LongTermMemory
from config.settings import settings, get_logger

logger = get_logger("MemoryStore")


class MemoryStore:
    """Unified facade for all memory operations in the JARVIS agent."""

    def __init__(
        self,
        short_term: Optional[ShortTermMemory] = None,
        long_term: Optional[LongTermMemory] = None,
    ):
        self.short_term = short_term or ShortTermMemory()
        self.long_term = long_term or LongTermMemory()
        logger.info("Unified MemoryStore initialized.")

    # ----------------------------------------------------
    # Short-Term / Active Conversation Methods
    # ----------------------------------------------------

    def add_user_message(self, content: str) -> Message:
        return self.short_term.add_message("user", content)

    def add_assistant_message(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> Message:
        return self.short_term.add_message("assistant", content, metadata=metadata)

    def add_system_message(self, content: str) -> Message:
        return self.short_term.add_message("system", content)

    def get_chat_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        return self.short_term.get_recent_messages(limit=limit)

    def clear_short_term(self) -> None:
        self.short_term.clear()

    def switch_conversation(self, conversation_id: str):
        return self.short_term.switch_conversation(conversation_id)

    def list_conversations(self) -> List[Dict[str, Any]]:
        return self.short_term.conv_mgr.list_conversations()

    # ----------------------------------------------------
    # Long-Term Hybrid RAG & Facts Methods
    # ----------------------------------------------------

    def remember(self, text: str, doc_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> int:
        """Store knowledge or insight in long-term hybrid RAG memory."""
        id_str = doc_id or f"mem_{self.long_term.current_id}"
        return self.long_term.add_memory(doc_id=id_str, text=text, metadata=metadata)

    def recall(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Search long-term memory using hybrid Dense Vector + BM25."""
        return self.long_term.search_memory(query_text=query, top_k=top_k)

    def add_facts(self, facts: Union[List[str], str]) -> int:
        return self.long_term.add_facts(facts)

    def get_facts(self) -> List[str]:
        return self.long_term.get_facts()

    # ----------------------------------------------------
    # Augmented Context Builder for System Prompts
    # ----------------------------------------------------

    def build_augmented_context(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """Gathers permanent facts and relevant RAG memories formatted for LLM prompts."""
        facts = self.get_facts() if settings.agent.enable_long_term_memory else []
        memories = self.recall(query, top_k=top_k) if settings.agent.enable_long_term_memory else []

        context_parts = []

        if facts:
            facts_text = "\n".join(f"- {f}" for f in facts)
            context_parts.append(f"### FAKTA PERMANEN PENGGUNA:\n{facts_text}")

        if memories:
            mems_text = "\n\n".join(f"[Memori #{i+1}]: {m['text']}" for i, m in enumerate(memories))
            context_parts.append(f"### INFORMASI TERKAIT DARI MEMORI JANGKA PANJANG (RAG):\n{mems_text}")

        formatted_context = "\n\n".join(context_parts) if context_parts else ""

        return {
            "facts": facts,
            "memories": memories,
            "formatted_context": formatted_context,
            "recent_messages": self.get_chat_history(),
        }


# Singleton instance
memory_store = MemoryStore()
