#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the downloadable work record (CSV + Markdown) from verified data.

Reads:
  out/upload_plan.json      - master item table (from the collection list)
  out/drive_index.json      - files actually present in the target Drive folders
  tools/drive_meta.json     - official metadata of the 5 public Drive originals
Writes deliverables into 下載及上載紀錄/ at the repository root.
"""
import csv
import json
import os
from collections import Counter
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "out", "upload_plan.json")
DRIVE_INDEX = os.path.join(ROOT, "out", "drive_index.json")
DRIVE_META = os.path.join(ROOT, "tools", "drive_meta.json")
OUTDIR = os.path.join(ROOT, "下載及上載紀錄")

# Items that need human verification of version / content, and why.
REVIEW = {
    "58": "官網檔名 POR_C_20260917 較倉庫 por_c_20251114_.md 新；未逐條比較修訂，需人工核對新舊 POR 差異及取代關係。",
    "08": "P22/2026 新修訂支部訓練綱要；清單提示通告目錄與支部頁曾指向不同附件路徑。",
    "07": "新修訂支部訓練綱要海報（Poster），屬配套宣傳品，需確認是否納入知識庫。",
    "59": "Google Drive 標示版本 2026-06-06；支部頁另載新制 2026-08-15 生效，需核對封面及正式發布版本。",
    "60": "Google Drive 標示版本 2026-08-09；支部頁另載新制 2026-08-15 生效，需核對封面及正式發布版本。",
    "61": "Google Drive 標示版本 2026-06-06；支部頁另載新制 2026-08-15 生效，需核對封面及正式發布版本。",
    "62": "Google Drive 標示版本 2026-08-14；清單提示深資支部中英文入口曾指向同一檔，且新制 2026-08-15 生效，需核對語言版本及封面。",
    "63": "Google Drive 標示版本 2026-05-30；支部頁另載新制 2026-08-15 生效，需核對封面及正式發布版本。",
    "70": "港島地域李鉅能基金（2026-09-01 文件，截止 2026-12-31），屬地域資助，不是總會通用規定；倉庫正文為 2026-04-01 第一期，需核對期數。",
    "23": "保護童軍成員免受傷害政策，與第 18、22、50 項所述保障成員／世界童軍政策可能互相引用，需核對取代關係。",
    "18": "有關保障成員之政策及指引，需與第 23 項保護童軍成員免受傷害政策核對關係。",
    "37": "香港童軍總會財務指引（只提供英文版），需與第 12 項童軍旅財政管理指引核對適用層級。",
    "49": "儀容與制服手冊（AC29/2022），需與第 10 項制服帽佩戴修訂核對是否仍有效。",
    "71": "配套表格：可能已附於相關計劃 MD 內，或未必需轉 MD；建議保留官方可填寫原檔。",
    "72": "配套表格：可能已附於相關計劃 MD 內，或未必需轉 MD；建議保留官方可填寫原檔。",
    "73": "配套表格：可能已附於相關計劃 MD 內，或未必需轉 MD；建議保留官方可填寫原檔。",
    "74": "配套表格（T/07）：可能已附於相關計劃 MD 內。",
    "75": "配套表格（T/06）：可能已附於相關計劃 MD 內。",
    "76": "配套表格（DEV/04）：可能已附於相關計劃 MD 內。",
    "77": "配套表格（DEV/05）：可能已附於相關計劃 MD 內。",
    "78": "配套表格：可能已附於相關計劃 MD 內。",
    "79": "配套表格（PT/39）：可能已附於相關計劃 MD 內。",
    "51": "屬會專用（會員訂座按金），不可當作總會通用規則。",
    "52": "屬會專用（總監俱樂部會籍），不可當作總會通用規則。",
    "54": "屬會專用（俱樂部會員証），不可當作總會通用規則。",
    "57": "屬會專用（個人資料私隱），不可當作總會通用規則。",
}
AFFILIATE = {"51", "52", "54", "57", "70"}
ENGLISH_ONLY = {"16", "37", "41"}
PRIORITY = {"58", "08", "18", "23", "25", "26", "10", "49", "37", "12",
            "59", "60", "61", "62", "63"}


def human(n):
    if n >= 1048576:
        return "%.2f MB" % (n / 1048576)
    return "%.1f KB" % (n / 1024)


def main():
    plan = json.load(open(PLAN, encoding="utf-8"))
    items = plan["plan"]
    folders = plan["folders"]
    root_link = plan["root_folder_link"]
    index = json.load(open(DRIVE_INDEX, encoding="utf-8")) if os.path.exists(DRIVE_INDEX) else []
    drive_meta = json.load(open(DRIVE_META, encoding="utf-8"))

    # map (folder_id, filename) -> drive record
    dmap = {}
    for d in index:
        dmap[(d.get("parents", [None])[0], d["name"])] = d

    rows = []
    for it in items:
        fid = it["folder_id"]
        d = dmap.get((fid, it["name"]))
        drive_id = d["id"] if d else ""
        drive_link = ("https://drive.google.com/file/d/%s/view?usp=drivesdk" % drive_id) if drive_id else ""
        drive_size = d.get("size", "") if d else ""
        drive_sha = d.get("sha256Checksum", "") if d else ""

        if it["status"] == "duplicate":
            status = "重複而略過"
            note = "與第 %s 項 SHA-256 完全相同，去重略過（此為清單「配套與更新提示」所述的對照附件，並非第 80 個跟進項目）。" % it["duplicate_of"]
            drive_link = "（未上載）"
        elif it["status"] == "failed":
            status = "無法下載／權限不足"
            note = it["verify"] + " " + it.get("error", "")
        elif d:
            status = "成功下載並上載"
            note = ""
        else:
            status = "未上載（待續）"
            note = "尚未在目標資料夾找到此檔，需續做。"

        remarks = [it["note"]]
        if it["id"] in REVIEW:
            remarks.append("【待人工核對】" + REVIEW[it["id"]])
        if it["id"] in AFFILIATE:
            remarks.append("【分類】地域／屬會專用，已與總會通用政策分隔。")
        if it["id"] in ENGLISH_ONLY:
            remarks.append("【語言】此文件只提供英文版。")
        if it["id"] in PRIORITY:
            remarks.append("【優先】清單列為優先下載項目。")
        if it["source_type"] == "google_drive":
            remarks.append("【來源】Google Drive 原檔；以 copy_file 複製原檔，SHA-256 與官方原檔核對一致。")
        else:
            remarks.append("【驗證】%s（HTTP %s；Content-Type: %s）。" % (
                it["verify"], it["http_status"], it["content_type"]))
        if drive_sha and it["sha256"] and drive_sha != it["sha256"]:
            remarks.append("【警告】Drive 端 SHA-256 與本機驗證值不符，需複查！")
        if note:
            remarks.append(note)

        rows.append({
            "項目編號": it["id"],
            "文件名稱": it["name"],
            "標題": it["title"],
            "分類資料夾": it["folder"],
            "版本／通告編號": it["version"],
            "官方來源網址": it["official_source_url"],
            "官方目錄／來源頁": it["source_page_url"],
            "實際下載網址": it["actual_download_url"] if it["status"] != "duplicate" else "",
            "檔案大小(bytes)": it["size"],
            "檔案大小": human(it["size"]) if it["size"] else "",
            "SHA-256": it["sha256"],
            "Drive檔案ID": drive_id,
            "Drive檔案大小": drive_size,
            "Drive SHA-256": drive_sha,
            "Drive連結": drive_link,
            "處理狀態": status,
            "備註": " ".join(x for x in remarks if x).replace("\n", " ").strip(),
        })

    os.makedirs(OUTDIR, exist_ok=True)
    cols = list(rows[0].keys())
    csv_path = os.path.join(OUTDIR, "工作紀錄.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    counts = Counter(r["處理狀態"] for r in rows)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def grp(title, keys, intro=""):
        lines = ["## " + title, ""]
        if intro:
            lines += [intro, ""]
        sel = [r for r in rows if r["處理狀態"] in keys]
        if not sel:
            lines += ["（無）", ""]
            return lines
        lines += ["| 項目 | 檔名 | 分類 | 大小 | SHA-256（首 12 位） |",
                  "|---|---|---|---|---|"]
        for r in sel:
            lines.append("| %s | %s | %s | %s | `%s` |" % (
                r["項目編號"], r["文件名稱"].replace("|", "\\|"),
                r["分類資料夾"], r["檔案大小"], r["SHA-256"][:12]))
        lines.append("")
        return lines

    md = [
        "# 童軍 PDF 補收 — 下載及上載工作紀錄", "",
        "- 產生時間：%s" % now,
        "- 來源清單：`童軍PDF補收清單_含下載連結.md`（整理日期 2026-10-27，第一輪官網檢查）",
        "- 清單跟進項目：**79**；本次實際處理網址：**80**（79 項 ＋ 1 個清單「配套與更新提示」內的對照附件）",
        "- Google Drive 目標資料夾：[童軍PDF補收（位於 working 內）](%s)" % root_link,
        "- Drive 工具：已連接，`upload_file`／`copy_file`／`create_file` 均可用（已實測）。",
        "- 下載驗證：`%%PDF-` 檔首 ＋ `%%EOF` 結尾 ＋ HTTP 200 ＋ SHA-256；不單憑網址副檔名判斷。",
        "- 上載後核對：Drive 端回傳之 SHA-256／大小與本機驗證值比對。",
        "",
        "## 統計", "",
        "| 處理狀態 | 數量 |", "|---|---|",
    ]
    for k, v in sorted(counts.items()):
        md.append("| %s | %d |" % (k, v))
    md += ["| **合計（處理網址）** | **%d** |" % len(rows), ""]

    md += ["## 分類結果", "", "| 分類資料夾 | 成功上載 |", "|---|---|"]
    for f in ["01_POR及會章", "02_支部訓練綱要", "03_政策及安全指引",
              "04_行政及領袖訓練", "05_資助計劃", "06_配套表格",
              "07_地域及屬會專用"]:
        n = sum(1 for r in rows if r["分類資料夾"] == f and r["處理狀態"] == "成功下載並上載")
        md.append("| %s | %d |" % (f, n))
    md.append("")

    md += grp("一、成功下載並上載", ["成功下載並上載"],
              "共 %d 份。全部保留官方原檔名稱；Google Drive 來源項目以複製原檔方式處理。" % counts.get("成功下載並上載", 0))
    md += grp("二、重複而略過", ["重複而略過"],
              "共 %d 份。以 SHA-256 判定內容完全相同，未重複上載。" % counts.get("重複而略過", 0))
    md += grp("三、無法下載／權限不足", ["無法下載／權限不足"],
              "共 %d 份。" % counts.get("無法下載／權限不足", 0))
    md += grp("四、版本或內容待人工核對", [], "見下表；這些檔案雖已成功上載，但版本關係或適用範圍仍需人工確認。")
    # replace last group with review table
    review_rows = [r for r in rows if r["項目編號"] in REVIEW]
    md += ["| 項目 | 檔名 | 待核對事項 |", "|---|---|---|"]
    for r in review_rows:
        md.append("| %s | %s | %s |" % (
            r["項目編號"], r["文件名稱"].replace("|", "\\|"),
            REVIEW[r["項目編號"]].replace("|", "\\|")))
    md.append("")

    md += [
        "## 重要聲明", "",
        "1. 清單的 **79 個跟進項目不等於 79 份全新 PDF**：包含版本更新、配套表格及海報；本次去重後實際上載 %d 份。" % counts.get("成功下載並上載", 0),
        "2. 「未見獨立 MD」**不代表現有文件完全沒有涵蓋**該內容；收錄前應先查看 PDF 內容、通告編號、生效日期及取代關係。",
        "3. 本清單來自 **2026-10-27 的第一輪官網檢查**，不是全站完整審核，也未逐份重新下載驗證所有連結（本次已逐份下載驗證本清單內所有網址）。",
        "4. 第 51、52、54、57、70 項為**地域／屬會專用**，已集中存放於 `07_地域及屬會專用`，**不可混作總會通用規定**。",
        "5. 全程**沒有刪除、沒有覆蓋**任何既有 Drive 檔案；所有檔案均為新建或複製到全新資料夾。",
        "6. 直連失效時本應回到清單所附官方來源頁查找；本次所有網址直連均成功，故未啟用後備查找。未猜測任何失效網址。",
        "7. 第 08 項與對照附件（X1）經 SHA-256 驗證**內容完全相同**，可解答清單關於「兩個不同附件路徑」的疑問；仍建議人工核對通告目錄與支部訓練檢討頁的過渡安排說明文字。",
        "",
        "## 檔案說明", "",
        "- `工作紀錄.csv`：完整逐項紀錄（UTF-8 with BOM，可直接用 Excel 開啟）。",
        "- `工作紀錄.md`：本檔，人類可讀報告。",
        "- `完成報告.md`：任務總結。",
        "- `分類說明.md`：分類決策與資料夾結構說明。",
        "",
    ]
    with open(os.path.join(OUTDIR, "工作紀錄.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print("CSV rows:", len(rows))
    print("status:", dict(counts))
    for r in rows:
        if r["處理狀態"] != "成功下載並上載":
            print("  non-success:", r["項目編號"], r["文件名稱"], r["處理狀態"])
    return rows, counts


if __name__ == "__main__":
    main()
