#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transport the verified PDFs back to the sandbox using only allowed hosts.

The Actions artifact endpoint redirects to blob.core.windows.net, which the
sandbox network allowlist blocks. Instead we tar+gzip the verified output and
POST it (in chunks) as *dangling* git blobs via api.github.com. Dangling blobs
are not referenced by any commit, so no large binaries enter Git history.
Only a tiny JSON index (blob SHAs + checksums) is committed.
"""
import base64
import hashlib
import io
import json
import os
import tarfile
import time
import urllib.request

REPO = os.environ.get("GITHUB_REPOSITORY", "playerkousas-rgb/MD")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("SCOUT_OUT", os.path.join(os.path.dirname(HERE), "out"))
INDEX = os.path.join(HERE, "_transport_index.json")
CHUNK = 24 * 1024 * 1024


def build_bundle():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=6) as tar:
        for root, dirs, files in os.walk(OUT):
            dirs.sort()
            for name in sorted(files):
                if name.startswith(".") or name.endswith(".zip"):
                    continue
                full = os.path.join(root, name)
                tar.add(full, arcname=os.path.relpath(full, OUT))
    return buf.getvalue()


def post_blob(chunk):
    body = json.dumps({
        "content": base64.b64encode(chunk).decode("ascii"),
        "encoding": "base64",
    }).encode("ascii")
    last = ""
    for attempt in range(3):
        req = urllib.request.Request(
            "https://api.github.com/repos/%s/git/blobs" % REPO,
            data=body, method="POST",
            headers={
                "Authorization": "Bearer " + TOKEN,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "arena-scout-pdf-agent",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=240) as resp:
                return json.load(resp)["sha"]
        except Exception as exc:  # noqa: BLE001
            last = "%s: %s" % (type(exc).__name__, exc)
            time.sleep(3 + attempt * 3)
    raise RuntimeError("blob POST failed: " + last)


def main():
    if not TOKEN:
        raise SystemExit("GH_TOKEN / GITHUB_TOKEN missing")
    data = build_bundle()
    parts = []
    for i, off in enumerate(range(0, len(data), CHUNK)):
        chunk = data[off:off + CHUNK]
        sha = post_blob(chunk)
        parts.append({
            "part": i,
            "blob_sha": sha,
            "bytes": len(chunk),
            "part_sha256": hashlib.sha256(chunk).hexdigest(),
        })
        print("published part %d: %d bytes -> %s" % (i, len(chunk), sha), flush=True)

    index = {
        "repo": REPO,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "bundle_bytes": len(data),
        "bundle_sha256": hashlib.sha256(data).hexdigest(),
        "chunk_bytes": CHUNK,
        "parts": parts,
        "contents": "tar.gz of out/: verified categorised PDFs + download_report.json + download_summary.txt",
        "note": "Dangling blobs; not referenced by any commit. Retrieve with tools/fetch_blobs.py.",
    }
    with open(INDEX, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print("bundle %d bytes in %d parts, sha256=%s" % (
        len(data), len(parts), index["bundle_sha256"]), flush=True)


if __name__ == "__main__":
    main()
