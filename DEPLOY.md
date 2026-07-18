# 部署到 Railway 操作指南

## 前置准备

1. 注册 [Railway](https://railway.com) 账号（需绑定信用卡，首月有 $5 免费额度）
2. 安装 Railway CLI（可选，也可全程用网页操作）
3. 把代码上传到 GitHub（Railway 从 GitHub 拉取代码）

---

## 第一步：把代码推送到 GitHub

在 PowerShell 里：

```powershell
cd D:\yinduzhanxing

# 初始化 git（如果还没有）
git init
git add .
git commit -m "init: vedic astrology platform"

# 在 GitHub 新建仓库（不要勾选 Initialize，空仓库）
# 然后：
git remote add origin https://github.com/你的用户名/仓库名.git
git push -u origin main
```

> ⚠️ `.gitignore` 已配置好，`backend/.env`（含 API Keys）不会上传。

---

## 第二步：在 Railway 创建项目

1. 打开 https://railway.com，点击 **New Project**
2. 选择 **Deploy from GitHub repo**，连接你的 GitHub 账号
3. 选择刚刚推送的仓库

Railway 会自动检测到根目录的 `Dockerfile` 并开始构建。

---

## 第三步：添加 Redis 和 PostgreSQL

在 Railway 项目页面：

1. 点击 **+ New** → **Database** → **Add Redis**
2. 点击 **+ New** → **Database** → **Add PostgreSQL**

Railway 会自动注入 `REDIS_URL` 和 `DATABASE_URL` 环境变量。

---

## 第四步：配置环境变量

在 API 服务的 **Variables** 页面，添加以下变量：

```
ANTHROPIC_API_KEY=你的key
ANTHROPIC_BASE_URL=https://gaccode.com/claudecode
CLAUDE_MODEL=claude-sonnet-4-6

QWEN_API_KEY=你的key
QWEN_MODEL=qwen-long

REPORTS_STORAGE_PATH=/app/storage/reports
VEDIC_SCRIPTS_PATH=/app/skills/scripts

DEBUG=false
```

> `REDIS_URL` 和 `DATABASE_URL` Railway 会自动注入，不需要手动填。

---

## 第五步：添加 Celery Worker 服务

Railway 支持同一仓库部署多个服务：

1. 在项目页面点击 **+ New** → **GitHub Repo**（选同一个仓库）
2. 点击这个新服务 → **Settings** → **Build**
3. 把 `Dockerfile Path` 改为 `Dockerfile.worker`
4. 在 **Variables** 里添加同样的环境变量（复制粘贴 API 服务的即可）
5. 服务名改为 `worker`

---

## 第六步：添加持久化存储（Volume）

Railway 的磁盘重启后会清空，需要挂载 Volume 保存报告：

1. 在 API 服务页面 → **Volumes** → **Add Volume**
2. Mount Path：`/app/storage`
3. Worker 服务同样操作，挂载到 `/app/storage`（**同一个 Volume**，这样两者共享报告文件）

---

## 第七步：等待部署完成

Railway 会自动构建并部署，大约 3-5 分钟。  
部署成功后，点击 API 服务的域名，如 `https://xxx.up.railway.app`，应该可以看到网站。

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
| API 服务（低流量）| ~$1-3 |
| Celery Worker | ~$1-2 |
| Redis | ~$0.5-1 |
| PostgreSQL | ~$0.5-1 |
| Volume（1GB）| ~$0.25 |
| **合计** | **约 $4-8（约 30-55 元）** |

Hobby 计划 $5/月起，前 $5 使用量免费。

---

## 常见问题

**Q：构建失败，提示 pysweph 找不到 cp313 wheel**  
A：Dockerfile 用的是 `python:3.13-slim`，pysweph 已有 3.13 的 wheel，理论上没问题。如果失败换成 `python:3.12-slim`。

**Q：前端页面打开空白**  
A：检查 Railway 日志，看 FastAPI 启动时是否找到了 `/app/static/index.html`。

**Q：排盘任务一直 pending**  
A：检查 Worker 服务是否正常运行，Redis URL 是否正确注入。
