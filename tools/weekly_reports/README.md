# 每週總會通告掃描報告

這個目錄由 `.github/workflows/weekly-scout-circulars.yml` 自動更新。檔名為 `YYYY-MM-DD-scout-circulars.md`；相同 UTC 日期的手動重跑會更新當日報告，不會製造多份同日檔案。

掃描器每次即時讀取香港童軍總會官方目錄的類別 3（政策／指引）、4（行政）及 5（資助計劃），依目錄分頁連結逐頁抓取。新 PDF 經檔頭／檔尾驗證後，以 `markitdown-web/convert_core.py` 的 `auto` OCR 模式轉換；來源 PDF 留在暫存目錄，不提交 Git。只新增新文件，不覆寫既有 Markdown。

報告包含分頁完成狀態、已存在／重複項目、新收錄文件、下載／驗證／轉換失敗、目錄中沒有 PDF 的項目，以及新轉文件的 OCR 頁數和轉換警告。成功 OCR 的文件亦標示供人工抽查。若掃描未完成或有失敗，工作流程仍會先提交可取得的文件及報告，之後把該次 Actions 執行標示為失敗。
