# ── 阶段1：前端 build ──────────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# 产物在 /frontend/dist/

# ── 阶段2：后端镜像 ────────────────────────────────────────────
FROM python:3.13-slim

WORKDIR /app

# 系统依赖（Playwright Chromium + 中文字体）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright Chromium
RUN playwright install chromium --with-deps

# ── 安装 vedic 占星引擎依赖 ────────────────────────────────────
# 直接按正确顺序安装（不用 setup_env.py 创建新 venv，装到系统 site-packages）
RUN pip install --no-cache-dir "pysweph>=2.10.3.5" pytz numpy geocoder geopy requests \
    timezonefinder python-dateutil
RUN pip install --no-cache-dir "dashaflow>=0.3" --no-deps
RUN pip install --no-cache-dir "PyJHora==4.8.6"

# ── 复制 skills 目录（占星引擎脚本）──────────────────────────
COPY skills/vedic-astrology/vedic-astrology-redskill/scripts /app/skills/scripts

# 修复 PyJHora 缺失的 ephemeris 数据（从 pysweph 复制）
RUN python -c "\
import os, glob, shutil; \
import jhora; \
import swisseph as swe; \
jhora_ephe = os.path.join(os.path.dirname(jhora.__file__), 'data', 'ephe'); \
os.makedirs(jhora_ephe, exist_ok=True); \
swe_dir = os.path.dirname(swe.__file__); \
[shutil.copy2(f, os.path.join(jhora_ephe, os.path.basename(f))) \
 for d in [swe_dir, os.path.join(swe_dir,'data'), os.path.join(swe_dir,'ephe')] \
 if os.path.isdir(d) for f in glob.glob(os.path.join(d, '*.se1'))] \
" || echo "ephemeris copy skipped (will use fallback)"

# ── 复制后端代码 ───────────────────────────────────────────────
COPY backend/ .

# ── 复制前端 build 产物到 static/ ─────────────────────────────
COPY --from=frontend-builder /frontend/dist /app/static

# 存储目录（Railway Volume 会挂载到 /app/storage）
RUN mkdir -p /app/storage/reports

# 启动脚本（同时启动 Celery Worker 和 uvicorn）
COPY start_both.sh /app/start_both.sh
RUN chmod +x /app/start_both.sh

EXPOSE 8000

# 单容器同时运行 API + Worker（共享文件卷，避免 Railway 双服务共享 Volume 的问题）
CMD ["/app/start_both.sh"]
