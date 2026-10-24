#!/usr/bin/env bash
# build_app.sh — 用 swiftc 打包 DiscordBot.app（不需開 Xcode）
# BUNDLE_BROWSERS=1 ./build_app.sh  → 把專案的 browsers/ 一起包進 App（約多 500 MB，首次啟動免下載）
set -euo pipefail
cd "$(dirname "$0")"
OUT="build/DiscordBot.app"
ARCH="$(uname -m)"
command -v swiftc >/dev/null 2>&1 || { echo "找不到 swiftc，請先執行：xcode-select --install"; exit 1; }

echo "[build] 編譯（$ARCH, macOS 14+）"
rm -rf "$OUT"; mkdir -p "$OUT/Contents/MacOS" "$OUT/Contents/Resources"
if ! swiftc -O -swift-version 5 -parse-as-library -target "$ARCH-apple-macos14.0" \
      app/AppModel.swift app/BotRunner.swift app/DiscordBotApp.swift app/EnvStore.swift app/Views.swift \
      -o "$OUT/Contents/MacOS/DiscordBot" 2> app/.build.log; then
  echo "[build] ❌ 編譯失敗："; head -40 app/.build.log; exit 1
fi

# 內建核心：所有 Python 腳本 ＋ 啟動殼（排除 old、測試）
CORE="$OUT/Contents/Resources/core"; mkdir -p "$CORE"
rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude 'test_*' \
  server.py tagged_reply.py renderer.py hello_msg.py get_message.py tcc.py sender split_long_image image_reg "$CORE/"
cp app/core-requirements.txt app/launch.py "$CORE/"
cp app/core_run.sh "$CORE/run.sh"; chmod +x "$CORE/run.sh"
if [ "${BUNDLE_BROWSERS:-0}" = "1" ] && [ -d browsers ]; then
  echo "[build] 內附 Playwright 瀏覽器…"; rsync -a browsers "$CORE/"
fi

ICON="build/AppIcon.icns"
if [ ! -f "$ICON" ] || [ app/make_icon.swift -nt "$ICON" ]; then
  TMP="$(mktemp -d)"
  if swift app/make_icon.swift "$TMP/icon.png" >/dev/null 2>&1; then
    mkdir -p "$TMP/AppIcon.iconset"
    for s in 16 32 128 256 512; do
      sips -z $s $s "$TMP/icon.png" --out "$TMP/AppIcon.iconset/icon_${s}x${s}.png" >/dev/null
      sips -z $((s * 2)) $((s * 2)) "$TMP/icon.png" --out "$TMP/AppIcon.iconset/icon_${s}x${s}@2x.png" >/dev/null
    done
    iconutil -c icns "$TMP/AppIcon.iconset" -o "$ICON" || echo "[build] ⚠️ 圖示產生失敗"
  else echo "[build] ⚠️ 圖示產生失敗（Dock 會顯示預設圖示）"; fi
  rm -rf "$TMP"
fi
[ -f "$ICON" ] && cp "$ICON" "$OUT/Contents/Resources/AppIcon.icns"

cat > "$OUT/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>tw.iambjlu.DiscordAIConcludeBot</string>
  <key>CFBundleName</key><string>DiscordBot</string>
  <key>CFBundleDisplayName</key><string>Discord AI Bot</string>
  <key>CFBundleExecutable</key><string>DiscordBot</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSUIElement</key><true/>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

codesign --force --deep -s - "$OUT" >/dev/null 2>&1 || echo "[build] ⚠️ 簽章失敗（不影響本機執行）"
rm -f app/.build.log
echo "[build] ✅ 完成：$OUT"
