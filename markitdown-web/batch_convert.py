#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量把一個資料夾(含子資料夾)的 PDF / Office 檔轉成 Markdown。

用法:
    python batch_convert.py ../out/dl -o ../knowledge --ocr auto

產出:
    OUT/<子資料夾>/<檔名>.md     —— 與來源同結構,方便前端按分類讀取
    OUT/_index.json              —— 前端／Gemini 用的索引(標題、字數、頁數、OCR 頁數、SHA-256)
    OUT/_report.csv              —— 逐檔結果(成功／失敗／警告)

特性:
    * 預設「可續跑」:已存在的 .md 會跳過,中斷後重跑不會重做
    * 逐頁判斷 OCR:只有沒有文字層的頁面才花 CPU
    * 單檔失敗不會中斷整批
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import convert_core as core  # noqa: E402

# 預設只轉「文件」;.txt/.json/.csv 這些通常是報表,不用進知識庫
DOC_EXTS = {"pdf", "docx", "pptx", "xlsx", "xls", "epub", "html", "htm", "msg"}


def sha256_file(path: str, buf: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(buf):
            h.update(chunk)
    return h.hexdigest()


def guess_title(md: str, fallback: str) -> str:
    """從 markdown 找第一個像標題的行,找不到就用檔名。"""
    for line in md.splitlines():
        s = line.strip()
        if not s or s.startswith("<!--") or s.startswith("---"):
            continue
        if s.startswith("#"):
            return s.lstrip("# ").strip()[:120]
        # PDF 抽出來的第一行通常就是標題
        return s[:120]
    return fallback


def collect(src: str, exts: set[str]) -> list[str]:
    found = []
    for root, _dirs, names in os.walk(src):
        for n in sorted(names):
            if os.path.splitext(n)[1].lower() in exts:
                found.append(os.path.join(root, n))
    return found


def convert_one(src_path: str, src_root: str, out_root: str, args) -> dict:
    rel = os.path.relpath(src_path, src_root)
    rel_md = os.path.splitext(rel)[0] + ".md"
    out_path = os.path.join(out_root, rel_md)
    name = os.path.basename(src_path)
    started = time.time()

    rec = {
        "source": rel,
        "md_file": rel_md,
        "filename": name,
        "ok": False,
        "skipped": False,
        "chars": 0,
        "pages": None,
        "pages_ocr": 0,
        "ocr_avg_score": None,
        "seconds": 0.0,
        "sha256": "",
        "title": os.path.splitext(name)[0],
        "category": os.path.dirname(rel) or ".",
        "warnings": [],
        "error": None,
    }

    if os.path.exists(out_path) and not args.force:
        rec["ok"] = True
        rec["skipped"] = True
        rec["chars"] = os.path.getsize(out_path)
        rec["seconds"] = 0.0
        return rec

    try:
        md, meta = core.convert_path(
            src_path, name,
            ocr_mode=args.ocr,
            page_markers=not args.no_page_markers,
            glossary=core.DEFAULT_GLOSSARY,
        )
        md = (md or "").replace("\r\n", "\n")

        if args.front_matter:
            fm = [
                "---",
                'source_file: "%s"' % name.replace('"', '\\"'),
                'source_category: "%s"' % rec["category"],
                'source_format: "%s"' % os.path.splitext(name)[1].lstrip(".").lower(),
            ]
            if meta.get("pages"):
                fm.append("pages: %d" % meta["pages"])
            if meta.get("pages_ocr"):
                fm.append("pages_ocr: %d" % meta["pages_ocr"])
                fm.append("ocr_avg_score: %s" % (meta.get("ocr_avg_score") or 0))
            fm += ["---", "", ""]
            md = "\n".join(fm) + md

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md if md.endswith("\n") else md + "\n")

        rec.update(
            ok=True,
            chars=len(md),
            pages=meta.get("pages"),
            pages_ocr=meta.get("pages_ocr") or 0,
            ocr_avg_score=meta.get("ocr_avg_score"),
            warnings=list(meta.get("warnings") or []),
            sha256=sha256_file(src_path),
            title=guess_title(md, os.path.splitext(name)[0]),
        )
    except Exception as e:  # noqa: BLE001
        rec["error"] = "%s: %s" % (type(e).__name__, e)

    rec["seconds"] = round(time.time() - started, 1)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description="批量轉換成 Markdown(含 OCR)")
    ap.add_argument("src", help="來源資料夾")
    ap.add_argument("-o", "--out", required=True, help="輸出資料夾")
    ap.add_argument("--ocr", default="auto", choices=list(core.OCR_MODES),
                    help="auto=只 OCR 沒有文字層的頁(預設);always=全部 OCR;never=不 OCR")
    ap.add_argument("--workers", type=int, default=2, help="平行處理檔數(預設 2)")
    ap.add_argument("--force", action="store_true", help="重新轉換,不跳過已存在的 .md")
    ap.add_argument("--limit", type=int, default=0, help="只處理前 N 個檔案(測試用)")
    ap.add_argument("--front-matter", action="store_true", default=True,
                    help="加入 YAML front matter(預設開啟)")
    ap.add_argument("--no-front-matter", dest="front_matter", action="store_false")
    ap.add_argument("--no-page-markers", action="store_true",
                    help="不要在每頁加 <!-- p.N --> 註記")
    ap.add_argument("--ext", default=",".join(sorted(DOC_EXTS)),
                    help='只轉這些副檔名(逗號分隔);用 "all" 表示全部支援格式。預設:%(default)s')
    args = ap.parse_args()

    src_root = os.path.abspath(args.src)
    out_root = os.path.abspath(args.out)
    if not os.path.isdir(src_root):
        print("找不到資料夾:%s" % src_root, file=sys.stderr)
        return 2

    if args.ext.strip().lower() == "all":
        wanted = set(core.SUPPORTED_EXT)
    else:
        wanted = {"." + e.strip().lstrip(".").lower()
                  for e in args.ext.split(",") if e.strip()}
    files = collect(src_root, wanted)
    if args.limit:
        files = files[: args.limit]
    if not files:
        print("沒有找到可轉換的檔案。", file=sys.stderr)
        return 1

    os.makedirs(out_root, exist_ok=True)
    print("來源:%s" % src_root)
    print("輸出:%s" % out_root)
    print("檔案:%d 個 | OCR 模式:%s | 平行:%d | OCR 可用:%s\n"
          % (len(files), args.ocr, args.workers, core.ocr_available()), flush=True)

    results: list[dict] = []
    t0 = time.time()
    done = 0

    def _progress(rec):
        nonlocal done
        done += 1
        tag = "SKIP" if rec["skipped"] else ("OK  " if rec["ok"] else "FAIL")
        extra = ""
        if rec["ok"] and not rec["skipped"]:
            extra = "%5d 字" % rec["chars"]
            if rec["pages"]:
                extra += " %3d 頁" % rec["pages"]
            if rec["pages_ocr"]:
                extra += " (OCR %d 頁)" % rec["pages_ocr"]
            extra += " %5.1fs" % rec["seconds"]
        elif not rec["ok"]:
            extra = rec["error"] or ""
        print("[%3d/%3d] %s %-58s %s" % (done, len(files), tag,
                                         rec["source"][-58:], extra), flush=True)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(convert_one, f, src_root, out_root, args): f for f in files
        }
        for fut in as_completed(futures):
            rec = fut.result()
            results.append(rec)
            _progress(rec)

    results.sort(key=lambda r: r["source"])
    elapsed = time.time() - t0

    # ---- 報表
    csv_path = os.path.join(out_root, "_report.csv")
    cols = ["source", "md_file", "filename", "category", "ok", "skipped", "chars",
            "pages", "pages_ocr", "ocr_avg_score", "seconds", "sha256",
            "title", "warnings", "error"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in results:
            row = dict(r)
            row["warnings"] = " | ".join(r["warnings"])
            w.writerow({k: row.get(k, "") for k in cols})

    ok = [r for r in results if r["ok"] and not r["skipped"]]
    skipped = [r for r in results if r["skipped"]]
    failed = [r for r in results if not r["ok"]]
    ocr_files = [r for r in results if r["pages_ocr"]]

    index = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source_root": os.path.relpath(src_root, os.path.dirname(out_root)),
        "ocr_mode": args.ocr,
        "total": len(results),
        "converted": len(ok),
        "skipped": len(skipped),
        "failed": len(failed),
        "files": [
            {k: r[k] for k in ("md_file", "title", "category", "chars", "pages",
                               "pages_ocr", "ocr_avg_score", "sha256", "source")}
            | {"needs_review": bool(r["pages_ocr"]) or not r["ok"]}
            for r in results if r["ok"]
        ],
    }
    with open(os.path.join(out_root, "_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 66)
    print("完成:%d 個 | 跳過(已存在):%d | 失敗:%d | 耗時 %.1fs"
          % (len(ok), len(skipped), len(failed), elapsed))
    if ocr_files:
        print("經 OCR 的檔案 %d 個(這些建議人工抽查):" % len(ocr_files))
        for r in ocr_files[:15]:
            print("   %-56s OCR %d/%s 頁  信心 %s" % (
                r["source"][-56:], r["pages_ocr"], r["pages"], r["ocr_avg_score"]))
    if failed:
        print("失敗清單:")
        for r in failed:
            print("   %-56s %s" % (r["source"][-56:], r["error"]))
    print("索引:%s" % os.path.join(out_root, "_index.json"))
    print("報表:%s" % csv_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
