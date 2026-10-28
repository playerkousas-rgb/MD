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

# ---------- 1+2. 檢查環境並安裝(共用 _setup.sh) ----------
if ! bash ./_setup.sh; then
  die "安裝未完成,請看上面的訊息。"
fi

# ---------- 3. 啟動 ----------
say "→ 啟動轉換器:http://localhost:$PORT"
say "   (按 Ctrl+C 停止)"
( sleep 2; command -v open >/dev/null && open "http://localhost:$PORT" \
  || command -v xdg-open >/dev/null && xdg-open "http://localhost:$PORT" >/dev/null 2>&1 ) &
exec ./.venv/bin/python -m uvicorn app:app --host 0.0.0.0 --port "$PORT"
