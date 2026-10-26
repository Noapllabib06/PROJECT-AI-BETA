"""Minecraft Log Streamer Adapter.

Streams real-time gameplay events (player deaths, advancements, challenges)
from %APPDATA%/.minecraft/logs/latest.log with zero CPU overhead.
"""

import os
import re
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from config.settings import get_logger
from src.game_copilot.adapters.base_adapter import BaseGameAdapter
from src.game_copilot.core.event_bus import GameEvent, EventBus

logger = get_logger("MinecraftAdapter")

# Common Minecraft death message patterns
DEATH_PATTERNS = [
    r"was slain by (?P<killer>.+)",
    r"was shot by (?P<killer>.+)",
    r"was blown up by (?P<killer>.+)",
    r"was killed by (?P<killer>.+)",
    r"fell from a high place",
    r"hit the ground too hard",
    r"drowned",
    r"experienced kinetic energy",
    r"burned to death",
    r"went up in flames",
    r"tried to swim in lava",
    r"suffocated in a wall",
    r"starved to death",
    r"was squashed by a falling anvil",
    r"withered away",
]

ADVANCEMENT_PATTERN = r"has made the advancement \[(?P<advancement>.+)\]"
CHALLENGE_PATTERN = r"has completed the challenge \[(?P<challenge>.+)\]"
CHAT_LINE_REGEX = re.compile(r"\[(?P<time>\d{2}:\d{2}:\d{2})\] \[[^\]]+\]: \[CHAT\] (?P<player>\w+) (?P<msg>.+)")


class MinecraftAdapter(BaseGameAdapter):
    """Adapter that reads Minecraft log events live."""

    def __init__(self, log_path: Optional[str] = None, bus: Optional[EventBus] = None):
        super().__init__(game_name="Minecraft", bus=bus)
        if log_path:
            self.log_file = Path(log_path)
        else:
            appdata = os.getenv("APPDATA", "")
            self.log_file = Path(appdata) / ".minecraft" / "logs" / "latest.log"

        self._file_handle = None
        self._last_inode = None

    def parse_log_line(self, line: str) -> Optional[GameEvent]:
        """Parses a single chat/event line from Minecraft log."""
        line = line.strip()
        if "[CHAT]" not in line:
            return None

        match = CHAT_LINE_REGEX.search(line)
        if not match:
            return None

        player = match.group("player")
        msg = match.group("msg")

        # 1. Check for Challenge / Victory (e.g. Free the End)
        chal_match = re.search(CHALLENGE_PATTERN, msg)
        if chal_match:
            chal_name = chal_match.group("challenge")
            severity = "CELEBRATION" if "End" in chal_name else "INFO"
            event_type = "VICTORY" if "Free the End" in chal_name else "ACHIEVEMENT"
            return GameEvent(
                game_name=self.game_name,
                event_type=event_type,
                severity=severity,
                summary=f"{player} completed challenge: [{chal_name}]",
                details={"player": player, "challenge": chal_name, "raw_msg": msg}
            )

        # 2. Check for Advancement
        adv_match = re.search(ADVANCEMENT_PATTERN, msg)
        if adv_match:
            adv_name = adv_match.group("advancement")
            return GameEvent(
                game_name=self.game_name,
                event_type="ACHIEVEMENT",
                severity="INFO",
                summary=f"{player} achieved: [{adv_name}]",
                details={"player": player, "achievement": adv_name, "raw_msg": msg}
            )

        # 3. Check for Death
        for pattern in DEATH_PATTERNS:
            death_match = re.search(pattern, msg)
            if death_match:
                cause = death_match.group("killer") if "killer" in death_match.groupdict() else pattern
                return GameEvent(
                    game_name=self.game_name,
                    event_type="PLAYER_DEATH",
                    severity="CRITICAL",
                    summary=f"{player} died ({cause})",
                    details={"player": player, "cause": cause, "raw_msg": msg}
                )

        return None

    async def poll_cycle(self) -> None:
        """Polls log file for newly appended lines."""
        if not self.log_file.exists():
            await asyncio.sleep(2.0)
            return

        try:
            if not self._file_handle:
                self._file_handle = open(self.log_file, "r", encoding="utf-8", errors="ignore")
                # Seek to end so we only read new live events
                self._file_handle.seek(0, os.SEEK_END)

            while True:
                line = self._file_handle.readline()
                if not line:
                    break
                event = self.parse_log_line(line)
                if event:
                    await self.event_bus.publish(event)
        except Exception as e:
            logger.debug(f"Minecraft log read exception: {e}")
            if self._file_handle:
                try:
                    self._file_handle.close()
                except Exception:
                    pass
                self._file_handle = None

        await asyncio.sleep(0.5)

    async def stop(self) -> None:
        """Stops log tailing and closes handle."""
        await super().stop()
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None
