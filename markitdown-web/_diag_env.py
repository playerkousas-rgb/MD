#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列印轉換環境的診斷摘要 — 由 _diag.bat 呼叫。

單獨執行也可以:
    .venv\\Scripts\\python.exe _diag_env.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import convert_core
except Exception as e:  # noqa: BLE001
    print("無法載入 convert_core:%s: %s" % (type(e).__name__, e))
    sys.exit(1)

info = convert_core.runtime_report()
print("Python      : %s" % info["python"])
print("PDF 引擎    : %s" % info["pdf_engine"])
print("PyMuPDF     : %s" % info["pymupdf"])
print("版面分析    : %s" % ("可用" if info["layout_available"] else "不可用(不會有標題／表格)"))
print("OCR         : %s" % ("可用" if info["ocr_available"] else "不可用(掃描版會抽不到字)"))
print()

warnings = convert_core.layout_doctor()
if not warnings:
    print("結論:一切正常,可以轉換。")
else:
    print("結論:有問題要處理 ——")
    for line in warnings:
        print("  " + line)
