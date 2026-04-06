import discord
import asyncio
import os
import re
import argparse
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# 設定部：可以根據需求調整
NAME_LIMIT = 4        # 名字顯示長度
MAX_MSG_LEN = 500     # 單則訊息最大長度
TZ = timezone(timedelta(hours=8)) # GMT+8

# 截斷字元 (訊息中若出現此字串，則後方內容將被捨棄，常用於過濾 Bot 總結)
IGNORE_TOKEN = "-# 🤖"

# 預設抓取天數 (若執行時沒指定 --days 則以此為準)
DEFAULT_DAYS = 30

# 預設頻道 ID 清單 (若不為空，則優先於 .env)
# 範例: DEFAULT_CHANNELS = [121...738, 7458...152]
DEFAULT_CHANNELS = [1162833322435690597,745840586510041152,1219637392848457738] 

async def get_messages(days=1, channel_ids=None):
    """
    抓取指定頻道在過去 X 天內的訊息並清理
    """
    load_dotenv()
    token = os.getenv('DISCORD_BOT_TOKEN')
    
    if not token:
        print("❌ 錯誤: 未在 .env 找到 DISCORD_BOT_TOKEN")
        return

    # 決定頻道來源優先順序
    if not channel_ids:
        # 1. 檢查頂部定義的 DEFAULT_CHANNELS
        if DEFAULT_CHANNELS:
            channel_ids = DEFAULT_CHANNELS
            print(f"📌 使用腳本頂部定義的預設頻道: {channel_ids}")
        # 2. 檢查 .env 的 SOURCE_CHANNEL_IDS
        else:
            source_ids_str = os.getenv('SOURCE_CHANNEL_IDS', '')
            if source_ids_str:
                channel_ids = [int(x.split('#')[0].strip()) for x in source_ids_str.split(',') if x.strip()]
                print(f"📌 從 .env 讀取頻道: {channel_ids}")
            else:
                print("❌ 錯誤: 未指定 channel_id，腳本頂部 DEFAULT_CHANNELS 為空，且 .env 中沒有 SOURCE_CHANNEL_IDS")
                return
    else:
        print(f"📌 使用手動指定的頻道: {channel_ids}")

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    # 將主要抓取邏輯封裝，避免在 on_ready 中直接 call close()
    async def run_scraper():
        now = datetime.now(TZ)
        after_date = now - timedelta(days=days)
        print(f"🕒 抓取範圍: {after_date.strftime('%Y-%m-%d %H:%M:%S')} 之後的訊息")
        
        results = []
        for ch_id in channel_ids:
            channel = client.get_channel(ch_id)
            if not channel:
                try:
                    channel = await client.fetch_channel(ch_id)
                except Exception as e:
                    print(f"⚠️ 無法取得頻道 {ch_id}: {e}")
                    continue
            
            print(f"📂 正在處理頻道: #{channel.name} ({ch_id})")
            results.append(f"\n--- [#{channel.name}] ---")
            
            count = 0
            async for msg in channel.history(after=after_date, limit=None):
                content = msg.content
                
                # 實作「截斷字元」邏輯：若內容中出現此符號，則只保留標記之前的部分
                if IGNORE_TOKEN and IGNORE_TOKEN in content:
                    content = content.split(IGNORE_TOKEN)[0]
                
                # 簡化連結
                def domain_replacer(match):
                    url = match.group(0)
                    try:
                        no_proto = url.split("://", 1)[1]
                        return f"(連結 {no_proto.split('/', 1)[0]})"
                    except: return url
                content = re.sub(r'https?://\S+', domain_replacer, content)
                content = re.sub(r'<a?:\w+:\d+>', '(貼圖)', content)
                
                if msg.mentions:
                    for user in msg.mentions:
                        u_name = user.display_name[:NAME_LIMIT]
                        content = content.replace(f"<@{user.id}>", f"@{u_name}")
                        content = content.replace(f"<@!{user.id}>", f"@{u_name}")

                if len(content) > MAX_MSG_LEN:
                    content = content[:MAX_MSG_LEN] + "..."
                
                if not content.strip() and not msg.attachments:
                    continue

                author_name = msg.author.display_name[:NAME_LIMIT]
                timestamp = msg.created_at.astimezone(TZ).strftime("%H:%M")
                
                line = f"[{timestamp}] {author_name}: {content}"
                if msg.attachments:
                    line += " (附件)"
                
                print(line)
                results.append(line)
                count += 1
            
            print(f"   ✅ 頻道 #{channel.name} 處理完成，共 {count} 則訊息")

        output_text = "\n".join(results)
        if output_text.strip():
            print("\n" + "="*30 + "\n抓取結果：\n" + "="*30)
            print(output_text)
            with open("messages_output.txt", "w", encoding="utf-8") as f:
                f.write(output_text)
            print(f"\n💾 結果已存至 messages_output.txt")
        else:
            print("\nℹ️ 該期間內沒有任何訊息。")

    @client.event
    async def on_ready():
        print(f"✅ 已登入為 {client.user.name}")
        # 在 on_ready 這裡執行 scraping
        await run_scraper()
        # 完成後關閉 client
        await client.close()

    async with client:
        try:
            await client.start(token)
        except Exception as e:
            if isinstance(e, asyncio.CancelledError):
                pass
            else:
                print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="抓取特定期間內的 Discord 訊息並清理")
    parser.add_argument("--days", type=float, default=DEFAULT_DAYS, help=f"追蹤天數 (目前設定預設為 {DEFAULT_DAYS})")
    parser.add_argument("--channels", type=str, help="頻道 ID (逗號分隔，若無則抓腳本頂部設定或 .env)")
    
    args = parser.parse_args()
    
    ch_list = None
    if args.channels:
        ch_list = [int(x.strip()) for x in args.channels.split(',') if x.strip()]
    
    asyncio.run(get_messages(days=args.days, channel_ids=ch_list))
