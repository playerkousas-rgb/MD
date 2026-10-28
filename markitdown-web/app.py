#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MarkItDown 網頁版 — 上載 → 轉 Markdown(含 OCR)。

微軟官方 MarkItDown 只有 CLI / Python API,這個服務補上網頁層,
並且加上官方沒有的兩件事:
  1. 掃描影像 PDF 的 OCR(RapidOCR,純 pip,不需系統 Tesseract)
  2. 逐頁判斷 → 同一份 PDF 內「文字頁直接抽、影像頁才 OCR」

啟動:
    uvicorn app:app --host 0.0.0.0 --port 8000

無需登入驗證 —— 這是刻意設計,供內網／本機使用。
若要放上公網,請自行在前面加 Nginx Basic Auth 或 Cloudflare Access。
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
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

import convert_core as core

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# 已轉換好的 Markdown 知識庫(batch_convert.py 的輸出)。
# 前端示範頁(/kbview)靠它做全文檢索,再交給 Gemini 回答。
KB_DIR = os.environ.get("KB_DIR", os.path.join(BASE_DIR, "..", "knowledge"))

MAX_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "100")) * 1024 * 1024
MAX_FILES = 50

app = FastAPI(title="MarkItDown 網頁版(含 OCR)", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_name(name: str) -> str:
    name = (name or "file").replace("\\", "/").split("/")[-1].strip()
    name = re.sub(r"[\x00-\x1f<>:\"|?*]", "_", name)
    return name[:180] or "file"


def _stem(name: str) -> str:
    return os.path.splitext(_safe_name(name))[0]


def _front_matter(name: str, meta: dict) -> str:
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %z")
    lines = [
        "---",
        'source_file: "%s"' % name.replace('"', '\\"'),
        'source_format: "%s"' % os.path.splitext(name)[1].lstrip(".").lower(),
        'converted_by: "MarkItDown + RapidOCR"',
        'converted_at: "%s"' % stamp,
    ]
    if meta.get("pages"):
        lines.append("pages: %d" % meta["pages"])
    if meta.get("pages_ocr"):
        lines.append("pages_ocr: %d" % meta["pages_ocr"])
        lines.append("ocr_avg_score: %s" % (meta.get("ocr_avg_score") or 0))
    lines += ["---", "", ""]
    return "\n".join(lines)


def _convert_one(filename: str, data: bytes, *, ocr_mode: str,
                 front_matter: bool, page_markers: bool) -> dict:
    """轉換單一檔案;任何錯誤都回報在 dict 內,不讓批次中斷。"""
    name = _safe_name(filename)
    ext = os.path.splitext(name)[1].lower()
    out = {
        "filename": name, "ext": ext, "size": len(data), "ok": False,
        "markdown": "", "chars": 0, "seconds": 0.0,
        "warnings": [], "error": None, "pages": None,
        "pages_ocr": 0, "ocr_avg_score": None,
    }

    if ext not in core.SUPPORTED_EXT:
        out["error"] = "不支援的格式:%s" % (ext or "(無副檔名)")
        return out
    if not data:
        out["error"] = "檔案是空的。"
        return out

    tmp_path = None
    started = time.time()
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, "wb") as f:
            f.write(data)

        md, meta = core.convert_path(
            tmp_path, name, ocr_mode=ocr_mode,
            page_markers=page_markers, glossary=core.DEFAULT_GLOSSARY,
        )
        md = (md or "").replace("\r\n", "\n")
        out["pages"] = meta.get("pages")
        out["pages_ocr"] = meta.get("pages_ocr") or 0
        out["ocr_avg_score"] = meta.get("ocr_avg_score")
        out["warnings"] = list(meta.get("warnings") or [])

        if not md.strip():
            out["warnings"].append(
                "轉換成功但沒有抽到任何文字;若 OCR 也認不到,可能是空白頁、純圖片或解析度太低。"
            )
        elif front_matter:
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


def _run_batch(files: List[UploadFile], ocr_mode: str, front_matter: bool,
               page_markers: bool) -> list[dict]:
    if not files:
        raise HTTPException(400, "沒有收到檔案。")
    if len(files) > MAX_FILES:
        raise HTTPException(400, "一次最多 %d 個檔案。" % MAX_FILES)
    if ocr_mode not in core.OCR_MODES:
        raise HTTPException(400, "ocr_mode 必須是 auto / always / never。")

    payload = []
    for uf in files:
        data = uf.file.read()
        if len(data) > MAX_BYTES:
            raise HTTPException(
                413, "「%s」超過 %d MB 上限。"
                % (_safe_name(uf.filename), MAX_BYTES // (1024 * 1024)))
        payload.append((uf.filename, data))

    # OCR 很吃 CPU(沙盒 2 核),多檔時最多 2 條執行緒平行,避免互相拖慢
    workers = 1 if len(payload) <= 2 else min(2, len(payload))
    if workers == 1:
        return [_convert_one(n, d, ocr_mode=ocr_mode, front_matter=front_matter,
                             page_markers=page_markers) for n, d in payload]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_convert_one, n, d, ocr_mode=ocr_mode,
                        front_matter=front_matter, page_markers=page_markers)
            for n, d in payload
        ]
        return [f.result() for f in futures]


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "version": app.version,
        "ocr_available": core.ocr_available(),
        "ocr_dpi": core.OCR_DPI,
        "min_chars_per_page": core.MIN_CHARS_PER_PAGE,
        "max_upload_mb": MAX_BYTES // (1024 * 1024),
        "max_files": MAX_FILES,
        "formats": sorted(e.lstrip(".") for e in core.SUPPORTED_EXT),
        "images": sorted(e.lstrip(".") for e in core.IMAGE_EXT),
    }


@app.post("/api/convert")
def convert(
    files: List[UploadFile] = File(...),
    ocr_mode: str = Form("auto"),
    front_matter: bool = Form(False),
    page_markers: bool = Form(True),
):
    return {"results": _run_batch(files, ocr_mode, front_matter, page_markers)}


@app.post("/api/convert-zip")
def convert_zip(
    files: List[UploadFile] = File(...),
    ocr_mode: str = Form("auto"),
    front_matter: bool = Form(False),
    page_markers: bool = Form(True),
):
    results = _run_batch(files, ocr_mode, front_matter, page_markers)
    buf = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for r in results:
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
        headers={"Content-Disposition": 'attachment; filename="markdown-%s.zip"' % stamp},
    )


@app.get("/kb/status")
def kb_status():
    """知識庫是否存在、有幾份文件。"""
    idx = os.path.join(KB_DIR, "_index.json")
    if not os.path.isfile(idx):
        return {"available": False, "dir": KB_DIR, "files": 0}
    import json

    with open(idx, encoding="utf-8") as f:
        data = json.load(f)
    return {
        "available": True,
        "dir": KB_DIR,
        "files": data.get("total", len(data.get("files", []))),
        "converted_at": data.get("generated_at"),
    }


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/kbview")
def kb_view():
    """示範前端:讀 knowledge/*.md → 交給 Gemini 回答。"""
    return FileResponse(os.path.join(STATIC_DIR, "kb.html"))


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 掛載知識庫(唯讀)。目錄不存在也不影響轉換功能。
if os.path.isdir(KB_DIR):
    app.mount("/kb", StaticFiles(directory=KB_DIR), name="kb")


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")), reload=False)
