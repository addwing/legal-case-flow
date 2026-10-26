# 设计

这一页解释三件事：为什么不合并成一个 skill、七个角色是怎么绑上去的、哪些地方**故意没打通**。

---

## 为什么不合并

七个模块加起来约 1500 行 SKILL.md、四万 token，每个自带几十到两千多条回归判据，
彼此还检查「一个字节没变」。合并会付出三样代价：

1. **拆掉守卫。** 那些判据是作者用真实卷宗喂出来的，合并即重写，重写即失效。
2. **上下文成本。** 一次对话里塞七个模块的全部规则，模型反而抓不住当前该干什么。
3. **版本锁死。** 上游改一版，你得跟着合一次；不合并，它改它的，这边重新探测即可。

所以这一层只做**编排**：谁先谁后、交什么、缺了怎么办。

---

## 角色制：唯一认人的地方

`capabilities.json` 把七个**角色**映射到**候选目录名**：

```json
"facts": {
  "label": "事实底稿（大事记）",
  "stage": 1,
  "candidates": ["mqc-chronicle-master"],
  "probe": {
    "skill_md": "SKILL.md",
    "name_field": "mqc-chronicle-master",
    "scripts": ["scripts/ingest.py", "scripts/check_facts.py", "scripts/to_render.py"]
  }
}
```

换作者、换目录名、上游改名，**只改这一份，脚本与文档一个字都不用动**。
这是「可移植」的全部秘密：绑的是能力，不是名字。

角色共七个：

| 角色 | 阶段 | 干什么 |
| --- | --- | --- |
| `facts` | 1 | 事实底稿、大事记、母表、简表 |
| `structure` | 2 | 法律关系图 |
| `adversary` | 2 | 庭审对抗图、17 列分析表 |
| `chronology` | 2 | 案件时间轴（旁路） |
| `data` | 3 | 法律数据图（类案统计） |
| `deck` | 3 | 课件容器 |
| `redraw` | 3 | 重画外部旧图 |

---

## 探测为什么要验三样

只看「目录在不在」不够。三种情况会让人拿错模块硬跑：

- 同名但换了作者的模块（更新内容，名字没改）
- 目录名对，但关键脚本被删或改名（版本不兼容）
- `SKILL.md` 的 `name` 与目录名不一致（拷贝时改了名）

所以 `probe()` 验三样：**目录存在 + `SKILL.md` 的 `name` 对得上 + 关键脚本齐**。
有一项不过就标 `broken` 并说明原因，**不硬用**。

---

## 契约：只读最小字段

跨版本的锚点不是「结构一样」，而是「这几个字段一定在」：

| 文件 | 只读这些 | 不许动 |
| --- | --- | --- |
| `casefile.json` | `case.cid`、`case.title`、`materials[].mid`、`parties[].pid`、`facts[].fid` | F 编号一旦分配不再变 |
| `relations.json` | `nodes[].id/name/kind`、`edges[].from/to/label` | `kind` 只有主体/客体；关系名照录 |
| `matrix-input.json` | `case.title/stance`、`claims[]`、`parts[].claim_bases[].elements[]` | 四段正文照录；条号案号不编 |

上游加字段，这边不报错（只读需要的）。上游改字段名，`bind.py` 探测会先报出来。

---

## 两处故意没打通的缝

**① F 编号没有真正流到下游。**
三件法宝都说「读同一份底稿」，但 `relations-guide.md` 与庭审的 `casefile-guide.md`
里没有一处引用 `F` 编号，而且两边的 `casefile.json` 是两套结构。
所以编号只能**人工对账**——`handoff.py` 出的《事实挂载表》就是给这个用的。

**② 两份产物没有 `-trace.json`。**
`adversary` 与 `facts` 的简表都不出溯源文件，进课件只能整张放、没有逐项出处。
`chronology` 与 `structure` 有。

这两处不修，是因为修它们要改上游；本层的态度是**摆明**，而不是悄悄糊过去。

---

## 加一个新角色（不写代码）

假设你有一套「证据目录生成器」，想接进来：

```json
"evidence": {
  "label": "证据目录",
  "stage": 2,
  "candidates": ["my-evidence-master"],
  "probe": {
    "skill_md": "SKILL.md",
    "name_field": "my-evidence-master",
    "scripts": ["scripts/build.py"]
  },
  "emits": ["证据目录.docx"],
  "next": "从 casefile.json 的 materials 取编号与页码"
}
```

`bind.py` 立刻能探测它，`flow.py next` 会把它排进阶段。
不需要改任何 `.py` 或 `SKILL.md`。

---

## 目录结构

```
skill/
├── SKILL.md            # 给 agent 读的编排规则（含弯路清单）
├── capabilities.json   # 角色表：唯一认人的地方
└── scripts/
    ├── bind.py         # 探测与绑定
    ├── handoff.py      # 两处机械转接
    ├── pack.py         # 打包 / 校验 / 安装 / 体检
    ├── flow.py         # 案件状态机
    └── native.py       # macOS 原生替身
```

五个脚本合计约 1800 行，**零第三方依赖**，任何一个 python3 ≥ 3.9 都能跑。
