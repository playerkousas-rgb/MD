#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每週掃描香港童軍總會通告目錄，下載新 PDF、轉成 Markdown 並留下覆核報告。

來源不是固定 manifest 或快照：每次直接讀取官方類別 3、4、5 的索引，
並從分頁連結動態找出、遍歷所有頁面。只新增知識庫尚未收錄的 PDF，不覆寫既有文件。

一般文字 PDF 由 PyMuPDF 抽取；呼叫共用 convert_core 的 ``ocr_mode="auto"``，
只在頁面文字不足時嘗試 RapidOCR。PDF 二進位檔留在暫存目錄，不進 Git。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
INDEX_BASE = "https://www.scout.org.hk/tc/circulars-forms/circulars/index.html"
INDEX_PATH = "/tc/circulars-forms/circulars/index.html"
ALLOWED_HOSTS = {"scout.org.hk", "www.scout.org.hk"}
USER_AGENT = "Mozilla/5.0 (compatible; ScoutKnowledgeUpdater/1.0; +https://www.scout.org.hk/)"
REQUEST_TIMEOUT = 60
REQUEST_RETRIES = 3
MAX_INDEX_BYTES = 24 * 1024 * 1024
MAX_PDF_BYTES = int(os.environ.get("SCOUT_MAX_PDF_BYTES", str(128 * 1024 * 1024)))
MAX_LISTING_PAGES = 1000

CATEGORIES = {
    "3": {"label": "政策／指引", "folder": "03_政策及安全指引"},
    "4": {"label": "行政", "folder": "04_行政及領袖訓練"},
    "5": {"label": "資助計劃", "folder": "05_資助計劃"},
}


@dataclass(frozen=True)
class CircularLink:
    category_id: str
    url: str
    title: str
    listing_date: str = ""

    @property
    def category_label(self) -> str:
        return CATEGORIES[self.category_id]["label"]

    @property
    def folder(self) -> str:
        return CATEGORIES[self.category_id]["folder"]

    @property
    def filename(self) -> str:
        return filename_from_url(self.url)


@dataclass
class ExistingKnowledge:
    urls: dict[str, str] = field(default_factory=dict)
    names: dict[str, str] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)
    paths: set[str] = field(default_factory=set)


class _ListingParser(HTMLParser):
    """只保留表格列、其內連結，以及列外分頁連結的輕量 HTML parser。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict] = []
        self.other_links: list[dict[str, str]] = []
        self.all_links: list[dict[str, str]] = []
        self._row: dict | None = None
        self._cell: list[str] | None = None
        self._anchor: dict | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = dict(attrs)
        if tag == "tr" and self._row is None:
            self._row = {"cells": [], "links": []}
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "a":
            self._anchor = {"href": attr.get("href") or "", "parts": []}

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
        if self._anchor is not None:
            self._anchor["parts"].append(data)

    @staticmethod
    def _clean(parts: list[str]) -> str:
        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a" and self._anchor is not None:
            link = {
                "href": str(self._anchor.get("href") or ""),
                "text": self._clean(self._anchor["parts"]),
            }
            self.all_links.append(link)
            if self._row is not None:
                self._row["links"].append(link)
            else:
                self.other_links.append(link)
            self._anchor = None
        elif tag in ("td", "th") and self._cell is not None:
            if self._row is not None:
                self._row["cells"].append(self._clean(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._cell is not None:
                self._row["cells"].append(self._clean(self._cell))
                self._cell = None
            self.rows.append(self._row)
            self._row = None

    def close(self) -> None:
        super().close()
        if self._row is not None:
            if self._cell is not None:
                self._row["cells"].append(self._clean(self._cell))
            self.rows.append(self._row)
            self._row = None


def _allowed_host(host: str | None) -> bool:
    return bool(host and host.lower().rstrip(".") in ALLOWED_HOSTS)


def _official_upload_suffix(url: str) -> str | None:
    parsed = urlsplit(url)
    if not _allowed_host(parsed.hostname):
        return None
    path = unquote(parsed.path)
    if not path.startswith("/uploads/tc/circulars/"):
        return None
    return Path(path).suffix.lower()


def canonical_url(url: str) -> str:
    """比較官方來源網址時忽略 www、query、fragment 和百分號編碼差異。"""
    parsed = urlsplit(url.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = unquote(parsed.path)
    return urlunsplit(("https", host, path, "", ""))


def _download_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit(("https", parsed.netloc, parsed.path, parsed.query, ""))


def filename_from_url(url: str) -> str:
    raw = unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    raw = unicodedata.normalize("NFC", raw).strip()
    raw = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", raw).rstrip(" .")
    if raw.lower().endswith(".pdf"):
        raw = raw[:-4]
    if not raw or raw in {".", ".."}:
        raw = "circular-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    # Keep ample room below common per-component filesystem limits.
    raw = raw[:180].rstrip(" .") or "circular"
    return raw + ".pdf"


def markdown_filename(url: str) -> str:
    return filename_from_url(url)[:-4] + ".md"


def normalize_name(name: str) -> str:
    """把官方檔名和 knowledge 檔名折疊成可比對別名（含前導零差異）。"""
    base = unquote(str(name).replace("\\", "/").rsplit("/", 1)[-1]).strip()
    if "." in base:
        base = base.rsplit(".", 1)[0]
    base = unicodedata.normalize("NFKC", base).casefold()
    base = re.sub(r"\d+", lambda m: str(int(m.group(0))), base)
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", base)


def build_index_url(category_id: str, page: int) -> str:
    if category_id not in CATEGORIES:
        raise ValueError("不支援的官方分類：%s" % category_id)
    params = [
        ("page", str(page)), ("t", ""), ("id", ""), ("year", ""),
        ("month", ""), ("category", category_id), ("type", "Y"),
        ("tag", ""), ("section", ""),
    ]
    return INDEX_BASE + "?" + urlencode(params)


def _listing_page_number(href: str, page_url: str, category_id: str) -> int | None:
    target = urljoin(page_url, href)
    parsed = urlsplit(target)
    if parsed.path.rstrip("/") != INDEX_PATH.rstrip("/"):
        return None
    if parsed.hostname and not _allowed_host(parsed.hostname):
        return None
    query = parse_qs(parsed.query, keep_blank_values=True)
    linked_category = query.get("category", [category_id])[0]
    linked_type = query.get("type", ["Y"])[0]
    if linked_category and linked_category != category_id:
        return None
    if linked_type and linked_type.upper() != "Y":
        return None
    for value in query.get("page", []):
        if value.isdigit() and int(value) >= 1:
            return int(value)
    return None


def _listing_date(text: str) -> str:
    match = re.search(r"(?<!\d)(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{4})(?!\d)", text)
    if not match:
        return ""
    day, month, year = map(int, match.groups())
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return ""


def parse_listing_page(html_text: str, page_url: str, category_id: str) -> dict:
    """抽出 PDF 項目、分頁編號、沒有 PDF 的通告列和非 PDF 附件。"""
    parser = _ListingParser()
    parser.feed(html_text)
    parser.close()

    page_numbers = {
        n for link in parser.all_links
        if (n := _listing_page_number(link.get("href", ""), page_url, category_id)) is not None
    }
    items_by_url: dict[str, CircularLink] = {}
    duplicate_items: list[dict[str, str]] = []
    rows_without_pdf: list[str] = []
    non_pdf_resources: list[dict[str, str]] = []

    row_links_seen: set[tuple[str, str]] = set()
    for row in parser.rows:
        cells = row.get("cells", [])
        links = row.get("links", [])
        row_text = " | ".join(c for c in cells if c)
        row_has_pdf = False
        for link in links:
            href = link.get("href", "").strip()
            if not href:
                continue
            absolute = urljoin(page_url, href)
            suffix = _official_upload_suffix(absolute)
            if suffix is None:
                continue
            safe_url = _download_url(absolute)
            row_links_seen.add((safe_url, link.get("text", "")))
            if suffix != ".pdf":
                non_pdf_resources.append({
                    "category_id": category_id,
                    "title": link.get("text") or row_text[:160] or filename_from_url(safe_url),
                    "url": safe_url,
                    "row": row_text[:240],
                })
                continue
            row_has_pdf = True
            title = link.get("text") or row_text or filename_from_url(safe_url)
            item = CircularLink(
                category_id=category_id,
                url=safe_url,
                title=title,
                listing_date=_listing_date(row_text),
            )
            key = canonical_url(safe_url)
            if key in items_by_url:
                duplicate_items.append({"title": title, "url": safe_url,
                                        "category_id": category_id,
                                        "first_title": items_by_url[key].title})
            else:
                items_by_url[key] = item

        # The official table's first column is an issue date. A date-bearing row
        # without an official PDF may mean the listing changed or has an omission.
        if not row_has_pdf and _listing_date(row_text):
            rows_without_pdf.append(row_text[:240] or "（日期列有值但無法讀取列內容）")

    # Also accept direct official PDF links outside <tr> markup. This is a
    # conservative fallback for a small HTML redesign, while keeping pagination
    # and non-circular links excluded by the official upload path check.
    for link in parser.other_links:
        href = link.get("href", "").strip()
        if not href:
            continue
        absolute = urljoin(page_url, href)
        suffix = _official_upload_suffix(absolute)
        if suffix is None:
            continue
        safe_url = _download_url(absolute)
        if suffix != ".pdf":
            non_pdf_resources.append({
                "category_id": category_id,
                "title": link.get("text") or filename_from_url(safe_url),
                "url": safe_url,
                "row": "",
            })
        elif (safe_url, link.get("text", "")) not in row_links_seen:
            items_by_url.setdefault(canonical_url(safe_url), CircularLink(
                category_id=category_id,
                url=safe_url,
                title=link.get("text") or filename_from_url(safe_url),
                listing_date="",
            ))

    pager_text = " ".join(link.get("text", "") for link in parser.all_links)
    pager_control = bool(re.search(r"下一頁|上一頁|最後一頁|next|last", pager_text, re.I))
    warnings: list[str] = []
    if pager_control and not page_numbers:
        warnings.append("頁面顯示分頁控制項，但 parser 找不到可用的 page 連結。")
    if not items_by_url and not parser.rows:
        warnings.append("頁面沒有可解析的表格列或通告 PDF 連結；可能是網站 HTML 改版或回應不完整。")

    return {
        "items": list(items_by_url.values()),
        "duplicate_items": duplicate_items,
        "page_numbers": page_numbers,
        "rows_without_pdf": rows_without_pdf,
        "non_pdf_resources": non_pdf_resources,
        "warnings": warnings,
        "row_count": len(parser.rows),
    }


def _read_response(url: str, accept: str, max_bytes: int) -> tuple[bytes, str, str]:
    request = Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Language": "zh-HK,zh-TW,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Referer": "https://www.scout.org.hk/",
    })
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        final_url = response.geturl()
        if not _allowed_host(urlsplit(final_url).hostname):
            raise RuntimeError("官方網址重新導向至非總會網域：%s" % final_url)
        data = bytearray()
        while True:
            chunk = response.read(min(64 * 1024, max_bytes + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > max_bytes:
                raise RuntimeError("回應超過大小上限（%d bytes）" % max_bytes)
        return bytes(data), final_url, response.headers.get("Content-Type", "")


def fetch_url(url: str, accept: str, max_bytes: int) -> tuple[bytes, str, str]:
    last_error = "未知網絡錯誤"
    for attempt in range(REQUEST_RETRIES):
        try:
            return _read_response(url, accept, max_bytes)
        except HTTPError as exc:
            last_error = "HTTP %s %s" % (exc.code, exc.reason)
            if exc.code not in (408, 425, 429) and exc.code < 500:
                break
        except (URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = "%s: %s" % (type(exc).__name__, exc)
            if "超過大小上限" in str(exc) or "重新導向至非總會網域" in str(exc):
                break
        if attempt + 1 < REQUEST_RETRIES:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(last_error)


def fetch_html(url: str) -> tuple[str, str]:
    data, final_url, content_type = fetch_url(
        url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5", MAX_INDEX_BYTES
    )
    charset_match = re.search(r"charset\s*=\s*['\"]?([\w.-]+)", content_type, re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        text = data.decode(charset, errors="replace")
    except LookupError:
        text = data.decode("utf-8", errors="replace")
    return text, final_url


def crawl_category(category_id: str, page_fetcher: Callable[[str], tuple[str, str]] = fetch_html) -> dict:
    """動態追蹤分頁連結；若 first page 只露出下一頁，也會逐頁走到最後。"""
    if category_id not in CATEGORIES:
        raise ValueError("不支援的官方分類：%s" % category_id)
    pending = deque([1])
    scheduled = {1}
    attempted: set[int] = set()
    pages_ok: list[int] = []
    page_errors: list[dict[str, str | int]] = []
    items_by_url: dict[str, CircularLink] = {}
    rows_without_pdf: list[dict[str, str | int]] = []
    non_pdf_resources: list[dict[str, str]] = []
    parse_warnings: list[dict[str, str | int]] = []
    catalog_duplicates: list[dict[str, str]] = []
    highest_page = 1

    while pending:
        page_number = pending.popleft()
        if page_number in attempted:
            continue
        attempted.add(page_number)
        page_url = build_index_url(category_id, page_number)
        try:
            page_html, final_url = page_fetcher(page_url)
            if not _allowed_host(urlsplit(final_url).hostname):
                raise RuntimeError("分頁回應位於非總會網域：%s" % final_url)
        except Exception as exc:  # 每一頁獨立記錄，不能讓單頁失敗中止整類掃描
            error = "%s: %s" % (type(exc).__name__, exc)
            print("[目錄 %s，第 %d 頁] 失敗：%s" % (category_id, page_number, error), flush=True)
            page_errors.append({
                "page": page_number,
                "url": page_url,
                "error": error,
            })
            continue

        parsed = parse_listing_page(page_html, final_url, category_id)
        print("[目錄 %s，第 %d 頁] OK；PDF 連結 %d；發現分頁 %s" % (
            category_id, page_number, len(parsed["items"]),
            ",".join(str(n) for n in sorted(parsed["page_numbers"])) or "無"), flush=True)
        pages_ok.append(page_number)
        for item in parsed["items"]:
            key = canonical_url(item.url)
            if key in items_by_url:
                catalog_duplicates.append({
                    "title": item.title, "url": item.url, "category_id": category_id,
                    "first_title": items_by_url[key].title,
                })
            else:
                items_by_url[key] = item
        rows_without_pdf.extend({"category_id": category_id, "page": page_number, "row": row}
                                for row in parsed["rows_without_pdf"])
        non_pdf_resources.extend(parsed["non_pdf_resources"])
        parse_warnings.extend({"category_id": category_id, "page": page_number, "warning": warning}
                              for warning in parsed["warnings"])
        catalog_duplicates.extend(parsed["duplicate_items"])

        if parsed["page_numbers"]:
            highest_page = max(highest_page, max(parsed["page_numbers"]))
        if highest_page > MAX_LISTING_PAGES:
            page_errors.append({
                "page": page_number,
                "url": page_url,
                "error": "官方分頁數 %d 超過保護上限 %d；停止擴展掃描。"
                         % (highest_page, MAX_LISTING_PAGES),
            })
            break
        # Enqueue every page up to the largest page observed. This handles both
        # a full numbered pager and the common sliding-window + last-page link.
        for candidate in range(1, highest_page + 1):
            if candidate not in scheduled:
                pending.append(candidate)
                scheduled.add(candidate)
        time.sleep(0.15)

    return {
        "category_id": category_id,
        "pages_expected": highest_page,
        "pages_ok": sorted(pages_ok),
        "page_errors": page_errors,
        "items": list(items_by_url.values()),
        "catalog_duplicates": catalog_duplicates,
        "rows_without_pdf": rows_without_pdf,
        "non_pdf_resources": non_pdf_resources,
        "parse_warnings": parse_warnings,
    }


def _yaml_value(value: str) -> str:
    # JSON double-quoted strings are valid YAML scalars and safely escape quotes/newlines.
    return json.dumps(str(value), ensure_ascii=False)


def _parse_yaml_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
            return str(decoded) if decoded is not None else ""
        except (json.JSONDecodeError, TypeError):
            return value.strip('"')
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def read_front_matter(path: Path) -> dict[str, str]:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            first = handle.readline().rstrip("\r\n")
            if first != "---":
                return {}
            values: dict[str, str] = {}
            for _ in range(160):
                line = handle.readline()
                if not line:
                    break
                line = line.rstrip("\r\n")
                if line.strip() == "---":
                    break
                match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
                if match:
                    values[match.group(1)] = _parse_yaml_scalar(match.group(2))
            return values
    except OSError:
        return {}


def load_existing_knowledge(knowledge_dir: Path) -> ExistingKnowledge:
    existing = ExistingKnowledge()
    if not knowledge_dir.is_dir():
        raise FileNotFoundError("知識庫目錄不存在：%s" % knowledge_dir)

    for path in knowledge_dir.rglob("*.md"):
        if not path.is_file():
            continue
        rel = path.relative_to(knowledge_dir).as_posix()
        existing.paths.add(rel)
        metadata = read_front_matter(path)
        source_url = metadata.get("source_url", "").strip()
        if source_url:
            existing.urls.setdefault(canonical_url(source_url), rel)
        for name in (path.name, metadata.get("source_file", "")):
            alias = normalize_name(name)
            if alias:
                existing.names.setdefault(alias, rel)
        source_sha = metadata.get("source_sha256", "").strip().lower()
        if re.fullmatch(r"[0-9a-f]{64}", source_sha):
            existing.hashes.setdefault(source_sha, rel)

    # The 79-item legacy index is not treated as a complete inventory, but its
    # PDF hashes are still useful duplicate hints when the referenced MD exists.
    legacy_index = knowledge_dir / "_index.json"
    if legacy_index.is_file():
        try:
            index = json.loads(legacy_index.read_text(encoding="utf-8"))
            for item in index.get("files", []):
                sha = str(item.get("sha256") or "").lower()
                md_file = str(item.get("md_file") or "").replace("\\", "/")
                if re.fullmatch(r"[0-9a-f]{64}", sha) and md_file in existing.paths:
                    existing.hashes.setdefault(sha, md_file)
        except (OSError, json.JSONDecodeError, AttributeError, TypeError):
            pass
    return existing


def find_existing(item: CircularLink, knowledge_dir: Path, existing: ExistingKnowledge) -> tuple[str, str] | None:
    source_url = canonical_url(item.url)
    if source_url in existing.urls:
        return "相同官方來源網址", existing.urls[source_url]
    alias = normalize_name(item.filename)
    if alias and alias in existing.names:
        return "相同／等價官方檔名", existing.names[alias]
    destination = knowledge_dir / item.folder / markdown_filename(item.url)
    if destination.exists():
        return "目標 Markdown 已存在（不覆寫）", destination.relative_to(knowledge_dir).as_posix()
    return None


def verify_pdf(data: bytes) -> tuple[bool, str]:
    if len(data) < 1024:
        return False, "PDF 回應小於 1 KiB，可能是不完整檔案或錯誤頁。"
    if b"%PDF-" not in data[:1024]:
        head = data[:500].lstrip().lower()
        if b"<html" in head or b"<!doctype" in head or b"<title" in head:
            return False, "伺服器回傳 HTML 頁面，不是 PDF。"
        if head.startswith((b"{", b"[")):
            return False, "伺服器回傳 JSON／資料回應，不是 PDF。"
        return False, "檔案開頭找不到 %PDF- 標記。"
    if b"%%EOF" not in data[-8192:]:
        return False, "檔尾找不到 %%EOF，PDF 可能未下載完整。"
    return True, "PDF 檔頭與結尾標記通過驗證。"


def _notice_meta(text: str) -> dict[str, str]:
    coverage_dir = str(ROOT / "tools" / "coverage")
    if coverage_dir not in sys.path:
        sys.path.insert(0, coverage_dir)
    try:
        from notice_meta import extract_meta  # type: ignore
        return extract_meta(text)
    except Exception:  # noqa: BLE001 - metadata parsing is helpful, not a conversion requirement
        return {}


def build_markdown(item: CircularLink, body: str, meta: dict, source_sha256: str,
                   retrieved_date: str) -> str:
    body = (body or "").replace("\r\n", "\n").strip()
    extracted = _notice_meta(body)
    lines = [
        "---",
        "source_file: %s" % _yaml_value(item.filename),
        "source_url: %s" % _yaml_value(item.url),
        "source_category: %s" % _yaml_value(item.folder),
        'source_format: "pdf"',
    ]
    if meta.get("pages"):
        lines.append("pages: %d" % int(meta["pages"]))
    pages_ocr = int(meta.get("pages_ocr") or 0)
    if pages_ocr:
        lines.append("pages_ocr: %d" % pages_ocr)
        score = meta.get("ocr_avg_score")
        if score is not None:
            lines.append("ocr_avg_score: %.3f" % float(score))
    lines += [
        "pipeline: %s" % ("pymupdf-layout" if meta.get("layout") else "pymupdf-text"),
        "ocr_engine: %s" % ("rapidocr" if pages_ocr else "none"),
        "source_sha256: %s" % _yaml_value(source_sha256),
        "retrieved_date: %s" % _yaml_value(retrieved_date),
    ]
    notice_no = extracted.get("notice_no")
    if notice_no:
        lines.append("notice_no: %s" % _yaml_value(notice_no))
    notice_date = item.listing_date or extracted.get("notice_date", "")
    if notice_date:
        lines.append("notice_date: %s" % _yaml_value(notice_date))
    if item.title:
        title = re.sub(r"\s+", " ", item.title).strip()
        if title:
            lines.append("title: %s" % _yaml_value(title))
    lines += ["---", "", body, ""]
    return "\n".join(lines)


def _load_converter():
    converter_dir = str(ROOT / "markitdown-web")
    if converter_dir not in sys.path:
        sys.path.insert(0, converter_dir)
    import convert_core  # type: ignore
    return convert_core


def _convert_pdf(data: bytes, item: CircularLink) -> tuple[str, dict, dict]:
    core = _load_converter()
    runtime = core.runtime_report()
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(prefix="scout-circular-", suffix=".pdf", delete=False) as temp:
            temp.write(data)
            temp_path = temp.name
        markdown, meta = core.convert_path(
            temp_path,
            item.filename,
            ocr_mode="auto",
            page_markers=True,
            glossary=core.DEFAULT_GLOSSARY,
            layout=True,
        )
        if not (markdown or "").strip():
            raise ValueError("轉換器沒有產生 Markdown 文字。")
        return markdown, meta or {}, runtime
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def _write_markdown(knowledge_dir: Path, item: CircularLink, content: str,
                    source_sha256: str) -> str:
    folder = knowledge_dir / item.folder
    folder.mkdir(parents=True, exist_ok=True)
    base = markdown_filename(item.url)
    destination = folder / base
    if destination.exists():
        stem = destination.stem
        destination = folder / ("%s_[%s].md" % (stem[:150], source_sha256[:8]))
        suffix = 2
        while destination.exists():
            destination = folder / ("%s_[%s_%d].md" % (stem[:145], source_sha256[:8], suffix))
            suffix += 1

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=folder,
            prefix="." + destination.name + ".", suffix=".tmp", delete=False,
        ) as temp:
            temp.write(content if content.endswith("\n") else content + "\n")
            temp_path = temp.name
        os.replace(temp_path, destination)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    return destination.relative_to(knowledge_dir).as_posix()


def _ocr_summary(record: dict) -> str:
    pages = record.get("pages")
    pages_ocr = int(record.get("pages_ocr") or 0)
    if pages_ocr:
        return "OCR %d/%s 頁" % (pages_ocr, pages if pages is not None else "?")
    return "無 OCR 頁"


def _make_issue(stage: str, message: str, item: CircularLink | None = None,
                url: str = "") -> dict[str, object]:
    return {
        "stage": stage,
        "message": message,
        "url": url or (item.url if item else ""),
        "title": item.title if item else "",
        "category_id": item.category_id if item else "",
    }


def _scan_item(item: CircularLink, knowledge_dir: Path, existing: ExistingKnowledge,
               retrieved_date: str, downloaded_hashes: dict[str, str]) -> tuple[dict | None, dict | None, dict | None]:
    """回傳 (新增文件、已存在／重複、失敗) 三者之一。"""
    prior = find_existing(item, knowledge_dir, existing)
    if prior:
        return None, {
            "title": item.title, "category_id": item.category_id,
            "filename": item.filename, "url": item.url,
            "path": prior[1], "reason": prior[0],
        }, None

    try:
        pdf_data, final_url, content_type = fetch_url(
            item.url, "application/pdf,application/octet-stream;q=0.9,*/*;q=0.5", MAX_PDF_BYTES
        )
    except Exception as exc:
        return None, None, _make_issue("下載", "%s: %s" % (type(exc).__name__, exc), item)

    valid, verification = verify_pdf(pdf_data)
    if not valid:
        return None, None, _make_issue("PDF 驗證", verification, item)
    source_sha256 = hashlib.sha256(pdf_data).hexdigest()
    if source_sha256 in existing.hashes:
        return None, {
            "title": item.title, "category_id": item.category_id,
            "filename": item.filename, "url": item.url,
            "path": existing.hashes[source_sha256],
            "reason": "PDF SHA-256 與已收錄文件相同",
        }, None
    if source_sha256 in downloaded_hashes:
        return None, {
            "title": item.title, "category_id": item.category_id,
            "filename": item.filename, "url": item.url,
            "path": downloaded_hashes[source_sha256],
            "reason": "PDF SHA-256 與本次另一項目相同",
        }, None

    runtime: dict = {}
    try:
        body, meta, runtime = _convert_pdf(pdf_data, item)
        content = build_markdown(item, body, meta, source_sha256, retrieved_date)
        rel_path = _write_markdown(knowledge_dir, item, content, source_sha256)
    except Exception as exc:
        issue = _make_issue("Markdown 轉換／寫入", "%s: %s" % (type(exc).__name__, exc), item)
        if not runtime:
            try:
                runtime = _load_converter().runtime_report()
            except Exception:  # noqa: BLE001
                runtime = {}
        if runtime:
            issue["runtime"] = runtime
        return None, None, issue

    downloaded_hashes[source_sha256] = rel_path
    existing.urls.setdefault(canonical_url(item.url), rel_path)
    alias = normalize_name(item.filename)
    if alias:
        existing.names.setdefault(alias, rel_path)
    existing.hashes.setdefault(source_sha256, rel_path)
    existing.paths.add(rel_path)
    warnings = [str(w) for w in (meta.get("warnings") or []) if str(w).strip()]
    result = {
        "title": item.title,
        "category_id": item.category_id,
        "filename": item.filename,
        "url": item.url,
        "path": rel_path,
        "sha256": source_sha256,
        "pages": meta.get("pages"),
        "pages_ocr": int(meta.get("pages_ocr") or 0),
        "ocr_avg_score": meta.get("ocr_avg_score"),
        "layout": bool(meta.get("layout")),
        "warnings": warnings,
        "runtime": runtime,
        "content_type": content_type,
        "final_url": final_url,
        "verification": verification,
    }
    return result, None, None


def _empty_category_result(category_id: str, error: str) -> dict:
    return {
        "category_id": category_id,
        "pages_expected": 1,
        "pages_ok": [],
        "page_errors": [{"page": 1, "url": build_index_url(category_id, 1), "error": error}],
        "items": [],
        "catalog_duplicates": [],
        "rows_without_pdf": [],
        "non_pdf_resources": [],
        "parse_warnings": [],
    }


def run_weekly_scan(knowledge_dir: Path | None = None) -> dict:
    started = datetime.now(timezone.utc)
    knowledge_dir = knowledge_dir or Path(os.environ.get("SCOUT_KNOWLEDGE_DIR", ROOT / "knowledge"))
    if not knowledge_dir.is_absolute():
        knowledge_dir = ROOT / knowledge_dir
    retrieved_date = started.date().isoformat()
    report: dict = {
        "started_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "finished_at": "",
        "retrieved_date": retrieved_date,
        "knowledge_dir": str(knowledge_dir),
        "categories": {},
        "discovered_count": 0,
        "catalog_duplicates": [],
        "already_present": [],
        "added": [],
        "failures": [],
        "rows_without_pdf": [],
        "non_pdf_resources": [],
        "parse_warnings": [],
        "runtime": None,
        "incomplete": False,
    }

    try:
        existing = load_existing_knowledge(knowledge_dir)
    except Exception as exc:
        existing = ExistingKnowledge()
        report["failures"].append(_make_issue("讀取知識庫", "%s: %s" % (type(exc).__name__, exc)))

    discovered_by_url: dict[str, CircularLink] = {}
    catalog_seen: dict[str, CircularLink] = {}
    for category_id in CATEGORIES:
        try:
            result = crawl_category(category_id)
        except Exception as exc:
            result = _empty_category_result(category_id, "%s: %s" % (type(exc).__name__, exc))
        report["categories"][category_id] = result
        report["rows_without_pdf"].extend(result["rows_without_pdf"])
        report["non_pdf_resources"].extend(result["non_pdf_resources"])
        report["parse_warnings"].extend(result["parse_warnings"])
        report["catalog_duplicates"].extend(result.get("catalog_duplicates", []))
        for item in result["items"]:
            key = canonical_url(item.url)
            if key in catalog_seen:
                first = catalog_seen[key]
                report["catalog_duplicates"].append({
                    "title": item.title,
                    "url": item.url,
                    "first_category_id": first.category_id,
                    "duplicate_category_id": item.category_id,
                })
                continue
            catalog_seen[key] = item
            discovered_by_url[key] = item

    report["discovered_count"] = len(discovered_by_url)
    items = list(discovered_by_url.values())
    print("官方目錄掃描完成：唯一 PDF %d 個；開始比對知識庫並處理新檔。" % len(items), flush=True)
    downloaded_hashes: dict[str, str] = {}
    for index, item in enumerate(items, 1):
        print("[PDF %d/%d] %s — %s" % (index, len(items), item.category_label, item.title), flush=True)
        added, duplicate, failure = _scan_item(
            item, knowledge_dir, existing, retrieved_date, downloaded_hashes
        )
        if added:
            report["added"].append(added)
            runtime = added.get("runtime") or {}
            if not report["runtime"]:
                report["runtime"] = runtime
            print("  新增：%s（%s）" % (added["path"], _ocr_summary(added)), flush=True)
        if duplicate:
            report["already_present"].append(duplicate)
            print("  已存在／重複：%s（%s）" % (duplicate.get("path", ""), duplicate.get("reason", "")), flush=True)
        if failure:
            report["failures"].append(failure)
            if not report["runtime"] and failure.get("runtime"):
                report["runtime"] = failure["runtime"]
            print("  失敗：%s — %s" % (failure.get("stage", ""), failure.get("message", "")), flush=True)

    report["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    report["incomplete"] = has_incomplete_issues(report)
    return report


def _normal_ocr_warning(warning: str) -> bool:
    return warning.startswith("本檔有 ") and " 頁經 OCR" in warning


def has_incomplete_issues(report: dict) -> bool:
    if report.get("failures"):
        return True
    if report.get("rows_without_pdf") or report.get("non_pdf_resources") or report.get("parse_warnings"):
        return True
    if not report.get("discovered_count"):
        return True
    for category in report.get("categories", {}).values():
        if category.get("page_errors"):
            return True
        if len(category.get("pages_ok", [])) < int(category.get("pages_expected", 1)):
            return True
    for item in report.get("added", []):
        if any(not _normal_ocr_warning(w) for w in item.get("warnings", [])):
            return True
        runtime = item.get("runtime") or {}
        if item.get("pages_ocr", 0) and not runtime.get("ocr_available", False):
            return True
    return False


def _inline(text: str) -> str:
    return "`" + str(text).replace("`", "\\`").replace("\n", " ") + "`"


def _url(url: str) -> str:
    return "<%s>" % url if url else "（無網址）"


def _category_summary(category_id: str, result: dict) -> str:
    expected = int(result.get("pages_expected", 0))
    ok = len(result.get("pages_ok", []))
    items = len(result.get("items", []))
    failures = len(result.get("page_errors", []))
    label = CATEGORIES[category_id]["label"]
    return "| %s | %d/%d | %d | %d |" % (label, ok, expected, items, failures)


def render_report(report: dict) -> str:
    issues = []
    if report.get("failures"):
        issues.extend(report["failures"])
    if report.get("rows_without_pdf"):
        for entry in report["rows_without_pdf"]:
            issues.append({"stage": "目錄列缺少 PDF", "message": entry.get("row", ""),
                           "url": build_index_url(str(entry.get("category_id", "3")), int(entry.get("page", 1)))})
    if report.get("non_pdf_resources"):
        for entry in report["non_pdf_resources"]:
            issues.append({"stage": "非 PDF 附件", "message": entry.get("title", "官方目錄附件不是 PDF"),
                           "url": entry.get("url", "")})
    if report.get("parse_warnings"):
        for entry in report["parse_warnings"]:
            issues.append({"stage": "頁面解析", "message": entry.get("warning", ""),
                           "url": build_index_url(str(entry.get("category_id", "3")), int(entry.get("page", 1)))})
    for category_id, category in report.get("categories", {}).items():
        for error in category.get("page_errors", []):
            issues.append({"stage": "目錄抓取", "message": error.get("error", ""), "url": error.get("url", "")})

    status = "⚠️ **本次掃描不完整；請檢視「可能漏抓／失敗」項目。**" if report.get("incomplete") else "✅ **掃描完成。**"
    lines = [
        "# 每週總會通告掃描報告",
        "",
        "- 執行時間（UTC）：%s 至 %s" % (report.get("started_at", ""), report.get("finished_at", "")),
        "- 官方來源：[總會通告目錄](%s)；掃描政策／指引、行政、資助計劃三類，逐頁追蹤目錄分頁。" % INDEX_BASE,
        "- 狀態：%s" % status,
        "- 發現 PDF 連結：%d；新增 Markdown：%d；已存在／重複：%d；下載／轉換失敗：%d；OCR 文件：%d。" % (
            report.get("discovered_count", 0), len(report.get("added", [])),
            len(report.get("already_present", [])) + len(report.get("catalog_duplicates", [])),
            len(report.get("failures", [])) + sum(len(c.get("page_errors", [])) for c in report.get("categories", {}).values()),
            sum(1 for item in report.get("added", []) if item.get("pages_ocr", 0)),
        ),
        "",
        "## 分類及分頁掃描",
        "",
        "| 分類 | 成功頁／發現頁 | 唯一 PDF 連結 | 抓取失敗頁 |",
        "|---|---:|---:|---:|",
    ]
    for category_id in CATEGORIES:
        lines.append(_category_summary(category_id, report.get("categories", {}).get(category_id, {})))
    lines += ["", "## 新收錄", ""]
    if report.get("added"):
        for item in report["added"]:
            details = ["%s 頁" % item["pages"] if item.get("pages") else "頁數未知",
                       _ocr_summary(item)]
            if item.get("ocr_avg_score") is not None:
                details.append("OCR 平均信心 %.3f" % float(item["ocr_avg_score"]))
            lines.append("- **%s** — %s（%s）；來源：%s" % (
                item.get("title") or item.get("filename", ""), _inline(item.get("path", "")),
                "；".join(details), _url(item.get("url", ""))))
    else:
        lines.append("- 本次沒有新文件。")

    lines += ["", "## 已存在／重複項目", ""]
    if report.get("already_present"):
        for item in report["already_present"]:
            label = CATEGORIES.get(item.get("category_id", ""), {}).get("label", "總會通告")
            lines.append("- **%s**（%s）— PDF %s → %s；%s；%s" % (
                item.get("title") or item.get("filename", ""), label,
                _inline(item.get("filename", "")), _inline(item.get("path", "")),
                item.get("reason", "已收錄"), _url(item.get("url", ""))))
    else:
        lines.append("- 無。")
    if report.get("catalog_duplicates"):
        for item in report["catalog_duplicates"]:
            category_id = item.get("category_id", "")
            first_id = item.get("first_category_id", category_id)
            duplicate_id = item.get("duplicate_category_id", category_id)
            first = CATEGORIES.get(first_id, {}).get("label", "總會通告")
            duplicate = CATEGORIES.get(duplicate_id, {}).get("label", "總會通告")
            lines.append("- 目錄重複連結：%s（首次列於%s、再次列於%s）— %s" % (
                item.get("title", ""), first, duplicate, _url(item.get("url", ""))))

    lines += ["", "## OCR／轉換品質覆核", ""]
    review_items = [item for item in report.get("added", [])
                    if item.get("pages_ocr", 0) or item.get("warnings")]
    if review_items:
        for item in review_items:
            lines.append("- **%s** — %s；%s" % (
                item.get("title") or item.get("filename", ""), _inline(item.get("path", "")),
                _ocr_summary(item)))
            for warning in item.get("warnings", []):
                lines.append("  - %s" % warning)
    else:
        lines.append("- 本次新轉換文件沒有 OCR 頁或轉換警告。")

    lines += ["", "## 可能漏抓／失敗", ""]
    if issues:
        for item in issues:
            category = CATEGORIES.get(item.get("category_id", ""), {}).get("label", "")
            prefix = ("[%s] " % category) if category else ""
            lines.append("- **%s**：%s%s%s" % (
                item.get("stage", "需追查"), prefix, item.get("message", ""),
                (" — " + _url(item.get("url", ""))) if item.get("url") else ""))
    else:
        lines.append("- 沒有發現目錄抓取、下載、PDF 驗證或轉換失敗。")

    lines += ["", "## 執行環境", ""]
    runtime = report.get("runtime")
    if runtime:
        lines.append("- Python %s；PDF 引擎：%s；PyMuPDF：%s；版面分析：%s；RapidOCR：%s。" % (
            runtime.get("python", "?"), runtime.get("pdf_engine", "?"),
            runtime.get("pymupdf", "?"), "可用" if runtime.get("layout_available") else "不可用",
            "可用" if runtime.get("ocr_available") else "不可用"))
    elif any("轉換" in item.get("stage", "") for item in report.get("failures", [])):
        lines.append("- 新 PDF 的轉換器未成功初始化；詳見上方失敗清單。")
    else:
        lines.append("- 本次沒有新 PDF 需要轉換，未初始化轉換器。")
    lines += ["", "> OCR 成功的頁面仍可能有辨識錯字；請覆核上列 OCR 文件。目錄頁抓取失敗或列出非 PDF 附件時，本報告會標示可能漏項。", ""]
    return "\n".join(lines)


def write_report(report: dict, report_dir: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    date = report.get("retrieved_date") or datetime.now(timezone.utc).date().isoformat()
    path = report_dir / (date + "-scout-circulars.md")
    content = render_report(report)
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=report_dir,
            prefix="." + path.name + ".", suffix=".tmp", delete=False,
        ) as temp:
            temp.write(content)
            temp_path = temp.name
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as summary:
            summary.write(content + "\n")
    return path


def main() -> int:
    try:
        report = run_weekly_scan()
    except Exception as exc:  # Keep a dated failure record even for an unexpected bug.
        now = datetime.now(timezone.utc)
        report = {
            "started_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "finished_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "retrieved_date": now.date().isoformat(),
            "categories": {code: _empty_category_result(code, "掃描器未能完成：" + str(exc))
                           for code in CATEGORIES},
            "discovered_count": 0,
            "catalog_duplicates": [],
            "already_present": [],
            "added": [],
            "failures": [_make_issue("程式執行", "%s: %s" % (type(exc).__name__, exc))],
            "rows_without_pdf": [],
            "non_pdf_resources": [],
            "parse_warnings": [],
            "runtime": None,
            "incomplete": True,
        }
    report_dir = Path(os.environ.get("SCOUT_WEEKLY_REPORT_DIR", ROOT / "tools" / "weekly_reports"))
    if not report_dir.is_absolute():
        report_dir = ROOT / report_dir
    try:
        report_path = write_report(report, report_dir)
        print("報告：%s" % report_path.relative_to(ROOT) if report_path.is_relative_to(ROOT) else "報告：%s" % report_path)
    except Exception as exc:
        print("無法寫入每週報告：%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1

    print("通告 PDF：%d；新增：%d；已存在／重複：%d；失敗：%d；不完整：%s" % (
        report.get("discovered_count", 0), len(report.get("added", [])),
        len(report.get("already_present", [])) + len(report.get("catalog_duplicates", [])),
        len(report.get("failures", [])) + sum(len(c.get("page_errors", [])) for c in report.get("categories", {}).values()),
        "是" if report.get("incomplete") else "否"))
    return 1 if report.get("incomplete") else 0


if __name__ == "__main__":
    raise SystemExit(main())
