# Phase 1 启动指南

## 项目结构

```
yinduzhanxing/
├── skills/vedic-astrology/vedic-astrology-redskill/  ← 现有占星引擎（只读）
├── backend/    ← FastAPI 后端
├── frontend/   ← Vue 3 前端
└── examples/   ← 样本报告
```

---

## 一、后端启动

### 1. 安装依赖

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 安装 FastAPI 等后端依赖
pip install -r requirements.txt

# 安装 Playwright Chromium（PDF 生成用）
playwright install chromium
```

### 2. 安装 vedic 占星引擎依赖

```bash
# 用 setup_env.py 正确处理版本冲突（必须用这个，不能直接 pip install）
python ../skills/vedic-astrology/vedic-astrology-redskill/scripts/setup_env.py
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，按需修改 REDIS_URL、DATABASE_URL、VEDIC_SCRIPTS_PATH
```

`.env` 关键配置：
```env
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=postgresql+asyncpg://vedic:vedic@localhost:5432/vedic
VEDIC_SCRIPTS_PATH=../skills/vedic-astrology/vedic-astrology-redskill/scripts
REPORTS_STORAGE_PATH=./storage/reports
CORS_ORIGINS=["http://localhost:5173"]
```

### 4. 启动基础服务（Redis + PostgreSQL）

```bash
# 方式一：Docker Compose（推荐）
docker-compose up -d redis postgres

# 方式二：本地已有 Redis/PostgreSQL 可跳过
```

### 5. 启动 FastAPI

```bash
uvicorn app.main:app --reload --port 8000
```

### 6. 启动 Celery Worker

```bash
# 新开一个终端
cd backend
celery -A app.tasks.reading_tasks.celery_app worker --loglevel=info --concurrency=2
```

---

## 二、前端启动

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

---

## 三、使用 Docker Compose 一键启动（生产环境）

```bash
cd backend
docker-compose up --build
```

然后：
- 后端 API：http://localhost:8000
- API 文档：http://localhost:8000/docs
- 前端需单独 build 后由 Nginx 托管

---

## 四、API 接口速查

| 方法 | 路径 | 说明 |
|:-----|:-----|:-----|
| POST | `/api/readings` | 提交排盘，返回 reading_id |
| GET  | `/api/readings/:id/status` | 轮询进度（备选）|
| WS   | `/api/readings/:id/ws` | WebSocket 实时进度 |
| GET  | `/api/reports/:id/html` | 获取 HTML 报告 |
| GET  | `/api/reports/:id/pdf` | 下载 PDF 报告 |
| GET  | `/api/cities/search?q=上海` | 城市搜索 |
| GET  | `/api/health` | 健康检查 |

---

## 五、常见问题

**Q：排盘计算很慢？**
A：首次约 10-15 秒，相同出生时间第二次命中 Redis 缓存约 <1 秒。

**Q：PDF 生成失败？**
A：确认 `playwright install chromium` 已执行。容器环境需安装 libgbm1 等依赖（Dockerfile 已包含）。

**Q：找不到城市坐标？**
A：内置了约 40 个亚洲常用城市。其余城市通过 geopy Nominatim 网络查询。
   也可在前端直接传 `lat`/`lon` 坐标跳过城市查找。

**Q：VEDIC_SCRIPTS_PATH 怎么设置？**
A：填写 `scripts/` 目录的绝对路径，例如：
   `/home/user/yinduzhanxing/skills/vedic-astrology/vedic-astrology-redskill/scripts`

---

## 六、Phase 2 预告（AI 分析接入）

Phase 1 生成的报告只包含星盘原始数据（structured_data.md）。
Phase 2 将接入通义千问 / DeepSeek API，自动生成：
- 行星审计（p2a-p2d）
- 分盘分析（p3a、p3b）
- 宫位诊断（p4a、p4b）
- 人生架构总结（p5a、p5b）

届时报告将从「数据表格」升级为「完整叙述分析」。
