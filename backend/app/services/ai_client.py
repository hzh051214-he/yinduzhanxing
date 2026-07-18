"""AI 客户端 — Claude（主）+ 通义千问（备用）。"""
import os
from pathlib import Path
from typing import Optional


def _load_env_direct() -> dict:
    """直接从 .env 文件读取 key，绕过所有缓存和 Settings。"""
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


def call_llm(
    system_prompt: str,
    user_content: str,
    provider: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """调用 LLM，优先 Claude，备用通义千问。"""
    # 每次调用都直接从 .env 文件读取，绕过所有缓存
    env = _load_env_direct()
    anthropic_key = env.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
    qwen_key      = env.get("QWEN_API_KEY")      or os.getenv("QWEN_API_KEY", "")
    claude_model  = env.get("CLAUDE_MODEL")      or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
    qwen_model    = env.get("QWEN_MODEL")        or os.getenv("QWEN_MODEL", "qwen-long")

    use_claude = bool(anthropic_key) and provider != "qwen"
    use_qwen   = bool(qwen_key)

    if use_claude:
        return _call_claude(anthropic_key, claude_model,
                            system_prompt, user_content, max_tokens)
    elif use_qwen:
        return _call_qwen(qwen_key, qwen_model,
                          system_prompt, user_content, temperature, max_tokens)
    else:
        raise ValueError("未配置任何 AI API Key（ANTHROPIC_API_KEY 或 QWEN_API_KEY）")


def _call_claude(api_key: str, model: str,
                 system_prompt: str, user_content: str,
                 max_tokens: int) -> str:
    """调用 Claude API，支持自定义 base_url，绕过系统代理。"""
    try:
        import anthropic
        import httpx
    except ImportError:
        raise RuntimeError("请先安装 anthropic SDK：pip install anthropic")

    env = _load_env_direct()
    base_url = (
        env.get("ANTHROPIC_BASE_URL") or
        os.environ.get("ANTHROPIC_BASE_URL") or
        "https://api.anthropic.com"
    )

    # 用 mounts 显式清空代理，避免 Clash/VPN 拦截 HTTPS 导致 SSL 错误
    # proxy=None 不够，必须用 mounts 才能覆盖系统代理
    http_client = httpx.Client(mounts={"https://": None, "http://": None}, timeout=300.0)
    client = anthropic.Anthropic(
        api_key=api_key,
        base_url=base_url,
        http_client=http_client,
    )

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text


def _call_qwen(api_key: str, model: str,
               system_prompt: str, user_content: str,
               temperature: float, max_tokens: int) -> str:
    """调用通义千问 API（OpenAI 兼容模式）。"""
    from openai import OpenAI
    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
