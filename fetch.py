# -*- coding: utf-8 -*-
"""
抓取脚本：下载指定网站书籍的正文章节，存到 data 目录（断点续传）。

用法:
    python fetch.py            # 自动确定正文范围并抓取（可断点续传）
    python fetch.py --idx 5    # 只抓单章(调试)，如 5

网站结构与默认范围请改 config.py。
"""
import argparse
import json
import os
import random
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

import config

HEADERS = {"User-Agent": config.USER_AGENT}
HEADERS.update(config.EXTRA_HEADERS)

# 网页结构正则（来源于 config，换网站只需改 config.py）
CATALOG_LINK_RE = re.compile(config.CATALOG_LINK_ID_RE)
STORY_TITLE_RE = re.compile(config.STORY_TITLE_RE)

# 老站整页兜底解析时，清洗短小的导航行（上一章/目录/收藏本站…）
NAV_LINE_RE = re.compile(
    r"(上一[章回节]|下一[章回节]|章节目录|返回|首页|目录|书签|书架|全集下载|"
    r"下载本书|推荐票|登录|注册|收藏本站|请收藏|加入书架|报错|上一页|下一页|"
    r"更新时间|手机阅读|手机版|朗诵|版权所有|书库|文学网|阅读网|回目录|"
    r"www\.|\.com|\.cn|\.net|章节内容|最新章节)")


def strip_dup_heading(paras, title):
    """去掉与章标题重复的段落行。

    老站正文常重复回目行：页内写「第一回」，目录写「第001回」，
    数字写法不同 → 去掉"第X回"前缀并抹平空白后再比较。
    """
    if not title:
        return paras

    def norm(s):
        s = re.sub(r"^第[0-9一二三四五六七八九十百千零两]+[回章][\u3000 ]*", "", s or "")
        return re.sub(r"\s+", "", s)

    t_norm = norm(title)
    if not t_norm:
        return paras
    return [p for p in paras if norm(p) != t_norm]


def is_noise_line(line, title):
    """整页兜底模式下判断一行是否是导航/重复行。"""
    if not line or len(line) <= 1:
        return True
    if title and line == title:
        return True
    if len(line) <= 30 and NAV_LINE_RE.search(line):
        return True
    if line.startswith("http"):
        return True
    return False


def log(msg):
    print(msg, flush=True)


def get(url, session):
    """带重试的 GET。"""
    last_err = None
    for attempt in range(1, config.MAX_RETRY + 1):
        try:
            r = session.get(url, headers=HEADERS, timeout=config.REQUEST_TIMEOUT)
            if r.status_code == 200:
                if config.PAGE_ENCODING:
                    r.encoding = config.PAGE_ENCODING
                elif r.encoding is None or r.encoding.lower() in (
                        "iso-8859-1", "ascii", "windows-1252"):
                    # 老站不写 charset 时 requests 会错判成 latin-1 → 交给编码探测
                    r.encoding = r.apparent_encoding or "utf-8"
                return r
            last_err = "HTTP %s" % r.status_code
        except requests.RequestException as e:
            last_err = repr(e)
        log("  retry %d/%d for %s -> %s" % (attempt, config.MAX_RETRY, url, last_err))
        time.sleep(config.RETRY_BACKOFF * attempt)
    raise RuntimeError("fetch failed after retries: %s (%s)" % (url, last_err))


def load_catalog(session):
    """解析目录页：返回 [(idx, title, is_vip), ...] 升序。

    两种模式：
    - CATALOG_ITEM_SELECTOR 非空（固定行容器目录）：从容器里逐条取 <a>；
    - 为空（散链接目录）：通扫页面全部 <a>，用 CATALOG_LINK_ID_RE 从 href 提取章节号。
    """
    html_text = get(config.CATALOG_URL.format(bid=config.BOOK_ID), session).text
    soup = BeautifulSoup(html_text, "lxml")
    if config.CATALOG_ITEM_SELECTOR:
        nodes = soup.select(config.CATALOG_ITEM_SELECTOR)
    else:
        nodes = [a for a in soup.find_all("a", href=True)
                 if CATALOG_LINK_RE.search(a.get("href", "") or "")]
    entries, seen = [], set()
    for li in nodes:
        if config.CATALOG_LINK_SELECTOR:
            a = li.select_one(config.CATALOG_LINK_SELECTOR)
            if not a:
                continue
        else:
            a = li                         # 链接即条目本身（散链接模式）
        href = a.get("href", "") or ""
        m = CATALOG_LINK_RE.search(href)
        if not m:
            continue
        idx = int(m.group(1))
        if idx in seen:                    # 目录页可能有正序/倒序两份，去重
            continue
        seen.add(idx)
        if config.CATALOG_TITLE_SELECTOR:
            name_el = a.select_one(config.CATALOG_TITLE_SELECTOR)
            title = name_el.get_text(strip=True) if name_el else ""
        else:
            title = a.get_text(" ", strip=True)      # 标题即链接自身文本
        is_vip = (li.select_one(config.CATALOG_LOCK_SELECTOR) is not None
                  if config.CATALOG_LOCK_SELECTOR else False)
        entries.append((idx, title, is_vip))
    entries.sort()
    return entries


def pick_free_story(entries):
    """只挑【免费 + 标题以 第X章 开头】的正文，剔除公告/感言/VIP。"""
    picked = [e for e in entries
              if (not e[2]) and STORY_TITLE_RE.match(e[1])
              and not any(k in e[1] for k in config.SKIP_TITLE_KEYWORDS)]
    return picked


def parse_chapter(html_text):
    """从章节页提取 (标题, 段落列表)。返回 None 表示未取到正文。

    段落拆分两种模式：
    - CHAPTER_PARAGRAPH_TAG 非空：取该标签内文本；
    - 为空（老站整页兜底 / 无段落标签）：正文用 <br/> 换行，把 <br/> 换成换行符再按行切分。
    正文容器为空字符串时（老站无 id/class），对整页做兜底解析并清洗导航行。
    """
    soup = BeautifulSoup(html_text, "lxml")
    if config.CHAPTER_TITLE_SELECTOR:
        h1 = soup.select_one(config.CHAPTER_TITLE_SELECTOR)
        title = h1.get_text(strip=True) if h1 else ""
    else:
        # 空 = 自动取页面第一个非空标题标签
        h1 = next((el for el in soup.find_all(["h1", "h2", "h3", "h4"])
                   if el.get_text(strip=True)), None)
        title = h1.get_text(strip=True) if h1 else ""
    if config.CHAPTER_CONTENT_SELECTOR:
        art = soup.select_one(config.CHAPTER_CONTENT_SELECTOR)
    else:
        art = soup.body or soup          # 整页兜底：正文无 id/class 的老站
    if art is None:
        return None
    # 先剔除广告/导航/脚本等干扰节点
    for sel in config.CHAPTER_CLEAN_SELECTORS:
        for node in art.select(sel):
            node.decompose()
    if config.CHAPTER_PARAGRAPH_TAG:
        splitted = [p.get_text(strip=True)
                    for p in art.find_all(config.CHAPTER_PARAGRAPH_TAG)]
    else:
        for br in art.find_all("br"):        # <br/> -> 换行符
            br.replace_with("\n")
        splitted = [t.strip() for t in art.get_text().split("\n") if t.strip()]
    paras = [p for p in splitted if p and not is_noise_line(p, title)]
    paras = strip_dup_heading(paras, title)
    if not paras:
        return None
    return title, paras


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--idx", type=int, default=None,
                    help="只抓单章(调试)，如 5")
    args = ap.parse_args()

    os.makedirs(config.DATA_DIR, exist_ok=True)
    os.makedirs("debug", exist_ok=True)
    session = requests.Session()

    entries = load_catalog(session)
    log("catalog: total=%d" % len(entries))

    if args.idx is not None:
        want = [e for e in entries if e[0] == args.idx]
    elif config.RANGE is not None:
        want = [e for e in entries if e[0] in config.RANGE]
    else:
        want = pick_free_story(entries)
        log("free story chapters: %d (idx %d..%d)" % (
            len(want), want[0][0], want[-1][0]))

    ok, skipped, failed = 0, 0, 0
    for pos, (idx, ctitle, _) in enumerate(want, start=1):
        fpath = os.path.join(config.DATA_DIR, "%d.json" % idx)
        if os.path.exists(fpath):
            skipped += 1
            continue
        try:
            r = get(config.CHAPTER_URL.format(bid=config.BOOK_ID, idx=idx), session)
            parsed = parse_chapter(r.text)
            if parsed is None:
                raise RuntimeError("no content (may be VIP wall)")
            title, paras = parsed
            if not title:
                title = ctitle            # 老站章节页常无标题标签 → 用目录里的章名
            paras = strip_dup_heading(paras, title)   # 标题补全后再去一次重复回目行
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump({"idx": idx, "title": title, "paras": paras},
                          f, ensure_ascii=False, indent=1)
            ok += 1
            log("[%d/%d] saved idx=%d paras=%d" % (pos, len(want), idx, len(paras)))
        except Exception as e:
            failed += 1
            log("[%d/%d] FAILED idx=%d -> %r" % (pos, len(want), idx, e))
        if pos < len(want):                 # 请求间隔，礼貌限速
            time.sleep(random.uniform(config.MIN_DELAY, config.MAX_DELAY))

    log("done: ok=%d skipped=%d failed=%d" % (ok, skipped, failed))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
