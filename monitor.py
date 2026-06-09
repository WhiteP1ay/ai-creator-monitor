#!/usr/bin/env python3
"""
AI Creator Monitor — 多平台AI博主更新采集
============================================
采集 YouTube (RSS) + B站 (API) 的AI博主最新视频，
输出结构化文本供下游 agent 格式化日报。

零外部Python依赖。仅需 blogwatcher-cli 管理YouTube RSS。

用法:
    python3 monitor.py

配置:
    修改下面的 YOUTUBE_CHANNELS 和 BILIBILI_UIDS 即可自定义监控名单。
"""

import subprocess
import sqlite3
import sys
import json
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ═══════════════════════════════════════════════
# 配置区 — 修改这里来定制监控名单
# ═══════════════════════════════════════════════

BLOGWATCHER_BIN = str(Path.home() / ".local/bin/blogwatcher-cli")
BLOGWATCHER_DB = str(Path.home() / ".blogwatcher-cli/blogwatcher-cli.db")
CUTOFF_HOURS = 48  # 只输出过去N小时内的更新

# YouTube: 博主名 -> 频道URL
YOUTUBE_CHANNELS = {
    "Fireship":           "https://www.youtube.com/@Fireship",
    "Matt Wolfe":         "https://www.youtube.com/@mreflow",
    "Greg Isenberg":      "https://www.youtube.com/@GregIsenberg",
    "Matthew Berman":     "https://www.youtube.com/@matthew_berman",
    "Corbin Brown":       "https://www.youtube.com/@Corbin_Brown",
    "Cole Medin":         "https://www.youtube.com/@ColeMedin",
    "AI Jason":           "https://www.youtube.com/@AIJasonZ",
    "Mervin Praison":     "https://www.youtube.com/@MervinPraison",
}

# B站: 博主名 -> UID
BILIBILI_UIDS = {
    "Genji是真想教会你": 211499116,
    "林亦LYi":           289889915,
    "图灵的猫":           282739748,
    "老麦的工具库":       486989780,
    "花叔v":             14097567,
    "AI研究室-帆哥":      2161614,
}

# ═══════════════════════════════════════════════
# 内部实现
# ═══════════════════════════════════════════════


def setup_youtube_channels():
    """首次运行：注册YouTube RSS源到blogwatcher。
    幂等操作，已注册的频道会跳过。
    """
    # 获取已注册的频道URL
    existing = set()
    try:
        result = subprocess.run(
            [BLOGWATCHER_BIN, "blogs"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.split("\n"):
            if "https://" in line:
                existing.add(line.strip().split()[-1])
    except Exception:
        pass

    for name, url in YOUTUBE_CHANNELS.items():
        if url in existing:
            continue
        subprocess.run(
            [BLOGWATCHER_BIN, "add", name, url],
            capture_output=True, timeout=15,
        )


def scan_youtube():
    """扫描所有YouTube RSS源，返回未读文章列表。"""
    result = subprocess.run(
        [BLOGWATCHER_BIN, "scan"],
        capture_output=True, text=True, timeout=120,
    )
    print(result.stdout, end="")

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=CUTOFF_HOURS)).isoformat()
    try:
        conn = sqlite3.connect(BLOGWATCHER_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT b.name, a.title, a.url, a.published_date
            FROM articles a JOIN blogs b ON a.blog_id = b.id
            WHERE a.is_read = 0 AND a.discovered_date > ?
            ORDER BY b.name, a.published_date DESC
        """, (cutoff,)).fetchall()
        conn.close()

        print("\n--- YOUTUBE ---")
        if rows:
            for r in rows:
                name = r["name"].replace("_", " ")
                date = r["published_date"][:10] if r["published_date"] else "?"
                print(f"[{name}] {r['title']} | {date} | {r['url']}")
        else:
            print("(no new videos in last {CUTOFF_HOURS}h)")
    except Exception as e:
        print(f"[YouTube DB Error] {e}", file=sys.stderr)


def _get_bilibili_cookies():
    """获取B站新鲜cookie。"""
    try:
        req = urllib.request.Request("https://www.bilibili.com", headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
        resp = urllib.request.urlopen(req, timeout=10)
        cookies = {}
        for part in resp.getheader("Set-Cookie", "").split(","):
            for item in part.split(";"):
                if "=" in item:
                    k, v = item.strip().split("=", 1)
                    if k in ("buvid3", "b_nut"):
                        cookies[k] = v
        return "; ".join(f"{k}={v}" for k, v in cookies.items())
    except Exception:
        return ""


def fetch_bilibili(uid, cookie=""):
    """拉取单个B站UP主的最新5条视频。"""
    url = (
        f"https://api.bilibili.com/x/space/arc/search"
        f"?mid={uid}&ps=5&pn=1&order=pubdate&jsonp=jsonp"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": f"https://space.bilibili.com/{uid}",
    }
    if cookie:
        headers["Cookie"] = cookie

    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        if data["code"] == 0:
            return data.get("data", {}).get("list", {}).get("vlist", [])
    except Exception as e:
        print(f"  [B站 API Error] {e}", file=sys.stderr)
    return []


def scan_bilibili():
    """轮询B站UP主的最新视频。"""
    print("\n--- BILIBILI ---")
    cookie = _get_bilibili_cookies()

    for name, uid in BILIBILI_UIDS.items():
        videos = fetch_bilibili(uid, cookie)
        if videos:
            for v in videos:
                created = v.get("created", 0)
                date_str = (
                    datetime.fromtimestamp(created).strftime("%Y-%m-%d")
                    if created else "?"
                )
                print(
                    f"[{name}] {v.get('title', '?')}"
                    f" | {date_str}"
                    f" | https://www.bilibili.com/video/{v.get('bvid', '')}"
                )
        else:
            print(f"[{name}] (API受限或无新视频)")
        time.sleep(1.5)  # 控制频率避免风控


def main():
    setup_youtube_channels()
    scan_youtube()
    scan_bilibili()
    print("\n--- END ---")


if __name__ == "__main__":
    main()
