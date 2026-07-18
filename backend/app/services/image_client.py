"""图像生成服务 — 使用通义万象（wanx），直接复用现有 QWEN_API_KEY。"""
import os
import time
from pathlib import Path
from typing import Optional


def _load_env_direct() -> dict:
    env_path = Path(__file__).parent.parent.parent / ".env"
    result = {}
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip()
    return result


def generate_portrait_image(prompt: str) -> Optional[str]:
    """
    调用通义万象 wanx2.1-t2i-turbo 生成人像图片，返回图片 URL。
    使用现有的 QWEN_API_KEY，无需额外配置。
    异步任务：提交 → 轮询结果，最多等待 60 秒。
    """
    import httpx

    env = _load_env_direct()
    api_key = env.get("QWEN_API_KEY") or os.getenv("QWEN_API_KEY", "")
    if not api_key:
        raise ValueError("未配置 QWEN_API_KEY，无法生成图片")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }

    # 提交生图任务
    client = httpx.Client(timeout=30.0)
    submit_resp = client.post(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis",
        headers=headers,
        json={
            "model": "wanx2.1-t2i-turbo",
            "input": {"prompt": prompt},
            "parameters": {"size": "1024*1024", "n": 1},
        },
    )
    submit_resp.raise_for_status()
    task_id = submit_resp.json()["output"]["task_id"]

    # 轮询任务状态，最多等 90 秒
    poll_headers = {"Authorization": f"Bearer {api_key}"}
    for _ in range(18):   # 18 次 × 5 秒 = 90 秒
        time.sleep(5)
        poll_resp = client.get(
            f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}",
            headers=poll_headers,
        )
        poll_resp.raise_for_status()
        result = poll_resp.json()
        task_status = result["output"]["task_status"]

        if task_status == "SUCCEEDED":
            results = result["output"].get("results", [])
            if results:
                return results[0].get("url")
            raise RuntimeError("生图成功但未返回图片 URL")

        if task_status == "FAILED":
            code = result["output"].get("code", "")
            msg  = result["output"].get("message", "未知错误")
            raise RuntimeError(f"生图失败：{code} - {msg}")

        # PENDING / RUNNING 继续等待

    raise RuntimeError("生图超时（90秒内未完成）")

