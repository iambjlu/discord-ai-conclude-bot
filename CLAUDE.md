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

# 專案規則

- 請使用中文（繁體）進行回應
- 做事之前先根據指令，列出 todo list再一步一步執行
- 如果我指出有發生問題，但是描述不夠清楚的話，則你先執行過一遍先了解問題，真的不了解才來問我詳細資訊


## 更動規範
在開始進行更動前，請先閱讀`Readme_Architecture.md`了解專案架構
如果真的找不到才用grep一個一個搜尋

在此專案中做任何更動（程式碼、設定、架構等），都必須：

1. 將變更內容同步更新到 `Readme_Architecture.md` （直接寫入對應程式檔所屬的章節裡面，不要獨立出來變成新章節，並且不要提及是何時的何計劃。）
2. 建立 git commit（原始更動 + Readme 更新一起 commit，或分開 commit 皆可）

此步驟不可省略。

## 完成後編譯與測試流程

每次任務完成後，必須執行：

- 說明有沒有需要重新編譯哪個程式、需不需要重新開
- 把有修改到的程式重新編譯，確認沒有發生錯誤。如果遇到該程序正在使用，則強制停止它然後再重新編譯
- 如果是參考md進行的任務，請在最後回頭檢視各項任務是否皆已確實完成或是有無新的任務(如有要求做完打✅，則先重新讀取有無新內容再打✅)

以上全部無誤才算完成
