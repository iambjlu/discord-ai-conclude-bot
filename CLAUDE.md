# Discord AI Conclude Bot — CLAUDE.md

## 專案概述
這是一個 Discord 機器人，專為學習社群（StudentCrew）設計。結合 AI 摘要、自動化截圖、天氣預報等實用工能。

## 核心檔案
- **`server.py`** — 排程執行腳本。啟動後登入 Discord，按時間表執行任務後自動結束。
- **`renderer.py`** — 圖片渲染模組。使用 Playwright 截圖渲染 HTML 模板，生成金句戰報與天氣卡片。
- **`tagged_reply.py`** — 對話機器人。需要常駐執行，監聽 @Bot 提及並回覆。
- **`.env`** — 環境變數（API keys、頻道 IDs 等）。

## Playwright 瀏覽器
- 瀏覽器二進位檔位於專案根目錄的 `browsers/` 資料夾
- 透過 `PLAYWRIGHT_BROWSERS_PATH` 環境變數設定，避免被系統 cache 清理
- `server.py` 第 61 行：`os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(__file__).parent / "browsers"))`
- 安裝命令：`PLAYWRIGHT_BROWSERS_PATH=browsers python -m playwright install chromium`

## 主要功能與函數
- `run_ai_summary()` — 抓取頻道最近 X 小時的訊息，Gemini AI 摘要
- `run_daily_quote()` — 統計昨天最多反應的訊息，渲染金句圖片
- `run_daily_ai_summary()` — 每日 AI 摘要
- `run_link_screenshot()` — 抓取頻道中的 URL，用 iPad 模擬器截圖
- `run_weather_forecast()` — 抓取 CWA 天氣資料，生成各地區天氣卡片
- `generate_choice_solver()` — 為選擇困難用戶生成選擇建議
- `generate_minesweeper()` — 生成踩地雷小遊戲

## 排程設定 (get_settings)
- `AI_SUMMARY_SCHEDULE_MODULO` — AI 摘要執行間隔（預設每 4 小時）
- `DAILY_QUOTE_MODE` — 每日金句（0: 關閉, 1: 午夜執行, 2: 強制）
- `LINK_SCREENSHOT_MODE` — 連結截圖（0: 關閉, 1: 排程, 2: 強制）
- `WEATHER_MODE` — 天氣預報（0: 關閉, 1: 排程, 2: 強制）
- `AI_SUMMARY_MODE` — AI 摘要（0: 關閉, 1: 排程, 2: 強制）

## 執行方式
```bash
# 排程機器人（執行完自動結束）
.venv/bin/python3 server.py

# 對話機器人（需常駐）
.venv/bin/python3 tagged_reply.py
```

## 注意事項
- 連結截圖功能需要 macOS + Xcode（iOS 模擬器）
- 此專案部分功能（天氣預報、金句圖片）依賴 Playwright 渲染，確保 `browsers/` 存在
- `.env` 不記錄在 git 中
- 修改 `.env` 後需重新啟動 bot
