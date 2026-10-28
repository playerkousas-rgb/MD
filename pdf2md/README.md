# pdf2md(Vercel 版)

同一個 PDF → Markdown 轉換器,但打包成 **Vercel Serverless Function**,開個網址就能用,
不用在自己電腦裝 Python。

```
pdf2md/
├── api/convert.py    # Vercel 函數(raw body 進、JSON 出)
├── public/index.html # 網頁介面(拖放、OCR 模式、逐檔進度)
├── convert_core.py   # 轉換邏輯(由 markitdown-web/convert_core.py 同步)
├── requirements.txt
├── vercel.json
└── local_server.py   # 本機預覽用
```

---

## 一、部署(兩種方式)

### A. Vercel 網頁介面(最簡單,建議)

1. Vercel → **Add New… → Project → Import Git Repository** → 選 `playerkousas-rgb/MD`
2. **Root Directory** 改成 **`pdf2md`**(很重要,不改會找不到 `api/`)
3. Framework Preset 選 **Other**,Build / Output 全部留空
4. Deploy

完成後網址長這樣:`https://<project>.vercel.app`。

### B. CLI

```bash
cd pdf2md
npx vercel --prod
```

(第一次會問要連結哪個專案,Root Directory 設成 `pdf2md` 即可。)

> 已內建 `vercel.json`,指定 Python 3.12、`maxDuration: 60`。
> 不需要任何環境變數。

---

## 二、Vercel 的硬限制(先看清楚)

| 限制 | 數值 | 對你的影響 |
|---|---|---|
| 單次請求 body | **4.5 MB**(平台硬限制)| 大於 ~4MB 的 PDF 會被擋,介面會直接提示 |
| 函數未壓縮大小 | 250 MB | 所以不用 PyMuPDF(116MB),改用 pypdfium2(8MB)|
| 執行時間 | 最多 60 秒(`maxDuration`)| 全掃描件約 3–4 秒／頁 → **大約 12 頁以內** |
| 冷啟動 | 1–4 秒 | 閒置一陣子後第一次轉換會慢一點 |

**超過上限怎麼辦?** 用同一個 repo 的 `markitdown-web/`:

```bash
cd markitdown-web && source .venv/bin/activate
python batch_convert.py ../out/dl -o ../knowledge --ocr auto   # 無限大小、可整批
```

它的轉換邏輯跟這裡完全相同(同一個 `convert_core.py`),
只是跑在你自己的機器上,沒有 4MB / 60 秒 / 250MB 的問題,
而且可以用 PyMuPDF 抽文字(比 pypdfium2 多回一些空白與換行,內容一樣)。

---

## 三、本機預覽

```bash
cd pdf2md
pip install -r requirements.txt     # 需要 pypdfium2,或直接用 markitdown-web 的 venv

python local_server.py              # http://localhost:8001
```

要模擬 Vercel 的環境(只裝 pypdfium2、沒有 PyMuPDF)加上:

```bash
PDF_ENGINE=pdfium python local_server.py
```

`local_server.py` 會把 `/api/*` 交給 `api/convert.py` 那個 handler,
其餘路徑出 `public/` 的靜態檔,行為與 Vercel 一致。

---

## 四、API

### `GET /api/health`

```json
{
  "ok": true,
  "pdf_engine": "pdfium",
  "ocr_available": true,
  "ocr_dpi": 200,
  "min_chars_per_page": 40,
  "max_upload_mb": 4,
  "formats": ["pdf", "docx", "xlsx", "..."]
}
```

### `POST /api/convert`

不是 multipart,而是**直接把檔案 bytes 當 body**(省體積、省解析):

```bash
curl -X POST "https://<project>.vercel.app/api/convert?filename=P110-26.pdf&ocr=auto&markers=1&frontmatter=0" \
     -H "Content-Type: application/octet-stream" \
     --data-binary @P110-26.pdf
```

參數(全部放在 query string):

| 參數 | 預設 | 說明 |
|---|---|---|
| `filename` | `upload` | 只用來判斷副檔名、顯示名稱 |
| `ocr` | `auto` | `auto`(只 OCR 沒文字層的頁)/ `always` / `never` |
| `markers` | `1` | 是否加 `<!-- p.N -->` 頁碼註記 |
| `frontmatter` | `0` | 是否加 YAML front matter |

回應:

```json
{
  "ok": true,
  "filename": "P110-26.pdf",
  "markdown": "<!-- p.1 -->\n香港童軍總會政策通告...",
  "chars": 685,
  "pages": 1,
  "pages_ocr": 0,
  "ocr_avg_score": null,
  "seconds": 0.34,
  "warnings": [],
  "error": null
}
```

錯誤:超過 4MB → `413`;格式不支援 → `400`;兩者都會回 `{ok:false, error:"..."}`。

---

## 四點五、這一版沒有版面分析(重要差異)

本機版(`markitdown-web/`)用 **PyMuPDF 2.0 的版面模型**,文字頁會輸出標題、
巢狀清單、真正的 Markdown 表格(79 份實測:表格 14 → 246、標題 10 → 1076)。

**Vercel 版做不到**,因為 PyMuPDF 2.0 連同 ONNX 模型要 116MB,
加上 onnxruntime、opencv、numpy 就撞爆 250MB 函數上限。
這一版用 pypdfium2 抽純文字 —— 內容正確,但**沒有標題層級與表格**。

實際選擇:

| 你要 | 用哪個 |
|---|---|
| 隨手轉一份、看內容 | Vercel 版(夠用)|
| 要進 `knowledge/` 餵 Gemini、要表格 | 本機版 `batch_convert.py` |

## 五、轉好的檔去哪裡?

1. 在網頁上按「下載 .md」
2. 按分類放進 repo 的 `knowledge/`(例:`knowledge/03_政策及安全指引/P110-26.md`)
3. 重跑一次索引(或直接改 `_index.json`)
4. Push → `gemini/` 問答頁就會讀到新文件

> 批次大量更新時,還是用 `markitdown-web/batch_convert.py`,
> 它會同時更新 `_index.json`。

---

## 六、為甚麼不用 PyMuPDF?

PyMuPDF 2.0 裝起來 116MB(其中 49MB 是內建的版面分析 ONNX 模型),
加上 onnxruntime(66MB)、opencv-headless(71MB)、numpy(41MB),
很容易撞上 Vercel 函數 250MB 的上限。

`pypdfium2` 只有約 8MB,抽出來的**內容字數與 PyMuPDF 完全一樣**
(實測 P060-24:兩邊去空白後都是 272 字),只是換行／空白少一點。
所以 Vercel 版用 pdfium,本機版預設仍用 PyMuPDF。

`convert_core.py` 會自動偵測:有 PyMuPDF 就用,沒有就退回 pypdfium2,
也可以用 `PDF_ENGINE=pymupdf|pdfium` 強制指定。
