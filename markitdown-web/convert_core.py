#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
轉換核心 — 網頁服務與批量腳本共用同一套邏輯。

PDF 走「逐頁判斷」路線:
    頁面有文字層  → 直接抽取(快、準)
    頁面是掃描影像 → 渲染成圖片再 OCR
兩種情況可以在同一份 PDF 內混用,這對「部分頁面是掃描件」的公文很常見。

OCR 用 RapidOCR(PP-OCR,ONNX Runtime),純 pip、不需系統 Tesseract。
PP-OCR 的中文模型輸出偏向簡體,所以用 OpenCC `s2t` 轉成繁體
(標準繁體)校正 —— 不能用 `s2hk`(會把「閱/說」改成異體「閲/説」),
也不能用 `s2twp`(會把「程序」換成臺灣的「程式」)。
"""

from __future__ import annotations

import io
import os
import re
import threading
import warnings
from typing import Iterable

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------- 可調參數

# 一頁抽到少於這個字數,就當作「沒有文字層」改用 OCR
MIN_CHARS_PER_PAGE = 40

# OCR 渲染解析度。200 對中文公文夠用;降到 150 快約一倍但小字易錯。
OCR_DPI = int(os.environ.get("OCR_DPI", "200"))

# 過短的碎行(通常是頁眉頁腳、印章殘影)直接丟掉
MIN_LINE_CHARS = 1
# 純標點／符號的框通常是表格框線或污點,直接丟掉
_NOISE_RE = re.compile(r"^[\W_]+$")

OCR_MODES = ("auto", "always", "never")

# 常見 OCR 誤認的童軍用語。只做「明確錯字」的整詞替換,不會亂改其他字。
DEFAULT_GLOSSARY = {
    "負袖": "負責",
    "童军": "童軍",
    "旅团": "旅團",
    "支部訓練网要": "支部訓練綱要",
    "網要": "綱要",
    "徽童": "徽章",
    "幼童军": "幼童軍",
    "深资": "深資",
    "乐行": "樂行",
    "总會": "總會",
    "總会": "總會",
    "地域总": "地域總",
}

# ---------------------------------------------------------------- 繁化轉換

_opencc = None
_opencc_failed = False
_opencc_lock = threading.Lock()


def _to_hant(text: str) -> str:
    """簡體 → 繁體。OpenCC 不可用時原樣返回(不影響主流程)。

    用 `s2t`(標準繁體)而不是 `s2hk`:
      * s2hk 會把原本正確的「閱/說」改寫成香港異體「閲/説」,
        實測整份知識庫會被改掉 212 處,與官方文件用字不符。
      * s2twp 會換成臺灣詞彙(程序→程式),更不對。
      * s2t 只做字形轉換,對已是繁體的文字完全無改動。
    """
    global _opencc, _opencc_failed
    if not text or _opencc_failed:
        return text
    with _opencc_lock:
        if _opencc is None:
            try:
                from opencc import OpenCC

                _opencc = OpenCC(os.environ.get("OPENCC_CONFIG", "s2t"))
            except Exception:
                _opencc_failed = True
                return text
    try:
        return _opencc.convert(text)
    except Exception:
        return text


def apply_glossary(text: str, glossary: dict | None = None) -> str:
    """套用詞彙表。傳 None → 用 DEFAULT_GLOSSARY;傳 {} → 完全不修正。"""
    if not text:
        return text
    table = DEFAULT_GLOSSARY if glossary is None else glossary
    for wrong, right in table.items():
        if wrong and wrong != right:
            text = text.replace(wrong, right)
    return text


# ---------------------------------------------------------------- OCR 引擎

_ocr_engine = None
_ocr_lock = threading.Lock()
_ocr_error = None


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401

        return True
    except Exception:
        return False


def _get_ocr():
    """RapidOCR 單例。模型載入只要 ~0.3s,但重複建立很浪費。"""
    global _ocr_engine, _ocr_error
    if _ocr_engine is not None:
        return _ocr_engine
    with _ocr_lock:
        if _ocr_engine is None:
            if _ocr_error:
                raise RuntimeError(_ocr_error)
            try:
                from rapidocr_onnxruntime import RapidOCR

                _ocr_engine = RapidOCR()
            except Exception as e:  # noqa: BLE001
                _ocr_error = "OCR 引擎無法載入:%s: %s" % (type(e).__name__, e)
                raise RuntimeError(_ocr_error) from e
    return _ocr_engine


_CJK = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


# ---------------------------------------------------------------- PDF 引擎
# 本機版用 PyMuPDF(功能最全);Vercel 版不裝 PyMuPDF(116MB),
# 自動退回 pypdfium2(約 8MB)。邏輯其餘部分兩邊完全一樣。

_PDF_ENGINE = None   # None=未決定 / "pymupdf" / "pdfium" / False=都沒有


def pdf_engine() -> str | None:
    """回傳目前使用的 PDF 引擎名稱;兩個都沒裝時回傳 None。"""
    global _PDF_ENGINE
    if _PDF_ENGINE is None:
        want = os.environ.get("PDF_ENGINE", "").strip().lower()
        if want in ("pymupdf", "fitz"):
            try:
                import pymupdf  # noqa: F401
                _PDF_ENGINE = "pymupdf"
            except ImportError:
                _PDF_ENGINE = False
        elif want == "pdfium":
            try:
                import pypdfium2  # noqa: F401
                _PDF_ENGINE = "pdfium"
            except ImportError:
                _PDF_ENGINE = False
        else:
            try:
                import pymupdf  # noqa: F401
                _PDF_ENGINE = "pymupdf"
            except ImportError:
                try:
                    import pypdfium2  # noqa: F401
                    _PDF_ENGINE = "pdfium"
                except ImportError:
                    _PDF_ENGINE = False
    return _PDF_ENGINE or None


class _PdfDoc:
    """把 PyMuPDF 與 pypdfium2 的 API 差異收在一層。"""

    def __init__(self, path: str):
        eng = pdf_engine()
        if eng == "pymupdf":
            import pymupdf
            self._doc = pymupdf.open(path)
            self.page_count = self._doc.page_count
        elif eng == "pdfium":
            import pypdfium2
            self._doc = pypdfium2.PdfDocument(path)
            self.page_count = len(self._doc)
        else:
            raise RuntimeError("沒有可用的 PDF 引擎(需要 pymupdf 或 pypdfium2)")

    def __iter__(self):
        if pdf_engine() == "pymupdf":
            for page in self._doc:
                yield page
        else:
            for page in self._doc:
                yield page
                try:
                    page.close()
                except Exception:
                    pass

    def close(self):
        try:
            self._doc.close()
        except Exception:
            pass


def page_text(page) -> str:
    """抽一頁的文字層。"""
    try:
        if pdf_engine() == "pymupdf":
            return page.get_text("text") or ""
        tp = page.get_textpage()
        try:
            return tp.get_text_range() or ""
        finally:
            tp.close()
    except Exception:
        return ""


def page_png(page, dpi: int) -> bytes:
    """把一頁點陣化成 PNG bytes,交給 OCR。"""
    import io

    if pdf_engine() == "pymupdf":
        return page.get_pixmap(dpi=dpi).tobytes("png")

    from PIL import Image

    bitmap = page.render(scale=dpi / 72.0)
    try:
        img = bitmap.to_pil()
    finally:
        try:
            bitmap.close()
        except Exception:
            pass
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def image_png(path: str) -> bytes:
    """把圖片檔轉成 PNG bytes。"""
    import io

    if pdf_engine() == "pymupdf":
        import pymupdf
        return pymupdf.Pixmap(path).tobytes("png")

    from PIL import Image

    buf = io.BytesIO()
    Image.open(path).convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def _is_cjk(ch: str) -> bool:
    return bool(ch) and bool(_CJK.match(ch))


def _join_wrapped(prev: str, nxt: str) -> str:
    """把 OCR 的「視覺行」接回段落:中文不加空格,英文加。"""
    if not prev:
        return nxt
    if not nxt:
        return prev
    if _is_cjk(prev[-1]) and _is_cjk(nxt[0]):
        return prev + nxt
    return prev + " " + nxt


# 通告類公文開頭的「欄位標籤」:這些行一定是獨立段落,不可與下一行黏在一起
_LABEL_RE = re.compile(
    r"^\s*(?:主題|主旨|標題|事項|致|由|日期|生效日期|發出日期|截止日期|檔號|檔案編號"
    r"|通告編號|通函編號|編號|參考編號|查詢|查詢電話|電話|傳真|電郵|網址|附件"
    r"|敬啟者|各位|承辦|對象|名額|費用|地點|時間|備註)\s*[:：]"
)


def _is_table_row(text: str, n_cells: int) -> bool:
    """看起來像表格的一列:多個框並排,或文字本身就含 | 分隔。"""
    return n_cells > 1 or text.count("|") >= 2 or "｜" in text


def _norm_pipes(text: str) -> str:
    """統一表格分隔:'a|b|c' / 'a ｜ b' → 'a | b | c'。"""
    text = text.replace("｜", "|")
    cells = [c.strip() for c in text.split("|")]
    return " | ".join(c for c in cells if c)


def _lines_to_text(lines: list[tuple[float, float, float, float, str]]) -> str:
    """
    把 OCR 的 (x0,y0,x1,y1,text) 依版面還原成段落。

    1. 先按 y 分「列」(同一水平線上的多個框 → 同一列,用 | 分隔,表格常見)
    2. 再按垂直間距分「段落」
    3. 段落內把折行接回去
    """
    if not lines:
        return ""

    lines = [
        l for l in lines
        if l[4] and len(l[4].strip()) >= MIN_LINE_CHARS
        and not _NOISE_RE.match(l[4].strip())
    ]
    if not lines:
        return ""

    heights = [l[3] - l[1] for l in lines if l[3] > l[1]]
    med_h = sorted(heights)[len(heights) // 2] if heights else 20.0

    # --- 依 y 聚成列
    lines.sort(key=lambda l: (l[1], l[0]))
    rows: list[list] = []
    for ln in lines:
        cy = (ln[1] + ln[3]) / 2
        placed = False
        for row in rows:
            rcy = sum((x[1] + x[3]) / 2 for x in row) / len(row)
            if abs(cy - rcy) < med_h * 0.6:
                row.append(ln)
                placed = True
                break
        if not placed:
            rows.append([ln])

    for row in rows:
        row.sort(key=lambda l: l[0])

    # --- 把列組成段落
    # 合併條件:垂直間距夠近、上一列不是句末標點、下一列不是清單標記
    marker = re.compile(
        r"^\s*(?:[0-9]{1,3}[.、)）]"
        r"|[（(][0-9一二三四五六七八九十]{1,3}[)）]"
        r"|[•·\-–—*]"
        r"|第[0-9一二三四五六七八九十百]+[章節條款部])"
    )
    stop_punct = "。！？；：.!?;:"

    # kind: "table"(表格列)/ "label"(欄位標籤)/ "text"(正文)
    blocks: list[list[list]] = []
    kinds: list[str] = []
    prev_bottom = None
    prev_text = ""
    prev_kind = ""
    for row in rows:
        top = min(x[1] for x in row)
        bottom = max(x[3] for x in row)
        row_text = " ".join(x[4].strip() for x in row).strip()

        # 先看是否公文表頭欄位(由／致／日期／檔號),再看是否表格列;
        # 否則「由 ｜ ：總俱樂部主席」這種兩格表頭會被誤判成表格
        if _LABEL_RE.match(row_text):
            kind = "label"
        elif _is_table_row(row_text, len(row)):
            kind = "table"
        else:
            kind = "text"

        new_block = True
        if prev_bottom is not None:
            gap = top - prev_bottom
            close = gap < med_h * 0.75
            prev_stop = bool(prev_text) and prev_text[-1] in stop_punct
            next_marker = bool(marker.match(row_text))

            if kind == "table":
                # 表格:每列獨立成行;只有連續表格列才歸同一塊
                new_block = not (prev_kind == "table" and close)
            elif kind == "label":
                # 「主題：xxx」這類標籤另起一段;但連續的由／致／日期要歸同一塊
                new_block = not (prev_kind == "label" and close and not prev_stop)
            elif prev_kind == "table":
                # 表格結束後的第一行正文,不要併進表格
                new_block = True
            else:
                new_block = not (close and not prev_stop and not next_marker)

        if new_block or not blocks:
            blocks.append([row])
            kinds.append(kind)
        else:
            blocks[-1].append(row)
        prev_bottom = bottom
        prev_text = row_text
        prev_kind = kind

    # --- 每段落內組成文字
    out_blocks: list[str] = []
    for block, kind in zip(blocks, kinds):
        if kind == "label":
            buf = "\n".join(
                re.sub(r"\s+([：:])", r"\1", " ".join(x[4].strip() for x in row))
                for row in block
            )
        elif kind == "table":
            # 表格:每一列各自一行,欄位之間用 | 保留關係
            lines = []
            for row in block:
                cells = [x[4].strip() for x in row]
                lines.append(_norm_pipes(" | ".join(c for c in cells if c)))
            buf = "\n".join(l for l in lines if l)
            if len(block) > 1:
                # 兩列以上 → 補上 Markdown 表格分隔線,讓它能被當成表格渲染
                parts = buf.split("\n")
                ncols = max(len(p.split("|")) for p in parts)
                sep = "| " + " | ".join(["---"] * ncols) + " |"
                buf = "\n".join([parts[0], sep] + parts[1:])
        else:
            buf = ""
            for row in block:
                cells = [x[4].strip() for x in row]
                cell = " | ".join(c for c in cells if c)
                buf = _join_wrapped(buf, cell) if buf else cell
        if buf.strip():
            out_blocks.append(buf.strip())
    return "\n\n".join(out_blocks)


def ocr_page_image(png: bytes) -> tuple[str, float]:
    """對一張 PNG(頁面點陣圖)做 OCR,回傳 (文字, 平均信心)。"""
    engine = _get_ocr()
    with _ocr_lock:  # onnxruntime session 連續推論較安全
        result, _elapse = engine(png)
    if not result:
        return "", 0.0

    boxes = []
    scores = []
    for item in result:
        box, text, score = item[0], item[1], item[2]
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        boxes.append((min(xs), min(ys), max(xs), max(ys), str(text)))
        scores.append(float(score))
    return _lines_to_text(boxes), (sum(scores) / len(scores) if scores else 0.0)


# ---------------------------------------------------------------- PDF 轉換


def pdf_to_markdown(path: str, ocr_mode: str = "auto", page_markers: bool = True,
                    glossary: dict | None = None):
    """回傳 (markdown, meta)。逐頁決定要不要 OCR。"""
    if ocr_mode not in OCR_MODES:
        ocr_mode = "auto"

    doc = _PdfDoc(path)
    page_count = doc.page_count
    pages_out: list[str] = []
    pages_ocr = 0
    pages_text = 0
    scores: list[float] = []
    warnings_out: list[str] = []

    try:
        for i, page in enumerate(doc, start=1):
            text = ""
            if ocr_mode != "always":
                text = page_text(page)

            need_ocr = ocr_mode == "always" or (
                ocr_mode == "auto" and len(text.strip()) < MIN_CHARS_PER_PAGE
            )

            used_ocr = False
            if need_ocr:
                try:
                    ocr_text, score = ocr_page_image(page_png(page, OCR_DPI))
                except Exception as e:  # noqa: BLE001
                    ocr_text, score = "", 0.0
                    warnings_out.append("第 %d 頁 OCR 失敗:%s: %s" % (i, type(e).__name__, e))
                if ocr_text.strip():
                    # 有文字層但偏少時,把 OCR 結果接在原文字後面,避免漏字
                    text = (text.strip() + "\n\n" + ocr_text) if text.strip() else ocr_text
                    pages_ocr += 1
                    used_ocr = True
                    scores.append(score)
                elif len(text.strip()) < MIN_CHARS_PER_PAGE:
                    warnings_out.append("第 %d 頁沒有文字層,OCR 也認不到內容(可能是純圖片、空白頁或解析度太低)。" % i)
            if text.strip():
                pages_text += 1 if not need_ocr else 0

            body = text.strip()
            if body:
                body = _to_hant(body)
                body = apply_glossary(body, glossary)
            if page_markers:
                head = ("<!-- p.%d ocr -->\n" % i) if used_ocr else ("<!-- p.%d -->\n" % i)
            else:
                head = ""
            pages_out.append(head + body if body else head + "_(本頁沒有可抽取的文字)_")
    finally:
        doc.close()

    md = "\n\n".join(pages_out).strip()
    meta = {
        "pages": page_count,
        "pages_ocr": pages_ocr,
        "ocr_avg_score": round(sum(scores) / len(scores), 3) if scores else None,
        "warnings": warnings_out,
    }
    if pages_ocr:
        meta["warnings"].append(
            "本檔有 %d 頁經 OCR 辨識;OCR 會有錯字(尤其繁體),重要內容請人工核對。"
            % pages_ocr
        )
    return md, meta


# ---------------------------------------------------------------- 其他格式


def markitdown_convert(path: str) -> str:
    from markitdown import MarkItDown

    md = MarkItDown()
    return md.convert(path).text_content or ""


IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def image_to_markdown(path: str, glossary: dict | None = None):
    text, score = ocr_page_image(image_png(path))
    text = apply_glossary(_to_hant(text), glossary)
    meta = {"pages": 1, "pages_ocr": 1 if text else 0,
            "ocr_avg_score": round(score, 3) if score else None,
            "warnings": []}
    if not text.strip():
        meta["warnings"].append("圖片 OCR 沒有認到文字。")
    return text, meta


# ---------------------------------------------------------------- 統一入口

TEXT_EXT = {
    ".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls", ".csv", ".tsv",
    ".html", ".htm", ".xml", ".json", ".txt", ".md", ".markdown",
    ".epub", ".msg", ".ipynb", ".rtf",
}
SUPPORTED_EXT = TEXT_EXT | IMAGE_EXT


def convert_path(path: str, filename: str, ocr_mode: str = "auto",
                 page_markers: bool = True, glossary: dict | None = None):
    """依副檔名選路線,回傳 (markdown, meta)。不拋例外以外的東西都由呼叫方處理。"""
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".pdf":
        return pdf_to_markdown(path, ocr_mode=ocr_mode,
                               page_markers=page_markers, glossary=glossary)

    if ext in IMAGE_EXT:
        md, meta = image_to_markdown(path, glossary=glossary)
        if page_markers and md.strip():
            md = "<!-- p.1 ocr -->\n" + md
        return md, meta

    if ext in TEXT_EXT:
        md = markitdown_convert(path)
        md = _to_hant(md)
        md = apply_glossary(md, glossary)
        return md, {"pages": None, "pages_ocr": 0, "ocr_avg_score": None, "warnings": []}

    raise ValueError("不支援的格式:%s" % (ext or "(無副檔名)"))
