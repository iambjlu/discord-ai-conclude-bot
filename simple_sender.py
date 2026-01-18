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
MESSAGE_TO_SEND = """# 管理員臨時公告
大家聊得太熱絡了 超過Gemini上下文上限 正在嘗試修復"""

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
