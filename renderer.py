
# 只有 renderer.py 改寫，server.py 不需要大改，只需要把 reactions_str 改成 list 傳進去
# 並且更新 renderer class

import asyncio
import base64
from playwright.async_api import async_playwright
import os
import io

class ImageGenerator:
    def __init__(self):
        # 瀏覽器實例會在生成時啟動
        pass

    def _bytes_to_base64(self, data: bytes, mime_type: str = "image/png") -> str:
        """Helper: 將 bytes 轉為 Data URI"""
        if not data:
            return ""
        b64 = base64.b64encode(data).decode('utf-8')
        return f"data:{mime_type};base64,{b64}"

    async def generate_quote_card(self, 
                                  quote_content: str, 
                                  author_name: str, 
                                  author_avatar: bytes, 
                                  date_text: str,
                                  server_name: str,
                                  server_icon: bytes = None,
                                  attachment_image: bytes = None,
                                  reactions: list = []): # 改成接收 list of (emoji, count, is_custom_emoji, url)
        
        # 1. 準備資源 (Base64)
        avatar_src = self._bytes_to_base64(author_avatar) or "https://cdn.discordapp.com/embed/avatars/0.png"
        server_icon_src = self._bytes_to_base64(server_icon) or "https://cdn.discordapp.com/embed/avatars/0.png"
        attachment_src = self._bytes_to_base64(attachment_image)
        
        # 2. 處理文字換行與安全
        import html
        
        # 若無內容且無附件，顯示預設文字
        if not quote_content.strip() and not attachment_image:
             quote_content = "(無法言喻的訊息)"
             
        quote_safe = html.escape(quote_content).replace("\n", "<br>")
        author_safe = html.escape(author_name)
        server_safe = html.escape(server_name)
        
        # 3. 表情符號 HTML 生成
        # 我們期望 reactions 是一個列表: [(emoji_str, count, url), ...]
        reaction_html = ""
        total_reactions = 0
        
        for r in reactions:
            # r: (emoji_str, count, url)
            e_char = r[0]
            count = r[1]
            url = r[2]
            total_reactions += count
            
            if url: # Custom Emoji
                icon_html = f'<img src="{url}" class="emoji-icon" />'
            else: # Unicode Emoji
                icon_html = f'<span class="emoji-text">{e_char}</span>'
                
            reaction_html += f"""
            <div class="reaction-pill">
                {icon_html}
                <span class="count">{count}</span>
            </div>
            """
            
        # 4. HTML/CSS 模板
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                :root {{
                    --glass-bg: rgba(255, 255, 255, 0.08); /* 更透一點 */
                    --glass-border: rgba(255, 255, 255, 0.2);
                    --text-color: #ffffff;
                    --text-sub: rgba(255, 255, 255, 0.7);
                    --accent-color: #ffd700; /* 金色 */
                }}
                body {{
                    margin: 0;
                    padding: 0;
                    width: 1440px;
                    height: 2560px;
                    background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
                    /* 字體優先級：System -> PingFang TC -> Fallback */
                    font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", "Heiti TC", sans-serif;
                    overflow: hidden;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    box-sizing: border-box;
                }}
                
                /* 裝飾 Blobs */
                .blob {{
                    position: absolute;
                    border-radius: 50%;
                    filter: blur(100px);
                    opacity: 0.5;
                    z-index: 0;
                    animation: float 10s infinite ease-in-out;
                }}
                .blob-1 {{ width: 700px; height: 700px; background: #8E2DE2; top: -200px; left: -200px; }}
                .blob-2 {{ width: 600px; height: 600px; background: #4A00E0; bottom: 100px; right: -100px; }}
                
                @keyframes float {{
                    0% {{ transform: translate(0, 0); }}
                    50% {{ transform: translate(20px, 30px); }}
                    100% {{ transform: translate(0, 0); }}
                }}

                /* 主卡片 */
                .card {{
                    position: relative;
                    z-index: 10;
                    width: 1200px;
                    /* 移除 min-height 讓內容決定高度，但設一個 max-height 防止蓋到底部 */
                    max-height: 2000px; 
                    
                    background: rgba(255, 255, 255, 0.05);
                    backdrop-filter: blur(50px);
                    -webkit-backdrop-filter: blur(50px);
                    border: 1px solid var(--glass-border);
                    border-radius: 80px;
                    box-shadow: 0 40px 80px rgba(0,0,0,0.5);
                    
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    padding: 80px 100px 100px 100px; /* 上 左右 下 */
                    box-sizing: border-box;
                    color: white;
                    overflow: hidden; /* 防止內容溢出 */
                }}
                
                .crown {{
                    font-size: 80px;
                    margin-bottom: -18px;
                    z-index: 20;
                    filter: drop-shadow(0 0 10px gold);
                    animation: bounce 2s infinite;
                }}
                @keyframes bounce {{
                    0%, 100% {{ transform: translateY(0); }}
                    50% {{ transform: translateY(-10px); }}
                }}

                /* 頭像區 */
                .avatar-container {{
                    position: relative;
                    margin-bottom: 30px;
                }}
                .avatar {{
                    width: 220px;
                    height: 220px;
                    border-radius: 50%;
                    object-fit: cover;
                    border: 8px solid rgba(255,255,255,0.15);
                    box-shadow: 0 15px 40px rgba(0,0,0,0.4);
                }}
                
                /* 姓名與日期 */
                .author-name {{
                    font-size: 64px;
                    font-weight: 800; /* Heavy */
                    margin-bottom: 14px;
                    letter-spacing: 1px;
                    text-shadow: 0 4px 20px rgba(0,0,0,0.3);
                    background: linear-gradient(to right, #fff, #ddd);
                    -webkit-background-clip: text;
                    -webkit-text-fill-color: transparent;
                }}
                .date {{
                    font-size: 48px;
                    color: rgba(255, 255, 255, 0.9);
                    margin-bottom: 40px;
                    font-weight: 600;
                    letter-spacing: 1px;
                    text-align: center;
                }}
                .date-subtext {{
                    font-size: 0.7em;
                    opacity: 0.8;
                    display: block;
                    margin-top: 8px;
                    font-weight: 500;
                }}

                /* 金句區 - 自動刪節號 */
                .quote-content {{
                    font-size: 64px;
                    line-height: 1.4;
                    font-weight: 700;
                    text-align: center;
                    margin-bottom: 40px;
                    width: 100%;
                    padding: 0 40px;
                    box-sizing: border-box;
                    
                    /* 多行截斷 */
                    display: -webkit-box;
                    -webkit-line-clamp: 6; /* 最多顯示 6 行 */
                    -webkit-box-orient: vertical;
                    overflow: hidden;
                    text-overflow: ellipsis;
                }}

                /* 附件圖片容器 */
                .attachment-container {{
                    margin-top: 10px;
                    margin-bottom: 30px;
                    display: flex;
                    justify-content: center;
                    width: 100%;
                }}
                .attachment-img {{
                    max-width: 100%;
                    max-height: 900px;
                    border-radius: 40px;
                    box-shadow: 0 20px 50px rgba(0,0,0,0.4);
                    border: 2px solid rgba(255,255,255,0.1);
                    object-fit: contain; # Ensure the image is contained
                }}

                /* 底部統計區 */
                .stats-section {{
                    width: 100%;
                    border-top: 2px solid rgba(255,255,255,0.1);
                    padding-top: 30px;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    margin-top: auto; 
                }}
                .stats-title {{
                    font-size: 42px;
                    color: #ffd700;
                    font-weight: 700;
                    margin-bottom: 24px;
                    text-transform: uppercase;
                    letter-spacing: 2px;
                }}
                .reactions-grid {{
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: center;
                    gap: 20px;
                }}
                .reaction-pill {{
                    background: rgba(0,0,0,0.3);
                    padding: 10px 24px;
                    border-radius: 40px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    border: 1px solid rgba(255,255,255,0.05);
                }}
                .emoji-icon {{ width: 48px; height: 48px; object-fit: contain; }}
                .emoji-text {{ font-size: 42px; line-height: 1; }}
                .count {{ font-size: 36px; font-weight: 600; color: white; margin-left: 6px; }}
                
                /* 伺服器 Footer */
                .footer {{
                    position: absolute;
                    bottom: 60px;
                    left: 0;
                    width: 100%;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    z-index: 10;
                    opacity: 0.8;
                }}
                .server-icon {{
                    width: 100px;
                    height: 100px;
                    border-radius: 30px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                    border: 2px solid rgba(255,255,255,0.1);
                }}
                .server-name {{
                    font-size: 32px;
                    color: rgba(255,255,255,0.5);
                    font-weight: 500;
                    text-transform: uppercase;
                    letter-spacing: 2px;
                }}

            </style>
        </head>
        <body>
            <div class="blob blob-1"></div>
            <div class="blob blob-2"></div>

            <div class="card">
                <div class="crown">👑</div>
                
                <div class="avatar-container">
                    <img class="avatar" src="{avatar_src}" />
                </div>
                
                <div class="author-name">{author_safe}</div>
                <div class="date">{date_text}</div>

                <div class="quote-content">
                    {quote_safe}
                </div>

                {f'<div class="attachment-container"><img class="attachment-img" src="{attachment_src}" /></div>' if attachment_src else ''}

                <div class="stats-section">
                    <div class="stats-title">🏆 本日金句王 獲得 {total_reactions} 個表情</div>
                    <div class="reactions-grid">
                        {reaction_html if reaction_html else '<div class="reaction-pill"><span class="emoji-text">✨</span><span class="count">0</span></div>'}
                    </div>
                </div>
            </div>

            <div class="footer">
                <img class="server-icon" src="{server_icon_src}" />
                <div class="server-name">{server_safe}</div>
            </div>
        </body>
        </html>
        """

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(channel="chrome", headless=True) # Try system Chrome first for improved font rendering
            except:
                browser = await p.chromium.launch(headless=True)
                
            # 設定語系與時區
            context = await browser.new_context(
                viewport={"width": 1440, "height": 2560},
                locale="zh-TW",
                timezone_id="Asia/Taipei"
            )
            page = await context.new_page()
            await page.set_content(html_content)
            await page.wait_for_timeout(500) # Wait for fonts/images
            
            img_bytes = await page.screenshot(type='png')
            await browser.close()
            
            import io
            return io.BytesIO(img_bytes)

    async def generate_weather_card(self, weather_data: list, server_name: str = "", server_icon: bytes = None, title: str = "🌤️ 台灣各縣市天氣預報"):
        """
        weather_data: list of dict
        """
        # 1. 準備資源
        server_icon_src = self._bytes_to_base64(server_icon) or "https://cdn.discordapp.com/embed/avatars/0.png"
        
        import html
        server_safe = html.escape(server_name)
        title_safe = html.escape(title)
        
        # 建立 Grid HTML
        cards_html = ""
        for item in weather_data:
            c_name = html.escape(item['county'])
            
            rows_html = ""
            for f in item.get('forecasts', []):
                # f['pop'] logic
                f_pop = f['pop']
                pop_val = int(f_pop) if f_pop.isdigit() else 0
                pop_color = "#1565C0" if pop_val > 50 else "#E10600"
                
                # Icon mapping (reuse logic or simplify)
                w_str = f['wx']
                ci_str = f.get('ci', '')
                
                full_wx_str = w_str
                if ci_str:
                    full_wx_str += f" ({ci_str})"

                icon = "☁️" 
                if "雨" in w_str: icon = "🌧️"
                elif "晴" in w_str: icon = "☀️"
                elif "陰" in w_str: icon = "☁️"
                elif "雲" in w_str: icon = "⛅"
                elif "雷" in w_str: icon = "⛈️"
                
                # POP Icon
                pop_icon = "☔"
                if f_pop == "0":
                    pop_icon = "🌂"
                
                # New POP logic: Text color + Shadow instead of badge
                # Material Design Colors: Red 600 for high, Blue 600 for low
                pop_color = "#E53935" if pop_val > 50 else "#1E88E5"
                
                rows_html += f"""
                <div class="hourly-item">
                    <div class="hourly-top">
                        <span class="h-time">{f['time']}</span>
                        <span class="h-icon">{icon}</span>
                        <span class="h-temp">{f['temp']}°</span>
                        <span class="h-pop" style="color: {pop_color}">{pop_icon} {f_pop}%</span>
                    </div>
                    <div class="hourly-bottom">
                         <span class="h-wx">{full_wx_str}</span>
                    </div>
                </div>
                """

            cards_html += f"""
            <div class="weather-item">
                <div class="header">
                    <span class="county">{c_name}</span>
                </div>
                <div class="hourly-list">
                    {rows_html}
                </div>
            </div>
            """
            
        time_info = weather_data[0]['time_range'] if weather_data else ""
        
        # Determine columns based on item count to save space if fewer than 3 items
        # But we want consistency, so let's stick to max 3 columns, but if only 1 or 2 items, fit content.
        # Actually user asked to "cut off excess".
        grid_cols_style = "repeat(3, 500px)"
        if len(weather_data) < 3:
             grid_cols_style = f"repeat({len(weather_data)}, 500px)"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                :root {{
                    --glass: rgba(255, 255, 255, 0.08);
                    --glass-border: rgba(255, 255, 255, 0.15);
                    --text: #ffffff;
                }}
                body {{
                    margin: 0; padding: 0;
                    width: fit-content;
                    height: fit-content;
                    /* Updated Gradient: Blue -> Dark Blue -> Red */
                    background: linear-gradient(120deg, #0066b2 0%, #002b5e 50%, #d12e2e 100%);
                    font-family: -apple-system, BlinkMacSystemFont, "PingFang TC", "Microsoft JhengHei", sans-serif;
                    box-sizing: border-box;
                    color: white;
                    font-weight: 700;
                    padding: 60px;
                }}
                
                /* BKG Blobs - adjusted to cover dynamic area */
                .blob {{ position: absolute; border-radius: 50%; filter: blur(150px); opacity: 0.3; z-index: -1; }}
                /* Make blobs strictly within body overflow if possible, or just large enough */
                .blob-1 {{ top: 0; left: 0; width: 100%; height: 800px; background: #E94560; }}
                .blob-2 {{ bottom: 0; right: 0; width: 100%; height: 800px; background: #533483; }}

                .content-wrapper {{
                    z-index: 10;
                    display: flex;
                    flex-direction: column;
                }}
                 /* ... css continues ... */


                .header-section {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center; /* Center horizontally aligned items vertically */
                    margin-bottom: 60px;
                    width: 100%;
                }}
                
                .title-group {{
                    display: flex;
                    flex-direction: column;
                    align-items: flex-start;
                    gap: 15px;
                }}
                
                h1 {{
                    font-size: 100px;
                    margin: 0;
                    font-weight: 900;
                    letter-spacing: 4px;
                    text-shadow: 0 5px 30px rgba(0,0,0,0.6);
                    text-align: left;
                    line-height: 1.1;
                }}
                .subtitle {{
                    font-size: 60px;
                    color: rgba(255, 255, 255, 0.7);
                    /* No background */
                    padding: 0;
                }}
                
                .server-group {{
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    /* No background */
                    padding: 10px;
                }}
                
                .server-icon {{
                    width: 120px;
                    height: 120px;
                    border-radius: 22px;
                    object-fit: cover;
                    margin-bottom: 10px;
                }}
                
                .server-name {{
                    font-size: 40px;
                    font-weight: 800;
                    color: rgba(255,255,255,0.8);
                    text-transform: uppercase;
                    letter-spacing: 2px;
                }}
                
                .grid {{
                    display: grid;
                    grid-template-columns: {grid_cols_style};
                    gap: 30px;
                }}
                
                .weather-item {{
                    background: var(--glass);
                    backdrop-filter: blur(30px);
                    -webkit-backdrop-filter: blur(30px);
                    border: 3px solid var(--glass-border);
                    border-radius: 40px;
                    padding: 35px;
                    color: white;
                    display: flex;
                    flex-direction: column;
                    justify-content: space-between;
                    box-shadow: 0 15px 40px rgba(0,0,0,0.25);
                    box-sizing: border-box;
                    min-height: 400px;
                }}
                
                .header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 15px;
                    border-bottom: 2px solid rgba(255,255,255,0.1);
                    padding-bottom: 15px;
                }}
                .county {{ font-size: 48px; font-weight: 900; }}
                .icon {{ font-size: 60px; filter: drop-shadow(0 0 5px rgba(255,255,255,0.4)); }}
                
                .wx-text {{
                    font-size: 48px;
                    margin-bottom: 15px;
                    color: #ffd700;
                    font-weight: 600;
                    min-height: 60px;
                    display: flex;
                    align-items: center;
                }}
                
                .temp {{
                    font-size: 60px;
                    font-weight: 600;
                    margin-bottom: 20px;
                    letter-spacing: -2px;
                }}
                
                .details {{
                    background: rgba(0,0,0,0.25);
                    border-radius: 25px;
                    padding: 20px;
                    display: flex;
                    flex-direction: column;
                    align-items: center; /* Center children horizontally */
                    gap: 10px;
                }}
                
                .detail-item {{
                    width: 100%;
                    display: flex;
                    justify-content: center;
                }}
                
                .ci-text {{ 
                    font-size: 42px; 
                    font-weight: 800; 
                    opacity: 1.0; 
                    text-align: center;
                }}
                
                .pop-val {{
                    font-size: 42px;
                    font-weight: 700;
                }}
                
                /* Hourly List Styles */
                .hourly-list {{
                    display: flex;
                    flex-direction: column;
                    gap: 8px; /* Slightly reduced gap */
                    width: 100%;
                }}
                .hourly-item {{
                    display: flex;
                    flex-direction: column;
                    border-bottom: 1px solid rgba(255,255,255,0.1);
                    padding-bottom: 6px; /* Reduced padding */
                    gap: 2px;
                }}
                .hourly-item:last-child {{ border-bottom: none; }}
                
                .hourly-top {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    width: 100%;
                }}

                .hourly-bottom {{
                    display: flex;
                    justify-content: flex-start;
                    align-items: center;
                    width: 100%;
                    padding-left: 0; 
                }}

                /* Reduced sizes to make room */
                .h-time {{ font-size: 30px; font-weight: 500; color: rgba(255,255,255,0.9); width: 100px; }}
                .h-icon {{ font-size: 36px; width: 50px; text-align: center; }}
                .h-temp {{ font-size: 36px; font-weight: 700; color: #ffd700; flex: 1; text-align: center; }}
                
                .h-pop {{ 
                    font-size: 28px; 
                    width: 130px; 
                    /* Use flex center for the oval content */
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    
                    background: rgba(255, 255, 255, 0.85);
                    backdrop-filter: blur(8px);
                    -webkit-backdrop-filter: blur(8px);
                    border-radius: 50px;
                    padding: 4px 0;
                    
                    font-weight: 800;
                    text-shadow: 0 1px 2px rgba(0,0,0,0.2);
                }}

                /* wx text prominent */
                .h-wx {{ 
                    font-size: 24px;  /* Reduced from 32px */
                    color: #ffffff;  /* White */
                    width: 100%;
                    text-align: left;
                    padding-left: 0;
                    margin-top: 4px;
                    font-weight: 500;
                }}
            </style>
        </head>
        <body>
            <div class="blob blob-1"></div>
            <div class="blob blob-2"></div>
            
            <div class="content-wrapper">
                <div class="header-section">
                    <div class="title-group">
                        <h1>{title_safe}</h1>
                        <div class="subtitle">{time_info}</div>
                        <!-- <div class="subtitle">📅 預報時段: {time_info}</div> -->
                    </div>
                    
                    <div class="server-group">
                        <img class="server-icon" src="{server_icon_src}" />
                        <div class="server-name">{server_safe}</div>
                    </div>
                </div>
                
                <div class="grid">
                    {cards_html}
                </div>
            </div>
        </body>
        </html>
        """
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(channel="chrome", headless=True)
            except:
                browser = await p.chromium.launch(headless=True)
                
            # Use explicit viewport size that is large enough for the content to layout horizontally
            # width ≈ 3 * 500 + 2 * 30 (gap) + 2 * 60 (padding) ≈ 1680. 
            # Set to 1850 to be safe.
            context = await browser.new_context(
                viewport={"width": 1850, "height": 1000}, 
                device_scale_factor=2, 
                locale="zh-TW"
            )
            page = await context.new_page()
            await page.set_content(html_content)
            await page.wait_for_timeout(500)
            
            # Crop to body content exactly
            body_handle = page.locator('body')
            img_bytes = await body_handle.screenshot(type='png')
            await browser.close()
            
            return io.BytesIO(img_bytes)

if __name__ == "__main__":
    # Test block
    async def main():
        gen = ImageGenerator()
        print("Testing generator...")
        img = await gen.generate_quote_card(
            "測試金句內容 Quote Content", 
            "User Name", 
            None, 
            "2026/01/17", 
            "Server Name", 
            None,
            None,
            [("🔥", 50, None), ("😂", 20, None), ("custom", 30, "https://cdn.discordapp.com/emojis/123456789.png")]
        )
        with open("test_renderer.png", "wb") as f:
            f.write(img.getbuffer())
        print("Done.")
    
    asyncio.run(main())
