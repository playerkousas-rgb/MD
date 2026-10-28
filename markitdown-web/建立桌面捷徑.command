#!/usr/bin/env bash
# 在桌面建立「PDF轉Markdown」捷徑(macOS / Linux,只需執行一次)
set -euo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"

DESK="$HOME/Desktop"
[ -d "$DESK" ] || DESK="$HOME/桌面"
[ -d "$DESK" ] || { echo "✗ 找不到桌面資料夾"; exit 1; }

LINK="$DESK/PDF轉Markdown.command"
ln -sfn "$HERE/轉換PDF.command" "$LINK"
chmod +x "$HERE/轉換PDF.command"

echo "✓ 已在桌面建立:$LINK"
echo "  之後直接雙擊桌面那個檔案就可以。"
echo ""
read -r -p "按 Enter 關閉" _
