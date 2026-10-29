#!/usr/bin/env python3
"""比對官網通告索引快照與 knowledge/ 內的 .md 覆蓋率。"""
import re, unicodedata, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KB = ROOT / "knowledge"
IDX = Path(__file__).with_name("site_index_20261029.txt")

def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"\.(pdf|md)$", "", s.strip())
    s = re.sub(r"[\s_\-–—／/\\()（）\[\]「」“”'\"·,，.。:：;；+&]+", "", s)
    return s

rows = []
for line in IDX.read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    cat, date, base = line.split("|", 2)
    rows.append({"cat": cat, "date": date, "base": base, "n": norm(base)})

files = [p for p in KB.rglob("*.md")]
have = {}
for p in files:
    rel = p.relative_to(KB).as_posix()
    stem = p.stem
    have[norm(stem)] = rel
    # 也登記「去掉中文補述後的檔名」，例如 PC012026C_性罪行… → pc012026c
    head = re.split(r"[_\s]", stem, 1)[0]
    have.setdefault(norm(head), rel)

matched, missing = [], []
for r in rows:
    hit = have.get(r["n"])
    if not hit:
        # 模糊：索引名稱是否以我們的檔名開頭（或反之）
        for k, v in have.items():
            if len(k) >= 6 and (r["n"].startswith(k) or k.startswith(r["n"])):
                hit = v
                break
    (matched if hit else missing).append({**r, "md": hit})

print(f"官網索引：{len(rows)} 項（政策/行政/資助）")
print(f"knowledge/：{len(files)} 份 .md")
print(f"已覆蓋：{len(matched)}　未覆蓋：{len(missing)}\n")

by = {}
for r in missing:
    by.setdefault(r["cat"], []).append(r)
labels = {"3": "政策／指引", "4": "行政", "5": "資助計劃"}
for c in ["3", "4", "5"]:
    tot = sum(1 for r in rows if r["cat"] == c)
    miss = len(by.get(c, []))
    print(f"[{c}] {labels[c]}：{tot} 項，未覆蓋 {miss} 項，覆蓋率 {(tot-miss)/tot*100:.0f}%")

# 依年份看未覆蓋
print("\n未覆蓋（按年份）：")
yr = {}
for r in missing:
    y = r["date"][-4:]
    yr[y] = yr.get(y, 0) + 1
for y in sorted(yr, reverse=True):
    print(f"  {y}: {yr[y]}")

if "--list" in sys.argv:
    print("\n=== 未覆蓋清單 ===")
    for c in ["3", "4", "5"]:
        print(f"\n## [{c}] {labels[c]}")
        for r in by.get(c, []):
            print(f"- {r['date']}  {r['base']}")
else:
    print("\n（加 --list 可列出全部未覆蓋項目）")
