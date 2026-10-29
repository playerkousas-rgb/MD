# 官網通告覆蓋率報告

產生日期：2026-10-29　｜　工具：`tools/coverage/check_coverage2.py`、`build_report.py`

## 一、摘要

文件庫：**223 份 `.md`**（全部在 `knowledge/`；另有 `archive/` 存放被取代的舊版本，不參與問答）
官網索引：**188 項**（政策／指引 8 頁、行政 2 頁、資助計劃 1 頁）

| 分類 | 官網項目 | 已有 | 缺 | 覆蓋率 |
|---|---:|---:|---:|---:|
| 政策／指引 | 151 | 151 | 0 | 100% |
| 行政 | 27 | 26 | 1 | 96% |
| 資助計劃 | 10 | 10 | 0 | 100% |
| **合計** | **188** | **187** | **1** | **99%** |

比對方式：檔名／通告編號／內文檔名／人工對照表。**同號不同版（被取代的舊通告）會算作已覆蓋**，
所以「已有」代表「檔案在庫」，不代表內容一定是最新版本。

## 二、缺口

| 分類 | 日期 | 檔名 |
|---|---|---|
| 行政 | 01/08/2023 | `pau_poster_012023` |

## 三、注意事項

1. 223 份之中，89 份有完整頁碼標記（`<!-- p.N -->`）與頁數；134 份是 2026-10-29 收納入庫的原始轉換版，
   **沒有頁碼標記**，3 份開頭有 OCR 雜訊（front matter 標 `quality: ocr-noisy`）；另有 10 份由官網 HTML 直接抓取
   （`pipeline: web-html`，帶 `source_url`／`retrieved_date`），有 `<!-- p.N -->` 標記但無 PDF 頁數。
2. 檔案清單（含通告編號、日期、字數、雜訊標記）：`tools/coverage/knowledge_manifest.csv`。
3. 官網連結含內部編號，容易失效，本報告不逐項列出；下載時用目錄頁按檔名搜尋：

- 政策／指引：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=3>
- 行政：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=4>
- 資助計劃：<https://www.scout.org.hk/tc/circulars-forms/circulars/index.html?type=Y&category=5>

## 四、重跑方法

```bash
python3 tools/coverage/check_coverage2.py          # 只看數字
python3 tools/coverage/check_coverage2.py --list   # 列出未覆蓋
python3 tools/coverage/build_report.py             # 重新產生本報告
```

索引快照：`tools/coverage/site_index_20261029.txt`（188 項，格式 `分類|日期|檔名`）。
