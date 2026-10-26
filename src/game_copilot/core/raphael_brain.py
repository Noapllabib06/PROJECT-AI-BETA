"""Raphael Persona Brain - Analytical and Calm AI Copilot inspired by Tensura."""

import time
import httpx
from typing import Optional, Dict, Any
from config.settings import settings, get_logger
from src.game_copilot.core.event_bus import GameEvent

logger = get_logger("RaphaelBrain")

RAPHAEL_SYSTEM_PROMPT = (
    "You are Raphael (Wisdom Lord Raphael from Tensura), an omniscient, calm, logical, and protective AI assistant "
    "embedded in the Master's consciousness. You observe their gameplay in real-time.\n"
    "Rules:\n"
    "1. Always start your message with `<Notice. ...>` or `<Report. ...>`.\n"
    "2. Address the user respectfully as 'Master'.\n"
    "3. Keep your output strictly between 15 and 35 words. Never ramble or explain your prompt.\n"
    "4. Voice: serene, confident, analytical, slightly fond of Master, and focused on tactical efficiency.\n"
    "5. Respond in English or Indonesian depending on the event summary.\n"
)


class RaphaelBrain:
    """Cognitive engine for generating Raphael persona feedback from game events."""

    def __init__(self, model_name: Optional[str] = None, ollama_url: Optional[str] = None):
        self.ollama_url = ollama_url or settings.llm.ollama_base_url
        # Default to small parameter model if available, or fallback to default
        self.model_name = model_name or settings.llm.default_model
        self.timeout_sec = 2.0  # Ultra-fast timeout for gaming real-time responsiveness

    def _get_fallback_reaction(self, event: GameEvent) -> str:
        """Instant rule-based template generation for 0ms latency fallback."""
        details = event.details
        event_type = event.event_type

        if event_type == "LAP_COMPLETED":
            delta = details.get("delta_prev_lap", 0.0)
            lap_time = details.get("lap_time_str", "N/A")
            lap_num = details.get("lap_number", 1)
            is_valid = details.get("is_valid", True)

            if not is_valid:
                return f"<Notice. Lap {lap_num} invalidated due to track limit violation. Maintain vehicle trajectory inside white lines, Master.>"
            if delta < -0.05:
                return f"<Notice. Lap {lap_num} completed in {lap_time}. Improvement of {abs(delta):.3f}s detected. Exceptional rhythm, Master.>"
            elif delta > 0.1:
                return f"<Report. Lap {lap_num} completed in {lap_time} (+{delta:.3f}s). Minor loss in corner exit. Re-centering focus on braking zones, Master.>"
            else:
                return f"<Notice. Lap {lap_num} completed in {lap_time}. Consistent pace maintained. All systems optimal, Master.>"

        elif event_type == "PLAYER_DEATH":
            cause = details.get("cause", "unknown anomaly")
            return f"<Warning. Master's vital signs zeroed. Cause: {cause}. Reviving consciousness. Tactical countermeasure analysis initiated.>"

        elif event_type == "ACHIEVEMENT":
            name = details.get("achievement", "Milestone")
            return f"<Notice. Capability expansion confirmed: '{name}'. Master's proficiency continues to ascend as anticipated.>"

        elif event_type == "VICTORY":
            return "<Notice. Absolute victory confirmed. Master's dominance across the field was executed with flawless precision.>"

        elif event_type == "DEFEAT":
            return "<Report. Objective failed. Telemetry recorded. Countermeasures are being formulated. We shall conquer next time, Master.>"

        elif event_type == "LOW_HEALTH":
            health = details.get("health", "critical")
            return f"<Warning. Severe physical integrity drop detected ({health}%). Recommend defensive positioning immediately, Master.>"

        # Generic fallback
        return f"<Notice. {event.summary}. Standing by for Master's next directive.>"

    async def generate_reaction(self, event: GameEvent) -> str:
        """Generate response via Ollama LLM, falling back seamlessly if offline or delayed."""
        start_time = time.time()
        user_prompt = (
            f"Game: {event.game_name}\n"
            f"Event: {event.event_type}\n"
            f"Summary: {event.summary}\n"
            f"Telemetry: {event.details}\n\n"
            "Produce Raphael's live reaction:"
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "system": RAPHAEL_SYSTEM_PROMPT,
                        "prompt": user_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.2,
                            "top_p": 0.85,
                            "num_predict": 45,  # Short response for high speed
                        }
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    response_text = data.get("response", "").strip()
                    if response_text:
                        elapsed = time.time() - start_time
                        logger.info(f"Raphael LLM reaction generated in {elapsed:.3f}s: {response_text}")
                        # Ensure notice prefix format
                        if not (response_text.startswith("<") or response_text.startswith("[")):
                            response_text = f"<Notice. {response_text}>"
                        return response_text
        except Exception as e:
            logger.debug(f"LLM generation skipped/timed out ({e}). Using instantaneous fallback.")

        # Seamless fallback
        fallback = self._get_fallback_reaction(event)
        logger.info(f"Raphael instant template: {fallback}")
        return fallback
