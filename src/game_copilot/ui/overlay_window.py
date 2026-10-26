"""Native Transparent Desktop HUD Overlay with Authentic Tensura Aesthetic, Bilingual Display, Win32 Hardened Topmost, and Draggable Window."""

import sys
import queue
import threading
import asyncio
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional, Dict, Any, Callable
from config.settings import get_logger
from src.game_copilot.core.event_bus import GameEvent
from src.game_copilot.ui.audio_tts import RaphaelAudioTTS

logger = get_logger("RaphaelHUDOverlay")


class RaphaelDesktopOverlay:
    """Always-on-top, borderless desktop HUD located in the top-left corner (draggable across screens)."""

    def __init__(
        self,
        x: int = 24,
        y: int = 24,
        width: int = 480,
        height: int = 160,
        enable_tts: bool = True,
        on_close: Optional[Callable[[], None]] = None
    ):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.enable_tts = enable_tts
        self.on_close = on_close

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

        # Close Button (✕)
        self.btn_close = tk.Label(
            header,
            text=" ✕ ",
            font=tkfont.Font(family="Segoe UI", size=9, weight="bold"),
            fg="#94a3b8",
            bg="#111827",
            padx=3,
            pady=1,
            cursor="hand2"
        )
        self.btn_close.pack(side=tk.RIGHT)
        self.btn_close.bind("<Enter>", lambda e: self.btn_close.config(fg="#ffffff", bg="#ef4444"))
        self.btn_close.bind("<Leave>", lambda e: self.btn_close.config(fg="#94a3b8", bg="#111827"))
        self.btn_close.bind("<Button-1>", lambda e: self._handle_user_exit())

        # Game Status Label
        status_font = tkfont.Font(family="Consolas", size=9)
        self.lbl_status = tk.Label(
            header,
            text="IDLE • SOUL LINK STABLE",
            font=status_font,
            fg="#7dd3fc",
            bg=bg_color
        )
        self.lbl_status.pack(side=tk.RIGHT, padx=(0, 8))

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
            if not self.root:
                return
            deltax = event.x - self._drag_x
            deltay = event.y - self._drag_y
            new_x = self.root.winfo_x() + deltax
            new_y = self.root.winfo_y() + deltay
            self.x = new_x
            self.y = new_y
            self.root.geometry(f"+{new_x}+{new_y}")

        # Context Menu & Right-click exit
        self.context_menu = tk.Menu(
            self.root,
            tearoff=0,
            bg="#0f172a",
            fg="#e2e8f0",
            activebackground="#0284c7",
            activeforeground="#ffffff",
            font=("Segoe UI", 9)
        )
        self.context_menu.add_command(label="✕ Tutup Raphael Copilot (Exit)", command=self._handle_user_exit)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="↻ Reset Posisi ke Default", command=self._reset_position)

        def _show_context_menu(event):
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()

        # Bind dragging and context menu to all labels and frames so user can grab and move anywhere
        interactive_widgets = [
            self.root, self.inner_frame, header, self.lbl_title,
            self.lbl_status, self.lbl_badge, self.lbl_speech_jp,
            self.lbl_speech_en, self.lbl_telem
        ]
        for widget in interactive_widgets:
            widget.bind("<ButtonPress-1>", _on_drag_start)
            widget.bind("<B1-Motion>", _on_drag_motion)
            widget.bind("<Button-3>", _show_context_menu)
            try:
                widget.configure(cursor="fleur")
            except Exception:
                pass

        # Escape key closes overlay
        self.root.bind("<Escape>", lambda e: self._handle_user_exit())

        # ==================== WIN32 NO-INTERFERENCE TOPMOST SETUP ====================
        if sys.platform == "win32":
            import ctypes

            HWND_TOPMOST = ctypes.c_void_p(-1)
            SWP_NOSIZE = 0x0001
            SWP_NOMOVE = 0x0002
            SWP_NOACTIVATE = 0x0010
            SWP_SHOWWINDOW = 0x0040
            TOPMOST_FLAGS = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW

            GWL_EXSTYLE = -20
            WS_EX_TOPMOST = 0x00000008
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_NOACTIVATE = 0x08000000  # Crucial: NEVER steal focus from ACC/game controls

            def _init_win32_overlay():
                if not self.root:
                    return
                try:
                    child = self.root.winfo_id()
                    root_hw = ctypes.windll.user32.GetAncestor(child, 3)  # GA_ROOTOWNER
                    target_hwnd = root_hw if root_hw else child

                    # Set styles ONCE: non-activating, tool window, topmost
                    ex_style = ctypes.windll.user32.GetWindowLongW(target_hwnd, GWL_EXSTYLE)
                    ctypes.windll.user32.SetWindowLongW(
                        target_hwnd,
                        GWL_EXSTYLE,
                        ex_style | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
                    )

                    # Position in topmost band ONCE without activating or racing with game
                    ctypes.windll.user32.SetWindowPos(
                        target_hwnd,
                        HWND_TOPMOST,
                        0, 0, 0, 0,
                        TOPMOST_FLAGS
                    )
                except Exception as e:
                    logger.debug(f"Win32 styles setup: {e}")

            # Apply once on startup - NO repetitive polling loop to prevent game control overrides
            self.root.after(150, _init_win32_overlay)

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
        """Closes the overlay window cleanly without thread corruption."""
        self._running = False
        if self.root:
            try:
                self.root.after(0, self._destroy_ui)
            except Exception:
                try:
                    self.root.destroy()
                except Exception:
                    pass
                self.root = None

    def _destroy_ui(self) -> None:
        if self.root:
            try:
                self.root.destroy()
            except Exception:
                pass
            self.root = None

    def _handle_user_exit(self, event=None) -> None:
        """Handles explicit user shutdown from UI button, context menu, or Escape key."""
        logger.info("Pengguna meminta penghentian Raphael Copilot melalui UI.")
        self.close()
        if self.on_close:
            try:
                self.on_close()
            except Exception as e:
                logger.error(f"Error in on_close callback: {e}")
        else:
            import os
            os._exit(0)

    def _reset_position(self) -> None:
        """Resets the overlay position to default coordinates."""
        self.x = 24
        self.y = 24
        if self.root:
            self.root.geometry(f"+{self.x}+{self.y}")
