#!/usr/bin/env bash
# 傻瓜版轉換器(macOS / Linux)
# 雙擊 → 揀資料夾 → 自動轉換 → 自動開結果資料夾
#
# 也可以把資料夾拖到這個檔案上(macOS Finder / Linux 檔案管理員)。
set -uo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"

cyan() { printf '\033[36m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red() { printf '\033[31m%s\033[0m\n' "$*"; }
pause_exit() { echo ""; read -r -p "按 Enter 關閉" _ ; exit "${1:-0}"; }

printf '\033[36m===============================================\033[0m\n'
printf '        PDF  →  Markdown  (含 OCR)\n'
printf '\033[36m===============================================\033[0m\n'

# ---------- 1. 安裝 ----------
if [ ! -f ".venv/.deps-ok" ]; then
  cyan "第一次使用,需要先安裝(約 2–4 分鐘,只需一次)…"
  if ! bash ./_setup.sh; then
    red "✗ 安裝未完成,請看上面的訊息。"
    pause_exit 1
  fi
fi

# ---------- 2. 取得目標 ----------
SRC="${1:-}"

# macOS 拖到 .command 上時,可能收到多個參數;只取第一個資料夾
if [ -z "$SRC" ] && [ "$(uname)" = "Darwin" ]; then
  SRC="$(osascript -e 'POSIX path of (choose folder with prompt "請選擇放了 PDF 的資料夾")' 2>/dev/null)"
  [ -z "$SRC" ] && { yellow "已取消。"; sleep 1; exit 0; }
elif [ -z "$SRC" ]; then
  # Linux:優先用圖形化選檔
  if command -v zenity >/dev/null 2>&1; then
    SRC="$(zenity --file-selection --directory --title="請選擇放了 PDF 的資料夾" 2>/dev/null)"
    [ -z "$SRC" ] && { yellow "已取消。"; sleep 1; exit 0; }
  else
    read -r -p "請貼上資料夾路徑: " SRC
  fi
fi

TEMP_DIR=""
WORK="$SRC"

if [ -f "$SRC" ]; then
  # 拖進來的是單一檔案 → 複製到暫存資料夾再轉,
  # 但輸出一樣放在「原檔旁邊」,否則檔案會落在隨機命名的暫存資料夾,找不到。
  ORIG="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"
  STEM="$(basename "$ORIG")"
  STEM="${STEM%.*}"
  TEMP_DIR="$(mktemp -d)"
  cp "$ORIG" "$TEMP_DIR/"
  WORK="$TEMP_DIR"
  OUT="$(dirname "$ORIG")/${STEM}-md"
else
  WORK="${SRC%/}"
  OUT="${WORK}-md"
fi

if [ ! -d "$WORK" ]; then
  red "✗ 找不到:$SRC"
  pause_exit 1
fi

echo ""
printf '  來源: %s\n  輸出: %s\n\n' "$SRC" "$OUT"

# ---------- 3. 轉換 ----------
START=$(date +%s)
LOG="$(mktemp)"
./.venv/bin/python batch_convert.py "$WORK" -o "$OUT" --ocr auto --workers 2 | tee "$LOG"
CODE=${PIPESTATUS[0]}
ELAPSED=$(( $(date +%s) - START ))

[ -n "$TEMP_DIR" ] && rm -rf "$TEMP_DIR"

# ---------- 4. 收尾 ----------
echo ""
if [ $CODE -ne 0 ]; then
  red "✗ 轉換過程有錯誤,請看上面訊息。"
  pause_exit $CODE
fi

N=$(find "$OUT" -name '*.md' -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$N" = "0" ]; then
  yellow "⚠ 這個資料夾裡找不到可轉換的檔案(PDF / Word / Excel …)。"
  pause_exit 0
fi

SKIPPED=$(grep -o '跳過(已存在):[0-9]*' "$LOG" 2>/dev/null | grep -o '[0-9]*$' || echo 0)
CONVERTED=$(grep -o '完成:[0-9]*' "$LOG" 2>/dev/null | head -1 | grep -o '[0-9]*$' || echo 0)
rm -f "$LOG"

green "==============================================="
if [ "${CONVERTED:-0}" = "0" ] && [ "${SKIPPED:-0}" != "0" ]; then
  green "  $N 份 .md 已經存在,全部跳過(沒有重新轉換)"
  yellow "  如要強制重轉:./convert.sh <資料夾>(加 --force)"
else
  green "  完成!$N 份 .md,用了 $ELAPSED 秒"
fi
green "==============================================="
echo ""
printf '  放在:%s\n' "$OUT"
echo "  已幫你開啟資料夾。"
echo ""

if [ "$(uname)" = "Darwin" ]; then
  open "$OUT"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$OUT" >/dev/null 2>&1 &
fi

sleep 2
