#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 markitdown-web/convert_core.py 同步到 pdf2md/(Vercel 版)。

兩個應用共用同一套轉換邏輯,但 Vercel 專案的根目錄是 pdf2md/,
不能 import 目錄外的模組,所以用複製 + 這支腳本保持同步。

    python tools/sync_core.py          # 同步
    python tools/sync_core.py --check  # 只檢查是否同步(CI 用,不同步則 exit 1)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "markitdown-web" / "convert_core.py"
DST = ROOT / "pdf2md" / "convert_core.py"

HEADER = """#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ⚠ 此檔由 markitdown-web/convert_core.py 複製而來,請勿直接編輯。
#   改動請改來源檔,再執行 python tools/sync_core.py。
#   Vercel 版不裝 PyMuPDF,會自動使用 pypdfium2(見 pdf_engine())。
"""


def render() -> str:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)
    while lines and (lines[0].startswith("#!") or "coding:" in lines[0]):
        lines.pop(0)
    return HEADER + "".join(lines)


def main() -> int:
    want = render()
    if "--check" in sys.argv:
        have = DST.read_text(encoding="utf-8") if DST.exists() else ""
        if have != want:
            print("✗ pdf2md/convert_core.py 與來源不同步,請執行 python tools/sync_core.py",
                  file=sys.stderr)
            return 1
        print("✓ 兩個核心檔同步")
        return 0
    DST.write_text(want, encoding="utf-8")
    print("✓ 已同步 → %s" % DST.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
