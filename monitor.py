#!/usr/bin/env python3
"""
AI Creator Monitor v3 — YouTube-only, yt-dlp based.
=================================================
零认证、零RSS、零blogwatcher依赖。
只用 yt-dlp flat-playlist 模式拉取频道最新视频列表。

用法:
    python3 monitor.py

依赖:
    pip install yt-dlp
"""

import subprocess
import sys
import json
import os
from datetime import datetime, timezone

# ═══════════════════════════════════════════════
# 配置区
# ═══════════════════════════════════════════════

CHANNELS = {
    "Fireship":       "https://www.youtube.com/@Fireship/videos",
    "Matt Wolfe":     "https://www.youtube.com/@mreflow/videos",
    "Greg Isenberg":  "https://www.youtube.com/@GregIsenberg/videos",
    "Matthew Berman": "https://www.youtube.com/@matthew_berman/videos",
    "Corbin Brown":   "https://www.youtube.com/@Corbin_Brown/videos",
    "Cole Medin":     "https://www.youtube.com/@ColeMedin/videos",
    "AI Jason":       "https://www.youtube.com/@AIJasonZ/videos",
    "Mervin Praison": "https://www.youtube.com/@MervinPraison/videos",
}

VIDEOS_PER_CHANNEL = 10   # 每个频道拉取条数

# ═══════════════════════════════════════════════
# 实现
# ═══════════════════════════════════════════════


def fetch_channel(name, url):
    """用 yt-dlp flat-playlist 拉取频道最新视频。"""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--flat-playlist",
        "--playlist-end", str(VIDEOS_PER_CHANNEL),
        "--print", "%(title)s|%(webpage_url)s",
        url,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60,
        )
        videos = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if "|" in line and "youtube.com" in line:
                title, link = line.split("|", 1)
                videos.append((title.strip(), link.strip()))
        return videos
    except subprocess.TimeoutExpired:
        print(f"[{name}] TIMEOUT", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[{name}] ERROR: {e}", file=sys.stderr)
        return []


def dedup_new(videos, seen_file):
    """去重：只返回之前没见过的视频。"""
    seen = set()
    if os.path.exists(seen_file):
        with open(seen_file) as f:
            for line in f:
                seen.add(line.strip())

    new_videos = []
    new_ids = []
    for title, url in videos:
        vid = url.split("v=")[-1] if "v=" in url else url.split("/")[-1]
        if vid not in seen:
            new_videos.append((title, url))
            new_ids.append(vid)

    # 记录新视频ID
    if new_ids:
        with open(seen_file, "a") as f:
            for vid in new_ids:
                f.write(vid + "\n")

    return new_videos


def main():
    seen_file = os.path.expanduser("~/.hermes/data/ai_monitor_seen.txt")
    os.makedirs(os.path.dirname(seen_file), exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print(f"--- YOUTUBE SCAN {date_str} ---")

    for name, url in CHANNELS.items():
        all_videos = fetch_channel(name, url)
        new_videos = dedup_new(all_videos, seen_file)

        if new_videos:
            for title, link in new_videos:
                print(f"[{name}] {title} | {link}")
        elif all_videos:
            # 有拉取到但全是旧视频
            print(f"[{name}] (无新视频) {len(all_videos)} 条已见")
        else:
            print(f"[{name}] (拉取失败)")

    print("--- END ---")


if __name__ == "__main__":
    main()
