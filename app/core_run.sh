#!/usr/bin/env bash
# app/core_run.sh → 打包成 DiscordBot.app/Contents/Resources/core/run.sh
# App 本體唯讀；Python 環境、Playwright 瀏覽器等會寫的東西放在
# ~/Library/Application Support/DiscordAIConcludeBot（第一次啟動自動建立）。
# 用法：run.sh <script.py> [args...]。訊息一律寫 stderr→App 日誌。
set -euo pipefail
CORE="$(cd "$(dirname "$0")" && pwd)"
DATA="${BOT_DATA:-$HOME/Library/Application Support/DiscordAIConcludeBot}"
mkdir -p "$DATA"
export BOT_DATA="$DATA"
export PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Playwright 瀏覽器：App 內有附就用內附的，否則放 Application Support 並在需要時下載
if [ -d "$CORE/browsers" ]; then
  export PLAYWRIGHT_BROWSERS_PATH="$CORE/browsers"
else
  export PLAYWRIGHT_BROWSERS_PATH="$DATA/browsers"
fi

# 找 Python（>= 3.11 優先；最後才退回系統內建的）
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3.14 python3.13 python3.12 python3.11 python3; do
    p="$(command -v "$c" 2>/dev/null || true)"
    [ -n "$p" ] && [ "$p" != "/usr/bin/python3" ] && { PY="$p"; break; }
  done
  PY="${PY:-/usr/bin/python3}"
fi

VENV="$DATA/venv"
REQ="$CORE/core-requirements.txt"
STAMP="$VENV/.requirements.sha"

# 兩個 bot 可能同時第一次啟動：用鎖避免同時 pip install
LOCK="$DATA/.setup.lock"
while ! mkdir "$LOCK" 2>/dev/null; do
  owner="$(cat "$LOCK/pid" 2>/dev/null || true)"
  if [ -n "$owner" ] && ! kill -0 "$owner" 2>/dev/null; then rm -rf "$LOCK"; continue; fi
  echo "[core] 等待另一個程序完成環境安裝…" >&2
  sleep 3
done
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c "pass" 2>/dev/null; then
  echo "[core] 第一次啟動：用 $PY 建立 Python 環境（約 1～3 分鐘，之後不用）" >&2
  rm -rf "$VENV"
  "$PY" -m venv "$VENV" >&2
fi
SUM="$(shasum "$REQ" | cut -d' ' -f1)"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$SUM" ]; then
  echo "[core] 安裝／更新 Python 套件…" >&2
  "$VENV/bin/python" -m pip install -q --upgrade pip >&2
  "$VENV/bin/python" -m pip install -q -r "$REQ" >&2
  echo "$SUM" > "$STAMP"
fi
if [ ! -d "$CORE/browsers" ] && ! ls "$DATA/browsers"/chromium-* >/dev/null 2>&1; then
  echo "[core] 下載 Playwright Chromium（約 150 MB，只需一次）…" >&2
  "$VENV/bin/python" -m playwright install chromium >&2 || echo "[core] ⚠️ Chromium 下載失敗，截圖／圖片渲染功能將無法使用" >&2
fi

rm -rf "$LOCK"; trap - EXIT
cd "$DATA"
exec "$VENV/bin/python" "$CORE/launch.py" "$@"
