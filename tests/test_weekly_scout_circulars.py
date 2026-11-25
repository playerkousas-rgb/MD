from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tools.weekly_scout_circulars import (
    CircularLink,
    build_index_url,
    build_markdown,
    crawl_category,
    find_existing,
    has_incomplete_issues,
    load_existing_knowledge,
    markdown_filename,
    parse_listing_page,
    render_report,
    verify_pdf,
)


def listing_page(page: int, last_page: int, filename: str | None = None) -> str:
    row = ""
    if filename:
        row = (
            "<table><tbody><tr><td>15/11/2026</td><td>"
            '<a href="/uploads/tc/circulars/test/%s">測試通告 %d</a>'
            "</td></tr></tbody></table>" % (filename, page)
        )
    pager = "".join(
        '<a href="?page=%d&amp;category=3&amp;type=Y">%d</a>' % (p, p)
        for p in range(1, min(last_page, 5) + 1)
    )
    if last_page > 5:
        pager += (
            '<a href="?page=%d&amp;category=3&amp;type=Y">下一頁&gt;</a>' % min(page + 1, last_page)
            + '<a href="?page=%d&amp;category=3&amp;type=Y">去最後一頁</a>' % last_page
        )
    return row + "<nav>" + pager + "</nav>"


class WeeklyScoutCircularTests(unittest.TestCase):
    def test_parse_pdf_and_pagination_links(self) -> None:
        url = build_index_url("3", 1)
        page = listing_page(1, 8, "P001-26.pdf")
        parsed = parse_listing_page(page, url, "3")
        self.assertEqual(parsed["page_numbers"], {1, 2, 3, 4, 5, 8})
        self.assertEqual(len(parsed["items"]), 1)
        self.assertEqual(parsed["items"][0].title, "測試通告 1")
        self.assertEqual(parsed["items"][0].listing_date, "2026-11-15")

    def test_crawler_discovers_pages_beyond_first_pager_window(self) -> None:
        calls: list[int] = []

        def fake_fetch(url: str) -> tuple[str, str]:
            page = int(parse_qs(urlsplit(url).query)["page"][0])
            calls.append(page)
            return listing_page(page, 8, "notice-%02d.pdf" % page), url

        with patch("tools.weekly_scout_circulars.time.sleep", return_value=None):
            result = crawl_category("3", page_fetcher=fake_fetch)

        self.assertEqual(result["pages_expected"], 8)
        self.assertEqual(result["pages_ok"], list(range(1, 9)))
        self.assertEqual(sorted(calls), list(range(1, 9)))
        self.assertEqual(len(result["items"]), 8)
        self.assertEqual(result["page_errors"], [])

    def test_crawler_follows_sliding_pagination_until_last_page(self) -> None:
        calls: list[int] = []

        def fake_fetch(url: str) -> tuple[str, str]:
            page = int(parse_qs(urlsplit(url).query)["page"][0])
            calls.append(page)
            # First page exposes only the next page. Each next page reveals one more.
            max_seen = min(page + 1, 4)
            anchors = "".join(
                '<a href="?page=%d&amp;category=4&amp;type=Y">%d</a>' % (p, p)
                for p in range(1, max_seen + 1)
            )
            if page == 1:
                anchors += '<a href="?page=2&amp;category=4&amp;type=Y">下一頁&gt;</a>'
            return (
                '<table><tr><td>01/01/2026</td><td><a href="/uploads/tc/circulars/a%d.pdf">項目</a></td></tr></table>'
                "<nav>%s</nav>" % (page, anchors),
                url,
            )

        with patch("tools.weekly_scout_circulars.time.sleep", return_value=None):
            result = crawl_category("4", page_fetcher=fake_fetch)

        self.assertEqual(result["pages_expected"], 4)
        self.assertEqual(sorted(calls), [1, 2, 3, 4])
        self.assertEqual(len(result["items"]), 4)

    def test_pdf_verification_rejects_html_and_missing_eof(self) -> None:
        valid = b"%PDF-1.7\n" + (b"x" * 1200) + b"\n%%EOF\n"
        self.assertTrue(verify_pdf(valid)[0])
        self.assertFalse(verify_pdf(b"<!doctype html>" + b" " * 2000)[0])
        self.assertFalse(verify_pdf(b"%PDF-1.7\n" + b"x" * 1200)[0])

    def test_existing_knowledge_matches_equivalent_zero_padded_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "knowledge"
            category = root / "03_政策及安全指引"
            category.mkdir(parents=True)
            (category / "P022-26.md").write_text(
                '---\nsource_file: "P022-26.pdf"\nsource_category: "03_政策及安全指引"\n---\n\n內容\n',
                encoding="utf-8",
            )
            known = load_existing_knowledge(root)
            item = CircularLink(
                "3", "https://www.scout.org.hk/uploads/tc/circulars/new/P22-26.pdf", "P22/2026"
            )
            found = find_existing(item, root, known)
            self.assertIsNotNone(found)
            self.assertEqual(found[1], "03_政策及安全指引/P022-26.md")
            self.assertEqual(markdown_filename(item.url), "P22-26.md")

    def test_markdown_front_matter_records_ocr_source_and_date(self) -> None:
        item = CircularLink(
            "4",
            "https://www.scout.org.hk/uploads/tc/circulars/test/AC01.pdf",
            '測試 "通告"',
            "2026-11-15",
        )
        text = build_markdown(
            item,
            "# 測試\n第 01/2026 號通告 2026 年 11 月 15 日\n",
            {"pages": 2, "pages_ocr": 1, "ocr_avg_score": 0.876, "layout": True},
            "a" * 64,
            "2026-11-25",
        )
        self.assertIn('source_category: "04_行政及領袖訓練"', text)
        self.assertIn('pages_ocr: 1', text)
        self.assertIn('ocr_avg_score: 0.876', text)
        self.assertIn('source_sha256: "' + "a" * 64 + '"', text)
        self.assertIn('notice_date: "2026-11-15"', text)
        self.assertIn('source_file: "AC01.pdf"', text)
        self.assertTrue(text.endswith("# 測試\n第 01/2026 號通告 2026 年 11 月 15 日\n"))

    def test_non_pdf_upload_is_reportable(self) -> None:
        url = build_index_url("5", 1)
        page = (
            '<table><tr><td>01/11/2026</td><td>'
            '<a href="/uploads/tc/circulars/notice.docx">表格附件</a>'
            "</td></tr></table>"
        )
        parsed = parse_listing_page(page, url, "5")
        self.assertEqual(parsed["items"], [])
        self.assertEqual(len(parsed["non_pdf_resources"]), 1)
        self.assertEqual(len(parsed["rows_without_pdf"]), 1)

    def test_report_marks_ocr_for_review_but_not_as_a_failed_scan(self) -> None:
        categories = {
            code: {
                "pages_expected": 1,
                "pages_ok": [1],
                "items": [],
                "page_errors": [],
                "rows_without_pdf": [],
                "non_pdf_resources": [],
                "parse_warnings": [],
                "catalog_duplicates": [],
            }
            for code in ("3", "4", "5")
        }
        report = {
            "started_at": "2026-11-25T02:17:00Z",
            "finished_at": "2026-11-25T02:18:00Z",
            "retrieved_date": "2026-11-25",
            "categories": categories,
            "discovered_count": 1,
            "catalog_duplicates": [],
            "already_present": [],
            "added": [{
                "title": "掃描測試通告",
                "path": "03_政策及安全指引/test.md",
                "url": "https://www.scout.org.hk/uploads/tc/circulars/test.pdf",
                "pages": 2,
                "pages_ocr": 1,
                "ocr_avg_score": 0.91,
                "warnings": [],
                "runtime": {"python": "3.11", "pdf_engine": "pymupdf", "pymupdf": "2.0",
                            "layout_available": True, "ocr_available": True},
            }],
            "failures": [],
            "rows_without_pdf": [],
            "non_pdf_resources": [],
            "parse_warnings": [],
            "runtime": {"python": "3.11", "pdf_engine": "pymupdf", "pymupdf": "2.0",
                         "layout_available": True, "ocr_available": True},
        }
        self.assertFalse(has_incomplete_issues(report))
        rendered = render_report(report)
        self.assertIn("OCR／轉換品質覆核", rendered)
        self.assertIn("OCR 1/2 頁", rendered)
        self.assertIn("掃描完成", rendered)

    def test_report_flags_a_failed_listing_page(self) -> None:
        report = {
            "categories": {
                "3": {"pages_expected": 2, "pages_ok": [1], "page_errors": [
                    {"page": 2, "url": "https://www.scout.org.hk/list?page=2", "error": "timeout"}
                ]},
                "4": {"pages_expected": 1, "pages_ok": [1], "page_errors": []},
                "5": {"pages_expected": 1, "pages_ok": [1], "page_errors": []},
            },
            "failures": [], "catalog_duplicates": [], "rows_without_pdf": [],
            "non_pdf_resources": [], "parse_warnings": [], "discovered_count": 1,
            "added": [], "already_present": [],
        }
        self.assertTrue(has_incomplete_issues(report))
        report.update({"started_at": "", "finished_at": "", "retrieved_date": ""})
        rendered = render_report(report)
        self.assertIn("目錄抓取", rendered)
        self.assertIn("timeout", rendered)


if __name__ == "__main__":
    unittest.main()
