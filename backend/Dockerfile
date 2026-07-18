FROM python:3.11-slim

WORKDIR /app

# 系统依赖（Playwright Chromium 需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright Chromium（无需完整 Chrome，只装 chromium）
RUN playwright install chromium --with-deps

# 安装 vedic 脚本依赖（使用 setup_env.py 正确处理版本冲突）
COPY ../skills/vedic-astrology/vedic-astrology-redskill/scripts/setup_env.py /tmp/setup_env.py
RUN python /tmp/setup_env.py --no-venv

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
