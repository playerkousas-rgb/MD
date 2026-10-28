# 用 CMD 更新 Python(你部機由 3.10 → 3.12)

> 你部機現況:`Python 3.10.11`、`pymupdf 1.28.2`、`版面分析 = 關`
> 目標:`Python 3.12.x`、`pymupdf 2.0`、`版面分析 = 開`
>
> 原因:`pymupdf 2.0` 在 PyPI 上寫明 `requires_python: >=3.11`。
> 3.10 只能裝 1.x,1.x 沒有 `to_markdown()`,所以永遠出純文字。

---

## 步驟 0 — 開一個「以管理員身分執行」的命令提示字元

1. 按 **Win 鍵**
2. 打 `cmd`
3. 在「命令提示字元」上 **右鍵** → **「以管理員身分執行」**
4. 按「是」

> 為什麼要管理員:安裝 Python 會寫入系統資料夾,PATH 也要改。
> 不是管理員的話,`winget` 可能裝到一半失敗。

---

## 步驟 1 — 先睇你而家有咩(照抄,按 Enter)

```cmd
python --version
```

```cmd
py -0
```

`py -0` 會列出你部機**所有**已安裝的 Python 版本,例如:

```
 -V:3.10 *        Python 3.10 (64-bit)
```

`*` 代表現在預設用哪個。**記住這個畫面**,裝完之後再跑一次對比。

---

## 步驟 2 — 用 winget 裝 Python 3.12(一行)

```cmd
winget install -e --id Python.Python.3.12
```

- 想裝 3.13(最新)就把 `3.12` 改成 `3.13`,一樣可以
- 過程中可能會問你同意條款,打 `Y` 按 Enter
- 大約 1 分鐘

**如果出現 `'winget' 不是內部或外部命令`:**

代表你部 Windows 太舊沒有 App Installer。跳到下面 **「方法 B」**。

---

## 步驟 3 — ⚠️ 關掉所有 CMD 視窗,再開一個新的

**這一步最多人漏,漏了就會以為裝失敗。**

Windows 的命令提示字元在開啟那一刻就固定了 PATH。你裝完 Python,
**舊視窗永遠看不到新版本**。

所以:

1. 把所有黑色 CMD 視窗 **全部關掉**(按 `exit` 或右上角 X)
2. 重新開一個 CMD(不需要管理員了,普通就可以)

---

## 步驟 4 — 驗證(照抄)

```cmd
py -0
```

應該變成這樣(多了一行 3.12,而 `*` 移到 3.12):

```
 -V:3.12 *        Python 3.12 (64-bit)
 -V:3.10          Python 3.10 (64-bit)
```

再確認指定版本叫得到:

```cmd
py -3.12 --version
```

應該印 `Python 3.12.x`。

> 3.10 **不要卸載**。兩個版本可以並存,`py` 啟動器負責選。
> 卸載反而可能弄壞其他東西。

---

## 步驟 5 — 重建 `.venv`(讓轉換器改用 3.12)

### 方法 0(最簡單)— 雙擊 `修正Python環境.bat`

回到 `markitdown-web` 資料夾,雙擊 **`修正Python環境.bat`**。它會:

1. 印出 `.venv` 現在用哪個 Python(你應該見到 `3.10.11 / pymupdf 1.28.2`)
2. 自動找 3.13 → 3.12 → 3.11 → python
3. 找到就刪掉舊 `.venv` 重建(2–4 分鐘)
4. 最後自動跑診斷,把結果印在畫面上

如果它說「No Python 3.11+ found」,代表你未裝,或者**這個視窗是在安裝前開的** ——
關掉所有 CMD,開新的,再雙擊一次。

### 方法 1 — 交給 `PDF2MD.bat`

新版 `PDF2MD.bat` 會先檢查 `.venv` 的 Python 版本,不對就自動走重建流程。


先 `cd` 到你的 `markitdown-web` 資料夾。**把路徑換成你自己的**:

```cmd
cd /d "D:\MD-arena-a2225b93-md\markitdown-web"
```

> 不確定路徑?在檔案總管打開 `markitdown-web` 資料夾,
> 按一下上方網址列,路徑會變成可複製的文字,複製貼上即可。

### 方法 1(推薦)— 交給新版自動做

```cmd
PDF2MD.bat
```

新版 `_setup.bat` 會偵測到舊 `.venv` 是 3.10、而機器上有 3.12,
**自動刪掉重建**。你只會看到:

```
   Using Python: py -3.12
   [!] Existing .venv uses an old Python. Rebuilding it...
   [1/3] Creating virtual environment...
   [2/3] Installing packages, 2 to 4 minutes, one time only...
   [3/3] Fixing OpenCV to headless build...

Python      : 3.12.4
PDF 引擎    : pymupdf
PyMuPDF     : 2.0
版面分析    : 可用
OCR         : 可用

結論:一切正常,可以轉換。
```

### 方法 2 — 手動刪(方法 1 失敗時才用)

```cmd
rmdir /s /q .venv
```

```cmd
PDF2MD.bat
```

---

## 步驟 6 — 最後確認

```cmd
.venv\Scripts\python -c "import pymupdf; print(pymupdf.__version__, hasattr(pymupdf.open(),'to_markdown'))"
```

| 印出 | 意思 |
|---|---|
| `2.0 True` | ✅ 成功,有標題有表格 |
| `1.28.2 False` | ❌ 還在用舊版,回到步驟 3 檢查有無重開 CMD |

再跑一次完整診斷:

```cmd
.venv\Scripts\python _diag_env.py
```

必須見到 `版面分析 : 可用` 和 `結論:一切正常,可以轉換。`

---

## 方法 B — 沒有 winget 時,用 CMD 下載安裝檔

Windows 10 1803 之後內建 `curl.exe`,可以直接在 CMD 下載:

```cmd
curl -L -o "%TEMP%\py-setup.exe" https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe
```

> 如果上面那條回 404,代表 patch 版本號更新了。
> 開 https://www.python.org/downloads/windows/ 找最新的 `3.12.x`,
> 把網址裡的 `3.12.10` 換成你看到的數字。

下載完,靜默安裝(**`PrependPath=1` 就是自動加 PATH,等於勾那個選框**):

```cmd
"%TEMP%\py-setup.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
```

等 1–2 分鐘,`%TEMP%\py-setup.exe` 那個視窗自己結束就是裝完。
然後回到 **步驟 3**。

> 老實講:我用唔到你部電腦,`curl` 那條 URL 我只驗證了格式,
> 冇辦法替你確認 `3.12.10` 這個 patch 號今天還存在。
> **有 winget 就優先用地方法 A**,它會自動找最新版,不會有這個問題。

---

## 遇錯時對照表

| 你見到 | 原因 | 點做 |
|---|---|---|
| `winget 不是內部或外部命令` | Windows 太舊 / 沒 App Installer | 用「方法 B」 |
| `winget` 說「已安裝現有套件 / 找不到可用的升級」 | Python **已經裝了**,唔需要再裝 | 跑 `py -0p` 看實際路徑;已裝就跳到步驟 3 重建 `.venv` |
| `py -0p` 見到 3.12,但轉出嚟仍然純文字 | `.venv` 仍是舊的,而舊 `PDF2MD.bat` 見到 `.deps-ok` 就跳過重建 | `rmdir /s /q .venv` 然後 `py -3.12 -m venv .venv`,或者用新版 ZIP |
| `py -0` 裝完仍是只有 3.10 | CMD 沒重開 | 關掉全部 CMD 視窗,再開新的 |
| `py -3.12` 說找不到 | PATH 沒更新 | 重開 CMD;仍不行就跑 `py -0p` 看實際路徑 |
| 重建時 `Could not delete the old .venv` | 有視窗正在用它 | 關掉 `PDF2MD.bat` / `start.bat` 的黑窗,再試 |
| `[X] Package installation failed` | 網絡 / 代理 | 檢查網絡;公司網絡可能要設 proxy |
| 裝完仍是 `pymupdf 1.28.2` | `.venv` 沒重建 | 手動 `rmdir /s /q .venv`,再 `PDF2MD.bat` |

---

## 一句話總結

```cmd
winget install -e --id Python.Python.3.12
```

→ **關掉所有 CMD,開新的** → `cd` 到 `markitdown-web` → `PDF2MD.bat` → 完工。
