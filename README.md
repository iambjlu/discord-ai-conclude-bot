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
```

---

## 🚀 如何執行 (Usage)

直接執行 Python 腳本即可啟動機器人：

```bash
python3 server.py
```

### 啟動流程：
1. 程式會自動檢查是否已安裝必要套件，若缺少會嘗試自動安裝。
2. 載入 `.env` 設定檔。
3. 機器人登入 Discord。
4. **立即執行**：「最近 X 小時訊息摘要」功能。
5. **排程執行**：若現在時間接近午夜 (00:00 - 00:10)，會執行「每日金句」統計；否則會顯示非執行時段並結束（視 `zero_clock_only` 設定而定）。

---

## ⚙️ 進階設定 (Configuration)

您可以在 `server.py` 程式碼中找到 `MyClient.on_ready` 方法內的設定區塊進行微調：

*   `recent_msg_hours = 4`: 設定摘要功能要抓取最近幾小時的訊息。
*   `gemini_model = "gemini-3-flash-preview"`: 設定使用的 Gemini 模型版本。
*   `gemini_token_limit = 4000`: 設定 AI 回應的長度上限。
*   `LINK_SCREENSHOT_ENABLED = True`: 開啟/關閉連結自動截圖功能。
*   `DAILY_QUOTE_IMAGE_ENABLED = True`: 開啟/關閉金句圖片生成功能。
*   `zero_clock_only = True`: 若設為 `True`，每日金句功能只會在午夜執行；設為 `False` 則每次啟動都會執行（方便測試）。

---

## ☁️ GitHub Actions 自動排程設定

本專案已包含 `.github/workflows/run_bot.yml`，設定為每 4 小時執行一次（0, 4, 8, 12, 16, 20 時）。
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
