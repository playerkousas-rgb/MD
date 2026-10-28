#!/usr/bin/env bash
# 共用安裝步驟(由 start.sh / 轉換PDF.command 呼叫)
#   exit 0 = 已就緒,1 = 失敗
set -euo pipefail
cd "$(dirname "$0")"

[ -f ".venv/.deps-ok" ] && exit 0

say() { printf '\033[36m%s\033[0m\n' "$*"; }
warn() { printf '\033[33m%s\033[0m\n' "$*"; }

PY=""
for c in python3.13 python3.12 python3.11 python3 python; do
  command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }
done
if [ -z "$PY" ]; then
  printf '\033[31m✗ 找不到 Python。請先安裝 Python 3.11+:https://www.python.org/downloads/\033[0m\n' >&2
  exit 1
fi

if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'; then
  warn "⚠ Python 低於 3.11:可用,但沒有「版面分析」(標題／表格),輸出會是純文字。"
fi

if [ ! -d .venv ]; then
  say "→ 第一次執行,建立虛擬環境…"
  "$PY" -m venv .venv
fi

say "→ 安裝依賴(約 2–4 分鐘,只需一次)…"
./.venv/bin/python -m pip install --upgrade pip -q
./.venv/bin/python -m pip install -r requirements.txt || {
  warn "⚠ 安裝過程有問題,改用不指定版本重試…"
  ./.venv/bin/python -m pip install pymupdf rapidocr-onnxruntime \
    opencv-python-headless opencc-python-reimplemented \
    fastapi "uvicorn[standard]" python-multipart markitdown
}

# rapidocr 會硬拉非 headless 的 opencv-python 並覆蓋 headless 版 → import cv2 會失敗
say "→ 修正 OpenCV 為 headless 版…"
./.venv/bin/python -m pip uninstall -y opencv-python >/dev/null 2>&1 || true
./.venv/bin/python -m pip install -q --force-reinstall --no-deps opencv-python-headless

touch .venv/.deps-ok
say "→ 安裝完成"
