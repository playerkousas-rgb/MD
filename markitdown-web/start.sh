#!/usr/bin/env bash
# 一鍵啟動(macOS / Linux)
#   第一次執行會自動建立虛擬環境並安裝依賴(約 2–4 分鐘),之後只會啟動。
#   用法:  ./start.sh          預設 http://localhost:8000
#          PORT=8080 ./start.sh
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
READY=".venv/.deps-ok"

say() { printf '\033[36m%s\033[0m\n' "$*"; }
die() { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

# ---------- 1. 找 Python ----------
PY=""
for c in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || die "找不到 Python。請先安裝 Python 3.11 或以上:https://www.python.org/downloads/"

VER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
say "→ 使用 Python $VER ($(command -v "$PY"))"
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || {
  say "⚠ Python 低於 3.11:仍然可用,但沒有「版面分析」(標題／表格),轉出來會是純文字。"
  say "  建議升級到 3.11+,輸出會好很多。"
}

# ---------- 2. 建立環境 ----------
if [ ! -d .venv ]; then
  say "→ 第一次執行,建立虛擬環境…"
  "$PY" -m venv .venv
fi

if [ ! -f "$READY" ]; then
  say "→ 安裝依賴(約 2–4 分鐘,只需一次)…"
  ./.venv/bin/python -m pip install --upgrade pip -q
  ./.venv/bin/python -m pip install -r requirements.txt || {
    say "⚠ 安裝過程有問題,嘗試不指定版本重試…"
    ./.venv/bin/python -m pip install pymupdf rapidocr-onnxruntime \
      opencv-python-headless opencc-python-reimplemented \
      fastapi "uvicorn[standard]" python-multipart markitdown
  }
  # rapidocr 會硬拉「非 headless」的 opencv-python,它會覆蓋掉 headless 版,
  # 結果 import cv2 時缺 libGL.so.1 → OCR 直接失效。這裡強制改回 headless。
  say "→ 修正 OpenCV 為 headless 版…"
  ./.venv/bin/python -m pip uninstall -y opencv-python >/dev/null 2>&1 || true
  ./.venv/bin/python -m pip install -q --force-reinstall --no-deps opencv-python-headless

  touch "$READY"
  say "→ 依賴安裝完成"
fi

# ---------- 3. 啟動 ----------
say "→ 啟動轉換器:http://localhost:$PORT"
say "   (按 Ctrl+C 停止)"
( sleep 2; command -v open >/dev/null && open "http://localhost:$PORT" \
  || command -v xdg-open >/dev/null && xdg-open "http://localhost:$PORT" >/dev/null 2>&1 ) &
exec ./.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
