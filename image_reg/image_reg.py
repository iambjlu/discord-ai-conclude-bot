import sys
import subprocess
import importlib.util
import os
import warnings

# ==========================================
#              環境檢查與安裝
# ==========================================

def check_requirements():
    """
    檢查並自動安裝必要的套件。
    使用 Google GenAI SDK。
    """
    required_packages = {
        'google.genai': 'google-genai',
        'dotenv': 'python-dotenv',
        'PIL': 'pillow',
        'requests': 'requests'
    }
    
    missing = []
    print("🔄 正在檢查環境依賴 (Google GenAI)...")
    
    for module_name, package_name in required_packages.items():
        try:
            if importlib.util.find_spec(module_name) is None:
                missing.append(package_name)
        except (ImportError, ModuleNotFoundError):
            missing.append(package_name)
            
    if missing:
        print(f"⚠️  偵測到缺少必要套件: {', '.join(missing)}")
        print("🚀 正在為您自動安裝...")
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            print("✅ 安裝完成！")
            print("-" * 30)
        except subprocess.CalledProcessError as e:
            print(f"❌ 自動安裝失敗: {e}")
            print(f"請嘗試手動執行: pip install {' '.join(missing)}")
            sys.exit(1)
    else:
        print("✅ 環境檢查通過。")

# 執行環境檢查
check_requirements()

# 導入依賴
from google import genai
from google.genai import types
from dotenv import load_dotenv
from PIL import Image
import requests
import io

# ==========================================
#              Gemma 識別主程式
# ==========================================

def main():
    # ==========================================
    #              設定與變數
    # ==========================================
    
    #在此設定預設圖片網址或路徑
    IMAGE_SOURCE = ""
    
    # ==========================================

    # 載入 .env 變數 (如果有的話)
    # 嘗試在上層目錄尋找 .env
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    dotenv_path = os.path.join(parent_dir, '.env')
    
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        print("✅ 已載入 .env 設定")
    else:
        # 嘗試當前目錄
        load_dotenv()

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        api_key = os.getenv('GOOGLE_API_KEY')

    if not api_key:
        print("❌ 錯誤: 未設定 GEMINI_API_KEY 或 GOOGLE_API_KEY 環境變數。")
        print("請在 .env 檔案中設定您的 API Key。")
        return

    # 決定圖片來源 (優先使用 sys.argv，否則使用 IMAGE_SOURCE)
    image_source = IMAGE_SOURCE
    if len(sys.argv) > 1:
        image_source = sys.argv[1]

    print(f"🔍 正在初始化 Google GenAI Client...")
    
    try:
        client = genai.Client(api_key=api_key)
        
        content_payload = []
        prompt = "請辨識這張圖片中的文字，直接輸出文字內容即可，不要有額外的描述。"
        content_payload.append(prompt)

        # 判斷是否為網址
        if image_source.startswith("http://") or image_source.startswith("https://"):
            print(f"🌐 正在傳送圖片網址給模型: {image_source}")
            # 簡單判斷 mime_type，預設 image/jpeg
            mime_type = "image/jpeg"
            lower_src = image_source.lower()
            if ".png" in lower_src: mime_type = "image/png"
            elif ".webp" in lower_src: mime_type = "image/webp"
            elif ".jpg" in lower_src or ".jpeg" in lower_src: mime_type = "image/jpeg"
            
            # 直接使用 SDK 的 from_uri，讓 SDK/API 處理
            image_part = types.Part.from_uri(file_uri=image_source, mime_type=mime_type)
            content_payload.append(image_part)
            
        else:
            print(f"📸 正在讀取圖片檔案: {image_source}")
            if not os.path.exists(image_source):
                print(f"❌ 找不到圖片檔案: {image_source}")
                print("請確保圖片位於同一目錄下，或提供正確的路徑/網址")
                return
            image = Image.open(image_source)
            content_payload.append(image)
        
        # 使用 Gemma 3 模型
        model_name = "gemma-3-27b-it"
        print(f"🤖 呼叫模型: {model_name}...")
        
        response = client.models.generate_content(
            model=model_name,
            contents=content_payload,
            config=types.GenerateContentConfig(
                temperature=0.1 # 降低隨機性，提高準確度
            )
        )
        
        if response.text:
            print("\n" + "="*15 + " 識別結果 " + "="*15)
            print(response.text)
            print("="*40)
            
            print("\n" + "="*15 + " 詳細資料 " + "="*15)
            if response.usage_metadata:
                print(f"📊 Token 用量: {response.usage_metadata}")
            
            print(f"📄 完整回應 (JSON):")
            print(response.model_dump_json(indent=2))
            print("="*40)
        else:
            print("⚠️  模型沒有回傳文字內容。")

    except Exception as e:
        print(f"❌ 識別過程中發生錯誤: {e}")
        # 如果是 404 Not Found，提示使用者可能該模型不可用
        if "404" in str(e):
            print("💡 提示: 如果遇到 404 錯誤，可能是您的 API Key 沒有權限存取 gemma-3-27b-it，")
            print("   或者該模型尚未對所有開發者開放。請嘗試改用 'gemini-1.5-flash' 測試。")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
