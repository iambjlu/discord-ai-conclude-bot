
import discord
import sys
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
        "TAGGED_REPLY_PROMPT_TEMPLATE": """你是一個機器人，請根據以下該頻道最新 {msg_limit} 則對話內容，自然地回應使用者的話 (若使用者有提問)，你無法讀取其他訊息頻道，請盡量基於此頻道對話進行回應。有時候用戶也會問你想法，這時候說你的想法，不要搓湯圓。不可以詢問跟進。每個句子寫完要換一行。Z世代口吻。通用知識類的東西也可以講。如果用戶情緒不好，請顧一下用戶情緒。你知道你不能看到圖片。
對話歷史:
{context_str}
使用者最新的提及: {u_name}: {content_clean}"""
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

        # ====================設定使用的模型====================
        # 模型優先順序列表 (如果不支援或失敗會自動嘗試下一個)
        self.model_priority_list = ["gemma-4-31b-it", "gemma-3-12b-it", "gemma-3-4b-it", "gemma-3-2b-it", "gemma-3-1b-it"]
        # ====================================================
        self.ignore_after_token = '> 🤖 '
        # ====================設定使用的模型====================

    def parse_chinese_number(self, s):
        """解析中文數字與阿拉伯數字字串為整數"""
        if not s: return 1
        if s.isdigit():
            return int(s)
            
        cn_map = {
            '一': 1, '壹': 1,
            '二': 2, '貳': 2, '兩': 2,
            '三': 3, '參': 3,
            '四': 4, '肆': 4,
            '五': 5, '伍': 5,
            '六': 6, '陸': 6,
            '七': 7, '柒': 7,
            '八': 8, '捌': 8,
            '九': 9, '玖': 9,
            '十': 10, '拾': 10,
            '廿': 20
        }
        
        # 簡單的中文數字解析 (適用於 1-99)
        total = 0
        current_val = 0 
        
        # 直接查表 check (針對單字元)
        if s in cn_map and cn_map[s] < 10:
             return cn_map[s]
        
        for char in s:
            if char in cn_map:
                val = cn_map[char]
                if val >= 10: 
                    if current_val == 0:
                        current_val = 1
                    total += current_val * val
                    current_val = 0
                else:
                    current_val = val
        
        total += current_val
        return total if total > 0 else 1

    async def on_ready(self):
        print('-------------------------------------------')
        print(f'✅ Bot 已登入 (Tagged Response Mode): {self.user}')
        print(f'🤖 模型優先順序: {self.model_priority_list}')
        print('-------------------------------------------')

    async def on_message(self, message):
        # 1. 忽略自己的訊息
        if message.author == self.user:
            return

        # 2. 檢查是否被提及 (Tagged)
        if self.user in message.mentions:
            print(f"📨 收到提及: {message.author} 在 #{message.channel}")
            
            # 顯示正在輸入...
            async with message.channel.typing():
                try:
                    # 3. 解析訊息則數 (預設 30 則)
                    # 嘗試從訊息中尋找 "數字 + 則/句" 或是單純的數字
                    content_clean = message.content.replace(f'<@{self.user.id}>', '').replace(f'<@!{self.user.id}>', '').strip()
                    
                    msg_limit = 30 # 預設值
                    
                    # 定義中文數字字元集合
                    cn_num_chars = "一二兩三四五六七八九十壹貳參肆伍陸柒捌玖拾廿"
                    
                    # Regex 匹配: "30", "30則", "30句", "三十", "三十則"
                    pattern = rf'(\d+|[{cn_num_chars}]+)\s*(?:m|msg|messages|則|句|行|lines)?'
                    match = re.search(pattern, content_clean, re.IGNORECASE)
                    
                    raw_limit_str = None
                    
                    if match:
                        raw_limit_str = match.group(1)
                    else:
                        # 如果輸入僅有數字
                        if content_clean.isdigit():
                            raw_limit_str = content_clean
                        elif re.fullmatch(rf'[{cn_num_chars}]+', content_clean):
                            raw_limit_str = content_clean

                    if raw_limit_str:
                        msg_limit = self.parse_chinese_number(raw_limit_str)

                    # 限制範圍避免濫用 (例如最大 500 則)
                    msg_limit = max(5, min(msg_limit, 500))
                    
                    print(f"   ⏳ 抓取數量: {msg_limit} 則")

                    # 3.5 檢查是否有回覆參照 (Reply Reference)
                    ref_msg_ctx = ""
                    if message.reference and message.reference.message_id:
                        try:
                            # 嘗試抓取被回覆的原始訊息
                            ref_msg = await message.channel.fetch_message(message.reference.message_id)
                            ref_text = ref_msg.content
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
                    # 使用 msg_limit 作為參考上下文的數量 (或固定一個比例，這裡遵照用戶需求也適用該數量)
                    # 但為了避免太多，這裡設一個稍微保守的上限，例如 max(msg_limit, 20) 或者直接用 msg_limit
                    ref_limit = msg_limit
                    
                    ref_context_str = ""
                    ref_msg_ids = set()
                    
                    if ref_msg_ctx and message.reference and message.reference.message_id:
                         try:
                            # 取得被回覆的訊息物件
                            center_msg = await message.channel.fetch_message(message.reference.message_id)
                            
                            ref_collected = []
                            # 抓取該訊息前後 msg_limit 則
                            async for h_msg in message.channel.history(around=center_msg, limit=ref_limit):
                                if not h_msg.content.strip() and not h_msg.attachments: continue
                                ref_msg_ids.add(h_msg.id)
                                
                                # 簡易格式化
                                h_author = h_msg.author.display_name
                                h_time = h_msg.created_at.astimezone(self.settings.get("TZ")).strftime("%H:%M")
                                h_content = h_msg.content.replace(self.ignore_after_token, "").strip()
                                if h_msg.attachments: h_content += " (含附件)"
                                
                                ref_line = f"{h_author}@{h_time}: {h_content}"
                                ref_collected.append((h_msg.created_at, ref_line))
                            
                            # 依照時間排序
                            ref_collected.sort(key=lambda x: x[0])
                            
                            ref_context_lines = [x[1] for x in ref_collected]
                            if ref_context_lines:
                                ref_context_str = f"\n[被回覆訊息的時間點上下文 (±{ref_limit//2}則)]\n" + "\n".join(ref_context_lines) + "\n--------------------\n"
                                print(f"   📎 額外抓取回覆上下文: {len(ref_context_lines)} 則")

                         except Exception as e:
                            print(f"   ⚠️ 無法抓取回覆上下文細節: {e}")

                    # 4. 抓取歷史訊息
                    tz = self.settings.get("TZ", timezone(timedelta(hours=8)))
                    # 改用 limit 抓取最新 N 則
                    
                    collected_messages = []
                    
                    # 準備時間格式
                    time_fmt = ""
                    if self.settings.get("SHOW_DATE", False): time_fmt += "%Y年%m月%d日 %A "
                    time_fmt += "%H:%M"
                    if self.settings.get("SHOW_SECONDS", False): time_fmt += ":%S"

                    # 遍歷歷史訊息 (history 取出預設是 newest first, 所以要反轉)
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
                                u_name = user.display_name[:self.settings.get("AUTHOR_NAME_LIMIT", 4)]
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
                        if self.settings.get("SIMPLIFY_LINKS", True):
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
                        author_name = msg.author.display_name[:self.settings.get("AUTHOR_NAME_LIMIT", 4)]
                        if author_name_override:
                            author_name = author_name_override

                        if not content.strip() and not msg.attachments: continue

                        msg_line = f"{author_name}@{created_at_local}: {content}"

                        # 附件顯示
                        if msg.attachments:
                            show_att = self.settings.get("SHOW_ATTACHMENTS", False)
                            msg_line += " (附件)" if not show_att else f" (附件 {[a.url for a in msg.attachments]})"

                        collected_messages.append(msg_line)

                    if not collected_messages:
                        await message.reply(f"❌ 過去 {msg_limit} 則內沒有足夠的對話內容可以分析。")
                        return

                    # 反轉訊息列表 (因為是從 newest 抓回來的)
                    collected_messages.reverse()

                    # 拼接對話內容
                    # 如果有回覆的歷史上下文，加在最前面
                    full_context_str = ref_context_str + "\n[最新對話]\n" + "\n".join(collected_messages)
                    print(f"   📄 收集到 {len(collected_messages)} 則近期訊息")
                    print(f"--- 收集到的訊息內容 ---\n{full_context_str}\n--------------------")

                    # 5. 呼叫 AI 模型 (嘗試優先順序列表)
                    if not self.genai_client:
                        await message.reply("❌ 無法回應：未設定 GEMINI_API_KEY。")
                        return

                    prompt_template = self.settings.get("TAGGED_REPLY_PROMPT_TEMPLATE", "")
                    prompt = prompt_template.format(
                        msg_limit=msg_limit, 
                        context_str=full_context_str, 
                        u_name=u_name, 
                        content_clean=content_clean + ref_msg_ctx
                    )

                    reply_content = None
                    used_model = None

                    for model_name in self.model_priority_list:
                        print(f"   🤖 嘗試使用模型: {model_name} ...")
                        try:
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
                            continue # 失敗則嘗試下一個

                    # 6. 回覆結果
                    if reply_content and used_model:
                        # 加上一些資訊讓使用者知道範圍
                        footer = (
                            f"\n"
                            f"> 🤖 以上回覆由「{used_model}」模型根據此頻道最新 {msg_limit} 則訊息回覆。\n"
                            f"> 🤓 AI 內容僅供參考，不代表本社群立場，敬請核實。\n"
                            f"> 📖 此次回應不包含附件內容、其他頻道、網路資料、伺服器內暱稱、訊息表情。\n"
                            f"> 💡 可以指定使用 5~500 (預設30) 則對話紀錄。"
                        )
                        await message.reply(reply_content + footer, allowed_mentions=discord.AllowedMentions.none())
                        print("   ✅ 已傳送回應")
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
            
            client = TaggedResponseBot(settings=settings_data, secrets=secrets_data, intents=intents)
            client.run(secrets_data['TOKEN'])
            
    except KeyboardInterrupt:
        print("\n🛑 程式已手動停止")
    except Exception as e:
        print(f"❌ 啟動失敗: {e}")
