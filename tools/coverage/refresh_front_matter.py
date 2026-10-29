#!/usr/bin/env python3
"""重算 knowledge/ 內 legacy-raw 檔案的 front matter（可重複執行）。

用途：抽取邏輯改進後，不必重新搬檔，直接更新 front matter。
    python3 tools/coverage/refresh_front_matter.py --dry-run
    python3 tools/coverage/refresh_front_matter.py
"""
from __future__ import annotations
import argparse
import csv
import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("nm", HERE / "notice_meta.py")
nm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nm)

FMRE = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n")


def build(category: str, meta: dict, junk: bool) -> str:
    lines = ["---", f'source_category: "{category}"', 'source_format: "pdf"', 'pipeline: "legacy-raw"']
    if meta.get("notice_type"):
        lines.append(f'notice_type: "{meta["notice_type"]}"')
    if meta.get("notice_no"):
        lines.append(f'notice_no: "{meta["notice_no"]}"')
    if meta.get("notice_date"):
        lines.append(f'notice_date: "{meta["notice_date"]}"')
    lines.append('ocr_engine: "unknown"')
    if junk:
        lines.append('quality: "ocr-noisy"')
    lines += ["---", "", ""]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    changed = 0
    manifest = []
    for p in sorted((ROOT / "knowledge").rglob("*.md")):
        text = p.read_text(encoding="utf-8", errors="ignore")
        m = FMRE.match(text)
        if not m or 'pipeline: "legacy-raw"' not in m.group(1):
            continue
        body = text[m.end():]
        meta = nm.extract_meta(body)
        junk = nm.junk_flag(body)
        new_fm = build(p.parent.name, meta, junk)
        new = new_fm + body
        manifest.append({
            "category": p.parent.name, "file": p.name,
            "notice_type": meta.get("notice_type", ""),
            "notice_no": meta.get("notice_no", ""),
            "notice_date": meta.get("notice_date", ""),
            "chars": len(body), "ocr_noisy": "yes" if junk else "",
        })
        if new != text:
            changed += 1
            if a.dry_run:
                print(f"[DRY] {p.relative_to(ROOT)}")
            else:
                p.write_text(new, encoding="utf-8")
    if not a.dry_run and manifest:
        out = HERE / "knowledge_manifest.csv"
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["category", "file", "notice_type", "notice_no",
                                              "notice_date", "chars", "ocr_noisy"])
            w.writeheader()
            w.writerows(manifest)
        print(f"清單寫入 {out.relative_to(ROOT)}（{len(manifest)} 份）")
    print(f"{'（dry-run）' if a.dry_run else ''}更新 {changed} 份")


if __name__ == "__main__":
    main()
