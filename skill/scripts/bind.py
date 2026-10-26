#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按能力角色探测并绑定本机已安装的法律模块。零第三方依赖。

为什么不写死技能名：换 agent、换作者、上游改名、只装其中几个，都是常态。
所以本脚本只认 capabilities.json 里的「角色」，把角色映射到实际目录，
并核对那个目录是不是它自称的那个模块（SKILL.md 的 name 字段 + 关键脚本齐备）。

用法：
    python3 bind.py                    打印绑定表
    python3 bind.py --check            有必需角色没绑上就退出 1
    python3 bind.py --require facts,structure
    python3 bind.py --plan             按阶段打印这条链，标出已绑 / 缺失
    python3 bind.py --json             输出机器可读的绑定结果
    python3 bind.py --roots A:B        只在这几个根里找（换 agent、做迁移测试时用）

覆盖：
    ~/.legal-case-flow/bindings.json   {"facts": "/abs/path/to/skill", ...}
    环境变量 LEGAL_CASE_FLOW_ROOTS     用 os.pathsep 分隔的额外搜索根
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAPS = os.path.join(os.path.dirname(HERE), "capabilities.json")
OVERRIDE = os.path.join(os.path.expanduser("~"), ".legal-case-flow", "bindings.json")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def frontmatter(path):
    """只取 name 与 version。不引 yaml：这两行足够判定是不是同一个模块。"""
    out = {}
    try:
        with open(path, encoding="utf-8") as f:
            head = [next(f, "") for _ in range(60)]
    except OSError:
        return out
    for line in head:
        m = re.match(r"^name:\s*(\S+)\s*$", line)
        if m and "name" not in out:
            out["name"] = m.group(1)
        m = re.match(r"^\s+version:\s*(\S+)\s*$", line) or re.match(r"^version:\s*(\S+)\s*$", line)
        if m and "version" not in out:
            out["version"] = m.group(1)
    return out


def pad(text, width):
    """按显示宽度补空格：中文占两格，不补就整列歪。"""
    text = str(text)
    w = sum(2 if ord(c) > 0x2E80 else 1 for c in text)
    return text + " " * max(0, width - w)


def search_roots(caps, given=None):
    # 自己所在的根永远排第一：包被搬到别处、装到同事机器上，
    # 它得先认自己旁边的同批模块，而不是回头去认原来那台机器上的。
    roots = [os.path.dirname(os.path.dirname(HERE))]
    if given:
        roots.extend([p for p in given.split(os.pathsep) if p.strip()])
    else:
        env = os.environ.get("LEGAL_CASE_FLOW_ROOTS", "")
        for part in [p for p in env.split(os.pathsep) if p.strip()]:
            roots.append(part)
        roots.extend(caps.get("search_roots", []))
    seen, out = set(), []
    for r in roots:
        p = os.path.abspath(os.path.expanduser(r))
        if p not in seen and os.path.isdir(p):
            seen.add(p)
            out.append(p)
    return out


def probe(skill_dir, spec):
    """返回 (ok, reasons, meta)。reasons 为空即通过。"""
    reasons = []
    meta = {}
    md = os.path.join(skill_dir, spec.get("skill_md", "SKILL.md"))
    if not os.path.isfile(md):
        return False, ["缺 %s" % os.path.basename(md)], meta
    meta = frontmatter(md)
    want = spec.get("name_field")
    if want and meta.get("name") != want:
        reasons.append("SKILL.md 的 name 是 %r，不是 %r" % (meta.get("name"), want))
    miss = [s for s in spec.get("scripts", []) if not os.path.isfile(os.path.join(skill_dir, s))]
    if miss:
        reasons.append("缺脚本 " + "、".join(miss))
    return (not reasons), reasons, meta


def bind(caps, given=None):
    roots = search_roots(caps, given)
    overrides = {}
    if os.path.isfile(OVERRIDE):
        try:
            overrides = load_json(OVERRIDE)
        except (OSError, ValueError) as e:
            print("！绑定覆盖文件读不出来，已忽略：%s（%s）" % (OVERRIDE, e), file=sys.stderr)
    result = {}
    for role, spec in caps.get("roles", {}).items():
        entry = {"role": role, "label": spec.get("label", role), "stage": spec.get("stage", 9),
                 "status": "missing", "dir": None, "version": None, "reasons": [], "source": None}
        cand = overrides.get(role)
        if cand:
            d = os.path.abspath(os.path.expanduser(cand))
            ok, reasons, meta = probe(d, spec.get("probe", spec))
            entry.update(dir=d, version=meta.get("version"), reasons=reasons, source="覆盖")
            entry["status"] = "bound" if ok else "broken"
        else:
            for root in roots:
                for name in spec.get("candidates", []):
                    d = os.path.join(root, name)
                    if not os.path.isdir(d):
                        continue
                    ok, reasons, meta = probe(d, spec.get("probe", spec))
                    entry.update(dir=d, version=meta.get("version"), reasons=reasons, source=root)
                    entry["status"] = "bound" if ok else "broken"
                    break
                if entry["dir"]:
                    break
        result[role] = entry
    return result, roots


def main(argv):
    if argv and argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    caps = load_json(CAPS)
    given = None
    for i, a in enumerate(argv):
        if a == "--roots" and i + 1 < len(argv):
            given = argv[i + 1]
    result, roots = bind(caps, given)
    check = "--check" in argv
    plan = "--plan" in argv
    as_json = "--json" in argv
    required = ["facts"]
    for i, a in enumerate(argv):
        if a == "--require" and i + 1 < len(argv):
            required = [r.strip() for r in argv[i + 1].split(",") if r.strip()]

    if as_json:
        print(json.dumps({"roots": roots, "roles": result}, ensure_ascii=False, indent=1))
    elif plan:
        print("搜索根：")
        for r in roots:
            print("  " + r)
        print()
        print("阶段  角色        状态     模块 / 版本")
        for role in sorted(result.values(), key=lambda e: (e["stage"], e["role"])):
            if role["status"] == "bound":
                print("  %s   %s已绑   %s %s" % (role["stage"], pad(role["role"], 12),
                                              os.path.basename(role["dir"]), role["version"] or ""))
            elif role["status"] == "broken":
                print("  %s   %s探测不过  %s" % (role["stage"], pad(role["role"], 12),
                                            "；".join(role["reasons"])))
            else:
                print("  %s   %s未安装  （这一阶段跳过）" % (role["stage"], pad(role["role"], 12)))
        print()
        for role in sorted(result.values(), key=lambda e: (e["stage"], e["role"])):
            if role["status"] == "bound":
                print("· %s → %s" % (role["label"], caps["roles"][role["role"]].get("next", "")))
    else:
        print("搜索根：%s" % ("、".join(roots) if roots else "（没有可用的技能目录）"))
        print()
        for role in sorted(result.values(), key=lambda e: (e["stage"], e["role"])):
            mark = {"bound": "OK  ", "broken": "坏  ", "missing": "缺  "}[role["status"]]
            where = os.path.basename(role["dir"]) if role["dir"] else "—"
            ver = role["version"] or ""
            note = "" if role["status"] == "bound" else "：" + "；".join(role["reasons"] or ["没找到候选目录"])
            print("%s %s%s %s%s%s" % (mark, pad(role["role"], 12), pad(role["label"], 20), pad(where, 34), ver, note))
        if os.path.isfile(OVERRIDE):
            print("\n（已叠加覆盖文件 %s）" % OVERRIDE)

    if check:
        bad = [r for r in required if result.get(r, {}).get("status") != "bound"]
        if bad:
            print("\n必需角色没绑上：%s" % "、".join(bad), file=sys.stderr)
            return 1
        print("\n必需角色齐备：%s" % "、".join(required))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
