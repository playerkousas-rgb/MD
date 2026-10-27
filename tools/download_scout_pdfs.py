#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Download every URL in scout_pdf_manifest.json, VERIFY it is a real PDF
(not a login/error HTML page), dedupe by SHA-256, and write categorised files
plus a machine-readable report.

Verification rules (deliberately strict — the URL's .pdf extension is never
trusted on its own):
  * HTTP status 200
  * first 5 bytes == b'%PDF-'
  * '%%EOF' present in the last 8 KiB
  * size >= 1 KiB
  * HTML/JSON error signatures in the first bytes => reject
"""
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import zipfile
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "scout_pdf_manifest.json")
OUT = os.environ.get("SCOUT_OUT", os.path.join(os.path.dirname(HERE), "out"))
REPORT = os.path.join(OUT, "download_report.json")
VERIFIED = os.path.join(OUT, "verified_manifest.json")
SUMMARY = os.path.join(OUT, "download_summary.txt")
ZIP_PATH = os.path.join(os.path.dirname(HERE), "童軍PDF補收_分類PDF.zip")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


def fetch(url):
    last_error = ""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENTS[attempt % len(USER_AGENTS)],
                "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
                "Referer": "https://www.scout.org.hk/",
            })
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = resp.read()
                return resp.status, resp.headers.get("Content-Type", ""), resp.geturl(), data, ""
        except urllib.error.HTTPError as e:
            last_error = "HTTP %s %s" % (e.code, e.reason)
        except Exception as e:  # noqa: BLE001
            last_error = "%s: %s" % (type(e).__name__, e)
        time.sleep(2 + attempt * 2)
    return None, "", url, b"", last_error


def verify_pdf(data):
    if not data or len(data) < 1024:
        return False, "失敗：檔案過小 (<1KB) 或沒有內容"
    if data[:5] != b"%PDF-":
        head = data[:400].lower()
        if b"<html" in head or b"<!doctype" in head or b"<title" in head:
            return False, "失敗：取得 HTML 網頁（登入頁／錯誤頁／權限頁），不是 PDF"
        if b"{" in data[:1] or head.lstrip().startswith(b"{"):
            return False, "失敗：取得 JSON／API 回應，不是 PDF"
        return False, "失敗：檔首不是 %%PDF-，不是有效 PDF"
    if b"%%EOF" not in data[-8192:]:
        return False, "失敗：找不到 PDF 結尾標記 %%EOF，檔案可能不完整"
    return True, "已驗證為 PDF（%PDF- 檔首 + %%EOF 結尾）"


def main():
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    items = manifest["items"]
    os.makedirs(OUT, exist_ok=True)
    for folder in sorted({i["folder"] for i in items}):
        os.makedirs(os.path.join(OUT, folder), exist_ok=True)

    report, seen_sha = [], {}
    for idx, it in enumerate(items, 1):
        status, ctype, final_url, data, err = fetch(it["download_url"])
        ok, reason = verify_pdf(data)
        rec = dict(it)
        rec.update({
            "http_status": status,
            "content_type": ctype,
            "actual_download_url": final_url,
            "size_bytes": len(data),
            "sha256": "",
            "verify": reason,
            "process_status": "success" if ok else "failed",
            "duplicate_of": "",
            "error": err,
            "local_path": "",
        })
        if ok:
            sha = hashlib.sha256(data).hexdigest()
            rec["sha256"] = sha
            if sha in seen_sha:
                rec["process_status"] = "duplicate"
                rec["duplicate_of"] = seen_sha[sha]
                rec["verify"] = "已驗證為 PDF；SHA-256 與項目 %s 完全相同，去重略過" % seen_sha[sha]
            else:
                seen_sha[sha] = it["id"]
                path = os.path.join(OUT, it["folder"], it["final_filename"])
                with open(path, "wb") as f:
                    f.write(data)
                rec["local_path"] = os.path.relpath(path, OUT)
        else:
            if not rec["error"]:
                rec["error"] = reason
        report.append(rec)
        print("[%02d/%d] %s %s | %s | %d bytes | %s" % (
            idx, len(items), it["id"], it["final_filename"][:48],
            rec["process_status"], rec["size_bytes"], rec["verify"][:60]), flush=True)

    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"report": report, "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                  f, ensure_ascii=False, indent=2)
    with open(VERIFIED, "w", encoding="utf-8") as f:
        json.dump({"manifest": manifest["manifest_item_count"], "report": report},
                  f, ensure_ascii=False, indent=2)

    counts = Counter(r["process_status"] for r in report)
    lines = [
        "童軍 PDF 補收 — 下載驗證摘要",
        "清單跟進項目：79；本次處理網址：%d（79 + 1 對照附件）" % len(report),
        "成功下載並驗證 PDF：%d" % counts.get("success", 0),
        "重複（SHA-256 相同）略過：%d" % counts.get("duplicate", 0),
        "無法下載／驗證失敗：%d" % counts.get("failed", 0),
        "",
        "失敗項目：",
    ]
    for r in report:
        if r["process_status"] == "failed":
            lines.append("  - [%s] %s → %s (%s)" % (
                r["id"], r["title"], r["verify"], r["error"]))
    with open(SUMMARY, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # Categorised ZIP fallback (used only if Drive upload is unavailable).
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, _dirs, files in os.walk(OUT):
            for name in sorted(files):
                full = os.path.join(root, name)
                if name.endswith((".json", ".txt")):
                    continue
                z.write(full, os.path.relpath(full, OUT))
    print("\n" + "\n".join(lines), flush=True)
    print("ZIP:", ZIP_PATH, os.path.getsize(ZIP_PATH), "bytes", flush=True)


if __name__ == "__main__":
    main()
