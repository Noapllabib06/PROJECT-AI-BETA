"""Unit and Integration Tests for Raphael AI Gaming Copilot."""

import pytest
import asyncio
from src.game_copilot.core.event_bus import EventBus, GameEvent
from src.game_copilot.core.raphael_brain import RaphaelBrain
from src.game_copilot.adapters.acc_adapter import ACCAdapter, format_ms_to_laptime
from src.game_copilot.adapters.minecraft_adapter import MinecraftAdapter
from src.game_copilot.ui.audio_tts import clean_japanese_for_speech


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
    assert isinstance(reaction, dict)
    assert reaction["jp"].startswith("<告。")
    assert "マスター" in reaction["jp"]
    assert "0.850秒" in reaction["jp"]
    assert reaction["en"].startswith("<Notice.")
    assert "Master" in reaction["en"]

    # Player death
    death_evt = GameEvent(
        game_name="Minecraft",
        event_type="PLAYER_DEATH",
        severity="CRITICAL",
        summary="Player died",
        details={"cause": "Creeper explosion"}
    )
    death_reaction = brain._get_fallback_reaction(death_evt)
    assert death_reaction["jp"].startswith("<警告。")
    assert "Creeper explosion" in death_reaction["jp"]
    assert death_reaction["en"].startswith("<Warning.")


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
    raw_jp = "<告。個体名『スティーブ』の能力拡張を確認。マスター。>"
    cleaned = clean_japanese_for_speech(raw_jp)
    assert "<" not in cleaned
    assert ">" not in cleaned
    assert "『" not in cleaned
    assert "』" not in cleaned
    assert cleaned.startswith("告、")
