#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正「排版分析靜靜退回純文字」的 bug。

問題:使用者用最新版轉換器,但機器上 PyMuPDF 是 1.x(Python < 3.11)
     → layout_available() 為 False → 程式靜靜走純文字路徑
     → 輸出沒有標題／表格,而畫面一句提示都沒有。

修正:
 1. convert_core.pdf_to_markdown:要求排版但不可用時,寫入 meta["warnings"]
 2. convert_core:新增 runtime_report() / layout_fix_hint() / layout_doctor()
 3. batch_convert:開跑前後都大聲報告環境與「幾多份真正有排版」
 4. batch_convert:_index.json 記錄 layout_available / layout_docs / python / pymupdf
 5. batch_convert:_report.csv 加入 layout 欄
"""
import ast
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
os.chdir(ROOT)


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def rep(path, old, new, count=1):
    src = read(path)
    assert src.count(old) == count, "在 %s 找不到預期文字(找到 %d 次):\n%r" % (
        path, src.count(old), old[:120])
    src = src.replace(old, new, count)
    write(path, src)
    return src


# ------------------------------------------------------------------ convert_core
CORE = "markitdown-web/convert_core.py"

# 1) 補 import sys
src = read(CORE)
if "\nimport sys\n" not in src:
    rep(CORE, "\nimport re\n", "\nimport re\nimport sys\n")

# 2) 在 layout_available() 之後加入常數與診斷函式
ANCHOR = '''def _pdf_to_markdown_layout(path: str, ocr_mode: str, page_markers: bool,
                            glossary: dict | None):'''

NEW_FUNCS = '''LAYOUT_MISSING_WARNING = (
    "本機沒有版面分析:需要 PyMuPDF 2.0 及 Python 3.11 以上(PyMuPDF 1.x 沒有 to_markdown)。"
    "已退回純文字模式,標題／清單／表格都不會有結構。"
)


def runtime_report() -> dict:
    """回報執行環境:Python／PyMuPDF 版本、版面分析與 OCR 是否可用。"""
    info = {
        "python": "%d.%d.%d" % sys.version_info[:3],
        "pdf_engine": pdf_engine(),
        "pymupdf": None,
        "ocr_available": False,
        "layout_available": False,
    }
    try:
        import pymupdf

        info["pymupdf"] = (getattr(pymupdf, "__version__", None)
                           or getattr(pymupdf, "VersionBind", None))
    except Exception:  # noqa: BLE001
        pass
    try:
        info["ocr_available"] = ocr_available()
    except Exception:  # noqa: BLE001
        pass
    try:
        info["layout_available"] = layout_available()
    except Exception:  # noqa: BLE001
        pass
    return info


def layout_fix_hint() -> str:
    """告訴使用者怎樣把版面分析裝回來的具體一步。"""
    v = sys.version_info
    if v < (3, 11):
        return ("你的 Python 是 %d.%d,要 3.11 或以上才會裝到 PyMuPDF 2.0。"
                "請安裝 Python 3.11+(_setup.bat 會自動用它),"
                "然後刪除 .venv 資料夾、重新雙擊 PDF2MD.bat。" % (v[0], v[1]))
    return ("請在工具資料夾開 cmd 執行: "
            '.venv\\\\Scripts\\\\python -m pip install -U "pymupdf>=2.0"'
            "(macOS/Linux 用 .venv/bin/python),然後再轉換一次。")


def layout_doctor() -> list:
    """回傳要顯示給使用者的診斷訊息(空清單 = 一切正常)。"""
    msgs: list[str] = []
    info = runtime_report()
    if not info["layout_available"]:
        msgs.append("!! 版面分析沒有啟用 -> 標題／表格不會有結構")
        msgs.append("   Python %s | PyMuPDF %s" % (info["python"], info["pymupdf"]))
        msgs.append("   " + layout_fix_hint())
    if not info["ocr_available"]:
        msgs.append("!! OCR 沒有啟用 -> 掃描版 PDF 會完全抽不到文字")
    return msgs


''' + ANCHOR

rep(CORE, ANCHOR, NEW_FUNCS)

# 3) 排版分支:記錄「要求了但不可用」
rep(CORE, '''    if layout is None:
        want = os.environ.get("PDF_LAYOUT", "auto").strip().lower()
        layout = want in ("auto", "1", "true", "yes") and layout_available()
    if layout and layout_available():
        return _pdf_to_markdown_layout(path, ocr_mode, page_markers, glossary)''',
    '''    layout_missing = False
    if layout is None:
        want = os.environ.get("PDF_LAYOUT", "auto").strip().lower()
        layout = want in ("auto", "1", "true", "yes")
    if layout and not layout_available():
        layout_missing = True
        layout = False
    if layout:
        return _pdf_to_markdown_layout(path, ocr_mode, page_markers, glossary)''')

# 4) 把警告塞進 meta
rep(CORE, '''        "warnings": warnings_out,
        "layout": False,
    }
    if pages_ocr:''',
    '''        "warnings": warnings_out,
        "layout": False,
    }
    if layout_missing:
        meta["warnings"].insert(0, LAYOUT_MISSING_WARNING)
    if pages_ocr:''')

ast.parse(read(CORE))
print("[OK] convert_core.py 已修好")

# ------------------------------------------------------------------ batch_convert
BAT = "markitdown-web/batch_convert.py"

# 5) 開跑前報告環境
rep(BAT, '''    print("檔案:%d 個 | OCR 模式:%s | 平行:%d | OCR 可用:%s\\n"
          % (len(files), args.ocr, args.workers, core.ocr_available()), flush=True)''',
    '''    print("檔案:%d 個 | OCR 模式:%s | 平行:%d | OCR 可用:%s\\n"
          % (len(files), args.ocr, args.workers, core.ocr_available()), flush=True)

    env = core.runtime_report()
    print("環境:Python %s | %s %s | 版面分析:%s | OCR:%s"
          % (env["python"], env["pdf_engine"], env["pymupdf"],
             "開" if env["layout_available"] else "關",
             "可用" if env["ocr_available"] else "不可用"), flush=True)
    env_warnings = core.layout_doctor()
    if env_warnings:
        print("", flush=True)
        for line in env_warnings:
            print(line, flush=True)
        print("", flush=True)''')

# 6) CSV 加 layout 欄
rep(BAT, '''            "pages", "pages_ocr", "ocr_avg_score", "seconds", "sha256",
            "title", "warnings", "error"]''',
    '''            "pages", "pages_ocr", "ocr_avg_score", "seconds", "sha256",
            "title", "warnings", "error", "layout"]''')

# 7) index.json 記錄排版狀態
rep(BAT, '''        "total": len(results),
        "converted": len(ok),''',
    '''        "total": len(results),
        "layout_available": env["layout_available"],
        "layout_docs": sum(1 for r in ok if r.get("layout")),
        "python": env["python"],
        "pymupdf": env["pymupdf"],
        "converted": len(ok),''')

# 8) 收尾報告排版覆蓋率
rep(BAT, '''    print("\\n" + "=" * 66)
    print("完成:%d 個 | 跳過(已存在):%d | 失敗:%d | 耗時 %.1fs"
          % (len(ok), len(skipped), len(failed), elapsed))''',
    '''    print("\\n" + "=" * 66)
    print("完成:%d 個 | 跳過(已存在):%d | 失敗:%d | 耗時 %.1fs"
          % (len(ok), len(skipped), len(failed), elapsed))
    got_layout = sum(1 for r in results if r.get("layout"))
    if got_layout:
        print("有版面分析(標題／表格):%d / %d 個" % (got_layout, len(results)))
    elif results:
        print("!! 全部 %d 個都沒有版面分析,輸出只有純文字 —— 原因見上面「環境」一節。"
              % len(results))''')

ast.parse(read(BAT))
print("[OK] batch_convert.py 已修好")
