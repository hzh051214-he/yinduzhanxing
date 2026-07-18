"""报告 API 路由。"""
import os
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional

from app.core.config import get_settings

router = APIRouter(prefix="/reports", tags=["reports"])
settings = get_settings()


def _safe_path(file_path: str) -> Path:
    """验证文件路径必须在报告存储目录内，防止路径遍历攻击。"""
    storage = Path(settings.reports_storage_path).resolve()
    target  = Path(file_path).resolve()
    if not str(target).startswith(str(storage)):
        raise HTTPException(status_code=403, detail="访问路径不合法")
    return target


def _meta_path(report_id: str) -> Optional[str]:
    """查找 report_meta.json 路径。
    优先走 Redis 索引（O(1)），缓存未命中时回退到磁盘遍历（O(n)）并写入缓存。
    """
    import redis as redis_lib
    storage = Path(settings.reports_storage_path)

    # 1. 先查 Redis 索引
    try:
        r = redis_lib.from_url(settings.redis_url)
        cached = r.get(f"report_idx:{report_id}")
        if cached:
            meta_file = Path(cached.decode())
            if meta_file.exists():
                return str(meta_file)
    except Exception:
        pass   # Redis 不可用时静默降级到磁盘遍历

    # 2. 磁盘全量遍历（兜底）
    if not storage.exists():
        return None
    for reading_dir in storage.iterdir():
        if not reading_dir.is_dir():
            continue
        meta_file = reading_dir / "report_meta.json"
        if meta_file.exists():
            try:
                with open(meta_file, encoding="utf-8") as f:
                    meta = json.load(f)
                if meta.get("report_id") == report_id:
                    # 写入 Redis 索引供下次快速查找，TTL 24小时
                    try:
                        r.setex(f"report_idx:{report_id}", 86400, str(meta_file))
                    except Exception:
                        pass
                    return str(meta_file)
            except Exception:
                continue
    return None


@router.get("/{report_id}/html", response_class=HTMLResponse)
async def get_report_html(report_id: str):
    """返回 HTML 报告内容（供前端 iframe 内嵌展示）。"""
    meta_file = _meta_path(report_id)
    if not meta_file:
        raise HTTPException(status_code=404, detail="报告不存在或已过期")

    with open(meta_file, encoding="utf-8") as f:
        meta = json.load(f)

    html_path = meta.get("html_path")
    if not html_path:
        raise HTTPException(status_code=404, detail="HTML 报告文件不存在")

    safe = _safe_path(html_path)   # 路径安全校验
    if not safe.exists():
        raise HTTPException(status_code=404, detail="HTML 报告文件不存在")

    return HTMLResponse(content=safe.read_text(encoding="utf-8"))


@router.get("/{report_id}/pdf")
async def download_report_pdf(report_id: str):
    """下载 PDF 报告。若 PDF 尚未生成，实时生成并返回。"""
    meta_file = _meta_path(report_id)
    if not meta_file:
        raise HTTPException(status_code=404, detail="报告不存在或已过期")

    with open(meta_file, encoding="utf-8") as f:
        meta = json.load(f)

    pdf_path = meta.get("pdf_path")

    # PDF 已存在，直接返回（路径安全校验）
    if pdf_path:
        safe_pdf = _safe_path(pdf_path)
        if safe_pdf.exists():
            return FileResponse(
                path=str(safe_pdf),
                media_type="application/pdf",
                filename="vedic_astrology_report.pdf",
            )

    # PDF 不存在，从 HTML 实时生成
    html_path = meta.get("html_path")
    if not html_path or not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="HTML 报告文件不存在，无法生成 PDF")

    with open(html_path, encoding="utf-8") as f:
        html_content = f.read()

    output_dir = str(Path(meta_file).parent)
    pdf_path = os.path.join(output_dir, "report.pdf")

    try:
        from app.services.pdf_printer import html_to_pdf_sync
        html_to_pdf_sync(html_content, pdf_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF 生成失败：{e}")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename="vedic_astrology_report.pdf",
    )


@router.get("/{report_id}/meta")
async def get_report_meta(report_id: str):
    """返回报告元数据（供前端判断报告状态）。"""
    meta_file = _meta_path(report_id)
    if not meta_file:
        raise HTTPException(status_code=404, detail="报告不存在或已过期")

    with open(meta_file, encoding="utf-8") as f:
        return json.load(f)
