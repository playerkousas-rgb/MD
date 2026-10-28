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
| `knowledge/` | 79 份文件的 Markdown + `_index.json` | — | 兩個工具的交集 |

轉換器只負責產出 `.md`,問答頁只負責讀 `.md` —— 兩邊不互相依賴。

---

## 快速開始

**👉 只想快點把 PDF 轉成 MD** → 先睇 **[`開始用-睇我.md`](開始用-睇我.md)**
(下載邊個 ZIP、解壓、雙擊邊個檔,一頁講完)

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

79 份文件、約 83 萬字,依官方分類:

| 分類 | 份數 |
|---|---|
| `01_POR及會章` | 1 |
| `02_支部訓練綱要` | 7 |
| `03_政策及安全指引` | 42 |
| `04_行政及領袖訓練` | 15 |
| `05_資助計劃` | 8 |
| `06_配套表格` | 1 |
| `07_地域及屬會專用` | 5 |

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
