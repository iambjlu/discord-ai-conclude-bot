# server.py (v3)
import sys
sys.stdout.reconfigure(line_buffering=True)
import subprocess
import importlib.util

# --- 0. 基礎依賴檢查 (Helper) ---
def check_requirements():
    required_packages = {
        'discord': 'discord.py',
        'google.genai': 'google-genai',
        'dotenv': 'python-dotenv'
    }
    missing = []
    for module_name, package_name in required_packages.items():
        if importlib.util.find_spec(module_name) is None:
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

# ==========================================
#              設定與環境 (FUNCTIONS)
# ==========================================

def get_settings():
    """回傳使用者偏好的設定參數"""
    return {
        # --- 功能開關 ---
        "AI_SUMMARY_ENABLED": True,      # AI總結
        "LINK_SCREENSHOT_ENABLED": True, # 連結截圖
        "ZERO_CLOCK_ONLY": True,         # 每日金句 (True=只在午夜)
        
        # --- 每日金句 ---
        "DAYS_AGO": 1,                   # 0為今天, 1為昨天...
        
        # --- Gemini AI 總結 ---
        "RECENT_MSG_HOURS": 5,           # 抓取範圍
        "AUTHOR_NAME_LIMIT": 4,          # 名字顯示長度
        "SHOW_DATE": False,              # 是否顯示日期
        "SHOW_SECONDS": False,           # 是否顯示秒數
        "SHOW_ATTACHMENTS": False,       # 是否顯示附件網址
        "SIMPLIFY_LINKS": True,          # 連結簡化
        "GEMINI_TOKEN_LIMIT": 120000,    # Token 上限
        "GEMINI_MODEL": "gemini-3-flash-preview", 
        "GEMINI_SUMMARY_FORMAT": """
依照以下md格式對各頻道總結，並且適時使用換行幫助閱讀，盡量不要省略成員名，不要多餘文字。如果有人提到何時要做什麼事，也請一併列出。
## [頻道名]
(請條列四五個重點但只能一層)\n
**提及的規劃**\n(請列出所有提到的時間規劃)\n
**結論**\n(如有結論請列出)\n
""",
        # --- 系統變數 ---
        "TZ": timezone(timedelta(hours=8))
    }

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
            source_ids = [int(x.strip()) for x in source_ids_str.split(',') if x.strip()]
            print(f"✅ 監聽頻道: {source_ids}")
        except ValueError:
            print(f"❌ SOURCE_CHANNEL_IDS 格式錯誤: {source_ids_str}")
    secrets['SOURCE_CHANNEL_IDS'] = source_ids

    # 4. Target Channel ID
    target_id = None
    try:
        t_id_str = os.getenv('TARGET_CHANNEL_ID')
        if t_id_str:
            target_id = int(t_id_str)
            print(f"✅ 目標頻道: {target_id}")
    except ValueError:
        print("❌ TARGET_CHANNEL_ID 格式錯誤")
    secrets['TARGET_CHANNEL_ID'] = target_id

    # 5. Target Preview ID
    preview_id = None
    try:
        p_id_str = os.getenv('TARGET_PREVIEW_ID')
        if p_id_str:
            preview_id = int(p_id_str)
            print(f"✅ 預覽頻道: {preview_id}")
    except ValueError:
        print("❌ TARGET_PREVIEW_ID 格式錯誤")
    secrets['TARGET_PREVIEW_ID'] = preview_id

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


# ==========================================
#              主要邏輯 (FEATURES)
# ==========================================

async def run_ai_summary(client, settings, secrets):
    if not settings["AI_SUMMARY_ENABLED"]:
        print("⏹️ AI 總結功能已關閉，跳過。")
        return

    hours = settings["RECENT_MSG_HOURS"]
    print(f">>> [AI Summary] 開始執行：抓取前 {hours} 小時訊息")
    
    tz = settings["TZ"]
    now = datetime.now(tz)
    target_time_ago = now - timedelta(hours=hours)
    collected_output = []

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
                
                # Mentions 處理
                if msg.mentions:
                    for user in msg.mentions:
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
                created_at_local = msg.created_at.astimezone(tz).strftime(time_fmt)
                author_name = msg.author.display_name[:settings["AUTHOR_NAME_LIMIT"]]

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

        final_messages_str = "\n".join(collected_output)
        print("   訊息收集完成，準備進行 AI 總結...")

        target_ch_id = secrets["TARGET_CHANNEL_ID"]
        gemini_key = secrets["GEMINI_API_KEY"]

        if final_messages_str and target_ch_id:
            target_ch = client.get_channel(target_ch_id)
            if target_ch and gemini_key:
                print("   🤖 呼叫 Gemini 中...")
                try:
                    ai_client = genai.Client(api_key=gemini_key)
                    prompt = f"請用繁體中文總結以下聊天內容\n{settings['GEMINI_SUMMARY_FORMAT']}\n\n{final_messages_str}"
                    
                    response = ai_client.models.generate_content(
                        model=settings["GEMINI_MODEL"],
                        contents=prompt,
                        config=types.GenerateContentConfig(max_output_tokens=settings["GEMINI_TOKEN_LIMIT"])
                    )
                    
                    if response.text:
                        start_str = target_time_ago.strftime('%Y年%m月%d日 %A %H:%M')
                        end_str = now.strftime('%H:%M')
                        report = (
                            f"# ✨ {recent_msg_hours} 小時重點摘要出爐囉！\n"
                            f"** 🕘 時間範圍：{start_time_str} ~ {end_time_str}**\n"
                            f"\n"
                            f"{summary_text}\n"
                            f"\n"
                            f">>> 🤖 重點摘要由業界領先的 Google Gemini AI 大型語言模型驅動。\n"
                            f"💡 AI總結內容僅供參考，敬請核實。\n"
                            f"🤓 使用模型：「{gemini_model}」。"
                        )
                        await target_ch.send(report)
                        print("   ✅ AI 總結已發送")
                except Exception as e:
                    print(f"   ❌ Gemini 錯誤: {e}")
                    await target_ch.send(f"⚠️ Gemini 總結失敗: {e}")
            elif not target_ch:
                print(f"   ⚠️ 找不到目標頻道 {target_ch_id}")
    except Exception as e:
        print(f"❌ AI Summary 執行錯誤: {e}")
    print()


async def run_daily_quote(client, settings, secrets):
    tz = settings["TZ"]
    now = datetime.now(tz)
    is_allow_time = (now.hour == 0)

    if settings["ZERO_CLOCK_ONLY"] and not is_allow_time:
        print(f"⏹️ [Daily Quote] 現在 {now.strftime('%H:%M')} 非執行時段 (00:xx)，跳過。")
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
    if best_message and target_ch:
        emoji_detail = " ".join([f"{str(r.emoji)} x{r.count}" for r in best_message.reactions])
        content = best_message.content or f"[**查看詳細**]({best_message.jump_url})"
        
        # Mentions 替換
        if best_message.mentions:
            for user in best_message.mentions:
                content = content.replace(f"<@{user.id}>", f"@{user.display_name}")
                content = content.replace(f"<@!{user.id}>", f"@{user.display_name}")

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
                extras.append(f"📎 [附件]: {att.url}")
        
        if extras: content += "\n\n" + "\n".join(extras)

        report = (
            f"# 🏆 **{target_date_str} 每日金句**\n"
            f"🔗 {best_message.jump_url}\n"
            f"👨‍💻 {best_message.author.mention}\n\n"
            f">>> {content}\n\n"
            f"🔥 **表情總數：{max_reactions}** ({emoji_detail})\n"
        )
        await target_ch.send(report)
        print("   ✅ 金句已發送")
    else:
        print("   ⚠️ 沒找到熱門訊息或無目標頻道")
    print()


async def run_link_screenshot(client, settings, secrets):
    if not settings["LINK_SCREENSHOT_ENABLED"]:
        print("⏹️ 連結截圖功能已關閉，跳過。")
        return

    hours = settings["RECENT_MSG_HOURS"]
    print(f">>> [Link Screenshot] 開始執行：連結截圖 ({hours} 小時內)")
    
    tz = settings["TZ"]
    now = datetime.now(tz)
    target_time_ago = now - timedelta(hours=hours)

    try:
        ipad_uuid, ipad_status = await asyncio.to_thread(get_best_ipad_13)
        if not ipad_uuid:
            print("   ⚠️ 無 iPad UUID，跳過")
            return

        # 開機檢查
        if ipad_status != "Booted":
            print("   🚀 啟動模擬器...")
            await asyncio.to_thread(subprocess.run, ["xcrun", "simctl", "boot", ipad_uuid])
            await asyncio.to_thread(subprocess.run, ["xcrun", "simctl", "bootstatus", ipad_uuid, "-b"])
        else:
            print("   ⚡️ 模擬器已就緒")

        # 收集連結
        captured_links = []
        for channel_id in secrets["SOURCE_CHANNEL_IDS"]:
            ch = client.get_channel(channel_id)
            if not ch: continue
            print(f"   掃描連結: #{ch.name}")
            async for msg in ch.history(after=target_time_ago, limit=None):
                urls = re.findall(r'(https?://\S+)', msg.content)
                for url in urls:
                    captured_links.append((url, msg))
        
        print(f"   共找到 {len(captured_links)} 個連結")

        target_ch = None
        if secrets["TARGET_PREVIEW_ID"]:
             target_ch = client.get_channel(secrets["TARGET_PREVIEW_ID"])
        
        if not target_ch:
            print(f"   ⚠️ 無預覽目標頻道 ({secrets.get('TARGET_PREVIEW_ID')})，僅截圖不發送")

        # 處理連結
        for idx, (url, msg) in enumerate(captured_links):
            print(f"   [{idx+1}/{len(captured_links)}] 處理: {url}")
            await asyncio.sleep(3) # 緩衝

            # 開啟網頁
            success_open = False
            for _ in range(2):
                res = await asyncio.to_thread(subprocess.run, ["xcrun", "simctl", "openurl", ipad_uuid, url])
                if res.returncode == 0:
                    success_open = True
                    break
                await asyncio.sleep(3)
            
            if not success_open:
                print("   ❌ 無法開啟連結")
                continue

            print("   ⏳ 等待渲染...")
            await asyncio.sleep(12)

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

        # 3. 執行 連結截圖
        await run_link_screenshot(self, self.settings, self.secrets)
        
        
        print('-------------------------------------------')
        print("🎉 所有排程執行完畢，Bot 關閉。")
        await self.close()

if __name__ == "__main__":
    # 讀取設定與變數
    settings_data = get_settings()
    secrets_data = get_secrets()

    if not secrets_data['TOKEN']:
        print("❌ 無法執行：缺少 TOKEN")
    else:
        # 啟動機器人
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        
        client = MyClient(settings=settings_data, secrets=secrets_data, intents=intents)
        client.run(secrets_data['TOKEN'])
