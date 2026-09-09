# -*- coding: utf-8 -*-
# ===== 本文件由 auto.py 自动生成（旧版本已备份为 config.py.bak）=====
# 源目录 URL: http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html
# 自动识别: 章节链接 120 条 | 章节URL模板 http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/{idx:03}.htm

# 书籍信息
BOOK_TITLE = "三国演义"
BOOK_AUTHOR = "罗贯中"
BOOK_ID = ""
BOOK_LANG = "zh-CN"
EPUB_TITLE = "三国演义（全本）"
EPUB_IDENTIFIER = "auto-www.langsong.net-"

# 网页地址模板
CATALOG_URL = "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html"
CHAPTER_URL = "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/{idx:03}.htm"

# 网页结构（auto.py 探测结果）
# 散链接目录型：空选择器 = 通扫全部 <a> 后按正则提编号
CATALOG_ITEM_SELECTOR = ""
CATALOG_LINK_SELECTOR = ""
CATALOG_TITLE_SELECTOR = ""
CATALOG_LOCK_SELECTOR = ""   # 未探测到 VIP 锁标记
CATALOG_LINK_ID_RE = r"(\d+)(?:\.html?)?$"   # 从链接 href 提取章节编号
CHAPTER_TITLE_SELECTOR = ""
CHAPTER_CONTENT_SELECTOR = ""
CHAPTER_PARAGRAPH_TAG = ""  # 空 = 正文用 <br/> 换行拆分
CHAPTER_CLEAN_SELECTORS = ("script","style")   # 正文容器内导航/广告节点，解析前删除
STORY_TITLE_RE = r"^第[0-9一二三四五六七八九十百千零两]+[章回]"
SKIP_TITLE_KEYWORDS = ("上架感言",)   # 标题含以下词即排除

# 抓取范围
RANGE = None   # None = 自动筛选正文（免费章或全部正文，视锁标记）

# 行为控制
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
EXTRA_HEADERS = {"Accept-Language": "zh-CN,zh;q=0.9", "Referer": "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html"}
PAGE_ENCODING = None   # None = 交给 requests 自动判断
REQUEST_TIMEOUT = 20
MIN_DELAY, MAX_DELAY = 1.5, 3.0
MAX_RETRY = 3
RETRY_BACKOFF = 5

# 本地路径
DATA_DIR = "data/www.langsong.net_"
OUTPUT_EPUB = "output/三国演义_全本.epub"
