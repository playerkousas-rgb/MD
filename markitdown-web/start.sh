#!/usr/bin/env bash
# 一鍵啟動(第一次會自動建立虛擬環境並安裝依賴)
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "→ 建立虛擬環境…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  echo "→ 安裝依賴(第一次約 30 秒)…"
  ./.venv/bin/pip install -q -r requirements.txt
fi

PORT="${PORT:-8000}"
echo "→ 啟動:http://localhost:${PORT}"
exec ./.venv/bin/uvicorn app:app --host 0.0.0.0 --port "${PORT}"
