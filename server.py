"""
server.py：你的 MCP Server（櫃台）

對照《00_專案學習地圖.md》第 4 節 B 段：
  B1  Claude 讀這裡每個工具的「說明」（服務項目表），決定要用哪一個
  B2  Claude 透過 MCP（統一格式的點單）把請求送進來
  B3  交給 search.py 找資料
  B4  把結果＋出處＋授權傳回去，並在 logs/tool_calls.jsonl 記一行（登記簿）

提供的內容：
  工具 search_artworks   用描述找作品
  工具 get_artwork       一件作品的完整資料（含授權與標示文字）
  工具 search_passages   最相關的 3 段原文與出處（回答由 AI 寫）
  工具 list_artworks     列出全部作品
  資料 artworks://catalog   館藏清單
  範本 tour_script          導覽稿

重要：這個程式透過「標準輸入輸出」和 Claude 溝通，所以絕對不能用 print()，
     要記錄東西請用 log（寫到 logs/server.log）。

工具說明（每個 @mcp.tool 底下的 description）：階段 5 由 Door 改寫成自己的版本。
"""

from __future__ import annotations

import difflib
import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

import search

# ─────────────────────────────────────────────
# 紀錄：伺服器狀況寫進 logs/server.log；每次工具呼叫寫進 logs/tool_calls.jsonl
# ─────────────────────────────────────────────
LOG_DIR = search.ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    filename=LOG_DIR / "server.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("art-rag")
TOOL_LOG = LOG_DIR / "tool_calls.jsonl"


@contextmanager
def log_call(tool: str, args: dict):
    """包住每次工具呼叫：記下時間、工具、參數、花多久、成功與否、回傳幾筆。"""
    record = {"time": datetime.now().isoformat(timespec="seconds"), "tool": tool, "args": args}
    t0 = time.perf_counter()
    try:
        yield record
        record["ok"] = True
    except Exception as e:
        record["ok"] = False
        record["error"] = str(e)
        raise
    finally:
        record["ms"] = round((time.perf_counter() - t0) * 1000)
        with TOOL_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        log.info("tool=%s ok=%s ms=%s", tool, record.get("ok"), record["ms"])


# ─────────────────────────────────────────────
# 資料：作品資料直接讀 data/（不需要模型）；搜尋第一次用到時才載入
# ─────────────────────────────────────────────
ARTWORKS, PROBLEMS = search.load_artworks()
for p in PROBLEMS:
    log.warning("資料問題：%s", p)
log.info("啟動：讀到 %d 件作品", len(ARTWORKS))

_searcher: search.Searcher | None = None


def get_searcher() -> search.Searcher:
    global _searcher
    if _searcher is None:
        try:
            _searcher = search.Searcher()
        except search.IndexNotReady as e:
            raise ToolError(f"{e}。建好之後再問一次就可以了。") from e
    return _searcher


def stale_note(s: search.Searcher) -> dict:
    """資料改過卻沒重建索引時，在結果裡提醒。"""
    if s.stale:
        return {"warning": "data/ 的資料有更新，但索引還是舊的：請雙擊 build_index.bat 重建，再完全結束並重開 Claude。"}
    return {}


def check_query(query: str) -> str:
    query = (query or "").strip()
    if not query:
        raise ToolError("query 不能是空的：請放入要查的文字，例如「谿山行旅圖的落款在哪裡」。")
    if len(query) > 500:
        raise ToolError("query 太長了（超過 500 字）：請只放要查的重點。")
    return query


# ─────────────────────────────────────────────
# MCP Server 本體
# ─────────────────────────────────────────────
mcp = MCPServer(
    name="art-rag",
    instructions=(
        "這是藝術作品知識庫（含臺灣民間藝術），資料來自博物館開放授權典藏。"
        "回答作品相關問題時，請先用工具查資料，並在回答中附上工具回傳的出處網址與授權；"
        "工具說找不到時，請直接告訴使用者知識庫沒有這方面的資料，不要自行編造。"
    ),
)


@mcp.tool(description=(
    "用一段描述找出最相關的作品（以作品為單位，最多 5 件）。"
    "適合：使用者描述內容、題材、匠師、地點，但不知道作品名稱或編號時。"
    "找到之後，要看完整資料請用 get_artwork；要引用原文細節請用 search_passages。"
))
def search_artworks(query: str, limit: int = 5) -> dict:
    with log_call("search_artworks", {"query": query, "limit": limit}) as rec:
        query = check_query(query)
        limit = max(1, min(int(limit), 10))
        s = get_searcher()
        result = s.search_artworks(query, limit=limit)
        rec["n_results"] = len(result["results"])
        if not result["found"]:
            result["message"] = "知識庫裡沒有和這個描述夠相關的作品。可以用 list_artworks 看看收錄了哪些作品。"
        return {**result, **stale_note(s)}


@mcp.tool(description=(
    "用作品編號取得一件作品的完整資料：名稱、作者、年代、材質、尺寸、典藏單位、"
    "每一段介紹與其出處網址，以及授權與標示文字（引用或使用圖片時要照標示文字寫）。"
    "需要作品編號（例如 npm-000001）；不知道編號時，先用 list_artworks 或 search_artworks。"
))
def get_artwork(artwork_id: str) -> dict:
    with log_call("get_artwork", {"artwork_id": artwork_id}) as rec:
        art_id = (artwork_id or "").strip().lower()
        record = ARTWORKS.get(art_id)
        if record is None:
            close = difflib.get_close_matches(art_id, list(ARTWORKS), n=3, cutoff=0.5)
            hint = f"你是不是要找：{', '.join(close)}？" if close else ""
            raise ToolError(f"找不到編號「{artwork_id}」的作品。{hint}請先用 list_artworks 查正確的編號。")
        image = record["image"]
        descriptions = []
        for d in record["descriptions"]:
            reason = search.should_skip(d)
            if reason:
                continue                     # 未審核、沒有出處的段落不提供（和搜尋的規則一致）
            descriptions.append({
                "topic": d.get("topic", ""),
                "text": d["text"],
                "source_url": d["source_url"],
                "license": d["license"],
            })
        rec["n_results"] = 1
        return {
            "artwork_id": record["id"],
            "title": record["title"],
            "artist": record["artist"],
            "date_text": record["date_text"],
            "medium": record.get("medium", ""),
            "dimensions": record.get("dimensions", ""),
            "collection": record["collection"],
            "source_url": record["source_url"],
            "image_license": image["license"],
            "image_source_url": image.get("source_url", ""),
            "credit_line": image.get("attribution") or f"{record['collection']}，{image['license']}",
            "style_tags": record.get("style_tags", []),
            "descriptions": descriptions,
        }


@mcp.tool(description=(
    "依問題找出知識庫中最相關的原文段落（預設 3 段），每段附作品編號、出處網址與授權。"
    "適合：回答作品細節、技法、用途、題材故事、匠師或畫家生平等需要引用原文的問題；"
    "請根據回傳的段落回答，並附上每段的出處。found 為 false 時代表知識庫沒有相關資料，請直接說明，不要編造。"
    "只想知道收錄了哪些作品時，改用 list_artworks。"
))
def search_passages(query: str, top_k: int = 3) -> dict:
    with log_call("search_passages", {"query": query, "top_k": top_k}) as rec:
        query = check_query(query)
        top_k = max(1, min(int(top_k), 5))
        s = get_searcher()
        result = s.search(query, top_k=top_k)
        rec["n_results"] = len(result["results"])
        if not result["found"]:
            result["message"] = "知識庫裡沒有和這個問題夠相關的段落。請直接告訴使用者查不到，或用 list_artworks 看看收錄了哪些作品。"
        return {**result, **stale_note(s)}


@mcp.tool(description=(
    "列出知識庫收錄的全部作品（編號、名稱、作者、年代、典藏單位）。"
    "適合：使用者問「有哪些作品」，或其他工具需要作品編號但你還不知道時。"
))
def list_artworks() -> dict:
    with log_call("list_artworks", {}) as rec:
        items = [{
            "artwork_id": r["id"],
            "title": r["title"]["zh"],
            "artist": r["artist"]["zh"],
            "date_text": r["date_text"],
            "collection": r["collection"],
        } for r in ARTWORKS.values()]
        rec["n_results"] = len(items)
        return {"count": len(items), "artworks": items}


@mcp.resource("artworks://catalog", name="館藏清單", mime_type="text/markdown",
              description="知識庫收錄的全部作品清單（Markdown 表格）。")
def catalog() -> str:
    lines = ["# 館藏清單", "", "| 編號 | 名稱 | 作者 | 年代 | 典藏單位 |", "| --- | --- | --- | --- | --- |"]
    for r in ARTWORKS.values():
        lines.append(f"| {r['id']} | {r['title']['zh']} | {r['artist']['zh']} | {r['date_text']} | {r['collection']} |")
    return "\n".join(lines)


@mcp.prompt(name="tour_script", title="導覽稿",
            description="產生一份附出處的導覽稿。topic 填主題或作品，minutes 填講幾分鐘。")
def tour_script(topic: str, minutes: str = "5") -> str:
    return (
        f"請幫我寫一份大約 {minutes} 分鐘的導覽稿，主題是「{topic}」。\n"
        "寫作前請先用 search_artworks 找出相關作品，再用 search_passages 或 get_artwork 取得原文。\n"
        "要求：\n"
        "1. 只使用工具查到的內容，查不到的部分直接說明，不要自行補充或編造。\n"
        "2. 每一段結尾用括號附上出處（典藏單位與出處網址）。\n"
        "3. 語氣親切、口語，適合現場解說；最後附上「資料授權」小節，列出每件作品的授權與標示文字。"
    )


if __name__ == "__main__":
    log.info("MCP Server 開始等待 Claude 連線（stdio）")
    mcp.run()
