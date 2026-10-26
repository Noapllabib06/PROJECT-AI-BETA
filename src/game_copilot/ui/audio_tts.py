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
    """High-fidelity Tensura voice synthesizer with crystalline divine chime and tuned feminine divine pitch."""

    def __init__(
        self,
        voice_name: str = "ja-JP-NanamiNeural",
        rate: str = "+6%",
        pitch: str = "+18Hz",
        play_chime: bool = True
    ):
        self.voice_name = voice_name
        self.rate = rate
        self.pitch = pitch
        self.play_chime = play_chime
        self._enabled = True
        self._lock = asyncio.Lock()
        self._chime_path = CACHE_DIR / "tensura_chime.wav"
        if not self._chime_path.exists():
            self._generate_default_chime(self._chime_path)

    @staticmethod
    def _generate_default_chime(target_path: Path) -> None:
        """Generates authentic high-frequency crystalline chime for Tensura Voice of the World preamble."""
        try:
            import wave
            import struct
            import math
            sample_rate = 44100
            duration = 0.38
            num_samples = int(sample_rate * duration)
            f1, f2, f3 = 1760.0, 2637.0, 3520.0  # High harmonic crystal triad
            with wave.open(str(target_path), 'w') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(sample_rate)
                for i in range(num_samples):
                    t = i / sample_rate
                    env = math.exp(-t * 10.0) * (1.0 - math.exp(-t * 120.0))
                    val = 0.5 * math.sin(2 * math.pi * f1 * t) + 0.35 * math.sin(2 * math.pi * f2 * t) + 0.15 * math.sin(2 * math.pi * f3 * t)
                    sample = int(32767.0 * env * val * 0.85)
                    wav.writeframes(struct.pack('<h', max(-32768, min(32767, sample))))
        except Exception:
            pass

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
        """Asynchronously synthesizes Japanese speech using edge-tts and plays it with Tensura chime."""
        if not self._enabled:
            return

        speech_text = clean_japanese_for_speech(jp_text)
        if not speech_text:
            return

        temp_audio_file = CACHE_DIR / f"raphael_voice_{uuid.uuid4().hex[:8]}.mp3"

        try:
            import edge_tts
            communicate = edge_tts.Communicate(
                speech_text,
                self.voice_name,
                rate=self.rate,
                pitch=self.pitch
            )
            await communicate.save(str(temp_audio_file))

            # Play chime preamble followed by the voice
            loop = asyncio.get_event_loop()
            if self.play_chime and self._chime_path.exists():
                await loop.run_in_executor(None, self._play_audio_file, str(self._chime_path))
                await asyncio.sleep(0.06)

            # Play voice in worker thread so event loop remains free
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
