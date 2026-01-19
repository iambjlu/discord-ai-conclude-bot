# Discord 訊息摘要與金句機器人

這是一個 Discord 機器人，專為學習社群設計。它具有以下核心功能：
1. **歷史熱門訊息摘要**：抓取指定頻道最近 X 小時的訊息，利用 Gemini AI 進行重點摘要，並發送到指定頻道。
2. **每日金句圖片**：每天自動統計前一天獲得最多表情反應（Reaction）的訊息，並透過 Playwright 自動渲染出一張精美的「每日金句」圖片戰報。
3. **網頁連結預覽**：自動偵測指定頻道中的 URL，呼叫 iOS 模擬器 (iPad) 開啟網頁並截圖，讓社群成員不必點開連結也能預覽內容。

---

## 🛠️ 安裝說明 (Installation)

### 1. 環境準備
此專案的部分功能（如 iOS 模擬器截圖）需要 **macOS** 環境與 **Xcode** 支援。
請確保您的環境包含：
*   **Python 3.8+**
*   **macOS** (若需使用連結截圖功能)
*   **Xcode Command Line Tools** (包含 simulator)

檢查 Python 版本：
```bash
python3 --version
```

### 2. 下載專案
將此專案下載到您的電腦中。

### 3. 安裝依賴套件
程式內建了自動檢查與安裝機制，但您也可以手動安裝：
```bash
pip install -r requirements.txt
playwright install  # 安裝 Playwright 瀏覽器核心
```
*必要的套件包含：`discord.py`, `google-genai`, `python-dotenv`, `playwright`, `pillow`*

### 4. 設定環境變數 (.env)
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

# 關鍵字觸發執行的指令 (可選)
DEPLOY_COMMAND=git pull && pm2 restart bot
```

---

## 🚀 如何執行 (Usage)

本專案包含兩個主要的 Python 執行檔，分別對應不同的運作模式：

### 1. 排程機器人 (`server.py`)
這是主要的**排程執行腳本**。設計上是讓系統定時觸發（例如透過 Cronjob 或 GitHub Actions），執行完任務後會**自動結束程式**。

*   **功能**：定期發送訊息摘要 (AI Summary)、每日金句 (Daily Quote)、連結預覽 (Link Screenshot)。
*   **執行方式**：
    ```bash
    python3 server.py
    ```
*   **運作邏輯**：
    1.  啟動並登入 Discord。
    2.  檢查現在時間是否符合 `AI_SUMMARY_SCHEDULE_MODULO` 或 `LINK_SCREENSHOT_SCHEDULE_MODULO` 的倍數小時。
    3.  檢查現在是否為午夜 (00:00) 以決定是否執行每日金句。
    4.  執行所有符合條件的任務。
    5.  任務完成後，程式自動關閉 (Exit)。
    *   *(若要在測試時強制執行所有功能，可將 `*_MODE` 設定改為 `2`)*

### 2. 對話機器人 (`tagged_reply.py`)
這是**互動式機器人**。需要**常駐執行 (Keep Alive)**，它會監聽頻道中的提及 (Mention) 並做出回應。

*   **功能**：當使用者 Tag 機器人時（例如 `@Bot 30` 或單純 `@Bot`），回覆該頻道最新的 30 則對話摘要與回應。
    *   若**回覆 (Reply)** 某則訊息並 Tag Bot，會自動包含該訊息前後一段時間的上下文。
    *   支援指定抓取數量，例如 `@Bot 50` 代表抓取最新 50 則。
*   **執行方式**：
    ```bash
    python3 tagged_reply.py
    ```
    *(請確保此程式在背景持續運作，例如使用 `nohup`, `tmux` 或 `Docker`)*

### 3. 發送公告 (`sender.py`)
這是**單次執行腳本**，用於手動發送公告或訊息至指定頻道。

*   **功能**：修改程式碼中的 `MESSAGE_TO_SEND` 變數文字，執行後會立即發送並結束。
*   **執行方式**：
    1.  開啟 `sender.py` 編輯 `MESSAGE_TO_SEND` 內容。
    2.  執行：
        ```bash
        python3 sender.py
        ```

---

## ⚙️ 進階設定 (Configuration)

您可以在 `server.py` 的 `get_settings()` 函式中調整變數。

### 功能開關 (Modes)
*   **`AI_SUMMARY_MODE`**: AI 摘要功能 (`0`: 關閉, `1`: 排程, `2`: 強制執行)
*   **`DAILY_QUOTE_MODE`**: 每日金句功能 (`0`: 關閉, `1`: 僅午夜執行, `2`: 強制執行)
*   **`DAILY_QUOTE_IMAGE_MODE`**: 金句圖片生成 (`0`: 關閉, `1`: 純文字, `2`: 產生圖片)
*   **`LINK_SCREENSHOT_MODE`**: 連結預覽功能 (`0`: 關閉, `1`: 排程, `2`: 強制執行)

### 排程與範圍 (Schedule & Ranges)
*   **`AI_SUMMARY_SCHEDULE_MODULO`**: AI 摘要的執行間隔小時數 (預設 `4`, 即 0, 4, 8... 點執行)。
*   **`LINK_SCREENSHOT_SCHEDULE_MODULO`**: 連結截圖的執行間隔小時數 (預設 `2`)。
*   **`RECENT_MSG_HOURS`**: AI 摘要要抓取「前幾小時」的訊息 (預設 `5`)。
*   **`LINK_SCREENSHOT_HOURS`**: 連結截圖要抓取「前幾小時」的連結 (預設 `3`)。
*   **`DAYS_AGO`**: 每日金句要統計「幾天前」的資料 (預設 `1` 代表昨天)。

### 內容顯示 (Display)
*   **`AUTHOR_NAME_LIMIT`**: 成員名稱顯示的最長字元數。
*   **`SHOW_DATE`**: 時間戳記是否顯示日期 (`True`/`False`)。
*   **`SHOW_SECONDS`**: 時間戳記是否顯示秒數。
*   **`SHOW_ATTACHMENTS`**: 是否顯示附件連結。
*   **`SIMPLIFY_LINKS`**: 是否將長連結簡化顯示 (例如只顯示網域或 Embed 標題)。
*   **`MINESWEEPER_ROWS`** / **`COLS`** / **`MINES`**: 摘要結尾附帶的踩地雷小遊戲設定。
*   **`BOT_NAME`**: 當機器人發言（包含 `ignore_token`）被讀取到時，替換成的顯示名稱（預設為 "Bot"）。

### Google Gemini AI 設定
*   **`GEMINI_TOKEN_LIMIT`**: AI 回應的最大 Token 數 (預設 `120000`)。
*   **`GEMINI_MODEL_PRIORITY_LIST`**: 優先使用的模型列表，會依序嘗試直到成功。
    *   範例: `["gemini-3-flash-preview", "gemma-3-27b-it", "gemma-3-12b-it", ...]`
*   **`IGNORE_TOKEN`**: 訊息截斷標記，若讀取到此符號，之後的內容會被忽略 (避免 Bot 讀到自己的摘要)。
*   **`GEMINI_SUMMARY_FORMAT`**: 給 AI 的 Prompt 模板，定義摘要的 Markdown 格式。
 
### 對話機器人 (tagged_reply.py) 設定
*   **`TOTAL_MSG_LIMIT`**: 訊息抓取總額度 (預設 `150`)。若有回覆參照，會自動分配給最新訊息與回覆上下文。
*   **`MAX_MSG_LENGTH`**: 單則訊息最大字數 (預設 `150`)，超過會被截斷，節省 Token。
*   **`TAGGED_REPLY_PROMPT_TEMPLATE`**: AI 回應的人設與 Prompt 模板。
*   **`ENABLE_EXEC_COMMAND`**: 是否開啟關鍵字執行指令功能 (`True`/`False`)。
*   **`EXEC_COMMAND_KEYWORD`**: 當被標註的訊息中包含此關鍵字時觸發執行（例如 `update_bot_now`）。
*   **`EXEC_COMMAND_ENV_NAME`**: 指定要從 `.env` 讀取的環境變數名稱，該變數儲存了實際執行的 Shell 指令。

這些變數會在程式啟動時讀取，若是 `tagged_reply.py` 則需要在修改後重新啟動 Bot 生效。

---

## ☁️ GitHub Actions 自動排程設定

本專案已包含 `.github/workflows/run_bot_link_preview.yml`，設定為每 4 小時執行一次（0, 4, 8, 12, 16, 20 時）。
若要啟用此功能，請在您的 GitHub Repository 完成以下設定：

1.  進入 Repo 的 **Settings**。
2.  在左側選單找到 **Secrets and variables** > **Actions**。
3.  點擊 **New repository secret**，依序新增以下四個變數（內容請參考您的 `.env` 檔案）：
    *   `DISCORD_BOT_TOKEN`
    *   `GEMINI_API_KEY`
    *   `SOURCE_CHANNEL_IDS`
    *   `TARGET_CHANNEL_ID`
4.  設定完成後，Actions 即可依照排程自動執行。您也可以在 Actions 頁面手動觸發測試。

---

## 📝 常見問題

**Q: 執行時出現 "ModuleNotFoundError"?**
A: 請確認您已執行 `pip install -r requirements.txt`，或確保網路連線正常讓程式自動安裝。

**Q: 機器人沒有反應？**
A: 請檢查 `.env` 中的 Token 是否正確，以及機器人是否有該頻道的「讀取訊息」與「發送訊息」權限。

**Q: Gemini 總結失敗？**
A: 請檢查 API Key 是否有效，以及 `gemini_model` 指定的模型名稱是否目前可用。
