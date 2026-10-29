#!/usr/bin/env python3
"""
把 repo 根目錄三個原始轉換目錄（政策指引／行政／資助計劃）收納入 knowledge/，
補上與 knowledge/ 一致的 front matter，並產生檔案清單。

用法：
    python3 tools/migrate_into_knowledge.py --dry-run   # 只印會做甚麼
    python3 tools/migrate_into_knowledge.py             # 真正執行

設計原則：
- 只搬位置、只加 front matter 開頭，正文一個字都不改。
- 不改 knowledge/_index.json（前端用 GitHub trees 自動發現，不靠索引）。
- 被取代的舊版本移到 archive/（在 knowledge/ 之外，所以不會被問答頁讀到）。
"""
from __future__ import annotations
import argparse
import csv
import re
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 來源目錄 → knowledge 分類
MOVE_MAP = {
    "政策指引": "knowledge/03_政策及安全指引",
    "行政": "knowledge/04_行政及領袖訓練",
    "資助計劃": "knowledge/05_資助計劃",
}

# 明確改名（OCR 產生的重複／缺字）
RENAME = {
    "「童軍先鋒工程訓練班 「童軍先鋒工程訓練班」開辦指引": "「童軍先鋒工程訓練班」開辦指引",
}

# 根目錄被取代的舊版本
SUPERSEDED = [
    ("por_c_20251114_.md", "archive/舊版本/por_c_20251114_.md", "POR 舊版（knowledge/01_POR及會章/POR_C_20260917.md 為現行版）"),
    ("會章.md", "archive/舊版本/會章_202307.md", "會章 07/2023 版（已由 POR_C_20260917 收錄）"),
]

CIRCRE = re.compile(r"第\s*[*_]{0,2}\s*([0-9]{1,3})\s*[/⁄∕]\s*([0-9]{2,4})\s*[*_]{0,2}\s*號")
DATEREC = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
TYPES = ["青少年活動通告", "資助計劃通告", "訓練通告", "政策通告", "行政通告", "活動指引", "通告"]


def clean_name(stem: str) -> str:
    """修掉 OCR 造成的多餘空格與重複標題。"""
    s = stem.strip()
    if s in RENAME:
        return RENAME[s]
    # 「A 「A」開辦指引」→「A」開辦指引
    m = re.match(r"^「(.+?) 「(.+?)」", s)
    if m and m.group(1) == m.group(2):
        s = "「" + m.group(2) + "」" + s[m.end():]
    # 中文之間的空格去掉（保留英文與數字之間）
    s = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", s)
    s = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[（「」／、])", "", s)
    s = re.sub(r"(?<=[）「」／、])\s+(?=[\u4e00-\u9fff])", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def extract_meta(text: str) -> dict:
    """抽取通告類型／編號／日期。只在文件開頭找，避免內文引用其他通告。"""
    head = unicodedata.normalize("NFKC", text[:2500])
    out: dict[str, str] = {}
    m = CIRCRE.search(head)
    if m:
        no, yr = m.group(1), m.group(2)
        out["notice_no"] = f"{int(no)}/{yr if len(yr) == 4 else '20' + yr}"
        ctx = head[max(0, m.start() - 16): m.start()] + "|" + head[m.end(): m.end() + 12]
        for t in TYPES:
            if t in ctx:
                out["notice_type"] = t
                break
    d = DATEREC.search(head)
    if d:
        y, mo, dy = d.group(1), int(d.group(2)), int(d.group(3))
        if 2000 <= int(y) <= 2100 and 1 <= mo <= 12 and 1 <= dy <= 31:
            out["notice_date"] = f"{y}-{mo:02d}-{dy:02d}"
    return out


def junk_flag(text: str) -> bool:
    """開頭是否有明顯 OCR 雜訊（用來標示需要重新轉換）。"""
    head = text[:400]
    if "~~" in head or "\ufffd" in text:
        return True
    lat = len(re.findall(r"[A-Za-z]{2,}", head))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", head))
    return lat > 6 and cjk < 15


def front_matter(category: str, meta: dict, junk: bool) -> str:
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

    manifest, moved = [], 0
    for src_name, dst_name in MOVE_MAP.items():
        src = ROOT / src_name
        if not src.exists():
            continue
        dst = ROOT / dst_name
        category = dst.name
        for p in sorted(src.glob("*.md")):
            text = p.read_text(encoding="utf-8", errors="ignore")
            stem = clean_name(p.stem)
            target = dst / f"{stem}.md"
            if target.exists() and target.resolve() != p.resolve():
                target = dst / f"{stem}_2.md"
            meta = extract_meta(text)
            junk = junk_flag(text)
            if text.startswith("---"):
                body = text                       # 已有 front matter，不再加
            else:
                body = front_matter(category, meta, junk) + text
            print(f"{'[DRY] ' if a.dry_run else ''}{p.relative_to(ROOT)}  →  {target.relative_to(ROOT)}")
            if not a.dry_run:
                target.write_text(body, encoding="utf-8")
                p.unlink()
            moved += 1
            manifest.append({
                "category": category,
                "file": target.name,
                "notice_type": meta.get("notice_type", ""),
                "notice_no": meta.get("notice_no", ""),
                "notice_date": meta.get("notice_date", ""),
                "chars": len(text),
                "ocr_noisy": "yes" if junk else "",
            })
        if not a.dry_run and src.exists() and not any(src.iterdir()):
            src.rmdir()
            print(f"  移除空目錄 {src_name}/")

    # 被取代的舊版本
    arch = ROOT / "archive" / "舊版本"
    for src_rel, dst_rel, why in SUPERSEDED:
        src = ROOT / src_rel
        if not src.exists():
            continue
        dst = ROOT / dst_rel
        print(f"{'[DRY] ' if a.dry_run else ''}{src_rel}  →  {dst_rel}   （{why}）")
        if not a.dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

    if not a.dry_run:
        arch.mkdir(parents=True, exist_ok=True)
        (ROOT / "archive" / "README.md").write_text(
            "# archive/ — 舊版本（不參與問答）\n\n"
            "這裡的檔案**不會**被 AI SCOUT 讀取（前端只讀 `knowledge/`）。\n"
            "保留原因：查歷史沿革、比較新舊條文。\n\n"
            "| 檔案 | 說明 |\n|---|---|\n"
            + "\n".join(f"| `{d.split('/')[-1]}` | {w} |" for _, d, w in SUPERSEDED)
            + "\n", encoding="utf-8")

        csv_path = ROOT / "tools" / "coverage" / "knowledge_manifest.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["category", "file", "notice_type", "notice_no",
                                              "notice_date", "chars", "ocr_noisy"])
            w.writeheader()
            w.writerows(manifest)
        print(f"\n搬運 {moved} 份；清單寫入 {csv_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
