"""Unit and Integration Tests for Raphael AI Gaming Copilot."""

import pytest
import asyncio
from src.game_copilot.core.event_bus import EventBus, GameEvent
from src.game_copilot.core.raphael_brain import RaphaelBrain
from src.game_copilot.adapters.acc_adapter import ACCAdapter, format_ms_to_laptime
from src.game_copilot.adapters.minecraft_adapter import MinecraftAdapter
from src.game_copilot.ui.audio_tts import clean_text_for_speech


def test_event_bus_subscription_and_throttling():
    async def _test_body():
        bus = EventBus()
        received_events = []

        async def sample_subscriber(evt: GameEvent):
            received_events.append(evt)

        bus.subscribe(sample_subscriber)

        # First event should pass
        evt1 = GameEvent(
            game_name="ACC",
            event_type="LAP_COMPLETED",
            severity="INFO",
            summary="Lap 1 done"
        )
        await bus.publish(evt1)
        assert len(received_events) == 1

        # Immediate second LAP_COMPLETED event within 8s cooldown should be throttled
        evt2 = GameEvent(
            game_name="ACC",
            event_type="LAP_COMPLETED",
            severity="INFO",
            summary="Lap 2 done too fast"
        )
        await bus.publish(evt2)
        assert len(received_events) == 1  # Throttled!

        # CRITICAL event should bypass cooldown
        evt3 = GameEvent(
            game_name="ACC",
            event_type="LAP_COMPLETED",
            severity="CRITICAL",
            summary="Critical Lap event"
        )
        await bus.publish(evt3)
        assert len(received_events) == 2

    asyncio.run(_test_body())


def test_raphael_brain_instant_templates():
    brain = RaphaelBrain()

    # Lap improvement
    lap_evt = GameEvent(
        game_name="Assetto Corsa Competizione",
        event_type="LAP_COMPLETED",
        severity="INFO",
        summary="Lap 2 finished",
        details={
            "lap_number": 2,
            "lap_time_str": "01:48.320",
            "delta_prev_lap": -0.850,
            "is_valid": True
        }
    )
    reaction = brain._get_fallback_reaction(lap_evt)
    assert reaction.startswith("<Notice.")
    assert "Master" in reaction
    assert "0.850s" in reaction

    # Player death
    death_evt = GameEvent(
        game_name="Minecraft",
        event_type="PLAYER_DEATH",
        severity="CRITICAL",
        summary="Player died",
        details={"cause": "Creeper explosion"}
    )
    death_reaction = brain._get_fallback_reaction(death_evt)
    assert death_reaction.startswith("<Warning.")
    assert "Creeper explosion" in death_reaction


def test_acc_lap_formatting_and_telemetry():
    # Test formatting
    assert format_ms_to_laptime(110820) == "01:50.820"
    assert format_ms_to_laptime(60000) == "01:00.000"

    adapter = ACCAdapter()

    # Lap 1: Baseline
    evt1 = adapter.process_telemetry_state({
        "status": 2,
        "completed_laps": 1,
        "last_time_ms": 112000,
        "best_time_ms": 112000,
        "position": 4,
    })
    assert evt1 is not None
    assert evt1.details["lap_number"] == 1
    assert evt1.details["is_personal_best"] is True

    # Lap 2: Faster by 2.0s
    evt2 = adapter.process_telemetry_state({
        "status": 2,
        "completed_laps": 2,
        "last_time_ms": 110000,
        "best_time_ms": 110000,
        "position": 2,
    })
    assert evt2 is not None
    assert evt2.details["lap_number"] == 2
    assert evt2.details["delta_prev_lap"] == -2.0
    assert evt2.details["is_personal_best"] is True


def test_minecraft_log_parsing():
    adapter = MinecraftAdapter()

    # 1. Death line
    death_line = "[12:00:00] [Render thread/INFO]: [CHAT] Alex was blown up by Creeper"
    evt_death = adapter.parse_log_line(death_line)
    assert evt_death is not None
    assert evt_death.event_type == "PLAYER_DEATH"
    assert evt_death.severity == "CRITICAL"
    assert evt_death.details["cause"] == "Creeper"

    # 2. Advancement line
    adv_line = "[12:05:00] [Render thread/INFO]: [CHAT] Alex has made the advancement [Diamonds!]"
    evt_adv = adapter.parse_log_line(adv_line)
    assert evt_adv is not None
    assert evt_adv.event_type == "ACHIEVEMENT"
    assert evt_adv.details["achievement"] == "Diamonds!"

    # 3. Challenge / Victory line
    chal_line = "[12:10:00] [Render thread/INFO]: [CHAT] Alex has completed the challenge [Free the End]"
    evt_chal = adapter.parse_log_line(chal_line)
    assert evt_chal is not None
    assert evt_chal.event_type == "VICTORY"
    assert evt_chal.severity == "CELEBRATION"


def test_audio_tts_text_cleaner():
    raw = "<Notice. Lap 2 completed in 1:47.320 (+0.450s). Well done, Master.>"
    cleaned = clean_text_for_speech(raw)
    assert "<" not in cleaned
    assert ">" not in cleaned
    assert "1 minute 47 point 320 seconds" in cleaned
    assert "plus 0.450 seconds" in cleaned
