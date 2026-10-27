#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build tools/upload_sessions.json from a compact TSV.

TSV columns: id <TAB> upload_id <TAB> session_crd
(For record files, prefix the id with "R:".)

Session URIs are one-time pre-authorized credentials. Instead of committing
them into the (public) repo tree, publish the JSON as a dangling Git blob and
commit only its SHA; the Actions runner fetches the blob by SHA.
"""
import base64
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV = os.path.join(ROOT, "tools", "session_uris.tsv")
PLAN = os.path.join(ROOT, "out", "upload_plan.json")
OUT = os.path.join(ROOT, "tools", "upload_sessions.json")
BLOBSHA = os.path.join(ROOT, "tools", "upload_sessions_blob.txt")

BASE = ("https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable"
        "&supportsAllDrives=True&upload_id={uid}&session_crd={crd}"
        "&upload_protocol=resumable")


def main():
    plan = {x["id"]: x for x in json.load(open(PLAN, encoding="utf-8"))["plan"]}
    rows = []
    for line in open(TSV, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        sid, uid, crd = parts[0].strip(), parts[1].strip(), parts[2].strip()
        uri = uid if uid.startswith("https://") else BASE.format(uid=uid, crd=crd)
        if sid.startswith("R:"):
            name = sid[2:]
            rows.append({
                "id": "REC_" + name, "file_name": name, "folder": "下載及上載紀錄",
                "folder_id": "1MIB7xz0wfQVRWFlH8y4ozpQ1dgmUVlOD",
                "size": 0, "sha256": "", "session_uri": uri,
                "content_mime_type": "text/csv" if name.endswith(".csv") else "text/markdown",
                "local_path": os.path.join("下載及上載紀錄", name),
            })
            continue
        p = plan[sid]
        rows.append({
            "id": sid, "file_name": p["name"], "folder": p["folder"],
            "folder_id": p["folder_id"], "size": p["size"], "sha256": p["sha256"],
            "session_uri": uri, "content_mime_type": "application/pdf",
        })

    seen = set()
    for r in rows:
        if r["id"] in seen:
            raise SystemExit("duplicate id in TSV: " + r["id"])
        seen.add(r["id"])
        if not r["file_name"]:
            raise SystemExit("empty file name for " + r["id"])
    cfg = {"note": "one-time pre-authorized Drive resumable sessions",
           "sessions": rows}
    json.dump(cfg, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("sessions:", len(rows))

    raw = open(OUT, "rb").read()
    payload = os.path.join(ROOT, "out", "_blob_payload.json")
    json.dump({"content": base64.b64encode(raw).decode(), "encoding": "base64"},
              open(payload, "w"))
    repo = subprocess.check_output(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        text=True, cwd=ROOT).strip()
    sha = subprocess.check_output(
        ["gh", "api", "-X", "POST", "repos/%s/git/blobs" % repo,
         "--input", payload, "-q", ".sha"], text=True, cwd=ROOT).strip()
    open(BLOBSHA, "w").write(sha + "\n")
    print("blob sha:", sha, "bytes:", len(raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
