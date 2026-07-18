"""合盘 API 路由。"""
import uuid
import json
import os
from pathlib import Path
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, validator

from app.core.config import get_settings
from app.services.geocoding import get_city_coords

router   = APIRouter(prefix="/synastry", tags=["synastry"])
settings = get_settings()


class PersonInfo(BaseModel):
    name:       str   = Field("", description="姓名")
    birth_date: str   = Field(..., example="1998-03-20")
    birth_time: str   = Field(..., example="08:00")
    place:      str   = Field(..., example="上海")
    lat:        Optional[float] = None
    lon:        Optional[float] = None
    tz_str:     Optional[str]   = None
    gender:     Literal["男", "女", "M", "F"] = "男"
    time_precision_level: int = Field(2, ge=1, le=4)

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


class SynastryRequest(BaseModel):
    p1:   PersonInfo
    p2:   PersonInfo
    lang: Literal["cn", "en"] = "cn"


class SynastryResponse(BaseModel):
    synastry_id: str
    status: str
    estimated_seconds: int
    message: str


class SynastryStatusResponse(BaseModel):
    synastry_id: str
    status: str
    progress: int
    error_msg:   Optional[str] = None
    report_id:   Optional[str] = None
    p1_name:     Optional[str] = None
    p2_name:     Optional[str] = None
    total_score: Optional[int] = None
    grade:       Optional[str] = None


def _resolve_person(p: PersonInfo) -> dict:
    """解析 PersonInfo，补全经纬度和时区。"""
    year, month, day = map(int, p.birth_date.split("-"))
    hour, minute     = map(int, p.birth_time.split(":"))

    lat, lon, tz_str = p.lat, p.lon, p.tz_str
    if lat is None or lon is None:
        coords = get_city_coords(p.place)
        if coords is None:
            raise HTTPException(
                status_code=422,
                detail=f"找不到城市坐标：'{p.place}'，请提供 lat/lon。"
            )
        lat, lon, auto_tz = coords
        if tz_str is None:
            tz_str = auto_tz

    return {
        "name": p.name, "year": year, "month": month, "day": day,
        "hour": hour, "minute": minute,
        "lat": lat, "lon": lon,
        "tz_str": tz_str or "Asia/Shanghai",
        "gender": p.gender,
        "time_precision_level": p.time_precision_level,
    }


@router.post("", response_model=SynastryResponse)
async def create_synastry(req: SynastryRequest):
    """提交合盘请求。"""
    p1 = _resolve_person(req.p1)
    p2 = _resolve_person(req.p2)

    synastry_id = str(uuid.uuid4())
    output_dir  = str(Path(settings.reports_storage_path) / f"synastry_{synastry_id}")

    from app.tasks.synastry_tasks import run_synastry
    run_synastry.apply_async(args=[{
        "synastry_id": synastry_id,
        "p1":          p1,
        "p2":          p2,
        "output_dir":  output_dir,
        "lang":        req.lang,
    }], task_id=synastry_id)

    return SynastryResponse(
        synastry_id=synastry_id,
        status="pending",
        estimated_seconds=120,
        message="合盘计算已开始，约需 1-2 分钟。",
    )


@router.get("/{synastry_id}/status", response_model=SynastryStatusResponse)
async def get_synastry_status(synastry_id: str):
    import redis.asyncio as aioredis
    r = aioredis.from_url(settings.redis_url)
    try:
        data = await r.hgetall(f"synastry:{synastry_id}")
    finally:
        await r.aclose()

    if not data:
        raise HTTPException(status_code=404, detail="synastry_id 不存在或已过期")

    result_raw = data.get(b"result", b"").decode()
    result = json.loads(result_raw) if result_raw else {}

    return SynastryStatusResponse(
        synastry_id=synastry_id,
        status=data.get(b"status", b"unknown").decode(),
        progress=int(data.get(b"progress", b"0")),
        error_msg=data.get(b"error_msg", b"").decode() or None,
        report_id=result.get("report_id"),
        p1_name=result.get("p1_name"),
        p2_name=result.get("p2_name"),
        total_score=result.get("total_score"),
        grade=result.get("grade"),
    )


@router.get("/{synastry_id}/html", response_class=HTMLResponse)
async def get_synastry_html(synastry_id: str):
    """返回合盘 HTML 报告。"""
    output_dir = str(Path(settings.reports_storage_path) / f"synastry_{synastry_id}")
    html_path  = os.path.join(output_dir, "report.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="报告尚未生成")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.websocket("/{synastry_id}/ws")
async def synastry_progress_ws(websocket: WebSocket, synastry_id: str):
    import redis.asyncio as aioredis
    await websocket.accept()
    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"synastry:{synastry_id}:progress")

    try:
        current = await r.hgetall(f"synastry:{synastry_id}")
        if current:
            status   = current.get(b"status", b"pending").decode()
            progress = int(current.get(b"progress", b"0"))
            await websocket.send_json({"status": status, "progress": progress})
            if status in ("done", "failed"):
                result_raw = current.get(b"result", b"").decode()
                result = json.loads(result_raw) if result_raw else {}
                await websocket.send_json({"status": status, "progress": progress, **result})
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
