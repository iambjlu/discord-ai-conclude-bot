#手動發訊息用 / 系統資訊發送
import discord
import os
import asyncio
import subprocess
import platform
from dotenv import load_dotenv

# 載入 .env 讀取 TOKEN 和 Channel ID
load_dotenv()

TOKEN = os.getenv('DISCORD_BOT_TOKEN')
HELLO_MSG_ID = os.getenv('HELLO_MSG_ID')

if not TOKEN or not HELLO_MSG_ID:
    print("❌ 錯誤: 請確認 .env 內有設定 DISCORD_BOT_TOKEN 和 HELLO_MSG_ID")
    exit(1)

def get_system_info():
    os_system = platform.system()
    
    if os_system == "Linux":
        script_content = """
echo "== 系統資訊 ============================"
uname -a
echo ""

echo "== CPU 資訊 ============================"
lscpu | egrep 'Architecture|CPU\\(s\\)|Thread|Core|Socket|Model name'
echo ""

echo "== 記憶體資訊 =========================="
free -h
echo ""

echo "== 磁碟資訊 ============================"
lsblk

echo ""

echo "== GPU / 顯示卡 ========================"
lspci | grep -i vga
echo ""

echo "== 作業系統版本 ========================"
cat /etc/os-release
echo ""

echo "== 開機時間與系統運行時間 ==============="
uptime
echo ""

echo "== 網路介面 ============================"
ip a | grep -E "^[0-9]+:|inet "
echo ""

echo "== 主機名稱 ============================"
hostname
echo ""
"""
        return run_shell_script(script_content, executable='/bin/bash')
        
    elif os_system == "Darwin":
        script_content = """
echo "== 系統資訊 ============================"
uname -a
echo ""

echo "== 網路介面 ====================="
for dev in $(networksetup -listallhardwareports | grep "Device:" | awk '{print $2}'); do
    ip=$(ipconfig getifaddr $dev 2>/dev/null)
    if [ ! -z "$ip" ]; then
        echo "$dev: $ip"
    fi
done
echo ""

echo "== 磁碟資訊 ============================"
diskutil list physical
echo ""

echo "== 詳細硬體與軟體報告 ==================="
system_profiler SPHardwareDataType SPSoftwareDataType | grep -v -E 'Serial Number|UUID|UDID'
echo ""
"""
        return run_shell_script(script_content, executable='/bin/bash')
        
    elif os_system == "Windows":
        commands = [
            ("== 系統資訊 ============================", "ver"),
            ("== CPU 資訊 ============================", "wmic cpu get Name, NumberOfCores, NumberOfLogicalProcessors"),
            ("== 記憶體資訊 ==========================", "wmic OS get TotalVisibleMemorySize, FreePhysicalMemory"),
            ("== 磁碟資訊 ============================", "wmic logicaldisk get Caption, FileSystem, FreeSpace, Size"),
            ("== GPU / 顯示卡 ========================", "wmic path win32_VideoController get name"),
            ("== 網路介面 ============================", "ipconfig"),
            ("== 主機名稱 ============================", "hostname")
        ]
        
        output = []
        try:
            for title, cmd in commands:
                output.append(title)
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, errors='replace')
                cmd_out = res.stdout.strip() if res.stdout.strip() else res.stderr.strip()
                output.append(cmd_out)
                output.append("")
            return "\n".join(output)
        except Exception as e:
            return f"獲取 Windows 系統資訊失敗: {e}"

    else:
        return f"不支援的作業系統: {os_system}"

def run_shell_script(script_content, executable):
    try:
        result = subprocess.run(script_content, shell=True, executable=executable, capture_output=True, text=True, errors='replace')
        return result.stdout if result.stdout else result.stderr
    except Exception as e:
        return f"執行指令時發生錯誤: {e}"

class HelloSender(discord.Client):
    async def on_ready(self):
        target_id = int(HELLO_MSG_ID)
        
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
            
            print(f"🚀 準備開始傳送系統規格...")
            
            sys_info = get_system_info()
            
            if not sys_info.strip():
                sys_info = "無法取得任何系統資訊。"
            
            # Discord 訊息有 2000 字元限制，超過時需要分段傳送
            chunk_size = 1900
            for i in range(0, len(sys_info), chunk_size):
                chunk = sys_info[i:i+chunk_size]
                if i == 0:
                    text_to_send = f"## 嗨 我上線囉！\n系統資訊：```text\n{chunk}\n```"
                else:
                    text_to_send = f"```text\n{chunk}\n```"
                await channel.send(text_to_send)
                await asyncio.sleep(1) # 避免觸發 Rate Limit
                
            print("✅ 系統規格傳送完成！")

        else:
            print(f"❌ 找不到目標頻道 {target_id} (請確認 ID 正確且機器人有權限訪問)")
        
        await self.close()

if __name__ == "__main__":
    intents = discord.Intents.default()
    client = HelloSender(intents=intents)
    client.run(TOKEN)
