# 📖 novel_epub — Turn a novel's table-of-contents URL into an EPUB in one command

[中文说明](README.md)

> Give the **table-of-contents URL** of a book you are **entitled to read/download**, and the tool detects the site layout, downloads the chapters, and packages them into a standard EPUB.

## 🚀 No-install Windows standalone exe (recommended)

**No Python required — just double-click.**

- **Download**: get `novel-epub-gui.exe` (~26 MB) from the **Releases** page of this repo.
  (Local dev builds also land in `dist\novel-epub-gui.exe`; binaries are not committed to the repo.)
- **Usage**: double-click → paste a table-of-contents URL → click “② 试水 (first 3 chapters)” → then “③ 全量抓取+打包”.
- **Outputs**: books & EPUBs are written **next to the exe** into `data\` and `output\`
  (needs write permission — don't place it under `C:\Program Files`).
- **Build it yourself** (if you want the latest code as an exe):

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name novel-epub-gui ^
    --collect-all ebooklib --hidden-import auto --hidden-import fetch ^
    --hidden-import build_epub --exclude-module config gui.py
```

Prefer running from source (Windows/macOS/Linux)? See [Install](#-install) and [Quick start](#-quick-start).

## ⚠️ Responsible-use notice (please read first)

This tool only supports content you have the right to obtain, with those limits enforced by design:

- ✅ Public-domain works (e.g. classic Chinese novels like *Romance of the Three Kingdoms*, *Journey to the West*)
- ✅ Content **freely and publicly readable** on official platforms (the tool detects VIP/paywall markers and only fetches chapters that are not locked)
- ⛔ It skips VIP / paid chapters — no scraping of paid content
- ⛔ No scraping support for unauthorized mirror sites (including obfuscated/encrypted ones): when it meets a JS-rendered SPA shell it prints a diagnosis and stops instead of trying to break protections
- 📦 This repository ships **no book content whatsoever** (`data/` and `output/` are local artifacts, excluded via `.gitignore`)

Use it only for content you are allowed to download, and take responsibility for your own usage.

## ✨ Features

- **Fully automatic**: give a table-of-contents URL → detect → write config → fetch → build EPUB
- **Adapts to many site shapes**:
  - Scattered-link catalogs (chapter links spread over the page)
  - Row-container catalogs (one `<li>/<dd>` per chapter, e.g. official reading platforms)
  - VIP lock detection → only free/public chapters are fetched
  - Chapter-title styles like `第X章` / `第X回`, zero-padded URLs (`001.htm`), GBK/GB18030 legacy encodings
  - Whole-page fallback parsing for legacy sites whose content has no id/class
  - JS-rendered (SPA) sites: diagnosed and refused gracefully
- **Resumable + polite rate limiting + retry with backoff**: re-run after an interruption to continue where it stopped
- Outputs a standard EPUB importable into WeRead / Kindle / most readers

## 📦 Install

Requires Python 3.8+ (developed and tested on 3.13).

```bash
pip install -r requirements.txt
```

## 🚀 Quick start

```bash
# 1. Dry run first: fetch only the first 3 chapters
python auto.py "TABLE_OF_CONTENTS_URL" --limit 3

# 2. Once verified, drop --limit to fetch everything and build the EPUB
python auto.py "TABLE_OF_CONTENTS_URL"
```

Working example (public domain, full book allowed):

```bash
# "Romance of the Three Kingdoms" (120 chapters)
python auto.py "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html" --limit 3
```

EPUBs are written to `output/`, chapter caches to `data/` (resumable).
`config.py` is generated automatically (git-ignored). To tweak a site by hand,
copy `config.example.py` to `config.py` and edit that.

> GUI users: there is a **fetch interval (ms)** box — leave it blank for the
> polite default (1500–3000 ms per chapter), type a number to force a fixed
> interval, and if you go below the 500 ms safety floor the app clamps to the
> fastest speed and shows *"已使用最大速度提取"* (fastest extraction in use).

### Options

| Option | Effect |
|---|---|
| `--limit N` | Fetch only the first N chapters as a dry run (recommended) |
| `--only-config` | Probe the site and write `config.py` only — no fetching/packing |

## 🗂 Repository layout

```
novel_epub/
├── README.md          # Chinese README
├── README_EN.md       # This file (English)
├── LICENSE            # MIT license
├── requirements.txt   # Dependencies
├── .gitignore
├── auto.py            # Entry: probe → generate config → fetch → build
├── fetch.py           # Downloader (resume / rate limit / retry)
├── build_epub.py      # EPUB packager
├── gui.py             # tkinter GUI (also the exe entry)
├── config.example.py  # Config template (config.py is auto-generated & git-ignored)
├── config.py          # Local, auto-written by auto.py/gui (ignored by git)
├── data/              # Local chapter cache (not committed)
└── output/            # Local EPUB output (not committed)
```

## 🔧 How it works

```
user provides a table-of-contents URL
   ↓ auto.py step 1: fetch catalog; detect chapter links / URL template / title rules / row containers / VIP locks
   ↓ step 2: fetch one chapter page; detect title node / content container / paragraph style / encoding
   ↓ step 3: write the detected structure into config.py (old config auto-backed-up as config.py.bak)
   ↓ step 4: fetch.py downloads chapters one by one (1.5–3 s delay, retries, resumable)
   ↓ step 5: build_epub.py packs a standard EPUB with TOC
```

To switch books, just run `auto.py` with another table-of-contents URL — no manual config editing needed.

## 🤔 FAQ

**Q: `can't open file '...auto.py'`?**
A: `cd` into this repository first, e.g. `cd "F:\ZCR_code\project\爬小说EPUB项目\novel_epub"`, or pass the full script path to `python`.

**Q: A site cannot be fetched?**
A: Read the error. If it says "JS-rendered site (SPA)", the text is not in the HTML or the site is an unauthorized mirror — per the responsible-use policy this tool will not break protections; switch to a source you are allowed to use.

**Q: How to fetch only some chapters?**
A: Set `RANGE` in `config.py` (e.g. `RANGE = [1,2,3]`) and run `python fetch.py`.

**Q: `config.py` keeps changing / shows as modified?**
A: Normal — it is rewritten on every run. It is git-ignored now; for manual
tuning copy `config.example.py` to `config.py`.

**Q: Author/title shown as `unknown`?**
A: Legacy sites often lack metadata; the tool tries `<h1>`/meta/`<title>`. You can fix it manually in `config.py` and re-run `python build_epub.py`.

## 📄 License

[MIT](LICENSE)
