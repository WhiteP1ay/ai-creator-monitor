# AI Creator Monitor

多平台 AI 博主更新采集器。每天跑一次，输出 YouTube + B站 博主的最新视频，给下游 agent 格式化日报。

## 设计哲学

**零外部 Python 依赖**。只用一个预编译的 Go 二进制 (`blogwatcher-cli`) 管理 YouTube RSS。B站直接用标准库 `urllib` 调公开 API。

任何能跑 Python 3.9+ 的机器都能用。任何 LLM agent 都能读这份代码。

## 快速开始

### 1. 安装 blogwatcher-cli

```bash
# macOS Apple Silicon
curl -fsSL https://github.com/JulienTant/blogwatcher-cli/releases/latest/download/blogwatcher-cli_darwin_arm64.tar.gz | tar xz -C ~/.local/bin blogwatcher-cli

# Linux amd64
curl -fsSL https://github.com/JulienTant/blogwatcher-cli/releases/latest/download/blogwatcher-cli_linux_amd64.tar.gz | sudo tar xz -C /usr/local/bin blogwatcher-cli
```

其他平台见 [blogwatcher-cli releases](https://github.com/JulienTant/blogwatcher-cli/releases)。

### 2. 运行

```bash
python3 monitor.py
```

首次运行会自动注册 YouTube RSS 源。输出示例：

```
Scanning 8 blog(s)...
  Fireship: RSS | Found: 15 | New: 3
  ...

--- YOUTUBE ---
[Fireship] Google's AI endgame is here... | 2026-05-22 | https://youtube.com/watch?v=...
[Matt Wolfe] AI News: Microsoft Finally Reveals Their Plan! | 2026-06-05 | ...

--- BILIBILI ---
[Genji是真想教会你] 只用200分钟系统学会AI动画 | 2026-06-01 | https://bilibili.com/video/BV...
[花叔v] Claude Code源码泄露！首发解读51万行代码 | 2026-05-20 | ...

--- END ---
```

### 3. 搭配 Hermes Agent

**方式一：Skill（推荐）**

项目中已附带 `ai-creator-inspiration` skill。用户说"同行最近更新了什么"或"找找灵感"即触发，无需定时。

```bash
# 安装 skill
hermes skill install WhiteP1ay/ai-creator-monitor
```

**方式二：Cron Job**

将 `monitor.py` 放到 `~/.hermes/scripts/`，然后：

```bash
hermes cron create \
  --name "AI博主日报" \
  --schedule "0 9 * * *" \
  --script monitor.py \
  --prompt "你是AI博主日报编辑。上方是数据采集输出（YouTube + B站）。请整理为中文日报格式：按平台分组，每人选2-3条，附点评。选出3条今日推荐。" \
  --deliver origin
```

## 配置

编辑 `monitor.py` 顶部的两个字典：

```python
YOUTUBE_CHANNELS = {
    "频道名": "https://www.youtube.com/@handle",
    ...
}

BILIBILI_UIDS = {
    "UP主名": 12345678,  # 从 space.bilibili.com/UID 获取
    ...
}
```

B站 UID 获取方式：打开 UP主 空间页，URL 中的数字即是 UID。

## 工作原理

```
monitor.py
  ├─ blogwatcher-cli scan  → 拉取所有YouTube RSS feed
  ├─ 查询 SQLite DB       → 筛出48h内未读文章
  ├─ B站 API 低频轮询     → 每人1.5s间隔，避免风控
  └─ 结构化文本输出        → agent 直接消费
```

- **YouTube**: 通过 blogwatcher-cli 订阅频道 RSS，自动发现 feed，持久化到 SQLite
- **B站**: 调用 `api.bilibili.com/x/space/arc/search`（无需认证），低频轮询不触发风控

## 已知限制

- **B站**: 如短时间内大量请求会触发风控（-799）。每天跑一次、6个UP主不会有问题
- **抖音/TikTok**: 未接入。ByteDance 无公开 API，需要 RSSHub 或 Selenium 方案
- **YouTube Shorts**: RSS 会采集 Shorts，可能产生噪音。agent 格式化时建议过滤

## 依赖

| 依赖 | 用途 |
|------|------|
| Python 3.9+ | 运行环境 |
| [blogwatcher-cli](https://github.com/JulienTant/blogwatcher-cli) | YouTube RSS 管理 |
| 无其他 | 零 pip install |

## License

MIT
