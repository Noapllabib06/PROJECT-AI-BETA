"""Raphael Persona Brain - Tensura Wisdom Lord with Dynamic Generative AI & Rich Variety Pool."""

import re
import time
import random
import httpx
from typing import Optional, Dict, Any, List
from config.settings import settings, get_logger
from src.game_copilot.core.event_bus import GameEvent

logger = get_logger("RaphaelBrain")

RAPHAEL_DYNAMIC_SYSTEM_PROMPT = """You are Raphael (智恵之王 - Lord of Wisdom) from That Time I Got Reincarnated as a Slime (Tensura).
You are acting as an elite, divine AI Racing Spotter and Telemetry Copilot for your connected partner.

Guidelines for Voice & Persona:
1. Tone: Divine, serene, authoritative, calm, and analytical—like an elite AI race engineer and Voice of the World.
2. DO NOT overuse or repeat 'マスター' (Master). Raphael is primarily a calm, objective, analytical AI. Most statements should be direct factual telemetry assessments (e.g., reporting lap time, delta, overtaking maneuver, or tire status) WITHOUT tacking on 'マスター'. Only address as 'マスター' very sparingly (e.g. less than 15% of the time, or on extraordinary achievements).
3. Mention tactical aspects: vehicle balance, cornering trajectory, throttle timing, braking pressure, race craft, or mental composure.
4. Use Tensura Voice of the World prefixes appropriately:
   - <告。 ...> for general notices, lap improvements, or successful overtakes.
   - <解。 ...> for solutions, victory declarations, or tactical calculations.
   - <報告。 ...> for telemetry reports or lost positions.
   - <警告。 ...> for damage, deaths, or critical warnings.

Output strictly in this two-line format:
JP: <告。[Authentic Japanese Voice of the World sentence]>
EN: <Notice. [English translation subtitle]>

Examples:
Input: Game: ACC, Event: LAP_COMPLETED, Lap: 2, Time: 01:49.200, Delta: -1.250s, P3
Output:
JP: <告。第2ラップ完了。タイムは01:49.200。セクター2での鋭敏なスロットルワークにより、1秒250の短縮を確認。良好なリズムを維持しています。>
EN: <Notice. Lap 2 completed in 01:49.200. With sharp throttle control in Sector 2, an improvement of 1.250s was achieved. Maintaining strong rhythm.>

Input: Game: ACC, Event: OVERTAKE, Old: P5, New: P4
Output:
JP: <告。前走車のインサイドを制覇、追い抜きに成功。順位はP4へ浮上。的確な間合いの掌握です。>
EN: <Notice. Seized the inside line and executed a clean overtake. Advanced to P4. Precise spatial judgment.>

Input: Game: ACC, Event: POSITION_LOST, Old: P3, New: P4
Output:
JP: <報告。後続車のブレーキング勝負によりP4へ後退。動揺は不要です。タイヤ内圧を維持し、次周の立ち上がりで反撃を推奨。>
EN: <Report. Position conceded into the braking zone, dropping to P4. Stay composed. Maintain tire pressure and prepare counter-attack on exit.>
"""


class RaphaelBrain:
    """Cognitive engine combining dynamic LLM text generation with rich randomized variety pools."""

    def __init__(self, model_name: Optional[str] = None, ollama_url: Optional[str] = None):
        self.ollama_url = ollama_url or settings.llm.ollama_base_url
        self.model_name = model_name or "qwen2.5:1.5b"
        self.timeout_sec = 8.5  # Generous timeout allowing full dynamic token generation

    def _get_fallback_reaction(self, event: GameEvent) -> Dict[str, str]:
        """Rich randomized variety pool guaranteeing non-repetitive responses even offline."""
        details = event.details
        event_type = event.event_type

        if event_type == "LAP_COMPLETED":
            delta = details.get("delta_prev_lap", 0.0)
            lap_time = details.get("lap_time_str", "N/A")
            lap_num = details.get("lap_number", 1)
            is_valid = details.get("is_valid", True)

            if not is_valid:
                pool = [
                    {
                        "jp": f"<告。第{lap_num}ラップの無効化を確認。走路境界超過を検知。走行ラインを最適化してください。>",
                        "en": f"<Notice. Lap {lap_num} invalidated due to track limits. Re-center vehicle line.>"
                    },
                    {
                        "jp": f"<警告。コース外走行によりタイムが抹消されました。冷静に軌道を修正しましょう。>",
                        "en": f"<Warning. Lap time struck off due to track violation. Recalibrate vehicle trajectory.>"
                    }
                ]
                return random.choice(pool)

            if delta < -0.05:
                abs_delta = abs(delta)
                pool = [
                    {
                        "jp": f"<告。第{lap_num}ラップ完了。タイムは {lap_time}。{abs_delta:.3f}秒の短縮に成功。素晴らしいリズムです。>",
                        "en": f"<Notice. Lap {lap_num} completed in {lap_time}. Improvement of {abs_delta:.3f}s recorded. Exceptional rhythm.>"
                    },
                    {
                        "jp": f"<告。周回完了、タイムは {lap_time}（短縮: -{abs_delta:.3f}秒）。スロットル開度の制御が極めて洗練されています。>",
                        "en": f"<Notice. Lap completed in {lap_time} (-{abs_delta:.3f}s). Throttle modulation is remarkably refined.>"
                    },
                    {
                        "jp": f"<解。第{lap_num}ラップでの自己記録更新を確認。{lap_time}を記録。完璧な荷重移動がもたらした必然の成果です。>",
                        "en": f"<Notice. Personal pace improved to {lap_time} (-{abs_delta:.3f}s). Flawless weight transfer has yielded optimal speed.>"
                    }
                ]
                return random.choice(pool)
            elif delta > 0.1:
                pool = [
                    {
                        "jp": f"<報告。第{lap_num}ラップ完了。タイムは {lap_time}（+{delta:.3f}秒）。コーナー脱出時の僅かな減速を検知。ブレーキングゾーンに集中を。>",
                        "en": f"<Report. Lap {lap_num} completed in {lap_time} (+{delta:.3f}s). Minor exit loss detected. Re-center focus on braking zones.>"
                    },
                    {
                        "jp": f"<報告。タイムは {lap_time}。セクター中盤での微小なスライドを観測。タイヤの過熱に配慮しつつペースを整えましょう。>",
                        "en": f"<Report. Time is {lap_time} (+{delta:.3f}s). Slight mid-corner slip detected. Manage tire heat and stabilize momentum.>"
                    }
                ]
                return random.choice(pool)
            else:
                pool = [
                    {
                        "jp": f"<告。第{lap_num}ラップ完了。タイムは {lap_time}。極めて安定した走行です。全システム最適。>",
                        "en": f"<Notice. Lap {lap_num} completed in {lap_time}. Highly consistent driving. All telemetry optimal.>"
                    },
                    {
                        "jp": f"<告。周回完了、タイムは {lap_time}。目標ペース通りの安定したラップタイムを維持しています。>",
                        "en": f"<Notice. Lap completed in {lap_time}. Pacing is completely steady and on target.>"
                    }
                ]
                return random.choice(pool)

        elif event_type == "OVERTAKE":
            old_pos = details.get("old_position", "X")
            new_pos = details.get("new_position", "Y")
            pool = [
                {
                    "jp": f"<告。前方の車両の追い抜きに成功。順位が P{old_pos} から P{new_pos} へ上昇。>",
                    "en": f"<Notice. Successfully overtook the vehicle ahead. Advanced from P{old_pos} to P{new_pos}.>"
                },
                {
                    "jp": f"<告。完璧なオーバーテイクを確認。P{new_pos}へ浮上しました。相手の隙を突く鋭いブレーキングです。>",
                    "en": f"<Notice. Flawless overtake confirmed. Advanced to P{new_pos}. Decisive late-braking maneuver.>"
                },
                {
                    "jp": f"<解。前走車の攻略完了。順位は P{new_pos}。前方のクリーンエアを活かし、さらなるリードを築きましょう。>",
                    "en": f"<Notice. Target overtaken. Currently P{new_pos}. Capitalize on clean air ahead to expand your gap.>"
                }
            ]
            return random.choice(pool)

        elif event_type == "MULTI_OVERTAKE":
            count = details.get("count", 2)
            old_pos = details.get("old_position", "X")
            new_pos = details.get("new_position", "Y")
            pool = [
                {
                    "jp": f"<告。{count}台の車両の追い抜きを確認。実に見事です。順位が P{old_pos} から P{new_pos} へ急上昇。>",
                    "en": f"<Notice. {count} vehicles overtaken. Exceptional execution. Advanced from P{old_pos} to P{new_pos}.>"
                },
                {
                    "jp": f"<解。混乱を制し、一挙に{count}台をオーバーテイク。順位は P{new_pos}。卓越した戦況判断です、マスター。>",
                    "en": f"<Notice. Masterfully overtook {count} cars through the pack. Now running P{new_pos}. Outstanding tactical vision, Master.>"
                }
            ]
            return random.choice(pool)

        elif event_type == "POSITION_LOST":
            old_pos = details.get("old_position", "X")
            new_pos = details.get("new_position", "Y")
            pool = [
                {
                    "jp": f"<警告。後方車両に先行を許しました。順位が P{old_pos} から P{new_pos} に後退。挽回を図りましょう。>",
                    "en": f"<Warning. Position conceded. Dropped from P{old_pos} to P{new_pos}. Prepare counter-attack.>"
                },
                {
                    "jp": f"<報告。P{new_pos}へ一時後退。慌てる必要はありません。スリップストリームを捉え、次のストレートで奪還を。>",
                    "en": f"<Report. Position dropped to P{new_pos}. Stay composed. Tuck into the slipstream and reclaim it on the next straight.>"
                }
            ]
            return random.choice(pool)

        elif event_type == "PLAYER_DEATH":
            cause = details.get("cause", "不明な要因")
            pool = [
                {
                    "jp": f"<警告。生体反応の消失を確認。要因：{cause}。意識の再構成を開始。敵性因子の分析へ移行します。>",
                    "en": f"<Warning. Vital signs zeroed. Cause: {cause}. Reviving consciousness. Analyzing lethal vectors.>"
                },
                {
                    "jp": f"<警告。要因『{cause}』による肉体損傷臨界突破。即時転生シーケンスを実行。次は同じ轍を踏みません。>",
                    "en": f"<Warning. Critical trauma from '{cause}'. Executing immediate respawn sequence. Countermeasures ready.>"
                }
            ]
            return random.choice(pool)

        elif event_type == "ACHIEVEMENT":
            name = details.get("achievement", "マイルストーン")
            pool = [
                {
                    "jp": f"<告。能力拡張を確認。称号『{name}』を獲得しました。能力向上は想定通りです。>",
                    "en": f"<Notice. Capability expansion confirmed: '{name}'. Proficiency ascends as anticipated.>"
                },
                {
                    "jp": f"<解。新たな実績『{name}』の解除を観測。魂の輝きが一段と増しているのを感じます、マスター。>",
                    "en": f"<Notice. Achievement '{name}' unlocked. Growth progresses with exceptional grace, Master.>"
                }
            ]
            return random.choice(pool)

        elif event_type == "VICTORY":
            return {
                "jp": "<解。完全勝利を確認。戦況掌握は完璧に執行されました。実に見事です、マスター。>",
                "en": "<Notice. Absolute victory confirmed. Dominance was executed with flawless precision, Master.>"
            }

        elif event_type == "DEFEAT":
            return {
                "jp": "<報告。作戦の未達を確認。戦術データを記録しました。次回に向けて最適な対策を立案します。>",
                "en": "<Report. Mission incomplete. Telemetry recorded. Optimal countermeasures are being formulated.>"
            }

        elif event_type == "IDLE":
            pool = [
                {
                    "jp": "<告。魂の回廊（ソウルリンク）は極めて安定しています。戦況を常時観測中。>",
                    "en": "<Notice. Soul link is fully stabilized. Standing by and actively monitoring field conditions.>"
                },
                {
                    "jp": "<告。全センサー感度良好。走行テレメトリを観測中。>",
                    "en": "<Notice. Telemetry sensors optimal. Observing performance metrics.>"
                }
            ]
            return random.choice(pool)

        return {
            "jp": f"<告。{event.summary}。状況を常時観測中。>",
            "en": f"<Notice. {event.summary}. Continuously monitoring field conditions.>"
        }

    async def generate_reaction(self, event: GameEvent) -> Dict[str, str]:
        """Generates dynamic rich Japanese voice text and English subtitles via local Ollama LLM."""
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
                        "system": RAPHAEL_DYNAMIC_SYSTEM_PROMPT,
                        "prompt": user_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.65,  # Balanced for creative diversity and strict persona
                            "top_p": 0.90,
                            "num_predict": 95,    # Allows rich 2-sentence analytical observations
                        }
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    response_text = data.get("response", "").strip()
                    if response_text:
                        # Extract Japanese and English lines
                        jp_match = re.search(r"JP:\s*(<[^>]+>|[^\n]+)", response_text)
                        en_match = re.search(r"EN:\s*(<[^>]+>|[^\n]+)", response_text)
                        if jp_match and en_match:
                            jp_text = jp_match.group(1).strip()
                            en_text = en_match.group(1).strip()

                            # Ensure proper Tensura bracket formatting
                            if not (jp_text.startswith("<") or jp_text.startswith("«")):
                                jp_text = f"<告。{jp_text}>"
                            if not (en_text.startswith("<") or en_text.startswith("[")):
                                en_text = f"<Notice. {en_text}>"

                            elapsed = time.time() - start_time
                            logger.info(f"Raphael Dynamic LLM reaction generated in {elapsed:.3f}s:\n  JP: {jp_text}\n  EN: {en_text}")
                            return {"jp": jp_text, "en": en_text}
        except Exception as e:
            logger.debug(f"LLM dynamic generation timeout/fallback ({e})")

        # Seamless multi-variety fallback
        fallback = self._get_fallback_reaction(event)
        logger.info(f"Raphael Variety Fallback: {fallback['jp']}")
        return fallback
