# ===========================================================
#  PDF -> Markdown  (傻瓜版)
#  由 PDF2MD.bat 呼叫;也可以直接把資料夾/PDF 拖到 PDF2MD.bat 上。
#  檔名與本檔的註解用英文,介面文字用中文(本檔有 UTF-8 BOM,
#  Windows PowerShell 5.1 才會正確顯示中文)。
# ===========================================================
param(
    [string]$Target = "",
    [switch]$Force
)

$ErrorActionPreference = "Continue"

# ---------- 定位 ----------
$Root = $PSScriptRoot
if ([string]::IsNullOrEmpty($Root)) {
    $Root = Split-Path -Parent $MyInvocation.MyCommand.Definition
}
Set-Location $Root

$Log = Join-Path $Root "_last-run.log"
$script:TranscriptOn = $false
try {
    Start-Transcript -Path $Log -Force -ErrorAction Stop | Out-Null
    $script:TranscriptOn = $true
} catch { }

function Stop-Log {
    if ($script:TranscriptOn) {
        try { Stop-Transcript | Out-Null } catch { }
        $script:TranscriptOn = $false
    }
}

function Say($text, $color = "Gray") {
    Write-Host $text -ForegroundColor $color
}

function Show-Banner {
    Say "===============================================" "DarkCyan"
    Say "        PDF  ->  Markdown   (含 OCR)" "White"
    Say "===============================================" "DarkCyan"
}

# ---------- 主流程 ----------
try {
    try { $Host.UI.RawUI.WindowTitle = "PDF to Markdown" } catch { }

    Show-Banner

    # 1. 檢查安裝
    if (-not (Test-Path ".venv\.deps-ok")) {
        Say ""
        Say "  尚未安裝完成。" "Red"
        Say "  請先雙擊同一個資料夾內的 PDF2MD.bat,讓它完成安裝。" "Yellow"
        Stop-Log
        exit 1
    }

    # 2. 取得目標
    $Src = $Target

    if ([string]::IsNullOrWhiteSpace($Src)) {
        Say ""
        Say "  請在彈出的視窗選擇放了 PDF 的資料夾…" "Cyan"
        Add-Type -AssemblyName System.Windows.Forms | Out-Null
        $dlg = New-Object System.Windows.Forms.FolderBrowserDialog
        $dlg.Description = "請選擇放了 PDF 的資料夾"
        $dlg.ShowNewFolderButton = $false

        $result = $dlg.ShowDialog()
        if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
            Say ""
            Say "  已取消。" "Yellow"
            Stop-Log
            exit 0
        }
        $Src = $dlg.SelectedPath
    }

    if ([string]::IsNullOrWhiteSpace($Src) -or -not (Test-Path $Src)) {
        Say ""
        Say ("  找不到: " + $Src) "Red"
        Stop-Log
        exit 1
    }

    # 3. 決定工作目錄與輸出位置
    $TempInput = $null
    $Work = $null
    $Out = $null

    if (Test-Path $Src -PathType Leaf) {
        # 拖進來的是單一檔案:轉換用暫存資料夾,但輸出放在原檔旁邊,
        # 否則結果會落在隨機命名的資料夾裡,使用者找不到。
        $Orig = (Resolve-Path $Src).Path
        $Stem = [System.IO.Path]::GetFileNameWithoutExtension($Orig)
        $Out = Join-Path (Split-Path $Orig -Parent) ($Stem + "-md")
        $TempInput = Join-Path $env:TEMP ("pdf2md-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
        New-Item -ItemType Directory -Path $TempInput -Force | Out-Null
        Copy-Item $Orig $TempInput
        $Work = $TempInput
    }
    else {
        $Work = $Src.TrimEnd('\')
        if ($Work -match '^[A-Za-z]:$') {
            $Out = Join-Path ([Environment]::GetFolderPath("Desktop")) "PDF轉Markdown"
        }
        else {
            $Out = $Work + "-md"
        }
    }

    Say ""
    Say ("  來源: " + $Src) "Gray"
    Say ("  輸出: " + $Out) "Gray"
    Say "  正在轉換,請稍等…" "Cyan"
    Say ""

    # 4. 轉換
    # 注意:PowerShell 5.1 在 ErrorActionPreference=Stop 下,
    # 原生程式寫 stderr 會被當成終止錯誤,python 的警告會中斷整個轉換。
    $ErrorActionPreference = "Continue"
    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    $extra = @()
    if ($Force) {
        Say "  模式: 強制重新轉換(覆蓋既有 .md)" "Yellow"
        $extra += "--force"
    }
    & ".\.venv\Scripts\python.exe" "batch_convert.py" "$Work" -o "$Out" --ocr auto --workers 2 @extra
    $code = $LASTEXITCODE

    $sw.Stop()
    $ErrorActionPreference = "Stop"

    if ($null -ne $TempInput -and (Test-Path $TempInput)) {
        Remove-Item $TempInput -Recurse -Force -ErrorAction SilentlyContinue
    }

    Say ""
    if ($code -ne 0) {
        Say "  [X] 轉換過程有錯誤,詳情見上面訊息。" "Red"
        Say ("  完整紀錄: " + $Log) "DarkGray"
        Stop-Log
        exit $code
    }

    # 5. 結果
    $mdCount = 0
    if (Test-Path $Out) {
        $mdCount = @(Get-ChildItem -Path $Out -Filter "*.md" -Recurse -ErrorAction SilentlyContinue).Count
    }

    if ($mdCount -eq 0) {
        Say "  [!] 這個資料夾裡找不到可轉換的檔案(PDF / Word / Excel / 圖片…)。" "Yellow"
        Stop-Log
        exit 0
    }

    Say "===============================================" "Green"
    Say ("  完成!{0} 份 .md,用了 {1:N0} 秒" -f $mdCount, $sw.Elapsed.TotalSeconds) "Green"
    Say "===============================================" "Green"
    Say ""
    Say ("  放在: " + $Out) "White"
    Say "  已幫你打開該資料夾。" "Gray"

    try { Start-Process explorer.exe $Out } catch { }

    Stop-Log
    exit 0
}
catch {
    Say ""
    Say "  [X] 發生錯誤:" "Red"
    Say ("      " + $_.Exception.Message) "Red"
    Say ("  完整紀錄: " + $Log) "DarkGray"
    Stop-Log
    exit 1
}
