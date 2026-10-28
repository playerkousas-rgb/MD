#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 gemini/index.html + knowledge/ 打包成一個可以雙擊即用的單檔 HTML。

為什麼要這樣做:
    gemini/index.html 用 fetch("../knowledge/_index.json") 讀知識庫。
    用 file:// 直接雙擊時,瀏覽器一律擋掉 fetch(同源政策),頁面會顯示
    「讀不到 _index.json」。要麼起一個 http server,要麼把資料塞進 HTML 裡。

    這個腳本選後者:產出 gemini/童軍問答-單檔.html,79 份文件全部內嵌,
    雙擊就能問問題,不需要 server、不需要安裝任何東西。

用法:
    python3 tools/build_gemini_single.py
    python3 tools/build_gemini_single.py --check    # 只驗證不重寫
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, "knowledge")
SRC = os.path.join(ROOT, "gemini", "index.html")
OUT = os.path.join(ROOT, "gemini", "童軍問答-單檔.html")

BANNER = """<!--
  單檔版:79 份文件全部內嵌,雙擊即可使用,不需要伺服器。
  由 tools/build_gemini_single.py 自動產生,請勿手改。
  要更新:重跑 python3 tools/build_gemini_single.py
-->
"""


def load_kb() -> tuple[dict, dict[str, str]]:
    idx_path = os.path.join(KB, "_index.json")
    with open(idx_path, encoding="utf-8") as f:
        index = json.load(f)

    texts: dict[str, str] = {}
    missing = []
    for item in index.get("files", []):
        rel = item["md_file"].replace("\\", "/")
        path = os.path.join(KB, rel.replace("/", os.sep))
        if not os.path.exists(path):
            missing.append(rel)
            continue
        with open(path, encoding="utf-8") as f:
            texts[rel] = f.read()

    if missing:
        raise SystemExit("索引列出但找不到的檔案:\n  " + "\n  ".join(missing))
    if len(texts) != index.get("total"):
        raise SystemExit("索引 total=%s 但讀到 %d 份" % (index.get("total"), len(texts)))
    return index, texts


def embed(index: dict, texts: dict[str, str]) -> str:
    """產生內嵌用的一段 JavaScript。用 JSON 確保跳脫正確。"""
    payload = json.dumps(texts, ensure_ascii=False, separators=(",", ":"))
    # </script> 出現在內容裡會提早結束 script 區塊,必須切開
    payload = payload.replace("</", "<\\/")
    idx = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
    idx = idx.replace("</", "<\\/")
    return (
        "<script>\n"
        "/* 內嵌知識庫:--kb-embedded-- */\n"
        "window.__KB_INDEX__ = " + idx + ";\n"
        "window.__KB_TEXTS__ = " + payload + ";\n"
        "</script>\n"
    )


def patch(src: str) -> str:
    """把原本靠 fetch 的邏輯換成讀內嵌資料。"""
    # 1) KB 路徑不再需要
    src = src.replace(
        'const KB = (new URLSearchParams(location.search).get("kb")\n'
        '        || (location.pathname.includes("/gemini/") ? "../knowledge" : "./knowledge"))\n'
        '        .replace(/\\/+$/, "");',
        'const EMBEDDED = true;   /* 單檔版:資料已內嵌,不需要 fetch */\n'
        'const KB = "";',
    )

    # 2) init:直接用內嵌索引
    old_init = """(async function init() {
  $("#key").value = localStorage.getItem("geminiKey") || "";
  $("#model").value = localStorage.getItem("geminiModel") || "gemini-2.5-flash";
  try {
    const res = await fetch(KB + "/_index.json");
    if (!res.ok) throw new Error("HTTP " + res.status);
    index = await res.json();
    renderDocs();
    $("#count").textContent =
      `${index.files.length} 份文件 · ${index.total} 個來源檔 · 轉換於 ${(index.generated_at || "").slice(0, 16)}`;
  } catch (e) {
    $("#count").textContent = "";
    $("#note").innerHTML =
      `讀不到 <code>${KB}/_index.json</code>(${e.message})。<br>` +
      `確認 <code>knowledge/_index.json</code> 與這頁在同一個站上,或用 <code>?kb=&lt;網址&gt;</code> 指定位置。`;
  }
})();"""
    new_init = """(async function init() {
  $("#key").value = localStorage.getItem("geminiKey") || "";
  $("#model").value = localStorage.getItem("geminiModel") || "gemini-2.5-flash";
  try {
    index = window.__KB_INDEX__;
    if (!index) throw new Error("內嵌資料缺失");
    renderDocs();
    const layout = (index.files || []).filter((f) => f.layout).length;
    $("#count").textContent =
      `${index.files.length} 份文件 · 約 ${Math.round(index.files.reduce((a, f) => a + f.chars, 0) / 10000)} 萬字` +
      ` · 有排版 ${layout} 份 · 轉換於 ${(index.generated_at || "").slice(0, 16)}`;
  } catch (e) {
    $("#count").textContent = "";
    $("#note").innerHTML = `初始化失敗:${e.message}`;
  }
})();"""
    assert src.count(old_init) == 1, "找不到原本的 init()"
    src = src.replace(old_init, new_init, 1)

    # 3) loadDoc:改讀內嵌文字
    old_load = """async function loadDoc(f) {
  if (cache.has(f.md_file)) return cache.get(f.md_file);
  const res = await fetch(KB + "/" + encodeURI(f.md_file));
  const text = res.ok ? await res.text() : "";
  cache.set(f.md_file, text);
  return text;
}"""
    new_load = """async function loadDoc(f) {
  const key = String(f.md_file).replace(/\\\\/g, "/");
  if (cache.has(key)) return cache.get(key);
  const text = window.__KB_TEXTS__[key] || "";
  cache.set(key, text);
  return text;
}"""
    assert src.count(old_load) == 1, "找不到原本的 loadDoc()"
    src = src.replace(old_load, new_load, 1)

    # 4) 文件預覽的「開新頁」連結:file:// 下無意義,改成提示
    src = src.replace(
        '$("#pvLink").href = KB + "/" + encodeURI(f.md_file);',
        '$("#pvLink").style.display = "none";',
    )
    return src


def build() -> str:
    index, texts = load_kb()
    with open(SRC, encoding="utf-8") as f:
        src = f.read()

    src = patch(src)
    block = embed(index, texts)

    marker = "<script>\nconst $ ="
    assert src.count(marker) == 1, "找不到主要 script 開頭"
    src = src.replace(marker, block + marker, 1)

    src = src.replace("<head>", "<head>\n" + BANNER, 1)
    return src


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只檢查產物是否為最新")
    args = ap.parse_args()

    html = build()
    if args.check:
        if not os.path.exists(OUT):
            print("[FAIL] 尚未產生 %s" % os.path.relpath(OUT, ROOT))
            return 1
        old = open(OUT, encoding="utf-8").read()
        same = old == html
        print("[%s] %s" % ("OK" if same else "FAIL",
                           "產物與來源一致" if same else "產物已過期,請重跑"))
        return 0 if same else 1

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    size = os.path.getsize(OUT)
    print("[OK] 已產生 %s (%.1f KB)" % (os.path.relpath(OUT, ROOT), size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
