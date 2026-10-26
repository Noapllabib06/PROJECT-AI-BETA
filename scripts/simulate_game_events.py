"""Interactive Gaming Copilot & Raphael Persona Simulator.

Simulates live in-game events for Assetto Corsa Competizione (ACC) and Minecraft.
Allows immediate testing of HUD overlay, Raphael reactions, and voice synthesis.
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
from typing import Optional
from config.settings import get_logger
from src.game_copilot.core.event_bus import event_bus, GameEvent
from src.game_copilot.core.raphael_brain import RaphaelBrain
from src.game_copilot.adapters.acc_adapter import ACCAdapter
from src.game_copilot.adapters.minecraft_adapter import MinecraftAdapter
from src.game_copilot.ui.overlay_window import RaphaelDesktopOverlay

logger = get_logger("CopilotSimulator")


async def run_simulation(enable_overlay: bool = True, enable_voice: bool = True):
    print("=" * 65)
    print("  RAPHAEL AI GAMING COPILOT - LIVE TELEMETRY SIMULATOR")
    print("=" * 65)
    print(f"[*] Visual Overlay : {'ENABLED (Top-Left)' if enable_overlay else 'DISABLED'}")
    print(f"[*] Voice Synthesis: {'ENABLED (Windows SAPI)' if enable_voice else 'DISABLED'}")
    print("=" * 65)

    overlay: Optional[RaphaelDesktopOverlay] = None
    if enable_overlay:
        overlay = RaphaelDesktopOverlay(enable_tts=enable_voice)
        overlay.start()
        time.sleep(1.0)  # Wait for UI window to anchor

    brain = RaphaelBrain()
    acc_adapter = ACCAdapter()
    mc_adapter = MinecraftAdapter()

    # Bus subscriber to route events to HUD
    async def on_event(evt: GameEvent):
        reaction = await brain.generate_reaction(evt)
        print(f"\n[EVENT] Game: {evt.game_name} | Type: {evt.event_type} | Severity: {evt.severity}")
        print(f"  Summary : {evt.summary}")
        print(f"  Raphael : {reaction}")
        if overlay:
            overlay.display_event(evt, reaction)

    event_bus.subscribe(on_event)

    try:
        # STEP 1: ACC Lap 1 Completed
        print("\n>>> Scenario 1: Assetto Corsa Competizione - Lap 1 completed (Baseline lap)")
        await asyncio.sleep(2.0)
        lap1_event = acc_adapter.process_telemetry_state({
            "status": 2,
            "completed_laps": 1,
            "last_time_ms": 112410,  # 1:52.410
            "best_time_ms": 112410,
            "position": 5,
        })
        if lap1_event:
            await event_bus.publish(lap1_event)

        # STEP 2: ACC Lap 2 Completed (IMPROVEMENT! Delta -1.590s)
        print("\n>>> Scenario 2: ACC - Lap 2 completed with significant lap time improvement (-1.590s)")
        await asyncio.sleep(6.0)
        lap2_event = acc_adapter.process_telemetry_state({
            "status": 2,
            "completed_laps": 2,
            "last_time_ms": 110820,  # 1:50.820 (Faster by 1.590s!)
            "best_time_ms": 110820,
            "position": 3,
        })
        if lap2_event:
            await event_bus.publish(lap2_event)

        # STEP 3: ACC Lap 3 Completed (Personal Best!)
        print("\n>>> Scenario 3: ACC - Lap 3 completed (NEW PERSONAL BEST: 1:49.110, P1)")
        await asyncio.sleep(6.0)
        lap3_event = acc_adapter.process_telemetry_state({
            "status": 2,
            "completed_laps": 3,
            "last_time_ms": 109110,  # 1:49.110
            "best_time_ms": 109110,
            "position": 1,
        })
        if lap3_event:
            await event_bus.publish(lap3_event)

        # STEP 4: Minecraft Advancement
        print("\n>>> Scenario 4: Minecraft - Player unlocks milestone achievement")
        await asyncio.sleep(6.0)
        mc_line1 = "[16:45:00] [Render thread/INFO]: [CHAT] Steve has made the advancement [Diamonds!]"
        mc_evt1 = mc_adapter.parse_log_line(mc_line1)
        if mc_evt1:
            await event_bus.publish(mc_evt1)

        # STEP 5: Minecraft Player Death (Critical Event)
        print("\n>>> Scenario 5: Minecraft - Player dies in combat (Creeper explosion)")
        await asyncio.sleep(6.0)
        mc_line2 = "[16:45:25] [Render thread/INFO]: [CHAT] Steve was blown up by Creeper"
        mc_evt2 = mc_adapter.parse_log_line(mc_line2)
        if mc_evt2:
            await event_bus.publish(mc_evt2)

        # STEP 6: Minecraft Victory Challenge
        print("\n>>> Scenario 6: Minecraft - Player defeats Ender Dragon")
        await asyncio.sleep(6.0)
        mc_line3 = "[16:45:50] [Render thread/INFO]: [CHAT] Steve has completed the challenge [Free the End]"
        mc_evt3 = mc_adapter.parse_log_line(mc_line3)
        if mc_evt3:
            await event_bus.publish(mc_evt3)

        print("\n" + "=" * 65)
        print("[*] Simulation scenarios completed successfully!")
        print("[*] Keeping HUD active for 8 seconds. Press Ctrl+C to exit.")
        print("=" * 65)
        await asyncio.sleep(8.0)

    finally:
        if overlay:
            overlay.close()


def main():
    parser = argparse.ArgumentParser(description="Raphael AI Gaming Copilot Simulator")
    parser.add_argument("--no-overlay", action="store_true", help="Run without Tkinter visual overlay")
    parser.add_argument("--no-voice", action="store_true", help="Run without SAPI audio speech")
    args = parser.parse_args()

    asyncio.run(run_simulation(
        enable_overlay=not args.no_overlay,
        enable_voice=not args.no_voice
    ))


if __name__ == "__main__":
    main()
