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
    檢查並自動安裝必要的 OCR 套件。
    改為使用 EasyOCR (基於 PyTorch)，在 Mac 上的相容性較佳。
    """
    required_packages = {
        'easyocr': 'easyocr',           # EasyOCR 本體 (會自動安裝 torch)
        'cv2': 'opencv-python-headless' # 圖像處裡 (headless 版較輕量)
    }
    
    missing = []
    print("🔄 正在檢查環境依賴 (EasyOCR 版本)...")
    
    for module_name, package_name in required_packages.items():
        try:
            if importlib.util.find_spec(module_name) is None:
                missing.append(package_name)
        except (ImportError, ModuleNotFoundError):
            missing.append(package_name)
            
    if missing:
        print(f"⚠️  偵測到缺少必要套件: {', '.join(missing)}")
        print("🚀 正在為您自動安裝 (EasyOCR 會下載 PyTorch，可能需要一段時間)...")
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            print("✅ 安裝完成！")
            print("-" * 30)
        except subprocess.CalledProcessError as e:
            print(f"❌ 自動安裝失敗: {e}")
            print("請嘗試手動執行: pip install easyocr opencv-python-headless")
            sys.exit(1)
    else:
        print("✅ 環境檢查通過。")

# 執行環境檢查
check_requirements()

# ==========================================
#              OCR 主程式
# ==========================================

# 抑制一些警告
warnings.filterwarnings("ignore", category=UserWarning)

try:
    import easyocr
except ImportError:
    print("❌ 載入 EasyOCR 失敗。")
    sys.exit(1)

def main():
    image_path = "img.jpg"
    
    if not os.path.exists(image_path):
        print(f"❌ 找不到圖片檔案: {image_path}")
        print("請確保圖片位於同一目錄下，並命名為 img.jpg")
        return

    print(f"🔍 正在初始化 EasyOCR 模型 (目標: 繁體中文 + 英文)...")
    print("   (初次執行會自動下載檢測模型與識別模型，請保持網路連線並稍候...)")

    try:
        # 初始化 Reader
        # ['ch_tra', 'en'] = 繁體中文 + 英文
        # gpu=False : 雖然 Mac M1/M2 支援 MPS 加速，但為了最大相容性與簡單性，先設為 False (使用 CPU)
        reader = easyocr.Reader(['ch_tra', 'en'], gpu=False)
        
        print(f"📸 正在讀取圖片: {image_path}")
        
        # detail=0 只回傳文字列表 (簡單模式)
        # detail=1 回傳 [座標, 文字, 信心度] (詳細模式)
        results = reader.readtext(image_path, detail=1)
        
        if not results:
            print("⚠️  無法識別出任何文字。")
            return

        print("\n" + "="*15 + " 識別結果 " + "="*15)
        
        for (bbox, text, prob) in results:
            # bbox 是座標，暫不顯示
            print(f"[{prob:.2f}] {text}")

        print("="*40)
        
    except Exception as e:
        print(f"❌ 識別過程中發生錯誤: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
