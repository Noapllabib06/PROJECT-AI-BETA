"""Base Agent and Pydantic v2 Tool Call Parser for JARVIS.

Migrated and upgraded from:
- src/engine/json_validator.js
- src/engine/agent.js (LLM invocation logic)
"""

import re
import json
import asyncio
from typing import List, Dict, Optional, Any, Union, Generator, AsyncGenerator
from pydantic import BaseModel, Field, ValidationError
import httpx

from config.settings import settings, get_logger
from src.prompts.templates import build_error_feedback_prompt

logger = get_logger("BaseAgent")


# ==========================================
# Pydantic v2 Tool Call Schemas
# ==========================================

class ToolCall(BaseModel):
    tool: str = Field(..., description="The name of the tool to invoke, or 'chat'")
    query: str = Field(default="", description="The primary query or instruction string")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Additional keyword parameters")

    @classmethod
    def from_raw_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        """Normalizes various LLM output flavors into standard ToolCall."""
        tool = str(data.get("tool", "chat")).strip()
        query = data.get("query", "")
        if query is None:
            query = ""
        elif not isinstance(query, str):
            query = str(query)

        # Extract extra fields (e.g. 'sender', 'date', 'filepath') into parameters
        params = {}
        for k, v in data.items():
            if k not in ("tool", "query"):
                params[k] = v

        return cls(tool=tool, query=query, parameters=params)


class ToolCallValidationResult(BaseModel):
    success: bool
    data: List[ToolCall] = Field(default_factory=list)
    raw_output: str = ""
    error: Optional[str] = None


class OutputParser:
    """Robust JSON extractor and Pydantic v2 validator for LLM output."""

    @staticmethod
    def extract_json_candidates(text: str) -> Optional[Union[List[Any], Dict[str, Any]]]:
        if not text or not isinstance(text, str):
            return None

        clean_text = text.strip()

        # 1. Check for Markdown fenced code blocks: ```json ... ```
        fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_text)
        if fenced_match:
            candidate = fenced_match.group(1).strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, (list, dict)):
                    return parsed
            except Exception:
                pass

        # 2. Check for JSON array [ { ... } ]
        array_match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", clean_text)
        if array_match:
            try:
                parsed = json.loads(array_match.group(0))
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass

        # 3. Check for single JSON object { ... }
        first_brace = clean_text.find("{")
        last_brace = clean_text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_substr = clean_text[first_brace : last_brace + 1]
            # Handle multiple concatenated JSON objects: "{ ... }\n{ ... }" -> "[{ ... }, { ... }]"
            json_substr_normalized = re.sub(r"\}\s*,?\s*\{", "},{", json_substr)
            wrapped = f"[{json_substr_normalized}]"
            try:
                parsed = json.loads(wrapped)
                if isinstance(parsed, list) and len(parsed) > 0:
                    return parsed
            except Exception:
                pass

            try:
                parsed_single = json.loads(json_substr)
                if isinstance(parsed_single, dict):
                    return [parsed_single]
            except Exception:
                pass

        # 4. Regex fallback for slightly broken or streaming tool calls
        regex = r'\{\s*"tool"\s*:\s*"([^"]+)"(?:\s*,\s*"?query"?\s*:\s*"([\s\S]*?)")?\s*\}'
        matches = re.findall(regex, clean_text)
        if matches:
            fallback_items = []
            for m in matches:
                fallback_items.append({"tool": m[0], "query": m[1] if len(m) > 1 else ""})
            return fallback_items

        return None

    @classmethod
    def parse_and_validate(
        cls,
        ai_output: str,
        valid_tools: Optional[List[str]] = None,
        all_fallback_tools: Optional[List[str]] = None
    ) -> ToolCallValidationResult:
        if not ai_output or not ai_output.strip():
            return ToolCallValidationResult(
                success=False,
                raw_output=ai_output or "",
                error="Output AI kosong"
            )

        extracted = cls.extract_json_candidates(ai_output)
        if not extracted:
            clean = ai_output.strip()
            # If the model produced natural conversational text without JSON, accept directly as chat
            if clean and not re.search(r'["\']tool["\']\s*:', clean):
                return ToolCallValidationResult(
                    success=True,
                    data=[ToolCall(tool="chat", query=clean)],
                    raw_output=ai_output
                )
            return ToolCallValidationResult(
                success=False,
                raw_output=ai_output,
                error="Tidak dapat menemukan JSON valid dalam output AI"
            )

        raw_list = extracted if isinstance(extracted, list) else [extracted]
        tool_calls: List[ToolCall] = []

        allowed = set(valid_tools) if valid_tools else None
        if allowed:
            allowed.add("chat")

        fallback_set = set(all_fallback_tools) if all_fallback_tools else set()
        fallback_set.add("chat")

        for item in raw_list:
            if not isinstance(item, dict):
                continue

            # Model edge-case: {"tool": ["t1", "t2"], "query": ["q1", "q2"]}
            if isinstance(item.get("tool"), list) and isinstance(item.get("query"), list):
                t_list = item["tool"]
                q_list = item["query"]
                for t, q in zip(t_list, q_list):
                    t_str = str(t).strip()
                    if allowed and t_str not in allowed and t_str not in fallback_set:
                        return ToolCallValidationResult(
                            success=False,
                            raw_output=ai_output,
                            error=f"Tool '{t_str}' tidak valid."
                        )
                    tool_calls.append(ToolCall(tool=t_str, query=str(q)))
                continue

            tool_name = str(item.get("tool", "")).strip()
            if not tool_name:
                return ToolCallValidationResult(
                    success=False,
                    raw_output=ai_output,
                    error="Field 'tool' kosong atau tidak ditemukan"
                )

            if allowed and tool_name not in allowed:
                # Accept if registered in master tool set
                if tool_name in fallback_set:
                    tool_calls.append(ToolCall.from_raw_dict(item))
                    continue
                return ToolCallValidationResult(
                    success=False,
                    raw_output=ai_output,
                    error=f"Tool '{tool_name}' tidak terdaftar dalam tool yang tersedia."
                )

            tool_calls.append(ToolCall.from_raw_dict(item))

        if not tool_calls:
            return ToolCallValidationResult(
                success=False,
                raw_output=ai_output,
                error="Tidak ada tool call valid yang berhasil diekstraksi."
            )

        return ToolCallValidationResult(
            success=True,
            data=tool_calls,
            raw_output=ai_output
        )


# ==========================================
# Base Agent LLM Client
# ==========================================

class BaseAgent:
    """Base AI Agent class handling Ollama / Cloud API invocations with retry."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        num_ctx: Optional[int] = None
    ):
        self.model_name = model_name or settings.llm.default_model
        self.base_url = (base_url or settings.llm.ollama_base_url).rstrip("/")
        self.temperature = temperature if temperature is not None else settings.llm.temperature
        self.num_ctx = num_ctx or settings.llm.num_ctx
        self.timeout = float(settings.agent.timeout_seconds)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Synchronous generation using Ollama generate API."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_ctx": self.num_ctx,
            }
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def a_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Asynchronous generation with Ollama generate API."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "system": system_prompt or "",
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_ctx": self.num_ctx,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def a_chat(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Asynchronous multi-turn chat using Ollama chat API."""
        url = f"{self.base_url}/api/chat"
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "stream": False,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_ctx": self.num_ctx,
            }
        }

        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    msg = data.get("message", {})
                    return msg.get("content", "")
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt == 0:
                    logger.warning(f"Ollama returned {e.response.status_code}, retrying in 2.0s (model loading/warming up)...")
                    await asyncio.sleep(2.0)
                    continue
                raise
        return ""

    async def a_chat_stream(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None
    ) -> AsyncGenerator[str, None]:
        """Asynchronous streaming of chat response chunks."""
        url = f"{self.base_url}/api/chat"
        formatted_messages = []
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        formatted_messages.extend(messages)

        payload = {
            "model": self.model_name,
            "messages": formatted_messages,
            "stream": True,
            "options": {
                "temperature": temperature if temperature is not None else self.temperature,
                "num_ctx": self.num_ctx,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        try:
                            chunk_data = json.loads(line)
                            chunk_content = chunk_data.get("message", {}).get("content", "")
                            if chunk_content:
                                yield chunk_content
                        except json.JSONDecodeError:
                            continue
