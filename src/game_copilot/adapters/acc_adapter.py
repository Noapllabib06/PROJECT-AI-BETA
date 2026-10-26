"""Assetto Corsa Competizione (ACC) Telemetry Adapter.

Reads Windows Shared Memory (Local\\acpmf_graphics) natively with 0% CPU/GPU overhead.
Uses OpenFileMappingW to ensure Python NEVER pre-creates or locks the mapping before ACC,
completely preventing EXCEPTION_ACCESS_VIOLATION in AC2-Win64-Shipping.exe.
"""

import sys
import struct
import asyncio
import ctypes
from ctypes import wintypes
from typing import Optional, Dict, Any
from config.settings import get_logger
from src.game_copilot.adapters.base_adapter import BaseGameAdapter
from src.game_copilot.core.event_bus import GameEvent, EventBus

logger = get_logger("ACCAdapter")

GRAPHICS_TAG = "Local\\acpmf_graphics"
FILE_MAP_READ = 0x0004
GRAPHICS_SIZE = 1588

# Setup Win32 Kernel32 prototypes
if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
    OpenFileMappingW = kernel32.OpenFileMappingW
    OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    OpenFileMappingW.restype = wintypes.HANDLE

    MapViewOfFile = kernel32.MapViewOfFile
    MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
    MapViewOfFile.restype = ctypes.c_void_p

    UnmapViewOfFile = kernel32.UnmapViewOfFile
    UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    UnmapViewOfFile.restype = wintypes.BOOL

    CloseHandle = kernel32.CloseHandle
    CloseHandle.argtypes = [wintypes.HANDLE]
    CloseHandle.restype = wintypes.BOOL


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
        self._h_map: Optional[int] = None
        self._p_buf: Optional[int] = None
        self._last_completed_laps: int = 0
        self._previous_lap_time_ms: Optional[int] = None
        self._best_lap_time_ms: Optional[int] = None
        self._connected: bool = False

    def _open_shared_memory(self) -> bool:
        """Attaches ONLY to an existing mapping created by ACC. Never creates or locks the name."""
        if sys.platform != "win32":
            return False

        try:
            # OpenFileMappingW fails (returns 0/NULL) if ACC is not running.
            # This is critical: it guarantees Python NEVER creates the mapping before ACC!
            h_map = OpenFileMappingW(FILE_MAP_READ, False, GRAPHICS_TAG)
            if not h_map:
                return False

            p_buf = MapViewOfFile(h_map, FILE_MAP_READ, 0, 0, GRAPHICS_SIZE)
            if not p_buf:
                CloseHandle(h_map)
                return False

            self._h_map = h_map
            self._p_buf = p_buf
            if not self._connected:
                self._connected = True
                logger.info("ACC process detected. Successfully attached to Local\\acpmf_graphics.")
            return True
        except Exception as e:
            logger.debug(f"ACC Shared memory check: {e}")
            self._close_handles()
            return False

    def _close_handles(self) -> None:
        """Releases memory view and handle cleanly."""
        if sys.platform == "win32":
            if self._p_buf:
                try:
                    UnmapViewOfFile(self._p_buf)
                except Exception:
                    pass
                self._p_buf = None
            if self._h_map:
                try:
                    CloseHandle(self._h_map)
                except Exception:
                    pass
                self._h_map = None
        self._connected = False

    def _read_telemetry(self) -> Optional[Dict[str, Any]]:
        """Parses the current graphics buffer from shared memory safely."""
        if not self._p_buf:
            if not self._open_shared_memory():
                return None

        try:
            # Read 160 bytes from the mapped memory address
            raw_bytes = ctypes.string_at(self._p_buf, 160)
            if len(raw_bytes) < 152:
                return None

            header_format = "=iii30s30s30s30siiiii"
            unpacked = struct.unpack_from(header_format, raw_bytes, 0)

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
            logger.debug(f"Error reading ACC buffer: {e}")
            self._close_handles()
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

        # Lap completion detection
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

    async def stop(self) -> None:
        """Stops adapter and releases Win32 handles."""
        await super().stop()
        self._close_handles()
