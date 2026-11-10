# 專案架構

## 總覽
Discord 機器人，專為學習社群（StudentCrew）設計，結合 AI 摘要、自動化截圖、天氣預報等功能，包成 macOS 選單列 App（`DiscordBot.app`）。App 用 Swift 管理兩個 Python 行程：
常駐的 `tagged_reply.py` 與定時執行、跑完自動結束的 `server.py`。環境變數放在 `.env`（API keys、頻道 IDs 等，不進 git；App 版改用 iCloud 的 `bot.env`），修改後需重新啟動 bot。

直接執行（不經 App）：
```bash
.venv/bin/python3 server.py        # 排程機器人（執行完自動結束）
.venv/bin/python3 tagged_reply.py  # 對話機器人（需常駐）
```

## Python 腳本

### `server.py`（排程任務）
登入 Discord，依 `get_settings()` 的各 `*_MODE`／`*_SCHEDULE_MODULO` 執行各項任務後結束。
- 主要函數：`run_ai_summary()`（抓頻道最近 X 小時訊息，Gemini 摘要）、`run_daily_quote()`（統計昨天最多反應的訊息並渲染金句圖）、`run_daily_ai_summary()`（每日摘要彙整）、`run_link_screenshot()`（抓頻道中的 URL，用 iPad 模擬器截圖）、`run_weather_forecast()`（抓 CWA 天氣資料，生成各地區天氣卡）、`generate_choice_solver()`（選擇困難建議）、`generate_minesweeper()`（踩地雷小遊戲）。
- 排程設定（`get_settings`）：`AI_SUMMARY_SCHEDULE_MODULO`（AI 摘要間隔，預設每 4 小時）；`DAILY_QUOTE_MODE`、`LINK_SCREENSHOT_MODE`、`WEATHER_MODE`、`AI_SUMMARY_MODE`（0 關閉、1 排程、2 強制）。
- Playwright 瀏覽器路徑：`os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", <專案>/browsers)`，避免被系統 cache 清理；安裝命令 `PLAYWRIGHT_BROWSERS_PATH=browsers python -m playwright install chromium`。
- 連結截圖需要 macOS + Xcode（iOS 模擬器），用 `xcrun simctl` 的 iPad 模擬器截圖；截圖暫存檔寫入系統暫存資料夾（`tempfile.gettempdir()`，檔名含 pid 避免衝突），送出後立即刪除，不會寫進 App 內部。

### `renderer.py`（圖片渲染）
用 Playwright 把 HTML 範本渲染成圖片（金句戰報、天氣卡），結果以記憶體 buffer 回傳，不落地成檔案；依賴 `browsers/` 內的 Chromium。
- 瀏覽器由 `launch_browser()` 選擇：環境變數 `BOT_BROWSER`（`chrome`／`edge`／`brave`／`chromium` 或執行檔完整路徑）指定，未設定則依序自動偵測 Chrome → Edge → Brave，都沒有才用 Playwright 的 Chromium。
- 啟動瀏覽器時帶 `LEAN_CHROMIUM_ARGS`（關閉磁碟快取、當機回報、背景網路與同步），並使用 `new_context()`（無痕，Cookies／歷史只在記憶體），以減少硬碟寫入。

### `tagged_reply.py`（對話機器人）
常駐，監聽 @Bot 提及並回覆；不寫暫存檔。

### 其他
`hello_msg.py`（系統資訊推播）、`get_message.py`、`tcc.py`、`sender/`、`split_long_image/`、`image_reg/`。

## Swift App（`app/`）

### `BotRunner.swift`
管理一個 Python 子行程（啟動、停止、常駐型當掉自動重啟、一次性逾時）並收集日誌。
- 日誌預設只保留在記憶體（最近 1000 行）。
- 「把日誌寫入硬碟」開啟（UserDefaults `logToDisk`）時才寫入 `~/Library/Logs/DiscordAIConcludeBot/<id>.log`：檔案持續開著寫入、以位元組計數判斷超過 5 MB 輪替；關閉時不建立資料夾也不開檔。

### `AppModel.swift`
兩個 `BotRunner` 的總管、排程計時（每 30 秒檢查）、`bot.env` 讀寫、偏好設定（UserDefaults，含 `logToDisk`）。

### `Views.swift`
主視窗：狀態、設定（含「把日誌寫入硬碟」開關）、日誌、設定檔分頁。

### `EnvStore.swift`
`bot.env` 放在 iCloud Drive（`DiscordAIConcludeBot/bot.env`），換電腦登入 iCloud 即可讀到。

### `DiscordBotApp.swift`、`make_icon.swift`
App 進入點與選單列、圖示產生。

### `core_run.sh` / `launch.py`（打包進 App 的 `core/`）
`run.sh` 在 `~/Library/Application Support/DiscordAIConcludeBot` 建立 venv、安裝套件；Chromium 的來源依序為：App 內附的 `browsers/`、系統已安裝的 Chrome／Edge／Brave（`renderer.py` 優先使用，此時不下載）、否則首次下載到 Application Support；設定 `PYTHONDONTWRITEBYTECODE=1` 避免寫入位元碼。`launch.py` 載入 iCloud 的 `bot.env` 後執行指定腳本。

## 打包
`./build_app.sh` 以 `swiftc` 編譯並組出 `build/DiscordBot.app`（目前機器架構、macOS 14+、ad-hoc 簽章）。
預設不內附瀏覽器，App 約 1 MB；`BUNDLE_BROWSERS=1 ./build_app.sh` 才會把 `browsers/` 一起內附（約多 500 MB，免首次下載）。

## 搬家需求
目標機需有 Python 3.11 以上、登入同一個 iCloud、對 App 執行 `xattr -cr` 解除 Gatekeeper；CPU 架構不同需重新打包；連結截圖另需 Xcode 與 iPad 模擬器。
