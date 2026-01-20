# server.py (v4)
import sys
import json
sys.stdout.reconfigure(line_buffering=True)
import subprocess
import importlib.util
import random


# --- 0. 基礎依賴檢查 (Helper) ---
def check_requirements():
    required_packages = {
        'discord': 'discord.py',
        'google.genai': 'google-genai',
        'dotenv': 'python-dotenv',
        'playwright': 'playwright',
        'PIL': 'pillow',
        'requests': 'requests',
    }
    missing = []
    for module_name, package_name in required_packages.items():
        try:
            if importlib.util.find_spec(module_name) is None:
                missing.append(package_name)
        except (ImportError, ModuleNotFoundError):
            missing.append(package_name)
    
    if missing:
        print(f"❌ 偵測到缺少必要套件: {', '.join(missing)}")
        print("🔄 正在嘗試自動安裝...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            print("✅ 安裝完成！繼續執行程式...")
        except subprocess.CalledProcessError:
            print("❌ 自動安裝失敗。請手動執行以下指令安裝：")
            print(f"pip install {' '.join(missing)}")
            sys.exit(1)

# 執行依賴檢查 (必須在 import discord 前執行)
check_requirements()

import discord
import asyncio
from datetime import datetime, timedelta, timezone
import re
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from renderer import ImageGenerator
import requests
import io
from contextlib import redirect_stdout

# ==========================================
#              設定與環境 (FUNCTIONS)
# ==========================================

def get_settings():
    """回傳使用者偏好的設定參數"""
    settings = {
        # --- 功能開關 (0=停用, 1=定時啟用(預設), 2=一律啟用) ---
        "AI_SUMMARY_MODE": 1,          # AI總結
        "DAILY_QUOTE_MODE": 1,         # 每日金句 (定時=午夜)
        "DAILY_QUOTE_IMAGE_MODE": 1,   # 每日金句圖片生成 (0=關閉, 1/2=啟用)
        "LINK_SCREENSHOT_MODE": 1,     # 連結截圖
        "WEATHER_MODE": 1,             # 天氣預報 (0=停用, 1=定時, 2=強制)
        
        # --- 定時規則 (GMT+8) ---
        "AI_SUMMARY_SCHEDULE_MODULO": 4,       # AI總結頻率 (每N小時，0, 4, 8...)
        "LINK_SCREENSHOT_SCHEDULE_MODULO": 2,  # 連結截圖頻率 (每N小時，0, 2, 4...)
        "WEATHER_SCHEDULE_MODULO": 4,          # 天氣預報頻率 (每N小時，0, 4, 8...)
        "SCHEDULE_DELAY_TOLERANCE": 1,         # 允許延遲執行的時數 (應對 GH Actions 延遲，單位: 小時)
        "TZ": timezone(timedelta(hours=8)),    # 機器人運作時區
        # 每日金句固定於 00:xx 執行 (24小時一次)

        # --- 天氣預報地點 ---
        # "WEATHER_COUNTIES": [
        #     "臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹縣", "新竹市", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣", "嘉義市", "屏東縣","宜蘭縣", "花蓮縣", "臺東縣", "澎湖縣", "金門縣", "連江縣", 
        # ],
        "WEATHER_COUNTIES": [
            "臺北市", "新北市", "桃園市", "臺中市", "臺南市", "高雄市", "基隆市", "新竹市", "苗栗縣", "彰化縣", "南投縣", "雲林縣", "嘉義縣", "嘉義市", "屏東縣","宜蘭縣", "花蓮縣", "臺東縣"
        ],

        
        # --- 抓取範圍 ---
        "DAYS_AGO": 1,                   # 每日金句抓取範圍  (X天前) 0為今天, 1為昨天...
        "RECENT_MSG_HOURS": 5,           # AI總結抓取範圍   (X小時內 需保留排程不準時的緩衝)
        "LINK_SCREENSHOT_HOURS": 3,      # 連結截圖抓取範圍  (X小時內 需保留排程不準時的緩衝)

        # --- 踩地雷 ---
        "MINESWEEPER_ROWS": 6,           # 
        "MINESWEEPER_COLS": 6,           # 
        "MINESWEEPER_MINES": 2,          # 地雷
        
        # --- Gemini AI 總結 ---
        
        "AUTHOR_NAME_LIMIT": 4,          # 名字顯示長度
        "MAX_MSG_LENGTH": 500,           # 單則訊息最大長度
        "SHOW_DATE": False,              # 是否顯示日期
        "SHOW_SECONDS": False,           # 是否顯示秒數
        "SHOW_ATTACHMENTS": False,       # 是否顯示附件網址
        "SIMPLIFY_LINKS": True,          # 連結簡化
        "GEMINI_TOKEN_LIMIT": 120000,    # Token 上限
        "GEMINI_MODEL_PRIORITY_LIST": ["gemini-3-flash-preview","gemini-2.5-flash","gemma-3-27b-it"], # 模型列表
        # "GEMINI_MODEL_PRIORITY_LIST": ["gemma-3-27b-it"], #測試用
        "IGNORE_TOKEN": "-# 🤖",         # 截斷標記
        "BOT_NAME": "機器人",           # Bot 在對話歷史中的顯示名稱
        "GEMINI_SUMMARY_FORMAT": """
依照以下md格式對各頻道總結，並且適時使用換行幫助閱讀，盡量不要省略成員名(以暱稱為主)，不要多餘文字。如果有人提到何時要做什麼事，也請一併列出。必須認真思考。
## [頻道名]
(請條列四五個重點但只能一層)\n
**提及的規劃**\n(請列出所有提到的時間規劃)\n
**結論**\n(總結內容)\n
""",
    }

    # GitHub Actions 環境強制覆寫 (避免本地測試改壞 Config 影響線上)
    if os.getenv('GITHUB_ACTIONS') == 'true':
        force_ai = os.getenv("FORCE_AI_SUMMARY", "false").lower() == "true"
        force_quote = os.getenv("FORCE_DAILY_QUOTE", "false").lower() == "true"
        force_link = os.getenv("FORCE_LINK_SCREENSHOT", "false").lower() == "true"
        force_weather = os.getenv("FORCE_WEATHER_FORECAST", "false").lower() == "true"
        
        # 只要有任何一個強制執行旗標被打開
        if force_ai or force_quote or force_link or force_weather: # 偵測到手動強制執行
            print("🚀 偵測到手動強制執行，將覆寫排程設定：")
            # 1. 先全部關閉 (設為 0)
            settings["AI_SUMMARY_MODE"] = 0
            settings["DAILY_QUOTE_MODE"] = 0
            settings["LINK_SCREENSHOT_MODE"] = 0
            settings["WEATHER_MODE"] = 0
            
            # 2. 針對被開啟的項目設為 2 (強制啟用)
            if force_ai:
                settings["AI_SUMMARY_MODE"] = 2
                print("   💪 強制執行 AI 總結 (Mode 2)")
            if force_quote:
                settings["DAILY_QUOTE_MODE"] = 2
                print("   💪 強制執行 每日金句 (Mode 2)")
            if force_link:
                settings["LINK_SCREENSHOT_MODE"] = 2
                print("   💪 強制執行 連結截圖 (Mode 2)")
            if force_weather:
                settings["WEATHER_MODE"] = 2
                print("   💪 強制執行 天氣預報 (Mode 2)")
        else:
            # 純排程模式 (無任何強制旗標) -> 全部設為 1 (定時)
            print("🕒 GitHub Actions 排程模式：全部設為定時檢查 (Mode 1)")
            settings["AI_SUMMARY_MODE"] = 1
            settings["DAILY_QUOTE_MODE"] = 1
            settings["LINK_SCREENSHOT_MODE"] = 1
            settings["WEATHER_MODE"] = 1
    
    return settings

def get_secrets():
    """讀取 .env 或環境變數，並回傳相關 Token 與 Channel ID"""
    load_dotenv()
    secrets = {}
    
    # 1. Discord Token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ 錯誤: 未讀取到 DISCORD_BOT_TOKEN")
    else:
        print(f"✅ 讀取 DISCORD_BOT_TOKEN ({token[:5]}***)")
    secrets['TOKEN'] = token

    # 2. Gemini API Key
    gemini_key = os.getenv('GEMINI_API_KEY')
    if not gemini_key:
        print("⚠️ 警告: 未讀取到 GEMINI_API_KEY")
    else:
        print("✅ 讀取 GEMINI_API_KEY")
    secrets['GEMINI_API_KEY'] = gemini_key

    # 3. Source Channel IDs
    source_ids_str = os.getenv('SOURCE_CHANNEL_IDS', '')
    source_ids = []
    if source_ids_str:
        try:
            # 支援以逗號分隔，並過濾掉 # 註解
            source_ids = [int(x.split('#')[0].strip()) for x in source_ids_str.split(',') if x.strip() and x.split('#')[0].strip()]
            print(f"✅ 監聽頻道: {source_ids}")
        except ValueError:
            print(f"❌ SOURCE_CHANNEL_IDS 格式錯誤: {source_ids_str}")
    secrets['SOURCE_CHANNEL_IDS'] = source_ids

    # 4. Target Channel ID
    target_id = None
    try:
        t_id_str = os.getenv('TARGET_CHANNEL_ID')
        if t_id_str:
            target_id = int(t_id_str.split('#')[0].strip())
            print(f"✅ 目標頻道: {target_id}")
    except ValueError:
        print("❌ TARGET_CHANNEL_ID 格式錯誤")
    secrets['TARGET_CHANNEL_ID'] = target_id

    # 5. Target Preview ID
    preview_id = None
    try:
        p_id_str = os.getenv('TARGET_PREVIEW_ID')
        if p_id_str:
            preview_id = int(p_id_str.split('#')[0].strip())
            print(f"✅ 預覽頻道: {preview_id}")
    except ValueError:
        print("❌ TARGET_PREVIEW_ID 格式錯誤")
    secrets['TARGET_PREVIEW_ID'] = preview_id

    # 5.5 Target Weather ID
    weather_channel_id = None
    try:
        w_id_str = os.getenv('TARGET_WEATHER_ID')
        if w_id_str:
            weather_channel_id = int(w_id_str.split('#')[0].strip())
            print(f"✅ 天氣頻道: {weather_channel_id}")
    except ValueError:
        print("❌ TARGET_WEATHER_ID 格式錯誤")
    secrets['TARGET_WEATHER_ID'] = weather_channel_id

    # 6. Weather Key
    weather_key = os.getenv('WEATHER_KEY')
    if not weather_key:
        print("⚠️ 警告: 未讀取到 WEATHER_KEY")
    else:
        print("✅ 讀取 WEATHER_KEY")
    secrets['WEATHER_KEY'] = weather_key

    return secrets

def get_best_ipad_13():
    """Helper: 尋找最好的 13 吋 iPad 模擬器"""
    try:
        output = subprocess.check_output(["xcrun", "simctl", "list", "devices"], text=True)
        # 找 13-inch iPad
        pattern = r"(iPad.*13-inch.*?)\s\(([A-F0-9-]{36})\)\s\((.*?)\)"
        matches = re.findall(pattern, output)
        
        if not matches:
            print("❌ 沒找到 13 吋 iPad")
            return None, None

        # 排序：已開機 (Booted) 的排前面
        sorted_matches = sorted(matches, key=lambda x: x[2] != "Booted")
        name, uuid, status = sorted_matches[0]
        
        print(f"✅ 抓到目標：{name} ({status})")
        return uuid, status
    except Exception as e:
        print(f"抓取清單錯誤: {e}")
        return None, None

def set_simulator_preferences(uuid):
    """將模擬器強制設定為 繁體中文 (台灣)"""
    home = os.path.expanduser("~")
    plist_path = f"{home}/Library/Developer/CoreSimulator/Devices/{uuid}/data/Library/Preferences/.GlobalPreferences.plist"
    
    print(f"   ⚙️  正在設定模擬器語系 (zh_TW)...")
    try:
        # 設定 AppleLocale = zh_TW
        subprocess.run(["plutil", "-replace", "AppleLocale", "-string", "zh_TW", plist_path], check=True, capture_output=True)
        # 設定 AppleLanguages = ["zh-Hant-TW", "en-US"]
        # 注意: JSON 格式在命令列傳遞需小心 quotes，但 subprocess list 參數會處理
        subprocess.run(["plutil", "-replace", "AppleLanguages", "-json", '["zh-Hant-TW", "en-US"]', plist_path], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️ 無法設定語系 (可能是路徑錯誤或權限問題): {e}")


def generate_minesweeper(rows=6, cols=6, mines=3):
    """生成踩地雷盤面 (Discord Spoils)"""
    # 初始化盤面
    grid = [[0 for _ in range(cols)] for _ in range(rows)]
    mine_positions = set()
    
    # 佈置地雷
    while len(mine_positions) < mines:
        r, c = random.randint(0, rows-1), random.randint(0, cols-1)
        if (r, c) not in mine_positions:
            mine_positions.add((r, c))
            grid[r][c] = -1  # -1 代表地雷
            
    # 計算周圍數字
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == -1: continue
            
            # 檢查八方
            count = 0
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0: continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if grid[nr][nc] == -1:
                            count += 1
            grid[r][c] = count
            
    # 轉換為 Emoji 字串
    # 對照表
    num_map = {
        -1: '💣',
        0: '0️⃣',
        1: '1️⃣',
        2: '2️⃣',
        3: '3️⃣',
        4: '4️⃣',
        5: '5️⃣',
        6: '6️⃣',
        7: '7️⃣',
        8: '8️⃣'
    }
    
    result_str = ""
    for r in range(rows):
        line_items = []
        for c in range(cols):
            val = grid[r][c]
            emoji = num_map.get(val, '❓')
            line_items.append(f"||{emoji}||")
        result_str += "".join(line_items) + "\n"
        
    return result_str.strip()

def generate_choice_solver(settings=None):
    """生成選擇困難解決器 (骰子與硬幣)"""
    # 預設值 (如果沒有傳入 settings)
    rows = settings["MINESWEEPER_ROWS"] if settings else 6
    cols = settings["MINESWEEPER_COLS"] if settings else 6
    mines = settings["MINESWEEPER_MINES"] if settings else 7

    # 骰子 (1-6) x 10 (使用全形數字以保持等寬)
    full_width_digits = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣']
    dice_outcomes = [random.choice(full_width_digits) for _ in range(10)]
    dice_str = "  ".join([f"|| {x} ||" for x in dice_outcomes])
    
    # 硬幣 (正/反) x 10
    coin_outcomes = ["⬆️" if random.choice([True, False]) else "⬇️" for _ in range(10)]
    coin_str = "  ".join([f"|| {x} ||" for x in coin_outcomes])
    
    return (
        "## 選擇困難解決器\n"
        "🎲 丟個骰子吧\n\n"
        f"{dice_str}\n\n"
        "🪙 丟個硬幣吧\n\n"
        f"{coin_str}\n\n"
        f"💣 踩個地雷吧 ( {mines} 個地雷，{rows} x {cols} )\n\n"
        f"{generate_minesweeper(rows, cols, mines)}\n"
    )

# ==========================================
#              主要邏輯 (FEATURES)
# ==========================================

async def send_split_message(channel, text):
    """Helper: 分段發送長訊息 (Discord limit 2000 chars)"""
    if not text: return
    LIMIT = 1900
    
    lines = text.split('\n')
    buffer = ""
    
    for line in lines:
        if len(buffer) + len(line) + 1 > LIMIT:
            if buffer:
                await channel.send(buffer)
                buffer = ""
            while len(line) > LIMIT:
                await channel.send(line[:LIMIT])
                line = line[LIMIT:]
            buffer = line + "\n"
        else:
            buffer += line + "\n"
            
    if buffer:
        await channel.send(buffer)

async def run_ai_summary(client, settings, secrets):
    mode = settings.get("AI_SUMMARY_MODE", 2)
    tz = settings["TZ"]
    now = datetime.now(tz)
    # 取得強制旗標 (相容大小寫)
    force_run = str(os.getenv("FORCE_AI_SUMMARY", "false")).lower() == "true"
    
    # Mode 2: 強制執行 (無視時間) -> 直接往下走
    # Mode 1: 定時執行 (需檢查時間，除非有 force_run)
    # Mode 0: 停用 (除非有 force_run)

    if mode == 0 and not force_run:
        print("⏹️ AI 總結功能已停用 (Mode 0)，跳過。")
        return

    if mode == 1 and not force_run:
        modulo = settings.get("AI_SUMMARY_SCHEDULE_MODULO", 4)
        delay_tolerance = settings.get("SCHEDULE_DELAY_TOLERANCE", 1)
        # 檢查是否在排程時段內 (允許一定程度的延遲)
        # 例如 modulo=4, delay=1, 則 0,1, 4,5, 8,9 ... 點都會執行
        if (now.hour % modulo) > delay_tolerance:
            print(f"⏹️ [AI Summary] 現在 {now.strftime('%H:%M')} 非排程時段 (每 {modulo} 小時，允許延遲 {delay_tolerance}h)，跳過。")
            return

    hours = settings["RECENT_MSG_HOURS"]
    print(f">>> [AI Summary] 開始執行：抓取前 {hours} 小時訊息")
    
    tz = settings["TZ"]
    now = datetime.now(tz)
    target_time_ago = now - timedelta(hours=hours)
    collected_output = []
    author_mapping = {} # 記錄作者用戶名與暱稱的對應關係

    try:
        # 時間格式
        time_fmt = ""
        if settings["SHOW_DATE"]: time_fmt += "%Y年%m月%d日 %A "
        time_fmt += "%H:%M"
        if settings["SHOW_SECONDS"]: time_fmt += ":%S"

        for channel_id in secrets["SOURCE_CHANNEL_IDS"]:
            ch = client.get_channel(channel_id)
            if not ch: continue
            
            print(f"   正在掃描: #{ch.name}")
            channel_msgs = []
            
            async for msg in ch.history(after=target_time_ago, limit=None):

                content = msg.content
                # 截斷標記
                ignore_token = settings.get("IGNORE_TOKEN", "> 🤖 ")
                bot_name = settings.get("BOT_NAME", "Bot")
                is_bot_msg = False

                if ignore_token in content:
                    content = content.split(ignore_token)[0]
                    is_bot_msg = True
                
                # 額外檢查：如果是機器人自己發的訊息，一律視為 Bot 訊息
                if msg.author.id == client.user.id:
                    is_bot_msg = True
                
                # 決定顯示名稱 (用於對照表與訊息)
                if is_bot_msg:
                    display_name = bot_name
                else:
                    display_name = msg.author.display_name

                # 記錄作者資訊 (更新對照表)
                author_mapping[msg.author.id] = (msg.author.name, display_name)

                # Mentions 處理
                if msg.mentions:
                    for user in msg.mentions:
                        if user.id == client.user.id:
                            u_name = bot_name
                        else:
                            u_name = user.display_name[:settings["AUTHOR_NAME_LIMIT"]]
                        content = content.replace(f"<@{user.id}>", f"@{u_name}")
                        content = content.replace(f"<@!{user.id}>", f"@{u_name}")

                # 轉發與附件處理 (Message Snapshots)
                if hasattr(msg, 'message_snapshots') and msg.message_snapshots:
                    for snapshot in msg.message_snapshots:
                        s_content = getattr(snapshot, 'content', '')
                        if s_content: content += f"[轉發內容]: {s_content}"
                        if hasattr(snapshot, 'attachments') and snapshot.attachments:
                            content += " (轉發附件)"

                # 連結簡化
                if settings["SIMPLIFY_LINKS"]:
                    # Embed 標題替換
                    if msg.embeds:
                        for embed in msg.embeds:
                            if embed.title:
                                if embed.url and embed.url in content:
                                    content = content.replace(embed.url, f"(連結 {embed.title})")
                                elif content.strip().startswith("http"):
                                    content = f"(連結 {embed.title})"
                    
                    # 剩餘連結僅留網域
                    def domain_replacer(match):
                        url = match.group(0)
                        try:
                            no_proto = url.split("://", 1)[1]
                            return f"(連結 {no_proto.split('/', 1)[0]})"
                        except: return url
                    content = re.sub(r'https?://\S+', domain_replacer, content)

                # 表情與時間
                content = re.sub(r'<a?:\w+:\d+>', '(貼圖)', content)

                # 長度截斷
                if len(content) > settings.get("MAX_MSG_LENGTH", 500):
                    content = content[:settings.get("MAX_MSG_LENGTH", 500)] + "..."

                created_at_local = msg.created_at.astimezone(tz).strftime(time_fmt)
                
                # 決定最終顯示名稱 (一般用戶需截斷，Bot 不需)
                if is_bot_msg:
                    author_name = display_name
                else:
                    author_name = display_name[:settings["AUTHOR_NAME_LIMIT"]]

                if not content.strip() and not msg.attachments: continue
                
                msg_line = f"{author_name}@{created_at_local}: {content}"
                
                # 附件顯示
                if msg.attachments:
                    show_att = settings["SHOW_ATTACHMENTS"]
                    msg_line += " (附件)" if not show_att else f" (附件 {[a.url for a in msg.attachments]})"
                
                channel_msgs.append(msg_line)

            if channel_msgs:
                collected_output.append(f"--[#{ch.name}]")
                collected_output.extend(channel_msgs)

        # 生成用戶對照表
        mapping_section = ""
        if author_mapping:
            name_limit = settings.get("AUTHOR_NAME_LIMIT", 4)
            mapping_lines = [f"- 用戶: {name}, 暱稱: {disp[:name_limit]}" for uid, (name, disp) in author_mapping.items()]
            mapping_section = "[參與對話的用戶與伺服器暱稱對照表]\n" + "\n".join(mapping_lines) + "\n\n"

        final_messages_str = mapping_section + "\n".join(collected_output)
        # print(f"--- 收集到的訊息 ---\n{final_messages_str}\n--------------------")
        print("   訊息收集完成，準備進行 AI 總結...")

        target_ch_id = secrets["TARGET_CHANNEL_ID"]
        gemini_key = secrets["GEMINI_API_KEY"]

        if not target_ch_id:
             print("   ⚠️ 未設定 TARGET_CHANNEL_ID，跳過 AI 總結發送")


        if target_ch_id:
            target_ch = client.get_channel(target_ch_id)
            if target_ch:
                print(f"   📣 準備發送至頻道: #{target_ch.name} ({target_ch.id})")
                if final_messages_str:
                    if gemini_key:
                        print("   🤖 呼叫 Gemini 中...")
                        
                        param_model_list = settings.get("GEMINI_MODEL_PRIORITY_LIST", ["gemini-3-flash-preview"])
                        # 相容舊設定: 若只有 GEMINI_MODEL 則轉為 list
                        if "GEMINI_MODEL" in settings and "GEMINI_MODEL_PRIORITY_LIST" not in settings:
                             param_model_list = [settings["GEMINI_MODEL"]]

                        generated_text = None
                        used_model_name = None
                        
                        ai_client = genai.Client(api_key=gemini_key)
                        prompt = f"請用繁體中文總結以下聊天內容\n{settings['GEMINI_SUMMARY_FORMAT']}\n\n{final_messages_str}"

                        print(final_messages_str)
                        
                        for model_name in param_model_list:
                            print(f"   🔄 嘗試模型: {model_name}...")
                            try:
                                response = ai_client.models.generate_content(
                                    model=model_name,
                                    contents=prompt,
                                    config=types.GenerateContentConfig(max_output_tokens=settings["GEMINI_TOKEN_LIMIT"])
                                )
                                if response.text:
                                    generated_text = response.text
                                    used_model_name = model_name
                                    print(f"   ✅ 模型 {model_name} 成功回應")
                                    print(f"Gemini 回應:\n{response.model_dump_json(indent=2)}")
                                    break
                            except Exception as e:
                                print(f"   ⚠️ 模型 {model_name} 失敗: {e}")
                                continue

                        if generated_text and used_model_name:
                            start_str = target_time_ago.strftime('%Y年%m月%d日 %A %H:%M')
                            end_str = now.strftime('%H:%M')
                            
                            if "gemini" in used_model_name.lower():
                                footer_model_text = f"> -# 🤖 以上重點摘要由業界領先的 Google Gemini AI 大型語言模型「{used_model_name}」驅動。"
                            else:
                                footer_model_text = f"> -# 🤖 以上重點摘要由 Google Gemma 開放權重模型「{used_model_name}」驅動。"

                            report = (
                                f"# ✨ {hours} 小時重點摘要出爐囉！\n"
                                f"** 🕘 {start_str} ~ {end_str}**\n"
                                f"\n"
                                f"{generated_text}\n"
                                f"{footer_model_text}\n"
                                f"> -# 🤓 AI 總結內容僅供參考，敬請核實。\n"
                                f"{generate_choice_solver(settings)}"
                            )
                            await send_split_message(target_ch, report)
                            print("   ✅ AI 總結已發送")
                        else:
                            print(f"   ❌ 所有模型嘗試皆失敗或無回應")
                            error_payload = {
                                "status": "Failed",
                                "module": "Gemini AI Summary",
                                "reason": "All models in priority list failed.",
                                "timestamp": datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
                            }
                            error_msg = f"## ⚠️ Gemini 發生錯誤 (所有模型嘗試失敗)\n```json\n{json.dumps(error_payload, indent=2, ensure_ascii=False)}\n```"
                            await send_split_message(target_ch, f"{error_msg}\n{generate_choice_solver(settings)}")
                    else:
                         print("   ⚠️ 缺少 Gemini Key，跳過 AI 總結")
                else:
                    # 無訊息的情況
                    print("   ℹ️ 無新訊息，發送空報告")
                    start_str = target_time_ago.strftime('%Y年%m月%d日 %A %H:%M')
                    end_str = now.strftime('%H:%M')
                    report = (
                        f"# ✨ {hours} 小時重點摘要出爐囉！\n"
                        f"** 🕘 {start_str} ~ {end_str}**\n\n"
                        f"**(這段時間內沒有新訊息)**\n\n"
                        f"{generate_choice_solver(settings)}"
                    )
                    await target_ch.send(report)
            else:
                print(f"   ⚠️ 找不到目標頻道 {target_ch_id}")
    except Exception as e:
        print(f"❌ AI Summary 執行錯誤: {e}")
    print()


async def run_daily_quote(client, settings, secrets):
    tz = settings["TZ"]
    now = datetime.now(tz)
    force_run = os.getenv("FORCE_DAILY_QUOTE", "false").lower() == "true"
    mode = settings.get("DAILY_QUOTE_MODE", 1)

    # Mode 0: 停用
    if mode == 0 and not force_run:
        print("⏹️ 每日金句功能已停用 (Mode 0)，跳過。")
        return

    # Mode 1: 定時 (午夜)
    if mode == 1 and not force_run:
        delay_tolerance = settings.get("SCHEDULE_DELAY_TOLERANCE", 1)
        # 允許在 00:xx ~ 01:xx 執行 (應對 GH Actions 延遲)
        is_scheduled_time = (0 <= now.hour <= delay_tolerance)
        if not is_scheduled_time:
            print(f"⏹️ [Daily Quote] 現在 {now.strftime('%H:%M')} 非執行時段 (00:00~{delay_tolerance:02d}:59)，跳過。")
            return

    print(">>> [Daily Quote] 開始執行：每日金句")
    target_start = (now - timedelta(days=settings["DAYS_AGO"])).replace(hour=0, minute=0, second=0, microsecond=0)
    target_end = target_start + timedelta(days=1)
    target_date_str = target_start.strftime('%Y年%m月%d日 %A')
    
    print(f"   查詢日期: {target_date_str}")
    best_message = None
    max_reactions = 0

    for channel_id in secrets["SOURCE_CHANNEL_IDS"]:
        ch = client.get_channel(channel_id)
        if not ch: continue
        print(f"   掃描: #{ch.name}")
        async for message in ch.history(after=target_start, before=target_end, limit=None):
            if not message.reactions: continue
            count = sum(r.count for r in message.reactions)
            if count > max_reactions:
                max_reactions = count
                best_message = message
    
    target_ch = client.get_channel(secrets["TARGET_CHANNEL_ID"])
    if target_ch:
        print(f"   📣 準備發送至頻道: #{target_ch.name} ({target_ch.id})")

    if best_message and target_ch:
        # 準備資料
        print("   📊 正在分析每日金句...")
        
        # 1. 取得頭像
        avatar_bytes = None
        try:
            avatar_bytes = await best_message.author.display_avatar.read()
        except: pass

        # 2. 取得伺服器 Icon
        server_icon_bytes = None
        server_name = "Discord"
        if best_message.guild:
            server_name = best_message.guild.name
            if best_message.guild.icon:
                try:
                    server_icon_bytes = await best_message.guild.icon.read()
                except: pass

        # 3. 取得附件圖片 (僅取第一張)
        attachment_bytes = None
        if best_message.attachments:
            for att in best_message.attachments:
                if att.content_type and att.content_type.startswith('image'):
                    try:
                        attachment_bytes = await att.read()
                        break
                    except: pass
        
        # 4. 表情符號資料列表 [(emoji_str, count, url), ...]
        reactions_data = []
        for r in best_message.reactions:
            e_str = str(r.emoji)
            url = None
            if hasattr(r.emoji, "url"):
                url = r.emoji.url
            reactions_data.append((e_str, r.count, url))
        
        # 排序：數量多的在前面
        reactions_data.sort(key=lambda x: x[1], reverse=True)
        
        # 5. 日期格式
        date_dt = best_message.created_at.astimezone(settings["TZ"])
        date_text_img = f"金句王<span class='date-subtext'>{date_dt.year}年{date_dt.month}月{date_dt.day}日</span>"
        target_date_str = date_dt.strftime('%Y年%m月%d日 %A')
        
        # 0. 準備內容 (Bot 文字訊息用)
        content = best_message.content or f"[**無法言喻的訊息，點一下來查看**]({best_message.jump_url})"
        
        # 0.5 準備內容 (圖片生成用 - 純淨版)
        image_clean_content = best_message.content if best_message.content else ""
        
        # Mentions 替換 (Bot 文字訊息用)
        if best_message.mentions:
            for user in best_message.mentions:
                content = content.replace(f"<@{user.id}>", f"@{user.display_name}")
                content = content.replace(f"<@!{user.id}>", f"@{user.display_name}")
                
        # Mentions 替換 (圖片生成用)
        if best_message.mentions and image_clean_content:
            for user in best_message.mentions:
                 image_clean_content = image_clean_content.replace(f"<@{user.id}>", f"@{user.display_name}")
                 image_clean_content = image_clean_content.replace(f"<@!{user.id}>", f"@{user.display_name}")

        # 額外資訊 (轉發/附件)
        extras = []
        if hasattr(best_message, 'message_snapshots') and best_message.message_snapshots:
            for snap in best_message.message_snapshots:
                s_con = getattr(snap, 'content', '')
                if s_con: extras.append(f"🔄 [轉發]: {s_con}")
                if hasattr(snap, 'attachments') and snap.attachments:
                    for att in snap.attachments: extras.append(f"📎 [轉發附件]: {att.url}")
        
        if best_message.attachments:
            for att in best_message.attachments:
                # 只有非圖片附件才列出連結，圖片已經被 renderer 處理了
                if not (att.content_type and att.content_type.startswith('image')):
                     extras.append(f"📎 [附件]: {att.url}")
        
        if extras: content += "\n\n" + "\n".join(extras)
        
        # 呼叫生成器 (若開啟)
        img_buffer = None
        # 1 或 2 皆視為啟用
        if settings.get("DAILY_QUOTE_IMAGE_MODE", 2) > 0:
            print("   🎨 正在生成每日金句圖片...")
            generator = ImageGenerator()
            
            # 改為直接 await (因為 renderer 內部現在是用 async Playwright)
            img_buffer = await generator.generate_quote_card(
                quote_content=image_clean_content,
                author_name=best_message.author.display_name,
                author_avatar=avatar_bytes,
                date_text=date_text_img,
                server_name=server_name,
                server_icon=server_icon_bytes,
                attachment_image=attachment_bytes,
                reactions=reactions_data
            )
        
        # 發送
        if img_buffer:
             file = discord.File(fp=img_buffer, filename="daily_quote.png")
             
             # 準備詳細文字報告
             emoji_detail = " ".join([f"{str(r.emoji)} x{r.count}" for r in best_message.reactions])
             
             report = (
                f"# 🏆 **{target_date_str} 每日金句出爐囉！**\n"
                f"🔗 來源: {best_message.jump_url}\n"
                f"👨‍💻 作者: {best_message.author.mention}\n\n"
                f">>> {content}\n\n"
                f"🔥 **總表情數：{max_reactions}**\n"
                f"📊 **表情明細：** {emoji_detail}\n"
             )
             await target_ch.send(content=report, file=file)
             print("   ✅ 金句圖片已發送")
        else:
             # 純文字模式 fallback
             emoji_detail = " ".join([f"{str(r.emoji)} x{r.count}" for r in best_message.reactions])
             report = (
                f"# 🏆 **{target_date_str} 每日金句**\n"
                f"🔗 {best_message.jump_url}\n"
                f"👨‍💻 {best_message.author.mention}\n\n"
                f">>> {content}\n\n"
                f"🔥 **表情總數：{max_reactions}** ({emoji_detail})\n"
             )
             await target_ch.send(content=report)
             print("   ✅ 金句(純文字)已發送")
    else:
        print("   ⚠️ 沒找到熱門訊息或無目標頻道")
    print()


async def run_link_screenshot(client, settings, secrets):
    mode = settings.get("LINK_SCREENSHOT_MODE", 2)
    tz = settings["TZ"]
    now = datetime.now(tz)
    # 取得強制旗標 (相容大小寫)
    force_run = str(os.getenv("FORCE_LINK_SCREENSHOT", "false")).lower() == "true"
    # Mode 0: 停用
    if mode == 0 and not force_run:
        print("⏹️ 連結截圖功能已停用 (Mode 0)，跳過。")
        return

    # Mode 2: 強制執行 (無視時間) -> 直接往下走
    if mode == 1 and not force_run:
        modulo = settings.get("LINK_SCREENSHOT_SCHEDULE_MODULO", 2)
        delay_tolerance = settings.get("SCHEDULE_DELAY_TOLERANCE", 1)
        if (now.hour % modulo) > delay_tolerance:
            print(f"⏹️ [Link Screenshot] 現在 {now.strftime('%H:%M')} 非排程時段 (每 {modulo} 小時，允許延遲 {delay_tolerance}h)，跳過。")
            return

    hours = settings["LINK_SCREENSHOT_HOURS"]
    print(f">>> [Link Screenshot] 開始執行：連結截圖 ({hours} 小時內)")
    
    target_time_ago = now - timedelta(hours=hours)

    try:
        ipad_uuid, ipad_status = await asyncio.to_thread(get_best_ipad_13)
        if not ipad_uuid:
            print("   ⚠️ 無 iPad UUID，跳過")
            return

        # 設定語系
        await asyncio.to_thread(set_simulator_preferences, ipad_uuid)

        # 狀態檢查與啟動
        # if ipad_status == "Booted":
        #     print("   � 偵測到模擬器已開啟，正在重啟以確保語系生效...")
        #     await asyncio.to_thread(subprocess.run, ["xcrun", "simctl", "shutdown", ipad_uuid])
        #     await asyncio.sleep(5) # 等待完全關閉
        
        print("   🚀 啟動模擬器...")
        await asyncio.to_thread(subprocess.run, ["xcrun", "simctl", "boot", ipad_uuid])
        await asyncio.to_thread(subprocess.run, ["xcrun", "simctl", "bootstatus", ipad_uuid, "-b"])

        # 收集連結
        captured_links = []
        
        # 整合要掃描的頻道 (Source + Target Preview)
        scan_channel_ids = set(secrets["SOURCE_CHANNEL_IDS"])
        if secrets["TARGET_PREVIEW_ID"]:
            scan_channel_ids.add(secrets["TARGET_PREVIEW_ID"])
        
        print(f"   [Debug] Source IDs: {secrets['SOURCE_CHANNEL_IDS']}")
        print(f"   [Debug] Scan Set: {scan_channel_ids}")

        for channel_id in scan_channel_ids:
            ch = client.get_channel(channel_id)
            if not ch: continue
            print(f"   掃描連結: #{ch.name}")
            async for msg in ch.history(after=target_time_ago, limit=None):
                if msg.author.id == client.user.id:
                    continue

                urls = re.findall(r'(https?://\S+)', msg.content)
                for url in urls:
                    captured_links.append((url, msg))
        
        print(f"   共找到 {len(captured_links)} 個連結")

        target_ch = None
        if secrets["TARGET_PREVIEW_ID"]:
             target_ch = client.get_channel(secrets["TARGET_PREVIEW_ID"])
        
        if not target_ch:
            print(f"   ⚠️ 無預覽目標頻道 ({secrets.get('TARGET_PREVIEW_ID')})，僅截圖不發送")
        else:
            print(f"   📣 準備發送至頻道: #{target_ch.name} ({target_ch.id})")
            # 發送預告 Header
            if captured_links:
                start_str = target_time_ago.strftime('%Y年%m月%d日 %A %H:%M')
                end_str = now.strftime('%H:%M')
                header_msg = (
                    f"# 🔗 {hours} 小時內連結預覽出爐囉！\n"
                    f"** 🕘 {start_str} ~ {end_str} (共有{len(captured_links)}個連結)**\n"
                )
                await target_ch.send(header_msg)

        # 處理連結
        for idx, (url, msg) in enumerate(captured_links):
            print(f"   [{idx+1}/{len(captured_links)}] 處理: {url}")

            # 訊號(Cellular): 0~4
            # cell_bars = str(idx % 5)
            cell_bars = str(random.randint(2, 4))
            # Wifi: 0~3
            wifi_bars = str(random.randint(2, 3))
            # wifi_bars = str(idx % 4)
            # 電池: 第一張 1% -> 最後一張 100%
            total_links = len(captured_links)
            if total_links > 1:
                level = 1 + int(99 * idx / (total_links - 1))
            else:
                level = 100
            batt_level = str(level)
            
            # 若 100% 則顯示為 discharging (剛拔掉電源的感覺)，否則顯示 charging
            batt_state = "discharging" if level == 100 else "charging"

            sb_cmd = [
                "xcrun", "simctl", "status_bar", ipad_uuid, "override",
                "--dataNetwork", "5g",
                "--wifiMode", "active",     # 改為 active 才能顯示 WiFi 格數
                "--wifiBars", wifi_bars,
                "--cellularMode", "active",
                "--cellularBars", cell_bars,
                "--operatorName", "Google Fi",
                "--batteryState", batt_state,
                "--batteryLevel", batt_level
            ]
            # 執行 Status Bar Override
            await asyncio.to_thread(subprocess.run, sb_cmd)

            await asyncio.sleep(5) # 緩衝 (從 3s 改為 5s)

            # 開啟網頁
            success_open = False
            for _ in range(3): # 增加重試次數 (2 -> 3)
                # 使用 asyncio.to_thread 避免卡住 event loop
                try:
                    res = await asyncio.to_thread(subprocess.run, ["xcrun", "simctl", "openurl", ipad_uuid, url], capture_output=True)
                    if res.returncode == 0:
                        success_open = True
                        break
                except Exception as e:
                    print(f"   ⚠️ openurlException: {e}")
                
                print("   ⚠️ 開啟超時或失敗，等待重試...")
                await asyncio.sleep(5) # 重試間隔 (3s -> 5s)
            
            if not success_open:
                print("   ❌ 無法開啟連結 (多次嘗試失败)")
                continue

            print("   ⏳ 等待渲染...")
            await asyncio.sleep(20) # 等待渲染 (12s -> 15s)

            filename = f"screenshot_temp_{idx}.png"
            await asyncio.to_thread(subprocess.run, ["xcrun", "simctl", "io", ipad_uuid, "screenshot", filename])

            # 關閉 Safari
            await asyncio.to_thread(subprocess.run, ["xcrun", "simctl", "terminate", ipad_uuid, "com.apple.mobilesafari"])

            if target_ch:
                content_text = (
                    f"📸 **網頁預覽** {msg.created_at.astimezone(tz).strftime('%Y年%m月%d日 %A %H:%M')}\n"
                    f">>> 💬 @{msg.author.name} 傳送到 {msg.jump_url}\n"
                    f" 原始連結: <{url}>\n"
                )
                if os.path.exists(filename):
                    await target_ch.send(content=content_text, file=discord.File(filename))
                    os.remove(filename)
                else:
                    await target_ch.send(content_text + "\n(❌ 截圖失敗)")
            
            await asyncio.sleep(1)

    except Exception as e:
        print(f"❌ Screenshot error: {e}")
    print()


def get_weather_data(api_key, counties, tz):
    """
    使用 F-D0047-089 (全台未來2天，含逐時溫度)
    回傳格式: list of {'county':..., 'forecasts': [{'time':..., 'temp':..., 'wx':..., 'pop':...}]}
    """
    url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-089?Authorization={api_key}&locationName={','.join(counties)}"
    results = []

    try:
        # verify=False 避免部分環境 SSL 錯誤
        response = requests.get(url, verify=False)
        data = response.json()

        if data.get("success") != "true":
            print("API 請求失敗，請檢查 Key 有沒有填對。")
            return []

        if not data.get("records") or "Locations" not in data["records"]:
            print("API 回傳結構異常 (Missing Locations)")
            return []

        locations = data["records"]["Locations"][0]["Location"]
        
        # 基準時間: 當前小時 (例如 16:45 -> 16:00)
        now = datetime.now(tz)
        current_hour_dt = now.replace(minute=0, second=0, microsecond=0)

        for county in counties:
            loc = next((l for l in locations if l["LocationName"] == county), None)
            if not loc: continue
            
            temps = []
            wxs = []
            pops = []
            cis = []

            for elem in loc["WeatherElement"]:
                ename = elem["ElementName"]
                if ename == "溫度": temps = elem["Time"]
                elif ename == "天氣現象": wxs = elem["Time"]
                elif ename == "3小時降雨機率": pops = elem["Time"]
                elif ename == "舒適度指數": cis = elem["Time"]
            
            # 整理未來 6 小時資料
            # 1. 篩選 Temperature (逐時) >= current_hour_dt
            #    且只取前 6 筆
            forecasts = []
            
            # 預先排序確保順序
            temps.sort(key=lambda x: x["DataTime"])
            
            count = 0
            for t_item in temps:
                t_dt = datetime.fromisoformat(t_item["DataTime"])
                # 簡單判定：若資料時間 >= 當前小時 (或者允許前一小時?)
                # user 說 4:40 看 -> 顯示 4, 5, 6...
                # 若 t_dt 是 04:00 (timestamp), current is 04:40. t_dt < current.
                # 但 user 想看 4點的資料. 所以 t_dt >= current_hour_dt 即可.
                if t_dt >= current_hour_dt:
                    t_val = t_item["ElementValue"][0]["Temperature"]
                    
                    # 找對應的 Wx 和 PoP (區間包含 t_dt)
                    # Wx/PoP 是 3h 區間. StartTime <= t_dt < EndTime
                    # 若剛好等於 EndTime 則不含? 通常是 [Start, End)
                    
                    curr_wx = "???"
                    curr_pop = "-"
                    curr_ci = ""
                    
                    # Find Wx
                    for w in wxs:
                        st = datetime.fromisoformat(w["StartTime"])
                        et = datetime.fromisoformat(w["EndTime"])
                        if st <= t_dt < et:
                            curr_wx = w["ElementValue"][0]["Weather"]
                            break
                    
                    # Find PoP
                    for p in pops:
                        st = datetime.fromisoformat(p["StartTime"])
                        et = datetime.fromisoformat(p["EndTime"])
                        if st <= t_dt < et:
                            curr_pop = p["ElementValue"][0]["ProbabilityOfPrecipitation"]
                            break
                            
                    # Find CI
                    for c in cis:
                        # CI 也是逐時 (DataTime)
                        if c["DataTime"] == t_item["DataTime"]:
                            curr_ci = c["ElementValue"][0]["ComfortIndexDescription"]
                            break

                    forecasts.append({
                        "time": t_dt.strftime("%H:%M"), # 04:00
                        "temp": t_val,
                        "wx": curr_wx,
                        "pop": curr_pop,
                        "ci": curr_ci
                    })
                    
                    count += 1
                    if count >= 6: break
            
            if forecasts:
                # 組裝結果
                # time_range 用第一筆到最後一筆
                # 需包含日期: YYYY/MM/DD HH:MM ~ HH:MM
                # 從原始資料找日期 (因為 forecasts 裡的 time 只有 HH:MM)
                # 最簡單用 current_hour_dt 或 forecasts 的 loop 變數
                # 但 forecasts loop 裡面 t_dt 是最後一個. 
                # Better: retrieve start date from first forecast logic?
                # Actually, `count` loop runs 6 times. We can capture text there?
                # Or just grab current time since it's "now" based?
                # The forecasts start from current_hour_dt.
                
                s_dt = current_hour_dt
                e_dt = forecasts[-1]['time'] # Wait, this is string.
                # Let's reconstruct consistent string.
                
                date_str = s_dt.strftime("%Y/%m/%d")
                start_str = forecasts[0]['time']
                end_str = forecasts[-1]['time']
                
                results.append({
                    "county": county,
                    "forecasts": forecasts,
                    "time_range": f"{date_str} {start_str} ~ {end_str}"
                })

        return results

    except Exception as e:
        print(f"發生錯誤啦：{e}")
        return []


async def run_weather_forecast(client, settings, secrets):
    mode = settings.get("WEATHER_MODE", 1)
    # 取得強制旗標 (相容大小寫)
    force_run = str(os.getenv("FORCE_WEATHER_FORECAST", "false")).lower() == "true"
    
    # Mode 0: 停用
    if mode == 0 and not force_run:
        print("⏹️ 天氣預報功能已停用 (Mode 0)，跳過。")
        return

    # Mode 1: 定時
    if mode == 1 and not force_run:
        tz = settings["TZ"]
        now = datetime.now(tz)
        modulo = settings.get("WEATHER_SCHEDULE_MODULO", 4)
        delay_tolerance = settings.get("SCHEDULE_DELAY_TOLERANCE", 1)
        if (now.hour % modulo) > delay_tolerance:
            print(f"⏹️ [Weather] 現在 {now.strftime('%H:%M')} 非排程時段 (每 {modulo} 小時，允許延遲 {delay_tolerance}h)，跳過。")
            return

    print(">>> [Weather] 開始執行：天氣預報")
    
    if not secrets['WEATHER_KEY']:
        print("   ❌ 無 WEATHER_KEY，跳過")
        return

    # 執行捉取 (傳入 TZ)
    weather_data_list = get_weather_data(secrets['WEATHER_KEY'], settings['WEATHER_COUNTIES'], settings['TZ'])
    
    if not weather_data_list:
        print("   ⚠️ 執行完畢但無資料")
        return

    # 生成文字報告 (簡易版)
    text_report = ""
    for item in weather_data_list[:3]: # 只列出前幾個避免太長
        text_report += f"### {item['county']} ({item['time_range']})\n"
        for f in item['forecasts']:
             text_report += f"  {f['time']} | {f['temp']}°C | {f['wx']} | ☔{f['pop']}%\n"
        text_report += "\n"

    # 優先使用 TARGET_WEATHER_ID，若無則 fallback 到 TARGET_CHANNEL_ID
    target_ch_id = secrets.get('TARGET_WEATHER_ID')
    if not target_ch_id:
        target_ch_id = secrets.get('TARGET_CHANNEL_ID')
        if target_ch_id:
            print(f"   ℹ️ 未設定 TARGET_WEATHER_ID，使用預設目標頻道 {target_ch_id}")
    else:
        print(f"   ℹ️ 使用天氣專用頻道 {target_ch_id}")

    if target_ch_id:
        ch = client.get_channel(target_ch_id)
        if ch:
            print(f"   📣 準備發送至頻道: #{ch.name} ({ch.id})")
            header = f"## ☀️ 天氣預報快訊\n"
            
            # 準備 Server Info
            server_name = "Discord Server"
            server_icon = None
            if hasattr(ch, "guild") and ch.guild:
                server_name = ch.guild.name
                if ch.guild.icon:
                    try:
                        server_icon = await ch.guild.icon.read()
                    except Exception as e:
                        print(f"   ⚠️ 無法讀取伺服器圖示: {e}")

            # 定義分區
            region_map = {
                # "北部地區": ["基隆市", "臺北市", "新北市", "桃園市", "新竹市", "新竹縣", "宜蘭縣"],
                "北部地區": ["基隆市", "臺北市", "新北市", "桃園市", "新竹市", "宜蘭縣"],
                "中部地區": ["苗栗縣", "臺中市", "彰化縣", "南投縣", "雲林縣","花蓮縣"],
                "南部地區": ["嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣","臺東縣"]
                # "東部與離島": ["澎湖縣", "金門縣", "連江縣"]
            }

            # 取得預報時間範圍 (假設所有縣市一致)
            time_range_str = weather_data_list[0]['time_range'] if weather_data_list else ""

            header = f"## 🌤️ 台灣各縣市天氣預報\n📅 **{time_range_str}**\n"
            await send_split_message(ch, header)

            gen = ImageGenerator()
            
            # 依序產生並發送四張圖
            for r_name, r_counties in region_map.items():
                # 過濾該區資料
                group_data = [d for d in weather_data_list if d['county'] in r_counties]
                
                # 若完全沒資料則跳過
                if not group_data:
                    continue
                    
                print(f"   🎨 正在生成 [{r_name}] 天氣卡 (共 {len(group_data)} 筆)...")
                try:
                    img_buffer = await gen.generate_weather_card(
                        group_data, 
                        server_name, 
                        server_icon, 
                        title=f"{r_name}天氣預報"
                    )
                    
                    if img_buffer:
                        file = discord.File(fp=img_buffer, filename=f"weather_{r_name}.png")
                        await ch.send(file=file)
                        # await ch.send(content=f"**{r_name}**", file=file)
                        print(f"   ✅ {r_name} 圖片已發送")
                except Exception as e:
                    print(f"   ❌ 生成/發送 {r_name} 失敗: {e}")
            
        else:
            print(f"   ⚠️ 找不到頻道 {target_ch_id}")

    else:
        print("   ⚠️ 未設定 TARGET_WEATHER_ID 或 TARGET_CHANNEL_ID")
    print()



# ==========================================
#              主程式 (MAIN)
# ==========================================

class MyClient(discord.Client):
    def __init__(self, settings, secrets, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = settings
        self.secrets = secrets

    async def on_ready(self):
        print(f'✅ Bot 已登入：{self.user}')
        print('-------------------------------------------')

        # 1. 執行 AI 總結
        await run_ai_summary(self, self.settings, self.secrets)

        # 2. 執行 每日金句
        await run_daily_quote(self, self.settings, self.secrets)

        # 3. 執行 天氣預報
        await run_weather_forecast(self, self.settings, self.secrets)

        # 4. 執行 連結截圖
        await run_link_screenshot(self, self.settings, self.secrets)

        
        print('-------------------------------------------')
        print("🎉 所有排程執行完畢，Bot 關閉。")
        await self.close()

if __name__ == "__main__":
    # 讀取設定與變數
    settings_data = get_settings()
    secrets_data = get_secrets()

    print("\n=== 目前排程模式設定 ===")
    print(f"GitHub Actions 環境: {os.getenv('GITHUB_ACTIONS') == 'true'}")
    print(f"AI Summary Mode: {settings_data['AI_SUMMARY_MODE']} (Force: {os.getenv('FORCE_AI_SUMMARY', 'false')})")
    print(f"Daily Quote Mode: {settings_data['DAILY_QUOTE_MODE']} (Force: {os.getenv('FORCE_DAILY_QUOTE', 'false')})")
    print(f"Link Screenshot Mode: {settings_data['LINK_SCREENSHOT_MODE']} (Force: {os.getenv('FORCE_LINK_SCREENSHOT', 'false')})")
    print(f"Weather Forecast Mode: {settings_data['WEATHER_MODE']} (Force: {os.getenv('FORCE_WEATHER_FORECAST', 'false')})")
    print("========================\n")

    if not secrets_data['TOKEN']:
        print("❌ 無法執行：缺少 TOKEN")
    else:
        # 啟動機器人
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        intents.members = True # 必須啟用才能正確讀取伺服器暱稱 (需在 Developer Portal 開啟 Server Members Intent)
        
        client = MyClient(settings=settings_data, secrets=secrets_data, intents=intents)
        client.run(secrets_data['TOKEN'])
