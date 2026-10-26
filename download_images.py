"""
download_images.py：下載作品圖片（階段 3-2）

由 download_images.bat 執行。對照學習地圖 A1「把書借回資料室」的「照片」那一半。

做的事：
  1. 讀 data/draft/ 和 data/artworks/ 裡每一筆作品 JSON
  2. 找出圖片網址：
       臺史博（文化部典藏網）→ 先打開藏品頁，找到頁面上的主圖
       國家文化記憶庫          → JSON 裡的 image.source_url 就是圖檔
  3. 下載、轉成 .jpg、長邊超過 1024 像素就縮小
  4. 存成 data/images/<作品編號>.jpg（已經有的就跳過）
  5. 結果同時寫到 logs/download_images.txt，Claude 可以直接讀

這不是 MCP Server，所以可以用 print() 印給你看。
"""

from __future__ import annotations

import html
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parent
JSON_DIRS = [ROOT / "data" / "draft", ROOT / "data" / "artworks"]
IMAGE_DIR = ROOT / "data" / "images"
LOG_FILE = ROOT / "logs" / "download_images.txt"
MAX_SIDE = 1024
HEADERS = {"User-Agent": "art-mcp/0.1 (student project; downloads openly licensed museum images)"}

LINES: list[str] = []


def say(msg: str) -> None:
    print(msg)
    LINES.append(msg)


def find_main_image(page_html: str, page_url: str) -> str | None:
    """在文化部典藏網的藏品頁裡找主圖：<img> 的 src 有 ShowGalImage、alt 有「登錄號」、
    class 是 img-fluid（不是下面那排小圖 OtherImage）。找不到回傳 None。"""
    for tag in re.findall(r"<img\b[^>]*>", page_html, flags=re.IGNORECASE):
        if ("ShowGalImage" in tag and "登錄號" in tag
                and re.search(r'class="[^"]*img-fluid', tag) and "OtherImage" not in tag):
            m = re.search(r'src="([^"]+)"', tag)
            if m:
                return urljoin(page_url, html.unescape(m.group(1)))
    return None


def to_jpeg(data: bytes) -> tuple[bytes, tuple[int, int]]:
    """任何格式的圖片 → RGB 的 JPEG，長邊不超過 MAX_SIDE。回傳（檔案內容, 寬高）。"""
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        return buf.getvalue(), im.size


def image_url_for(record: dict, client: httpx.Client) -> str:
    src = record["image"]["source_url"]
    if "/Object" in src:                       # 臺史博藏品頁：要先開頁面找主圖
        r = client.get(src)
        r.raise_for_status()
        url = find_main_image(r.text, str(r.url))
        if not url:
            raise RuntimeError("藏品頁上找不到主圖（網站可能改版了）")
        return url
    return src                                 # 國家文化記憶庫：直接就是圖檔


def main() -> int:
    force = "--force" in sys.argv
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(exist_ok=True)
    records = {}
    for d in JSON_DIRS:
        for p in sorted(d.glob("*.json")):
            rec = json.loads(p.read_text(encoding="utf-8"))
            records[rec["id"]] = rec
    say(f"共 {len(records)} 筆作品資料，圖片存到 data/images/")
    ok = skipped = 0
    failed: list[str] = []
    with httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        for aid, rec in records.items():
            out = IMAGE_DIR / f"{aid}.jpg"
            if out.exists() and not force:
                skipped += 1
                say(f"  ・{aid} 已經有了，跳過")
                continue
            try:
                url = image_url_for(rec, client)
                r = client.get(url)
                r.raise_for_status()
                data, size = to_jpeg(r.content)
                out.write_bytes(data)
                ok += 1
                say(f"  ✔ {aid} {rec['title']['zh']}：{size[0]}×{size[1]}，{len(data) // 1024} KB")
                time.sleep(0.5)                # 對博物館網站客氣一點，不要連續猛抓
            except Exception as e:             # 一筆失敗不影響其他筆
                failed.append(aid)
                reason = (str(e).splitlines() or [""])[0][:120]
                say(f"  ✘ {aid} {rec['title']['zh']}：{type(e).__name__}：{reason}")
    say("")
    say(f"結果：下載 {ok} 筆、跳過 {skipped} 筆、失敗 {len(failed)} 筆")
    if failed:
        say("失敗的編號：" + "、".join(failed) + "（可以再雙擊一次重試；還是失敗就告訴 Claude）")
    LOG_FILE.write_text("\n".join(LINES) + "\n", encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
