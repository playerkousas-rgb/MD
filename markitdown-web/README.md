# MarkItDown 網頁版(含 OCR + 批次轉換)

微軟官方的 [MarkItDown](https://github.com/microsoft/markitdown) 只有 **命令列(CLI)** 和 **Python API**,
沒有網頁介面。這個小專案補上那一層:**一個「拖放檔案 → 轉成 Markdown」的網頁**,
並且加上官方沒有的兩件事——**掃描件 OCR** 和 **整個資料夾批次轉換**。

- 後端:FastAPI + MarkItDown(Python)
- 前端:單一 HTML 檔,無需 npm、無需 build、無 CDN
- OCR:RapidOCR(PP-OCRv4 ONNX)+ OpenCC 簡轉繁(香港)
- 檔案只在本機處理,不經第三方服務

本專案的用途是**把 PDF 轉成 Markdown 存進這個 repo**,再由前端網頁讀取,
交給 Gemini 回答使用者問題。因此:**刻意不設登入驗證**。

> **repo 內有三件東西,各自負責一件事**
>
> | 目錄 | 是甚麼 | 跑在哪 |
> |---|---|---|
> | `markitdown-web/`(本目錄)| 轉換器:網頁 + 批次 CLI,**無大小限制** | 自己電腦 / 內網 |
> | `pdf2md/` | 同一個轉換器的 **Vercel 版**(單檔 ≤4MB)| Vercel |
> | `gemini/` | 問答頁:只讀 `.md`,接 Gemini | 靜態網站 |
>
> 轉換器只輸出 `.md`;問答頁只讀 `.md`。兩邊不互相依賴。

---

## 一、最快上手(本機執行)

> **只想快點開始?** 看 [本機使用指南.md](本機使用指南.md) —— 三步、兩個雙擊。
> 下面是最完整的說明。

### 1. 確認 Python 版本

需要 **Python 3.11 或以上**(PyMuPDF 2.0 的要求;
3.10 仍可執行,但沒有版面分析,輸出會退化成純文字):

```bash
python --version        # Windows 也可能是 python3 或 py
```

### 2. 建立虛擬環境並安裝依賴

**macOS / Linux**

```bash
cd markitdown-web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows(PowerShell)**

```powershell
cd markitdown-web
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> 如果 PowerShell 不給執行啟動腳本,先執行:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

`requirements.txt` 只裝需要的格式(避開 Azure SDK、語音辨識等重型依賴)。
OCR 的部分**全部用 pip 安裝,不需要系統 Tesseract**:

| 套件 | 用途 |
|---|---|
| `pymupdf` | 把 PDF 頁面點陣化成 PNG,交給 OCR |
| `rapidocr-onnxruntime` | PP-OCRv4 中英文模型(約 15MB,隨 wheel 附帶,不用另外下載)|
| `opencv-python-headless` | rapidocr 依賴;**必須**用 headless 版,否則缺 `libGL.so.1` |
| `opencc-python-reimplemented` | 簡體 → 繁體(`s2t`)|

### 3. 啟動

最簡單:雙擊 `start.bat`(Windows)或 `./start.sh`(macOS / Linux),
它會自動建立環境、安裝依賴(首次 2–4 分鐘)並開瀏覽器。

手動方式:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

然後開瀏覽器:**<http://localhost:8000>**

拖放檔案進去 → 選 OCR 模式 → 按「轉成 Markdown」→ 可逐個複製／下載,或一次下載 ZIP。

> 只想給自己用,`--host 127.0.0.1` 更安全;要讓同一個 Wi-Fi 下的同事用,
> 就用 `0.0.0.0`,再開 `http://你的內網IP:8000`。

---

## 二、用 Docker 跑(不想碰 Python 環境時)

```bash
cd markitdown-web
docker build -t markitdown-web .
docker run --rm -p 8000:8000 markitdown-web
```

或用 compose:

```bash
docker compose up -d
```

映像裡已裝 `libglib2.0-0`(opencv-headless 仍需要它)。OCR 走 CPU,
不需要 CUDA 映像;但記憶體建議至少 2GB,因為載模型與同時轉多頁會佔用。

---

## 三、OCR 怎麼運作(重點)

### 三種模式

| 模式 | 行為 | 何時用 |
|---|---|---|
| `auto`(預設)| **逐頁**判斷:該頁抽到的文字少於 40 字才 OCR | 幾乎所有情況都適合 |
| `always` | 每一頁都 OCR | 掃描品質差、或文字層本身是亂碼 |
| `never` | 完全不 OCR | 只要文字層,想跑快一點 |

### 版面分析(預設開啟)

文字頁不是單純「抽字」,而是走 **PyMuPDF 2.0 內建的 ONNX 版面模型**:

- 偵測標題 → `#` / `##`
- 巢狀清單 → `1.` / `- a)` 層級保留
- 表格 → 真正的 Markdown 表格(含 `| --- |` 分隔線)
- 多欄版面 → 依閱讀順序重排
- 去掉螢光筆／底線註記產生的 `<mark>`、`<u>` 標籤

實測這批 79 份文件的差別:

| | 純文字模式 | 版面分析 |
|---|---|---|
| Markdown 表格 | 14 個 | **246 個** |
| 標題 | 10 個 | **1076 個** |
| 轉換耗時 | 65 秒 | 663 秒(2 執行緒,牆鐘約 5–6 分鐘)|

代價是慢 3–5 倍;只要文字、不要結構時加 `--no-layout`。

> 注意:PyMuPDF 2.0 **自己也會**用 RapidOCR 對掃描頁做 OCR,
> 但它不標記哪一頁、沒有信心度、也不做簡繁轉換。
> 本專案明確關掉它(`use_ocr=0`),改用自己的逐頁 OCR,
> 才會有 `<!-- p.N ocr -->` 標記與詞彙表修正。

`auto` 的關鍵是**逐頁**而不是逐檔:一份 214 頁的訓練綱要裡只有 2 頁是掃描圖,
就只會 OCR 那 2 頁,其餘照常抽文字層。實測 79 份童軍 PDF 中,
只有 9 份需要 OCR,總共約 18 頁。

### 輸出長這樣

實際輸出(測試樣本,未經人手修飾):

```markdown
<!-- p.1 ocr -->
香港童軍總會政策通告P110-26

主題：寰宇童軍計劃探索課程開辦指引

生效日期：2026年9月17日

1.本通告旨在明開辦探索課程的申請程序。

2.各旅團於活動前四星期提交申請表。

3.查詢請聯絡國際事務處。

表格一：申請資料

旅團編號 | 負責 | 參加人數
| --- | --- | --- |
HKG-1234 | 陳大文 | 24
```

可以看到:編號清單各自成段、`主題`／`生效日期` 不會黏在一起、
表格有分隔線可以直接被 Markdown 渲染。

- 每頁開頭有 `<!-- p.1 -->` 頁碼註記,**經 OCR 的頁面會標成 `<!-- p.1 ocr -->`**,
  方便你(和 Gemini)知道哪些內容可能有錯字。
- OCR 出來的字會過一次 `OpenCC('s2t')`,把 PP-OCR 的簡體輸出轉成標準繁體
  (`查询→查詢`、`编號→編號`),不會出現臺灣用語(`程序` 不會變 `程式`)。
- 常見誤認會由詞彙表修正(`負袖→負責`、`童军→童軍`、`網要→綱要`),
  詞彙表在 `convert_core.py` 的 `DEFAULT_GLOSSARY`,可自行增修。

### 實測數據(2 核 VPS)

| 項目 | 數值 |
|---|---|
| OCR 速度 | 約 3–4 秒 / 頁(A4,200 dpi)|
| 平均信心度 | 0.92–0.96 |
| 模型載入 | 約 0.3 秒(僅第一次)|
| 文字 PDF | 每頁約 0.01 秒(完全不經 OCR)|
| 79 份童軍 PDF 全量轉換 | **65 秒**(含 18 頁 OCR,共 1.7MB Markdown)|

環境變數 `OCR_DPI` 可調(預設 200)。實測 150 快約四成、準確度略降;
**調到 300 / 400 對這個模型沒有幫助**(它會把圖縮到固定尺寸),不要白花時間。

---

## 四、批次轉換整個資料夾

網頁一次最多 50 個檔案;**整個目錄(含子目錄)請用 `batch_convert.py`**:

```bash
cd markitdown-web
source .venv/bin/activate

python batch_convert.py ../out/dl -o ../knowledge --ocr auto
```

它會:

1. 遞迴找檔案,依原有子目錄結構輸出 `.md`(分類不會亂)
2. **可續跑**:已存在的 `.md` 會跳過,中斷後重跑不會重做(`--force` 強制重來)
3. 產生 `_index.json`(給前端／Gemini 用的索引)和 `_report.csv`(逐檔結果)
4. 單檔失敗不中斷整批,最後列出失敗清單

常用參數:

```bash
--ocr auto|always|never   # OCR 模式,預設 auto
--workers 2               # 平行處理檔數;2 核機器建議 2
--limit 5                 # 只跑前 5 個(測試用)
--force                   # 重新轉換,不跳過已存在的
--ext pdf,docx            # 只轉這些格式;預設 pdf,docx,pptx,xlsx,xls,epub,html,msg
                          # 用 --ext all 表示全部支援格式
--no-front-matter         # 不加 YAML front matter
--no-page-markers         # 不加 <!-- p.N --> 頁碼註記
```

輸出長相:

```
knowledge/
├── 01_POR及會章/
│   └── POR_C_20260917.md
├── 02_支部訓練綱要/
│   ├── 01 小童軍活動指引(第三版).md
│   └── 03_Scout Training Scheme_Chi_20260606.md
├── _index.json      ← 前端讀這個
└── _report.csv      ← 人看的報表
```

### `_index.json` 的結構

前端網頁(Gemini 問答)只需要讀這一個檔案,不必掃目錄:

```json
{
  "generated_at": "2026-10-28T14:30:00+0800",
  "ocr_mode": "auto",
  "total": 79,
  "converted": 79,
  "failed": 0,
  "files": [
    {
      "md_file": "01_POR及會章/POR_C_20260917.md",
      "title": "香港童軍總會政策、組織及規條",
      "category": "01_POR及會章",
      "chars": 62605,
      "pages": 105,
      "pages_ocr": 0,
      "ocr_avg_score": null,
      "sha256": "…",
      "needs_review": false
    }
  ]
}
```

`needs_review: true` 代表該檔有頁面經過 OCR(或轉換失敗),內容可能有錯字,
答題時應降低信心或提示使用者查原文。

### 給前端 + Gemini 的建議流程

```js
// 1. 讀索引
const index = await fetch("./knowledge/_index.json").then(r => r.json());

// 2. 先做關鍵字／標題篩選,不要一次把 80 份文件全塞給模型
const hits = index.files.filter(f =>
  f.title.includes(q) || f.category.includes(q));

// 3. 只把命中的 2–3 份 Markdown 放進 context
const docs = await Promise.all(hits.slice(0, 3).map(f =>
  fetch("./knowledge/" + encodeURI(f.md_file)).then(r => r.text())));

// 4. 連同問題交給 Gemini,並要求附出處
const prompt = `
以下係香港童軍總會官方文件節錄。只可以根據呢啲內容回答;
答唔到就講「文件中未提及」。每個答案要標明出自邊個檔案。
${docs.join("\n\n---\n\n")}

問題:${q}`;
```

> 有用 `pages_ocr > 0` 的文件要提醒模型:OCR 可能有錯字,
> 涉及日期、金額、通告編號時要說明「請以原文為準」。

### 問答頁是另一個專案

Gemini 問答頁只讀 Markdown,不做任何轉換或 OCR,已獨立成 repo 內的 `gemini/`。
本目錄(`markitdown-web/`)只負責轉換。詳見 `gemini/README.md`。
---

## 五、API 一覽

啟動後打開 **<http://localhost:8000/docs>** 可以看到可互動的 API 文件。

| 方法 | 路徑 | 說明 |
|---|---|---|
| `GET` | `/` | 網頁介面 |
| `GET` | `/api/health` | 服務狀態、OCR 是否可用、支援格式 |
| `POST` | `/api/convert` | 上載 1–50 個檔案,回傳 JSON |
| `POST` | `/api/convert-zip` | 上載檔案,直接回傳 `.md` 打包的 ZIP |

`/api/convert` 的參數(multipart):

| 參數 | 預設 | 說明 |
|---|---|---|
| `files` | 必填 | 可重複,最多 50 個,單檔上限由 `MAX_UPLOAD_MB` 控制(預設 100MB)|
| `ocr_mode` | `auto` | `auto` / `always` / `never` |
| `front_matter` | `false` | 是否加 YAML front matter |
| `page_markers` | `true` | 是否加 `<!-- p.N -->` 頁碼註記 |

回傳的每個結果:

```json
{
  "filename": "deposit.pdf",
  "ext": ".pdf",
  "size": 210334,
  "ok": true,
  "markdown": "<!-- p.1 ocr -->\n…",
  "chars": 272,
  "pages": 1,
  "pages_ocr": 1,
  "ocr_avg_score": 0.945,
  "seconds": 4.94,
  "warnings": ["本檔有 1 頁經 OCR 辨識;OCR 會有錯字(尤其繁體),重要內容請人工核對。"],
  "error": null
}
```

用 curl:

```bash
# 單檔
curl -X POST http://localhost:8000/api/convert \
     -F "files=@政策通告.pdf" -F "ocr_mode=auto" -F "front_matter=true"

# 多檔,直接拿 ZIP
curl -X POST http://localhost:8000/api/convert-zip \
     -F "files=@a.pdf" -F "files=@掃描件.jpg" -F "ocr_mode=always" \
     -o markdown.zip
```

---

## 六、支援格式

`pdf` `docx` `doc` `pptx` `xlsx` `xls` `csv` `tsv` `html` `htm` `xml`
`json` `txt` `md` `epub` `msg` `ipynb` `rtf`
**圖片**:`png` `jpg` `jpeg` `bmp` `tif` `tiff` `webp`(直接 OCR)

轉換效果大致是:

| 來源 | 結果 |
|---|---|
| 文字型 PDF | 段落文字(**不保留**原版面、多欄順序可能錯亂)|
| 掃描型 PDF | **OCR** 出文字,逐頁輸出,並標記 `<!-- p.N ocr -->` |
| 圖片 | 直接 OCR |
| Word | 標題／段落／清單,圖片不抽出 |
| Excel | 每個工作表 → 一個 Markdown 表格 |
| PowerPoint | 逐頁標題與文字 |
| HTML | 標題、粗體、連結、清單 → 對應 Markdown |

---

## 七、重要限制(先看清楚,以免期待落差)

1. **OCR 一定會有錯字**,繁體尤其中文筆畫多的字。
   實測信心度 0.92–0.96,但「總監」變「總會」、「港幣」變「港」這類錯誤仍會出現。
   **涉及金額、日期、通告編號時必須核對原文**;程式已在 `ocr_avg_score` 與
   `needs_review` 標出需要複查的檔案。
2. **不保留複雜版面**:多欄排版、跨頁表格、垂直文字仍會被打散或漏掉。
   但同一行的多個表格欄位會用 ` | ` 連接,不會全部黏成一坨。
3. **圖片、圖表、QR code、印章不會變成文字**(只能認字,不會描述圖中內容)。
4. **手寫字、藝術字、淺色浮水印**的辨識率很低。
5. **Excel/Word 公式、註解、追蹤修訂**不一定保留。
6. OCR 是 CPU 密集工作:2 核機器上大約 **3–4 秒 / 頁**,
   一份 100 頁全掃描的 PDF 要 6 分鐘左右。批次請預留時間。

---

## 八、部署

### A. 內網 / 自己電腦 + Cloudflare Tunnel

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
# 另開一個終端
cloudflared tunnel --url http://localhost:8000
```

會得到一個 `https://xxx.trycloudflare.com` 網址,同事可直接開。

> 本服務**沒有登入機制,這是刻意設計**——它的用途只是把 PDF 轉成 repo 裡的
> Markdown,給前端網頁 + Gemini 用。若你之後要把它放到完全公開的網路上,
> 建議自己加 Cloudflare Access 或 Nginx Basic Auth,一行都不用改程式。

### B. Render / Railway / Fly.io

- Build:`pip install -r requirements.txt`
- Start:`uvicorn app:app --host 0.0.0.0 --port $PORT`
- 記得設 `PORT` 環境變數(平台通常會自動給)
- 免費層 CPU 很弱,OCR 會很慢,建議至少 1GB RAM

`Dockerfile` 已可直接用,選擇「Docker」部署即可。

### C. 自己的 VPS

```bash
docker run -d --restart unless-stopped -p 8000:8000 --name markitdown-web markitdown-web
```

再前面掛 Nginx / Caddy 做 HTTPS。

---

## 九、檔案結構

```
markitdown-web/
├── convert_core.py      # 核心:OCR、簡轉繁、版面重組、逐頁決策(web 與 CLI 共用)
├── app.py               # FastAPI 後端(上載、批次、ZIP 匯出)
├── batch_convert.py     # 資料夾批次轉換 CLI → .md + _index.json + _report.csv
├── static/
│   └── index.html       # 轉換頁(拖放、OCR 模式、預覽、複製、下載)
├── start.sh / start.bat     # 一鍵安裝 + 啟動
├── convert.sh / convert.bat # 拖一個資料夾進來 → 批量轉換
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── start.sh / start.bat
└── README.md
```

`convert_core.py` 是唯一的轉換邏輯來源,網頁和 CLI 都呼叫它,
所以兩邊行為一定一致,不會出現「網頁轉得對、腳本轉得不對」。

---

## 十、疑難排解

| 症狀 | 原因 / 解法 |
|---|---|
| `pip install` 失敗 | Python 版本 < 3.10;或先 `pip install -U pip` |
| `ModuleNotFoundError: markitdown` | 忘了啟動虛擬環境(`source .venv/bin/activate`)|
| `ImportError: libGL.so.1` | 裝到了 `opencv-python`;換成 `opencv-python-headless` |
| 開網頁是空白 | 後端沒啟動;確認終端機沒有錯誤訊息 |
| `Address already in use` | 8000 被佔用,改 `--port 8001` |
| 上載大檔回 413 | 調高 `MAX_UPLOAD_MB=300` |
| 轉出來是空的 | 頁面是空白、純圖片但 OCR 也認不到,或 `ocr_mode=never` |
| OCR 出來是簡體 | `opencc-python-reimplemented` 沒裝好;檢查 `_to_hant()` |
| OCR 很慢 | 正常,3–4 秒 / 頁;降低 `OCR_DPI` 或改用 `ocr_mode=auto` |
| 中文變亂碼 | 檔案本身可能是 Big5;下載時用 UTF-8 開 |
| `ImportError: libGL.so.1` | rapidocr 把 headless 版 opencv 覆蓋了;`pip uninstall -y opencv-python` 後 `pip install --force-reinstall --no-deps opencv-python-headless` |
| 輸出沒標題沒表格 | Python < 3.11 → PyMuPDF 只有 1.x;升級後刪 `.venv` 重裝 |
| 進度／總結沒顯示 | 已修(mute stdout 的方式在 2.0 以前會弄壞 fd 1) |

---

## 十一、和這批童軍 PDF 的搭配

`out/dl/` 是 79 份官方 PDF(分類為 `01_POR及會章` … `07_地域及屬會專用`),
`knowledge/` 是轉換後的 Markdown 知識庫,兩者都保留在 repo 內。

```bash
cd markitdown-web && source .venv/bin/activate
python batch_convert.py ../out/dl -o ../knowledge --ocr auto
```

79 份的實測結果:

| 分類 | 純文字 | 需要 OCR |
|---|---|---|
| 全部 79 份 | 70 份 | 9 份(共約 18 頁)|

需要 OCR 的 9 份:

- **全掃描**:`a.pdf`、`deposit.pdf`、`MidWeekMember.pdf`、`02.pdf`(總俱樂部文件)
- **部分掃描**:小童軍活動指引、Cub Scout / Venture / Rover 訓練綱要、木章訓練綱要

建議流程:

1. 官方 PDF 更新時,先放進 `out/dl/` 對應分類
2. 跑 `batch_convert.py`(會跳過沒變的檔案,很快)
3. `_report.csv` 裡 `pages_ocr > 0` 的檔案抽幾頁人工抽查
4. 確認後把 `knowledge/` 一起 commit,前端網頁即時可讀
