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
# ==============================
# 👇 在這裡輸入你想傳送的訊息
MESSAGE_TO_SEND = """"""

# 👇 指定頻道 ID 或 討論串 ID (填寫數字即可，留空則使用 .env 設定)
SPECIFIED_CHANNEL_ID = 1463956373619347642
# SPECIFIED_CHANNEL_ID = 1234567890 

# ==============================
# ==============================
# ==============================

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
TARGET_CHANNEL_ID = os.getenv('TARGET_CHANNEL_ID')

if not TOKEN or (not TARGET_CHANNEL_ID and not SPECIFIED_CHANNEL_ID):
    print("❌ 錯誤: 請確認 .env 內有設定 DISCORD_BOT_TOKEN 和 TARGET_CHANNEL_ID，或是在程式碼中指定 SPECIFIED_CHANNEL_ID")
    exit(1)

class OnceSender(discord.Client):
    async def on_ready(self):
        target_id = int(SPECIFIED_CHANNEL_ID) if SPECIFIED_CHANNEL_ID else int(TARGET_CHANNEL_ID)
        
        try:
             # 先嘗試從快取取得
            channel = self.get_channel(target_id)
            # 如果快取沒有 (例如是討論串或是冷門頻道)，則嘗試透過 API 抓取
            if not channel:
                print(f"⚠️ 快取找不到頻道 {target_id}，嘗試透過 API 抓取...")
                channel = await self.fetch_channel(target_id)
        except Exception as e:
            print(f"❌ 無法取得目標頻道/討論串 ({target_id}): {e}")
            await self.close()
            return

        if channel:
            print(f"✅ 已鎖定目標: #{channel.name} (ID: {channel.id})")
            if hasattr(channel, 'guild'):
                print(f"   所屬伺服器: {channel.guild.name}")
            
            print(f"🚀 準備開始傳送...")
            
            if MESSAGE_TO_SEND.strip():
                await channel.send(MESSAGE_TO_SEND)
                print("✅ 文字訊息傳送成功！")
            
            # 傳送圖片邏輯
            # 取得 sender.py 所在的目錄
            base_dir = os.path.dirname(os.path.abspath(__file__))
            img_dir = os.path.join(base_dir, 'img')
            
            if os.path.exists(img_dir):
                print(f"📂 發現 img 資料夾：{img_dir}")
                # 取得所有圖片檔案並排序
                files = os.listdir(img_dir)
                image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.heic')
                images = sorted([f for f in files if f.lower().endswith(image_extensions)])
                
                if images:
                    print(f"📸 準備傳送 {len(images)} 張圖片...")
                    for idx, image_name in enumerate(images):
                        image_path = os.path.join(img_dir, image_name)
                        try:
                            file = discord.File(image_path)
                            await channel.send(file=file)
                            print(f"   [{idx+1}/{len(images)}] 已傳送: {image_name}")
                            await asyncio.sleep(1) # 避免觸發 Rate Limit
                        except Exception as e:
                            print(f"   ❌ 傳送失敗 {image_name}: {e}")
                    print("✅ 所有圖片傳送完成！")
                else:
                    print("ℹ️ img 資料夾內沒有圖片")
            else:
                print(f"ℹ️ 未發現 img 資料夾 ({img_dir})，跳過圖片傳送")

        else:
            print(f"❌ 找不到目標頻道 {target_id} (請確認 ID 正確且機器人有權限訪問)")
        
        await self.close()

if __name__ == "__main__":
    intents = discord.Intents.default()
    client = OnceSender(intents=intents)
    client.run(TOKEN)
