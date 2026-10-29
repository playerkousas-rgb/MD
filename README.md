# 童軍文件知識庫

香港童軍總會官方文件的 Markdown 版,加上兩支配合的工具。

**兩件事,分開放:**

```
PDF ──(轉換器)──▶ knowledge/*.md ──(問答頁)──▶ Gemini ──▶ 答案
      pdf2md /              ↑
      markitdown-web        └── 只讀 .md,不做 OCR
```

| 目錄 | 是甚麼 | 跑在哪 | 說明 |
|---|---|---|---|
| **`pdf2md/`** | PDF → Markdown 轉換器(**Vercel 版**)| Vercel Serverless | 單檔 ≤4MB、≤60 秒;開網址即用 |
| **`markitdown-web/`** | 同一個轉換器(**本機版**)| 自己電腦 / 內網 | 無大小限制、可整批、可 CLI |
| **`gemini/`** | 問答頁 | 靜態網站 | **只讀 `.md`**,不轉換、不 OCR |
| `knowledge/` | **249 份**文件的 Markdown（`_index.json` 為舊索引，前端已不用） | — | 兩個工具的交集 |

轉換器只負責產出 `.md`,問答頁只負責讀 `.md` —— 兩邊不互相依賴。

---

## 快速開始

**👉 只想快點把 PDF 轉成 MD** → 先睇 **[`開始用-睇我.md`](開始用-睇我.md)**
(下載邊個 ZIP、解壓、雙擊邊個檔,一頁講完)

**👉 想有標題／表格,但顯示「版面分析:關」** → 睇 **[`更新Python-用CMD.md`](更新Python-用CMD.md)**
(用 CMD 一行 `winget` 由 3.10 升到 3.12,附驗證指令)

其他細節才需要看 **[`markitdown-web/本機使用指南.md`](markitdown-web/本機使用指南.md)**。
Vercel 完全不需要。

**只是想問文件內容** → 開 `gemini/index.html`(需要 Gemini API key)。

**要把新 PDF 轉成 Markdown**

- 少量、單檔 → 用 `pdf2md/`(部署到 Vercel 後開網址拖放)
- 大量、大檔、整批 → 用 `markitdown-web/`:

  ```bash
  cd markitdown-web && source .venv/bin/activate
  python batch_convert.py ../out/dl -o ../knowledge --ocr auto
  ```

詳細說明分別在 `pdf2md/README.md`、`markitdown-web/README.md`、`gemini/README.md`。

---

## knowledge/ 內容

249 份文件,依官方分類:

| 分類 | 份數 |
|---|---:|
| `01_POR及會章` | 2 |
| `02_支部訓練綱要` | 8 |
| `03_政策及安全指引` | 145 |
| `04_行政及領袖訓練` | 43 |
| `05_資助計劃` | 20 |
| `06_配套表格` | 4 |
| `07_地域及屬會專用` | 6 |
| `08_童軍運動及歷史` | 9 |
| `09_營地及場地使用守則` | 12 |
| **合計** | **249** |

六批來源：

- **79 份**：完整轉換（`pipeline: pymupdf-layout`），有頁數、有 `<!-- p.N -->` 頁碼標記，18 頁經 OCR。
- **134 份**：2026-10-29 由 repo 根目錄的 `政策指引/`、`行政/`、`資助計劃/` 三個原始目錄收納入庫
  （`pipeline: legacy-raw`），**沒有頁碼標記**，其中 3 份開頭有 OCR 雜訊（front matter `quality: ocr-noisy`）。
  這批若要補頁碼，需重新下載原 PDF 再轉換。
- **8 份**：2026-10-29 由 Google Drive `NEW PDF` 資料夾補入的第二批（`pipeline: pypdf-text`／`drive-pdf-text`／`ocr-vision`）：
  開辦童軍旅指引（2025-08）、區總監實務手冊（2018-04）、YMIS 用戶指南（2020-01）、童軍典禮儀式指引（2019）、
  颱風及暴雨警告下的工作安排、內部指引 01/2022（委任署理總監）、
  童軍禮儀（2008，掃描件已 OCR）、邀請政府司長／局長／部門首長級官員主禮（2009 便箋，掃描件已 OCR）。
  （同批的活動指引 02/2018 及政策通告 05/2022 因庫內已有更新／相同版本，沒有重複收錄。）
- **12 份**：2026-10-29 由官網各營地頁面（PDF）及 Google Drive「NEW PDF」資料夾（場地借用條款）補入的
  營地及場地使用守則（`pipeline: web-pdf-text`／`drive-pdf-text`，全部帶 `source_url` 或 `source_file`、`retrieved_date`）：
  大潭（營友守則、無人機守則）、洞梓、大美督、沙田、基維爾、白沙灣譚華正、蔡志明聯光（暫停開放）、
  香港童軍中心 9–11 樓借用條款、百周年大樓借用條款、攀爬設施、射箭場。
- **6 份**：2026-10-29 由 Google Drive `working` 資料夾補入（`pipeline: drive-pdf-text`）：
  活動指引第 01/2020 號、第 02/2020 號、表格 PT/21、PT/22、PT/69、2026 支部訓練綱要修訂簡介會。
- **10 份**：2026-10-29 由官網「童軍運動」各頁直接抓取的 HTML 版
  （`pipeline: web-html`，帶 `source_url`／`retrieved_date`）：會徽、抱負使命價值觀、誓詞與規律、會章、
  總會執行委員會、香港總監諮議會、貝登堡勳爵、香港童軍發展史（12 個年代分頁）、歷任總領袖、歷任香港總監。

被取代的舊版本放在 `archive/`（在 `knowledge/` 之外，所以問答頁不會讀到）。

其中 9 份(共 18 頁)是掃描件,經 OCR 產生 —— `_index.json` 內 `needs_review: true`、
檔案內 `<!-- p.N ocr -->` 標記的頁面,內容可能有錯字,涉及日期／金額／通告編號請核對原文。

檔名沿用官方名稱;PDF 原檔不入 Git(`out/` 在 `.gitignore`),需要時用 `tools/fetch_blobs.py` 還原。

---

## 開發

```bash
python tools/sync_core.py          # 改完 markitdown-web/convert_core.py 後,同步到 pdf2md/
python tools/sync_core.py --check  # 檢查兩邊是否一致
```

兩個轉換器共用同一套邏輯(`convert_core.py`),所以轉出來的結果一致。
