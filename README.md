# Discord 訊息摘要與金句機器人

這是一個 Discord 機器人，專為學習社群設計。它具有以下核心功能：
1. **歷史熱門訊息摘要**：抓取指定頻道最近 X 小時的訊息，利用 Gemini AI 進行重點摘要，並發送到指定頻道。
2. **每日金句圖片**：每天自動統計前一天獲得最多表情反應（Reaction）的訊息，並透過 Playwright 自動渲染出一張精美的「每日金句」圖片戰報。
3. **網頁連結預覽**：自動偵測指定頻道中的 URL，呼叫 iOS 模擬器 (iPad) 開啟網頁並截圖，讓社群成員不必點開連結也能預覽內容。
4. **天氣預報卡片**：定時抓取中央氣象署 (CWA) 資料，生成精美的台灣各地區天氣預報卡片（包含溫度、降雨機率、舒適度）。
5. **圖片辨識與分析**：使用 `/辨識圖片` 指令，讓 AI 辨識並描述訊息中的圖片內容。可搭配 `/聰明模型` 使用更強大的多模態模型。

本專案有兩種使用方式：**🐍 Python 版**（直接執行腳本）與 **🖥️ macOS 選單列 App**（把同一套程式包成 App，圖形介面管理）。

## 🐍 Python 版（直接執行腳本）

不使用 App，直接在終端機、Cronjob、Docker 或 GitHub Actions 執行 Python 腳本。

### 🛠️ 安裝說明 (Installation)

#### 1. 環境準備
此專案的部分功能（如 iOS 模擬器截圖）需要 **macOS** 環境與 **Xcode** 支援。
請確保您的環境包含：
*   **Python 3.8+**
*   **macOS** (若需使用連結截圖功能)
*   **Xcode Command Line Tools** (包含 simulator)

檢查 Python 版本：
```bash
python3 --version
```

#### 2. 下載專案
將此專案下載到您的電腦中。

#### 3. 安裝依賴套件
程式內建了自動檢查與安裝機制，但您也可以手動安裝：
```bash
pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH=browsers python -m playwright install chromium  # 安裝 Playwright 瀏覽器（存於專案目錄，避免被 cache 清理）
```
*必要的套件包含：`discord.py`, `google-genai`, `python-dotenv`, `playwright`, `pillow`*

#### 4. 設定環境變數 (.env)
在專案根目錄下建立一個名為 `.env` 的檔案（如果是 Mac/Linux，請注意檔案名稱開頭有點）。
**請複製以下內容並填入您的真實資料**：

```ini
# Discord Bot Token (請至 Discord Developer Portal 取得)
DISCORD_BOT_TOKEN=你的_DISCORD_BOT_TOKEN

# Gemini AI API Key (請至 Google AI Studio 取得)
GEMINI_API_KEY=你的_GEMINI_API_KEY

# 來源頻道 ID 列表 (要掃描的頻道，用逗號分隔)
SOURCE_CHANNEL_IDS=123456789012345678,987654321098765432

# 目標頻道 ID (要發送摘要和戰報的頻道)
TARGET_CHANNEL_ID=112233445566778899

# 連結預覽的頻道ID
TARGET_PREVIEW_ID=112233445566778899

# 天氣預報的頻道ID (可選，若未設定則使用 TARGET_CHANNEL_ID)
TARGET_WEATHER_ID=112233445566778899

# 中央氣象署 OpenData API Key (請至 CWA 開放資料平台取得)
WEATHER_KEY=你的_CWA_API_KEY

# 關鍵字觸發執行的指令 (可選)
DEPLOY_COMMAND=git pull && pm2 restart bot

# 額外的本地 AI 伺服器設定 (可選，若要使用額外本地化模型)
LOCAL_AI_ENABLED=true
LOCAL_AI_SERVER=http://172.20.10.3:8000/v1
LOCAL_AI_MODEL=Qwen3.6-35B-A3B-6bit
LOCAL_AI_API_KEY=0000
LOCAL_AI_IMAGE_SUPPORT=true
```

---

### 🚀 如何執行 (Usage)

本專案包含兩個主要的 Python 執行檔，分別對應不同的運作模式：

#### 1. 排程機器人 (`server.py`)
這是主要的**排程執行腳本**。設計上是讓系統定時觸發（例如透過 Cronjob 或 GitHub Actions），執行完任務後會**自動結束程式**。

*   **功能**：定期發送訊息摘要 (AI Summary)、每日金句 (Daily Quote)、連結預覽 (Link Screenshot)、天氣預報 (Weather Forecast)。
*   **執行方式**：
    ```bash
    python3 server.py
    ```
*   **運作邏輯**：
    1.  啟動並登入 Discord。
    2.  檢查現在時間是否符合 `AI_SUMMARY_SCHEDULE_MODULO`、`LINK_SCREENSHOT_SCHEDULE_MODULO` 或 `WEATHER_SCHEDULE_MODULO` 的倍數小時。
    3.  檢查現在是否為午夜 (00:00) 以決定是否執行每日金句。
    4.  執行所有符合條件的任務。
    5.  任務完成後，程式自動關閉 (Exit)。
    *   *(若要在測試時強制執行所有功能，可將 `*_MODE` 設定改為 `2`)*

#### 2. 對話機器人 (`tagged_reply.py`)
這是**互動式機器人**。需要**常駐執行 (Keep Alive)**，它會監聽頻道中的提及 (Mention) 並做出回應。

*   **執行方式**：
    ```bash
    python3 tagged_reply.py
    ```
    *(請確保此程式在背景持續運作，例如使用 `nohup`, `tmux` 或 `Docker`)*

    #### ✨ 圖片辨識功能 (Image Recognition)
    *   **指令**：`/辨識圖片`
    *   **用法**：
        1.  **直接上傳**：上傳圖片時，在訊息內寫入 `/辨識圖片 [你的Prompt]`。
        2.  **回覆圖片**：對著別人發的圖片訊息，回覆 `/辨識圖片 [你的Prompt]`。
        3.  **搭配聰明模型**：加入 `/聰明模型` 關鍵字（例如 `/辨識圖片 /聰明模型 詳細分析這張圖`），可切換至更強大的 Gemini 多模態模型以獲得更精準的分析結果。


#### 3. 發送公告 (`sender.py`)
這是**單次執行腳本**，用於手動發送公告或訊息至指定頻道。

*   **功能**：修改程式碼中的 `MESSAGE_TO_SEND` 變數文字，執行後會立即發送並結束。
*   **執行方式**：
    1.  開啟 `sender.py` 編輯 `MESSAGE_TO_SEND` 內容。
    2.  執行：
        ```bash
        python3 sender.py
        ```

---

### ⚙️ 進階設定 (Configuration)

您可以在 `server.py` 的 `get_settings()` 函式中調整變數。

#### 功能開關 (Modes)
*   **`AI_SUMMARY_MODE`**: AI 摘要功能 (`0`: 關閉, `1`: 排程, `2`: 強制執行)
*   **`DAILY_QUOTE_MODE`**: 每日金句功能 (`0`: 關閉, `1`: 僅午夜執行, `2`: 強制執行)
*   **`DAILY_QUOTE_IMAGE_MODE`**: 金句圖片生成 (`0`: 關閉, `1`/`2`: 啟用)
*   **`LINK_SCREENSHOT_MODE`**: 連結預覽功能 (`0`: 關閉, `1`: 排程, `2`: 強制執行)
*   **`WEATHER_MODE`**: 天氣預報功能 (`0`: 關閉, `1`: 排程, `2`: 強制執行)

#### 排程與範圍 (Schedule & Ranges)
*   **`AI_SUMMARY_SCHEDULE_MODULO`**: AI 摘要的執行間隔小時數 (預設 `4`, 即 0, 4, 8... 點執行)。
*   **`LINK_SCREENSHOT_SCHEDULE_MODULO`**: 連結截圖的執行間隔小時數 (預設 `2`)。
*   **`WEATHER_SCHEDULE_MODULO`**: 天氣預報的執行間隔小時數 (預設 `4`, 即 0, 4, 8... 點執行)。
*   **`SCHEDULE_DELAY_TOLERANCE`**: 允許排程執行的延遲寬容度 (單位: 小時，預設 `1`)，用於應對 GitHub Actions 可能的排隊延遲。
*   **`RECENT_MSG_HOURS`**: AI 摘要要抓取「前幾小時」的訊息 (預設 `5`)。
*   **`LINK_SCREENSHOT_HOURS`**: 連結截圖要抓取「前幾小時」的連結 (預設 `3`)。
*   **`DAYS_AGO`**: 每日金句要統計「幾天前」的資料 (預設 `1` 代表昨天)。
*   **`WEATHER_COUNTIES`**: 要抓取天氣預報的縣市列表。

#### 內容顯示 (Display)
*   **`AUTHOR_NAME_LIMIT`**: 成員名稱顯示的最長字元數。
*   **`SHOW_DATE`**: 時間戳記是否顯示日期 (`True`/`False`)。
*   **`SHOW_SECONDS`**: 時間戳記是否顯示秒數。
*   **`SHOW_ATTACHMENTS`**: 是否顯示附件連結。
*   **`SIMPLIFY_LINKS`**: 是否將長連結簡化顯示 (例如只顯示網域或 Embed 標題)。
*   **`MINESWEEPER_ROWS`** / **`COLS`** / **`MINES`**: 摘要結尾附帶的踩地雷小遊戲設定。
*   **`BOT_NAME`**: 當機器人發言（包含 `ignore_token`）被讀取到時，替換成的顯示名稱（預設為 "Bot"）。

#### Google Gemini AI 設定
*   **`GEMINI_TOKEN_LIMIT`**: AI 回應的最大 Token 數 (預設 `120000`)。
*   **`GEMINI_MODEL_PRIORITY_LIST`**: 優先使用的模型列表，會依序嘗試直到成功。
    *   範例: `["gemini-3.5-flash", "gemma-4-31b-it", "gemma-3-12b-it", ...]`
*   **`IGNORE_TOKEN`**: 訊息截斷標記，若讀取到此符號，之後的內容會被忽略 (避免 Bot 讀到自己的摘要)。
*   **`GEMINI_SUMMARY_FORMAT`**: 給 AI 的 Prompt 模板，定義摘要的 Markdown 格式。
 
#### 對話機器人 (tagged_reply.py) 設定
*   **`TOTAL_MSG_LIMIT`**: 訊息抓取總額度 (預設 `50`)。若有回覆參照，會自動分配給最新訊息與回覆上下文。
*   **`MAX_MSG_LENGTH`**: 單則訊息最大字數 (預設 `100`)，超過會被截斷，節省 Token。
*   **`TAGGED_REPLY_PROMPT_TEMPLATE`**: AI 回應的人設與 Prompt 模板。
*   **`ENABLE_EXEC_COMMAND`**: 是否開啟關鍵字執行指令功能 (`True`/`False`)。
*   **`EXEC_COMMAND_KEYWORD`**: 當被標註的訊息中包含此關鍵字時觸發執行（例如 `update_bot`），將執行 `git pull` 並重啟。
*   **`SMARTER_MODE_KEYWORD`**: 觸發「聰明模式」的關鍵字 (預設 `/聰明模型`)，機器人將切換至更強大的模型 (如 Gemini 2.5 Flash) 並大幅提升 Token 上限。
*   **`SMARTER_TOKEN_LIMIT`**: 聰明模式下的 Token 上限 (預設 `120000`)。
*   **`SMARTER_TOTAL_MSG_LIMIT`**: 聰明模式下的訊息抓取總額度 (預設 `100`)。

這些變數會在程式啟動時讀取，若是 `tagged_reply.py` 則需要在修改後重新啟動 Bot 生效。

---

### ☁️ GitHub Actions 自動排程設定

本專案已包含 `.github/workflows/run_bot_link_preview.yml`，設定為每 4 小時執行一次（0, 4, 8, 12, 16, 20 時）。
若要啟用此功能，請在您的 GitHub Repository 完成以下設定：

1.  進入 Repo 的 **Settings**。
2.  在左側選單找到 **Secrets and variables** > **Actions**。
3.  點擊 **New repository secret**，依序新增以下四個變數（內容請參考您的 `.env` 檔案）：
    *   `DISCORD_BOT_TOKEN`
    *   `GEMINI_API_KEY`
    *   `SOURCE_CHANNEL_IDS`
    *   `TARGET_CHANNEL_ID`
    *   `WEATHER_KEY` (若要啟用天氣功能)
    *   `TARGET_WEATHER_ID` (可選)
4.  設定完成後，Actions 即可依照排程自動執行。您也可以在 Actions 頁面手動觸發測試。

#### 自動排程與強制執行邏輯
在 GitHub Actions 環境中 (`GITHUB_ACTIONS=true`)，程式會自動調整運作模式：

1.  **預設排程模式**：
    *   若沒有設定任何強制執行變數，所有功能 (`AI_SUMMARY`, `DAILY_QUOTE`, `LINK_SCREENSHOT`, `WEATHER`) 都會自動設為 **Mode 1 (排程模式)**。
    *   程式會檢查當前時間是否符合設定的 `SCHEDULE_MODULO` (執行頻率) 與 `SCHEDULE_DELAY_TOLERANCE` (寬容度)。

2.  **手動強制執行 (Workflow Dispatch)**：
    *   若您在 Actions 手動觸發時設定了以下任一環境變數為 `true`，程式將進入「強制執行模式」：
        *   `FORCE_AI_SUMMARY`: 強制執行 AI 摘要
        *   `FORCE_DAILY_QUOTE`: 強制執行 每日金句
        *   `FORCE_LINK_SCREENSHOT`: 強制執行 連結截圖
        *   `FORCE_WEATHER_FORECAST`: 強制執行 天氣預報
    *   **注意**：一旦啟用任一強制開關，其餘未被開啟的功能將會自動 **停用 (Mode 0)**，僅執行您指定的任務。這非常適合用於測試特定功能或補跑任務。

---

### 📝 常見問題

**Q: 執行時出現 "ModuleNotFoundError"?**
A: 請確認您已執行 `pip install -r requirements.txt`，或確保網路連線正常讓程式自動安裝。

**Q: 機器人沒有反應？**
A: 請檢查 `.env` 中的 Token 是否正確，以及機器人是否有該頻道的「讀取訊息」與「發送訊息」權限。

**Q: Gemini 總結失敗？**
A: 請檢查 API Key 是否有效，以及 `gemini_model` 指定的模型名稱是否目前可用。

---

## 🖥️ macOS 選單列 App

把上面的兩個 Python 程式包成一個 macOS 選單列 App（`DiscordBot.app`）：不用開終端機，由 App 幫你啟動、監看、自動重啟，並依排程定時執行。App 本體只有約 1 MB，Python 環境與瀏覽器在第一次啟動時才建立。

### 它做了什麼
*   **標注回覆**（常駐）：App 開啟時自動啟動，當掉會自動重啟（間隔逐次拉長，最長 60 秒）。
*   **排程任務**（定時）：依設定的間隔（預設每 2 小時、整點後第 3 分鐘）執行，跑完自動結束，超過 45 分鐘會被強制結束。每一輪實際會做哪些功能，仍由程式內各 `*_MODE`／`*_SCHEDULE_MODULO` 決定。
    *   App 剛開啟時視為「這一輪已處理」，不會一開就跑；電腦睡眠醒來後，最多補跑 90 分鐘內錯過的那一輪。
    *   手動「立即執行」或「強制執行」前會連續確認兩次，避免誤在頻道發訊息。
*   **設定檔放在 iCloud**：`iCloud Drive/DiscordAIConcludeBot/bot.env`，內容與上面 `.env` 相同（檔名不以「.」開頭，iCloud 才會同步）。換電腦登入同一個 iCloud 就讀得到。可在主視窗的「設定檔」分頁直接編輯，存檔時若標注回覆在跑會自動重啟讓設定生效。

### 需求
*   macOS 14 以上。
*   Python 3.11 以上（例如 `brew install python`）。第一次啟動會在 `~/Library/Application Support/DiscordAIConcludeBot` 建立 venv 並安裝套件（需連網，約 1～3 分鐘），之後不用再裝。
*   一個可用來渲染圖片的瀏覽器：已安裝 Chrome、Edge 或 Brave 就直接使用；都沒有才會下載 Playwright 的 Chromium（約 150 MB，一次）。
*   連結截圖功能另需 Xcode 與 iPad 模擬器；沒有的話只有這個功能不能用。

### 打包與安裝
```bash
./build_app.sh                      # 產生 build/DiscordBot.app（約 1 MB）
BUNDLE_BROWSERS=1 ./build_app.sh    # 連 Chromium 一起內附（約多 500 MB，免首次下載）
```
*   打包使用 `swiftc`（不需開 Xcode）；用 Xcode 27 的 macOS 27 SDK 連結，部署目標為 macOS 14。架構與打包的那台機器相同。
*   App 為臨時簽章。搬到其他 Mac 後若被 Gatekeeper 擋下，執行 `xattr -cr DiscordBot.app`。
*   要手動刪除 App 下載的 Chromium：退出 App 後 `rm -rf ~/Library/Application\ Support/DiscordAIConcludeBot/browsers`（刪之前確認有 Chrome／Edge／Brave，否則下次啟動會再下載）。

### 選單列狀態圖示

App 以選單列圖示顯示目前狀態（由上往下判斷，符合第一個就採用）：

| 圖示 | SF Symbol | 狀態 |
|:---:|---|---|
| <img src="docs/icons/ellipsis.bubble.fill.png" width="48"> | `ellipsis.bubble.fill` | 正在啟動（標注回覆尚未登入 Discord，或當掉後等待自動重啟） |
| <img src="docs/icons/text.bubble.badge.sparkles.fill.png" width="48"> | `text.bubble.badge.sparkles.fill` | 正在工作（執行排程任務，或正在回覆被提及的訊息） |
| <img src="docs/icons/text.bubble.badge.clock.png" width="48"> | `text.bubble.badge.clock` | 已設定排程、閒置中，未開啟標注回覆 |
| <img src="docs/icons/text.bubble.badge.clock.fill.png" width="48"> | `text.bubble.badge.clock.fill` | 已設定排程、閒置中，已開啟標注回覆 |
| <img src="docs/icons/text.bubble.fill.png" width="48"> | `text.bubble.fill` | 未設定排程，已開啟標注回覆 |
| <img src="docs/icons/text.bubble.png" width="48"> | `text.bubble` | 都沒開 |

### 設定頁
*   **渲染圖片的瀏覽器**：下拉選單可選 自動／Chrome／Edge／Brave／內建 Chromium，未安裝的會標示。選「自動」時依序偵測 Chrome → Edge → Brave → 內建 Chromium。下次執行排程任務時生效；也可在 `bot.env` 以 `BOT_BROWSER` 指定（App 的選擇優先）。
*   **日誌頁最多保留**：0／100／300／500／1000／3000 行（預設 500），存在記憶體裡，調小會立刻裁掉舊的。
*   **把日誌寫入硬碟**：預設關閉。開啟後寫入 `~/Library/Logs/DiscordAIConcludeBot/`，超過 5 MB 會輪替。
*   **權限**：重新要求權限、開啟系統設定的區域網路頁。
*   開機自動啟動、開啟 App 時是否顯示主視窗、排程間隔與分鐘。

### 權限
連到區域網路上的本地 AI 服務（`LOCAL_AI_SERVER`）需要「區域網路」權限，讀取 `bot.env` 需要 iCloud Drive 存取。App 在**第一次開啟、或重新打包後第一次開啟**時，會主動把這些權限要過一遍。臨時簽章每次打包身分都會改變，macOS 會重新詢問，所以重新打包後要再按一次「允許」。Python 的區網連線算在 App 頭上，App 取得權限後 bot 就能連線。

### 省電與少寫硬碟
*   **日誌預設只放記憶體**，不寫 SSD；Python 位元碼也不寫（`PYTHONDONTWRITEBYTECODE`）。
*   **Chromium**：使用無痕 context，並關閉磁碟快取、當機回報、背景網路與同步，圖片以記憶體傳給 Discord，不存成檔。
*   **待命記憶體**：`google-genai`、`openai` 延遲到第一次需要才載入；Discord 訊息快取只留 100 則、不快取成員；處理完訊息安靜 60 秒後才釋放一次記憶體。選單列展開時會顯示 App 與子行程的記憶體用量（與活動監視器相同的算法）。
*   **待命喚醒**：App 的排程檢查每 60 秒一次並放寬容許誤差，讓系統合併喚醒；完全閒置時 Python 端沒有任何定時工作。

### 本地模型
`LOCAL_AI_ENABLED=false` 可一鍵停用本地模型（`LOCAL_AI_SERVER`／`LOCAL_AI_MODEL` 會被忽略）。有人使用 `/本地模型` 時，bot 會分開回報原因：已停用、未設定、初始化失敗（附錯誤內容）；連線逾時這類呼叫時的錯誤則由「模型發生錯誤」訊息回報。

### 常見問題（App）
**Q: bot 連不到區網的本地 AI？**
A: 到「系統設定 › 隱私權與安全性 › 區域網路」確認 Discord AI Bot 已允許；重新打包後權限會被重置，需再允許一次。

**Q: 打開 App 沒反應或被擋？**
A: 對 App 執行 `xattr -cr DiscordBot.app`，再開啟。

**Q: 日誌頁看不到內容？**
A: 確認設定頁的「日誌頁最多保留」不是 0。日誌預設不寫硬碟，結束 App 就消失。
