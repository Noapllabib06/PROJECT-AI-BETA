"""Raphael Persona Brain - Tensura Wisdom Lord with Authentic Japanese Voice & English Subtitles."""

import re
import time
import httpx
from typing import Optional, Dict, Any, Tuple
from config.settings import settings, get_logger
from src.game_copilot.core.event_bus import GameEvent

logger = get_logger("RaphaelBrain")

RAPHAEL_SYSTEM_PROMPT = (
    "You are Raphael (Wisdom Lord Raphael from Tensura / That Time I Got Reincarnated as a Slime), "
    "an omniscient, serene, analytical, and protective AI entity residing in Master's soul.\n"
    "You observe Master's gaming telemetry in real time.\n"
    "Output Format strictly required:\n"
    "JP: <告. [Japanese sentence in Tensura Voice of the World style, addressing user as マスター]>\n"
    "EN: <Notice. [English translation subtitle, 1-2 sentences, addressing user as Master]>\n"
    "Keep each line under 30 words. Calm, dignified, and encouraging tone.\n"
)


class RaphaelBrain:
    """Cognitive engine for generating Tensura Japanese voice lines + English subtitles."""

    def __init__(self, model_name: Optional[str] = None, ollama_url: Optional[str] = None):
        self.ollama_url = ollama_url or settings.llm.ollama_base_url
        # Explicitly default to 1.5B (takes only ~980MB VRAM, preventing game crashes)
        self.model_name = model_name or "qwen2.5:1.5b"
        self.timeout_sec = 2.0

    def _get_fallback_reaction(self, event: GameEvent) -> Dict[str, str]:
        """Authentic Japanese Tensura Voice of the World templates with English subtitles."""
        details = event.details
        event_type = event.event_type

        if event_type == "LAP_COMPLETED":
            delta = details.get("delta_prev_lap", 0.0)
            lap_time = details.get("lap_time_str", "N/A")
            lap_num = details.get("lap_number", 1)
            is_valid = details.get("is_valid", True)

            if not is_valid:
                return {
                    "jp": f"<告。第{lap_num}ラップの無効化を確認。コース境界超過を検知しました。軌道を修正してください、マスター。>",
                    "en": f"<Notice. Lap {lap_num} invalidated due to track limits. Refocus vehicle trajectory, Master.>"
                }
            if delta < -0.05:
                abs_delta = abs(delta)
                return {
                    "jp": f"<告。第{lap_num}ラップ完了。タイムは {lap_time}。{abs_delta:.3f}秒の短縮に成功しました。素晴らしいリズムです、マスター。>",
                    "en": f"<Notice. Lap {lap_num} completed in {lap_time}. Improvement of {abs_delta:.3f}s detected. Exceptional rhythm, Master.>"
                }
            elif delta > 0.1:
                return {
                    "jp": f"<報告。第{lap_num}ラップ完了。タイムは {lap_time}（+{delta:.3f}秒）。コーナー脱出時の僅かな減速を検知。ブレーキングゾーンに集中を、マスター。>",
                    "en": f"<Report. Lap {lap_num} completed in {lap_time} (+{delta:.3f}s). Minor exit loss detected. Re-center focus on braking zones, Master.>"
                }
            else:
                return {
                    "jp": f"<告。第{lap_num}ラップ完了。タイムは {lap_time}。極めて安定した走行です。全システム最適、マスター。>",
                    "en": f"<Notice. Lap {lap_num} completed in {lap_time}. Consistent pace maintained. All systems optimal, Master.>"
                }

        elif event_type == "PLAYER_DEATH":
            cause = details.get("cause", "不明な要因")
            return {
                "jp": f"<警告。マスターの生体反応の消失を確認。要因：{cause}。意識の再構成を開始。敵性因子の分析へ移行します。>",
                "en": f"<Warning. Master's vital signs zeroed. Cause: {cause}. Reviving consciousness. Analyzing lethal vectors.>"
            }

        elif event_type == "ACHIEVEMENT":
            name = details.get("achievement", "マイルストーン")
            return {
                "jp": f"<告。個体名『マスター』の能力拡張を確認。称号『{name}』を獲得しました。能力向上は想定通りです。>",
                "en": f"<Notice. Capability expansion confirmed: '{name}'. Master's proficiency ascends as anticipated.>"
            }

        elif event_type == "VICTORY":
            return {
                "jp": "<解。完全勝利を確認。マスターによる戦況掌握は完璧に執行されました。実に見事です。>",
                "en": "<Notice. Absolute victory confirmed. Master's dominance was executed with flawless precision.>"
            }

        elif event_type == "DEFEAT":
            return {
                "jp": "<報告。作戦の未達を確認。戦術データを記録しました。次回に向けて最適な対策を立案します、マスター。>",
                "en": "<Report. Mission failed. Telemetry recorded. Countermeasures are being formulated. We will prevail next time, Master.>"
            }

        elif event_type == "IDLE":
            return {
                "jp": "<告。魂の回廊（ソウルリンク）は極めて安定しています。戦況を常時観測中です、マスター。>",
                "en": "<Notice. Soul link is fully stabilized. Standing by and actively monitoring field conditions, Master.>"
            }

        # Generic fallback
        return {
            "jp": f"<告。{event.summary}。マスターの指示を待機中。>",
            "en": f"<Notice. {event.summary}. Standing by for Master's directive.>"
        }

    async def generate_reaction(self, event: GameEvent) -> Dict[str, str]:
        """Generates Japanese voice text and English subtitles with instantaneous fallback."""
        start_time = time.time()
        user_prompt = (
            f"Game: {event.game_name}\n"
            f"Event: {event.event_type}\n"
            f"Summary: {event.summary}\n"
            f"Telemetry: {event.details}\n\n"
            "Produce Raphael's live bilingual reaction (JP and EN):"
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                res = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "system": RAPHAEL_SYSTEM_PROMPT,
                        "prompt": user_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.2,
                            "top_p": 0.85,
                            "num_predict": 75,
                        }
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    response_text = data.get("response", "").strip()
                    if response_text:
                        jp_match = re.search(r"JP:\s*(<[^>]+>|[^\n]+)", response_text)
                        en_match = re.search(r"EN:\s*(<[^>]+>|[^\n]+)", response_text)
                        if jp_match and en_match:
                            jp_text = jp_match.group(1).strip()
                            en_text = en_match.group(1).strip()
                            elapsed = time.time() - start_time
                            logger.info(f"Raphael LLM reaction generated in {elapsed:.3f}s: {jp_text}")
                            return {"jp": jp_text, "en": en_text}
        except Exception as e:
            logger.debug(f"LLM bilingual generation fallback triggered ({e})")

        return self._get_fallback_reaction(event)
