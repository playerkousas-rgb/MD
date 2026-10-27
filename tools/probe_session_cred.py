#!/usr/bin/env python3
"""Probe whether a Drive resumable session credential can authenticate the
regular Drive API. Prints status codes only; never prints the credential."""
import json
import os
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = json.load(open(os.path.join(ROOT, "tools", "upload_sessions.json"), encoding="utf-8"))
uri = cfg["sessions"][0]["session_uri"]
qs = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query)
crd = qs["session_crd"][0]
print("credential present:", bool(crd), "length:", len(crd), flush=True)

tests = [
    ("bearer-about", "https://www.googleapis.com/drive/v3/about?fields=user",
     {"Authorization": "Bearer " + crd}),
    ("bearer-list", "https://www.googleapis.com/drive/v3/files?pageSize=1&fields=files(id)",
     {"Authorization": "Bearer " + crd}),
    ("xg-header", "https://www.googleapis.com/drive/v3/files?pageSize=1&fields=files(id)",
     {"X-Goog-Upload-Session-Credential": crd}),
]
verdicts = {}
for name, url, headers in tests:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            code = r.status
            r.read()
    except urllib.error.HTTPError as e:
        code = e.code
        e.read()
    except Exception as e:
        code = "ERR:" + type(e).__name__
    verdicts[name] = code
    print("%s -> %s" % (name, code), flush=True)

json.dump(verdicts, open(os.path.join(ROOT, "out", "cred_probe.json"), "w"), indent=2)
print("GENERAL_TOKEN:", any(v == 200 for v in verdicts.values()), flush=True)
