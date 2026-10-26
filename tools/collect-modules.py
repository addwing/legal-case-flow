#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把本机已装的上游模块收成一份可分发的包，给同事或另一台机器用。零依赖。

本仓库不含那七个可视化模块（它们是缪奇川的独立作品）。所以在已经装好模块的机器上
用这个脚本收一份，拷到新机器，再用 ./install.sh --modules 装。

    python3 tools/collect-modules.py                      # 出 ./legal-case-modules-<日期>.tar.gz
    python3 tools/collect-modules.py -o ~/Desktop/m.tar.gz
    python3 tools/collect-modules.py --from ~/别的技能根
    python3 tools/collect-modules.py --slim               # 去掉 assets/ 与 tests/
    python3 tools/collect-modules.py --list               # 只列会收哪些，不打包

包里是原样目录 + 一份 manifest.json，一个字节也没改。每个模块的 SKILL.md
随包带走，`metadata.author` 与 `metadata.license` 因此不会丢。
"""
import io
import json
import os
import re
import sys
import tarfile
import time

SKILL_NAMES = ("~/.workbuddy/skills", "~/.claude/skills", "~/.codex/skills")
SLIM_EXCLUDE = {"assets", "tests", "__pycache__", ".git"}
JUNK = {".DS_Store", ".localized"}
SCHEMA = "legal-case-modules/1"


def die(msg, code=2):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(code)


def frontmatter(path):
    """只取 name / version / author / license，不引 yaml。"""
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            head = [next(f, "") for _ in range(40)]
    except OSError:
        return out
    for line in head:
        for key in ("name", "version", "author", "license"):
            m = re.match(r"^\s*%s:\s*(\S.*?)\s*$" % key, line)
            if m and key not in out:
                out[key] = m.group(1).strip()
    return out


def roots(given):
    if given:
        return [os.path.abspath(os.path.expanduser(given))]
    return [os.path.abspath(os.path.expanduser(r)) for r in SKILL_NAMES
            if os.path.isdir(os.path.abspath(os.path.expanduser(r)))]


def find_modules(root):
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        d = os.path.join(root, name)
        if not os.path.isdir(d) or not name.startswith("mqc-"):
            continue
        md = os.path.join(d, "SKILL.md")
        if not os.path.isfile(md):
            print("· 跳过 %s（没有 SKILL.md）" % name)
            continue
        meta = frontmatter(md)
        if meta.get("name") != name:
            print("· 跳过 %s（SKILL.md 自报名字是 %r，对不上，不硬收）"
                  % (name, meta.get("name")))
            continue
        out.append((name, d, meta))
    return out


def files_of(base, slim):
    out = []
    for dirpath, dirnames, filenames in os.walk(base):
        if slim:
            dirnames[:] = [x for x in dirnames if x not in SLIM_EXCLUDE]
        dirnames[:] = [x for x in dirnames if x != "__pycache__"]
        for fn in filenames:
            if fn in JUNK or fn.startswith("._") or fn.endswith(".pyc"):
                continue
            out.append(os.path.relpath(os.path.join(dirpath, fn), base))
    return sorted(out)


def main(argv):
    out_path = os.path.join(os.getcwd(), "legal-case-modules-%s.tar.gz" % time.strftime("%Y%m%d"))
    given, slim, only_list = None, False, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("-o", "--out") and i + 1 < len(argv):
            out_path = os.path.abspath(os.path.expanduser(argv[i + 1])); i += 2
        elif a == "--from" and i + 1 < len(argv):
            given = argv[i + 1]; i += 2
        elif a == "--slim":
            slim = True; i += 1
        elif a == "--list":
            only_list = True; i += 1
        elif a in ("-h", "--help", "help"):
            print(__doc__.strip()); return 0
        else:
            die("不认识的参数：%s（-h 看用法）" % a)

    mods = []
    for r in roots(given):
        for name, d, meta in find_modules(r):
            if any(m[0] == name for m in mods):
                continue
            mods.append((name, d, meta))
            print("收 %s  %s  %s" % (name.ljust(34), (meta.get("version") or "").ljust(8),
                                     meta.get("author") or ""))
    if not mods:
        die("这个搜索范围里一个 mqc-* 模块都没有。用 --from 指定技能根目录，"
            "或先确认模块装在哪。")

    if only_list:
        print("\n只列不收（--list）。去掉 --list 就打包。")
        return 0

    manifest = {
        "schema": SCHEMA,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "slim": slim,
        "note": "上游模块为第三方作品（作者见各模块 SKILL.md 的 metadata.author，MIT），"
                "本包原样收拢，未修改任何字节。装法：./install.sh --modules 本包",
        "modules": [],
    }
    total = 0
    for name, d, meta in mods:
        fs = files_of(d, slim)
        size = sum(os.path.getsize(os.path.join(d, f)) for f in fs)
        total += size
        manifest["modules"].append({
            "dir": name,
            "version": meta.get("version"),
            "author": meta.get("author"),
            "license": meta.get("license"),
            "files": len(fs),
            "bytes": size,
        })

    payload = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")
    with tarfile.open(out_path, "w:gz") as tar:
        info = tarfile.TarInfo("manifest.json")
        info.size, info.mtime = len(payload), int(time.time())
        tar.addfile(info, io.BytesIO(payload))
        for name, d, meta in mods:
            for rel in files_of(d, slim):
                tar.add(os.path.join(d, rel), arcname="%s/%s" % (name, rel))

    print("\n已出包：%s（%.1f MB%s）" % (out_path, os.path.getsize(out_path) / 1048576.0,
                                    "，精简版" if slim else ""))
    print("模块 %d 个，源文件 %d 个文件 / %.1f MB" % (
        len(mods), sum(m["files"] for m in manifest["modules"]), total / 1048576.0))
    print("\n到新机器上：")
    print("  ./install.sh --modules %s" % os.path.basename(out_path))
    print("\n或者解开后看 manifest.json，核对每个模块的作者与许可。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
