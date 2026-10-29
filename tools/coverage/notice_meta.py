#!/usr/bin/env python3
"""從通告正文抽取類型／編號／日期。給 migrate_into_knowledge.py 與 refresh_front_matter.py 共用。"""
from __future__ import annotations
import re
import unicodedata

# 第 92/2011 號、第 **30/2026** 號、第 03⁄2021號、`第` 92/2011 `號`
CIRCRE = re.compile(r"第\s*[*_`]{0,3}\s*([0-9]{1,3})\s*[*_`]{0,3}\s*[/⁄∕]\s*[*_`]{0,3}\s*([0-9]{2,4})\s*[*_`]{0,3}\s*號")
DATE_SEP = r"\s*[*_`]{0,3}\s*"
DATEREC = re.compile(r"(?<![0-9])(19|20)(\d{2})" + DATE_SEP + r"年" + DATE_SEP +
                     r"(\d{1,2})" + DATE_SEP + r"月" + DATE_SEP + r"(\d{1,2})" + DATE_SEP + r"日")
TYPES = ["青少年活動通告", "資助計劃通告", "訓練通告", "政策通告", "行政通告",
         "活動指引", "國際通告", "童軍通告", "通告"]


def extract_meta(text: str, window: int = 2500) -> dict:
    head = unicodedata.normalize("NFKC", text[:window])
    out: dict[str, str] = {}

    m = CIRCRE.search(head)
    if m:
        no, yr = m.group(1), m.group(2)
        year = yr if len(yr) == 4 else "20" + yr
        out["notice_no"] = f"{int(no):02d}/{year}"
        out["_pos"] = m.start()
        ctx = head[max(0, m.start() - 18): m.start()] + "|" + head[m.end(): m.end() + 14]
        for t in TYPES:
            if t in ctx:
                out["notice_type"] = t
                break

    dates = []
    for d in DATEREC.finditer(head):
        y, mo, dy = int(d.group(1) + d.group(2)), int(d.group(3)), int(d.group(4))
        if 1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= dy <= 31:
            dates.append((d.start(), y, mo, dy))
    if dates:
        pos = out.get("_pos")
        if pos is not None:
            # 取最接近通告編號的日期，避免抓到「本通告取代 20XX 年…」的舊日期
            best = min(dates, key=lambda x: abs(x[0] - pos))
        else:
            best = min(dates, key=lambda x: x[0])
        _, y, mo, dy = best
        out["notice_date"] = f"{y}-{mo:02d}-{dy:02d}"

    out.pop("_pos", None)
    return out


def junk_flag(text: str) -> bool:
    """開頭是否有明顯 OCR 雜訊（用來標示需要重新轉換）。"""
    head = text[:400]
    if "~~" in head or "\ufffd" in text:
        return True
    lat = len(re.findall(r"[A-Za-z]{2,}", head))
    cjk = len(re.findall(r"[\u4e00-\u9fff]", head))
    return lat > 6 and cjk < 15
