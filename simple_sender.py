#手動發訊息用
import discord
import os
import asyncio
from dotenv import load_dotenv

# 載入 .env 讀取 TOKEN 和 Channel ID
load_dotenv()

# ==============================
# ==============================
# ==============================
# 👇 在這裡輸入你想傳送的訊息
MESSAGE_TO_SEND = """# 重點摘要與每日金句頻道(公開預覽版)現已推出！

## Google Gemini 驅動的 AI 重點摘要 現已空降
別再說你懶得時光旅行了！
由業界頂尖的 Google Gemini 大型語言模型
每天定時為你整理聊天室最新戰況
不再錯過任何內容和八卦

## 每日金句
每天梗王是誰？
誰能獲得最多成員的表情符號呢？
不再需要苦苦計算啦！

> 注意： 
> AI總結內容僅供參考，請務必查證。
> AI 言論不代表本社群立場。
> 公開預覽版可能會發生預期之外的錯誤。
> 本更新日誌為人工撰寫。"""
# ==============================
# ==============================
# ==============================

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
TARGET_CHANNEL_ID = os.getenv('TARGET_CHANNEL_ID')

if not TOKEN or not TARGET_CHANNEL_ID:
    print("❌ 錯誤: 請確認 .env 內有設定 DISCORD_BOT_TOKEN 和 TARGET_CHANNEL_ID")
    exit(1)

class OnceSender(discord.Client):
    async def on_ready(self):
        channel = self.get_channel(int(TARGET_CHANNEL_ID))
        if channel:
            print(f"正在傳送訊息至 #{channel.name} ...")
            await channel.send(MESSAGE_TO_SEND)
            print("✅ 傳送成功！")
        else:
            print("❌ 找不到目標頻道")
        
        await self.close()

if __name__ == "__main__":
    intents = discord.Intents.default()
    client = OnceSender(intents=intents)
    client.run(TOKEN)
