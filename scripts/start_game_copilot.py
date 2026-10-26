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

logger = get_logger("GameCopilotRunner")


async def main_async(enable_acc: bool = True, enable_mc: bool = True, enable_voice: bool = True, enable_overlay: bool = True):
    acc_status = "ACTIVE (Listening to Local\\acpmf_graphics)" if enable_acc else "DISABLED"
    mc_status = "ACTIVE (Streaming .minecraft/logs/latest.log)" if enable_mc else "DISABLED"
    overlay_status = "ENABLED (Top-Left)" if enable_overlay else "DISABLED"
    voice_status = "ENABLED (Tensura Japanese Neural Voice)" if enable_voice else "DISABLED"

    print("=" * 68)
    print("   « 智恵之王 » RAPHAEL AI GAMING COPILOT - LIVE ACTIVE SYSTEM")
    print("=" * 68)
    print(f"[*] Visual Overlay : {overlay_status}")
    print(f"[*] Voice Engine   : {voice_status}")
    print(f"[*] ACC Telemetry  : {acc_status}")
    print(f"[*] Minecraft Log  : {mc_status}")
    print("=" * 68)
    print("[*] Status: STANDBY. Buka game Anda (ACC / Minecraft) dan mulai bermain.")
    print("[*] Raphael akan mendeteksi dan merespon secara otomatis.")
    print("[*] Tekan CTRL+C di terminal ini untuk berhenti.")
    print("=" * 68)

    overlay: Optional[RaphaelDesktopOverlay] = None
    if enable_overlay:
        overlay = RaphaelDesktopOverlay(enable_tts=enable_voice)
        overlay.start()
        await asyncio.sleep(1.0)

    brain = RaphaelBrain()

    # Route event to Brain and HUD
    async def on_game_event(evt: GameEvent):
        reaction_dict = await brain.generate_reaction(evt)
        jp_line = reaction_dict.get("jp", "")
        en_sub = reaction_dict.get("en", "")
        print(f"\n[EVENT DETECTED] [{evt.game_name}] {evt.event_type} - {evt.summary}")
        print(f"  Raphael (JP) : {jp_line}")
        print(f"  Subtitle(EN) : {en_sub}")
        if overlay:
            overlay.display_event(evt, reaction_dict)

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
        # Keep alive loop
        while True:
            await asyncio.sleep(1.0)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        print("\n[*] Mematikan sensor dan menutup Raphael Copilot...")
        for adapter in adapters:
            await adapter.stop()
        if overlay:
            overlay.close()
        print("[*] Raphael Copilot dinonaktifkan dengan aman. Sampai jumpa, Master.")


def main():
    parser = argparse.ArgumentParser(description="Raphael AI Gaming Copilot Live Runner")
    parser.add_argument("--no-acc", action="store_true", help="Nonaktifkan sensor Assetto Corsa Competizione")
    parser.add_argument("--no-mc", action="store_true", help="Nonaktifkan sensor Minecraft")
    parser.add_argument("--no-voice", action="store_true", help="Nonaktifkan suara Jepang (hanya visual)")
    parser.add_argument("--no-overlay", action="store_true", help="Nonaktifkan desktop overlay (hanya terminal/web)")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(
            enable_acc=not args.no_acc,
            enable_mc=not args.no_mc,
            enable_voice=not args.no_voice,
            enable_overlay=not args.no_overlay
        ))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
