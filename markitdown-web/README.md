# MarkItDown 網頁版

微軟官方的 [MarkItDown](https://github.com/microsoft/markitdown) 只有 **命令列(CLI)** 和 **Python API**,
沒有網頁介面。這個小專案就是自己補上那一層:**一個「拖放檔案 → 轉成 Markdown」的網頁**。

- 後端:FastAPI + MarkItDown(Python)
- 前端:單一 HTML 檔,無需 npm、無需 build
- 檔案只在本機處理,不經第三方服務

---

## 一、最快上手(本機執行)

### 1. 確認 Python 版本

需要 **Python 3.10 或以上**:

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

`requirements.txt` 只裝需要的格式(避開 Azure SDK、語音辨識等重型依賴):

```
markitdown[pdf,docx,pptx,xlsx,xls,outlook]>=0.1.9
fastapi>=0.115
uvicorn[standard]>=0.32
python-multipart>=0.0.12
```

### 3. 啟動

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

然後開瀏覽器:**<http://localhost:8000>**

拖放檔案進去 → 按「轉成 Markdown」→ 可逐個複製／下載,或一次下載 ZIP。

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

---

## 三、一次轉換一整批(不用開網頁)

網頁適合臨時用;**大量檔案**建議直接用 CLI 或呼叫本服務的 API。

### 直接呼叫 API(curl)

```bash
# 單檔
curl -X POST http://localhost:8000/api/convert \
     -F "files=@政策通告.pdf" -F "front_matter=true"

# 多檔,直接取回 ZIP
curl -X POST http://localhost:8000/api/convert-zip \
     -F "files=@a.pdf" -F "files=@b.docx" -F "front_matter=true" \
     -o markdown.zip
```

### Python 批次腳本

```python
import pathlib, requests

SRC = pathlib.Path("./pdfs")        # 你的 PDF 資料夾
OUT = pathlib.Path("./markdown")
OUT.mkdir(exist_ok=True)

for p in sorted(SRC.rglob("*.pdf")):
    with p.open("rb") as f:
        r = requests.post(
            "http://localhost:8000/api/convert",
            files={"files": (p.name, f, "application/pdf")},
            data={"front_matter": "true"},
            timeout=600,
        )
    item = r.json()["results"][0]
    if item["ok"]:
        (OUT / (p.stem + ".md")).write_text(item["markdown"], encoding="utf-8")
        flag = "  ⚠ " + item["warnings"][0][:40] if item["warnings"] else ""
        print(f"OK   {p.name}  {item['chars']} 字元{flag}")
    else:
        print(f"FAIL {p.name}  {item['error']}")
```

### 直接用官方 CLI(不經本服務)

```bash
markitdown 政策通告.pdf -o 政策通告.md

# 整個資料夾
for f in pdfs/*.pdf; do markitdown "$f" -o "markdown/$(basename "${f%.*}").md"; done
```

---

## 四、API 一覽

| 方法 | 路徑 | 說明 |
|---|---|---|
| `GET` | `/` | 網頁介面 |
| `GET` | `/api/health` | 服務狀態、允許格式、上載上限 |
| `POST` | `/api/convert` | 批次轉換,回傳 JSON |
| `POST` | `/api/convert-zip` | 批次轉換,直接回傳 ZIP |
| `GET` | `/docs` | 自動產生的 API 文件(Swagger) |

`POST /api/convert` 參數:

- `files`:可重複的檔案欄位(最多 20 個)
- `front_matter`: `true` / `false`,是否在 Markdown 前加 YAML 來源資訊

回應(每個檔案一筆):

```json
{
  "results": [{
    "filename": "P110-26.pdf",
    "ext": ".pdf",
    "size": 702764,
    "ok": true,
    "markdown": "...",
    "chars": 4213,
    "pages": 6,
    "seconds": 1.24,
    "warnings": [],
    "error": null
  }]
}
```

可用環境變數:`MAX_UPLOAD_MB`(預設 100)、`PORT`(預設 8000)。

---

## 五、支援格式

`pdf` `docx` `doc` `pptx` `xlsx` `xls` `csv` `tsv` `html` `htm` `xml`
`json` `txt` `md` `epub` `msg` `ipynb` `zip` `rtf`

轉換效果大致是:

| 來源 | 結果 |
|---|---|
| 文字型 PDF | 段落文字(**不保留**原版面、欄位順序可能錯亂)|
| Word | 標題／段落／清單,圖片不抽出 |
| Excel | 每個工作表 → 一個 Markdown 表格 |
| PowerPoint | 逐頁標題與文字 |
| HTML | 標題、粗體、連結、清單 → 對應 Markdown |

---

## 六、重要限制(先看清楚,以免期待落差)

1. **掃描影像 PDF 沒有文字層** → 轉出來會是空的。
   本服務會偵測「每頁字數過少」並回傳 warning,但**不會自動 OCR**。
   要處理掃描件,需另外接 Tesseract / PaddleOCR / Azure Document Intelligence。
2. **不保留版面**:多欄排版、表格框線複雜的 PDF,文字順序可能被打散。
   重要通告建議轉完後人工校對。
3. **圖片、圖表不會變成文字**(不會描述圖中內容)。
4. **Excel/Word 公式、註解、追蹤修訂**不一定保留。
5. 特大檔案(數十 MB 的 PDF)轉換會慢,屬於正常;必要時調高 `MAX_UPLOAD_MB`。

---

## 七、部署到雲端(要給團隊用)

三種常見做法,由簡到繁:

### A. 內網 / 自己電腦 + Cloudflare Tunnel(最快)

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
# 另開一個終端
cloudflared tunnel --url http://localhost:8000
```

會得到一個 `https://xxx.trycloudflare.com` 網址,同事可直接開。**記得加驗證**,
否則等於把轉換服務公開上網。

### B. Render / Railway / Fly.io(有免費層)

- Build:`pip install -r requirements.txt`
- Start:`uvicorn app:app --host 0.0.0.0 --port $PORT`
- 記得設 `PORT` 環境變數(平台通常會自動給)

`Dockerfile` 已可直接用,選擇「Docker」部署即可。

### C. 自己的 VPS

```bash
docker run -d --restart unless-stopped -p 8000:8000 --name markitdown-web markitdown-web
```

再前面掛 Nginx / Caddy 做 HTTPS。

> ⚠️ **安全提醒**:本服務沒有任何登入機制。放到公網前請至少加
> Basic Auth、Cloudflare Access 或只綁 127.0.0.1 走內網。

---

## 八、檔案結構

```
markitdown-web/
├── app.py               # FastAPI 後端(轉換、警告偵測、ZIP 匯出)
├── static/
│   └── index.html       # 單頁前端(拖放、預覽、複製、下載)
├── requirements.txt     # Python 依賴(精簡版)
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 九、疑難排解

| 症狀 | 原因 / 解法 |
|---|---|
| `pip install` 失敗 | Python 版本 < 3.10;或先 `pip install -U pip` |
| `ModuleNotFoundError: markitdown` | 忘了啟動虛擬環境(`source .venv/bin/activate`) |
| 開網頁是空白 | 後端沒啟動;確認終端機沒有錯誤訊息 |
| `Address already in use` | 8000 被佔用,改 `--port 8001` |
| 上載大檔回 413 | 調高 `MAX_UPLOAD_MB=300` |
| 轉出來是空的 | 幾乎都是掃描影像 PDF,需要 OCR |
| 中文變亂碼 | 確認檔案本身是文字層 PDF;下載時用 UTF-8 開 |

---

## 十、和你手上那批童軍 PDF 的搭配

`04` 類(行政)與 `03` 類(政策)的 PDF 大多是文字型,轉換品質不錯;
`07` 類與海報類可能是圖檔輸出,轉出來容易是空的。

建議流程:

1. 用上面的 Python 批次腳本一次轉完整個資料夾
2. 檢查輸出中 `chars` 很小的檔案 → 標記為「需 OCR / 需人工」
3. 轉出的 `.md` 先放 `staging/`,人工核對通告編號與生效日期後才進 Git
4. 檔名沿用官方名稱,與 `下載及上載紀錄/工作紀錄.csv` 對得上
