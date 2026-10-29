#!/usr/bin/env python3
"""覆蓋率比對 v2：同時比對檔名＋通告編號，並涵蓋 repo 內全部 4 個文件目錄。"""
import re, unicodedata, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDX = Path(__file__).with_name("site_index_20261029.txt")
DIRS = ["knowledge"]
LABELS = {"3": "政策／指引", "4": "行政", "5": "資助計劃"}

def norm(s):
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"\.(pdf|md)$", "", s.strip())
    return re.sub(r"[\s_\-–—／/\\()（）\[\]「」“”'\"·,，.。:：;；+&]+", "", s)

# ---------- 官網索引 ----------
rows = []
for line in IDX.read_text(encoding="utf-8").splitlines():
    if not line.strip() or line.startswith("#"):
        continue
    cat, date, base = line.split("|", 2)
    rows.append({"cat": cat, "date": date, "base": base, "n": norm(base)})

# ---------- 由 PDF 檔名推通告編號 ----------
def numkey(base):
    b = unicodedata.normalize("NFKC", base).strip()
    b = re.sub(r"\.(pdf|PDF)$", "", b)
    # 1) PC012018C / ACR612018_C / AG042018C / AC022018C / PCR022022C
    m = re.match(r"^(PC|ACR|PCR|AC|AG)[_\- ]?(\d{2})[_\- ]?(\d{4})[_ ]?C?", b, re.I)
    if m:
        return (int(m.group(2)), int(m.group(3)))
    # 2) P110-26 / P022-26 / P008-26- / P0101-10
    m = re.match(r"^P(\d{1,4})[\-_ ]?(\d{2,4})", b, re.I)
    if m:
        y = m.group(2)
        return (int(m.group(1)), int(y) if len(y) == 4 else 2000 + int(y))
    # 3) T3125_Apr / T525_Feb / T4315_Jul / T7420_Nov / T6521_Oct
    m = re.match(r"^T(\d{2,4})", b, re.I)
    if m:
        d = m.group(1)
        if len(d) == 4:
            return (int(d[:2]), 2000 + int(d[2:]))
        if len(d) == 3:
            return (int(d[0]), 2000 + int(d[1:]))
    # 4) IT01-23 / CIR_0523 / RC0125C
    m = re.match(r"^(?:IT|CIR|RC)[_\- ]?(\d{2})[_\- ]?(\d{2})", b, re.I)
    if m:
        return (int(m.group(1)), 2000 + int(m.group(2)))
    return None

for r in rows:
    r["num"] = numkey(r["base"])
    r["year"] = int(r["date"][-4:])


# ---------- 人工對照表：官網 PDF 檔名 → 本地檔（檔名與內文都對不上時用） ----------
OVERRIDES = {
    # 官網 PDF 檔名（去掉 .pdf）      本地檔名（只寫檔名，路徑自動找）
    "C_Safety_Precaution_in_Scout_Pioneering": "進行童軍先鋒工程活動安全須知.md",
    "guidelines_Chi_2021": "童軍成員向外界發放童軍消息注意事項.md",
    "P114-16": "深資童軍支部之訓練班.md",
    "P091-15": "樂行童軍支部各級徽章簽發及領取／購買方法.md",
    "P059-15": "童軍支部「童軍探索獎章」與幼童軍支部各級徽章豁免考驗安排.md",
    "P110-13": "小童軍支部各級徽章簽發及購買方法.md",
    "ACR0912C_R": "透過本會網頁獲取資訊及以「電子郵件」方式收取本會文件.md",
    "P092-11": "「童軍露營訓練班」開辦指引.md",
    "P0101-10": "深資童軍支部之學習時數.md",
    "ITCR0109C": "童軍網站指引.md",
    "UG0002": "童軍網站指引.md",
    "P174-04": "童軍專科徽章訓練班及考驗.md",
    "ACR0704C": "申請佩戴紀念章指引.md",
    "P105-04": "樂行童軍擔任領袖工作.md",
    "P084S-00": "特能童軍活動 - 傷健共融.md",
    "T032000Feb": "借用場地舉辦訓練班的注意事項.md",
    "SubsidyScheme02_2026Apr_C_ssnlt": "有經濟需要之童軍領袖訓練資助計劃（2026 - 2027）.md",
    "SubsidyScheme03_2026Apr_C_os": "青年領袖發展計劃（海外活動津貼）（2026 - 2027）.md",
    "AdmCir302020_LTIFoundationSubsidy_C_Final": "領袖訓練學院基金「進修資助計劃」申請章則及指引.md",
}
BY_BASENAME = {}

# ---------- 本地檔案 ----------
CIRCRE = re.compile(r"第\s*[*_]{0,2}\s*([0-9]{1,3})\s*[\/⁄∕]\s*([0-9]{2,4})\s*[*_]{0,2}\s*號")
files = []
for d in DIRS:
    for p in (ROOT / d).rglob("*.md"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        nums = set()
        for m in CIRCRE.finditer(txt[:2500]):
            a, y = int(m.group(1)), m.group(2)
            nums.add((a, int(y) if len(y) == 4 else 2000 + int(y)))
        files.append({"path": p.relative_to(ROOT).as_posix(), "n": norm(p.stem),
                      "nums": nums, "size": len(txt),
                      "body": norm(txt[:4000])})

for f in files:
    BY_BASENAME[Path(f["path"]).name] = f["path"]

by_name = {}
for f in files:
    by_name.setdefault(f["n"], f["path"])
    head = re.split(r"[_\s]", Path(f["path"]).stem, 1)[0]
    by_name.setdefault(norm(head), f["path"])
num_index = {}
for f in files:
    for k in f["nums"]:
        num_index.setdefault(k, []).append(f["path"])

matched, missing = [], []
for r in rows:
    if r["base"] in OVERRIDES and OVERRIDES[r["base"]] in BY_BASENAME:
        (matched if True else missing).append({**r, "md": BY_BASENAME[OVERRIDES[r["base"]]], "how": "對照表"})
        continue
    hit = by_name.get(r["n"])
    how = "檔名" if hit else None
    if not hit:
        for k, v in by_name.items():
            if len(k) >= 6 and (r["n"].startswith(k) or k.startswith(r["n"])):
                hit, how = v, "檔名(模糊)"
                break
    if not hit and len(r["n"]) >= 5:
        for f in files:
            if r["n"] in f["body"]:
                hit, how = f["path"], "內文檔名"
                break
    if not hit and r["num"]:
        a, y = r["num"]
        y = y or r["year"]
        if (a, y) in num_index:
            hit, how = num_index[(a, y)][0], "編號"
    (matched if hit else missing).append({**r, "md": hit, "how": how})

tot = {c: sum(1 for r in rows if r["cat"] == c) for c in "345"}
miss = {c: sum(1 for r in missing if r["cat"] == c) for c in "345"}

if __name__ == "__main__":
    print(f"文件庫：{len(files)} 份 .md（{'、'.join(DIRS)}）")
    print(f"官網索引：{len(rows)} 項\n")
    print("| 分類 | 官網 | 已有 | 缺 | 覆蓋率 |")
    print("|---|---:|---:|---:|---:|")
    for c in "345":
        print(f"| {LABELS[c]} | {tot[c]} | {tot[c]-miss[c]} | {miss[c]} | {(tot[c]-miss[c])/tot[c]*100:.0f}% |")
    print(f"| **合計** | **{len(rows)}** | **{len(matched)}** | **{len(missing)}** | **{len(matched)/len(rows)*100:.0f}%** |")
    hows = {}
    for r in matched:
        hows[r["how"]] = hows.get(r["how"], 0) + 1
    print("\n比對方式：", hows)
    if "--list" in sys.argv:
        for c in "345":
            print(f"\n## [{c}] {LABELS[c]} 未覆蓋")
            for r in missing:
                if r["cat"] == c:
                    print(f"- {r['date']}  {r['base']}")
