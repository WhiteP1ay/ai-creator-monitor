#!/usr/bin/env python3
"""
AI Creator Monitor v4 — time-window based with parallel metadata fetch.
=======================================================================
flat-playlist 快速拉列表 → 新视频并行获取元数据 → 过滤7天内 → 输出。
"""

import subprocess
import sys
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

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

LIST_PER_CHANNEL = 10
WINDOW_DAYS = 7
MAX_WORKERS = 8


def flat_list(url):
    """flat-playlist: fast title+URL list, no dates."""
    cmd = [
        sys.executable, "-m", "yt_dlp", "--flat-playlist",
        "--playlist-end", str(LIST_PER_CHANNEL),
        "--print", "%(title)s|%(webpage_url)s",
        url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    videos = []
    for line in r.stdout.strip().split("\n"):
        if "|" in line and "youtube.com" in line:
            title, link = line.split("|", 1)
            videos.append((title.strip(), link.strip()))
    return videos


def get_upload_date(url):
    """Single video: dump-json to get upload_date. ~20s per call."""
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--cookies-from-browser", "chrome",
        "--dump-json", "--skip-download", url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        d = json.loads(r.stdout)
        return d.get("upload_date")
    except Exception:
        return None


def load_seen(path):
    seen = set()
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                vid = line.strip().split("|")[0]
                if vid:
                    seen.add(vid)
    return seen


def save_seen(path, entries):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for e in entries:
            f.write(e + "\n")


def main():
    seen_file = os.path.expanduser("~/.hermes/data/ai_monitor_seen.txt")
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    cutoff_str = cutoff.strftime("%Y%m%d")
    seen = load_seen(seen_file)
    new_seen = []

    print(f"--- YOUTUBE SCAN {datetime.now(timezone.utc).strftime('%Y-%m-%d')} ---")
    print(f"(window: past {WINDOW_DAYS}d, cutoff: {cutoff_str})")

    all_new = []  # (name, title, link, vid)

    # Step 1: flat-list all channels
    for name, url in CHANNELS.items():
        videos = flat_list(url)
        for title, link in videos:
            vid = link.split("v=")[-1] if "v=" in link else link.split("/")[-1]
            if vid not in seen:
                all_new.append((name, title, link, vid))

    if not all_new:
        print("(all channels: no new videos)")
        print("--- END ---")
        return

    print(f"(fetching dates for {len(all_new)} new videos in parallel...)")

    # Step 2: parallel metadata fetch
    vid_to_info = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(get_upload_date, link): (name, title, link, vid)
                   for name, title, link, vid in all_new}
        for f in as_completed(futures):
            name, title, link, vid = futures[f]
            date_str = f.result()
            vid_to_info[vid] = (name, title, link, date_str)

    # Step 3: filter by date window and output
    by_channel = {}
    for name, title, link, vid in all_new:
        info = vid_to_info.get(vid)
        if info is None:
            continue
        _, _, _, date_str = info
        new_seen.append(f"{vid}|{date_str or 'unknown'}")

        if date_str and date_str >= cutoff_str:
            formatted = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            by_channel.setdefault(name, []).append((title, link, formatted))

    # Output
    for name in CHANNELS:
        items = by_channel.get(name, [])
        if items:
            for title, link, date in items:
                print(f"[{name}] {title} | {date} | {link}")
        else:
            # Check if channel had new items outside window
            outside = sum(1 for n, t, l, v in all_new if n == name and v in vid_to_info)
            if outside > 0:
                print(f"[{name}] ({outside} new items, all outside {WINDOW_DAYS}d window)")

    save_seen(seen_file, new_seen)
    print("--- END ---")


if __name__ == "__main__":
    main()
