#!/usr/bin/env python3
"""由 check_coverage 的結果產生 tools/coverage/coverage_report.md。"""
import importlib.util, re, sys
from pathlib import Path

here = Path(__file__).parent
spec = importlib.util.spec_from_file_location("cc", here / "check_coverage.py")
cc = importlib.util.module_from_spec(spec)
sys.argv = ["x"]           # 避免觸發 --list
spec.loader.exec_module(cc)

rows, matched, missing = cc.rows, cc.matched, cc.missing
labels = {"3": "政策／指引", "4": "行政", "5": "資助計劃"}

def prior(r):
    """粗略優先次序：1 最高。"""
    b, y = r["base"], r["date"][-4:]
    if y == "2018" and b.startswith(("PC", "AG", "AC")):
        return (1, "常設政策／活動指引（2018 年整批重發，仍屬現行）")
    if re.match(r"(PC|ACR|PolicyCircular|PCR|CIR|pau|RC|2026-C|Subsidy|AdmCir|AI|AiS)", b, re.I):
        return (1, "政策通告／行政通告")
    if re.match(r"(P\d|T\d|IT|UG|TN|GNFM|Circular)", b, re.I):
        return (2, "開辦指引／訓練通告")
    return (3, "其他")

tot = {c: sum(1 for r in rows if r["cat"] == c) for c in "345"}
miss = {c: sum(1 for r in missing if r["cat"] == c) for c in "345"}

L = []
A = L.append
A("# 官網通告覆蓋率報告")
A("")
A("產生日期：2026-10-29　｜　工具：`tools/coverage/check_coverage.py`、`build_report.py`")
A("")
A("## 一、摘要")
A("")
A("| 分類 | 官網項目 | 已有 MD | 缺 | 覆蓋率 |")
A("|---|---:|---:|---:|---:|")
for c in "345":
    A(f"| {labels[c]} | {tot[c]} | {tot[c]-miss[c]} | {miss[c]} | {(tot[c]-miss[c])/tot[c]*100:.0f}% |")
A(f"| **合計** | **{sum(tot.values())}** | **{sum(tot.values())-len(missing)}** | **{len(missing)}** | **{(sum(tot.values())-len(missing))/sum(tot.values())*100:.0f}%** |")
A("")
A(f"`knowledge/` 現有 {len(cc.files)} 份 `.md`。其中 {len(matched)} 份對應到官網上列三類通告；"
  f"其餘 {len(cc.files)-len(matched)} 份是支部訓練綱要、POR、會章、表格及地域文件，不在這三份清單內。")
A("")
A("## 二、缺口集中在哪裡")
A("")
yr = {}
for r in missing:
    yr[r["date"][-4:]] = yr.get(r["date"][-4:], 0) + 1
A("| 年份 | 缺 |")
A("|---|---:|")
for y in sorted(yr, reverse=True):
    A(f"| {y} | {yr[y]} |")
A("")
A("## 三、建議補收次序")
A("")
groups = {}
for r in missing:
    p, name = prior(r)
    groups.setdefault((p, name), []).append(r)
for (p, name) in sorted(groups):
    items = sorted(groups[(p, name)], key=lambda r: (r["cat"], -int(r["date"][-4:])))
    A(f"### 優先 {p}：{name}（{len(items)} 項）")
    A("")
    A("| 分類 | 日期 | 檔名 |")
    A("|---|---|---|")
    for r in items:
        A(f"| {labels[r['cat']]} | {r['date']} | `{r['base']}` |")
    A("")
A("## 四、下載連結")
A("")
A("本報告不含逐項 PDF 直連（官網連結含內部編號，容易失效）。下載時用目錄頁：")
A("")
A("- 政策／指引：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=3>")
A("- 行政：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=4>")
A("- 資助計劃：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=5>")
A("")
A("按檔名搜尋即可（例如搜 `PC-062022_C`）。")
A("")
A("## 五、重跑方法")
A("")
A("```bash")
A("python3 tools/coverage/check_coverage.py          # 只看數字")
A("python3 tools/coverage/check_coverage.py --list   # 列出全部未覆蓋")
A("python3 tools/coverage/build_report.py            # 重新產生本報告")
A("```")
A("")
A("索引快照：`tools/coverage/site_index_20261029.txt`（188 項，格式 `分類|日期|檔名`）。")

out = here / "coverage_report.md"
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote", out, len(L), "lines")
