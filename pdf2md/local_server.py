#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本機預覽 pdf2md(Vercel 版)。

Vercel 只會把 api/convert.py 當函數跑;本機用這支把「靜態頁 + /api」湊起來,
方便測試,不用每改一次就部署一次。

    cd pdf2md
    PDF_ENGINE=pdfium python local_server.py      # http://localhost:8001
"""

from __future__ import annotations

import os
import sys
import mimetypes
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from api.convert import handler as ApiHandler  # noqa: E402

PUBLIC = os.path.join(HERE, "public")


class Router(ApiHandler):
    """ /api/* 交給 Vercel 那個 handler;其餘由 public/ 出靜態檔。"""

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api"):
            return super().do_GET()
        self._serve_static()

    def do_POST(self):  # noqa: N802
        if self.path.startswith("/api"):
            return super().do_POST()
        self._plain(405, "只支援 GET")

    # ---------------- 靜態檔 ----------------
    def _serve_static(self):
        path = self.path.split("?")[0]
        if path in ("/", ""):
            path = "/index.html"
        target = os.path.normpath(os.path.join(PUBLIC, path.lstrip("/")))
        if not target.startswith(PUBLIC) or not os.path.isfile(target):
            return self._plain(404, "Not found: %s" % path)
        ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype.endswith("javascript"):
            ctype += "; charset=utf-8"
        with open(target, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _plain(self, status: int, msg: str):
        body = msg.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8001"))
    print("pdf2md 本機預覽 → http://localhost:%d" % port)
    print("PDF 引擎:%s" % ("以環境變數指定" if os.environ.get("PDF_ENGINE") else "自動"))
    ThreadingHTTPServer(("0.0.0.0", port), Router).serve_forever()
