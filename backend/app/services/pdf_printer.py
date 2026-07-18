"""PDF 生成服务 — 用 Playwright (headless Chromium) 把 HTML 打印成 PDF。

安装命令（首次）：
  pip install playwright
  playwright install chromium
"""
import asyncio
import tempfile
import os
from pathlib import Path

from app.core.config import get_settings


async def html_to_pdf(html_content: str, output_path: str) -> str:
    """
    将 HTML 字符串渲染为 PDF，保存到 output_path。

    返回 output_path（绝对路径）。
    超时由 settings.pdf_timeout_seconds 控制。
    """
    settings = get_settings()

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright 未安装。请运行：\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    # 写临时 HTML 文件（Playwright file:// 加载比 data URI 更可靠）
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                     mode="w", encoding="utf-8") as tmp:
        tmp.write(html_content)
        tmp_path = tmp.name

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    # 禁止加载外部资源（确保离线可用）
                    "--disable-web-security",
                ]
            )
            page = await browser.new_page()

            # 拦截 Google Fonts 等外部请求，避免超时
            await page.route("**/*fonts.googleapis.com*", lambda r: r.abort())
            await page.route("**/*fonts.gstatic.com*",   lambda r: r.abort())

            await page.goto(
                f"file://{tmp_path}",
                wait_until="networkidle",
                timeout=settings.pdf_timeout_seconds * 1000
            )

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            await page.pdf(
                path=output_path,
                format="A4",
                print_background=True,   # 保留背景色（羊皮纸底色）
                margin={
                    "top": "22mm",
                    "right": "20mm",
                    "bottom": "24mm",
                    "left": "20mm",
                }
            )
            await browser.close()

    finally:
        os.unlink(tmp_path)

    return output_path


def html_to_pdf_sync(html_content: str, output_path: str) -> str:
    """同步包装器，供 Celery worker（非 async 环境）调用。"""
    return asyncio.run(html_to_pdf(html_content, output_path))
