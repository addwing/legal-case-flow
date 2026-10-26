#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一宗案子的工作目录与下一步。零第三方依赖。

它只做两件事：把案子的目录摆好；按目录里已有的产物判断走到哪一步、下一步该敲什么。
它不替你跑上游管线——那几家都有必须问人的步骤（勾材料、勾时段、定风格），
一口气跑完等于替你答了。

用法：
    python3 flow.py init 案目录 [--title 案件名]
    python3 flow.py next 案目录
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from handoff import bound_dir  # noqa: E402  同一个技能内复用，省一套重复的探测

DIRS = ["材料", "产物/大事记", "产物/时间轴", "产物/关系图", "产物/对抗图", "产物/课件"]


def die(msg, code=2):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(code)


def shq(p):
    """打印给人复制的路径：含空格就加引号，否则照抄会被 shell 拆成两个参数。"""
    p = str(p)
    if any(c.isspace() for c in p):
        return "'%s'" % p
    return p


def py(role, script):
    """返回可粘贴的命令前缀；角色没绑上就返回 None。"""
    d = bound_dir(role)
    if not d:
        return None
    return "python3 %s" % shq(os.path.join(d, "scripts", script))


def files_in(path):
    if not os.path.isdir(path):
        return []
    out = []
    for dirpath, _, filenames in os.walk(path):
        for fn in filenames:
            if not fn.startswith("."):
                out.append(os.path.join(dirpath, fn))
    return out


def cmd_init(argv):
    if not argv:
        die("用法：flow.py init 案目录 [--title 案件名]")
    case = os.path.abspath(os.path.expanduser(argv[0]))
    title = ""
    for i, a in enumerate(argv):
        if a == "--title" and i + 1 < len(argv):
            title = argv[i + 1]
    for d in DIRS:
        os.makedirs(os.path.join(case, d), exist_ok=True)
    meta = os.path.join(case, "flow.json")
    if os.path.isfile(meta):
        print("这个目录已经有 flow.json，不覆盖：%s" % meta)
    else:
        with open(meta, "w", encoding="utf-8") as f:
            json.dump({"title": title or os.path.basename(case),
                       "cid": os.path.basename(case),
                       "created": time.strftime("%Y-%m-%d")},
                      f, ensure_ascii=False, indent=1)
        print("已建案目录：%s" % case)
    print()
    print("把材料丢进 %s" % os.path.join(case, "材料"))
    print("放好之后跑：python3 %s next %s" % (shq(os.path.join(HERE, "flow.py")), shq(case)))
    return 0


def stage_state(case):
    """按产物判断，不看自称。返回 (第几步, 名称, 已就绪说明, [命令], 交接说明)。"""
    m = os.path.join(case, "材料")
    w = os.path.join(case, "产物", "大事记")
    cf = os.path.join(w, "casefile.json")
    mats = files_in(m)
    made = files_in(w)

    if not mats:
        return (0, "放材料", "材料目录是空的",
                ["把起诉状、合同、证据、判决书、扫描件原样放进 %s 就行，不必先整理格式" % m],
                "")

    if not os.path.isfile(cf):
        ing = py("facts", "ingest.py")
        chk = py("facts", "check_facts.py")
        cmds = []
        if ing:
            cmds.append("%s %s/* %s" % (ing, m, w))
        cmds.append("（这一步由模型做）照 %s/references/casefile-guide.md 把材料读成 %s"
                    % (os.path.dirname(os.path.dirname(ing)) if ing else "<大事记模块>",
                       os.path.join(w, "casefile.json")))
        if chk:
            src = os.path.join(w, "sources.json")
            cmds.append("%s %s%s" % (chk, cf, (" " + src) if os.path.isfile(src) else ""))
        ready = "材料 %d 份" % len(mats)
        if os.path.isfile(os.path.join(w, "materials.json")):
            ready += "，材料清单已出（materials.json）"
        return (1, "事实底稿", ready, cmds,
                "产物/大事记/casefile.json（F001 起编，后面所有图都靠这个编号对齐）")

    if not made or not any(f.endswith((".docx", ".xlsx")) for f in made):
        pipe = py("facts", "pipeline.py")
        src = os.path.join(w, "sources.json")
        # pipeline.py 的第二个位置参数是 sources.json，第三个才是输出目录；
        # 没有 sources 时必须拿一对空引号占位，否则输出目录会被当成 sources 读。
        cmds = []
        if pipe:
            if os.path.isfile(src):
                cmds.append("%s %s %s %s" % (pipe, shq(cf), shq(src), shq(w)))
            else:
                cmds.append('%s %s "" %s' % (pipe, shq(cf), shq(w)))
                cmds.append("（中间那对空引号是 sources.json 的位置，没有就留空，别删）")
        cmds.append("要简表另跑 build_brief.py → export_brief.py，见大事记 SKILL.md 的工作流一节")
        return (1, "事实底稿（已写底稿，未出交付物）",
                "底稿 %d 条事实" % len(json.load(open(cf, encoding="utf-8-sig")).get("facts", [])),
                cmds, "Word 交付版 + Excel 母表 + 简表")

    rel = os.path.join(case, "产物", "关系图", "relations.json")
    mat = os.path.join(case, "产物", "对抗图", "matrix-input.json")
    deck = os.path.join(case, "产物", "课件", "deck.json")

    if not os.path.isfile(rel) and not os.path.isfile(mat):
        h = os.path.join(HERE, "handoff.py")
        return (2, "结构 / 攻防（二选一或都做）",
                "底稿已出交付物",
                ["python3 %s relations %s -o %s" % (shq(h), shq(cf), shq(rel)),
                 "python3 %s matrix %s -o %s" % (shq(h), shq(cf), shq(mat)),
                 "两份都是骨架，填完再出图；骨架的待办清单会自己列出来"],
                "relations.json / matrix-input.json")

    # 关系图与对抗图是并行的两条，谁也不挡谁：两边都还在填的时候，两边的下一步一起给
    blocks, ready = [], []
    mk = py("structure", "make.py")
    if os.path.isfile(rel):
        try:
            edges = json.load(open(rel, encoding="utf-8-sig")).get("edges", [])
        except ValueError:
            edges = []
        if not edges:
            ready.append("关系图草案（edges 空）")
            blocks += ["—— 法律关系图：草案还没有关系 ——",
                       "把关系名与指向照录原文补进 %s（脚本不生成关系）" % rel]
            if mk:
                blocks.append("%s %s --plan-only" % (mk, shq(rel)))
        else:
            ready.append("关系图已填")
            if mk:
                blocks += ["—— 法律关系图 ——",
                           "%s %s --plan-only" % (mk, shq(rel)),
                           "%s %s --out %s --shape wide" % (mk, shq(rel), shq(os.path.join(case, "产物", "关系图")))]
    if os.path.isfile(mat):
        chk = py("adversary", "check_claims.py")
        bm = py("adversary", "build_matrix.py")
        rm = py("adversary", "render_main.py")
        out = os.path.join(case, "产物", "对抗图")
        try:
            D = json.load(open(mat, encoding="utf-8-sig"))
        except ValueError:
            D = {}
        filled = bool(D.get("case", {}).get("stance")) and bool(D.get("parts"))
        ready.append("对抗图%s" % ("已填" if filled else "骨架未填"))
        blocks.append("—— 庭审对抗图%s ——" % ("" if filled else "：骨架还没填"))
        if chk:
            blocks.append("%s %s" % (chk, shq(mat)))
        if not filled:
            blocks.append("校验报 P1 / M1 / T2，就是程序站、成熟度、立场三项还没写")
        if bm:
            blocks.append("%s %s %s" % (bm, shq(mat), shq(os.path.join(out, "庭审对抗分析表.xlsx"))))
        if rm:
            blocks.append("%s %s %s" % (rm, shq(mat), shq(os.path.join(out, "庭审对抗.svg"))))
    if blocks:
        return (2, "结构 / 攻防", "、".join(ready), blocks,
                "relations.json / matrix-input.json；对抗图不出 -trace.json，课件里只能整张放")

    if not os.path.isfile(deck):
        bd = py("deck", "build.py")
        cmds = ["%s %s --new --title %s" % (bd, shq(os.path.join(case, "产物", "课件")), "案件汇报")] if bd else []
        cmds.append("把各层的 svg 与同名 -trace.json 放进 课件/assets/")
        cmds.append("%s %s --check" % (bd, shq(os.path.join(case, "产物", "课件"))) if bd else "")
        return (3, "课件", "图都有了吗", [c for c in cmds if c], "pptx")
    return (4, "收尾", "各层产物齐了",
            ["%s %s" % (py("deck", "build.py"), shq(os.path.join(case, "产物", "课件")))
             if py("deck", "build.py") else "（课件模块未绑定）"],
            "")


def cmd_next(argv):
    if not argv:
        die("用法：flow.py next 案目录")
    case = os.path.abspath(os.path.expanduser(argv[0]))
    if not os.path.isdir(case):
        die("没有这个目录：%s" % case)
    if not os.path.isfile(os.path.join(case, "flow.json")):
        print("！（这个目录没有 flow.json，按普通目录判断；要建规范目录用 flow.py init）\n")
    step, name, ready, cmds, handoff = stage_state(case)
    print("现在：第 %d 步 · %s" % (step, name))
    if ready:
        print("已就绪：%s" % ready)
    print()
    for c in cmds:
        if not c:
            continue
        if c.startswith("（"):
            print("  " + c)
        else:
            print("  " + c)
    if handoff:
        print()
        print("这一步交出：%s" % handoff)
    print()
    print("命令里的路径都来自当前绑定；模块换位置了先跑 bind.py --plan 看一眼。")
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    if argv[0] == "init":
        return cmd_init(argv[1:])
    if argv[0] == "next":
        return cmd_next(argv[1:])
    die("不认识的子命令 %r，只有 init / next" % argv[0])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
