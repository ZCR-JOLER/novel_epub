# -*- coding: utf-8 -*-
"""一键自动下载：给出目录页 URL，自动识别网站结构并抓全本 + 打包 EPUB。

用法:
    python auto.py <目录页URL> [--limit N] [--only-config]

流程:
    1. 抓目录页，自动识别章节链接（标题以「第X章 / Chapter N」开头）
       + 章节号提取规则 + 章节 URL 模板
    2. 抓第一章内容页，自动探测 标题节点 / 正文容器 / 段落方式
    3. 把探测结果重写进 config.py（旧文件自动备份为 config.py.bak）
    4. 调用 fetch.py 抓正文，再调用 build_epub.py 打包

示例:
    cd "F:/ZCR_code/project/爬小说EPUB项目/novel_epub"   # 或先 cd 到本仓库目录
    python auto.py http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html --limit 3
    python auto.py http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html
    python auto.py http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html --only-config

注意: 仅用于你有权获取的内容（公有领域作品 / 官方平台免费公开部分）；
     自动跳过 VIP 付费章；不对未授权转载站做抓取支持。
"""
import os
import re
import sys
import shutil
import subprocess
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

# ============ 常量 ============
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 20

# 章节标题探测正则：中文「第X章/第X回」(四大名著等章回体) / 英文「Chapter N / 12.」
ZH_STORY_RE = re.compile(r"^第[0-9一二三四五六七八九十百千零两]+[章回]")
EN_STORY_RE = re.compile(r"^(?:chapter\s*)?\d+(?:[.\s、:])", re.I)

# 导航/广告识别（用于排除非正文容器）
NAV_CLASS_RE = re.compile(r"(nav|menu|sidebar|header|footer|banner|ad(?!ap)|adv|comment|"
                          r"recommend|breadcrumb|login|search|hot|copy)", re.I)
NAV_TEXT_RE = re.compile(r"(首页|目录|书签|书架|推荐|登录|注册|排行|评论|返回|上一|下一|搜索)")
NOISE_TITLE = re.compile(r"(上一章|下一章|章节目录|返回|首页|目录|书签|书架|全集下载|下载|推荐票|登录|注册|上一页|下一页)")


def log(msg):
    print(msg, flush=True)


def http_get(url, referer=None):
    """GET 并自动纠正编码。"""
    headers = {"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9"}
    if referer:
        headers["Referer"] = referer
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError("HTTP %s for %s (也许需要额外请求头/登录？)" % (r.status_code, url))
    if r.encoding is None or r.encoding.lower() in ("iso-8859-1", "ascii", "windows-1252"):
        # 老站常不写 charset → requests 会错判成 latin-1；交给编码探测
        r.encoding = r.apparent_encoding or "utf-8"
    return r


def css_selector(node):
    """从 BeautifulSoup 节点生成 CSS 选择器：优先 #id，其次 tag.class。"""
    if not node or not getattr(node, "name", None):
        return None
    ids = node.get("id")
    if isinstance(ids, str) and ids.strip():
        return "#" + ids.split()[0]
    cls = node.get("class") or []
    if cls:
        return "%s.%s" % (node.name, ".".join(str(c) for c in cls[:2]))
    return None


def pick_num(href):
    """从章节链接 href 提取末尾数字（章节号），提取不到返回 None。"""
    m = re.search(r"(\d+)(?:\.\w+)?$", href.strip())
    return int(m.group(1)) if m else None


def to_template(url):
    """把章节链接 URL 转成 {idx} 模板；无法模板化（不含数字）返回 None。

    只替换最后一段「纯数字(+可选 .html 等后缀)」；如
    .../55138983.html  ->  .../{idx}.html
    .../read/12        ->  .../read/{idx}
    .../001.htm        ->  .../{idx:03d}.htm   （保留前导补零，抓取时按位数回填）
    """
    u = url.strip()
    m = re.search(r"(?<![0-9a-zA-Z])(\d+)(\.\w+)?$", u)
    if not m:
        return None
    digits = m.group(1)
    if len(digits) > 1 and digits.startswith("0"):     # 前导补零：001 → {idx:03d}
        return u[:m.start()] + "{idx:0%d}" % len(digits) + (m.group(2) or "")
    return u[:m.start()] + "{idx}" + (m.group(2) or "")


def detect_story_re(titles):
    """根据真实标题推断 STORY_TITLE_RE；识别不出返回 None。"""
    if not titles:
        return None
    zh = sum(1 for t in titles if ZH_STORY_RE.match(t))
    en = sum(1 for t in titles if EN_STORY_RE.match(t))
    if zh >= max(1, len(titles) * 0.5):
        return r"^第[0-9一二三四五六七八九十百千零两]+[章回]"
    if en >= max(1, len(titles) * 0.5):
        return r"^(?:chapter\s*)?\d+(?:[.\s、:])?"
    return None


def detect_spa_shell(html, soup):
    """判断页面是否为 JS 动态渲染的空壳页（SPA 单页应用）。

    此类站点服务器对任何网址都返回同一个 index.html，正文由浏览器 JS
    从后台接口(常为加密 JSON)拉取后渲染 —— requests + BeautifulSoup
    抓不到任何章节链接/正文。返回 (是否壳页, [特征列表])。
    """
    hints = []
    # 1) 前端 hash 路由：href 形如 "#/..." 或 "...#/..."（浏览器端跳转，不发请求给服务器）
    if re.search(r'href=["\'][^"\']*#/', html) or html.count("/#/") >= 2:
        hints.append("链接带 #/（前端路由，请求不会发给服务器）")
    # 2) 常见 SPA 挂载点：内容都渲染在 id=app / __nuxt / root 里
    if re.search(r'id=["\'](?:app|__nuxt|root)["\']', html, re.I):
        hints.append("存在 SPA 挂载点 (id=app/__nuxt/root)")
    # 3) 页面文本几乎全是 <a> 导航文字 → 服务端基本没返回可读正文
    links = soup.find_all("a")
    a_text = sum(len(a.get_text(" ", strip=True)) for a in links)
    body_text = soup.get_text(" ", strip=True)
    if a_text and body_text and a_text / len(body_text) > 0.7:
        hints.append("页面文本几乎全是导航链接，无可读正文")
    # 4) 引用打包后的 JS bundle（现代前端项目特征）
    if re.search(r'<script[^>]+src=["\'][^"\']*(?:static/js|/app\.|chunk)[^"\']*\.js',
                 html, re.I):
        hints.append("引用打包后的 JS bundle")
    return len(hints) >= 2, hints


def detect_container_mode(anchors, soup):
    """探测「行容器」型目录（官方站点常见，如 QQ阅读）：每章套在一个 <li>/<dd>/<tr> 里，
    内含 <a> 链接、标题子元素（如 span.name）、VIP 行还带锁图标（如 i.lock）。

    返回 (item_selector, link_selector, title_selector, lock_selector)；
    不属于此形态时返回 4 个空串（= 走"通扫全部 <a>"的散链接模式）。
    """
    if not anchors:
        return "", "", "", ""
    # 1) 找章节链接的公共行容器（只比较实际抽样数量）
    sampled = anchors[:150]
    rows = {}
    for nd in sampled:
        p = nd.find_parent(["li", "dd", "tr"])
        if p is None:
            continue
        sel = css_selector(p)
        if sel:
            rows[sel] = rows.get(sel, 0) + 1
    if not rows:
        return "", "", "", ""
    item_sel = max(rows, key=rows.get)
    if rows[item_sel] < max(10, int(len(sampled) * 0.5)):
        return "", "", "", ""
    # 2) 标题子元素：锚内第一个有文本的 span/em/b（如 span.name）
    title_sel = ""
    for sp in anchors[0].find_all(["span", "em", "b", "strong"]):
        if sp.get_text(strip=True):
            title_sel = css_selector(sp) or ""
            break
    # 3) VIP 锁图标：行内 i/span/em/s/b 等，class 含 lock/vip 字样
    locks = {}
    for row in soup.select(item_sel)[:600]:
        for node in row.find_all(["i", "span", "em", "s", "b"]):
            cls = " ".join(str(c) for c in (node.get("class") or []))
            if re.search(r"(?:^|[\s_-])(?:lock|vip)(?:[\s_-]|$)", cls, re.I):
                s2 = css_selector(node)
                if s2:
                    locks[s2] = locks.get(s2, 0) + 1
                break          # 每行至多认一个锁图标，提高速度
    lock_sel = max(locks, key=locks.get) if locks else ""
    return item_sel, "a", title_sel, lock_sel


def probe_catalog(url):
    """抓目录页：识别章节链接 → [(idx, abs_url, title)] + URL 模板 + 标题正则。"""
    log("==> 第1步 抓目录页: %s" % url)
    r = http_get(url, referer=url)
    soup = BeautifulSoup(r.text, "lxml")

    raw = []
    for a in soup.find_all("a", href=True):
        href0 = a.get("href", "").strip()
        txt = a.get_text(" ", strip=True)
        if not href0 or href0.startswith(("#", "javascript:", "mailto:")):
            continue
        if not txt or len(txt) > 40 or NOISE_TITLE.search(txt):
            continue
        raw.append((a, urljoin(url, href0), href0, txt))

    # 优先取标题以「第X章 / Chapter N」开头的链接；找不到再退而取全部短链接
    story = [(a, u, h, t) for a, u, h, t in raw
             if ZH_STORY_RE.match(t) or EN_STORY_RE.match(t)]
    chosen = story if story else raw

    entries, seen = [], set()
    for a, abs_url, href0, txt in chosen:
        n = pick_num(href0 or abs_url)
        if n is None or n in seen:
            continue
        seen.add(n)
        entries.append((n, abs_url, txt))

    # 目录形态探测：若每章套在 li/dd 行容器里（如 QQ阅读），识别行/链接/标题/VIP锁 选择器
    item_sel = link_sel = title_sel = lock_sel = ""
    if entries:
        nodes = [x[0] for x in chosen]
        item_sel, link_sel, title_sel, lock_sel = detect_container_mode(nodes, soup)
        if item_sel:
            log("    目录形态: 行容器=%s 链接=%s 标题=%s VIP锁=%s" % (
                item_sel, link_sel, title_sel, lock_sel or "(未发现=全免费)"))
    entries.sort()

    if not entries:
        spa, hints = detect_spa_shell(r.text, soup)
        if spa:
            raise RuntimeError(
                "该网址是「JS 动态渲染站点(SPA)」——服务器对所有网址都返回同一个空壳 HTML，"
                "章节与正文由浏览器里的 JS 从后台接口（往往是加密 JSON）拉取后渲染，"
                "所以 requests+BeautifulSoup 看不到任何章节链接。\n"
                "  壳页特征: %s\n"
                "auto.py 目前只支持「服务器直接把正文写在 HTML 里」的网站。可选方案：\n"
                "  1) 换成本书的官方/授权网站（正文直接写在 HTML 里的目录页），auto.py 即可用；\n"
                "  2) 提供你有权使用、且正文以明文 JSON 接口提供的站点，可以给 auto.py 增加 json-api 模式；\n"
                "  3) 对未授权转载站的混淆/加密接口做逆向解密，不属于本工具支持的用途。" % "；".join(hints))
        raise RuntimeError("没有从目录页发现任何带数字编号的章节链接，无法自动推断，"
                           "请手动填写 config.py")
    tpl = to_template(entries[0][1])
    story_re = detect_story_re([t for _, _, t in entries])
    if tpl is None or story_re is None:
        raise RuntimeError("目录链接形态无法自动识别（章节URL不含数字 或 标题非「第X章/Chapter」），"
                           "请手动填写 config.py")
    log("    识别出 %d 条章节链接，示例: %s → %s" % (len(entries), entries[0][1], entries[0][2]))
    log("    章节URL模板: %s" % tpl)
    return {"url": url, "entries": entries, "chapter_template": tpl,
            "story_re": story_re, "soup": soup,
            "item_sel": item_sel, "link_sel": link_sel,
            "title_sel": title_sel, "lock_sel": lock_sel}


def probe_title(soup):
    """探测章节标题节点：优先匹配「第X章/Chapter N」的标题标签。"""
    # 第一遍：标题含「第X章/Chapter N」，且该标题下确实有正文文本
    headings = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        t = el.get_text(" ", strip=True)
        if not t:
            continue
        headings.append((el, t))
    for el, t in headings:
        if ZH_STORY_RE.match(t) or EN_STORY_RE.match(t):
            return css_selector(el) or el.name, t
    # 第二遍：没有「第X章」标题，退而取页面第一个标题标签
    for el, t in headings:
        if len(t) >= 2:
            return css_selector(el) or el.name, t
    return None, None


def div_bad(div):
    """正文容器判定辅助：多个坏信号累加。返回 True 表示疑似导航/广告容器。"""
    cls = " ".join(str(c) for c in (div.get("class") or []))
    ident = " ".join(str(x) for x in div.get("id", "").split()) if div.get("id") else ""
    # 名为 content/article/book 等 class/id 直接放行
    good = re.search(r"(content|article|book|chapter|text|read|nr)", cls + " " + ident, re.I)
    if good:
        return False
    if NAV_CLASS_RE.search(cls + " " + ident):
        return True
    txt = div.get_text(" ", strip=True)
    if len(NAV_TEXT_RE.findall(txt)) >= 3:
        return True
    links = div.find_all("a", href=True)
    if len(links) > 0 and len(txt) > 0:
        link_txt = sum(len(a.get_text(strip=True)) for a in links)
        if link_txt / max(1, len(txt)) > 0.35:
            return True
    return False


def probe_content(soup):
    """探测正文容器：排除导航/广告 div，在“纯文本最多的候选”里挑 HTML 最短（最深）的叶子。

    这样外层壳 div（如整页阅读器 #bookRead）即使文本更多，也会让位于其内部真正的
    正文容器（如 #article）——对 QQ阅读 这类嵌套结构尤其重要。
    """
    cands = []
    for div in soup.find_all("div"):
        if not div.find(string=True):
            continue
        txt = div.get_text(" ", strip=True)
        if len(txt) < 120:
            continue
        if div_bad(div):
            continue
        # 收益：本容器贡献的纯文本（扣掉自身链接文字，避免外层“壳 div”得分虚高）
        link_txt = " ".join(a.get_text(strip=True) for a in div.find_all("a", href=True))
        pure = len(txt) - len(link_txt)
        if pure < 120:
            continue
        cands.append((pure, div, txt))
    if not cands:
        return None
    top_pure = max(c for c, _, _ in cands)
    top = [x for x in cands if x[0] >= top_pure * 0.75]
    top.sort(key=lambda x: len(str(x[1])))     # 叶子更小 → 排前面
    _, div, txt = top[0]
    return div, txt


def probe_chapter(chap_url, referer):
    """抓一个章节页，探测标题节点/正文容器/段落方式。"""
    log("==> 第2步 抓章节页(探测正文结构): %s" % chap_url)
    r = http_get(chap_url, referer=referer)
    soup = BeautifulSoup(r.text, "lxml")

    title_sel, title = probe_title(soup)
    found = probe_content(soup)
    if found is None:
        raise RuntimeError("章节页里没找到像正文的容器（文本都太短？）。"
                           "可能需要登录/付费墙，或页面是 JS 动态加载。")
    div, txt = found
    log("    标题节点: %s  例:「%s」" % (title_sel, (title or "")[:30]))
    content_sel = css_selector(div)
    if not content_sel:
        # 老站常见：正文 div 没有 id/class → 整页兜底：<br> 拆段 + 清洗导航行
        content_sel = ""
        whole = soup.body or soup
        p_cnt = len(whole.find_all("p"))
        br_cnt = len(whole.find_all("br"))
        para_tag = "p" if (p_cnt >= 3 and p_cnt >= br_cnt) else ""
        clean = ["script", "style"]
        log("    正文容器: (无 id/class，整页兜底) 文本 %d 字 | <p>×%d <br>×%d → 段落: %s" % (
            len(txt), p_cnt, br_cnt, para_tag or "<br/>拆分"))
    else:
        p_cnt = len(div.find_all("p"))
        br_cnt = len(div.find_all("br"))
        para_tag = "p" if (p_cnt >= 3 and p_cnt >= br_cnt) else ""
        # 收集正文容器内部残留的导航小 div（如「上一章/下一章」）供 fetch 清理。
        # 含大量正文的子节点（比如正文容器自身的后代 #article）绝不能进清理清单。
        inner_nav = []
        whole_txt_len = len(txt)
        for d in div.find_all(["div", "span"]):
            sel = css_selector(d)
            if not sel:
                continue
            if div_bad(d):
                continue
            dtxt = d.get_text(" ", strip=True)
            if len(dtxt) >= min(300, int(whole_txt_len * 0.6)):
                continue          # 文本量接近正文 → 是正文一部分，不清理
            if (len(d.find_all("a", href=True)) >= 4
                    or re.search(r"(上一|下一|目录|返回|导航)", dtxt)):
                inner_nav.append(sel)
        clean = ["script", "style"] + inner_nav
        log("    正文容器: %s  文本 %d 字 | <p>×%d <br>×%d → 段落方式: %s" % (
            content_sel, len(txt), p_cnt, br_cnt, para_tag or "<br/>拆分"))
    return {"title_selector": title_sel, "content_selector": content_sel,
            "para_tag": para_tag, "clean": clean}


def best_title_segment(t):
    """从 <title> 里挑书名：按分隔符切段，剔除站点词后，
    取“最长 / 含作品通名(演义传记志梦…) 加分”的一段。"""
    segs = [s.strip() for s in re.split(r"[_\|\-—·,，。、\u2014:：/]+", t) if s.strip()]
    junk = re.compile(r"(在线阅读|在线|朗诵|书库|文学|下载|列表|目录|最新章节|小说|书坊|"
                      r"官网|读书|阅读|小说网|电子书|免费|全文|论坛|手机版)")
    endword = re.compile(r"(演义|传|记|志|缘|梦|录|经|史|诗|赋|文|章|话|说|集)$")
    best, best_score = "", -1
    for s in segs:
        if not (2 <= len(s) <= 20) or junk.search(s):
            continue
        score = len(s) + (12 if endword.search(s) else 0)
        if score > best_score:
            best, best_score = s, score
    return best


def guess_meta(soup, url):
    """从目录页尽力猜测 书名/作者/书籍ID。"""
    title_tag = soup.find("title")
    t = title_tag.get_text(" ", strip=True) if title_tag else ""
    body = soup.get_text(" ", strip=True)
    book = ""

    def meta_content(keys):
        for m in soup.find_all("meta"):
            k = (m.get("property") or "") + " " + (m.get("name") or "")
            if any(kk in k for kk in keys) and m.get("content"):
                return m["content"].strip()
        return ""

    # 书名优先级：<h1> → og 元信息 → meta keywords 首词 → <title> 首段
    h1 = soup.find("h1")
    if h1:
        cand = h1.get_text(" ", strip=True)
        if cand and len(cand) <= 40 and not re.search(r"(目录|列表|章节目录|阅读页)", cand):
            book = cand
    if not book:
        book = meta_content(["og:novel:book_name", "og:title", "novel:book_name",
                             "og:book"])
    if not book:
        kw = meta_content(["keywords"])       # 老站常把书名写进 keywords 首词
        first = kw.split(",")[0].strip() if kw else ""
        if first and not re.search(r"(在线阅读|朗诵|书库|文学|小说|免费|首页|全集|下载)",
                                   first) and len(first) <= 24:
            book = first
    if not book:
        book = best_title_segment(t)
    if book:
        book = re.sub(r"[\(（].*?[\)）]", "", book).strip()
        book = re.sub(r"(最新章节|全文在线阅读|在线阅读|全部章节列表|小说在线阅读|目录|小说|_q+阅读|努努书坊)$",
                      "", book).strip()
    if not book:
        book = "unknown"
    # 作者：正文里「XX 著」最常见，其次「作者：XX」
    author = ""
    m = re.search(r"([^\s，,。:：<>]{2,15}?)\s*著", body)
    if m:
        author = m.group(1).strip()
    if not author:
        m = re.search(r"作\s*者[:：]?\s*([^\s，,。:：<>]{2,20})", body)
        if m:
            author = m.group(1).strip()
    if not author:
        author = "unknown"
    mu = re.search(r"/(\d+)/?$", url.strip("/"))
    book_id = mu.group(1) if mu else ""
    return book, author, book_id


def render_config(cfg):
    """把探测结果渲染成 config.py 文件内容。"""
    story_re = cfg["story_re"] or ZH_STORY_RE.pattern
    item_sel = cfg.get("item_sel") or ""
    link_sel = cfg.get("link_sel") or ""
    title_sel = cfg.get("title_sel") or ""
    lock_sel = cfg.get("lock_sel") or ""
    has_vip = bool(lock_sel)              # 探测到 VIP 锁 → 只抓未上锁的免费公开章
    suffix = "免费公开章节" if has_vip else "全本"
    limit = cfg.get("limit")
    if limit and cfg["entries"]:
        pre = [e[0] for e in cfg["entries"][:limit]]
        range_line = "RANGE = %s   # auto.py --limit %d （只抓前 %d 章试水）" % (
            pre, limit, limit)
    else:
        range_line = "RANGE = None   # None = 自动筛选正文（免费章或全部正文，视锁标记）"

    L = []
    L.append("# -*- coding: utf-8 -*-")
    L.append("# ===== 本文件由 auto.py 自动生成（旧版本已备份为 config.py.bak）=====")
    L.append("# 源目录 URL: %s" % cfg["url"])
    L.append("# 自动识别: 章节链接 %d 条 | 章节URL模板 %s" % (
        len(cfg["entries"]), cfg["chapter_template"]))
    L.append("")
    L.append("# 书籍信息")
    L.append('BOOK_TITLE = "%s"' % cfg["book"])
    L.append('BOOK_AUTHOR = "%s"' % cfg["author"])
    L.append('BOOK_ID = "%s"' % cfg["book_id"])
    L.append('BOOK_LANG = "zh-CN"')
    L.append('EPUB_TITLE = "%s（%s）"' % (cfg["book"], suffix))
    L.append('EPUB_IDENTIFIER = "auto-%s-%s"' % (cfg["host"], cfg["book_id"]))
    L.append("")
    L.append("# 网页地址模板")
    L.append('CATALOG_URL = "%s"' % cfg["url"])
    L.append('CHAPTER_URL = "%s"' % cfg["chapter_template"])
    L.append("")
    L.append("# 网页结构（auto.py 探测结果）")
    if item_sel:
        L.append("# 行容器目录型（如 QQ阅读）：每章一个行元素，行内 <a> + 标题子元素 + 可选 VIP 锁")
        L.append('CATALOG_ITEM_SELECTOR = "%s"' % item_sel)
        L.append('CATALOG_LINK_SELECTOR = "%s"' % link_sel)
        L.append('CATALOG_TITLE_SELECTOR = "%s"' % title_sel)
        L.append('CATALOG_LOCK_SELECTOR = "%s"' % lock_sel)
    else:
        L.append("# 散链接目录型：空选择器 = 通扫全部 <a> 后按正则提编号")
        L.append('CATALOG_ITEM_SELECTOR = ""')
        L.append('CATALOG_LINK_SELECTOR = ""')
        L.append('CATALOG_TITLE_SELECTOR = ""')
        L.append('CATALOG_LOCK_SELECTOR = ""   # 未探测到 VIP 锁标记')
    L.append('CATALOG_LINK_ID_RE = r"(\\d+)(?:\\.html?)?$"   # 从链接 href 提取章节编号')
    L.append('CHAPTER_TITLE_SELECTOR = "%s"' % (cfg.get("title_selector") or ""))
    L.append('CHAPTER_CONTENT_SELECTOR = "%s"' % cfg["content_selector"])
    L.append('CHAPTER_PARAGRAPH_TAG = "%s"  # 空 = 正文用 <br/> 换行拆分' % cfg["para_tag"])
    clean_items = [s for s in cfg.get("clean", []) or []]
    L.append('CHAPTER_CLEAN_SELECTORS = %s   # 正文容器内导航/广告节点，解析前删除'
             % ("(" + ",".join('"%s"' % s for s in clean_items) + ")"))
    L.append('STORY_TITLE_RE = r"%s"' % story_re)
    L.append('SKIP_TITLE_KEYWORDS = ("上架感言",)   # 标题含以下词即排除')
    L.append("")
    L.append("# 抓取范围")
    L.append(range_line)
    L.append("")
    L.append("# 行为控制")
    L.append('USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "')
    L.append('              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")')
    L.append('EXTRA_HEADERS = {"Accept-Language": "zh-CN,zh;q=0.9", "Referer": "%s"}' % cfg["url"])
    L.append('PAGE_ENCODING = None   # None = 交给 requests 自动判断')
    L.append("REQUEST_TIMEOUT = 20")
    L.append("MIN_DELAY, MAX_DELAY = 1.5, 3.0")
    L.append("MAX_RETRY = 3")
    L.append("RETRY_BACKOFF = 5")
    L.append("")
    L.append("# 本地路径")
    L.append('DATA_DIR = "data/%s_%s"' % (cfg["host"], cfg["book_id"]))
    L.append('OUTPUT_EPUB = "output/%s_%s.epub"' % (cfg["book"], suffix))
    return "\n".join(L) + "\n"


def main():
    args = list(sys.argv[1:])
    only_config = False
    if "--only-config" in args:
        only_config = True
        args.remove("--only-config")
    limit = None
    if "--limit" in args:
        i = args.index("--limit")
        limit = int(args[i + 1])
        del args[i:i + 2]
    url = args[0] if args else input("请输入目录页网址: ").strip()
    if not url:
        print("没有网址，退出。")
        return
    # 中文路径 URL 先百分号编码（请求头 Referer 只接受 ASCII）
    url = quote(url, safe=":/?&=#%+")

    ROOT = os.path.dirname(os.path.abspath(__file__))
    os.chdir(ROOT)            # 保证之后 fetch.py/build_epub.py 能 import config
    log("")

    # 1) 目录页探测
    cat = probe_catalog(url)

    # 2) 章节页探测：第 1 章可能是过短的引言/公告页，往后多试几章直到找到像正文的容器
    first = cat["entries"][0]
    chap = None
    for cand in cat["entries"][:6]:
        try:
            chap = probe_chapter(cand[1], referer=url)
            log("    采用章节示例: idx=%s (%s)" % (cand[0], cand[2][:30]))
            break
        except RuntimeError as e:
            log("    [跳过试例] idx=%s 探测失败 → %s" % (cand[0], str(e).splitlines()[0]))
    if chap is None:
        raise RuntimeError("连续几个章节都无法探测到正文容器，请人工检查该站结构或改手动配置 config.py")

    # 3) 元信息
    book, author, book_id = guess_meta(cat["soup"], url)
    host = re.sub(r"^https?://", "", url).split("/")[0]
    cfg = dict(cat)
    cfg.update(chap)
    cfg.update({"book": book, "author": author, "book_id": book_id,
                "host": host, "limit": limit})

    # 4) 打印摘要
    log("")
    log("===== 自动探测摘要 =====")
    log("书名     : %s" % book)
    log("作者     : %s" % author)
    log("书籍编号 : %s " % book_id)
    log("章节点   : %s / 正文容器: %s / 段落: %s" % (
        chap["title_selector"], chap["content_selector"],
        chap["para_tag"] or "<br/>拆分"))
    log("章节数   : 识别 %d 条（示例: %s | %s）" % (
        len(cat["entries"]), first[1], first[2]))

    # 5) 备份并重写 config.py
    cfg_path = os.path.join(ROOT, "config.py")
    if os.path.exists(cfg_path):
        shutil.copy(cfg_path, cfg_path + ".bak")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(render_config(cfg))
    log("已重写 config.py （旧文件备份为 config.py.bak）")

    if only_config:
        log("--only-config：接下来请手动运行:")
        log("  python fetch.py")
        log("  python build_epub.py")
        return

    # 6) 自动抓取 + 打包
    log("")
    log("==> 第3步 运行 fetch.py 抓取正文（已抓过的自动跳过）...")
    code = subprocess.call([sys.executable, "fetch.py"], cwd=ROOT)
    if code != 0:
        log("[注意] fetch.py 返回非零：有章节抓取失败，可重跑续传。")
    log("")
    log("==> 第4步 运行 build_epub.py 打包 EPUB ...")
    subprocess.call([sys.executable, "build_epub.py"], cwd=ROOT)
    log("")
    log("全部完成！EPUB 输出路径见 config.py 的 OUTPUT_EPUB")
    if limit:
        log("提示：本次是 --limit %d 试水（只抓前 %d 章）。正式全本请去掉 --limit 再运行：" % (limit, limit))
        log("  python auto.py %s" % url)


if __name__ == "__main__":
    main()