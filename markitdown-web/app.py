#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MarkItDown 網頁版 — 自己架一個「上載 → 轉 Markdown」的網頁服務。

微軟官方的 MarkItDown 只有 CLI 和 Python API,沒有網頁介面;
這個小服務就是把它包成 HTTP API,再配一個單頁前端。

啟動:
    uvicorn app:app --host 0.0.0.0 --port 8000

設計重點:
  * 每個請求用獨立的 MarkItDown 實例(MarkItDown 不保證執行緒安全)。
  * 上載檔案先落地成暫存檔(保留副檔名),轉完即刪。
  * 掃描影像 PDF 沒有文字層,會回傳 warning 提示需要 OCR,而不是靜靜地給空結果。
"""

from __future__ import annotations

import io
import os
import re
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

try:
    from markitdown import MarkItDown
except ImportError:  # pragma: no cover
    raise SystemExit("請先安裝依賴:pip install -r requirements.txt")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

MAX_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "100")) * 1024 * 1024
MAX_FILES = 20

# MarkItDown 支援的格式(配上 requirements.txt 已安裝的 extras)
ALLOWED_EXT = {
    ".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls", ".csv", ".tsv",
    ".html", ".htm", ".xml", ".json", ".txt", ".md", ".markdown",
    ".epub", ".msg", ".ipynb", ".zip", ".rtf",
}

# PDF 平均每頁字數低於此值 → 懷疑是掃描影像,沒有文字層
SCANNED_CHARS_PER_PAGE = 30

app = FastAPI(title="MarkItDown 網頁版", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_name(name: str) -> str:
    """去掉路徑成分,保留中文檔名。"""
    name = (name or "file").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name)
    return name[:180] or "file"


def _stem(name: str) -> str:
    base = _safe_name(name)
    root, _ = os.path.splitext(base)
    return root


def _pdf_page_count(path: str) -> int | None:
    """用 pdfplumber 取頁數;失敗就回 None(不影響轉換)。"""
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return len(pdf.pages)
    except Exception:
        return None


def _convert_one(filename: str, data: bytes, want_front_matter: bool) -> dict:
    """轉換單一檔案。永遠回傳 dict,不拋例外,方便批次處理。"""
    name = _safe_name(filename)
    ext = os.path.splitext(name)[1].lower()
    out = {
        "filename": name,
        "ext": ext,
        "size": len(data),
        "ok": False,
        "markdown": "",
        "chars": 0,
        "seconds": 0.0,
        "warnings": [],
        "error": None,
        "pages": None,
    }

    if ext not in ALLOWED_EXT:
        out["error"] = "不支援的格式:%s" % (ext or "(無副檔名)")
        return out
    if not data:
        out["error"] = "檔案是空的。"
        return out

    tmp_path = None
    started = time.time()
    try:
        # 保留副檔名,MarkItDown 靠副檔名判斷格式
        fd, tmp_path = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, "wb") as f:
            f.write(data)

        md = MarkItDown()  # 每個工作執行緒一個實例
        result = md.convert(tmp_path)
        text = (result.text_content or "").replace("\r\n", "\n")

        if ext == ".pdf":
            pages = _pdf_page_count(tmp_path)
            out["pages"] = pages
            if pages and pages > 0:
                per_page = len(text.strip()) / pages
                if per_page < SCANNED_CHARS_PER_PAGE:
                    out["warnings"].append(
                        "PDF 只有 %.0f 字／頁,可能是掃描影像而沒有文字層;"
                        "需要 OCR(如 Tesseract 或 Azure Document Intelligence)才有內容。" % per_page
                    )
        if not text.strip():
            out["warnings"].append(
                "轉換成功但沒有抽到任何文字;若是 PDF 多數情況是掃描影像檔。"
            )

        if want_front_matter and text.strip():
            stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")
            qname = name.replace('"', '\\"')
            fm = "\n".join([
                "---",
                'source_file: "%s"' % qname,
                'source_format: "%s"' % ext.lstrip("."),
                'converted_by: "MarkItDown"',
                'converted_at: "%s"' % stamp,
                "---",
                "",
                "",
            ])
            text = fm + text

        out["markdown"] = text
        out["chars"] = len(text)
        out["ok"] = True
    except Exception as e:  # noqa: BLE001 - 任何失敗都回報給前端
        out["error"] = "%s: %s" % (type(e).__name__, e)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        out["seconds"] = round(time.time() - started, 2)
    return out


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "max_upload_mb": MAX_BYTES // (1024 * 1024),
        "max_files": MAX_FILES,
        "formats": sorted(e.lstrip(".") for e in ALLOWED_EXT),
    }


@app.post("/api/convert")
def convert(
    files: List[UploadFile] = File(...),
    front_matter: bool = Form(False),
):
    """批次轉換。回傳 JSON,前端自行顯示／下載。"""
    if not files:
        raise HTTPException(400, "沒有收到檔案。")
    if len(files) > MAX_FILES:
        raise HTTPException(400, "一次最多 %d 個檔案。" % MAX_FILES)

    payload = []
    for uf in files:
        data = uf.file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(
                413,
                "「%s」超過 %d MB 上限。" % (_safe_name(uf.filename), MAX_BYTES // (1024 * 1024)),
            )
        payload.append((uf.filename, data))

    # 少量檔案直接順序處理;多檔才開執行緒,避免搶記憶體。
    if len(payload) == 1:
        results = [_convert_one(payload[0][0], payload[0][1], front_matter)]
    else:
        with ThreadPoolExecutor(max_workers=min(4, len(payload))) as pool:
            futures = [
                pool.submit(_convert_one, n, d, front_matter) for n, d in payload
            ]
            results = [f.result() for f in futures]
    return {"results": results}


@app.post("/api/convert-zip")
def convert_zip(
    files: List[UploadFile] = File(...),
    front_matter: bool = Form(False),
):
    """一次轉換並直接回傳 ZIP(每個檔案一個 .md)。"""
    data = convert(files=files, front_matter=front_matter)["results"]
    buf = io.BytesIO()
    used = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for r in data:
            if not r["ok"]:
                continue
            base = _stem(r["filename"]) + ".md"
            outname, i = base, 2
            while outname in used:
                outname = "%s (%d).md" % (_stem(r["filename"]), i)
                i += 1
            used.add(outname)
            z.writestr(outname, r["markdown"])
    buf.seek(0)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="markdown-%s.zip"' % stamp
        },
    )


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=False,
    )
