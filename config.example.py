# -*- coding: utf-8 -*-
"""
config.example.py —— 配置模板（示例：公有领域《三国演义》）。

用法说明：
- 正常使用：直接运行 `python auto.py <目录页网址>` 或打开 GUI，
  程序会自动探测并把结果写入 `config.py`（config.py 已被 .gitignore 忽略，不会提交）。
- 需要手动调整结构/范围时：把本文件复制一份为 `config.py` 再修改。

字段含义：
- BOOK_* / EPUB_*      书籍元信息与 EPUB 标题
- CATALOG_URL          目录页网址（必须）
- CHAPTER_URL          章节网址模板，{idx} 是章节编号占位（自动探测生成）
- CATALOG_ITEM/LINK/TITLE/LOCK_SELECTOR  目录结构选择器
     空 = 散链接目录型（通扫全部 <a>）；非空 = 行容器目录型
- CHAPTER_TITLE/CONTENT_SELECTOR         章节页结构选择器（空 = 自动/整页兜底）
- CHAPTER_PARAGRAPH_TAG                  段落标签（空 = 用 <br/> 换行拆段）
- STORY_TITLE_RE / SKIP_TITLE_KEYWORDS   哪些算“正文章”标题 / 要排除的关键词
- RANGE               抓取范围：None=自动筛选；或列表如 [1,2,3]
- MIN_DELAY/MAX_DELAY 每章之间的随机等待秒数（对站点礼貌一点）
- DATA_DIR / OUTPUT_EPUB  正文缓存目录与最终 EPUB 输出路径
"""

# 书籍信息
BOOK_TITLE = "三国演义"
BOOK_AUTHOR = "罗贯中"
BOOK_ID = ""
BOOK_LANG = "zh-CN"
EPUB_TITLE = "三国演义（全本）"
EPUB_IDENTIFIER = "auto-example"

# 网页地址模板
CATALOG_URL = "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html"
CHAPTER_URL = "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/{idx:03}.htm"

# 网页结构（auto.py 探测结果）
CATALOG_ITEM_SELECTOR = ""        # 空 = 散链接目录型；非空如 "li.list" = 行容器型
CATALOG_LINK_SELECTOR = ""
CATALOG_TITLE_SELECTOR = ""
CATALOG_LOCK_SELECTOR = ""        # VIP 锁标记选择器，如 "i.lock"；留空视为全免费
CATALOG_LINK_ID_RE = r"(\d+)(?:\.html?)?$"
CHAPTER_TITLE_SELECTOR = ""       # 空 = 自动取第一个标题/用目录章名补
CHAPTER_CONTENT_SELECTOR = ""     # 空 = 整页兜底解析（老站无 id/class 时）
CHAPTER_PARAGRAPH_TAG = ""        # 空 = 用 <br/> 换行拆分段落
CHAPTER_CLEAN_SELECTORS = ("script", "style")
STORY_TITLE_RE = r"^第[0-9一二三四五六七八九十百千零两]+[章回]"
SKIP_TITLE_KEYWORDS = ("上架感言",)

# 抓取范围
RANGE = None    # None = 自动筛选（VIP 锁标记存在时只抓免费公开章）

# 行为控制
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
EXTRA_HEADERS = {"Accept-Language": "zh-CN,zh;q=0.9",
                 "Referer": "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html"}
PAGE_ENCODING = None      # None = 自动判断；老站 GBK 时可手动填 "gb18030"
REQUEST_TIMEOUT = 20
MIN_DELAY, MAX_DELAY = 1.5, 3.0    # 每章随机等待 1.5~3 秒
MAX_RETRY = 3
RETRY_BACKOFF = 5

# 本地路径
DATA_DIR = "data/example"
OUTPUT_EPUB = "output/example.epub"
