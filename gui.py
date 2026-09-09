# -*- coding: utf-8 -*-
"""novel_epub 图形界面（tkinter 版）。

用法:
    python gui.py                          # 打开图形界面
    python gui.py <目录页URL> [--limit N]   # 控制台模式（不弹界面，方便调试/测试）
    python gui.py <目录页URL> --only-config # 控制台模式：只探测生成 config.py

打包成 exe（Windows）:
    pip install pyinstaller
    pyinstaller --onefile --noconsole --name novel-epub-gui ^
        --collect-all ebooklib --hidden-import auto --hidden-import fetch ^
        --hidden-import build_epub gui.py

合规提示：仅用于你有权获取的内容（公有领域 / 官方免费公开部分）；
自动跳过 VIP/付费章；不破解未授权镜像站的加密接口。
"""
import importlib
import os
import queue
import re
import shutil
import sys
import threading
from urllib.parse import quote

# 运行目录：脚本所在目录（打包后 = exe 所在目录）。data/output/config 都放这里。
if getattr(sys, "frozen", False):            # PyInstaller 打包运行
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# 首次运行时若 config.py 不存在，用下面这个“公有领域示例”兜底（之后会被自动探测覆盖）
DEFAULT_CONFIG = '''# -*- coding: utf-8 -*-
# 示例默认配置（三国演义/公有领域）。运行一次 gui/auto 后会被自动探测结果覆盖。
BOOK_TITLE = "三国演义"
BOOK_AUTHOR = "罗贯中"
BOOK_ID = ""
BOOK_LANG = "zh-CN"
EPUB_TITLE = "三国演义（全本）"
EPUB_IDENTIFIER = "auto-example"
CATALOG_URL = "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html"
CHAPTER_URL = "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/{idx:03}.htm"
CATALOG_ITEM_SELECTOR = ""
CATALOG_LINK_SELECTOR = ""
CATALOG_TITLE_SELECTOR = ""
CATALOG_LOCK_SELECTOR = ""
CATALOG_LINK_ID_RE = r"(\\d+)(?:\\.html?)?$"
CHAPTER_TITLE_SELECTOR = ""
CHAPTER_CONTENT_SELECTOR = ""
CHAPTER_PARAGRAPH_TAG = ""
CHAPTER_CLEAN_SELECTORS = ("script", "style")
STORY_TITLE_RE = r"^第[0-9一二三四五六七八九十百千零两]+[章回]"
SKIP_TITLE_KEYWORDS = ("上架感言",)
RANGE = None
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
EXTRA_HEADERS = {"Accept-Language": "zh-CN,zh;q=0.9",
                 "Referer": "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html"}
PAGE_ENCODING = None
REQUEST_TIMEOUT = 20
MIN_DELAY, MAX_DELAY = 1.5, 3.0
MAX_RETRY = 3
RETRY_BACKOFF = 5
DATA_DIR = "data/example"
OUTPUT_EPUB = "output/example.epub"
'''


def bootstrap():
    """确保运行目录正确、config.py 存在、并可直接 import 本仓库各模块。"""
    os.makedirs(APP_DIR, exist_ok=True)
    os.chdir(APP_DIR)
    if APP_DIR not in sys.path:
        sys.path.insert(0, APP_DIR)
    cfg = os.path.join(APP_DIR, "config.py")
    if not os.path.exists(cfg):
        with open(cfg, "w", encoding="utf-8") as f:
            f.write(DEFAULT_CONFIG)


def prepare_config(url, limit=None):
    """复刻 auto.py 的探测流程：探测目录/正文结构 → 生成 config.py。"""
    import auto
    # 中文路径 URL 先百分号编码（Referer 请求头只接受 ASCII）
    url = quote(url, safe=":/?&=#%+")
    print("==> 第1步 抓目录页: %s" % url, flush=True)
    cat = auto.probe_catalog(url)

    print("==> 第2步 抓章节页(探测正文结构)...", flush=True)
    chap = None
    for cand in cat["entries"][:6]:
        try:
            chap = auto.probe_chapter(cand[1], referer=url)
            print("    采用章节示例: idx=%s (%s)" % (cand[0], cand[2][:30]), flush=True)
            break
        except RuntimeError as e:
            print("    [跳过试例] idx=%s 探测失败 → %s" % (cand[0], str(e).splitlines()[0]), flush=True)
    if chap is None:
        raise RuntimeError("连续几个章节都无法探测到正文容器，请人工检查该站结构。")

    book, author, book_id = auto.guess_meta(cat["soup"], url)
    host = re.sub(r"^https?://", "", url).split("/")[0]
    cfg = dict(cat)
    cfg.update(chap)
    cfg.update({"book": book, "author": author, "book_id": book_id,
                "host": host, "limit": limit})

    print("===== 自动探测摘要 =====", flush=True)
    print("书名: %s | 作者: %s | 识别章节: %d" % (
        book, author, len(cat["entries"])), flush=True)

    cfg_path = os.path.join(APP_DIR, "config.py")
    if os.path.exists(cfg_path):
        shutil.copy(cfg_path, cfg_path + ".bak")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write(auto.render_config(cfg))
    print("已重写 config.py（旧配置备份为 config.py.bak）", flush=True)


def fetch_and_build():
    """抓正文 + 打包 EPUB（进程内调用，避免打包后找不到脚本文件）。"""
    import config
    importlib.reload(config)          # 让新生成的 config 生效

    print("==> 第3步 抓取正文（已抓过的自动跳过，可断点续传）...", flush=True)
    import fetch
    importlib.reload(fetch)           # 重新加载，让模块顶部的请求头/正则读新 config
    sys.argv = ["fetch.py"]           # fetch.main 用 argparse 读 sys.argv，别让它误读 GUI 参数
    try:
        fetch.main()
    except SystemExit as e:           # fetch.main 失败时 sys.exit(1)
        print("[注意] 抓取有失败章节：%s（可重跑续传）" % e, flush=True)

    print("==> 第4步 打包 EPUB ...", flush=True)
    import build_epub
    build_epub.main()
    return config.OUTPUT_EPUB


def run_flow(url, limit=None, only_config=False):
    """整条流水线：探测 → 生成 config → 抓取 → 打包。返回 EPUB 路径（仅打包时）。"""
    bootstrap()
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError("请先填写正确的目录页网址（http/https 开头）")
    prepare_config(url, limit=limit)
    if only_config:
        print("已生成 config.py（未抓取）。", flush=True)
        return None
    out = fetch_and_build()
    print("全部完成！EPUB 输出：%s" % out, flush=True)
    return out


# ==================== 控制台模式（无界面） ====================

def main_cli():
    args = sys.argv[1:]
    only_config = "--only-config" in args
    if only_config:
        args.remove("--only-config")
    limit = None
    if "--limit" in args:
        i = args.index("--limit")
        limit = int(args[i + 1])
        del args[i:i + 2]
    url = args[0] if args else ""
    run_flow(url, limit=limit, only_config=only_config)


# ==================== 图形界面模式 ====================

class _QueueWriter:
    """把 print() 的输出转发进队列（GUI 里再显示到日志框）。"""
    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s:
            self.q.put(s)

    def flush(self):
        pass


def main_gui():
    import tkinter as tk
    from tkinter import messagebox, scrolledtext

    root = tk.Tk()
    root.title("novel_epub — 目录页 → EPUB")
    root.geometry("860x640")

    log_q = queue.Queue()

    frm = tk.Frame(root, padx=12, pady=8)
    frm.pack(fill="x")

    tk.Label(frm, text="目录页网址：", anchor="w").grid(row=0, column=0, sticky="w")
    url_var = tk.StringVar()
    tk.Entry(frm, textvariable=url_var, width=78).grid(row=0, column=1, sticky="we", padx=6)

    # 试水数量
    row2 = tk.Frame(frm)
    row2.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
    tk.Label(row2, text="试水章数：").pack(side="left")
    limit_var = tk.StringVar(value="3")
    tk.Spinbox(row2, from_=1, to=20, width=4, textvariable=limit_var).pack(side="left")
    tk.Label(row2, text="  （先抓几章试效果，确认没问题再点全量）", fg="#666").pack(side="left")

    btns = tk.Frame(root, padx=12)
    btns.pack(fill="x", pady=4)
    b_cfg = tk.Button(btns, text="① 仅生成配置", width=16)
    b_try = tk.Button(btns, text="② 试水抓取（前 N 章）", width=20)
    b_all = tk.Button(btns, text="③ 全量抓取 + 打包 EPUB", width=22)
    b_cfg.pack(side="left", padx=4)
    b_try.pack(side="left", padx=4)
    b_all.pack(side="left", padx=4)

    tk.Label(root, text="⚠ 仅限你有权获取的内容（公有领域 / 官方免费公开部分）；自动跳过 VIP 付费章，不破解未授权镜像站。",
             fg="#b00020", padx=12, anchor="w").pack(fill="x")

    txt = scrolledtext.ScrolledText(root, state="disabled", wrap="word", height=22)
    txt.pack(fill="both", expand=True, padx=12, pady=6)

    status_var = tk.StringVar(value="就绪：填网址 → 点 ②试水 或 ③全量")
    tk.Label(root, textvariable=status_var, anchor="w", padx=12, pady=8).pack(fill="x")

    def append_log(s):
        txt.config(state="normal")
        txt.insert("end", s)
        txt.see("end")
        txt.config(state="disabled")

    def pump():
        try:
            while True:
                s = log_q.get_nowait()
                append_log(s)
        except queue.Empty:
            pass
        root.after(100, pump)

    def set_busy(busy):
        state = "disabled" if busy else "normal"
        for b in (b_cfg, b_try, b_all):
            b.config(state=state)
        url_var.set(url_var.get() or "")

    def run(mode):
        url = url_var.get().strip()
        if not url:
            messagebox.showwarning("缺少网址", "请先填写目录页网址。")
            return
        limit = None
        if mode == "only_config":
            pass
        elif mode == "try":
            limit = int(limit_var.get() or 3)
        # mode == "all" → limit=None
        set_busy(True)
        status_var.set("运行中…（限速抓取，整本较慢属正常）")

        def worker():
            try:
                run_flow(url, limit=limit, only_config=(mode == "only_config"))
                status_var.set("完成 ✅  成品 EPUB 在程序同目录的 output\\ 文件夹")
            except Exception as e:
                print("出错了：%s" % e, flush=True)
                status_var.set("出错了，详见上方日志")
            finally:
                set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    b_cfg.config(command=lambda: run("only_config"))
    b_try.config(command=lambda: run("try"))
    b_all.config(command=lambda: run("all"))

    # 把整个程序的 print 输出都送进日志框
    sys.stdout = _QueueWriter(log_q)
    sys.stderr = _QueueWriter(log_q)

    print("novel_epub GUI 已就绪。\n"
          "用法：粘贴『目录页网址』→ 先点 ②试水（默认前3章）看效果，确认无误后点 ③全量。\n"
          "数据缓存 data\\，成品 EPUB 在 output\\。\n", flush=True)

    root.after(120, pump)
    root.mainloop()


if __name__ == "__main__":
    bootstrap()
    if len(sys.argv) > 1:                 # 带参数 = 控制台模式
        main_cli()
    else:
        main_gui()
