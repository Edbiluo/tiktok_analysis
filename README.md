# 抖音热点雷达 🔥

实时监控抖音热点和同行动态，发现起势视频，推送到企业微信。

## 功能

- 📊 同行账号监控（50 个关注账号的最新视频数据）
- 🔥 起势视频检测（综合评分算法，发现增长异常的视频）
- 📈 抖音热搜趋势追踪
- 💬 企业微信自动推送预警
- 🌐 Web 仪表盘（手机/电脑都能看）
- ⏱️ 定时自动采集 + 手动触发

## 架构

```
GitHub Actions（定时采集）→ Turso DB（存储）→ Vercel（API + 前端）
                                                    ↓
                                              企业微信推送
```

## 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的配置

# 手动触发一次采集
python -m scripts.collect

# 启动本地 API
vercel dev
```

## 部署

- **前端 + API**：Vercel（自动从 GitHub 部署）
- **定时任务**：GitHub Actions（每 4 小时）
- **数据库**：Turso（SQLite 云端版）

## 配置

在 GitHub Secrets 和 Vercel 环境变量中设置：

| 变量名 | 说明 |
|--------|------|
| `WECOM_CORP_ID` | 企业微信企业 ID |
| `WECOM_AGENT_ID` | 自建应用 AgentId |
| `WECOM_SECRET` | 自建应用 Secret |
| `WECOM_USER_ID` | 接收人 UserID |
| `DOUYIN_COOKIE` | 抖音 Cookie |
| `TURSO_DATABASE_URL` | Turso 数据库地址 |
| `TURSO_AUTH_TOKEN` | Turso 认证 Token |
