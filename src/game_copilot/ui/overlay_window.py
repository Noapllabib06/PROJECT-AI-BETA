"""Native Transparent Desktop HUD Overlay with Authentic Tensura Aesthetic, Bilingual Display, Win32 Hardened Topmost, and Draggable Window."""

import sys
import queue
import threading
import asyncio
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Dict, Any
from config.settings import get_logger
from src.game_copilot.core.event_bus import GameEvent
from src.game_copilot.ui.audio_tts import RaphaelAudioTTS

logger = get_logger("RaphaelHUDOverlay")


class RaphaelDesktopOverlay:
    """Always-on-top, borderless desktop HUD located in the top-left corner (draggable across screens)."""

    def __init__(self, x: int = 24, y: int = 24, width: int = 480, height: int = 160, enable_tts: bool = True):
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
        self._idle_timer_id = None
        self._idle_timeout_ms = 9000  # Return to idle after 9 seconds

        self._drag_x = 0
        self._drag_y = 0

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
        header.pack(fill=tk.X, padx=12, pady=(8, 2))

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
            text="IDLE • SOUL LINK STABLE",
            font=status_font,
            fg="#7dd3fc",
            bg=bg_color
        )
        self.lbl_status.pack(side=tk.RIGHT)

        # Event Badge
        badge_font = tkfont.Font(family="Segoe UI", size=8, weight="bold")
        self.lbl_badge = tk.Label(
            self.inner_frame,
            text="STANDBY",
            font=badge_font,
            fg="#00f0ff",
            bg="#101827",
            padx=6,
            pady=1
        )
        self.lbl_badge.pack(anchor="w", padx=12, pady=(1, 3))

        # Japanese Voice Text (Line 1)
        jp_font = tkfont.Font(family="Meiryo", size=10, weight="bold")
        self.lbl_speech_jp = tk.Label(
            self.inner_frame,
            text="<告。魂の回廊（ソウルリンク）は安定。戦況を常時観測中です、マスター。>",
            font=jp_font,
            fg="#ffffff",
            bg=bg_color,
            justify=tk.LEFT,
            wraplength=self.width - 24
        )
        self.lbl_speech_jp.pack(anchor="w", padx=12, pady=(0, 2))

        # English Subtitle (Line 2)
        en_font = tkfont.Font(family="Segoe UI", size=9, slant="italic")
        self.lbl_speech_en = tk.Label(
            self.inner_frame,
            text="[Subtitle] <Notice. Soul corridor is stable. Actively monitoring field conditions, Master.>",
            font=en_font,
            fg="#ffd166",
            bg=bg_color,
            justify=tk.LEFT,
            wraplength=self.width - 24
        )
        self.lbl_speech_en.pack(anchor="w", padx=12, pady=(0, 4))

        # Telemetry / Details Strip
        telem_font = tkfont.Font(family="Consolas", size=8)
        self.lbl_telem = tk.Label(
            self.inner_frame,
            text="STATUS: OPTIMAL | LINK: 100% SYNCHRONIZED [DRAG TO MOVE]",
            font=telem_font,
            fg="#38bdf8",
            bg=bg_color
        )
        self.lbl_telem.pack(anchor="w", padx=12, pady=(0, 6))

        # ==================== DRAGGABLE MOUSE BINDINGS ====================
        def _on_drag_start(event):
            self._drag_x = event.x
            self._drag_y = event.y

        def _on_drag_motion(event):
            deltax = event.x - self._drag_x
            deltay = event.y - self._drag_y
            new_x = self.root.winfo_x() + deltax
            new_y = self.root.winfo_y() + deltay
            self.x = new_x
            self.y = new_y
            self.root.geometry(f"+{new_x}+{new_y}")

        # Bind dragging to all labels and frames so user can grab and move anywhere
        for widget in [
            self.root, self.inner_frame, header, self.lbl_title,
            self.lbl_status, self.lbl_badge, self.lbl_speech_jp,
            self.lbl_speech_en, self.lbl_telem
        ]:
            widget.bind("<ButtonPress-1>", _on_drag_start)
            widget.bind("<B1-Motion>", _on_drag_motion)
            try:
                widget.configure(cursor="fleur")
            except Exception:
                pass

        # ==================== WIN32 ABSOLUTE TOPMOST ENFORCEMENT ====================
        if sys.platform == "win32":
            import ctypes
            def _enforce_win32_topmost():
                try:
                    hwnd = self.root.winfo_id()
                    # HWND_TOPMOST = -1, SWP_NOSIZE = 0x0001, SWP_NOMOVE = 0x0002, SWP_NOACTIVATE = 0x0010
                    # Calling SetWindowPos periodically prevents DirectX exclusive/borderless windows from burying HUD
                    ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0013)
                except Exception:
                    pass
                if self.root:
                    self.root.after(1200, _enforce_win32_topmost)

            self.root.after(300, _enforce_win32_topmost)

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

    def _set_idle_state(self) -> None:
        """Restores the HUD to serene, ambient idle state when no events occur."""
        if not self.root:
            return
        self.root.configure(bg="#00f0ff")
        self.lbl_status.config(text="IDLE • SOUL LINK STABLE", fg="#7dd3fc")
        self.lbl_badge.config(text="STANDBY", bg="#101827", fg="#00f0ff")
        self.lbl_speech_jp.config(
            text="<告。魂の回廊（ソウルリンク）は安定。戦況を常時観測中です、マスター。>",
            fg="#ffffff"
        )
        self.lbl_speech_en.config(
            text="[Subtitle] <Notice. Soul corridor is stable. Actively monitoring field telemetry, Master.>",
            fg="#ffd166"
        )
        self.lbl_telem.config(text="STATUS: OPTIMAL | LINK: 100% SYNCHRONIZED [DRAG TO MOVE]")

    def _apply_payload(self, payload: Dict[str, Any]) -> None:
        """Updates text and styles on Tkinter widgets."""
        game_name = payload.get("game_name", "GAME")
        event_type = payload.get("event_type", "EVENT")
        severity = payload.get("severity", "INFO")
        reaction_jp = payload.get("reaction_jp", "")
        reaction_en = payload.get("reaction_en", "")
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
            self.lbl_status.config(text=f"{game_name.upper()} • ACTIVE", fg="#e0f2fe")
            self.lbl_badge.config(text=event_type, bg=badge_bg, fg=badge_fg)

            self.lbl_speech_jp.config(text=reaction_jp or summary)
            self.lbl_speech_en.config(text=f"[Subtitle] {reaction_en}" if reaction_en else "")

            # Telemetry Strip Formatting
            if event_type in ("OVERTAKE", "MULTI_OVERTAKE"):
                old_p = details.get("old_position", "?")
                new_p = details.get("new_position", "?")
                count = details.get("count", 1)
                self.lbl_telem.config(text=f"MANEUVER: OVERTAKE | ADVANCED: P{old_p} -> P{new_p} (+{count} CARS)")
            elif event_type == "POSITION_LOST":
                old_p = details.get("old_position", "?")
                new_p = details.get("new_position", "?")
                count = details.get("count", 1)
                self.lbl_telem.config(text=f"WARNING: POSITION LOST | DROPPED: P{old_p} -> P{new_p} (-{count} CARS)")
            elif "lap_time_str" in details:
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
                self.lbl_telem.config(text="TELEMETRY RECORDED • OPTIMAL")

            # Reset idle countdown
            if self._idle_timer_id:
                self.root.after_cancel(self._idle_timer_id)
            self._idle_timer_id = self.root.after(self._idle_timeout_ms, self._set_idle_state)

    def display_event(self, event: GameEvent, reaction_dict: Dict[str, str]) -> None:
        """Sends new event and bilingual reaction to the overlay and speaks in Japanese."""
        payload = {
            "game_name": event.game_name,
            "event_type": event.event_type,
            "severity": event.severity,
            "summary": event.summary,
            "reaction_jp": reaction_dict.get("jp", ""),
            "reaction_en": reaction_dict.get("en", ""),
            "details": event.details,
        }
        self._msg_queue.put(payload)

        # Trigger authentic Japanese neural speech
        if self.enable_tts and reaction_dict.get("jp"):
            def _async_speak():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._tts.speak_japanese(reaction_dict["jp"]))
                loop.close()

            threading.Thread(target=_async_speak, daemon=True).start()

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
