#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把编排层与它绑定的模块打成一个可校验的包，换机器、换同事、换 agent 都用它。零第三方依赖。

不做的事：不联网、不装依赖、不改上游一个字节。包里放的是原样目录 + 一份清单，
装回去之后由 bind.py 重新探测，所以「装上了」和「接得通」是两件事，各自有各自的判据。

用法：
    python3 pack.py pack                   在 ./legal-case-bundle.tar.gz 出包（含全部模块）
    python3 pack.py pack --slim            去掉 assets/ 与 tests/（体积约减到十分之一）
    python3 pack.py pack -o /tmp/x.tar.gz
    python3 pack.py verify 包.tar.gz        只读包，核对清单与文件指纹
    python3 pack.py install 包.tar.gz --to 技能根目录 [--force]
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SKILLS_ROOT = os.path.dirname(SKILL_DIR)
ORCH = "legal-case-flow"
PREFIX = "legal-case-bundle"
SLIM_EXCLUDE = ("assets", "tests", "__pycache__", ".git")
# mac 上 Finder 浏览一眼就会生成 .DS_Store，U 盘与网络盘还会多出 ._ 分身。
# 它们进包会让文件数、体积、指纹每次都不一样，排查时白费一晚。
MAC_JUNK = (".DS_Store", ".localized")
SCHEMA = "legal-case-flow/bundle@1"
VERSION = "0.2.0"


def die(msg, code=2):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(code)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def bound_roles():
    """问绑定表要实际目录。包只装「现在真接得通」的模块，不装一整排空目录。"""
    try:
        out = subprocess.run([sys.executable, os.path.join(HERE, "bind.py"), "--json"],
                             capture_output=True, text=True, timeout=60)
        if out.returncode != 0:
            die("绑定表读不出来：%s" % (out.stderr.strip() or out.stdout.strip()))
        return json.loads(out.stdout)["roles"]
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        die("绑定表读不出来：%s" % e)


def should_skip(rel, slim):
    base = os.path.basename(rel)
    if base in MAC_JUNK or base.startswith("._"):
        return True
    if not slim:
        return rel.endswith(".pyc") or "__pycache__" in rel
    parts = rel.split(os.sep)
    return any(p in SLIM_EXCLUDE for p in parts) or rel.endswith(".pyc")


def walk_files(base, slim):
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        if slim:
            dirnames[:] = [d for d in dirnames if d not in SLIM_EXCLUDE]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, base)
            if not should_skip(rel, slim):
                out.append(rel)
    return sorted(out)


def cmd_pack(argv):
    slim = "--slim" in argv
    out_path = os.path.join(os.getcwd(), PREFIX + ("-slim" if slim else "") + ".tar.gz")
    for i, a in enumerate(argv):
        if a in ("-o", "--out") and i + 1 < len(argv):
            out_path = os.path.abspath(argv[i + 1])
    roles = bound_roles()
    dirs = {ORCH: SKILL_DIR}
    manifest = {"schema": SCHEMA, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "slim": slim, "python": sys.version.split()[0],
                "note": "上游模块为第三方作品，随包保留其原目录与许可文件（MIT）；本层只读不改。",
                "orchestrator": {"dir": ORCH, "version": VERSION}, "roles": {}}
    for role, e in roles.items():
        d = e.get("dir")
        if e.get("status") != "bound" or not d or not os.path.isdir(d):
            print("· 跳过角色 %s（%s）" % (role, e.get("status")))
            continue
        name = os.path.basename(d)
        if name in dirs:
            manifest["roles"][role] = {"dir": name, "shared": True}
            continue
        dirs[name] = d
        files = walk_files(d, slim)
        md = os.path.join(d, "SKILL.md")
        manifest["roles"][role] = {"dir": name, "version": e.get("version"),
                                   "files": len(files),
                                   "bytes": sum(os.path.getsize(os.path.join(d, f)) for f in files),
                                   "sha256_skill_md": sha256(md) if os.path.isfile(md) else None}
    manifest["orchestrator"]["files"] = len(walk_files(SKILL_DIR, slim))

    payload = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")
    with tarfile.open(out_path, "w:gz") as tar:
        info = tarfile.TarInfo(PREFIX + "/manifest.json")
        info.size, info.mtime = len(payload), int(time.time())
        tar.addfile(info, io.BytesIO(payload))
        for name, d in dirs.items():
            for rel in walk_files(d, slim):
                tar.add(os.path.join(d, rel), arcname="%s/skills/%s/%s" % (PREFIX, name, rel))
    size = os.path.getsize(out_path)
    print("已出包：%s（%.1f MB%s）" % (out_path, size / 1048576.0, "，精简版" if slim else ""))
    print("编排层 1 个 + 模块 %d 个：%s" % (len(dirs) - 1, "、".join(sorted(k for k in dirs if k != ORCH))))
    print("下一步：python3 %s verify %s" % (os.path.join(HERE, "pack.py"), out_path))
    return 0


def read_manifest(tar):
    try:
        m = tar.extractfile(PREFIX + "/manifest.json")
    except KeyError:
        die("包里没有 manifest.json —— 不是本脚本出的包，或文件被改过")
    return json.loads(m.read().decode("utf-8"))


def verify_tar(path, quiet=False):
    if not os.path.isfile(path):
        die("找不到包：%s" % path)
    with tarfile.open(path, "r:gz") as tar:
        man = read_manifest(tar)
        names = set(tar.getnames())
        bad = []
        for role, e in man.get("roles", {}).items():
            if e.get("shared"):
                continue
            base = "%s/skills/%s" % (PREFIX, e["dir"])
            md = base + "/SKILL.md"
            if md not in names:
                bad.append("%s：包里没有 %s/SKILL.md" % (role, e["dir"]))
                continue
            got = hashlib.sha256(tar.extractfile(md).read()).hexdigest()
            if e.get("sha256_skill_md") and got != e["sha256_skill_md"]:
                bad.append("%s：SKILL.md 指纹不符（包被改过或写坏了）" % role)
            n = sum(1 for x in names if x.startswith(base + "/") and tar.getmember(x).isfile())
            if e.get("files") and n != e["files"]:
                bad.append("%s：文件数 %d，清单写 %d" % (role, n, e["files"]))
    if bad:
        print("✗ 校验不过：")
        for b in bad:
            print("  - " + b)
        return 1
    if not quiet:
        print("✓ 校验通过：%d 个模块，清单与文件指纹一致" % len(man.get("roles", {})))
        print("  出包时间 %s，Python %s%s" % (man.get("created_at"), man.get("python"),
                                          "，精简版" if man.get("slim") else ""))
        for role, e in sorted(man.get("roles", {}).items()):
            print("  %-11s %-34s %s" % (role, e["dir"], e.get("version") or ""))
    return 0


def _native_mod():
    """同目录的 native.py：原生替身表与实测都问它，别在这里抄一份。"""
    sys.path.insert(0, HERE)
    try:
        import native
        return native
    except Exception:
        return None


def cmd_doctor():
    """换机器时先看这一眼：模块齐不等于出得了活，缺的往往是运行它们的那几个依赖。

    mac 上分三段说：原生就能顶的、确实要装的、原先那套备用。顺序反过来就是浪费——
    为了 pdftotext 装一整套 Homebrew，结果 PDFKit 本来就是系统自带的。
    """
    import importlib.util
    import platform as _pf
    import shutil as _sh
    nv = _native_mod()
    mac = _pf.system() == "Darwin"
    print("运行环境：%s %s / %s，Python %s" % (_pf.system(), _pf.release(), _pf.machine(),
                                          sys.version.split()[0]))
    print("  %s" % sys.executable)
    if sys.executable.startswith("/usr/bin/"):
        print("  ！系统 Python 需要 Command Line Tools，缺了会弹窗让你下 2 GB。"
              "先 xcode-select -p 看一眼。")
    print()

    if mac and nv:
        print("一、mac 原生优先（系统自带，先走这里，不要先 brew install）")
        for tool, what, replaces in nv.NATIVE:
            ok = bool(_sh.which(tool))
            print("  %s %s｜%s" % ("OK  " if ok else "缺  ", tool.ljust(11), what))
        pages, chars, why = nv.selftest_pdf()
        if why:
            print("  ！ PDF 通路：%s" % why)
        else:
            print("  OK  PDF 通路实测：PDFKit 读到 %s 页、%d 字 —— 不用装 pdfinfo / pdftotext" % (pages, chars))
        print("      出图：SVG→PNG 用 sips；首页栅格化用 sips --resampleWidth；放大才用 qlmanage")
        print("      Word 取文字：textutil -convert txt（表格摊平、样式丢弃，只够读）")
        print()

    print("二、mac 上也确实要装的（第三方库，装进 venv，别装系统）")
    hard = [("openpyxl", "Excel 母表、对抗分析表"),
            ("docx", "读 .docx 材料（python-docx）"),
            ("pypdf", "多页简表合并成一个 PDF"),
            ("cairosvg", "上游脚本自己出 PNG 时 import 它；只手工补图可改用 sips")]
    miss_hard = []
    for name, why in hard:
        ok = importlib.util.find_spec(name) is not None
        print("  %s %s %s" % ("OK  " if ok else "缺  ", name.ljust(10), why))
        if not ok:
            miss_hard.append(name)
    print()

    print("三、备用（非 mac，或原生顶不住时才装）")
    soft = [("pdftoppm / pdftotext / pdfinfo", "扫描件逐页栅格化（mac 上唯一真缺口）"),
            ("soffice", "SVG 转 PNG 的老路；mac 上用 sips，不必装"),
            ("node", "Word 交付版、溯源索引；缺就看托管的那份绝对路径")]
    miss_soft = []
    for names, why in soft:
        first = names.split(" / ")[0]
        ok = bool(_sh.which(first))
        print("  %s %s %s" % ("OK  " if ok else "缺  ", names.ljust(30), why))
        if not ok:
            miss_soft.append((first, why))
    print()

    if not miss_hard and not miss_soft:
        print("依赖齐备。")
        return 0
    if miss_hard:
        print("要补 %d 个 Python 库，一条命令：" % len(miss_hard))
        print("  %s -m pip install %s" % (sys.executable, " ".join(
            "python-docx" if m == "docx" else m for m in miss_hard)))
        print("  用托管解释器时它就是 venv 里的 python，别加 sudo。")
    if miss_soft:
        print("备用项缺 %d 处。mac 上先用原生路径，真要做扫描件逐页再：" % len(miss_soft))
        print("  brew install poppler     # 只有这一项值得为它装 Homebrew")
    print("这几项决定的只是「能出哪些格式」，不影响编排与探测本身。")
    return 0


def safe_extract(tar, dest):
    """不信任包里的路径：挡掉绝对路径与 .. 越界。"""
    for m in tar.getmembers():
        p = os.path.normpath(os.path.join(dest, m.name))
        if not p.startswith(os.path.normpath(dest) + os.sep) and p != os.path.normpath(dest):
            die("包里有一处路径越界，已中止：%s" % m.name)
        if m.issym() or m.islnk():
            die("包里带链接，已中止：%s" % m.name)
    if hasattr(tarfile, "data_filter"):
        tar.extractall(dest, filter="data")
    else:
        tar.extractall(dest)


def _unquarantine(path):
    """从 U 盘、网盘、微信传过来的包会带 com.apple.quarantine，脚本一跑就被拦。
    mac 上一条 xattr 就解开，不必去「系统设置 → 隐私与安全性」里逐个点允许。"""
    if not shutil.which("xattr"):
        return
    subprocess.run(["xattr", "-dr", "com.apple.quarantine", path],
                   capture_output=True, timeout=120)


def cmd_install(argv):
    path, to, force = None, None, "--force" in argv
    for i, a in enumerate(argv):
        if a in ("-t", "--to") and i + 1 < len(argv):
            to = os.path.abspath(os.path.expanduser(argv[i + 1]))
        elif not a.startswith("-") and path is None and a not in ("install",):
            path = a
    if not path or not to:
        die("用法：pack.py install 包.tar.gz --to 技能根目录 [--force]")
    if verify_tar(path, quiet=True) != 0:
        die("包没通过校验，不装")
    os.makedirs(to, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="legal-bundle-")
    try:
        with tarfile.open(path, "r:gz") as tar:
            safe_extract(tar, tmp)
        src = os.path.join(tmp, PREFIX, "skills")
        if not os.path.isdir(src):
            die("包里没有 skills/ 目录")
        installed, skipped = [], []
        for name in sorted(os.listdir(src)):
            s = os.path.join(src, name)
            if not os.path.isdir(s):
                continue
            dst = os.path.join(to, name)
            if os.path.exists(dst) and not force:
                skipped.append(name)
                continue
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(s, dst)
            _unquarantine(dst)
            installed.append(name)
        print("装到：%s" % to)
        print("  新装 %d 个：%s" % (len(installed), "、".join(installed) or "—"))
        if skipped:
            print("  已存在、未覆盖 %d 个：%s（要覆盖加 --force）" % (len(skipped), "、".join(skipped)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print()
    print("装上了不等于接得通，接着验一次探测：")
    r = subprocess.run([sys.executable, os.path.join(to, ORCH, "scripts", "bind.py"),
                        "--roots", to, "--plan"])
    print()
    cmd_doctor()
    print("之后在这个根目录里用：python3 %s/scripts/flow.py next 案目录"
          % os.path.join(to, ORCH))
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0 if argv else 2
    cmd = argv[0]
    if cmd == "pack":
        return cmd_pack(argv[1:])
    if cmd == "verify":
        rest = [a for a in argv[1:] if not a.startswith("-")]
        if not rest:
            die("要给出包路径")
        return verify_tar(rest[0])
    if cmd == "install":
        return cmd_install(argv[1:])
    if cmd == "doctor":
        return cmd_doctor()
    die("不认识的子命令 %r，只有 pack / verify / install / doctor" % cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
