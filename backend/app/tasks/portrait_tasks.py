"""真爱画像 Celery 任务。"""
import os
import sys
import json
import traceback
from pathlib import Path

# 主动加载 .env
_env_file = Path(__file__).parent.parent.parent / ".env"
if _env_file.exists():
    with open(_env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()

from celery.utils.log import get_task_logger
from app.tasks.reading_tasks import celery_app, _get_redis
from app.services.ai_client import call_llm
from app.services.portrait_prompts import portrait_prompt

logger = get_task_logger(__name__)


def _update_portrait_status(portrait_id: str, status: str, progress: int,
                             error_msg: str = None, result: dict = None):
    """把状态写入 Redis Pub/Sub + Hash。"""
    r = _get_redis()
    payload = {"portrait_id": portrait_id, "status": status, "progress": progress}
    if error_msg:
        payload["error_msg"] = error_msg
    if result:
        payload["result"] = json.dumps(result, ensure_ascii=False)

    r.publish(f"portrait:{portrait_id}:progress", json.dumps(payload, ensure_ascii=False))
    r.hset(f"portrait:{portrait_id}", mapping={k: str(v) for k, v in payload.items()})
    r.expire(f"portrait:{portrait_id}", 3600)


@celery_app.task(bind=True, name="tasks.run_portrait", max_retries=1)
def run_portrait(self, params: dict):
    """
    真爱画像流水线任务。

    params:
      portrait_id: str
      year/month/day/hour/minute: int
      lat/lon: float
      tz_str: str
      gender: str  — 用户自己的性别
      d60_consent: bool | None
    """
    portrait_id = params["portrait_id"]

    try:
        # ── Step 1: 天文计算 ─────────────────────────────────
        _update_portrait_status(portrait_id, "calculating", 10)
        logger.info(f"[portrait:{portrait_id}] 开始排盘计算")

        _vedic_scripts = os.environ.get("VEDIC_SCRIPTS_PATH") or str(
            Path(__file__).parent.parent.parent.parent /
            "skills" / "vedic-astrology" / "vedic-astrology-redskill" / "scripts"
        )
        if _vedic_scripts not in sys.path:
            sys.path.insert(0, _vedic_scripts)

        from engine import calculate_full_chart
        chart = calculate_full_chart(
            params["year"], params["month"], params["day"],
            params["hour"], params["minute"],
            params["lat"], params["lon"],
            tz_str=params.get("tz_str", "Asia/Shanghai"),
            d60_consent=params.get("d60_consent"),
            time_precision_level=params.get("time_precision_level", 2),
            d60_trust_level="auto",
        )
        _update_portrait_status(portrait_id, "calculating", 35)

        # ── Step 2: 提取 love_appearance_hints ───────────────
        hints = chart.get("love_appearance_hints", {})
        if not hints:
            raise ValueError("星盘数据中未找到感情外貌信息，请确认出生信息正确")

        # 补充引擎已算好但 love_appearance_hints 未携带的字段
        dk_planet = hints.get("dk_planet")
        l7_planet = hints.get("l7_planet")
        hints = dict(hints)   # 浅拷贝
        hints["dk_consistent"] = chart.get("karakas", {}).get("dk_consistent", True)
        if dk_planet and dk_planet in chart.get("planets", {}):
            hints["dk_house"] = chart["planets"][dk_planet].get("house")
        # L7 尊贵度（入旺/入庙时画像要突出这个特质）
        if l7_planet:
            hints["l7_dignity"] = chart.get("dignity", {}).get(l7_planet, {}).get("compound", "neutral")

        _update_portrait_status(portrait_id, "analyzing", 45)
        logger.info(f"[portrait:{portrait_id}] 开始生成气质描述")

        # ── Step 3: LLM 生成气质描述 + 英文 Prompt ──────────
        sys_p, usr_p = portrait_prompt(hints, gender_of_user=params.get("gender", "男"))
        portrait_text = call_llm(sys_p, usr_p, max_tokens=1500)
        logger.info(f"[portrait:{portrait_id}] 气质描述生成完成，{len(portrait_text)} 字符")

        # 从 portrait_text 里提取英文 Prompt（代码块内的内容）
        import re
        prompt_match = re.search(r"```\n(.*?)\n```", portrait_text, re.DOTALL)
        image_prompt = prompt_match.group(1).strip() if prompt_match else ""

        _update_portrait_status(portrait_id, "generating", 65)

        # ── Step 4: 调用 DALL-E 3 生成图片 ──────────────────
        image_url = None
        if image_prompt:
            try:
                from app.services.image_client import generate_portrait_image
                logger.info(f"[portrait:{portrait_id}] 开始生成图片")
                image_url = generate_portrait_image(image_prompt)
                logger.info(f"[portrait:{portrait_id}] 图片生成完成")
            except Exception as img_err:
                # 图片生成失败不影响文字结果
                logger.warning(f"[portrait:{portrait_id}] 图片生成失败（不影响文字结果）: {img_err}")

        _update_portrait_status(portrait_id, "done", 100, result={
            "portrait_text": portrait_text,
            "image_prompt":  image_prompt,
            "image_url":     image_url,
            "hints_summary": {
                "l7_sign":       hints.get("l7_sign", ""),
                "base_vibe":     hints.get("base_vibe", ""),
                "d9_venus_sign": hints.get("d9_venus_sign", ""),
                "has_overseas":  hints.get("has_overseas_hint", False),
            },
        })
        logger.info(f"[portrait:{portrait_id}] 真爱画像任务完成")

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.error(f"[portrait:{portrait_id}] 任务失败: {err_msg}\n{traceback.format_exc()}")
        _update_portrait_status(portrait_id, "failed", 0, error_msg=str(exc))
        raise
