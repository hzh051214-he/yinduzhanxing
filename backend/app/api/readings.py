"""排盘 API 路由。"""
import uuid
import json
import os
from pathlib import Path
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, validator
import redis as redis_lib

from app.core.config import get_settings
from app.services.geocoding import search_city, get_city_coords
from app.tasks.reading_tasks import run_reading

router = APIRouter(prefix="/readings", tags=["readings"])
settings = get_settings()


# ── 请求/响应模型 ─────────────────────────────────────────────────────────

class ReadingRequest(BaseModel):
    # 出生信息
    birth_date:  str          = Field(..., example="2005-12-14", description="YYYY-MM-DD")
    birth_time:  str          = Field(..., example="10:28",      description="HH:MM")
    place:       str          = Field(..., example="上海",       description="城市名")
    lat:         Optional[float] = Field(None, description="纬度（提供时跳过城市查找）")
    lon:         Optional[float] = Field(None, description="经度（提供时跳过城市查找）")
    tz_str:      Optional[str]   = Field(None, description="时区（不提供时自动推断）")

    gender:      Literal["男", "女", "M", "F"] = Field("男")
    relationship: str = Field("单身", example="单身")
    name:        str  = Field("",    description="当事人姓名（用于报告封面）")
    lang:        Literal["cn", "en"] = Field("cn")

    # 时间精度（1-4）
    time_precision_level: int = Field(2, ge=1, le=4,
        description="1=出生证明精确, 2=±5分钟, 3=±15分钟, 4=不确定")

    # D60 知情同意
    d60_consent: Optional[bool] = Field(None, description="是否同意查看 D60 业力盘")

    # 报告模块（Phase 1 仅 core 可用）
    modules: str = Field("core", description="逗号分隔: core（Phase 1 仅支持 core）")

    @validator("birth_date")
    def validate_date(cls, v):
        from datetime import datetime
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("birth_date 格式必须为 YYYY-MM-DD")
        return v

    @validator("birth_time")
    def validate_time(cls, v):
        from datetime import datetime
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError:
            raise ValueError("birth_time 格式必须为 HH:MM")
        return v


class ReadingResponse(BaseModel):
    reading_id: str
    status: str
    estimated_seconds: int
    message: str


class StatusResponse(BaseModel):
    reading_id: str
    status: str
    progress: int
    error_msg: Optional[str] = None
    report_id: Optional[str] = None


# ── API 端点 ──────────────────────────────────────────────────────────────

@router.post("", response_model=ReadingResponse)
async def create_reading(req: ReadingRequest):
    """提交排盘请求，立即返回 job ID。实际计算在后台 Celery worker 中异步执行。"""

    # 解析出生日期时间
    year, month, day = map(int, req.birth_date.split("-"))
    hour, minute     = map(int, req.birth_time.split(":"))

    # 坐标解析
    lat, lon, tz_str = req.lat, req.lon, req.tz_str
    if lat is None or lon is None:
        coords = get_city_coords(req.place)
        if coords is None:
            raise HTTPException(
                status_code=422,
                detail=f"找不到城市坐标：'{req.place}'。请提供 lat/lon 参数，或使用更精确的城市名。"
            )
        lat, lon, auto_tz = coords
        if tz_str is None:
            tz_str = auto_tz

    if tz_str is None:
        tz_str = "Asia/Shanghai"

    reading_id = str(uuid.uuid4())
    output_dir = str(Path(settings.reports_storage_path) / reading_id)

    # 提交 Celery 任务
    task_params = {
        "reading_id":          reading_id,
        "year": year, "month": month, "day": day,
        "hour": hour, "minute": minute,
        "lat": lat, "lon": lon, "tz_str": tz_str,
        "place_name":          req.place,
        "gender":              req.gender,
        "relationship":        req.relationship,
        "name":                req.name,
        "lang":                req.lang,
        "time_precision_level": req.time_precision_level,
        "d60_consent":         req.d60_consent,
        "modules":             req.modules,
        "output_dir":          output_dir,
    }
    run_reading.apply_async(args=[task_params], task_id=reading_id)

    return ReadingResponse(
        reading_id=reading_id,
        status="pending",
        estimated_seconds=90,
        message="排盘计算已开始，请通过 WebSocket 或轮询查看进度。",
    )


@router.get("/{reading_id}/status", response_model=StatusResponse)
async def get_reading_status(reading_id: str):
    """轮询排盘状态（WebSocket 不可用时的备选方案）。"""
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.redis_url)
    try:
        data = await r.hgetall(f"reading:{reading_id}")
    finally:
        await r.aclose()

    if not data:
        raise HTTPException(status_code=404, detail="reading_id 不存在或已过期")

    return StatusResponse(
        reading_id=reading_id,
        status=data.get(b"status", b"unknown").decode(),
        progress=int(data.get(b"progress", b"0")),
        error_msg=data.get(b"error_msg", b"").decode() or None,
        report_id=data.get(b"report_id", b"").decode() or None,
    )


@router.websocket("/{reading_id}/ws")
async def reading_progress_ws(websocket: WebSocket, reading_id: str):
    """
    WebSocket 实时进度推送。
    使用 redis.asyncio 异步 Pub/Sub，不阻塞 asyncio 事件循环。
    """
    import redis.asyncio as aioredis
    await websocket.accept()

    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"reading:{reading_id}:progress")

    try:
        # 先推送当前状态（防止 ws 建立时任务已在进行）
        current = await r.hgetall(f"reading:{reading_id}")
        if current:
            status   = current.get(b"status",   b"pending").decode()
            progress = int(current.get(b"progress", b"0"))
            report_id = current.get(b"report_id", b"").decode() or None
            payload = {"status": status, "progress": progress}
            if report_id:
                payload["report_id"] = report_id
            await websocket.send_json(payload)
            # 任务已完成就不用等 pubsub 了
            if status in ("done", "failed"):
                return

        # 异步监听后续进度事件，不阻塞事件循环
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
                if data.get("status") in ("done", "failed"):
                    break
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()
        await r.aclose()
