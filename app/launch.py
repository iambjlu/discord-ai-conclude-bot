# launch.py — App 內建的 Python 啟動殼
# 先把 iCloud 上的 bot.env 載入環境變數（override），再用 __main__ 身分執行指定腳本。
# 用法：python launch.py <script.py> [args...]
import os
import runpy
import sys

core = os.path.dirname(os.path.abspath(__file__))
env_file = os.environ.get("BOT_ENV_FILE", "")
if env_file and os.path.isfile(env_file):
    from dotenv import load_dotenv
    load_dotenv(env_file, override=True)
else:
    print(f"⚠️ 找不到設定檔 BOT_ENV_FILE={env_file!r}，將只使用現有環境變數", flush=True)

script = os.path.join(core, sys.argv[1])
sys.path.insert(0, core)
sys.argv = [script] + sys.argv[2:]     # 腳本自己 os.execv 重啟時也能直接跑
runpy.run_path(script, run_name="__main__")
