# 抖音热点雷达 🔥

帮手工类博主（风琴本、尼泊尔手工、手账）实时监控抖音热点，发现起势视频，AI 分析蹭热度方案，推送到企业微信群。

## 整体架构

```
cron-job.org (每45分钟)
    │
    ▼
Vercel API (/api/trigger)
    │
    ├── 1. 采集抖音热搜 (不需要Cookie)
    │       └── AI 分析：哪些热搜能和手工关联？怎么蹭？
    │
    ├── 2. 采集同行视频 (需要Cookie)
    │       ├── 50个监控账号的最新作品数据
    │       ├── 起势评分算法（增速+互动+突破）
    │       └── AI 分析：这条为什么火？怎么蹭？
    │
    └── 3. 推送到企微群
            ├── 热搜蹭热度机会
            ├── 起势预警 + AI 建议
            └── Cookie 失效提醒

GitHub Actions (每45分钟备用) ──── 同上流程
         │
Turso DB ◄──── 所有数据存这里 ────► Vercel 前端仪表盘
(云端SQLite)                         (手机/电脑都能看)
```

## 推送效果

### 热搜蹭热度

```
📈 热搜蹭热度机会

1. 🔍 慢充旅行太治愈了
   > 关联：手工本身就是"慢生活"，拍一条制作风琴本的过程，配上旅行bgm
   > 拍什么：「边旅行边做手工本」的vlog片段
   > 标题：慢充旅行｜在尼泊尔做一本风琴本有多治愈

2. 🔍 万物皆可波点风
   > 关联：把波点元素融入手账本封面设计
   > 拍什么：手工制作波点主题风琴本
   > 标题：万物皆可波点｜我的新手账本也不例外
```

### 起势预警

```
🔥 起势预警 (88分)
手工制作迷你书包挂件 超治愈的过程
@手作小匠
> 赞 9.5w | 评 4.2k | 藏 1.2w

💡 怎么蹭
🔥 这条火在迷你化+治愈感，拍手工过程的人特别多
👉 具体做法：把风琴本做成挂件版，拍个过程视频，
   标题带上"挂件""治愈""手工"
📝 标题参考：
> 手工迷你风琴本挂件｜5分钟完成
> 用尼泊尔手工纸做治愈系挂件
```

## 功能模块

| 模块 | 说明 |
|------|------|
| **热搜监控** | 每 45 分钟抓抖音热搜榜，AI 分析哪些能和手工关联 |
| **同行监控** | 监控 50 个同行账号，发现数据异常增长的视频 |
| **起势评分** | 三维度加权算法：增速 35% + 互动质量 35% + 账号突破 30% |
| **AI 分析** | Claude Sonnet 分析爆点、评论、蹭热度方案（说人话版） |
| **企微推送** | 群机器人 Webhook，发现机会自动推送 |
| **Web 仪表盘** | 深色主题，手机/电脑都能看，管理账号、更新 Cookie |
| **防重复** | 同一视频只推一次，热搜分析 1 小时去重 |
| **Cookie 检测** | 失效时推送提醒，24 小时只提醒 1 次 |

## 项目结构

```
tiktok/
├── core/                          # 核心模块
│   ├── config.py                  # 配置管理（环境变量 + 算法参数）
│   ├── douyin.py                  # 抖音 Web API 客户端
│   ├── database.py                # 数据库（Turso 云端 / 本地 SQLite）
│   ├── analyzer.py                # 起势评分算法
│   ├── ai_analyzer.py             # AI 爆点分析（Claude）
│   └── notifier.py                # 企微群机器人推送
│
├── api/                           # Vercel Serverless API
│   ├── trigger.py                 # 触发采集（GET/POST，cron-job.org 调这个）
│   ├── dashboard.py               # 仪表盘数据（分页 + 热搜 + 概览）
│   ├── author_detail.py           # 作者详情（统计 + TOP 作品）
│   ├── authors.py                 # 监控账号管理
│   ├── settings.py                # Cookie 更新 / 批量添加账号
│   └── test_notify.py             # 推送测试
│
├── scripts/                       # 本地脚本
│   ├── collect.py                 # 采集主流程（Actions 跑这个）
│   ├── import_following.py        # 导入关注列表
│   ├── verify.py                  # 项目验收（5 项检查）
│   └── test_notify.py             # 推送测试
│
├── public/
│   └── index.html                 # 前端仪表盘（深色主题，4 个 Tab）
│
├── .github/workflows/
│   ├── collect.yml                # 定时采集（每 45 分钟，白天）
│   └── test_ai.yml                # AI 网关连通性测试
│
├── vercel.json                    # Vercel 路由配置
└── requirements.txt               # Python 依赖
```

## 前端仪表盘

4 个 Tab：

| Tab | 功能 |
|-----|------|
| 🔥 起势 | 视频列表（按评分排序），点击作者看详情，触底加载更多 |
| 📈 热搜 | 抖音热搜 Top 30 |
| 👥 同行 | 添加/移除监控账号（粘贴主页链接，支持批量） |
| ⚙️ 设置 | 更新 Cookie、测试推送 |

## 起势评分算法

```
总分 = 增速分 × 0.35 + 互动质量分 × 0.35 + 账号突破分 × 0.30

增速分：点赞数 ÷ 发布小时数，新视频加权
互动质量分：点赞率 + 评论率 + 分享率 + 收藏率（手工类收藏权重更高）
账号突破分：本条数据 ÷ 该账号近 20 条平均（超 3 倍开始拿分，10 倍满分）

60 分以上 → 起势预警
```

## 部署依赖

| 服务 | 用途 | 费用 |
|------|------|------|
| [Vercel](https://vercel.com) | 前端 + API 托管 | 免费 |
| [Turso](https://turso.tech) | 云端 SQLite 数据库 | 免费 |
| [cron-job.org](https://cron-job.org) | 定时触发采集（每 45 分钟） | 免费 |
| [GitHub Actions](https://github.com/features/actions) | 备用定时任务 | 免费 |
| 企业微信群机器人 | 推送通知 | 免费 |
| AI 网关 | Claude/Gemini 分析 | 需要 Key |

**总费用：¥0**（AI 用量除外）

## 环境变量

### 必填

| 变量 | 说明 |
|------|------|
| `TURSO_DATABASE_URL` | Turso 数据库地址 |
| `TURSO_AUTH_TOKEN` | Turso 认证 Token |
| `WECOM_WEBHOOK_URL` | 企微群机器人 Webhook URL |

### 推荐

| 变量 | 说明 |
|------|------|
| `DOUYIN_COOKIE` | 抖音 Cookie（也可通过网页设置页更新到数据库） |
| `AI_GATEWAY_URL` | AI 网关地址（不配则跳过 AI 分析） |
| `AI_GATEWAY_KEY` | AI 网关 Key |
| `AI_MODEL` | AI 模型，默认 `claude-sonnet-4-6` |

### 可选

| 变量 | 说明 |
|------|------|
| `WECOM_CORP_ID` | 企微企业 ID（应用推送备用） |
| `WECOM_AGENT_ID` | 企微应用 AgentId |
| `WECOM_SECRET` | 企微应用 Secret |
| `WECOM_USER_ID` | 企微接收人 UserID |

## 快速开始

### 1. 本地开发

```bash
git clone https://github.com/Edbiluo/tiktok_analysis.git
cd tiktok_analysis
pip install -r requirements.txt
cp .env.example .env  # 编辑填入配置

# 验收检查
python -m scripts.verify

# 手动采集一次
python -m scripts.collect --hot-only

# 导入关注列表
python -m scripts.import_following --sec-uid YOUR_SEC_UID
```

### 2. 部署

1. **Vercel**：GitHub 登录 → Import 仓库 → 添加环境变量 → 部署
2. **Turso**：注册 → 建数据库 → 拿 URL 和 Token
3. **cron-job.org**：注册 → 创建任务 → URL 填 `https://你的域名/api/trigger` → 每 45 分钟
4. **企微**：建群 → 添加群机器人 → 拿 Webhook URL
5. **GitHub Secrets**：添加所有环境变量

### 3. 获取抖音 Cookie

1. Chrome 打开 `douyin.com` 并登录
2. F12 → Network → 随便点一个请求 → 复制 Cookie 值
3. 在仪表盘设置页粘贴保存（或写入环境变量）

## 数据库表

| 表 | 说明 |
|----|------|
| `authors` | 监控账号（sec_uid 主键） |
| `videos` | 视频基本信息 |
| `video_snapshots` | 每次采集的数据快照（播放/赞/评/藏/转） |
| `trending_topics` | 热搜记录 |
| `alerts` | 推送记录（防重复） |
| `settings` | KV 设置（当前存 Cookie） |
