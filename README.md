# 📖 novel_epub —— 小说目录页 → 一键 EPUB 转换工具

[English README](README_EN.md)

> 给定一本**你有权获取**的书的「目录页网址」，程序自动识别网站结构、抓取正文、打包成标准 EPUB。

## 🚀 免安装直接用：Windows 单文件版（推荐）

**不用装 Python，双击即用。** 打包好的单个 exe：

- **下载**：到本仓库 **Releases** 页下载 `novel-epub-gui.exe`（约 26 MB）；本地开发机也可直接用 `dist\novel-epub-gui.exe`（该文件不入库，仅本地打包产物）
- **用法**：双击打开窗口 → 粘贴「目录页网址」→ 先点「② 试水（前3章）」→ 确认后点「③ 全量抓取+打包」
- **产出位置**：抓的书与成品 EPUB 直接生成在 **exe 同目录**的 `data\`、`output\`（无需管理员权限，别放 `C:\Program Files`）
- **没有现成 exe 时**：在项目目录执行下方打包命令即可自行生成

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name novel-epub-gui ^
    --collect-all ebooklib --hidden-import auto --hidden-import fetch ^
    --hidden-import build_epub --exclude-module config gui.py
```

如果你想用源码跑（Windows/macOS/Linux 均可），见下方 [安装](#-安装) 与 [快速开始](#-快速开始)。

## ⚠️ 合规声明（请先读）

本工具**只支持你有权获取的内容**，并内置了对应的边界：

- ✅ 公有领域作品（如《三国演义》《西游记》等明清经典）
- ✅ 官方平台**免费公开**阅读的内容（工具自动识别 VIP 锁标记，只抓未上锁的免费公开章）
- ⛔ 自动跳过 VIP / 付费章，不做任何付费内容抓取
- ⛔ 对未授权转载站（含混淆 / 加密接口的镜像站）**不提供抓取支持**：遇到 JS 动态渲染的壳页，工具会给出诊断说明并停止，而不是尝试破解
- 📦 本仓库**不含任何书籍正文数据**（`data/`、`output/` 均为本地运行产物，已被 `.gitignore` 排除）

请只对你有权下载的内容使用本工具，并为结果承担相应责任。

## ✨ 功能特性

- **全自动**：只给目录页 URL，自动完成 探测 → 写配置 → 抓正文 → 打包 EPUB
- **多形态站点自适应**：
  - 散链接目录（章节链接分散在页面各处）
  - 行容器目录（每章一个 `<li>/<dd>`，如官方阅读平台）
  - VIP 锁标记自动识别 → 只抓免费公开章
  - 章回体标题（第X章 / 第X回）、补零链接（`001.htm`）、GBK/GB18030 老站编码
  - 正文无 id/class 的老站整页兜底解析
  - JS 动态渲染(SPA)站点：给出诊断并停止
- **断点续传 + 礼貌限速 + 失败重试**：中断后重跑只补未抓的章节
- 输出标准 EPUB，可在 微信读书 / Kindle / 各类阅读器导入

## 📦 安装

需要 Python 3.8+（在 3.13 上开发验证）。

```bash
pip install -r requirements.txt
```

## 🚀 快速开始

```bash
# 1. 先试水：只抓前 3 章，确认效果
python auto.py "目录页网址" --limit 3

# 2. 没问题后，去掉 --limit 抓取全部目标章节并打包
python auto.py "目录页网址"
```

工作示例（公有领域，可全本）：

```bash
# 《三国演义》120 回（朗诵天地文学书库）
python auto.py "http://www.langsong.net/lstd/wxshk/htm/oem/gd/xs/3/index.html" --limit 3
```

完成后 EPUB 输出到 `output/`，正文缓存到 `data/`（可断点续传）。
`config.py` 由程序自动生成（已加入 `.gitignore` 不入库）；想手动改结构时复制
`config.example.py` 为 `config.py` 再编辑。

### 参数

| 参数 | 作用 |
|---|---|
| `--limit N` | 只抓前 N 章试水（强烈建议先跑） |
| `--only-config` | 只探测并生成 `config.py`，不抓取不打包 |

## 🖥 图形界面 & 打包 exe

不想敲命令？附带了 tkinter 图形界面（Python 自带，零额外依赖）：

```bash
python gui.py        # 打开窗口：填网址 → 试水 → 全量
```

GUI 里有个**抓取间隔(ms)** 输入框：

- 留空 = 使用默认礼貌限速（每章随机 1500~3000 ms）；
- 填数字 = 按你设定的间隔抓取（单位毫秒，程序会尽量遵循）；
- 若你填的间隔低于安全下限（500 ms/章），程序会**自动按最快速度 500 ms 执行**，并在输入框下方提示 **“已使用最大速度提取”**，避免把目标站抓挂。

打包成 Windows 单文件 exe（先 `pip install pyinstaller`）：

```bash
pyinstaller --onefile --noconsole --name novel-epub-gui ^
    --collect-all ebooklib --hidden-import auto --hidden-import fetch ^
    --hidden-import build_epub --exclude-module config gui.py
```

- 产物在 `dist/novel-epub-gui.exe`，双击即用（无需安装 Python）。
- 把 exe 放到**有写权限的文件夹**（如桌面、`D:\`），程序会在同目录生成 `data/`、`output/`、`config.py`。
- exe 在进程内直调各模块，无需 Python 环境；合规边界与命令行版完全一致。

## 🗂 目录结构

```
novel_epub/
├── README.md          # 本文件（中文）
├── README_EN.md       # English README
├── LICENSE            # MIT 许可证
├── requirements.txt   # 依赖清单
├── .gitignore
├── auto.py            # 主程序：探测 → 生成 config → 抓取 → 打包
├── fetch.py           # 抓取模块（断点续传 / 限速 / 重试）
├── build_epub.py      # EPUB 打包模块
├── gui.py             # 图形界面（tkinter），可打包成 exe
├── config.example.py  # 配置模板（config.py 由程序自动生成且不入库）
├── config.py          # 本地生成：auto.py/gui 自动写入（被 .gitignore 忽略）
├── data/              # 本地：章节正文缓存（不入库）
└── output/            # 本地：生成的 EPUB（不入库）
```

## 🔧 工作原理

```
用户给出「目录页 URL」
   ↓ auto.py 第1步：抓目录页，识别章节链接/URL 模板/标题规则/行容器/VIP锁
   ↓ 第2步：抓一个章节页，探测 标题节点/正文容器/段落方式/编码
   ↓ 第3步：把探测结果写入 config.py（旧配置自动备份 config.py.bak）
   ↓ 第4步：fetch.py 逐章抓正文（1.5~3s 限速、失败重试、断点续传）
   ↓ 第5步：build_epub.py 打包标准 EPUB（含目录 TOC）
```

换书 = 换一个「目录页 URL」重新运行 auto.py，无需手工改配置（`auto.py` 自动完成）。

## 🤔 常见问题

**Q：报错 `can't open file '...auto.py'`？**
A：先 `cd` 到本仓库目录再运行，例如 `cd "F:\ZCR_code\project\爬小说EPUB项目\novel_epub"`；或用 `python` 加完整脚本路径。

**Q：某网站抓不到？**
A：先看报错。若是"JS 动态渲染站点(SPA)"的诊断信息，说明该站正文不在 HTML 里、或属未授权镜像站——按合规边界本工具不做破解；请改用你有权获取的源。

**Q：怎么只抓部分章节？**
A：把 `config.py` 的 `RANGE` 改成想要的编号列表（如 `RANGE = [1,2,3]`），再运行 `python fetch.py`。

**Q：`config.py` 老是变、会显示为已修改(M)？**
A：正常——它是每次运行自动生成的（换书即重写），已加入 `.gitignore` 不再入库。手动调整请复制 `config.example.py` 为 `config.py`。

**Q：作者/书名显示 unknown？**
A：老站目录页常缺元信息，工具已尽力从 `<h1>`/meta/`<title>` 猜测；不影响抓取与阅读，可在 `config.py` 手工改正后重跑 `python build_epub.py`。

## 📄 License

[MIT](LICENSE)
