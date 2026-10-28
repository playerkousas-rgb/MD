# 傻瓜版轉換器(Windows)
# 雙擊 → 揀資料夾 → 自動轉換 → 自動開結果資料夾
#
# 也可以把資料夾（或幾個 PDF）直接拖到這個檔案上。
param(
    [string]$Target = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Head($text) { Write-Host ""; Write-Host $text -ForegroundColor Cyan }

try {
    # ---------- 0. 標題 ----------
    try { $Host.UI.RawUI.WindowTitle = "PDF → Markdown" } catch { }
    Write-Host "===============================================" -ForegroundColor DarkCyan
    Write-Host "        PDF  →  Markdown  (含 OCR)" -ForegroundColor White
    Write-Host "===============================================" -ForegroundColor DarkCyan

    # ---------- 1. 檢查／安裝 ----------
    if (-not (Test-Path ".venv\.deps-ok")) {
        Write-Head "第一次使用,需要先安裝(約 2-4 分鐘,只需一次)…"
        & cmd /c "`"$Root\_setup.bat`""
        if (-not (Test-Path ".venv\.deps-ok")) {
            Write-Host ""
            Write-Host "✗ 安裝未完成,請看上面的訊息。" -ForegroundColor Red
            Read-Host "按 Enter 關閉"
            exit 1
        }
    }

    # ---------- 2. 取得目標資料夾 ----------
    $Src = $Target
    $TempInput = $null
    $Work = $null
    $Out = $null

    if ([string]::IsNullOrWhiteSpace($Src)) {
        Add-Type -AssemblyName System.Windows.Forms | Out-Null
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = "請選擇放了 PDF 的資料夾"
        $dlg.ShowNewFolderButton = $false
        $dlg.RootFolder = [System.Environment+SpecialFolder]::MyComputer

        if ($dlg.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) {
            Write-Host ""
            Write-Host "已取消。" -ForegroundColor Yellow
            Start-Sleep -Seconds 2
            exit 0
        }
        $Src = $dlg.SelectedPath
    }
    if (-not (Test-Path $Src)) {
        Write-Host ""
        Write-Host "✗ 找不到:$Src" -ForegroundColor Red
        Read-Host "按 Enter 關閉"
        exit 1
    }

    # ---------- 3. 決定工作目錄與輸出路徑 ----------
    if (Test-Path $Src -PathType Leaf) {
        # 拖進來的是單一檔案 → 轉換用暫存資料夾,但輸出放在原檔旁邊,
        # 否則檔案會落在隨機命名的暫存資料夾,使用者找不到。
        $Orig = (Resolve-Path $Src).Path
        $Stem = [System.IO.Path]::GetFileNameWithoutExtension($Orig)
        $Out = Join-Path (Split-Path $Orig -Parent) "$Stem-md"
        $TempInput = Join-Path $env:TEMP ("pdf2md-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
        New-Item -ItemType Directory -Path $TempInput -Force | Out-Null
        Copy-Item $Orig $TempInput
        $Work = $TempInput
    }
    else {
        $Work = $Src.TrimEnd('\')
        if ($Work -match '^[A-Za-z]:$') {
            # 整個磁碟機 → 放到桌面
            $Out = Join-Path ([Environment]::GetFolderPath("Desktop")) "PDF轉Markdown"
        }
        else {
            $Out = "$Work-md"
        }
    }

    Write-Host ""
    Write-Host "  來源: $Src" -ForegroundColor Gray
    Write-Host "  輸出: $Out" -ForegroundColor Gray
    Write-Host ""

    # ---------- 4. 轉換 ----------
    # ⚠ 必須先放寬 ErrorActionPreference:PowerShell 5.1 在 Stop 模式下,
    #   原生程式輸出到 stderr 會被當成終止錯誤,python 的警告會直接中斷轉換。
    $ErrorActionPreference = "Continue"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    & ".\.venv\Scripts\python.exe" "batch_convert.py" "$Work" -o "$Out" --ocr auto --workers 2
    $code = $LASTEXITCODE
    $sw.Stop()
    $ErrorActionPreference = "Stop"

    if ($TempInput) { Remove-Item $TempInput -Recurse -Force -ErrorAction SilentlyContinue }

    # ---------- 5. 收尾 ----------
    Write-Host ""
    if ($code -ne 0) {
        Write-Host "✗ 轉換過程有錯誤,請看上面訊息。" -ForegroundColor Red
        Read-Host "按 Enter 關閉"
        exit $code
    }

    $mdCount = (Get-ChildItem -Path $Out -Filter "*.md" -Recurse -ErrorAction SilentlyContinue).Count
    if ($mdCount -eq 0) {
        Write-Host "⚠ 這個資料夾裡找不到可轉換的檔案(PDF / Word / Excel …)。" -ForegroundColor Yellow
        Read-Host "按 Enter 關閉"
        exit 0
    }

    Write-Host "===============================================" -ForegroundColor Green
    Write-Host ("  完成!{0} 份 .md,用了 {1:N0} 秒" -f $mdCount, $sw.Elapsed.TotalSeconds) -ForegroundColor Green
    Write-Host "===============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host ("  放在:" + $Out) -ForegroundColor White
    Write-Host "  已幫你開啟資料夾。" -ForegroundColor Gray
    Write-Host ""

    # 開啟結果資料夾
    Start-Process explorer.exe $Out

    Read-Host "  按 Enter 關閉" | Out-Null
}
catch {
    Write-Host ""
    Write-Host "✗ 發生錯誤:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    Read-Host "按 Enter 關閉"
    exit 1
}
