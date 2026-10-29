#!/usr/bin/env python3
"""產生「需要下載」清單：tools/coverage/下載清單_20261029.md

三層：
  A 完全缺（官網有、庫內找不到）
  B 建議重下（開頭有 OCR 雜訊，重轉可修正）
  C 可選（只為補頁碼標記，內容已可用）
"""
from __future__ import annotations
import importlib.util
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("cc", HERE / "check_coverage2.py")
cc = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(cc)

ROOT = cc.ROOT
LABELS = cc.LABELS

# 官網 PDF 直連（抓取時記錄；連結含內部編號，日後可能失效）
DIRECT = {
    "pau_poster_012023": "https://www.scout.org.hk/uploads/tc/circulars/13298/pau_poster_012023.pdf",
    "P006-25": "https://www.scout.org.hk/uploads/tc/circulars/18701/P006-25.pdf",
    "P008-25": "https://www.scout.org.hk/uploads/tc/circulars/18709/P008-25.pdf",
    "P031-20": "https://www.scout.org.hk/article_attach/33790/P031-20.pdf",
    "P077-22": "https://www.scout.org.hk/uploads/tc/circulars/8785/P077-22.pdf",
    "P091-15": "https://www.scout.org.hk/article_attach/24373/P091-15.pdf",
    "IT01_0420040621": "https://www.scout.org.hk/article_attach/1754/IT01_0420040621.pdf",
    "P037-19": "https://www.scout.org.hk/article_attach/31942/P037-19.pdf",
    "P110-13": "https://www.scout.org.hk/article_attach/21011/P110-13.pdf",
}


def fm(text: str) -> dict:
    m = re.match(r"^---\r?\n([\s\S]*?)\r?\n---", text)
    out = {}
    if not m:
        return out
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


rows = []
for p in sorted((ROOT / "knowledge").rglob("*.md")):
    t = p.read_text(encoding="utf-8", errors="ignore")
    meta = fm(t)
    rows.append({
        "path": p.relative_to(ROOT).as_posix(),
        "cat": p.parent.name,
        "name": p.stem,
        "no": meta.get("notice_no", ""),
        "date": meta.get("notice_date", ""),
        "type": meta.get("notice_type", ""),
        "noisy": meta.get("quality") == "ocr-noisy",
        "pages": bool(re.search(r"<!--\s*p\.\d+", t)),
        "chars": len(t),
    })

missing = cc.missing
noisy = [r for r in rows if r["noisy"]]
no_page = [r for r in rows if not r["pages"] and not r["noisy"]]

L = []
A = L.append
A("# 下載清單（2026-10-29）")
A("")
A(f"文件庫現有 **{len(rows)} 份**；官網三類通告共 **{len(cc.rows)} 項**，已覆蓋 **{len(cc.matched)} 項（{len(cc.matched)/len(cc.rows)*100:.0f}%）**。")
A("")
A("## A. 完全缺（必須下載）")
A("")
if missing:
    A("| # | 分類 | 日期 | 官網檔名 | 下載 |")
    A("|---:|---|---|---|---|")
    for i, r in enumerate(missing, 1):
        link = DIRECT.get(r["base"])
        A(f"| {i} | {LABELS[r['cat']]} | {r['date']} | `{r['base']}` | "
          + (f"[PDF]({link})" if link else "官網搜尋") + " |")
    A("")
    A("> `pau_poster_012023` 是龍獅藝團招募**海報**，不是正式通告。可下載可不理。")
else:
    A("**無。** 三類通告全部已有檔案。")
A("")
A(f"## B. 建議重下（{len(noisy)} 份，開頭有 OCR 雜訊）")
A("")
A("這批內容主體正確，但開頭有亂碼（例如 `vv VY i Bubih ~~a~~ 李鉅能基金`）。")
A("重新下載原 PDF 再轉換即可修正。")
A("")
A("| # | 通告 | 檔案 | 下載 |")
A("|---:|---|---|---|")
for i, r in enumerate(sorted(noisy, key=lambda x: (x["cat"], x["name"])), 1):
    link = DIRECT.get(r["no"].replace("/", "-") + "-" + r["no"].split("/")[1][-2:]) if r["no"] else None
    A(f"| {i} | {r['no'] or '—'} | `{r['cat']}/{r['name']}` | "
      + (f"[PDF]({link})" if link else "官網搜尋") + " |")
A("")
A(f"## C. 可選（{len(no_page)} 份，只為補頁碼標記）")
A("")
A("內容已足夠作答（這些檔案都 <30KB，會整份送給模型），只是**沒有 `<!-- p.N -->` 頁碼標記**，")
A("所以答案的「根據」只能顯示檔名、不能顯示第幾頁。想補頁碼才需要重下 PDF。")
A("")
A("<details><summary>展開完整清單</summary>")
A("")
A("| # | 通告 | 檔案 |")
A("|---:|---|---|")
for i, r in enumerate(sorted(no_page, key=lambda x: (x["cat"], x["no"]), reverse=False), 1):
    A(f"| {i} | {r['no'] or '—'} | `{r['cat']}/{r['name']}` |")
A("")
A("</details>")
A("")
A("## 下載方式")
A("")
A("官網目錄（按檔名或通告編號搜尋）：")
A("")
A("- 政策／指引：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=3>")
A("- 行政：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=4>")
A("- 資助計劃：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=5>")
A("")
A("下載後放入 `out/dl/`，再跑：")
A("")
A("```bash")
A("cd markitdown-web && python batch_convert.py ../out/dl -o ../knowledge --ocr auto")
A("```")
A("")
A("## 檔案清單")
A("")
A("全部 213 份的通告編號、日期、字數、雜訊標記：`tools/coverage/knowledge_manifest.csv`。")

out = HERE / "下載清單_20261029.md"
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", out)
print(f"A={len(missing)} B={len(noisy)} C={len(no_page)}")
