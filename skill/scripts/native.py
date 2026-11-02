#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""macOS 原生替身工具箱：能用系统自带的，就不装第三方的。零依赖、零安装。

上游那几家写命令时假定 Linux：poppler 取 PDF、soffice 转图、python-docx 读 Word。
在 mac 上这三件事系统本来就自带，先走原生，顶不住时才回头装——顺序反过来，
就是为了少装一整套 Homebrew。

    python3 native.py check                      这台机器上哪些原生的能用（现造 PDF / SVG 实测）
    python3 native.py pdfpages 卷.pdf            页数（PDFKit，不看索引脸色）
    python3 native.py pdftext  卷.pdf [-o x.txt] [--page N]  文字层（PDFKit；扫描件取不到是正常的）
    python3 native.py doc2txt  材料.docx [-o x.txt]  取文字（textutil）
    python3 native.py svg2png  图.svg 图.png [--size 2400]  SVG 转 PNG（sips；箭头自动展开）
    python3 native.py pdf2png  卷.pdf 目录/ [--size 1600]   首页转 PNG（sips）
    python3 native.py clean    目录/             清 .DS_Store 与 ._ 分身（打包前跑）

为什么是这几条：
- sips 走 ImageIO，直接吃 SVG，中文与配色都对 —— mac 上出 PNG 的正路。
- osascript 用 JXA 调 PDFKit，页数与全文都能拿，连 pip 都不用。
- textutil 读 docx 只取文字，表格会摊平；要结构仍用 python-docx。

边界（都是实测过的，别被「系统自带」四个字骗了）：
- **sips 不实现 <marker>**：法律关系图、对抗图、重画的箭头全靠 marker-end，
  直转出来箭头全丢，线成了光头。所以 svg2png 会先调同目录的 svg_marker.py
  把箭头展开成真实图形，再交给 sips。缺了 svg_marker.py 也不致命，只是没箭头。
- **sips 出的 PDF 是位图**：整张栅格化成 JPEG 塞进 PDF，没有文字层（/Font 0）。
  要矢量、可检索的 PDF，仍得用 cairosvg.svg2pdf，这一项 sips 顶不了。
- qlmanage 在无 GUI 会话或沙箱里会报 sandbox initialization failed，所以它排在 sips 之后。
- PDF 逐页栅格化（扫描件整套）mac 原生顶不住，那时才装 poppler。
"""
import os
import platform
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import svg_marker                     # 同目录，零依赖；缺了不影响其它子命令
except ImportError:                       # pragma: no cover
    svg_marker = None

# 原生工具 → 干什么 → 顶替谁。doctor 与 check 共用这一张表。
NATIVE = [
    ("sips", "SVG→PNG（原尺寸，箭头要先展开）、PDF 首页栅格化、位图缩放", "cairosvg / rsvg-convert / soffice / pdftoppm（首页）"),
    ("osascript", "JXA 调 PDFKit：PDF 页数与全文文字", "pdfinfo / pdftotext"),
    ("qlmanage", "QuickLook 缩略图：按指定长边出图", "soffice（放大时才需要）"),
    ("textutil", "doc/docx/rtf/html 互转与取文字", "python-docx（仅取文字时）"),
    ("cupsfilter", "txt/图片 打成 PDF", "—"),
    ("mdls", "兜底读页数（依赖 Spotlight 索引）", "pdfinfo"),
    ("mdimport", "给单个文件建索引，喂 mdls", "—"),
    ("mdfind", "按内容找文件（找同一份材料的不同版本）", "—"),
    ("ditto", "打包拷贝，保住 UTF-8 名与扩展属性", "tar / rsync"),
    ("xattr", "清 com.apple.quarantine，解开被拦的脚本", "—"),
    ("open", "用默认程序打开产物（交付时给律师看）", "—"),
]


def have(name):
    return bool(shutil.which(name))


def run(args, timeout=120):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return 1, "", str(e)


def die(msg, code=2):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(code)


def is_mac():
    return platform.system() == "Darwin"


def require(tool):
    if not have(tool):
        die("这台机器上没有 %s。%s" % (tool, "本技能的原生路径只在 macOS 上成立；"
                                      "非 mac 就按 SKILL.md 的备用方案装 poppler / LibreOffice。"))


def mdls(path, key):
    rc, out, err = run(["mdls", "-raw", "-name", key, path])
    if rc != 0:
        return None
    out = out.strip()
    if not out or out in ("(null)", "null"):
        return None
    return out


def selftest_pdf():
    """真造一个 PDF 再读一遍。只报「命令在」不算数，要报「这条路通」。"""
    d = tempfile.mkdtemp(prefix="pdfprobe-")
    txt, pdf = os.path.join(d, "probe.txt"), os.path.join(d, "probe.pdf")
    try:
        with open(txt, "w", encoding="utf-8") as f:
            f.write("编排层自检 二零二六\n")
        if not have("cupsfilter"):
            return None, None, "没有 cupsfilter，造不出测试 PDF"
        with open(pdf, "wb") as out, open(os.devnull, "wb") as null:
            subprocess.run(["cupsfilter", "-m", "application/pdf", txt],
                           stdout=out, stderr=null, timeout=120)
        if not os.path.isfile(pdf) or os.path.getsize(pdf) == 0:
            return None, None, "cupsfilter 没造出 PDF"
        n, t = jxa(pdf, "count"), jxa(pdf, "all")
        if n and t:
            return n, len(t), None
        return n, (len(t) if t else 0), "PDFKit 读得到页数、读不到文字"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def cmd_check(_argv):
    print("系统：%s %s / %s" % (platform.system(), platform.release(), platform.machine()))
    print("Python：%s（%s）" % (sys.version.split()[0], sys.executable))
    if sys.executable.startswith("/usr/bin/"):
        print("  ！这是系统 Python，需要 Command Line Tools；没装会弹窗要你下 2 GB。")
        print("    先跑 xcode-select -p 看一眼；没有就换 python.org / Homebrew / 托管的那一份。")
    print()
    if not is_mac():
        print("！不是 macOS。下面这张表只在 mac 上成立，请按 SKILL.md「备用方案」走。")
    print("原生工具（系统自带，装了就能用，不需要 Homebrew）：")
    for tool, what, replaces in NATIVE:
        p = shutil.which(tool)
        print("  %s %s｜%s｜顶替 %s" % ("OK  " if p else "缺  ", pad(tool, 11), pad(what, 44), replaces))
    print()
    print("PDF 通路实测（现造一份 PDF，再读页数与文字）：")
    pages, chars, why = selftest_pdf()
    if why:
        print("  ！ %s" % why)
    else:
        print("  OK  PDFKit 读到 %s 页、%d 字 —— 这台机器不需要 pdfinfo / pdftotext" % (pages, chars))
    print()
    print("SVG→PNG 实测（样本特意带 marker-end 箭头，专盯 sips 的短板）：")
    d = tempfile.mkdtemp(prefix="svgprobe-")
    try:
        s = os.path.join(d, "p.svg")
        with open(s, "w", encoding="utf-8") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="80">'
                    '<rect width="200" height="80" fill="#fff"/>'
                    '<defs><marker id="m" markerWidth="12" markerHeight="12" refX="0" refY="6"'
                    ' orient="auto" markerUnits="userSpaceOnUse">'
                    '<path d="M0,0 L12,6 L0,12 Z" fill="#00FF00"/></marker></defs>'
                    '<line x1="20" y1="40" x2="150" y2="40" stroke="#000" stroke-width="2"'
                    ' marker-end="url(#m)"/>'
                    '<text x="20" y="70" font-size="14" fill="#333">宋体测试</text></svg>')
        work, n = _expand_arrows(s, d)
        ok = False
        if have("sips"):
            rc, _, _ = run(["sips", "-s", "format", "png", work, "--out", os.path.join(d, "p.png")])
            ok = rc == 0 and os.path.isfile(os.path.join(d, "p.png"))
        if svg_marker is None:
            print("  ！ 同目录缺 svg_marker.py —— 出图时箭头会全丢（关系图、对抗图都靠它）")
            print("     补上这一个文件就行，不需要装任何库")
        else:
            print("  OK  箭头展开：%d 个（sips 不认 <marker>，不展开直转就是一个不剩）" % n)
            if n == 0:
                print("  ！ 样本里的箭头没被认出来，展开器可能坏了")
        print("  %s sips 出图：%s" % ("OK  " if ok else "缺  ",
                                    "200×80，中文与配色都对" if ok else "转不出来，放大时才需要 qlmanage"))
        print("     要矢量、可检索的 PDF（交法院那种），sips 顶不了，仍用 cairosvg.svg2pdf")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print()
    print("中文字体（上游写死「宋体」，mac 上要换名）：")
    for name, path in [("Songti SC（←宋体）", "/System/Library/Fonts/Supplemental/Songti.ttc"),
                       ("STHeiti（←黑体）", "/System/Library/Fonts/STHeiti Medium.ttc"),
                       ("Hiragino Sans GB（←微软雅黑）", "/System/Library/Fonts/Hiragino Sans GB.ttc"),
                       ("Kaiti SC（←楷体）", "/System/Library/Fonts/Supplemental/Kaiti.ttc")]:
        print("  %s %s" % ("OK  " if os.path.isfile(path) else "缺  ", name))
    print()
    print("结论：PDF 页数与文字走 PDFKit（osascript），首页出图走 sips，SVG→PNG 走 sips + 箭头展开。")
    print("      Word 取文字走 textutil。这几件事在 mac 上都不用装东西。")
    print("      唯一的缺口：矢量 PDF（仍要 cairosvg）与扫描件逐页栅格化（仍要 poppler）。")
    return 0


def jxa(path, mode, page=None):
    """用 JXA 调系统的 PDFKit 读 PDF。mac 上零安装就能拿到页数与文字层。

    这是本文件里最值钱的一条：poppler 三件套（pdfinfo / pdftotext / pdftoppm）
    为的就是这件事，而 PDFKit 是系统自带的，连 pip 都不用。
    """
    if not have("osascript"):
        return None
    lit = '"%s"' % path.replace('\\', '\\\\').replace('"', '\\"')
    if mode == "count":
        body = "if(!d){throw new Error('打不开')} d.pageCount"
    elif mode == "page":
        body = ("if(!d){throw new Error('打不开')} ObjC.unwrap(d.pageAtIndex(%d).string)" % (page or 0))
    else:
        body = "if(!d){throw new Error('打不开')} ObjC.unwrap(d.string)"
    script = ('ObjC.import("Quartz");var d=$.PDFDocument.alloc.initWithURL('
              '$.NSURL.fileURLWithPath(%s));%s' % (lit, body))
    rc, out, err = run(["osascript", "-l", "JavaScript", "-e", script], timeout=180)
    if rc != 0:
        return None
    return out.strip()


def cmd_pdfpages(argv):
    if not argv:
        die("用法：native.py pdfpages 文件.pdf")
    src = os.path.abspath(argv[0])
    n = jxa(src, "count")                      # PDFKit 先来：不看索引脸色
    if n:
        print(n)
        return 0
    if have("mdls"):                           # 退一步看 Spotlight（只对已索引目录有效）
        n = mdls(src, "kMDItemNumberOfPages")
        if n:
            print(n + "（来自 Spotlight；放在未索引目录时会读不到，那是索引的事）")
            return 0
    die("读不到页数。装 poppler 用 pdfinfo，或确认这是个真 PDF。")


def cmd_pdftext(argv):
    if not argv:
        die("用法：native.py pdftext 文件.pdf [-o 输出.txt] [--page N]")
    src = os.path.abspath(argv[0])
    out = argv[argv.index("-o") + 1] if "-o" in argv else None
    page = int(argv[argv.index("--page") + 1]) if "--page" in argv else None
    text = jxa(src, "page" if page is not None else "all", page)
    if not text:                                # PDFKit 取不到（扫描件就是没有文字层）
        if have("mdls"):
            if have("mdimport"):
                run(["mdimport", "-i", src])    # 塞进索引，否则新文件 mdls 是空的
            text = mdls(src, "kMDItemTextContent")
    if not text:
        print("！取不到文字层。", file=sys.stderr)
        print("  三种可能：① 扫描件（本来就没有文字层，要 OCR）② PDF 被加密 ③ 文件坏了。",
              file=sys.stderr)
        print("  要 OCR 时才装 poppler：pdftoppm -r 150 -png 卷.pdf 页 && 再走 OCR。", file=sys.stderr)
        return 1
    text = text.replace("\\n", "\n").replace("\\/", "/")
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print("已写 %s（%d 字%s）" % (out, len(text), "，第 %d 页" % (page + 1) if page is not None else ""))
    else:
        print(text)
    return 0


def cmd_doc2txt(argv):
    if not argv:
        die("用法：native.py doc2txt 文件.docx [-o 输出.txt]")
    src = argv[0]
    out = argv[argv.index("-o") + 1] if "-o" in argv else os.path.splitext(src)[0] + ".txt"
    require("textutil")
    rc, _, err = run(["textutil", "-convert", "txt", "-encoding", "UTF-8", "-output", out, src])
    if rc != 0:
        die("textutil 转不出来：%s" % (err.strip() or "格式不支持"))
    n = os.path.getsize(out)
    print("已写 %s（%d 字节）。只取文字，表格摊平、样式全丢。" % (out, n))
    return 0


def ql_thumb(src, size, dest_dir):
    """qlmanage 把缩略图写成 <源文件名>.png，改名成我们要的。"""
    rc, out, err = run(["qlmanage", "-t", "-s", str(size), "-o", dest_dir, src], timeout=180)
    base = os.path.basename(src)
    cand = os.path.join(dest_dir, base + ".png")
    if not os.path.isfile(cand):
        return None, (err.strip() or out.strip() or "qlmanage 没出图")
    return cand, None


def px(path):
    rc, out, _ = run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path])
    w = h = "?"
    for line in out.splitlines():
        if "pixelWidth" in line:
            w = line.split(":")[-1].strip()
        if "pixelHeight" in line:
            h = line.split(":")[-1].strip()
    return w, h


def _expand_arrows(src, tmpd):
    """把 <marker> 箭头展开成真实图形，返回 (可渲染的 svg, 箭头数)。

    sips 不认 <marker>，直转出来箭头全丢。缺 svg_marker.py 或图里没有箭头时，
    原样返回——这一步失败不该挡住出图。
    """
    if svg_marker is None:
        return src, 0
    try:
        return svg_marker.expand_file(src, os.path.join(tmpd, "expanded.svg"))
    except (OSError, ValueError, UnicodeDecodeError, RecursionError) as e:
        print("  ！ 箭头展开失败（%s），按原图转——箭头可能丢" % e)
        return src, 0


def cmd_svg2png(argv):
    if len(argv) < 2:
        die("用法：native.py svg2png 图.svg 图.png [--size 2400]")
    src, dst = os.path.abspath(argv[0]), argv[1]
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 0
    if not os.path.isfile(src):
        die("找不到 %s" % src)

    tmpd = tempfile.mkdtemp(prefix="svgmk-")
    try:
        work, arrows = _expand_arrows(src, tmpd)
        if arrows:
            print("  已展开 %d 个 marker 箭头（sips 不认 <marker>，不展开就全丢）" % arrows)
        elif svg_marker is None:
            print("  ！ 同目录缺 svg_marker.py：这张图若带箭头，转出来会是光头")
        return _svg2png(work, dst, size)
    finally:
        shutil.rmtree(tmpd, ignore_errors=True)


def _plain_ql_error(err):
    """qlmanage 吐的是英文系统话，别把它原样丢给人看。"""
    e = (err or "").strip()
    if "sandbox initialization failed" in e:
        return "这台机器上 QuickLook 被沙箱挡住，不是你的图有问题"
    if "No such file" in e or "not found" in e.lower():
        return "qlmanage 找不到这个文件"
    return e.splitlines()[0][:120] if e else "QuickLook 没给出图"


def _svg2png(src, dst, size):
    # 第一路：sips。macOS 的 ImageIO 直接吃 SVG，一条命令出图，
    # 中文、配色、透明背景都对，而且不用装 cairosvg / rsvg / soffice 里的任何一个。
    # 代价是只出 SVG 的固有尺寸——课件与 Word 里够用，印刷放大才需要第二路。
    if not size and have("sips"):
        rc, _, err = run(["sips", "-s", "format", "png", src, "--out", dst])
        if rc == 0 and os.path.isfile(dst):
            w, h = px(dst)
            print("已写 %s（%s×%s，SVG 固有尺寸）" % (dst, w, h))
            return 0

    # 第二路：qlmanage，按长边放大。沙箱或某些系统上会被拦，所以放在 sips 之后。
    if have("qlmanage"):
        tmp = tempfile.mkdtemp(prefix="ql-")
        try:
            got, err = ql_thumb(src, size or 2400, tmp)
            if got:
                shutil.move(got, dst)
                w, h = px(dst)
                print("已写 %s（%s×%s，qlmanage 长边 %d）" % (dst, w, h, size or 2400))
                return 0
            why = _plain_ql_error(err)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    else:
        why = "这台机器没有 qlmanage"

    # 第三路：还是要放大但要不到，退回 sips 原尺寸——尺寸小一点，总比没有强。
    if have("sips"):
        rc, _, _ = run(["sips", "-s", "format", "png", src, "--out", dst])
        if rc == 0 and os.path.isfile(dst):
            w, h = px(dst)
            print("已写 %s（%s×%s）。要不了 %d 长边（%s），给的是固有尺寸。" % (dst, w, h, size, why))
            return 0
    die("转不出来：%s。退路：rsvg-convert 或 soffice --convert-to png。" % why)


def cmd_pdf2png(argv):
    if len(argv) < 2:
        die("用法：native.py pdf2png 卷.pdf 目录/ [--size 1600]")
    src, outdir = os.path.abspath(argv[0]), argv[1]
    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 1600
    os.makedirs(outdir, exist_ok=True)
    dst = os.path.join(outdir, os.path.splitext(os.path.basename(src))[0] + "-p1.png")
    # sips 走 ImageIO，PDF 首页直接栅格化，还能顺手放大——首页预览、封面、附件缩览都够。
    if have("sips"):
        rc, _, err = run(["sips", "-s", "format", "png", "--resampleWidth", str(size), src, "--out", dst])
        if rc == 0 and os.path.isfile(dst):
            w, h = px(dst)
            print("已写 %s（%s×%s）—— 只是首页。" % (dst, w, h))
            print("要逐页（扫描件整套栅格化），mac 原生顶不住：pdftoppm -r 150 -png 卷.pdf 页")
            return 0
    if have("qlmanage"):
        got, err = ql_thumb(src, size, outdir)
        if got:
            print("已写 %s —— 只是首页缩略图。" % got)
            return 0
    die("转不出来：%s" % err)


def cmd_clean(argv):
    if not argv:
        die("用法：native.py clean 目录/  （清 .DS_Store 与 ._ 分身，打包前跑）")
    root = argv[0]
    if not os.path.isdir(root):
        die("不是目录：%s" % root)
    n = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn == ".DS_Store" or fn.startswith("._") or fn == ".localized":
                os.unlink(os.path.join(dirpath, fn))
                n += 1
    print("清掉 %d 个 mac 垃圾文件。它们会让包的指纹对不上，也会白占体积。" % n)
    return 0


def pad(text, width):
    """中文占两格，不补整列就歪。

    → ← ↑ ↓ ⇒ ⇔ 这类箭头码位在 0x2E80 以下，却被终端当宽字符画两格，
    不特判就会让整张表的竖线错位（check 的输出里天天有箭头）。
    """
    w = 0
    for c in str(text):
        w += 2 if (ord(c) > 0x2E80 or c in "→←↑↓⇒⇔⇐⇑⇓") else 1
    return str(text) + " " * max(0, width - w)


CMDS = {"check": cmd_check, "pdfpages": cmd_pdfpages, "pdftext": cmd_pdftext,
        "doc2txt": cmd_doc2txt, "svg2png": cmd_svg2png, "pdf2png": cmd_pdf2png,
        "clean": cmd_clean}


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0 if argv else 2
    fn = CMDS.get(argv[0])
    if not fn:
        die("不认识的子命令 %r，只有：%s" % (argv[0], " / ".join(CMDS)))
    return fn(argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
