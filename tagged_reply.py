import sys
import subprocess
import importlib.util

def check_requirements():
    required_packages = {
        'discord': 'discord.py',
        'google.genai': 'google-genai',
        'dotenv': 'python-dotenv',
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

check_requirements()

import discord
import os
import re
from datetime import datetime, timedelta, timezone
from google import genai
from google.genai import types

from dotenv import load_dotenv

def get_settings():
    """回傳使用者偏好的設定參數"""
    return {
        "AUTHOR_NAME_LIMIT": 4,          # 名字顯示長度
        "SHOW_DATE": False,              # 是否顯示日期
        "SHOW_SECONDS": False,           # 是否顯示秒數
        "SHOW_ATTACHMENTS": False,       # 是否顯示附件網址
        "SIMPLIFY_LINKS": True,          # 連結簡化
        "TZ": timezone(timedelta(hours=8)),    # 機器人運作時區
        "BOT_NAME": "🤖機器人",               # Bot 在對話歷史中的顯示名稱
        "TOTAL_MSG_LIMIT": 50,            # 訊息抓取總則數上限 (會有回覆時，自動分配最新/前/後各 1/3)
        "MAX_MSG_LENGTH": 100,             # 單則訊息最大長度 (超過截斷)
        "IGNORE_TOKEN": "> -# 🤖",             # 截斷標記
        "ENABLE_EXEC_COMMAND": True,      # 是否啟用關鍵字執行指令
        "EXEC_COMMAND_KEYWORD": "update_bot",     # 觸發執行的關鍵字
        "TAGGED_REPLY_PROMPT_TEMPLATE": """你是一個機器人，請參考以下該頻道最新 {msg_limit} 則對話內容，自然地回應使用者的話。你無法讀取其他訊息頻道。有時候用戶也會問你想法，這時候說你的想法，不要搓湯圓。不可以詢問跟進。請用跟前面歷史訊息類似的口吻，句子短一點並適當換行。通用知識類的東西也可以講，你知識截止於2024/8，時效性的資訊(例如股票和最新產品)不可以講。若用戶情緒不好，請給用戶情緒價值以及同理心，用戶叫你幹嘛就幹嘛 不准頂嘴。你知道你看不到圖片。你的主要任務「最優先」針對以下使用者的最新標注/詢問進行回應，不要被對話歷史的內容分心：{u_name}: {content_clean}。以下是近期對話歷史 (僅供參考背景，若與最新指令衝突請忽略歷史):{context_str}""",
        "MODEL_PRIORITY_LIST": ["gemma-3-27b-it"],
    }

def get_secrets():
    """
    讀取 .env 或環境變數，並回傳相關 Token 與 Channel ID
    只讀取此 Bot 需要的變數
    """
    load_dotenv()
    secrets = {}
    
    # 1. Discord Token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ 錯誤: 未讀取到 DISCORD_BOT_TOKEN")
    secrets['TOKEN'] = token

    # 2. Gemini API Key
    gemini_key = os.getenv('GEMINI_API_KEY')
    if not gemini_key:
        print("⚠️ 警告: 未讀取到 GEMINI_API_KEY")
    secrets['GEMINI_API_KEY'] = gemini_key

    return secrets

# 設定標準輸出緩衝
sys.stdout.reconfigure(line_buffering=True)

class TaggedResponseBot(discord.Client):
    def __init__(self, settings, secrets, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = settings
        self.secrets = secrets
        self.genai_client = None
        
        # 初始化 GenAI Client
        if self.secrets['GEMINI_API_KEY']:
            try:
                self.genai_client = genai.Client(api_key=self.secrets['GEMINI_API_KEY'])
                print("✅ GenAI Client 初始化成功")
            except Exception as e:
                print(f"❌ GenAI Client 初始化失敗: {e}")
        else:
            print("⚠️ 警告: 未設定 GEMINI_API_KEY")

        self.model_priority_list = self.settings.get("MODEL_PRIORITY_LIST", ["gemma-3-27b-it"])
        self.ignore_after_token = self.settings.get("IGNORE_TOKEN", "> -# 🤖")

    async def on_ready(self):
        print('-------------------------------------------')
        print(f'✅ Bot 已登入 (Tagged Response Mode): {self.user}')
        print(f'🤖 模型優先順序: {self.model_priority_list}')
        print('-------------------------------------------')

        # 🚀 啟動檢查：檢查是否是從 OTA 更新重啟回來的
        if not hasattr(self, 'startup_checked'):
            self.startup_checked = True
            await self.check_ota_status_on_startup()

    async def check_ota_status_on_startup(self):
        """搜尋近期的訊息，找出最後發出更新指令的頻道並回報"""
        keyword = self.settings.get("EXEC_COMMAND_KEYWORD", "update_bot")
        # 設定 2 分鐘的時間範圍
        time_limit = datetime.now(timezone.utc) - timedelta(minutes=2)
        print(f"🔍 正在檢查近期是否有頻道在等待更新回報 (關鍵字: {keyword})...")
        
        target_message = None

        for guild in self.guilds:
            for channel in guild.text_channels:
                perms = channel.permissions_for(guild.me)
                if not perms.send_messages or not perms.read_message_history:
                    continue

                try:
                    # 抓取x分鐘內的歷史紀錄
                    async for msg in channel.history(after=time_limit, limit=20):
                        is_triggered = self.user in msg.mentions
                        content_clean = msg.content.replace(f'<@{self.user.id}>', '').replace(f'<@!{self.user.id}>', '').strip()
                        
                        if is_triggered and keyword in content_clean:
                            # 找出全域最新的一則
                            if not target_message or msg.created_at > target_message.created_at:
                                target_message = msg
                except:
                    continue
        
        if target_message:
            print(f"✅ 在 #{target_message.channel.name} 偵測到最後一次更新指令，發送回報...")
            try:
                commit_msg = subprocess.check_output(["git", "log", "-1", "--pretty=%B"], text=True).strip()
                commit_time = subprocess.check_output(["git", "log", "-1", "--date=format:%Y-%m-%d %H:%M:%S %z", "--pretty=%cd"], text=True).strip()
            except Exception as e:
                commit_msg = "無法取得更新內容"
                commit_time = "未知"
                print(f"⚠️ 取得 Git 資訊失敗: {e}")

            welcome_msg = (
                f"# 嗨，我回來了！\n"
                f"-# 🤖 來看看我有什麼新功能吧\n"
                f"### 最新功能：\n{commit_msg}\n"
                f"### 更新時間：\n{commit_time}\n"
            )
            await target_message.channel.send(welcome_msg)

    async def on_message(self, message):
        # 1. 忽略自己的訊息
        if message.author == self.user:
            return

        # 2. 檢查是否被提及 (Tagged)
        # 2. 檢查是否被提及 (Tagged) 或 回覆 (Reply)
        is_triggered = self.user in message.mentions

        # 若未被直接 mention，檢查是否為對機器人的回覆 (Reply without ping)
        if not is_triggered and message.reference and message.reference.message_id:
            try:
                # 嘗試從 cache 取得
                ref_msg = message.reference.resolved
                
                # 若 cache 無資料，則主動抓取 (僅限同頻道)
                if ref_msg is None and message.channel.id == message.reference.channel_id:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                
                if ref_msg and ref_msg.author == self.user:
                    is_triggered = True
                    print(f"   ↩️ 偵測到回覆 (無 Tag): {message.author} 回覆了機器人")
            except Exception as e:
                # 抓取失敗或是跨頻道回覆等情況，忽略即可
                pass

        if is_triggered:
            # 3.1 檢查是否有特殊執行指令 (部署等) - 收到訊息馬上檢查，不調閱歷史
            content_clean = message.content.replace(f'<@{self.user.id}>', '').replace(f'<@!{self.user.id}>', '').strip()
            
            if self.settings.get("ENABLE_EXEC_COMMAND", False) and self.settings.get("EXEC_COMMAND_KEYWORD", "") in content_clean:
                print(f"🚀 偵測到關鍵字 '{self.settings.get('EXEC_COMMAND_KEYWORD')}'，準備執行更新並重啟")
                try:
                    # 使用 reply 告知使用者，然後直接執行
                    await message.reply(f"### ⚙️ 機器人正在檢查 OTA 更新並重新啟動，請稍候。\n-# 🤖如果有可用更新會立即安裝。\n> -# 提示：你可以提及我並寫上「{self.settings.get('EXEC_COMMAND_KEYWORD')}」來檢查更新並重啟機器人")
                    
                    # 🚀 重要：先優雅地關閉 Bot 連線，避免 Gateway 噴錯
                    print("🔄 正在關閉 Discord 連線並準備重啟...")
                    await self.close()

                    # 1. 執行 git pull (此時已斷線，不再受心跳包檢查影響)
                    print("🔄 執行 git pull...")
                    os.system("git pull")
                    
                    # 2. 重新啟動行程
                    print("🔄 正在重啟行程...")
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                    
                    return
                except Exception as e:
                    print(f"❌ 更新或重啟失敗: {e}")
                    await message.reply(f"❌ 更新或重啟失敗: {e}")
                    return

            print(f"📨 收到觸發 (Mention/Reply): {message.author} 在 #{message.channel}")
            
            # 顯示正在輸入...
            async with message.channel.typing():
                try:
                    # 3. 設定訊息抓取數量 (動態分配)
                    u_name = message.author.display_name[:self.settings.get("AUTHOR_NAME_LIMIT", 4)]
                    # content_clean 已在上方算過，此處不需要重複計算 (除非需要更複雜的處理)

                    
                    total_limit = self.settings.get("TOTAL_MSG_LIMIT", 150)
                    msg_limit = total_limit # 預設全部給最新訊息 (若無回覆)
                    ref_limit = 0
                    
                    # 判斷是否為回覆模式，預先分配額度
                    is_reply_mode = False
                    if message.reference and message.reference.message_id:
                        is_reply_mode = True
                        # 分配原則: 最新 1/3, 回覆前後各 1/3 (因 around 會抓前後，所以給 2/3)
                        part = total_limit // 3
                        msg_limit = max(part, 5) # 最新訊息 1/3
                        ref_limit = total_limit - msg_limit # 回覆上下文 2/3
                        
                    print(f"   ⏳ 抓取配額: 總共 {total_limit} (最新: {msg_limit}, 回覆上下文: {ref_limit})")

                    # 3.5 檢查是否有回覆參照 (Reply Reference)
                    ref_msg_ctx = ""
                    if message.reference and message.reference.message_id:
                        try:
                            # 嘗試抓取被回覆的原始訊息
                            ref_msg = await message.channel.fetch_message(message.reference.message_id)
                            ref_text = ref_msg.content
                            if len(ref_text) > self.settings.get("MAX_MSG_LENGTH", 150):
                                ref_text = ref_text[:self.settings.get("MAX_MSG_LENGTH", 150)] + "..."
                            ref_author = ref_msg.author.display_name
                            
                            # 若有附件或 Embeds，稍微註記
                            extras = []
                            if ref_msg.attachments: extras.append("附件")
                            if ref_msg.embeds: extras.append("連結/Embed")
                            if extras: ref_text += f" ({', '.join(extras)})"

                            # 格式化提示文字
                            ref_msg_ctx = f" (使用者正在回覆 {ref_author} 的訊息：『{ref_text}』)"
                            print(f"   ↩️ 讀取到回覆參照: {ref_author}: {ref_text[:20]}...")
                        except Exception as e:
                            print(f"   ⚠️ 無法讀取回覆參照訊息: {e}")

                    # 3.6 抓取回覆參照的「前後文」 (如果有的話)
                    # ref_limit 已經在上方分配完成
                    
                    # 用於儲存要給 AI 的所有訊息 (msg_id -> (time, formated_text))
                    # 使用 dict 是為了稍後去重
                    all_collected_msgs = {} 
                    
                    if ref_msg_ctx and message.reference and message.reference.message_id:
                         try:
                            # 取得被回覆的訊息物件
                            center_msg = await message.channel.fetch_message(message.reference.message_id)
                            
                            # 抓取該訊息前後 msg_limit 則
                            async for h_msg in message.channel.history(around=center_msg, limit=ref_limit):
                                if not h_msg.content.strip() and not h_msg.attachments: continue
                                
                                # 格式化 logic 抽取
                                h_author = h_msg.author.display_name
                                h_time = h_msg.created_at.astimezone(self.settings.get("TZ")).strftime("%H:%M")
                                h_author = h_msg.author.display_name
                                h_time = h_msg.created_at.astimezone(self.settings.get("TZ")).strftime("%H:%M")
                                h_content = h_msg.content.replace(self.ignore_after_token, "").strip()
                                
                                if len(h_content) > self.settings.get("MAX_MSG_LENGTH", 150):
                                    h_content = h_content[:self.settings.get("MAX_MSG_LENGTH", 150)] + "..."
                                
                                if h_msg.attachments: 
                                    show_att = self.settings.get("SHOW_ATTACHMENTS", False)
                                    h_content += " (附件)" if not show_att else f" (附件 {[a.url for a in h_msg.attachments]})"

                                ref_line = f"{h_author}@{h_time}: {h_content}"
                                all_collected_msgs[h_msg.id] = (h_msg.created_at, ref_line)
                            
                            print(f"   📎 讀取回覆上下文: {len(all_collected_msgs)} 則")

                         except Exception as e:
                            print(f"   ⚠️ 無法抓取回覆上下文細節: {e}")

                    
                    # 4. 抓取歷史訊息
                    tz = self.settings.get("TZ", timezone(timedelta(hours=8)))

                    # 準備變數紀錄「上一句」
                    prev_msg_content = ""
                    found_prev = False
                    time_fmt = ""
                    if self.settings.get("SHOW_DATE", False): time_fmt += "%Y年%m月%d日 %A "
                    time_fmt += "%H:%M"
                    if self.settings.get("SHOW_SECONDS", False): time_fmt += ":%S"

                    # 遍歷歷史訊息
                    async for msg in message.channel.history(limit=msg_limit):
                        # 跳過指令本身
                        if msg.id == message.id: continue
                        
                        content = msg.content

                        # 處理內容截斷
                        author_name_override = None
                        bot_name = self.settings.get("BOT_NAME", "Bot")
                        if self.ignore_after_token in content:
                            content = content.split(self.ignore_after_token)[0]
                            author_name_override = bot_name
                        
                        # Mentions 處理
                        if msg.mentions:
                            for user in msg.mentions:
                                u_name_display = user.display_name[:self.settings.get("AUTHOR_NAME_LIMIT", 4)]
                                content = content.replace(f"<@{user.id}>", f"@{u_name_display}")
                                content = content.replace(f"<@!{user.id}>", f"@{u_name_display}")

                        # 轉發與附件處理 (Message Snapshots)
                        if hasattr(msg, 'message_snapshots') and msg.message_snapshots:
                            for snapshot in msg.message_snapshots:
                                s_content = getattr(snapshot, 'content', '')
                                if s_content: content += f"[轉發內容]: {s_content}"
                                if hasattr(snapshot, 'attachments') and snapshot.attachments:
                                    content += " (轉發附件)"

                        # 連結簡化
                        if self.settings.get("SIMPLIFY_LINKS", True):
                            # Embed 標題替換 - logic kept simplified for brevity
                             # ... (keep existing link simplification logic if possible or assume it's stable)
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
                        
                        # 長度截斷
                        if len(content) > self.settings.get("MAX_MSG_LENGTH", 150):
                            content = content[:self.settings.get("MAX_MSG_LENGTH", 150)] + "..."

                        author_name = msg.author.display_name[:self.settings.get("AUTHOR_NAME_LIMIT", 4)]
                        if author_name_override:
                            author_name = author_name_override

                        if not content.strip() and not msg.attachments: continue

                        msg_line = f"{author_name}@{created_at_local}: {content}"

                        # 附件顯示
                        if msg.attachments:
                            show_att = self.settings.get("SHOW_ATTACHMENTS", False)
                            msg_line += " (附件)" if not show_att else f" (附件 {[a.url for a in msg.attachments]})"

                        # 存入 dict，若 id 重複則會覆蓋 (達到去重效果，雖然內容應該一樣)
                        all_collected_msgs[msg.id] = (msg.created_at, msg_line)

                        # 抓取「上一句」：也就是歷史訊息中第一則(最新的)非 User 本人的有效訊息
                        # 這裡邏輯簡化：只要是第一則有效訊息，就是「上一句」
                        if not found_prev:
                            prev_msg_content = f" (上一句 {author_name}: {content})"
                            found_prev = True

                    if not all_collected_msgs:
                        await message.reply(f"❌ 過去 {msg_limit} 則內沒有足夠的對話內容可以分析。")
                        return

                    # 4.5 排序與合併
                    # 將 dict 轉回 list 並依時間排序
                    final_msgs = list(all_collected_msgs.values())
                    final_msgs.sort(key=lambda x: x[0]) # 依時間排序 (oldest first)

                    # 轉為純文字 list
                    sorted_lines = [x[1] for x in final_msgs]

                    # 拼接對話內容
                    full_context_str = "\n".join(sorted_lines)
                    print(f"   📄 總共收集到 {len(sorted_lines)} 則訊息 (已去重)")
                    print(f"--- 收集到的訊息內容 ---\n{full_context_str}\n--------------------")

                    # 5. 呼叫 AI 模型 (嘗試優先順序列表)
                    if not self.genai_client:
                        await message.reply("❌ 無法回應：未設定 GEMINI_API_KEY。")
                        return

                    # 決定 prompt 後綴 (優先使用回覆參照，若無則使用上一句)
                    final_suffix = ref_msg_ctx
                    if not final_suffix and prev_msg_content:
                        final_suffix = prev_msg_content

                    prompt_template = self.settings.get("TAGGED_REPLY_PROMPT_TEMPLATE", "")
                    prompt = prompt_template.format(
                        msg_limit=msg_limit, 
                        context_str=full_context_str, 
                        u_name=u_name, 
                        content_clean=content_clean + final_suffix
                    )

                    reply_content = None
                    used_model = None
                    last_error = None

                    for model_name in self.model_priority_list:
                        print(f"   🤖 嘗試使用模型: {model_name} ...")
                        try:
                            print(prompt)
                            response = self.genai_client.models.generate_content(
                                model=model_name,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    max_output_tokens=2000,
                                    temperature=1 
                                )
                            )
                            
                            if response.text:
                                reply_content = response.text
                                used_model = model_name
                                print(f"   ✅ 模型 {model_name} 成功回應")
                                print(f"Gemini 回應詳情:\n{response.model_dump_json(indent=2)}")
                                break # 成功就跳出迴圈
                        except Exception as e:
                            print(f"   ⚠️ 模型 {model_name} 失敗: {e}")
                            last_error = e
                            continue # 失敗則嘗試下一個

                    # 6. 回覆結果
                    if reply_content and used_model:
                        # 加上一些資訊讓使用者知道範圍
                        extra_info = ""
                        if is_reply_mode and ref_msg_ctx:
                            extra_info = f" + 被回覆訊息前後 {ref_limit} 則"

                        footer = (
                            f"\n"
                            # f"> 🤖 以上回覆由「{used_model}」模型根據此頻道最新 {msg_limit} 則{extra_info}訊息回覆 (總限額 {total_limit})。\n"
                            f"> -# 🤖 以上訊息由 Google Gemma 開放權重模型「{used_model}」驅動。\n"
                            f"> -# 🤓 AI 內容僅供參考，不代表本社群立場，敬請核實。\n"
                            f"> -# 📖 回應內容不會參考附件內容、其他頻道、網路資料、訊息表情。"
                        )
                        await message.reply(reply_content + footer, allowed_mentions=discord.AllowedMentions.none())
                        print("   ✅ 已傳送回應")
                    else:
                        if last_error:
                             # 檢查是否為 429 Resource Exhausted 錯誤
                             error_str = str(last_error)
                             if "429" in error_str or "Resource has been exhausted" in error_str:
                                 wait_msg = (
                                     "我的配額被你們問爆了啦🫠\n"
                                     "你們可以一分鐘後或是明天重試看看嗎🥺\n"
                                     f"# ⚠️ 模型發生錯誤\n```json\n{error_str}\n```"
                                 )
                                 await message.reply(wait_msg)
                             elif "503" in error_str or "Service Unavailable" in error_str:
                                 wait_msg = (
                                     "我被你們問爆了啦🫠\n"
                                     "你們可能要重試一下🥺\n"
                                     f"# ⚠️ 模型發生錯誤\n```json\n{error_str}\n```"
                                 )
                                 await message.reply(wait_msg)
                             else:
                                 await message.reply(f"# ⚠️ 模型發生錯誤\n```json\n{error_str}\n```")
                        else:
                             await message.reply("🤖 模型未產生任何回應。")

                except Exception as e:
                    print(f"❌ 處理訊息時發生錯誤: {e}")
                    await message.reply(f"❌ 發生錯誤: {str(e)}")

# 程式進入點
if __name__ == "__main__":
    # 讀取 server.py 的共用設定
    try:
        settings_data = get_settings()
        secrets_data = get_secrets()
        
        if not secrets_data['TOKEN']:
            print("❌ 無法執行：缺少 TOKEN (請檢查 .env)")
        else:
            # 設定 Intents
            intents = discord.Intents.default()
            intents.message_content = True # 必須啟用才能讀取訊息內容
            intents.members = True # 必須啟用才能正確讀取伺服器暱稱 (需在 Developer Portal 開啟 Server Members Intent)
            
            client = TaggedResponseBot(settings=settings_data, secrets=secrets_data, intents=intents)
            client.run(secrets_data['TOKEN'])
            
    except KeyboardInterrupt:
        print("\n🛑 程式已手動停止")
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
