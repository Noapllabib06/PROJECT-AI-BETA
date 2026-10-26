"""Assetto Corsa Competizione (ACC) Telemetry Adapter.

Reads Windows Shared Memory (Local\\acpmf_graphics) natively with 0% CPU/GPU overhead.
Requires zero game configuration or mods from the user.
"""

import sys
import mmap
import struct
import asyncio
from typing import Optional, Dict, Any, Tuple
from config.settings import get_logger
from src.game_copilot.adapters.base_adapter import BaseGameAdapter
from src.game_copilot.core.event_bus import GameEvent, EventBus

logger = get_logger("ACCAdapter")

GRAPHICS_TAG = "Local\\acpmf_graphics"
GRAPHICS_SIZE = 1588  # Approximate size of ACC graphics shared memory buffer


def format_ms_to_laptime(ms: int) -> str:
    """Converts milliseconds into MM:SS.mmm format."""
    if ms <= 0 or ms > 3600000:
        return "--:--.---"
    minutes = ms // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


class ACCAdapter(BaseGameAdapter):
    """Adapter for Assetto Corsa & Assetto Corsa Competizione shared memory."""

    def __init__(self, bus: Optional[EventBus] = None, poll_interval_sec: float = 0.1):
        super().__init__(game_name="Assetto Corsa Competizione", bus=bus)
        self.poll_interval = poll_interval_sec
        self._mmap: Optional[mmap.mmap] = None
        self._last_completed_laps: int = 0
        self._previous_lap_time_ms: Optional[int] = None
        self._best_lap_time_ms: Optional[int] = None
        self._session_active: bool = False

    def _open_shared_memory(self) -> bool:
        """Attempts to attach to Windows named shared memory mapping."""
        if sys.platform != "win32":
            return False

        try:
            # On Windows, negative fd (-1) opens named shared memory
            self._mmap = mmap.mmap(-1, GRAPHICS_SIZE, tagname=GRAPHICS_TAG, access=mmap.ACCESS_READ)
            logger.info("Successfully connected to ACC Shared Memory (Local\\acpmf_graphics).")
            return True
        except FileNotFoundError:
            # Game is not currently running
            return False
        except Exception as e:
            logger.debug(f"ACC Shared memory not available yet: {e}")
            return False

    def _read_telemetry(self) -> Optional[Dict[str, Any]]:
        """Parses the current graphics buffer from shared memory."""
        if not self._mmap:
            if not self._open_shared_memory():
                return None

        try:
            self._mmap.seek(0)
            data = self._mmap.read(160)
            if len(data) < 152:
                return None

            # Unpack initial header:
            # packetId (i), status (i), session (i)
            # currentTime (30s), lastTime (30s), bestTime (30s), split (30s)
            # completedLaps (i), position (i), iCurrentTime (i), iLastTime (i), iBestTime (i)
            header_format = "=iii30s30s30s30siiiii"
            unpacked = struct.unpack_from(header_format, data, 0)

            packet_id = unpacked[0]
            status = unpacked[1]  # 0: OFF, 1: REPLAY, 2: LIVE, 3: PAUSE
            session_type = unpacked[2]
            completed_laps = unpacked[7]
            position = unpacked[8]
            i_current_time = unpacked[9]
            i_last_time = unpacked[10]
            i_best_time = unpacked[11]

            return {
                "packet_id": packet_id,
                "status": status,
                "session_type": session_type,
                "completed_laps": completed_laps,
                "position": position,
                "current_time_ms": i_current_time,
                "last_time_ms": i_last_time,
                "best_time_ms": i_best_time,
            }
        except Exception as e:
            logger.debug(f"Error reading ACC shared memory: {e}")
            self._mmap = None
            return None

    def process_telemetry_state(self, telemetry: Dict[str, Any]) -> Optional[GameEvent]:
        """Analyzes state changes and returns GameEvent if a milestone occurred."""
        status = telemetry.get("status", 0)
        completed_laps = telemetry.get("completed_laps", 0)
        last_time_ms = telemetry.get("last_time_ms", 0)
        best_time_ms = telemetry.get("best_time_ms", 0)
        position = telemetry.get("position", 1)

        # Status 2 = LIVE session
        if status != 2 and status != 0:
            pass

        # First time detecting laps
        if self._last_completed_laps == -1:
            self._last_completed_laps = completed_laps
            self._previous_lap_time_ms = last_time_ms if last_time_ms > 0 else None
            self._best_lap_time_ms = best_time_ms if best_time_ms > 0 else None
            return None

        # Lap completion detection!
        if completed_laps > self._last_completed_laps and last_time_ms > 0:
            lap_number = completed_laps
            lap_time_str = format_ms_to_laptime(last_time_ms)
            delta_prev = 0.0
            is_improvement = False

            if self._previous_lap_time_ms and self._previous_lap_time_ms > 0:
                delta_prev = (last_time_ms - self._previous_lap_time_ms) / 1000.0
                is_improvement = delta_prev < 0

            # Personal best check
            is_personal_best = False
            if self._best_lap_time_ms is None or last_time_ms <= self._best_lap_time_ms:
                is_personal_best = True
                self._best_lap_time_ms = last_time_ms

            # Update cache
            self._previous_lap_time_ms = last_time_ms
            self._last_completed_laps = completed_laps

            # Determine severity and summary
            if is_personal_best:
                severity = "CELEBRATION"
                summary = f"Lap {lap_number} completed: {lap_time_str} (NEW PERSONAL BEST! Delta: {delta_prev:+.3f}s, P{position})"
            elif is_improvement:
                severity = "INFO"
                summary = f"Lap {lap_number} completed: {lap_time_str} (Faster by {abs(delta_prev):.3f}s, P{position})"
            else:
                severity = "INFO"
                summary = f"Lap {lap_number} completed: {lap_time_str} (Delta: {delta_prev:+.3f}s, P{position})"

            return GameEvent(
                game_name=self.game_name,
                event_type="LAP_COMPLETED",
                severity=severity,
                summary=summary,
                details={
                    "lap_number": lap_number,
                    "lap_time_ms": last_time_ms,
                    "lap_time_str": lap_time_str,
                    "delta_prev_lap": delta_prev,
                    "is_personal_best": is_personal_best,
                    "position": position,
                    "is_valid": True,
                }
            )

        self._last_completed_laps = completed_laps
        return None

    async def poll_cycle(self) -> None:
        """Single polling cycle executed periodically."""
        telemetry = self._read_telemetry()
        if telemetry:
            event = self.process_telemetry_state(telemetry)
            if event:
                await self.event_bus.publish(event)
        await asyncio.sleep(self.poll_interval)
