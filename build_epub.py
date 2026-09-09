# -*- coding: utf-8 -*-
"""
打包脚本：把 data/chapters/*.json 合成为标准 EPUB。

用法:
    python build_epub.py
产出:
    output/<书名>_<后缀>.epub   （由 config.py 决定，如《三国演义》_全本.epub）
"""
import glob
import html
import json
import os

from ebooklib import epub

import config


def load_chapters():
    chapters = []
    for fpath in glob.glob(os.path.join(config.DATA_DIR, "*.json")):
        with open(fpath, encoding="utf-8") as f:
            ch = json.load(f)
        if any(k in ch["title"] for k in config.SKIP_TITLE_KEYWORDS):
            continue
        chapters.append(ch)
    chapters.sort(key=lambda c: c["idx"])
    return chapters


def build(chapters):
    book = epub.EpubBook()
    book.set_identifier(config.EPUB_IDENTIFIER)
    book.set_title(config.EPUB_TITLE)
    book.set_language(config.BOOK_LANG)
    book.add_author(config.BOOK_AUTHOR)

    items = []
    for ch in chapters:
        title = ch["title"]
        # 正文段落：每段一个 <p>；必须做 HTML 转义
        paras = "".join("<p>%s</p>" % html.escape(p) for p in ch["paras"])
        body = "<h1>%s</h1>\n%s" % (html.escape(title), paras)
        item = epub.EpubHtml(
            title=title,
            file_name="chap_%04d.xhtml" % ch["idx"],
            lang=config.BOOK_LANG,
        )
        item.content = body
        book.add_item(item)
        items.append(item)

    book.toc = items                      # 章节目录
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + items          # 阅读顺序
    return book


def main():
    chapters = load_chapters()
    if not chapters:
        raise SystemExit("no chapter json found under %s — run fetch.py first"
                         % config.DATA_DIR)
    print("chapters loaded: %d (%d..%d)" % (
        len(chapters), chapters[0]["idx"], chapters[-1]["idx"]))
    os.makedirs(os.path.dirname(config.OUTPUT_EPUB), exist_ok=True)
    book = build(chapters)
    epub.write_epub(config.OUTPUT_EPUB, book)
    size = os.path.getsize(config.OUTPUT_EPUB)
    print("EPUB saved:", config.OUTPUT_EPUB, "(%d bytes)" % size)


if __name__ == "__main__":
    main()
