#!/usr/bin/env python3
"""由 check_coverage2 的結果產生 tools/coverage/coverage_report.md。"""
import importlib.util, sys
from pathlib import Path

here = Path(__file__).parent
spec = importlib.util.spec_from_file_location("cc", here / "check_coverage2.py")
cc = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(cc)

rows, matched, missing, files = cc.rows, cc.matched, cc.missing, cc.files
LABELS = cc.LABELS
tot = {c: sum(1 for r in rows if r["cat"] == c) for c in "345"}
miss = {c: sum(1 for r in missing if r["cat"] == c) for c in "345"}

L = []
A = L.append
A("# 官網通告覆蓋率報告")
A("")
A("產生日期：2026-10-29　｜　工具：`tools/coverage/check_coverage2.py`、`build_report.py`")
A("")
A("## 一、摘要")
A("")
A(f"文件庫：**{len(files)} 份 `.md`**（`knowledge/` 79 份 + `政策指引/` 100 份 + `行政/` 22 份 + `資助計劃/` 12 份）")
A(f"官網索引：**{len(rows)} 項**（政策／指引 8 頁、行政 2 頁、資助計劃 1 頁）")
A("")
A("| 分類 | 官網項目 | 已有 | 缺 | 覆蓋率 |")
A("|---|---:|---:|---:|---:|")
for c in "345":
    A(f"| {LABELS[c]} | {tot[c]} | {tot[c]-miss[c]} | {miss[c]} | {(tot[c]-miss[c])/tot[c]*100:.0f}% |")
A(f"| **合計** | **{len(rows)}** | **{len(matched)}** | **{len(missing)}** | **{len(matched)/len(rows)*100:.0f}%** |")
A("")
A("比對方式：檔名／通告編號／內文檔名／人工對照表。**同號不同版（被取代的舊通告）會算作已覆蓋**，")
A("所以「已有」代表「檔案在庫」，不代表內容一定是最新版本。")
A("")
A("## 二、缺口")
A("")
if missing:
    A("| 分類 | 日期 | 檔名 |")
    A("|---|---|---|")
    for r in missing:
        A(f"| {LABELS[r['cat']]} | {r['date']} | `{r['base']}` |")
else:
    A("無。")
A("")
A("## 三、注意事項")
A("")
A("1. `政策指引/`、`行政/`、`資助計劃/` 三個目錄是原始轉換結果：**沒有 front matter、沒有頁碼標記**，")
A("   部分檔名含 OCR 雜訊（例如 `李鉅能基金.md` 開頭有亂碼），引用時要提醒核對原文。")
A("2. `knowledge/` 內的 79 份有完整 front matter（頁數、OCR 頁數、來源分類）與 `<!-- p.N -->` 頁碼標記。")
A("3. 官網連結含內部編號，容易失效，本報告不逐項列出；下載時用目錄頁按檔名搜尋：")
A("")
A("- 政策／指引：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=3>")
A("- 行政：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=4>")
A("- 資助計劃：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=5>")
A("")
A("## 四、重跑方法")
A("")
A("```bash")
A("python3 tools/coverage/check_coverage2.py          # 只看數字")
A("python3 tools/coverage/check_coverage2.py --list   # 列出未覆蓋")
A("python3 tools/coverage/build_report.py             # 重新產生本報告")
A("```")
A("")
A("索引快照：`tools/coverage/site_index_20261029.txt`（188 項，格式 `分類|日期|檔名`）。")

out = here / "coverage_report.md"
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", out)
