#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finalize pre-authorized Google Drive resumable upload sessions.

Runs on the GitHub Actions runner, which has unrestricted outbound internet.
It reads tools/upload_sessions.json (session URIs created by the Drive
connector), streams each local PDF to its session URI with HTTP PUT, then
writes tools/upload_results.json with the Drive file id / SHA-256 returned by
Google. No Drive OAuth token is needed: the session URI is pre-authorized.
"""
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSIONS = os.path.join(ROOT, "tools", "upload_sessions.json")
RESULTS = os.path.join(ROOT, "tools", "upload_results.json")
CHUNK = 256 * 1024  # Google requires 256 KiB chunks except the final one


def put(uri, offset, total, body, finalize, extra_headers=None):
    cmd = "upload, finalize" if finalize else "upload"
    headers = {
        "Content-Type": "application/pdf",
        "Content-Length": str(len(body)),
        "X-Goog-Upload-Offset": str(offset),
        "X-Goog-Upload-Command": cmd,
    }
    if total is not None:
        headers["X-Goog-Upload-Total-Size"] = str(total)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(uri, data=body, method="PUT", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def main():
    cfg = json.load(open(SESSIONS, encoding="utf-8"))
    sessions = cfg["sessions"]
    results = []
    if os.path.exists(RESULTS):
        results = json.load(open(RESULTS, encoding="utf-8")).get("results", [])
    done = {r["id"] for r in results if r.get("status") == "ok"}

    for s in sessions:
        sid = s["id"]
        if sid in done:
            print("[skip] %s already finalized" % sid, flush=True)
            continue
        path = os.path.join(ROOT, "out", "dl", s["folder"], s["file_name"])
        rec = {"id": sid, "file_name": s["file_name"], "folder": s["folder"]}
        if not os.path.isfile(path):
            rec.update(status="error", error="local file missing: " + path)
            results.append(rec)
            print("[FAIL] %s missing" % sid, flush=True)
            continue
        data = open(path, "rb").read()
        sha = hashlib.sha256(data).hexdigest()
        rec["local_sha256"] = sha
        rec["local_size"] = len(data)
        if len(data) != s["size"]:
            rec.update(status="error", error="size mismatch: %d vs %d" % (len(data), s["size"]))
            results.append(rec)
            print("[FAIL] %s size mismatch" % sid, flush=True)
            continue

        uri = s["session_uri"]
        total = len(data)
        final_response = None
        status_code = None
        try:
            if total <= CHUNK:
                # Single request: can finalize in one shot.
                status_code, hdrs, body = put(uri, 0, total, data, True)
                final_response = (status_code, hdrs, body)
            else:
                # Multi-chunk; each non-final chunk is exactly 256 KiB.
                offset = 0
                while offset < total:
                    chunk = data[offset:offset + CHUNK]
                    is_last = (offset + len(chunk) >= total)
                    status_code, hdrs, body = put(uri, offset, total, chunk, is_last)
                    offset += len(chunk)
                    if is_last:
                        final_response = (status_code, hdrs, body)
                    else:
                        ust = (hdrs.get("X-Goog-Upload-Status") or
                               hdrs.get("x-goog-upload-status") or "")
                        print("  %s chunk -> %s status=%s" % (sid, status_code, ust), flush=True)
                        if status_code not in (200, 201, 308):
                            raise RuntimeError("chunk failed %s: %s" % (status_code, body[:300]))
            sc, hdrs, body = final_response
            rec["http_status"] = sc
            rec["upload_status"] = hdrs.get("X-Goog-Upload-Status") or hdrs.get("x-goog-upload-status")
            text = body.decode("utf-8", "replace")
            rec["response"] = text[:2000]
            if sc in (200, 201):
                try:
                    j = json.loads(text)
                    rec["drive_id"] = j.get("id")
                    rec["drive_sha256"] = j.get("sha256Checksum")
                    rec["drive_size"] = j.get("size")
                    rec["drive_name"] = j.get("name")
                    rec["parents"] = j.get("parents")
                    rec["status"] = "ok"
                except Exception as e:
                    rec.update(status="error", error="non-JSON final response: %r" % e)
            else:
                rec.update(status="error", error="final HTTP %s" % sc)
        except Exception as e:
            rec.update(status="error", error=repr(e))

        print("[%s] %s %s http=%s %s" % (
            rec["status"].upper(), sid, s["file_name"], rec.get("http_status"),
            (rec.get("error") or rec.get("drive_id") or "")), flush=True)
        # keep only the newest record per id
        results = [r for r in results if r["id"] != sid] + [rec]
        json.dump({"results": results}, open(RESULTS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    ok = sum(1 for r in results if r["status"] == "ok")
    bad = [r for r in results if r["status"] != "ok"]
    print("\nTOTAL ok=%d failed=%d" % (ok, len(bad)), flush=True)
    for r in bad:
        print("  FAIL %s %s :: %s :: %s" % (r["id"], r["file_name"], r.get("error"), r.get("response", "")[:300]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
