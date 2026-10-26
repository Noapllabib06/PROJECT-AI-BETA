"""Production Launcher for Raphael AI Gaming Copilot.

Automatically attaches to live games (Assetto Corsa Competizione, Minecraft, etc.),
displays the top-left Tensura desktop HUD overlay, and speaks Japanese voice feedback.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import time
import asyncio
import argparse
import signal
from typing import Optional
from config.settings import get_logger
from src.game_copilot.core.event_bus import event_bus, GameEvent
from src.game_copilot.core.raphael_brain import RaphaelBrain
from src.game_copilot.adapters.acc_adapter import ACCAdapter
from src.game_copilot.adapters.minecraft_adapter import MinecraftAdapter
from src.game_copilot.ui.overlay_window import RaphaelDesktopOverlay
from src.game_copilot.ui.audio_tts import RaphaelAudioTTS

logger = get_logger("GameCopilotRunner")


def unload_heavy_models():
    """Immediately unloads heavy 7B models from GPU VRAM to ensure 100% memory is free for the game."""
    try:
        import httpx
        with httpx.Client(timeout=1.5) as client:
            client.post("http://localhost:11434/api/generate", json={"model": "qwen2.5:7b", "keep_alive": 0})
    except Exception:
        pass


async def main_async(enable_acc: bool = True, enable_mc: bool = True, enable_voice: bool = True, enable_overlay: bool = False, model_name: str = "llama3.2:3b"):
    unload_heavy_models()

    mode_desc = "DESKTOP HUD OVERLAY" if enable_overlay else "PURE VOICE SPOTTER (Radio Helm - 0% Gangguan Layar)"
    acc_status = "ACTIVE (Waiting for ACC to start...)" if enable_acc else "DISABLED"
    mc_status = "ACTIVE (Streaming .minecraft/logs/latest.log)" if enable_mc else "DISABLED"
    voice_status = "ENABLED (Tensura Crystal Divine Voice & Chime)" if enable_voice else "DISABLED"

    print("=" * 72)
    print("   « 智恵之王 » RAPHAEL AI GAMING COPILOT - GT3 VOICE SPOTTER")
    print("=" * 72)
    print(f"[*] Operation Mode : {mode_desc}")
    print(f"[*] Active LLM Model: {model_name} (High-Context Reasoning & Fluid Speech)")
    print(f"[*] Voice Engine   : {voice_status}")
    print(f"[*] ACC Telemetry  : {acc_status}")
    print(f"[*] Minecraft Log  : {mc_status}")
    print("=" * 72)
    print("[*] Status: STANDBY. Buka game Anda (ACC / Minecraft) dan mulai bermain.")
    print("[*] Raphael akan berbicara langsung ke headset/speaker Anda secara otomatis.")
    print("[*] Tekan CTRL+C di terminal ini untuk berhenti.")
    print("=" * 72)

    overlay: Optional[RaphaelDesktopOverlay] = None
    stop_event = asyncio.Event()

    def _trigger_stop(*args):
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda s, f: _trigger_stop())
        except Exception:
            pass

    if enable_overlay:
        overlay = RaphaelDesktopOverlay(
            enable_tts=enable_voice,
            on_close=lambda: _trigger_stop()
        )
        overlay.start()
        await asyncio.sleep(0.5)

    tts: Optional[RaphaelAudioTTS] = RaphaelAudioTTS() if enable_voice else None
    brain = RaphaelBrain(model_name=model_name)

    # Route event to Brain, TTS, and optional HUD
    async def on_game_event(evt: GameEvent):
        reaction_dict = await brain.generate_reaction(evt)
        jp_line = reaction_dict.get("jp", "")
        en_sub = reaction_dict.get("en", "")

        print("\n" + "═" * 72)
        print(f" 🏁 [{evt.game_name}] {evt.event_type} • {evt.summary}")
        print("─" * 72)
        print(f" 🔊 Raphael (JP) : {jp_line}")
        print(f" 💬 Subtitle (EN): {en_sub}")
        print("═" * 72)

        if overlay:
            overlay.display_event(evt, reaction_dict)
        elif tts and jp_line:
            # Voice Spotter mode: trigger authentic Japanese speech directly into headphones!
            asyncio.create_task(tts.speak_japanese(jp_line))

    event_bus.subscribe(on_game_event)

    # Start Active Sensors
    adapters = []
    if enable_acc:
        acc = ACCAdapter()
        await acc.start()
        adapters.append(acc)

    if enable_mc:
        mc = MinecraftAdapter()
        await mc.start()
        adapters.append(mc)

    try:
        # Keep alive loop with fast exit checking
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        print("\n[*] Mematikan sensor dan menutup Raphael Copilot...")
        for adapter in adapters:
            try:
                await adapter.stop()
            except Exception:
                pass
        if overlay:
            overlay.close()
        print("[*] Raphael Copilot dinonaktifkan dengan aman. Sampai jumpa, Master.")


def main():
    parser = argparse.ArgumentParser(description="Raphael AI Gaming Copilot Live Runner")
    parser.add_argument("--overlay", action="store_true", help="Aktifkan desktop HUD overlay (default: False / Pure Voice Spotter)")
    parser.add_argument("--no-acc", action="store_true", help="Nonaktifkan sensor Assetto Corsa Competizione")
    parser.add_argument("--no-mc", action="store_true", help="Nonaktifkan sensor Minecraft")
    parser.add_argument("--no-voice", action="store_true", help="Nonaktifkan suara Jepang (hanya terminal)")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(
            enable_acc=not args.no_acc,
            enable_mc=not args.no_mc,
            enable_voice=not args.no_voice,
            enable_overlay=args.overlay
        ))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
