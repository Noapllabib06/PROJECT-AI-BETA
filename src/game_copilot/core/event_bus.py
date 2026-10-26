"""Universal Game Event Bus & Event Normalizer for Gaming Copilot."""

import time
import asyncio
from typing import Dict, Any, List, Callable, Optional, Awaitable
from pydantic import BaseModel, Field
from config.settings import get_logger

logger = get_logger("GameEventBus")


class GameEvent(BaseModel):
    """Normalized universal representation of an in-game event."""
    game_name: str = Field(..., description="Name of the game (e.g. Assetto Corsa Competizione, Minecraft)")
    event_type: str = Field(..., description="Category: LAP_COMPLETED, PLAYER_DEATH, ACHIEVEMENT, WARNING, VICTORY, etc.")
    severity: str = Field(default="INFO", description="INFO, WARNING, CELEBRATION, CRITICAL")
    summary: str = Field(..., description="Short plain-text summary of the event")
    details: Dict[str, Any] = Field(default_factory=dict, description="Game-specific telemetry payload")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of event generation")


class EventBus:
    """Publish-Subscribe bus that decouples game sensors from the AI Brain and HUD."""

    def __init__(self):
        self._subscribers: List[Callable[[GameEvent], Awaitable[None]]] = []
        self._last_event_time: Dict[str, float] = {}
        # Cooldown intervals in seconds to prevent spam
        self._cooldowns: Dict[str, float] = {
            "LAP_COMPLETED": 8.0,
            "PLAYER_DEATH": 1.0,     # Critical events have almost no cooldown
            "ACHIEVEMENT": 5.0,
            "OVERTAKE": 2.5,
            "MULTI_OVERTAKE": 2.5,
            "POSITION_LOST": 3.0,
            "WARNING": 10.0,
            "VICTORY": 3.0,
            "DEFEAT": 3.0,
            "LOW_HEALTH": 15.0,
        }

    def subscribe(self, callback: Callable[[GameEvent], Awaitable[None]]) -> None:
        """Register a subscriber callback that receives GameEvents."""
        if callback not in self._subscribers:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[GameEvent], Awaitable[None]]) -> None:
        """Remove an event subscriber callback."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def is_throttled(self, event: GameEvent) -> bool:
        """Checks if event should be dropped due to cooldown/anti-spam rules."""
        now = time.time()
        cooldown = self._cooldowns.get(event.event_type, 5.0)

        # Critical severity events always bypass non-zero cooldowns
        if event.severity == "CRITICAL":
            self._last_event_time[event.event_type] = now
            return False

        last_time = self._last_event_time.get(event.event_type, 0.0)
        if (now - last_time) < cooldown:
            logger.debug(f"Event {event.event_type} throttled ({now - last_time:.1f}s < {cooldown}s)")
            return True

        self._last_event_time[event.event_type] = now
        return False

    async def publish(self, event: GameEvent) -> None:
        """Dispatches an event to all subscribers if not throttled."""
        if self.is_throttled(event):
            return

        logger.info(f"[{event.game_name}] Event triggered: {event.event_type} - {event.summary}")
        tasks = [sub(event) for sub in self._subscribers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# Global singleton instance
event_bus = EventBus()
