# gemini/ — 童軍文件問答頁

**只讀 Markdown。** 這一頁不做轉換、不做 OCR、不需要 Python,
它把 repo 裡已經轉好的 `.md` 當知識庫,交給 Gemini 回答問題,並標出答案出自哪份文件。

```
gemini/
├── ai-scout.html        # ★ AI SCOUT 介面(GitHub 直讀 .md,自動發現新檔案)
├── 童軍問答-單檔.html   # 79 份文件全部內嵌,雙擊即開,離線可用
├── index.html           # 需要 http server 的版本(知識庫另外載入)
├── README.md
└── (tools/build_gemini_single.py 產生單檔版)
```

## AI SCOUT（`ai-scout.html`）

單一 HTML 檔,貼進 Gemini Canvas 或直接開都可以。特點:

- **自動發現文件**:用 GitHub trees API 列出 `knowledge/` 內所有 `.md`(共 213 份),
  新檔案只要放進 `knowledge/` 就自動出現,不需要改索引、不需要重新 build。
- **不需要輸入 API key**:Canvas 會用登入者自己的 Google 額度。
- **三段式輸出**:大字答案 / 可摺疊的「具體要點」(自動轉列點) / 可摺疊的「根據」(檔名 + 頁數)。
- **長文件不會截斷**:`excerptOf()` 抽最相關段落,再按頁碼合併前後文。
- **輸出上限處理**:`maxOutputTokens` 按模型給到最大(2.5-flash 65536),
  實際長度由提示詞的字數規矩控制;真的撞到上限會自動續寫。
- 文件清單與診斷紀錄收在右上角 ⚙ 內,預設隱藏。

© Scout System

## 〇、直接雙擊就能用(推薦)

**雙擊 `童軍問答-單檔.html` 即可。**

這一個檔案裡已經內嵌了全部 79 份 Markdown(約 1.5 MB)與索引,
所以不需要起 server、不需要 Python、不需要網路(除了呼叫 Gemini)。

> `index.html` 是用 `fetch("../knowledge/…")` 讀資料的版本。
> 用 `file://` 雙擊時瀏覽器會擋掉 fetch(同源政策),所以那個版本必須
> 用 http server 開,例如 `python -m http.server`。
> 只是要問問題的話,用單檔版就好。

要更新單檔版(例如 `knowledge/` 換了內容):

```
python3 tools/build_gemini_single.py
python3 tools/build_gemini_single.py --check    # 只檢查是否過期
```

配合的資料:

```
knowledge/
├── _index.json                       # 文件清單(標題、分類、字數、頁數、OCR 頁數)
├── 01_POR及會章/*.md
├── 02_支部訓練綱要/*.md
└── … 共 79 份
```

---

## 一、它怎樣回答問題

1. 讀 `_index.json` → 左邊列出所有文件
2. 你問問題 → 在**瀏覽器內**用 IDF 加權的關鍵字檢索,從 79 份挑出最相關的 2–6 份
3. 只把這幾份的內容組成 prompt 送去 Gemini(不會把整個知識庫上傳)
4. 答案下方列出引用文件;命中的文件若含 OCR 頁,會標 `OCR` 提醒核對原文

API key 只存在瀏覽器的 `localStorage`,不經任何伺服器。
沒有 key 也可以搜尋、瀏覽、複製原文。

---

## 二、知識庫放在哪(`KB` 變數)

`index.html` 開頭:

```js
const KB = (new URLSearchParams(location.search).get("kb")
        || (location.pathname.includes("/gemini/") ? "../knowledge" : "./knowledge"))
```

三種用法:

| 情況 | 網址 | `KB` |
|---|---|---|
| 部署在 repo 根,頁面在 `/gemini/` | `https://xxx.vercel.app/gemini/` | `../knowledge` ✓ |
| 把 `knowledge/` 複製到頁面旁邊 | `https://xxx/` | `./knowledge` ✓ |
| 頁面與資料不同站 | `…?kb=https://raw.githubusercontent.com/…/knowledge` | 由參數指定 |

第三種很適合「頁面放在 Vercel,資料留在 GitHub」:
repo 是公開的,`raw.githubusercontent.com` 有開 CORS,直接就能讀。

---

## 三、部署

### A. Vercel(Root Directory 留空 = repo 根目錄)

1. Add New… → Project → Import `playerkousas-rgb/MD`
2. **Root Directory 留空**(不要選 `gemini`)
3. Framework Preset:**Other**,Build / Output 留空
4. Deploy → 開 `https://<project>.vercel.app/gemini/`

這樣 `/gemini/index.html` 與 `/knowledge/*.md` 同站,`../knowledge` 直接可用。
(整份 repo 都會被發佈,包括 `tools/`、`下載及上載紀錄/` 等;repo 本身是公開的,內容一致。)

### B. GitHub Pages

Settings → Pages → Source: `Deploy from a branch` → 選 `arena/a2225b93-md` / `root`。
網址 `https://playerkousas-rgb.github.io/MD/gemini/`,同樣是 `../knowledge`。

### C. 只想部署 gemini/ 一個資料夾

Root Directory 選 `gemini`,然後用 `?kb=` 指向 GitHub raw:

```
https://<project>.vercel.app/?kb=https://raw.githubusercontent.com/playerkousas-rgb/MD/arena/a2225b93-md/knowledge
```

---

## 四、換 Gemini 模型

頁面上可以直接選,或用 `localStorage.geminiModel` 設預設:

| 模型 | 建議 |
|---|---|
| `gemini-2.5-flash`(預設)| 夠快、夠便宜,一般問答首選 |
| `gemini-2.5-pro` | 要跨幾份長文件推理時才用 |
| `gemini-2.0-flash` | 舊專案相容 |

---

## 五、改提示詞

在 `index.html` 找 `const system = [...]`,目前規則:

1. 只根據提供的文件回答,文件沒有就說「文件中未提及」
2. 每個答案標明出自哪個檔案
3. 引用的檔案若含 OCR 頁,涉及日期／金額／通告編號時要提醒核對原文
4. 用香港繁體、先結論後要點

改完直接重新整理頁面即可,沒有 build 步驟。

---

## 六、除錯

| 症狀 | 原因 |
|---|---|
| 左邊空白、提示讀不到 `_index.json` | `KB` 路徑不對;先直接開 `…/knowledge/_index.json` 看是否 200 |
| 有 key 但回 `API key not valid` | key 錯了,或該 key 沒開 Generative Language API |
| 回 `model not found` | 換一個模型(見上表) |
| 瀏覽器擋 CORS | 直接把 `index.html` 用 `file://` 開會失效,要用 http(s) 提供 |
| 答案老是「文件中未提及」 | 檢索沒抓到;換更接近原文的關鍵字,或把「引用文件數」調高 |
