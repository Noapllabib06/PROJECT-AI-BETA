"""Raphael Authentic Japanese TTS Voice using Edge-TTS NanamiNeural and WinMM Native Playback."""

import os
import re
import sys
import uuid
import ctypes
import asyncio
from pathlib import Path
from typing import Optional
from config.settings import get_logger

logger = get_logger("RaphaelAudioTTS")

CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "raw" / "audio_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def clean_japanese_for_speech(text: str) -> str:
    """Prepares Japanese text for natural speech synthesis by removing anime notice brackets."""
    # Remove < > or « »
    cleaned = re.sub(r"[<«》>『』]", "", text)
    # Ensure natural pauses around Kokuchi (告。) or Kai (解。)
    cleaned = re.sub(r"^(告|解|報告|警告)[。、\.\s]*", r"\1、", cleaned)
    return cleaned.strip()


class RaphaelAudioTTS:
    """High-fidelity Tensura voice synthesizer using Japanese neural voice NanamiNeural."""

    def __init__(self, voice_name: str = "ja-JP-NanamiNeural", rate: str = "+0%"):
        self.voice_name = voice_name
        self.rate = rate
        self._enabled = True
        self._lock = asyncio.Lock()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def _play_audio_file(self, file_path: str) -> None:
        """Plays audio file using native Windows Multimedia MCI with 0% latency and no extra tools."""
        if sys.platform != "win32":
            logger.debug(f"[Non-Windows TTS Mock] Playing: {file_path}")
            return

        try:
            alias = f"r_audio_{uuid.uuid4().hex[:8]}"
            abs_path = os.path.abspath(file_path)
            # Open media file via winmm
            ctypes.windll.winmm.mciSendStringW(f'open "{abs_path}" type mpegvideo alias {alias}', None, 0, None)
            # Play and wait for completion in background worker thread
            ctypes.windll.winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
            ctypes.windll.winmm.mciSendStringW(f"close {alias}", None, 0, None)
        except Exception as e:
            logger.warning(f"WinMM audio playback exception: {e}")

    async def speak_japanese(self, jp_text: str) -> None:
        """Asynchronously synthesizes Japanese speech using edge-tts and plays it."""
        if not self._enabled:
            return

        speech_text = clean_japanese_for_speech(jp_text)
        if not speech_text:
            return

        temp_audio_file = CACHE_DIR / f"raphael_voice_{uuid.uuid4().hex[:8]}.mp3"

        try:
            import edge_tts
            communicate = edge_tts.Communicate(speech_text, self.voice_name, rate=self.rate)
            await communicate.save(str(temp_audio_file))

            # Play in worker thread so event loop remains free
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._play_audio_file, str(temp_audio_file))
        except Exception as e:
            logger.warning(f"Edge-TTS synthesis error ({e}), falling back to Windows SAPI.")
            self._fallback_sapi(speech_text)
        finally:
            # Clean up temp file
            if temp_audio_file.exists():
                try:
                    temp_audio_file.unlink()
                except Exception:
                    pass

    def _fallback_sapi(self, text: str) -> None:
        """Fallback to Windows SAPI."""
        import subprocess
        safe_text = text.replace("'", "''")
        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$synth.Speak('{safe_text}');"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                timeout=10,
            )
        except Exception:
            pass

    async def speak(self, text: str) -> None:
        """General interface accepting Japanese text."""
        await self.speak_japanese(text)
