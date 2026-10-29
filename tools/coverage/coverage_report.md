# 官網通告覆蓋率報告

產生日期：2026-10-29　｜　工具：`tools/coverage/check_coverage2.py`、`build_report.py`

## 一、摘要

文件庫：**213 份 `.md`**（`knowledge/` 79 份 + `政策指引/` 100 份 + `行政/` 22 份 + `資助計劃/` 12 份）
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

1. `政策指引/`、`行政/`、`資助計劃/` 三個目錄是原始轉換結果：**沒有 front matter、沒有頁碼標記**，
   部分檔名含 OCR 雜訊（例如 `李鉅能基金.md` 開頭有亂碼），引用時要提醒核對原文。
2. `knowledge/` 內的 79 份有完整 front matter（頁數、OCR 頁數、來源分類）與 `<!-- p.N -->` 頁碼標記。
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
