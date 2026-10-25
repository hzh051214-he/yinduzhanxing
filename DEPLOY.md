# 部署到 Railway 操作指南（单服务架构）

> **架构说明**：API（uvicorn）与 Celery Worker 在**同一个容器**内运行（由 `start_both.sh` 启动），
> 这样两者天然共享 `/app/storage` 文件卷——Railway 的 Volume 只能挂载到一个服务上，
> 拆成两个服务会导致 API 读不到 Worker 生成的报告文件。

## 前置准备

1. 注册 [Railway](https://railway.com) 账号（需绑定信用卡，首月有 $5 免费额度）
2. 把代码上传到 GitHub（Railway 从 GitHub 拉取代码）

---

## 第一步：把代码推送到 GitHub

```powershell
cd D:\yinduzhanxing
git add .
git commit -m "deploy: single-service architecture"
git push origin main
```

> ⚠️ `.gitignore` 已配置好，`backend/.env`（含 API Keys）不会上传。

---

## 第二步：在 Railway 创建项目

1. 打开 https://railway.com，点击 **New Project**
2. 选择 **Deploy from GitHub repo**，连接你的 GitHub 账号
3. 选择刚刚推送的仓库

Railway 会自动检测到根目录的 `Dockerfile` 并开始构建。

---

## 第三步：添加 Redis（必需）和 PostgreSQL（可选）

在 Railway 项目页面：

1. 点击 **+ New** → **Database** → **Add Redis**
2. （可选）点击 **+ New** → **Database** → **Add PostgreSQL**

Railway 会自动注入 `REDIS_URL`（必需，Celery 队列 + 进度推送依赖它）。
> `DATABASE_URL` 目前代码尚未实际使用（模型已定义、未接线），不加也不影响运行。

---

## 第四步：配置环境变量

在 **API 服务**的 **Variables** 页面，添加以下变量：

```
# AI 分析（两者都填：通义千问为主）
QWEN_API_KEY=你的key
ANTHROPIC_API_KEY=你的key
ANTHROPIC_BASE_URL=https://gaccode.com/claudecode
CLAUDE_MODEL=claude-sonnet-4-6

REPORTS_STORAGE_PATH=/app/storage/reports
VEDIC_SCRIPTS_PATH=/app/skills/scripts

DEBUG=false
```

> `REDIS_URL` Railway 会自动注入，不需要手动填。

---

## 第五步：添加持久化存储（Volume）

Railway 的磁盘重启后会清空，需要挂载 Volume 保存报告：

1. 在 **API 服务**页面 → **Settings** → **Volumes** → **Add Volume**
2. Mount Path：`/app/storage`

---

## 第六步：等待部署完成

Railway 会自动构建并部署，大约 5-10 分钟（首次构建要装 Playwright Chromium 和 PyJHora，比较慢）。
部署成功后，点击 API 服务的域名，如 `https://xxx.up.railway.app`，应该可以看到网站。

> 验证 Worker 是否随容器启动：查看 API 服务日志，应能看到
> `[start_both] launching celery worker...` 和 `uvicorn` 的启动日志。

---

## 访问地址

部署完成后：
- 网站：`https://你的服务名.up.railway.app`（直接访问就是前端页面）
- API 文档：无（生产环境已关闭，需要调试时在环境变量加 `DEBUG=true`）
- 健康检查：`https://你的服务名.up.railway.app/api/health`

---

## 费用估算

| 服务 | 估算费用/月 |
|------|------------|
| API+Worker 单服务（低流量）| ~$2-5 |
| Redis | ~$0.5-1 |
| Volume（1GB）| ~$0.25 |
| **合计** | **约 $3-6（约 20-45 元）** |

Hobby 计划 $5/月起，前 $5 使用量免费。

---

## 常见问题

**Q：构建失败，提示 pysweph 找不到 cp313 wheel**
A：Dockerfile 用的是 `python:3.13-slim`，pysweph 已有 3.13 的 wheel，理论上没问题。如果失败换成 `python:3.12-slim`。

**Q：前端页面打开空白**
A：检查 Railway 日志，看 FastAPI 启动时是否找到了 `/app/static/index.html`。

**Q：排盘任务一直 pending**
A：检查 API 服务日志里有没有 celery worker 的启动日志。若 worker 崩了，看日志中的 Python 报错（常见是 `VEDIC_SCRIPTS_PATH` 不对或 Redis 连不上）。

**Q：想要单独扩容 Worker**
A：单容器架构下 Worker 与 API 同生共死。若以后并发压力大，可以再建一个 Railway 服务用 `Dockerfile.worker`，但**报告文件需改为对象存储**（如 S3/R2），因为两个服务无法共享 Volume。
