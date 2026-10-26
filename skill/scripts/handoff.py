#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把大事记的底稿转成下游两份输入的骨架。零第三方依赖。

这一层只做机械搬运：底稿里有的照搬，底稿里没有的一律留空并列出待办。
它不写法律判断，也不假装产物能直接出图 —— 骨架是给模型和律师往上填的。

用法：
    python3 handoff.py matrix    底稿.json -o matrix-input.json [--index 事实挂载表.md]
    python3 handoff.py relations 底稿.json -o relations.json
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

DOC_KINDS = ["起诉状", "反诉状", "答辩状", "上诉状", "判决书", "裁决书",
             "证据目录", "代理意见", "质证意见", "鉴定意见", "合同", "笔录"]

OBJ_KW = ("合同", "协议", "工程", "款项", "标的物")
OBJ_NO = ("通知", "文件", "说明", "目录", "清单", "状", "判决", "裁定", "笔录",
          "函", "澄清", "封面", "表格", "情况", "意见")


def die(msg, code=2):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(code)


def load_casefile(path):
    if not os.path.isfile(path):
        die("找不到底稿：%s" % path)
    with open(path, encoding="utf-8") as f:
        try:
            d = json.load(f)
        except ValueError as e:
            die("底稿不是合法 JSON：%s" % e)
    if d.get("schema") != "mqc-casefile/1":
        print("！底稿的 schema 是 %r，不是 mqc-casefile/1 —— 按最小字段继续试"
              % d.get("schema"), file=sys.stderr)
    for key in ("case", "materials", "parties", "facts"):
        if key not in d:
            die("底稿缺 %s，无法转接（可用字段：%s）" % (key, "、".join(d.keys())))
    return d


def bound_dir(role):
    """问一次绑定表要真实路径，好把下一步命令写具体。问不到就给空。"""
    try:
        out = subprocess.run([sys.executable, os.path.join(HERE, "bind.py"), "--json"],
                             capture_output=True, text=True, timeout=30)
        if out.returncode != 0 or not out.stdout.strip():
            return ""
        return (json.loads(out.stdout).get("roles", {}).get(role) or {}).get("dir") or ""
    except (OSError, ValueError, subprocess.SubprocessError):
        return ""


def doc_kinds(materials):
    names = [m.get("name", "") for m in materials]
    got = [k for k in DOC_KINDS if any(k in n for n in names)]
    return got, [k for k in DOC_KINDS if k not in got]


def case_title(cf):
    c = cf.get("case", {})
    t = (c.get("title") or "未命名案件").strip()
    p = (c.get("program") or "").strip()
    return "%s（%s）" % (t, p) if p else t


def write_json(path, obj):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def cmd_matrix(cf, out, index_path):
    got, miss = doc_kinds(cf.get("materials", []))
    rec = cf.get("reconcile", {}) or {}
    facts = cf.get("facts", [])
    anchor = rec.get("external_anchor") or "（底稿未写对账锚）"
    skeleton = {
        "case": {
            "title": "庭审对抗分析表　·　" + case_title(cf),
            "procedural": {"jurisdiction": "", "parties": "", "res_judicata": ""},
            "triage": "",
            "stance": "",
            "counterattacks": [],
        },
        "claims": [],
        "parts": [],
        "scope": {
            "obtained": got,
            "not_obtained": miss,
            "maturity": "",
            "note": "材料 %d 份，%d 条事实；对账锚：%s" % (len(cf.get("materials", [])), len(facts), anchor),
        },
    }
    write_json(out, skeleton)

    if not index_path:
        index_path = os.path.splitext(out)[0] + "-事实挂载表.md"
    lines = ["# 事实挂载表（由底稿机械导出，供把要件挂到事实上时引用）", "",
             "> 底稿：`%s`　共 %d 条事实。" % (os.path.basename(cf.get("case", {}).get("cid", "")), len(facts)),
             "> F 编号只作人工对账，不写进 matrix-input.json：V5 对四段正文有照录判据，",
             "> 往里面塞编号会触碰判据。挂要件时在分析表的「待证事实」里写清即可。", ""]
    by_mid = {m.get("mid"): m.get("name", "") for m in cf.get("materials", [])}
    for f in facts:
        certain = {"exact": "", "month": "（仅到月）", "year": "（仅到年）", "range": "（区间）"}
        lines.append("### %s · %s%s · %s" % (f.get("fid"), f.get("date", "日期不详"),
                                             certain.get(f.get("date_certainty"), ""), f.get("item", "")))
        lines.append("证据：%s ｜ 出处：%s %s" % (f.get("evidence_no") or "（无编号）",
                                              f.get("mid", ""), f.get("locator", "")))
        lines.append("")
        lines.append("> " + (f.get("content") or "").replace("\n", " "))
        lines.append("")
    if cf.get("uncertainties"):
        lines.append("## 底稿里已标的不确定项")
        lines.append("")
        for u in cf["uncertainties"]:
            lines.append("- %s：%s（%s）" % (u.get("fid"), u.get("what"), u.get("why")))
        lines.append("")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    v5 = bound_dir("adversary")
    print("已写：%s" % out)
    print("已写：%s" % index_path)
    print()
    print("这份骨架现在**不能出图**，下面这些底稿里没有，得由人填或由模型推：")
    print("  □ case.stance：我代理谁（原告向 / 被告向）—— 必须问律师，底稿推不出来")
    print("  □ case.procedural：管辖 / 主体 / 重复起诉，三项都要写到")
    print("  □ scope.maturity：L0／L1／L2／L3，按材料齐备程度定")
    print("  □ claims：诉请逐条固定，类型取自封闭表，金额要有构成明细")
    print("  □ parts／elements：请求权基础 → 要件拆解 → 四段攻防，四段正文照录")
    print()
    print("已自动填的：标题、材料范围（获得 %d 类 / 缺 %d 类）、对账锚、事实索引 %d 条"
          % (len(got), len(miss), len(facts)))
    if v5:
        print("填完先跑：python3 %s/scripts/check_claims.py %s" % (v5, out))
    else:
        print("（没绑到庭审对抗图模块，跳过校验命令）")


def cmd_relations(cf, out):
    parties = cf.get("parties", [])
    nodes = []
    for p in parties:
        roles = [r for r in (p.get("roles_verbatim") or []) if r]
        nodes.append({"id": p.get("pid", ""), "name": p.get("name", ""),
                      "note": "·".join(roles[:3]) if roles else "", "kind": "主体"})
    objs = []
    for m in cf.get("materials", []):
        n = m.get("name", "")
        if any(k in n for k in OBJ_KW) and not any(x in n for x in OBJ_NO):
            objs.append({"id": "C%d" % (len(objs) + 1), "name": n,
                         "note": "%s·候选客体" % m.get("mid", ""), "kind": "客体"})
    data = {
        "slug": (cf.get("case", {}).get("cid") or "case").lower().replace(" ", "-"),
        "title": case_title(cf) + " · 法律关系图",
        "sources": [m.get("name", "") for m in cf.get("materials", [])],
        "nodes": nodes + objs,
        "edges": [],
    }
    write_json(out, data)
    v3 = bound_dir("structure")
    print("已写：%s" % out)
    print()
    print("主体 %d 个（照录底稿 parties，pid 原样保留）、客体候选 %d 个（按材料名筛的，需你确认要不要）"
          % (len(nodes), len(objs)))
    print()
    print("现在**还不能出图**：")
    print("  □ edges 一条都没有 —— 关系名与指向必须照录原文，脚本猜不出来")
    print("  □ 客体候选只按材料名筛，招标文件、通知书这类被排除了，但可能有漏或有错")
    print("  □ 模块上限 9 个、关系上限 12 条；超了 make.py 会停在第〇轮要你取舍")
    if len(nodes) + len(objs) > 9:
        print("  ! 现在 %d 个模块，已超 9：先按要紧程度删，别硬塞" % (len(nodes) + len(objs)))
    if v3:
        print()
        print("填完先跑：python3 %s/scripts/make.py %s --plan-only" % (v3, out))
        print("过规模判断后再出图：make.py %s --out 出图目录" % out)


def main(argv):
    if len(argv) < 2 or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    sub, src = argv[0], argv[1]
    out = index = ""
    for i, a in enumerate(argv):
        if a in ("-o", "--out") and i + 1 < len(argv):
            out = argv[i + 1]
        if a == "--index" and i + 1 < len(argv):
            index = argv[i + 1]
    if not out:
        die("要写 -o 输出路径")
    cf = load_casefile(src)
    if sub == "matrix":
        cmd_matrix(cf, out, index)
    elif sub == "relations":
        cmd_relations(cf, out)
    else:
        die("不认识的子命令 %r，只有 matrix / relations" % sub)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
