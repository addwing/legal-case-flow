# legal-case-flow · 法律可视化编排层

> 七个法律可视化模块各自都很硬。难的是**它们之间那几句话**：这次该从哪进、
> 上一步交什么、缺一个还能不能跑。

这一层不画图、不写法律意见，只回答上面三件事。它把「事实底稿 → 法律关系图 →
庭审对抗图 → 时间轴 → 课件」串成一条能中断、能接手、能换机器的流水线。

```
材料 ──▶ ① 事实底稿（F001 起编，唯一编号源）
           │
           ├─▶ ② 法律关系图 ──┐
           ├─▶ ③ 庭审对抗图 ──┼─▶ ⑤ 课件（要讲才做）
           └─▶ ④ 时间轴 ──────┘
                    ⑥ 数据图（有一批判决才做）   ⑦ 重画（只接外部旧图）
```

---

## 它解决什么

**① 不知道该从哪一步开始。**
七个模块都自称「读同一份底稿」，实际上两边的底稿是两套结构。这里定死起点：
`facts` 永远在第一，`F` 编号一次分配不再变。

**② 不知道上一步交什么。**
三份契约写死最小字段（`case.cid`、`facts[].fid`、`edges[].label`……），
**只读这些，其余一律忽略**。上游加字段不报错，换版本不用改代码。

**③ 缺一个模块就卡住。**
七个角色按能力探测，没绑上的跳过并在计划里写明，不替它编一个替代品。
只装四个也能跑，只是少两张图。

---

## 安装

```bash
git clone https://github.com/<你的账号>/legal-case-flow.git
cd legal-case-flow
./install.sh
```

零依赖、不需要 `sudo`、不联网装包。装完自动跑三段验证。

- 没有 git？下 Release 包，解开后同样 `./install.sh`
- 装到 Claude Code？`./install.sh --to ~/.claude/skills`
- 只想看看它要干什么？`./install.sh --dry-run`
- 卸掉？`./install.sh --uninstall`（会自动恢复最近一次备份）

详细步骤与「装到哪」的探测顺序见 **[docs/install.md](docs/install.md)**。

> **上游七个可视化模块不在本仓库里。** 它们是缪奇川的独立作品（MIT），版本节奏与
> 这一层不同。三种获取方式见 [docs/install.md](docs/install.md#上游七个模块不在这个仓库里)。
> 本仓库只提供编排层，不 fork、不打补丁、不代管版本。

---

## 三十秒跑通

```bash
# 1. 开案
python3 ~/.workbuddy/skills/legal-case-flow/scripts/flow.py init 案件-甲诉乙 --title "甲诉乙买卖合同纠纷"

# 2. 看下一步该干什么（它会打印带绝对路径的完整命令）
python3 ~/.workbuddy/skills/legal-case-flow/scripts/flow.py next 案件-甲诉乙

# 3. 用示例底稿试试两处转接（虚构案件，随便跑）
cd 案件-甲诉乙
python3 ~/.workbuddy/skills/legal-case-flow/scripts/handoff.py matrix \
        <仓库>/examples/minimal/casefile.json -o /tmp/matrix-input.json
```

第 3 步你会看到两份骨架和一堆待办——**这是设计，不是没做完**。
脚本不替你猜立场、关系名和诉请类型；猜错了会一路错到交付物上。

---

## 七个角色

| 角色 | 干什么 | 什么时候才上 |
| --- | --- | --- |
| `facts` | 事实底稿、大事记 Word、Excel 母表、A4 简表 | **起点固定**，整卷材料先过这里 |
| `structure` | 谁与谁、就哪份合同或工程成立什么关系 | 要在事实之外讲清结构时 |
| `adversary` | 九步法推演、争点攻防、17 列分析表 | 庭前推演、向当事人汇报；**不对法院出示** |
| `chronology` | 案件时间轴（三种图种、双泳道） | 只在「距离本身是论点」时：时效、逾期、期间重叠 |
| `data` | 统计图、类案编码、金额逐级加减 | 有一批判决或逐件登记表才上 |
| `deck` | 把各层的图装进 12×6 网格页 | 要讲、要汇报、要交客户时 |
| `redraw` | 把外部旧图重画 | 只接外部来的图；**本链自己产的 SVG 不要回炉** |

角色怎么绑、怎么加一个新角色，见 **[docs/architecture.md](docs/architecture.md)**。

---

## 五个命令

| 脚本 | 一句话 |
| --- | --- |
| [`flow.py`](docs/commands.md#flowpy--案件状态机) | 案件状态机：开案、判断走到哪一步 |
| [`bind.py`](docs/commands.md#bindpy--角色探测) | 角色探测：谁绑在哪、缺谁、为什么缺 |
| [`handoff.py`](docs/commands.md#handoffpy--两处机械转接) | 两处机械转接：底稿 → 对抗图输入 / 关系图输入 |
| [`pack.py`](docs/commands.md#packpy--打包校验安装体检) | 打包、校验、安装、依赖体检 |
| [`native.py`](docs/commands.md#nativepy--macos-原生替身) | macOS 原生替身：sips 出图、PDFKit 读 PDF |

全部零第三方依赖，`python3 <脚本> -h` 看用法。完整参数表见 **[docs/commands.md](docs/commands.md)**。

---

## macOS 上不必装的东西

| 要干的事 | 系统自带 | 原来那套（备用） |
| --- | --- | --- |
| SVG → PNG | `sips` | cairosvg / rsvg / soffice |
| PDF 页数与全文 | `osascript` + PDFKit | pdfinfo / pdftotext |
| PDF 首页转图 | `sips --resampleWidth` | pdftoppm |
| .docx 取文字 | `textutil` | python-docx（仅读文字时） |

**唯一值得为它装 Homebrew 的只有「扫描件逐页栅格化」**（`pdftoppm`）。
其余在 mac 上都可以不装。详见 **[docs/macos-native.md](docs/macos-native.md)**，
里面还有一张「不要再走的弯路」表（12 条真实踩过的坑）。

---

## 已知的两处缝（不掩饰）

1. **F 编号没有真正流到下游。** 上游的关系图与对抗图指南里没有一处引用 `F` 编号，
   两边的 `casefile.json` 还是两套结构。所以编号只能**人工对账**——
   `handoff.py` 出的《事实挂载表》就是给这个用的。
2. **两份产物没有 `-trace.json`。** `adversary` 与 `facts` 的简表都不出溯源文件，
   进课件只能整张放、没有逐项出处。

修这两处要改上游，本层的态度是摆明，而不是悄悄糊过去。

---

## 边界与免责

- **不做法律判断。** 争点、要件、证明前景、立场，全部留给人。
- **不对法院出示分析稿。** 庭审对抗图、17 列分析表是内部推演稿，不是诉讼文书。
- **法域不通用。** 上游写死中国诉讼语境（九步法、民法典条号、A4 与宋体、证据编号）。
  这一层的「通用」只到顺序与交接为止。
- **不替代律师。** 产出是工作底稿，不是法律意见；用之前逐条核对卷宗。
- **别把真实卷宗提交到 issue 或仓库。** 当事人信息、案号、金额请替换成虚构值。

---

## 目录结构

```
legal-case-flow/
├── install.sh              # 装到技能目录（mac / Linux，零依赖）
├── skill/                  # 技能本体：SKILL.md + capabilities.json + 5 个脚本
├── docs/                   # 安装 / 使用 / 命令 / 设计 / mac 原生 / 排错
├── examples/minimal/       # 虚构示例：一份合规的 casefile.json
├── tools/collect-modules.py# 从本机收集上游模块，打成可分发的包
├── tests/smoke.sh          # 冒烟测试（8 组，CI 与本机同一条命令）
└── .github/workflows/      # CI：ubuntu + macos × py3.9 / 3.12
```

## 文档

| 文档 | 讲什么 |
| --- | --- |
| [docs/install.md](docs/install.md) | 四种安装方式、上游模块怎么拿、升级与卸载 |
| [docs/usage.md](docs/usage.md) | 从备材料到交付的完整流程，每步的验收标准 |
| [docs/commands.md](docs/commands.md) | 五个脚本的全部参数与退出码 |
| [docs/macos-native.md](docs/macos-native.md) | 原生对照表 + 12 条弯路 |
| [docs/architecture.md](docs/architecture.md) | 为什么不合并、角色制、两处缝、加新角色 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 按症状查的排错手册 |

---

## 许可与致谢

本仓库（编排层）以 **MIT** 发布，见 [LICENSE](LICENSE)。

上游七个可视化模块由 **缪奇川（Miao Qichuan）** 创作，同样以 MIT 授权，
版权归原作者。本仓库不包含它们的代码；分发时请保留其署名与许可声明，
详见 [NOTICE](NOTICE)。

版本变更见 [CHANGELOG.md](CHANGELOG.md)。
