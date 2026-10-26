"""Native Transparent Top-Left Desktop HUD Overlay for Raphael Gaming Copilot."""

import sys
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Dict, Any
from config.settings import get_logger
from src.game_copilot.core.event_bus import GameEvent
from src.game_copilot.ui.audio_tts import RaphaelAudioTTS

logger = get_logger("RaphaelHUDOverlay")


class RaphaelDesktopOverlay:
    """Always-on-top, borderless desktop HUD located in the top-left corner."""

    def __init__(self, x: int = 24, y: int = 24, width: int = 460, height: int = 140, enable_tts: bool = True):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.enable_tts = enable_tts

        self.root: Optional[tk.Tk] = None
        self._msg_queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._tts = RaphaelAudioTTS()
        self._running = False
        self._fade_after_id = None

    def start(self) -> None:
        """Launches the Tkinter overlay in a dedicated daemon thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_ui, daemon=True)
        self._thread.start()
        logger.info(f"Raphael Desktop Overlay launched at ({self.x}, {self.y}).")

    def _run_ui(self) -> None:
        """Tkinter GUI thread event loop."""
        self.root = tk.Tk()
        self.root.title("Raphael AI Copilot")

        # Geometry & Window attributes
        self.root.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
        self.root.overrideredirect(True)  # Frameless / Borderless
        self.root.wm_attributes("-topmost", True)  # Always on top

        # Background color
        bg_color = "#0a0e1a"
        border_cyan = "#00f0ff"
        self.root.configure(bg=border_cyan)

        # Inner frame to create 1.5px glowing border
        self.inner_frame = tk.Frame(self.root, bg=bg_color)
        self.inner_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Header Frame
        header = tk.Frame(self.inner_frame, bg=bg_color)
        header.pack(fill=tk.X, padx=12, pady=(10, 4))

        # Title Label
        title_font = tkfont.Font(family="Segoe UI", size=11, weight="bold")
        self.lbl_title = tk.Label(
            header,
            text="RAPHAEL « 智恵之王 »",
            font=title_font,
            fg="#00f0ff",
            bg=bg_color
        )
        self.lbl_title.pack(side=tk.LEFT)

        # Game Status Label
        status_font = tkfont.Font(family="Consolas", size=9)
        self.lbl_status = tk.Label(
            header,
            text="STANDBY • MONITORING",
            font=status_font,
            fg="#7dd3fc",
            bg=bg_color
        )
        self.lbl_status.pack(side=tk.RIGHT)

        # Event Badge
        badge_font = tkfont.Font(family="Segoe UI", size=8, weight="bold")
        self.lbl_badge = tk.Label(
            self.inner_frame,
            text="SYSTEM READY",
            font=badge_font,
            fg="#ffd166",
            bg="#1e2238",
            padx=6,
            pady=1
        )
        self.lbl_badge.pack(anchor="w", padx=12, pady=(2, 4))

        # Reaction / Speech Text
        speech_font = tkfont.Font(family="Segoe UI", size=10)
        self.lbl_speech = tk.Label(
            self.inner_frame,
            text="<Notice. Wisdom Lord Raphael is synchronized with Master's gameplay.>",
            font=speech_font,
            fg="#ffffff",
            bg=bg_color,
            justify=tk.LEFT,
            wraplength=self.width - 30
        )
        self.lbl_speech.pack(anchor="w", padx=12, pady=(0, 6))

        # Telemetry / Details Strip
        telem_font = tkfont.Font(family="Consolas", size=8)
        self.lbl_telem = tk.Label(
            self.inner_frame,
            text="DELTA: +0.000s | OPTIMAL RHYTHM",
            font=telem_font,
            fg="#38bdf8",
            bg=bg_color
        )
        self.lbl_telem.pack(anchor="w", padx=12, pady=(0, 8))

        # Periodic queue checker
        self.root.after(100, self._process_queue)
        self.root.mainloop()

    def _process_queue(self) -> None:
        """Polls messages from async backend to safely update Tkinter widgets."""
        try:
            while not self._msg_queue.empty():
                payload = self._msg_queue.get_nowait()
                self._apply_payload(payload)
        except Exception as e:
            logger.error(f"Error updating overlay UI: {e}")

        if self.root:
            self.root.after(100, self._process_queue)

    def _apply_payload(self, payload: Dict[str, Any]) -> None:
        """Updates text and styles on Tkinter widgets."""
        game_name = payload.get("game_name", "GAME")
        event_type = payload.get("event_type", "EVENT")
        severity = payload.get("severity", "INFO")
        reaction = payload.get("reaction", "")
        summary = payload.get("summary", "")
        details = payload.get("details", {})

        # Colors based on severity
        if severity == "CRITICAL" or severity == "WARNING":
            border_color = "#ff2a6d"
            badge_bg = "#4c0519"
            badge_fg = "#ff2a6d"
        elif severity == "CELEBRATION":
            border_color = "#ffd166"
            badge_bg = "#451a03"
            badge_fg = "#ffd166"
        else:
            border_color = "#00f0ff"
            badge_bg = "#1e2238"
            badge_fg = "#00f0ff"

        if self.root:
            self.root.configure(bg=border_color)
            self.lbl_status.config(text=f"{game_name.upper()} • ACTIVE")
            self.lbl_badge.config(text=event_type, bg=badge_bg, fg=badge_fg)

            display_text = reaction or summary
            self.lbl_speech.config(text=display_text)

            # Details
            if "lap_time_str" in details:
                delta = details.get("delta_prev_lap", 0.0)
                pos = details.get("position", 1)
                delta_str = f"{delta:+.3f}s"
                pb_str = " [NEW PERSONAL BEST]" if details.get("is_personal_best") else ""
                self.lbl_telem.config(text=f"LAP: {details['lap_time_str']} | DELTA: {delta_str} | P{pos}{pb_str}")
            elif "cause" in details:
                self.lbl_telem.config(text=f"STATUS: CASUALTY | CAUSE: {details.get('cause', '').upper()}")
            elif "achievement" in details:
                self.lbl_telem.config(text=f"UNLOCK: {details.get('achievement', '').upper()} | REWARD: CONFIRMED")
            else:
                self.lbl_telem.config(text="")

    def display_event(self, event: GameEvent, reaction: str) -> None:
        """Sends new event and reaction to the overlay and speaks it via TTS."""
        payload = {
            "game_name": event.game_name,
            "event_type": event.event_type,
            "severity": event.severity,
            "summary": event.summary,
            "reaction": reaction,
            "details": event.details,
        }
        self._msg_queue.put(payload)

        # Trigger TTS
        if self.enable_tts and reaction:
            threading.Thread(target=self._tts._speak_sync, args=(reaction,), daemon=True).start()

    def close(self) -> None:
        """Closes the overlay window."""
        self._running = False
        if self.root:
            try:
                self.root.quit()
                self.root.destroy()
            except Exception:
                pass
            self.root = None
