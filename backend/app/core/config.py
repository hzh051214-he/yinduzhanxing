"""应用配置，从环境变量读取。"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # 应用
    app_name: str = "Vedic Astrology API"
    debug: bool = False

    # Redis — Railway 注入 REDIS_URL，本地用 localhost
    redis_url: str = "redis://localhost:6379/0"

    # 数据库 — Railway 注入 DATABASE_URL
    database_url: str = "postgresql+asyncpg://vedic:vedic@localhost:5432/vedic"

    # Vedic 脚本路径 — 容器内固定为 /app/skills/scripts
    vedic_scripts_path: str = "/app/skills/scripts"

    # 报告存储路径 — Railway Volume 挂载到 /app/storage
    reports_storage_path: str = "./storage/reports"

    # PDF 生成超时（秒）
    pdf_timeout_seconds: int = 60

    # 排盘缓存过期时间（秒）
    chart_cache_ttl: int = 86400

    # CORS — 生产环境设为 * 或实际域名
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000", "*"]

    # ── AI 配置 ──────────────────────────────────────────────
    anthropic_api_key: Optional[str] = None
    claude_model: str = "claude-sonnet-4-6"
    anthropic_base_url: str = "https://api.anthropic.com"

    qwen_api_key: Optional[str] = None
    qwen_model: str = "qwen-long"

    deepseek_api_key: Optional[str] = None
    deepseek_model: str = "deepseek-chat"

    ai_provider: str = "auto"

    # ── 图像生成（通义万象）──────────────────────────────────
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    dalle_model: str = "dall-e-3"
    dalle_size: str = "1024x1024"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


from functools import lru_cache


def get_settings() -> Settings:
    return _get_settings_cached()


@lru_cache(maxsize=1)
def _get_settings_cached() -> Settings:
    return Settings()
