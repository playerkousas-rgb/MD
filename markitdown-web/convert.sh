#!/usr/bin/env bash
# 批量把一個資料夾(含子資料夾)的 PDF 轉成 Markdown
#
# 用法:
#   ./convert.sh /path/to/資料夾            → 輸出到 /path/to/資料夾-md
#   ./convert.sh /path/to/資料夾 ./輸出      → 自訂輸出位置
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  printf '\033[31m✗ 尚未安裝。請先執行 ./start.sh 完成一次安裝。\033[0m\n' >&2
  exit 1
fi

SRC="${1:-}"
if [ -z "$SRC" ]; then
  printf '請輸入要轉換的資料夾路徑: '
  read -r SRC
fi
[ -d "$SRC" ] || { printf '\033[31m✗ 找不到資料夾: %s\033[0m\n' "$SRC" >&2; exit 1; }

SRC="${SRC%/}"
OUT="${2:-${SRC}-md}"

printf '\033[36m來源: %s\033[0m\n輸出: %s\n\n' "$SRC" "$OUT"
exec ./.venv/bin/python batch_convert.py "$SRC" -o "$OUT" --ocr auto --workers 2
