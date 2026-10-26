"""Base Game Adapter interface for modular sensor integration."""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional
from config.settings import get_logger
from src.game_copilot.core.event_bus import EventBus, event_bus

logger = get_logger("BaseGameAdapter")


class BaseGameAdapter(ABC):
    """Abstract base class that all game-specific telemetry adapters must implement."""

    def __init__(self, game_name: str, bus: Optional[EventBus] = None):
        self.game_name = game_name
        self.event_bus = bus or event_bus
        self._running = False
        self._task: Optional[asyncio.Task] = None

    @abstractmethod
    async def poll_cycle(self) -> None:
        """Single polling cycle to check game state or read buffer."""
        pass

    async def _worker_loop(self) -> None:
        """Internal background loop running poll_cycle periodically."""
        logger.info(f"Adapter for [{self.game_name}] started listening.")
        while self._running:
            try:
                await self.poll_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in [{self.game_name}] adapter loop: {e}")
                await asyncio.sleep(2.0)
        logger.info(f"Adapter for [{self.game_name}] stopped.")

    async def start(self) -> None:
        """Starts the adapter background worker."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        """Stops the adapter background worker."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    def is_running(self) -> bool:
        """Returns True if the adapter is currently active."""
        return self._running
