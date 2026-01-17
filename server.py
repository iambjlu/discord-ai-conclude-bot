import sys
sys.stdout.reconfigure(line_buffering=True)
import subprocess
import importlib.util

# --- 自動檢查依賴套件 ---
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
check_requirements()
# ----------------------

import discord
import asyncio
from datetime import datetime, timedelta, timezone
import re
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv

# 載入 .env 環境變數
load_dotenv()

# --- 讀取與檢查環境變數 ---
TOKEN = os.getenv('DISCORD_BOT_TOKEN')
if not TOKEN:
    print("❌ 錯誤: 未讀取到 DISCORD_BOT_TOKEN。")
    print("   - 若在本地執行，請確認 .env 檔案內有設定 DISCORD_BOT_TOKEN。")
    print("   - 若在 GitHub Actions 執行，請確認 Settings -> Secrets 內已設定。")
else:
    # 遮罩顯示前幾碼，確認有讀到
    print(f"✅ 成功讀取 DISCORD_BOT_TOKEN (長度: {len(TOKEN)}, 前綴: {TOKEN[:5]}***)")

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("⚠️ 警告: 未讀取到 GEMINI_API_KEY，AI 總結功能將無法使用。")
else:
    print("✅ 成功讀取 GEMINI_API_KEY")

source_ids_str = os.getenv('SOURCE_CHANNEL_IDS', '')
if not source_ids_str:
    print("⚠️ 警告: SOURCE_CHANNEL_IDS 未設定，將無法抓取頻道訊息。")
    SOURCE_CHANNEL_IDS = []
else:
    try:
        SOURCE_CHANNEL_IDS = [int(x.strip()) for x in source_ids_str.split(',') if x.strip()]
        print(f"✅ 成功讀取監聽頻道清單: {SOURCE_CHANNEL_IDS}")
    except ValueError:
        print(f"❌ 錯誤: SOURCE_CHANNEL_IDS 格式不正確 (應為逗號分隔的數字): {source_ids_str}")
        SOURCE_CHANNEL_IDS = []

target_ch_id_str = os.getenv('TARGET_CHANNEL_ID')
TARGET_CHANNEL_ID = None
if target_ch_id_str:
    try:
        TARGET_CHANNEL_ID = int(target_ch_id_str)
        print(f"✅ 成功讀取目標發送頻道: {TARGET_CHANNEL_ID}")
    except ValueError:
        print(f"❌ 錯誤: TARGET_CHANNEL_ID 格式不正確 (應為數字): {target_ch_id_str}")
else:
    print("⚠️ 警告: TARGET_CHANNEL_ID 未設定，將無法發送訊息。")

target_preview_id_str = os.getenv('TARGET_PREVIEW_ID')
TARGET_PREVIEW_ID = None
if target_preview_id_str:
    try:
        TARGET_PREVIEW_ID = int(target_preview_id_str)
        print(f"✅ 成功讀取預覽發送頻道: {TARGET_PREVIEW_ID}")
    except ValueError:
        print(f"❌ 錯誤: TARGET_PREVIEW_ID 格式不正確 (應為數字): {target_preview_id_str}")
else:
    print("⚠️ 警告: TARGET_PREVIEW_ID 未設定，連結預覽截圖將無法發送 (或需 fallback)。")
    # 如果希望沒設定就回退到預設頻道，可以打開下面這行：
    # TARGET_PREVIEW_ID = TARGET_CHANNEL_ID 

# ------------------------

class MyClient(discord.Client):
    async def on_ready(self):
        print(f'已登入：{self.user}，開始掃描歷史熱門訊息...')

        #快速設定 ############################################
        days_ago = 1          # 每日金句: 0為今天, 1為昨天...
        zero_clock_only = True # 每日金句: True=只在午夜執行, False=每次都執行  (預設 True)
        ai_summary_zero_clock_only = False # AI總結: True=只在午夜執行, False=每次都執行  (預設 False)
        link_screenshot_zero_clock_only = False # 連結截圖: True=只在午夜執行, False=每次都執行  (預設 False)
        
        # Gemini 重點摘要設定 #################################
        recent_msg_hours = 4  # 抓取最近 x 小時的訊息
        author_name_limit = 4 # 名字顯示長度限制
        show_date = False      # 是否顯示日期
        show_seconds = False   # 是否顯示秒數
        show_attachments = False # 是否顯示附件網址
        simplify_links = True  # 是否將連結簡化為標題
        gemini_token_limit = 120000 # 總結輸出的 Token 上限
        gemini_model = "gemini-3-flash-preview" # 使用的模型
        # 要求的總結格式
        gemini_summary_format = """
依照以下md格式對各頻道總結，並且適時使用換行幫助閱讀，盡量不要省略成員名，不要多餘文字。
## [頻道名]
(請條列四五個重點但只能一層)\n
**結論**\n(如有結論請列出)\n
**AI點評**\n(以Z世代的口吻給出幽默的見解)\n
"""
        ######################

        # 共用時間與檢查
        tz = timezone(timedelta(hours=8))
        now = datetime.now(tz)
        is_allow_time = (now.hour == 0) # 簡化判斷: 0點時段 (00:00 ~ 00:59)

        # --- 新增功能：AI重點摘要模組 ---
        if ai_summary_zero_clock_only and not is_allow_time:
            print(f"現在時間 {now.strftime('%H:%M')} 非 AI 總結執行時段，跳過。")
        else:
            print(f">>> 開始執行：抓取當下之前 {recent_msg_hours} 小時訊息")
            collected_output = [] # 用於暫存所有訊息的列表

            try:
                # 使用上方定義的時間
                target_time_ago = now - timedelta(hours=recent_msg_hours)

                # 決定時間格式
                time_fmt = ""
                if show_date:
                    time_fmt += "%Y/%m/%d "
                time_fmt += "%H:%M"
                if show_seconds:
                    time_fmt += ":%S"

                for channel_id in SOURCE_CHANNEL_IDS:
                    ch = self.get_channel(channel_id)
                    if not ch:
                        continue
                    
                    print(f"正在掃描({recent_msg_hours}hr): #{ch.name}")
                    
                    channel_msgs = []
                    async for msg in ch.history(after=target_time_ago, limit=None):
                        # 處理 Mentions (替換成名字前4字)
                        content = msg.content
                        if msg.mentions:
                            for user in msg.mentions:
                                u_name = user.display_name
                                if len(u_name) > author_name_limit:
                                    u_name = u_name[:author_name_limit]
                                # 替換兩種可能的 mention 格式
                                content = content.replace(f"<@{user.id}>", f"@{u_name}")
                                content = content.replace(f"<@!{user.id}>", f"@{u_name}")

                        # 處理轉發訊息 (Forwarded Messages / Snapshots)
                        if hasattr(msg, 'message_snapshots') and msg.message_snapshots:
                            for snapshot in msg.message_snapshots:
                                # 嘗試取得轉發內容
                                s_content = getattr(snapshot, 'content', '')
                                if s_content:
                                    content += f"[轉發內容]: {s_content}"
                                
                                # 嘗試取得轉發附件
                                if hasattr(snapshot, 'attachments'):
                                    if show_attachments:
                                        for att in snapshot.attachments:
                                            content += f" (轉發附件 {att.url})"
                                    elif snapshot.attachments:
                                        content += " (轉發附件)"

                        # 處理連結簡化 (變數控制)
                        if simplify_links:
                            # 1. 先嘗試用 Embed 標題替換
                            if msg.embeds:
                                for embed in msg.embeds:
                                    if embed.title:
                                        # 若 embed.url 存在且在內容中，直接替換
                                        if embed.url and embed.url in content:
                                            content = content.replace(embed.url, f"(連結 {embed.title})")
                                        # 若內容本身像是純網址，也直接替換
                                        elif content.strip().startswith("http"):
                                            content = f"(連結 {embed.title})"

                            # 2. 剩下的網址如果沒被替換，就只留網域
                            # 尋找還存在的 http/https 連結
                            def domain_replacer(match):
                                url = match.group(0)
                                try:
                                    # 簡單取出 :// 後面直到遇到 / 或結束
                                    no_proto = url.split("://", 1)[1]
                                    domain = no_proto.split("/", 1)[0]
                                    return f"(連結 {domain})"
                                except:
                                    return url
                            
                            content = re.sub(r'https?://\S+', domain_replacer, content)

                        # 處理自定義表情符號 (變成 (貼圖))
                        content = re.sub(r'<a?:\w+:\d+>', '(貼圖)', content)

                        # 轉換時間顯示
                        created_at_local = msg.created_at.astimezone(tz).strftime(time_fmt)
                        
                        # 處理名字顯示 (截斷)
                        author_name = msg.author.display_name
                        if len(author_name) > author_name_limit:
                            author_name = author_name[:author_name_limit]
                        
                        # 若內容為空且無附件，則跳過此訊息
                        if not content.strip() and not msg.attachments:
                            continue
                        
                        channel_msgs.append(f"{author_name}@{created_at_local}: {content}")
                        
                        # 處理附件顯示
                        if msg.attachments:
                            if show_attachments:
                                for attachment in msg.attachments:
                                    channel_msgs.append(f"(附件 {attachment.url})")
                            else:
                                channel_msgs.append("(附件)")
                    
                    # 如果該頻道有訊息，才加入 output
                    if channel_msgs:
                        collected_output.append(f"--[#{ch.name}]")
                        collected_output.extend(channel_msgs)

                # 將抓到的全部訊息存成一個字串變數
                final_messages_str = "\n".join(collected_output)
                print(final_messages_str)

                # 回傳到 Target Channel
                if final_messages_str:
                    target_ch = self.get_channel(TARGET_CHANNEL_ID)
                    if target_ch:
                        # Discord 訊息限制 2000 字，若超過需分段傳送
                        # if len(final_messages_str) > 1900:
                        #     for i in range(0, len(final_messages_str), 1900):
                        #         await target_ch.send(final_messages_str[i:i+1900])
                        # else:
                        #     await target_ch.send(final_messages_str)
                        # print(f"✅ 已將 {recent_msg_hours} 小時訊息摘要發送至頻道: {target_ch.name}")

                        # --- Gemini AI 總結 ---
                        if GEMINI_API_KEY:
                            print("🤖 正在呼叫 Gemini 進行總結...")
                            try:
                                client = genai.Client(api_key=GEMINI_API_KEY)
                                
                                prompt = f"請用繁體中文總結以下聊天內容\n{gemini_summary_format}\n\n{final_messages_str}"
                                
                                response = client.models.generate_content(
                                    model=gemini_model,
                                    contents=prompt,
                                    config=types.GenerateContentConfig(
                                        max_output_tokens=gemini_token_limit
                                    )
                                )
                                
                                summary_text = response.text
                                if summary_text:
                                    # 組裝 Discord 訊息格式
                                    start_time_str = target_time_ago.strftime('%m月%d日 (%a) %H:%M')
                                    end_time_str = now.strftime('%H:%M')
                                    
                                    summary_report = (
                                        f"# ✨ {recent_msg_hours} 小時重點摘要出爐囉！\n"
                                        f"** 🕘 時間範圍：{start_time_str} ~ {end_time_str}**\n"
                                        f"\n"
                                        f"{summary_text}\n"
                                        f"\n"
                                        f">>> 🤖 重點摘要由業界領先的 Google Gemini AI 大型語言模型驅動。\n"
                                        f"💡 AI總結內容僅供參考，敬請核實。\n"
                                        f"🤓 使用模型：「{gemini_model}」。"
                                    )

                                    await target_ch.send(summary_report)
                                    print("✅ Gemini 總結已發送")
                            except Exception as gemini_err:
                                print(f"❌ Gemini API Error: {gemini_err}")
                                await target_ch.send(f"**⚠️ Gemini 總結失敗**\n{gemini_err}") # 失敗時不一定要回傳到頻道，看需求
                    else:
                        print(f"⚠️ 找不到目標頻道 ID: {TARGET_CHANNEL_ID}")

                print(f">>> {recent_msg_hours} 小時訊息抓取完成\n")
            except Exception as e:
                print(f"抓取 {recent_msg_hours} 小時訊息時發生錯誤: {e}")
        
        # --- 新增功能：連結截圖模組 ---
        if link_screenshot_zero_clock_only and not is_allow_time:
             print(f"現在時間 {now.strftime('%H:%M')} 非連結截圖執行時段，跳過。")
        else:
            print(f">>> 開始執行：連結截圖 ({recent_msg_hours} 小時內)")
            subprocess.run(["open", "http://captive.apple.com"])
            await asyncio.sleep(10)
            try:
                target_time_ago = now - timedelta(hours=recent_msg_hours)
                
                # 收集所有連結
                captured_links = [] # List of tuples (url, message_object)

                for channel_id in SOURCE_CHANNEL_IDS:
                    ch = self.get_channel(channel_id)
                    if not ch: continue
                    
                    print(f"正在掃描連結: #{ch.name}")
                    async for msg in ch.history(after=target_time_ago, limit=None):
                         # 簡單的正則表達式抓取 http/https 連結
                         urls = re.findall(r'(https?://\S+)', msg.content)
                         for url in urls:
                             captured_links.append((url, msg))
                
                print(f"共找到 {len(captured_links)} 個連結，準備開始截圖程序...")
                
                # 依序處理
                for idx, (url, msg) in enumerate(captured_links):
                    print(f"處理第 {idx+1}/{len(captured_links)} 個連結: {url}")
                    
                    # 1. 用系統預設瀏覽器打開 URL
                    # 注意: subprocess.run 是同步阻塞的，但在本地單機腳本通常可接受
                    subprocess.run(["open", url])

                    # 2. 等 5 秒讓網頁跑一下 (使用 asyncio.sleep 避免完全卡死 Heartbeat)
                    await asyncio.sleep(20)
                    
                    # 3. 使用 Mac 內建的 screencapture 指令截取整個螢幕
                    screenshot_filename = f"screenshot_temp.jpg"
                    subprocess.run(["sudo", "killall", "-9", "UserNotificationCenter"], stderr=subprocess.DEVNULL)
                    subprocess.run(["screencapture", "-x", screenshot_filename])
                    
                    # 4. 回傳到 Target Channel
                    target_ch = None
                    if TARGET_PREVIEW_ID:
                        target_ch = self.get_channel(TARGET_PREVIEW_ID)
                    
                    if not target_ch:
                         print(f"⚠️ 找不到預覽目標頻道 ID: {TARGET_PREVIEW_ID}")
                    
                    if target_ch:
                        # 準備文字訊息
                        content_text = (
                            f"📸 **網頁預覽**\n"
                            f">>> 💬 訊息來源: {msg.jump_url}\n"
                            f"👤 發送者: @{msg.author.name}\n"
                            f"🕒 發送時間: {msg.created_at.astimezone(tz).strftime('%m/%d (%a) %H:%M')}\n"
                            f"🔗 原始連結: <{url}>\n"
                        )
                        
                        # 發送圖片
                        if os.path.exists(screenshot_filename):
                            file = discord.File(screenshot_filename)
                            await target_ch.send(content=content_text, file=file)
                            # 刪除暫存檔
                            os.remove(screenshot_filename)
                        else:
                            await target_ch.send(content=content_text + "\n(❌ 截圖檔案未產生)")
                    
                    # 每個連結處理完稍微休息一下，避免瀏覽器開太快炸裂
                    await asyncio.sleep(1)

                print(f">>> 連結截圖程序完成\n")

            except Exception as e:
                print(f"執行連結截圖時發生錯誤: {e}")
        # ------------------------------------------------
        # 每日金句模組(已在上方定義 tz, now, is_allow_time)

        if zero_clock_only and not is_allow_time:
            print(f"現在時間 {now.strftime('%H:%M')} 非每日金句執行時段。")
            await self.close()
            return

        target_start = (now - timedelta(days=days_ago)).replace(hour=0, minute=0, second=0, microsecond=0)
        target_end = target_start + timedelta(days=1)

        target_date_str = target_start.strftime('%Y-%m-%d')
        print(f"📅 正在查詢日期：{target_date_str}")

        best_message = None
        max_reactions = 0

        for channel_id in SOURCE_CHANNEL_IDS:
            channel = self.get_channel(channel_id)
            if not channel:
                print(f"找不到頻道 {channel_id}，跳過。")
                continue

            print(f"正在掃描頻道：#{channel.name}...")

            async for message in channel.history(after=target_start, before=target_end, limit=None):
                # 如果訊息沒表情或作者是 Bot，可以考慮跳過（看你需求）
                if not message.reactions:
                    continue

                reaction_count = sum(r.count for r in message.reactions)

                if reaction_count > max_reactions:
                    max_reactions = reaction_count
                    best_message = message

        # 準備發送結果
        target_channel = self.get_channel(TARGET_CHANNEL_ID)

        if best_message and target_channel:
            emoji_detail = " ".join([f"{str(r.emoji)} x{r.count}" for r in best_message.reactions])
            content = best_message.content if best_message.content else f"[**無法言喻的訊息，點一下查看**]({best_message.jump_url})"

            # 處理 Mentions (避免打擾成員，僅顯示文字)
            if best_message.mentions:
                for user in best_message.mentions:
                    content = content.replace(f"<@{user.id}>", f"@{user.display_name}")
                    content = content.replace(f"<@!{user.id}>", f"@{user.display_name}")

            # --- 新增：處理轉發與附件 (每日金句) ---
            extra_infos = []

            # 1. 處理轉發訊息 (Snapshots)
            if hasattr(best_message, 'message_snapshots') and best_message.message_snapshots:
                for snapshot in best_message.message_snapshots:
                    s_content = getattr(snapshot, 'content', '')
                    if s_content:
                        extra_infos.append(f"🔄 [轉發內容]: {s_content}")
                    
                    if hasattr(snapshot, 'attachments') and snapshot.attachments:
                        for att in snapshot.attachments:
                            extra_infos.append(f"📎 [轉發附件]: {att.url}")

            # 2. 處理本身附件
            if best_message.attachments:
                for att in best_message.attachments:
                    extra_infos.append(f"📎 [附件]: {att.url}")

            # 若有額外資訊，附加在 content 後方
            if extra_infos:
                content += "\n\n" + "\n".join(extra_infos)
            # -------------------------------------

            # 組裝 Discord 訊息格式
            report = (
                f"# 🏆 **{target_date_str} 每日金句出爐囉！**\n"
                f"🔗 來源: {best_message.jump_url}\n"
                f"👨‍💻 作者: {best_message.author.mention}\n\n"
                f">>> {content}\n\n"
                f"🔥 **總表情數：{max_reactions}**\n"
                f"📊 **表情明細：** {emoji_detail}\n"
            )

            await target_channel.send(report)
            print(f"✅ 戰報已發送到目標頻道！")
        else:
            msg = f"哎呀，{target_date_str} 這天似乎沒什麼熱門訊息。"

            if target_channel:
                await target_channel.send(msg)
            print(msg)

        await self.close()

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = MyClient(intents=intents)
client.run(TOKEN)
