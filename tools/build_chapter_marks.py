#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""為 knowledge/*.md 加上「章節標記」，令前端可以按章節抽段。

做法
----
只在有 `<!-- p.N -->` 頁碼標記、而且偵測到可靠標題的檔案裡，
於標題所在頁的頁碼標記之後插入一行：

    <!-- ch: 第三章 制服配件 -->

- 標題來源依次為：Markdown 標題（#～####）、`第X章／第X節／第X篇`、
  `N.N` 或 `N.N.` 編號小節、`G-801` 這類條號。
- 每份檔案最多留 60 個標記（避免把內文每個編號都當標題）。
- 明顯是 OCR 雜訊（含 `!"#$%`、只有一兩個字、過長、含表格符號）一律不標。
- **偵測不可靠的檔案就不標** —— 前端遇到沒有 `<!-- ch: -->` 的檔案會自動
  退回原本的全文切段檢索（fall back），不會壞。
- 質量守門：大書（>30,000 字）標到少於 6 章、或平均每章超過 30,000 字（等於冇標），
  一律當作「標唔好」，不寫檔。寧可唔標，唔好標錯。

用法
----
    python3 tools/build_chapter_marks.py            # 標記（可重複執行，先清除舊標記）
    python3 tools/build_chapter_marks.py --check    # 只統計，不改檔
    python3 tools/build_chapter_marks.py --list     # 列出每份檔案會標幾多章
"""
from __future__ import annotations

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(ROOT, "knowledge")

MARK_RE = re.compile(r"^[ \t]*<!--\s*ch:.*?-->[ \t]*\n?", re.M)
PAGE_RE = re.compile(r"<!--\s*p\.(\d+)[^>]*-->")
MD_HEAD = re.compile(r"^(#{1,4})\s+(\S.{0,40})$")
CHAP_ZH = re.compile(r"^(第[一二三四五六七八九十百零〇]+[章節篇部])\s*[：:、.]?\s*(\S.{0,38})$")
NUM_SEC = re.compile(r"^(\d{1,2}\.\d{1,2}\.?)\s*(\S.{1,38})$")
CODE_SEC = re.compile(r"^([A-Z]-\d{3})\s*(\S.{0,38})$")
JUNK = ("!\"#$%", "&'()*", "||", "|", "��", "``", "。", "，", "：", "；", "「", "（", "(", "?", "？")
MAX_MARKS = 60
# 「第一章 6．領巾…」這類是頁眉＋內文混在一起，不是標題
HEAD_MIX = re.compile(r"^第[一二三四五六七八九十百零〇]+[章節篇部]\s*[0-9０-９]")


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("**", "").replace("`", "")).strip(" *#:：.")


def is_junk(title: str) -> bool:
    if not (2 <= len(title) <= 30):
        return True
    if HEAD_MIX.match(title):
        return True
    if any(j in title for j in JUNK):
        return True
    cjk = sum(1 for c in title if "\u4e00" <= c <= "\u9fff")
    latin = sum(1 for c in title if c.isascii() and c.isalnum())
    return (cjk + latin) < max(2, len(title) // 3)


def strip_paren(s: str) -> str:
    """「第三節 原地向右轉 (Turning at the halt)」→ 只留中文部分。"""
    m = re.search(r"[（(]", s)
    if m and m.start() >= 2:
        return s[: m.start()].strip()
    return s


def detect(title_line: str):
    """回傳 (標題, 層級)；層級 1＝章，2＝節。"""
    raw = strip_paren(title_line.rstrip())
    m = MD_HEAD.match(raw.strip())
    if m:
        t = clean(m.group(2))
        if not is_junk(t):
            return t, 1 if len(m.group(1)) <= 2 else 2
        return None
    s = clean(raw)
    for rx, lvl in ((CHAP_ZH, 1), (CODE_SEC, 2), (NUM_SEC, 2)):
        m = rx.match(s)
        if not m:
            continue
        t = clean(m.group(1) + " " + m.group(2)) if rx is CHAP_ZH else clean(s)
        if not is_junk(t):
            return t[:44], lvl
    return None


def strip_docname(title: str, docname: str) -> str:
    cands = [docname, docname.split("_")[0], docname.replace("_全書", ""), docname.replace("_第二版", "")]
    for c in cands:
        if c and len(c) >= 3 and c in title:
            t = clean(title.replace(c, ""))
            if len(t) >= 2:
                title = t
                break
    return title


def scan(text: str):
    """回傳 [(頁碼位置, 頁碼, 標題, 層級)]，位置＝標題行在原文的 offset。"""
    body = PAGE_RE.sub(lambda m: m.group(0), text)
    pages = [(m.start(), int(m.group(1))) for m in PAGE_RE.finditer(body)]
    found = []
    for i, (pos, page) in enumerate(pages):
        end = pages[i + 1][0] if i + 1 < len(pages) else len(body)
        for off, line in enumerate(body[pos:end].split("\n")):
            got = detect(line)
            if got:
                found.append((pos, page, got[0], got[1]))
                break
    return found


def plan(text: str, docname: str = ""):
    """決定要插入哪些標記；回傳 (要插入的 [(標題, 頁碼, 層級)], 理由)。"""
    found = scan(text)
    if not found:
        return [], "no-heading"
    chapters = [f for f in found if f[3] == 1]
    def norm(s):
        return re.sub(r"[\s\-_/·・、,，.。:：()（）「」]", "", s)

    picked = []
    for _, page, title, lvl in found:
        title = strip_docname(title, docname)
        nt = norm(title)
        dup = any(nt in norm(p[0]) or norm(p[0]) in nt for p in picked[-2:])
        if dup:
            continue
        picked.append((title, page, lvl))
        if len(picked) >= MAX_MARKS:
            break
    # 質量守門：大書（>30,000 字）如果只標到幾章，等於冇標 —— 寧可唔標，讓前端 fall back
    if len(text) > 30000:
        if len(picked) < 6:
            return [], "too-few(%d)" % len(picked)
        if len(text) / len(picked) > 30000:
            return [], "too-sparse(%d)" % len(picked)
    if len(chapters) >= 2:
        return picked, "ok-chapters"
    if len(picked) >= 3:
        return picked, "ok-sections"
    return [], "too-few(%d)" % len(picked)


def apply(text: str, picked):
    """在每個標題所在頁的頁碼標記後面插入 <!-- ch: ... -->。"""
    out = []
    last = 0
    for title, page, _lvl in picked:
        # 找該頁的第一個頁碼標記
        m = re.search(r"<!--\s*p\.%d[^>]*-->" % page, text[last:])
        if not m:
            continue
        at = last + m.end()
        out.append(text[last:at])
        out.append("\n<!-- ch: %s -->" % title)
        last = at
    out.append(text[last:])
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只統計，不改檔")
    ap.add_argument("--list", action="store_true", help="列出每份檔案的章節數")
    args = ap.parse_args()

    files, marked, skipped, total_marks = [], 0, [], 0
    for dp, _dirs, names in os.walk(KB):
        for name in sorted(names):
            if name.endswith(".md"):
                files.append(os.path.join(dp, name))
    files.sort()

    for path in files:
        rel = os.path.relpath(path, KB)
        raw = open(path, encoding="utf-8", errors="replace").read()
        text = MARK_RE.sub("", raw)          # 先清掉舊標記，可重複執行
        base = os.path.basename(path).rsplit(".", 1)[0]
        picked, why = plan(text, base)
        if why.startswith("ok"):
            marked += 1
            total_marks += len(picked)
            if args.list:
                print("%-64s %3d 章  %s" % (rel, len(picked), why))
            if not args.check:
                new = apply(text, picked)
                if new != text:
                    open(path, "w", encoding="utf-8").write(new)
                if raw != new and not args.check:
                    pass
        else:
            skipped.append((rel, why))
            if not args.check and raw != text:   # 之前標錯，現已不合格 → 移除標記
                open(path, "w", encoding="utf-8").write(text)

    print("\n有標記：%d / %d 份，共 %d 個章節標記" % (marked, len(files), total_marks))
    by = {}
    for _rel, why in skipped:
        by[why] = by.get(why, 0) + 1
    print("未標記（前端會 fall back 全文檢索）：", ", ".join("%s=%d" % kv for kv in sorted(by.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
