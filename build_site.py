#!/usr/bin/env python3
"""扫描当前目录下所有 .mp4 视频，生成静态视频展示网站 index.html。
用法: 在视频所在目录运行 python3 build_site.py
新加了视频后重跑一次即可，然后 git add -A && git commit && git push 更新网站。
"""
import json
import os
import subprocess
import urllib.parse
from datetime import datetime

VIDEO_EXT = ".mp4"
THUMB_DIR = "thumbs"


def video_info(path):
    """用 ffprobe 获取视频时长(秒)，失败则返回 None。"""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(out.stdout.strip())
    except Exception:
        return None


def fmt_duration(sec):
    if not sec:
        return ""
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def clean_title(name):
    """从文件名生成展示标题：去掉扩展名，下划线转空格。"""
    return name[: -len(VIDEO_EXT)].replace("_", " ")


def main():
    videos = []
    for name in sorted(os.listdir(".")):
        if not name.lower().endswith(VIDEO_EXT):
            continue
        path = name
        st = os.stat(path)
        thumb = os.path.join(THUMB_DIR, name[: -len(VIDEO_EXT)] + ".jpg")
        videos.append({
            "name": name,
            "title": clean_title(name),
            "url": urllib.parse.quote(name),
            "thumb": urllib.parse.quote(thumb),
            "size": fmt_size(st.st_size),
            "date": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d"),
            "duration": fmt_duration(video_info(path)),
        })
    # 最新拍摄的排前面
    videos.sort(key=lambda v: v["date"], reverse=True)

    data = json.dumps(videos, ensure_ascii=False)

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>视频展示</title>
<style>
  :root {
    --bg: #0d1117; --card: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg); color: var(--text);
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
    min-height: 100vh;
  }
  header {
    position: sticky; top: 0; z-index: 10;
    background: rgba(13,17,23,.85); backdrop-filter: blur(8px);
    border-bottom: 1px solid var(--border);
    padding: 18px 24px;
    display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
  }
  header h1 { font-size: 20px; font-weight: 600; }
  header .count { color: var(--muted); font-size: 13px; }
  #search {
    margin-left: auto; flex: 0 1 300px;
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    color: var(--text); padding: 8px 14px; font-size: 14px; outline: none;
  }
  #search:focus { border-color: var(--accent); }
  main { padding: 24px; max-width: 1400px; margin: 0 auto; }
  .grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
  }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    overflow: hidden; cursor: pointer; transition: transform .15s, border-color .15s;
  }
  .card:hover { transform: translateY(-3px); border-color: var(--accent); }
  .thumb { position: relative; aspect-ratio: 16/9; background: #000; }
  .thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .badge {
    position: absolute; right: 8px; bottom: 8px;
    background: rgba(0,0,0,.75); color: #fff; font-size: 12px;
    padding: 2px 8px; border-radius: 6px;
  }
  .card .meta { padding: 12px 14px; }
  .card .title {
    font-size: 14px; line-height: 1.4; font-weight: 500;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; min-height: 39px;
  }
  .card .info { margin-top: 6px; font-size: 12px; color: var(--muted); }
  /* 播放弹窗 */
  .modal {
    position: fixed; inset: 0; z-index: 100; display: none;
    background: rgba(0,0,0,.9); align-items: center; justify-content: center;
    padding: 32px;
  }
  .modal.open { display: flex; }
  .modal-box { width: min(1080px, 100%); }
  .modal video { width: 100%; max-height: 72vh; background: #000; border-radius: 8px; }
  .modal-title {
    color: var(--text); font-size: 16px; font-weight: 500;
    padding: 12px 4px; text-align: center;
  }
  #close {
    position: absolute; top: 20px; right: 28px;
    background: none; border: none; color: #fff; font-size: 36px; cursor: pointer;
    opacity: .7; line-height: 1;
  }
  #close:hover { opacity: 1; }
  .empty { text-align: center; color: var(--muted); padding: 60px 0; display: none; }
</style>
</head>
<body>
<header>
  <h1>📹 视频展示</h1>
  <span class="count" id="count"></span>
  <input id="search" type="search" placeholder="搜索视频…" autocomplete="off">
</header>
<main>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty">没有找到匹配的视频</div>
</main>

<div class="modal" id="modal">
  <button id="close" title="关闭 (Esc)">&times;</button>
  <div class="modal-box">
    <video id="player" controls preload="metadata"></video>
    <div class="modal-title" id="mTitle"></div>
  </div>
</div>

<script>
const VIDEOS = __DATA__;

const grid = document.getElementById('grid');
const search = document.getElementById('search');
const empty = document.getElementById('empty');
const modal = document.getElementById('modal');
const player = document.getElementById('player');
const mTitle = document.getElementById('mTitle');

document.getElementById('count').textContent = '共 ' + VIDEOS.length + ' 个视频';

function render(list) {
  grid.innerHTML = '';
  empty.style.display = list.length ? 'none' : 'block';
  for (const v of list) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="thumb">
        <img loading="lazy" src="${v.thumb}" alt="${v.title}" onerror="this.style.display='none'">
        ${v.duration ? `<span class="badge">${v.duration}</span>` : ''}
      </div>
      <div class="meta">
        <div class="title">${v.title}</div>
        <div class="info">${v.date} · ${v.size}</div>
      </div>`;
    card.addEventListener('click', () => openVideo(v));
    grid.appendChild(card);
  }
}

function openVideo(v) {
  mTitle.textContent = v.title;
  player.src = v.url;
  modal.classList.add('open');
  player.play().catch(() => {});
  document.body.style.overflow = 'hidden';
}

function closeVideo() {
  modal.classList.remove('open');
  player.pause();
  player.removeAttribute('src');
  player.load();
  document.body.style.overflow = '';
}

document.getElementById('close').addEventListener('click', closeVideo);
modal.addEventListener('click', e => { if (e.target === modal) closeVideo(); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeVideo(); });

search.addEventListener('input', () => {
  const q = search.value.trim().toLowerCase();
  render(VIDEOS.filter(v => v.title.toLowerCase().includes(q)));
});

render(VIDEOS);
</script>
</body>
</html>
"""
    html = html.replace("__DATA__", data)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ 生成 index.html，共 {len(videos)} 个视频")


if __name__ == "__main__":
    main()
