# art-mcp：讓 AI 助理查得到臺灣民間藝術的 MCP Server

> 狀態：開發中（2026-10-23 建立）。這份 README 會在階段 8 改寫成正式版。

## 這是什麼

一個 MCP Server：接上 Claude 桌面版之後，Claude 回答藝術作品的問題時，會先來這裡查資料，再附上博物館出處回答。
搜尋用的是一個小型中文向量模型（BAAI/bge-small-zh-v1.5），在一般筆電就能跑，不需要顯示卡。

白話的完整說明在「專題大決戰」資料夾的 `00_專案學習地圖.md`。

## 檔案一覽

| 檔案 | 用途 | 對照學習地圖 |
| --- | --- | --- |
| `setup.bat` | 雙擊安裝環境（uv、Python 3.12、固定版本的套件），全部裝在這個資料夾裡 | 階段 2 |
| `hello_server.py` | 最小測試工具，只用來確認 Claude 連得到 | 階段 2 |
| `check_env.py` | 檢查環境，並產生要貼進 Claude 的設定檔 | 階段 2 |
| `data/artworks/*.json` | 作品資料（格式和小組 `kb/artworks/` 相同） | A1 |
| `data/images/*.jpg` | 作品圖片 | A1 |
| `data/keywords.txt` | 關鍵字加分用的名字清單（可以自己加） | 4-3 |
| `search.py` | 切段、向量化、搜尋、關鍵字加分 | A2～A4、B3 |
| `build_index.py`／`.bat` | 雙擊建立索引（第一次會下載模型） | A2～A4 |
| `server.py` | MCP Server：4 個工具、館藏清單、導覽稿範本、工具呼叫紀錄 | B1～B5 |
| `test_search.py`／`.bat` | 搜尋小測驗：比較有加分和沒加分的 Top-3 命中率 | 階段 4 |
| `self_check.py`／`.bat` | 健康檢查：一次測試資料、搜尋、MCP 連線與每個工具 | 全部 |
| `eval/` | 測驗題目與結果 | 階段 4、6 |
| `logs/` | `tool_calls.jsonl`（每次工具呼叫）、`server.log`（Server 狀況） | B4 |

執行後才會出現（不放進 Git）：`.tools/`（uv 和 Python）、`.venv/`（套件）、`models/`（向量模型）、`index/`（索引）。

## 使用順序

1. 雙擊 `setup.bat`
2. 把 `claude_config_step1_hello.json` 的內容放進 Claude 桌面版設定，**完全結束** Claude 再開，請它「用 hello 工具」
3. 雙擊 `build_index.bat`（第一次會下載模型）
4. 雙擊 `self_check.bat`，全部通過
5. 換成 `claude_config_step2_full.json` 的設定，完全結束 Claude 再開，開始問問題

## 目前的資料

`data/` 現在放的是小組知識庫原本的 3 幅名畫（谿山行旅圖、有絲柏的麥田、大碗島的星期天下午），先拿來測試整條流程；
階段 3 會加入 20 件臺灣民間藝術（12 件版印、8 件交趾陶剪黏）。

## 設計決定（摘要）

- **Server 只找資料、不寫回答**：寫回答交給 AI，Server 專心把資料和出處找對。
- **沒有官方出處網址、或標示「未審核」的段落不收**：例如小組資料裡的觀眾留言，避免來路不明的內容混進 AI 的回答。
- **關鍵字加分**：向量模型對人名、廟名不敏感，名字一字不差對上時加 0.05 分（最多 0.10）。
- **找不到就說找不到**：第 1 名分數低於門檻（暫定 0.45，階段 4 校正）時回傳 found=false。
- **模型在第一次搜尋時才載入**：讓 Claude 連線時 Server 能很快啟動。

## 授權

資料授權照每筆資料的 `license` 與 `attribution` 欄位；程式碼授權待定。
