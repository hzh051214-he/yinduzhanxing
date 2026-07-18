"""真爱画像 API 路由。"""
import uuid
import json
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, validator

from app.core.config import get_settings
from app.services.geocoding import get_city_coords

router = APIRouter(prefix="/portrait", tags=["portrait"])
settings = get_settings()


class PortraitRequest(BaseModel):
    birth_date: str          = Field(..., example="2005-12-14", description="YYYY-MM-DD")
    birth_time: str          = Field(..., example="10:28",      description="HH:MM")
    place:      str          = Field(..., example="上海")
    lat:        Optional[float] = Field(None, description="纬度（提供时跳过城市查找）")
    lon:        Optional[float] = Field(None, description="经度（提供时跳过城市查找）")
    tz_str:     Optional[str]   = Field(None)
    gender:     Literal["男", "女", "M", "F"] = Field("男")
    name:       str             = Field("", description="当事人姓名")
    time_precision_level: int   = Field(2, ge=1, le=4)
    d60_consent: Optional[bool] = Field(None)

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


class PortraitResponse(BaseModel):
    portrait_id: str
    status: str
    estimated_seconds: int
    message: str


class PortraitStatusResponse(BaseModel):
    portrait_id: str
    status: str
    progress: int
    error_msg: Optional[str] = None
    portrait_text: Optional[str] = None
    image_prompt:  Optional[str] = None
    image_url:     Optional[str] = None


@router.post("", response_model=PortraitResponse)
async def create_portrait(req: PortraitRequest):
    """提交真爱画像请求，立即返回 portrait_id。"""
    year, month, day = map(int, req.birth_date.split("-"))
    hour, minute     = map(int, req.birth_time.split(":"))

    lat, lon, tz_str = req.lat, req.lon, req.tz_str
    if lat is None or lon is None:
        coords = get_city_coords(req.place)
        if coords is None:
            raise HTTPException(
                status_code=422,
                detail=f"找不到城市坐标：'{req.place}'。请提供 lat/lon 参数。"
            )
        lat, lon, auto_tz = coords
        if tz_str is None:
            tz_str = auto_tz

    if tz_str is None:
        tz_str = "Asia/Shanghai"

    portrait_id = str(uuid.uuid4())

    from app.tasks.portrait_tasks import run_portrait
    run_portrait.apply_async(args=[{
        "portrait_id":         portrait_id,
        "year": year, "month": month, "day": day,
        "hour": hour, "minute": minute,
        "lat": lat, "lon": lon, "tz_str": tz_str,
        "gender":              req.gender,
        "name":                req.name,
        "time_precision_level": req.time_precision_level,
        "d60_consent":         req.d60_consent,
    }], task_id=portrait_id)

    return PortraitResponse(
        portrait_id=portrait_id,
        status="pending",
        estimated_seconds=60,
        message="正在计算星盘并生成画像，约需 60 秒。",
    )


@router.get("/{portrait_id}/status", response_model=PortraitStatusResponse)
async def get_portrait_status(portrait_id: str):
    """轮询真爱画像状态。"""
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.redis_url)
    try:
        data = await r.hgetall(f"portrait:{portrait_id}")
    finally:
        await r.aclose()

    if not data:
        raise HTTPException(status_code=404, detail="portrait_id 不存在或已过期")

    result_raw = data.get(b"result", b"").decode()
    result = json.loads(result_raw) if result_raw else {}

    return PortraitStatusResponse(
        portrait_id=portrait_id,
        status=data.get(b"status", b"unknown").decode(),
        progress=int(data.get(b"progress", b"0")),
        error_msg=data.get(b"error_msg", b"").decode() or None,
        portrait_text=result.get("portrait_text"),
        image_prompt=result.get("image_prompt"),
        image_url=result.get("image_url"),
    )


@router.websocket("/{portrait_id}/ws")
async def portrait_progress_ws(websocket: WebSocket, portrait_id: str):
    """WebSocket 实时进度推送。"""
    import redis.asyncio as aioredis
    await websocket.accept()

    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"portrait:{portrait_id}:progress")

    try:
        current = await r.hgetall(f"portrait:{portrait_id}")
        if current:
            status   = current.get(b"status", b"pending").decode()
            progress = int(current.get(b"progress", b"0"))
            await websocket.send_json({"status": status, "progress": progress})
            if status in ("done", "failed"):
                # 已完成，直接推送完整结果
                result_raw = current.get(b"result", b"").decode()
                result = json.loads(result_raw) if result_raw else {}
                await websocket.send_json({
                    "status": status, "progress": progress, **result
                })
                return

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
