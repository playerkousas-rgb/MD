#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse the checked-in collection list (童軍PDF補收清單_含下載連結.md) into a
machine-readable download manifest. Purely local parsing: NO network access and
NO guessing of URLs. Every download URL comes verbatim from the list file.

The only additions are:
  * a category folder assignment for each item (documented in FOLDER_LOGIC),
  * one extra item X1, whose URL is taken verbatim from the list's own
    「配套與更新提示」 section (the alternate P22/2026 attachment),
  * URL-decoded official filenames,
  * a disambiguation suffix when two official filenames would collide.
"""
import json
import os
import re
from urllib.parse import urlparse, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MD = os.path.join(ROOT, "童軍PDF補收清單_含下載連結.md")
DRIVE_META = os.path.join(HERE, "drive_meta.json")
OUT = os.path.join(HERE, "scout_pdf_manifest.json")

FOLDERS = {
    "01": "01_POR及會章",
    "02": "02_支部訓練綱要",
    "03": "03_政策及安全指引",
    "04": "04_行政及領袖訓練",
    "05": "05_資助計劃",
    "06": "06_配套表格",
    "07": "07_地域及屬會專用",
}

# Classification decisions (see 分類說明.md in the deliverable):
#  01 POR / constitution .............. item 58
#  02 Branch training syllabuses ..... 07, 08, 59-63 (+ X1 alternate attachment)
#  04 Admin / leader training ........ 25-32, 42, 64-69
#  05 Subsidy scheme forms ........... 72-79 (all named subsidy application forms)
#  06 Other supplementary forms ...... 71
#  07 Region / affiliate specific .... 51, 52, 54, 57, 70  (flagged in the list)
#  03 Policy & safety guidelines ..... all remaining 政策／指引 items
MAP = {}


def assign(nums, key):
    for n in nums:
        MAP["%02d" % n] = key


assign([58], "01")
assign([7, 8, 59, 60, 61, 62, 63], "02")
assign(list(range(25, 33)) + [42] + list(range(64, 70)), "04")
assign(list(range(72, 80)), "05")
assign([71], "06")
assign([51, 52, 54, 57, 70], "07")


def extract_version(title):
    """Only return a version/circular code when the list's title states one."""
    groups = re.findall(r"[（(]([^）)]*)[）)]", title)
    codes = []
    for g in groups:
        g = g.strip()
        if re.search(r"\d", g) and (
            "/" in g or "／" in g
            or re.match(r"(?i)^(P|T|AC|ACR|PC|PCR|DEV|PT|CIR)\d", g)
        ):
            codes.append(g)
    return codes[-1] if codes else ""


def safe_filename(name):
    name = name.replace("/", "／").replace("\\", "＼")
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    return name.strip()


text = open(MD, encoding="utf-8").read()
drive_meta = json.load(open(DRIVE_META, encoding="utf-8")) if os.path.exists(DRIVE_META) else {}

blocks = re.split(r"(?m)^###\s+", text)
items = []
for block in blocks[1:]:
    head, _, rest = block.partition("\n")
    m = re.match(r"(\d+)\.\s*(.+)", head.strip())
    if not m:
        continue
    num = "%02d" % int(m.group(1))
    title = m.group(2).strip()

    kv = re.search(r"-\s*類別：([^；\n]+)；狀態：([^\n]+)", rest)
    category = kv.group(1).strip() if kv else ""
    status = kv.group(2).strip() if kv else ""

    links = re.findall(r"\[([^\]]*)\]\((https?://[^)]+)\)", rest)
    pdf_url = next((u for label, u in links if "PDF直連" in label), "")
    src_url = next((u for label, u in links if "官方目錄" in label), "")
    nm = re.search(r"(?m)^-\s*注意：([^\n]+)", rest)
    note = nm.group(1).strip() if nm else ""

    parsed = urlparse(pdf_url)
    is_drive = "drive.google.com" in parsed.netloc
    if is_drive:
        fid_m = re.search(r"/d/([^/]+)", pdf_url)
        fid = fid_m.group(1) if fid_m else ""
        official = drive_meta.get(fid, {}).get("name", "") or ("%s_%s.pdf" % (num, title))
        download_url = "https://drive.google.com/uc?export=download&id=%s" % fid
        source_type = "google_drive"
    else:
        fid = ""
        official = unquote(parsed.path.rsplit("/", 1)[-1]) or ("%s_%s.pdf" % (num, title))
        download_url = pdf_url
        source_type = "scout_org_hk"

    items.append({
        "id": num,
        "title": title,
        "category_field": category,
        "status_field": status,
        "official_source_url": pdf_url,
        "source_page_url": src_url,
        "download_url": download_url,
        "note": note,
        "official_filename": official,
        "final_filename": safe_filename(official),
        "folder": FOLDERS[MAP.get(num, "03")],
        "version": extract_version(title),
        "source_type": source_type,
        "drive_file_id": fid,
    })

# Extra item: URL taken verbatim from the list's 配套與更新提示 section.
items.append({
    "id": "X1",
    "title": "新修訂支部訓練綱要（P22/2026）— 支部訓練檢討頁所連通告附件",
    "category_field": "支部訓練（附加核對）",
    "status_field": "需人工核對是否與通告目錄版本相同",
    "official_source_url": "https://www.scout.org.hk/uploads/tc/circulars/23585/p022-26.pdf",
    "source_page_url": "https://sites.google.com/scouting.org.hk/sections/支部訓練檢討",
    "download_url": "https://www.scout.org.hk/uploads/tc/circulars/23585/p022-26.pdf",
    "note": "清單「配套與更新提示」指出支部訓練檢討頁與通告目錄曾指向P22/2026的不同附件路徑，需核對兩者內容及修訂／過渡安排。此為對照用附件，並非清單內第80個跟進項目。",
    "official_filename": "p022-26.pdf",
    "final_filename": "p022-26_[支部頁附件23585].pdf",
    "folder": FOLDERS["02"],
    "version": "P22/2026",
    "source_type": "scout_org_hk",
    "drive_file_id": "",
})

# Avoid overwriting when different sources share one official filename.
seen = {}
for it in items:
    key = it["final_filename"].lower()
    if key in seen:
        stem, ext = os.path.splitext(it["final_filename"])
        it["final_filename"] = safe_filename("%s_[src_%s]%s" % (stem, it["id"], ext))
        it["note"] += " 官方檔名與項目 %s 相同，已附加來源識別避免覆蓋。" % seen[key]
    seen[it["final_filename"].lower()] = it["id"]

manifest = {
    "source_list": "童軍PDF補收清單_含下載連結.md",
    "list_date": "2026-10-27",
    "list_scope_note": "第一輪官網檢查，不是全站完整審核，亦未逐份重新下載驗證所有連結。",
    "followup_item_count": 79,
    "manifest_item_count": len(items),
    "items": items,
}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

from collections import Counter
c = Counter(i["folder"] for i in items)
print("manifest written:", OUT)
print("total manifest items:", len(items), "(79 follow-up items + 1 comparison attachment)")
for k in sorted(c):
    print("  %s: %d" % (k, c[k]))
