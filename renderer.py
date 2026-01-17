
# 只有 renderer.py 改寫，server.py 不需要大改，只需要把 reactions_str 改成 list 傳進去
# 並且更新 renderer class

import asyncio
import base64
from playwright.async_api import async_playwright
import os

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
