#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function:PDF → Markdown(含 OCR)。

設計給 Vercel 的限制:
  * 不用 FastAPI / multipart —— 直接收 raw body,省體積也省解析時間
  * PDF 引擎用 pypdfium2(8MB),不用 PyMuPDF(116MB),以免超過 250MB 函數上限
  * 單次請求只處理一個檔案;多檔由前端逐個呼叫(避免 4.5MB body 上限一次爆掉)

請求:
    POST /api/convert?filename=xxx.pdf&ocr=auto&markers=1&frontmatter=0
    Body: 檔案原始 bytes(Content-Type 任意)

回應:
    { ok, filename, markdown, chars, pages, pages_ocr, ocr_avg_score,
      seconds, warnings[], error }

其他路由:
    GET /api/health  → 引擎 / OCR 是否可用、上限
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler

# Vercel 會把整個函數目錄放到 /var/task;本地執行時是本檔的上一層
HERE = os.path.dirname(os.path.abspath(__file__))
for cand in (HERE, os.path.dirname(HERE)):
    if cand not in sys.path:
        sys.path.insert(0, cand)

import convert_core as core  # noqa: E402

# Vercel Serverless Function 的請求 body 上限是 4.5MB(硬限制,改不到)
MAX_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "4")) * 1024 * 1024


def _safe_name(name: str) -> str:
    name = (name or "file").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name)
    return name[:180] or "file"


def _front_matter(name: str, meta: dict) -> str:
    lines = [
        "---",
        'source_file: "%s"' % name.replace('"', '\\"'),
        'source_format: "%s"' % os.path.splitext(name)[1].lstrip(".").lower(),
        'converted_by: "pdf2md (Vercel)"',
    ]
    if meta.get("pages"):
        lines.append("pages: %d" % meta["pages"])
    if meta.get("pages_ocr"):
        lines.append("pages_ocr: %d" % meta["pages_ocr"])
        lines.append("ocr_avg_score: %s" % (meta.get("ocr_avg_score") or 0))
    lines += ["---", "", ""]
    return "\n".join(lines)


def convert_bytes(filename: str, data: bytes, ocr_mode: str,
                  page_markers: bool, front_matter: bool) -> dict:
    name = _safe_name(filename)
    ext = os.path.splitext(name)[1].lower()
    out = {
        "ok": False, "filename": name, "ext": ext, "size": len(data),
        "markdown": "", "chars": 0, "seconds": 0.0, "pages": None,
        "pages_ocr": 0, "ocr_avg_score": None, "warnings": [], "error": None,
    }

    if ext not in core.SUPPORTED_EXT:
        out["error"] = "不支援的格式:%s" % (ext or "(無副檔名)")
        return out
    if not data:
        out["error"] = "檔案是空的。"
        return out

    started = time.time()
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, "wb") as f:
            f.write(data)

        md, meta = core.convert_path(
            tmp_path, name, ocr_mode=ocr_mode,
            page_markers=page_markers, glossary=core.DEFAULT_GLOSSARY,
        )
        md = (md or "").replace("\r\n", "\n")
        out.update(
            pages=meta.get("pages"),
            pages_ocr=meta.get("pages_ocr") or 0,
            ocr_avg_score=meta.get("ocr_avg_score"),
            warnings=list(meta.get("warnings") or []),
        )
        if front_matter:
            md = _front_matter(name, meta) + md
        out["markdown"] = md
        out["chars"] = len(md)
        out["ok"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = "%s: %s" % (type(e).__name__, e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        out["seconds"] = round(time.time() - started, 2)
    return out


class handler(BaseHTTPRequestHandler):  # noqa: N801  (Vercel 要求的類名)
    protocol_version = "HTTP/1.1"

    # ---------------- 工具 ----------------
    def _send(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _query(self) -> dict:
        q = urllib.parse.urlparse(self.path).query
        return {k: v[0] for k, v in urllib.parse.parse_qs(q).items()}

    def _flag(self, q: dict, key: str, default: str = "0") -> bool:
        return str(q.get(key, default)).lower() in ("1", "true", "yes", "on")

    # ---------------- 路由 ----------------
    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if not path.endswith("/health"):
            self._send(404, {"ok": False, "error": "只有 /api/health 支援 GET"})
            return
        self._send(200, {
            "ok": True,
            "pdf_engine": core.pdf_engine(),
            "ocr_available": core.ocr_available(),
            "ocr_dpi": core.OCR_DPI,
            "min_chars_per_page": core.MIN_CHARS_PER_PAGE,
            "max_upload_mb": MAX_BYTES // (1024 * 1024),
            "formats": sorted(e.lstrip(".") for e in core.SUPPORTED_EXT),
        })

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if not path.endswith("/convert"):
            self._send(404, {"ok": False, "error": "路徑應為 /api/convert"})
            return

        q = self._query()
        filename = q.get("filename") or "upload"
        ocr_mode = q.get("ocr", "auto")
        if ocr_mode not in core.OCR_MODES:
            self._send(400, {"ok": False, "error": "ocr 必須是 auto / always / never"})
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            self._send(400, {"ok": False, "error": "沒有收到檔案內容。"})
            return
        if length > MAX_BYTES:
            # 讀掉 body 才不會讓連線卡住
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            self._send(413, {
                "ok": False,
                "error": "檔案 %.1f MB 超過上限 %d MB(Vercel 函數的請求上限是 4.5MB)。"
                         "大檔請用本機版或 batch_convert.py。"
                         % (length / 1048576, MAX_BYTES // (1024 * 1024)),
            })
            return

        data = self.rfile.read(length)
        result = convert_bytes(
            filename, data, ocr_mode,
            page_markers=self._flag(q, "markers", "1"),
            front_matter=self._flag(q, "frontmatter", "0"),
        )
        self._send(200 if result["ok"] else 400, result)

    def log_message(self, fmt, *args):  # 不要污染 Vercel 日誌
        pass
