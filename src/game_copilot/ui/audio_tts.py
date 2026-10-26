"""TTS Audio module for Raphael's serene, analytical voice using Windows Native SAPI."""

import re
import sys
import asyncio
import subprocess
from typing import Optional
from config.settings import get_logger

logger = get_logger("RaphaelAudioTTS")


def clean_text_for_speech(text: str) -> str:
    """Prepares text for natural speech synthesis by removing special brackets."""
    # Convert <Notice. Text> -> Notice. Text
    cleaned = re.sub(r"[<>]", "", text)
    # Convert lap times like 1:47.320 into speakable format
    cleaned = re.sub(r"(\d+):(\d+)\.(\d+)", r"\1 minute \2 point \3 seconds", cleaned)
    # Convert +/- delta like +0.450s into speakable format
    cleaned = re.sub(r"\+([0-9.]+)\s*s", r"plus \1 seconds", cleaned)
    cleaned = re.sub(r"\-([0-9.]+)\s*s", r"minus \1 seconds", cleaned)
    return cleaned.strip()


class RaphaelAudioTTS:
    """Non-blocking Windows Speech Synthesizer for Raphael persona."""

    def __init__(self, voice_name: str = "Microsoft Zira Desktop", rate: int = 1):
        self.voice_name = voice_name
        self.rate = rate  # -10 to 10
        self._enabled = True

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    async def speak(self, text: str) -> None:
        """Asynchronously triggers voice synthesis without blocking the event loop."""
        if not self._enabled:
            return

        speech_text = clean_text_for_speech(text)
        if not speech_text:
            return

        # Run non-blocking subprocess in executor thread
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._speak_sync, speech_text)

    def _speak_sync(self, text: str) -> None:
        """Executes Windows SAPI speech synthesis via PowerShell."""
        if sys.platform != "win32":
            logger.debug(f"[Non-Windows TTS Mock] Raphael: {text}")
            return

        # Sanitize single quotes for PowerShell
        safe_text = text.replace("'", "''").replace('"', '`"')
        ps_cmd = (
            f"Add-Type -AssemblyName System.Speech; "
            f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"try {{ $synth.SelectVoice('{self.voice_name}') }} catch {{ }}; "
            f"$synth.Rate = {self.rate}; "
            f"$synth.Speak('{safe_text}');"
        )

        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Raphael TTS playback warning: {e}")
