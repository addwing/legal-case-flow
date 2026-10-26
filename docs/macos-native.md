# macOS 上不必装的东西

这一页只讲一件事：**出图、读 PDF、读 Word 这三件事，mac 本来就自带能力。**
为了跑通去 `brew install` 一整套，是这条路上最常见的浪费。

以下全部 macOS 14 / 15 实测。

---

## 一张对照表

| 要干的事 | 系统自带 | 一条命令 | 原来那套（备用） |
| --- | --- | --- | --- |
| SVG → PNG | `sips`（ImageIO 直接吃 SVG） | `sips -s format png 图.svg --out 图.png` | cairosvg / rsvg-convert / soffice |
| SVG → 更大尺寸 | `qlmanage -t -s 2400` | `native.py svg2png 图.svg 图.png --size 2400` | soffice |
| PDF 页数 / 全文 | `osascript` + PDFKit | `native.py pdftext 卷.pdf` | pdfinfo / pdftotext |
| PDF 首页 → PNG | `sips --resampleWidth 1600` | `native.py pdf2png 卷.pdf 目录/` | pdftoppm |
| .docx 取文字 | `textutil` | `textutil -convert txt -output x.txt 材料.docx` | python-docx |
| 中文字体 | Songti.ttc / STHeiti / Hiragino Sans GB | 字体名写 `Songti SC`，别写「宋体」 | 自备字体文件 |
| 大目录拷贝 | `ditto`（保 UTF-8 名与扩展属性） | `ditto 源 目标` | tar / rsync |
| 被 Gatekeeper 拦 | `xattr` | `xattr -dr com.apple.quarantine 目录` | 去隐私设置点允许 |

`sips` 转出来的图，中文、配色、透明背景都对，实测与原 SVG 一致。
**这就是 mac 上出 PNG 的正路。**

---

## 唯一值得为它装 Homebrew 的

**扫描件逐页栅格化**。

`sips` 只出首页，`qlmanage` 也只出首页缩略图。要把一本 150 页的扫描卷宗
按页转成图（OCR 前处理、或逐页比对笔迹），只有 `pdftoppm`：

```bash
brew install poppler
pdftoppm -r 150 -png 卷.pdf 页
```

除这一项之外，poppler、LibreOffice、cairosvg 在 mac 上都可以不装。

---

## 也不要走的弯路

| 别这么做 | 为什么错 | 该怎么做 |
| --- | --- | --- |
| 直接用 `/usr/bin/python3` | 没装 Command Line Tools 会弹窗下 2 GB，看着像卡死 | 先 `xcode-select -p`；用 python.org 或托管的解释器 |
| `sudo pip install` | 报 `externally-managed-environment`，装进去也会被系统更新冲掉 | 装进 venv，不加 sudo |
| 把网盘/U 盘拷来的目录直接跑 | `com.apple.quarantine` 会让脚本被拦，报错难懂 | `xattr -dr com.apple.quarantine 目录` |
| 用 `tar` 在两个 mac 之间打包 | 中文名与扩展属性容易丢，还混进 `._` 分身 | 本机用 `ditto`；跨机用 `pack.py pack` |
| Finder 里翻过目录再打包 | 生成 `.DS_Store`，校验的文件数每次不一样 | `native.py clean .` 先清一遍 |
| 用 `mdls` 取 PDF 文字 | 依赖 Spotlight 索引，`/tmp` 与外部盘读不到，返回 `(null)` | 用 PDFKit（`native.py pdftext`） |
| 把 `qlmanage` 当出图首选 | 无 GUI 会话或沙箱里报 `sandbox initialization failed` | `sips` 打头，qlmanage 只用于放大 |
| 拿 `textutil` 转出的 txt 当底稿 | 表格被摊平成行，样式全丢，看着像原文其实结构没了 | 只用来「读」；底稿仍用上游 ingest |

---

## 字体：为什么图里会掉方框

上游写死「宋体」，那是 Windows 的字体名。mac 上没有这个名，PDF 与 SVG 渲染时会
回退到默认字体，中文可能变成方框。

mac 上的对应关系：

| 上游写的 | mac 用 |
| --- | --- |
| 宋体 / SimSun | `Songti SC` |
| 黑体 / SimHei | `STHeiti`（或 `Heiti SC`） |
| 微软雅黑 | `Hiragino Sans GB` |
| 楷体 / KaiTi | `Kaiti SC`（部分系统未预装） |

`native.py check` 会列出这台机器上有哪几个。

---

## 自检

```bash
python3 <技能>/scripts/native.py check
```

它会现造一份 PDF 和一个 SVG 真跑一遍，而不是只报「命令在不在」：

```
OK  PDF 通路实测：PDFKit 读到 1 页、10 字 —— 这台机器不需要 pdfinfo / pdftotext
OK  sips 直接转 （中文与配色都对）
```
