#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Retrieve the PDF bundle published by publish_blobs.py (sandbox side).
Uses only api.github.com / github.com, which are on the sandbox allowlist.
"""
import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile

REPO = os.environ.get("GITHUB_REPOSITORY", "playerkousas-rgb/MD")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "tools", "_transport_index.json")
DEST = os.path.join(ROOT, "out", "dl")


def api(blob_sha):
    path = "/tmp/blob_%s.json" % blob_sha[:12]
    r = subprocess.run(
        ["gh", "api", "repos/%s/git/blobs/%s" % (REPO, blob_sha)],
        capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError("gh api failed for %s: %s" % (blob_sha, r.stderr[:400]))
    d = json.loads(r.stdout)
    return base64.b64decode(d["content"])


def main():
    idx = json.load(open(INDEX, encoding="utf-8"))
    print("bundle: %d bytes, %d parts, sha256=%s" % (
        idx["bundle_bytes"], len(idx["parts"]), idx["bundle_sha256"]))
    chunks = []
    for p in idx["parts"]:
        data = api(p["blob_sha"])
        assert len(data) == p["bytes"], "part %d size mismatch" % p["part"]
        assert hashlib.sha256(data).hexdigest() == p["part_sha256"], "part %d checksum mismatch" % p["part"]
        chunks.append(data)
        print("  part %d ok (%d bytes)" % (p["part"], len(data)), flush=True)
    bundle = b"".join(chunks)
    assert hashlib.sha256(bundle).hexdigest() == idx["bundle_sha256"], "bundle checksum mismatch"
    os.makedirs(DEST, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:gz") as tar:
        tar.extractall(DEST)
    print("extracted to", DEST, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
