---
name: legal-case-flow
description: 法律事务的编排层。当一个案子要把多个法律可视化模块串起来跑（事实底稿 → 法律关系图 → 庭审对抗图 → 时间轴 → 课件 → 数据图），或者不确定这次该从哪一步开始、上一步该交什么给下一步、缺了某个模块还能不能跑时使用。按能力角色探测本机已装模块并绑定，给出阶段计划与两处交接骨架；不代替任何模块干活，也不做法律判断。目标机器是 macOS，依赖一律先用系统自带的（sips / PDFKit / textutil），第三方那套只作备用。触发词：把这些技能串起来、从哪一步开始、案件的图怎么排、大事记接关系图、编排、pipeline、工作流、移植到 mac。
tags: [legal, orchestration, pipeline, 编排, 交接, macos]
metadata:
  version: 0.2.0
  upstream_policy: 只读不改，按角色探测绑定
  platform: macOS 优先，原生工具优先；Linux 那套作备用
---

# 法律事务编排层

七个模块各自都很硬，难的是它们之间那几句话：这次该从哪进、上一步交什么、缺一个还能不能跑。这一层只回答这三件事。

## 四条移植原则

1. **只认角色，不认名字。** 角色是 `facts / chronology / structure / adversary / data / deck / redraw`，名字映射全在 `capabilities.json`。换作者、换模块、上游改名，改那一份，脚本与本文一个字都不用动。
2. **只调命令行，不 import 上游代码。** 只读产物文件，不碰 `state.json`、缓存、内部函数。上游改内部实现，这一层不受影响。
3. **缺谁降级，不崩。** 没绑上的角色跳过并在计划里写明，不替它编一个替代品。
4. **mac 上先用系统自带的。** 出图、读 PDF、读 Word 这三件事，mac 本来就自带能力，别为先跑通去装一套 Homebrew。原生顶不住时才装，而且只装那一样（见下节）。

## macOS：原生优先（第一原则，不是优化项）

这一层要在 mac 上跑，先认清哪几件事根本不用装东西。以下全部实测过（macOS 14/15 通用）：

| 要干的事 | mac 原生 | 一条命令 | 原来那套（**备用**，只在原生不够时） |
| --- | --- | --- | --- |
| SVG → PNG | `sips`（ImageIO 直接吃 SVG） | `sips -s format png 图.svg --out 图.png` | cairosvg / rsvg-convert / `soffice --convert-to png` |
| SVG → 更大尺寸 PNG | `qlmanage -t -s 2400` | 见 `native.py svg2png 图.svg 图.png --size 2400` | 同上 |
| PDF 页数 / 全文文字 | `osascript` + PDFKit | `native.py pdftext 卷.pdf` | poppler：`pdfinfo` / `pdftotext` |
| PDF 首页 → PNG | `sips --resampleWidth 1600` | `native.py pdf2png 卷.pdf 目录/` | `pdftoppm`（**逐页**只能用它） |
| .docx 取文字 | `textutil` | `textutil -convert txt -output x.txt 材料.docx` | python-docx（取文字时不必装） |
| 中文字体 | Songti.ttc / STHeiti / Hiragino Sans GB | 字体名换 Songti SC，别写「宋体」 | 自备字体文件 |
| 拷/打包大目录 | `ditto`（保 UTF-8 名与属性） | `ditto 源 目标` | tar / rsync |
| 被 Gatekeeper 拦 | `xattr` | `xattr -dr com.apple.quarantine 目录` | 手动去隐私设置点允许 |

```bash
python3 <本技能目录>/scripts/native.py check      # 这台机器上哪些原生能用，顺手实测 PDF 与 SVG 两条路
python3 <本技能目录>/scripts/native.py clean 目录 # 打包前清 .DS_Store 与 ._ 分身
```

`sips` 转出来的图，中文、配色、透明背景都对，实测与原 SVG 一致——**这就是 mac 上出 PNG 的正路**，不必为这一件事装 LibreOffice。

## 不要再走的弯路

下面是这条路上一脚一脚踩出来的。**每一条都写着「别这么做」和「该怎么做」**，照着走能省掉整晚。

### 环境类（装东西这件事）

| 别这么做 | 为什么错 | 该怎么做 |
| --- | --- | --- |
| 为了 `pdftotext` 装 `brew install poppler` | PDFKit 是系统自带的，一条 osascript 就能取全文 | `native.py pdftext`；**只有扫描件逐页栅格化**才装 poppler |
| 为了 SVG→PNG 装 LibreOffice 或 cairosvg | `sips` 一条命令就出图，中文配色都对 | `sips -s format png`；放大再上 `qlmanage` |
| 直接用 `/usr/bin/python3` | 没装 Command Line Tools 会弹窗让你下 2 GB，脚本看着像“卡住” | 先 `xcode-select -p`；用托管解释器或 python.org 那份的绝对路径 |
| `sudo pip install` 或装进系统 Python | mac 上直接报 `externally-managed-environment`，装进去也会被系统更新冲掉 | 装进 venv：`<venv>/bin/python -m pip install ...`，不加 sudo |
| `which node` 不到就以为没 node | WorkBuddy 托管的 node 不在 PATH 里，但能直接用 | 用绝对路径：`~/.workbuddy/binaries/node/versions/*/bin/node` |
| 把网盘/U 盘拷来的目录直接跑 | `com.apple.quarantine` 会让脚本被拦，报错还很难懂 | `xattr -dr com.apple.quarantine 目录`；`pack.py install` 已自动清 |
| 用 `tar` 在两个 mac 之间打包拷贝 | 中文名与扩展属性容易丢，包里混进 `._` 分身 | 本机用 `ditto`；跨机用 `pack.py pack`（已过滤垃圾） |

### 管线类（顺序这件事）

| 别这么做 | 为什么错 | 该怎么做 |
| --- | --- | --- |
| 先跑时间轴，再跑大事记 | 两边各抽一遍事项，等于同一批材料读两次、两份事实、两套编号 | **facts 永远在第一**；时间轴只做旁路对照 |
| 一口气把上游管线跑完 | 那几家都有必须问人的步骤（勾材料、勾时段、定风格） | 跑到提问点就停，问完再往下 |
| 把 V2 / V3 自己产的 SVG 回炉 `redraw` | 几何会掉，坐标重排，图看着像但尺寸不对 | `redraw` 只接**外部**旧图；本链产物直接进 `deck` |
| 往 `matrix-input.json` 里塞 F 编号 | 那边四段正文有照录判据，塞编号会触碰判据 | 编号只进《事实挂载表》，JSON 不碰 |
| 指望 `casefile.json` 在 V4 与 V5 之间通用 | 两家的 casefile 是两套结构，指南里也没引用 F 编号 | 人工对账；`handoff.py` 只出骨架 |
| 缺一个模块就找替代品硬凑 | 每个模块都有几十到两千条回归判据 | 缺就跳过并在计划里写明，不编替代 |

### 产物类（东西发出去之前）

| 别这么做 | 为什么错 | 该怎么做 |
| --- | --- | --- |
| 字体写「宋体」 | mac 上没有这个名，PDF 里会掉成方框或默认字体 | 换 `Songti SC`；黑体用 `STHeiti`，正文别用 Hiragino |
| 拿 `textutil` 转出的 txt 当底稿 | 表格被摊平成行，样式全丢，看着像原文其实结构没了 | 只用来“读”；底稿仍用 python-docx / 上游的 ingest |
| Finder 里翻一遍目录再打包 | 生成 `.DS_Store`，`verify` 的文件数每次都不一样 | 打包前 `native.py clean`；`pack.py` 已过滤 |
| 用 `qlmanage` 当出图的首选 | 无 GUI 会话或沙箱里报 `sandbox initialization failed` | `sips` 打头，qlmanage 只作放大 |
| 拿 `mdls` 取 PDF 文字 | 依赖 Spotlight 索引，`/tmp` 与外部盘读不到，返回 `(null)` | 用 PDFKit（`native.py pdftext`）；mdls 只兜页数 |
| 分析稿直接当上诉状递 | 分析是给代理人看的，递出去的是另一套文体与格式 | 正式文书另起一份，逐条对条号案号 |

## 先探测，再动手

```bash
python3 <本技能目录>/scripts/bind.py            # 绑定表：哪个角色绑在哪个目录、什么版本
python3 <本技能目录>/scripts/bind.py --plan     # 按阶段打印这条链，标出已绑 / 缺失
python3 <本技能目录>/scripts/bind.py --check    # 必需角色（默认 facts）绑不上就退出 1
python3 <本技能目录>/scripts/bind.py --roots A:B  # 只在这几个根里找：迁移、交接给同事时用
```

探测看三样：目录在不在、`SKILL.md` 的 `name` 是不是它自称的那个模块、关键脚本齐不齐。**三样有一项不过就报出来，不硬用**——同名但换了作者的模块会被拦在门外，而不是拿错的模块硬跑。搜索根默认覆盖 `~/.workbuddy/skills`、`~/.claude/skills`、`~/.codex/skills` 与当前目录下的同类目录；要加自己的，用环境变量 `LEGAL_CASE_FLOW_ROOTS`（`os.pathsep` 分隔）或覆盖文件 `~/.legal-case-flow/bindings.json`（`{"facts": "/abs/path"}`）。

## 角色与分流

| 角色 | 干什么 | 什么时候才上 |
| --- | --- | --- |
| `facts` | 事实底稿、大事记 Word / Excel / 简表 | **起点固定**。整卷材料先过这里 |
| `structure` | 谁与谁、就哪份合同或工程成立什么关系 | 要在事实之外讲清结构时 |
| `adversary` | 九步法推演、争点攻防、17 列分析表 | 庭前推演、向当事人汇报；不对法院出示 |
| `chronology` | 案件经过时间轴（三种图种、双泳道） | **旁路**：只在「距离本身是论点」（时效、逾期、期间重叠）或两方材料对读时启动 |
| `data` | 统计图、类案编码、金额逐级加减 | 一批判决或逐件登记表才上；单案通常用不上 |
| `deck` | 把上面各层的图装进 12×6 网格页 | 要讲、要汇报、要交客户时 |
| `redraw` | 把外部旧图重画 | 只接外部来的图；**本链自己产出的 SVG 不要回炉** |

## 一条案子怎么串

```
材料 ──▶ facts（底稿 casefile.json，F001 起编）
             │
             ├─▶ structure（relations.json）──┐
             ├─▶ adversary（matrix-input.json）┼─▶ deck（assets/ 收 SVG + -trace.json）
             └─▶ chronology（按需，自带 -trace.json）┘
                        data（有数才上，出 module.json）
```

顺序上守两条：

- **先 facts 再 chronology。** 时间轴自己也会抽一遍事项；反过来跑，等于同一批材料读两次、两份事实、两套编号。
- **redraw 是本链之外的入口。** 手上已经有一张画得难看的图，直接从它进，不必过底稿。

## 交接契约

契约是唯一跨版本的锚点。**只读下面这些字段，其余一律忽略；上游加字段不报错。**

| 交接 | 最小必需 | 不许动的 |
| --- | --- | --- |
| `casefile.json`（`mqc-casefile/1`） | `case.cid`、`case.title`、`materials[].mid`、`parties[].pid`、`facts[].fid` | F 编号一旦分配不再变动；`content` 照录 |
| `relations.json` | `nodes[].id/name/kind`、`edges[].from/to/label` | `kind` 只有主体 / 客体；关系名照录原文 |
| `matrix-input.json` | `case.title/stance`、`claims[]`、`parts[].claim_bases[].elements[]` | 四段正文照录；条号案号不编造 |
| `assets/` | `*.svg` 与同名 `-trace.json` | 缺 trace 的图在课件里悬停看不出处，不是错误但要说明 |

**已知的两处缝**（上游没打通，本层把它摆明，不悄悄糊过去）：

- 三件法宝都说「读同一份底稿」，但 `relations-guide.md` 与庭审的 `casefile-guide.md` 里没有一处引用 F 编号，且两边的 `casefile.json` 是两套结构。所以编号只能**人工对账**。
- `adversary` 与 `facts` 的简表都不出 `-trace.json`，进 `deck` 只能整张放、没有逐项出处。

## 两处机械转接

只有两件事能机械做，其余都是判断：

```bash
python3 <本技能目录>/scripts/handoff.py matrix    底稿.json -o matrix-input.json
python3 <本技能目录>/scripts/handoff.py relations 底稿.json -o relations.json
```

- **matrix**：填标题、材料范围（已获取 / 未获取的文书类别）、对账锚，另出一份《事实挂载表》（F 编号 + 日期 + 证据 + 出处 + 原文），供把要件挂到事实上时引用。**编号不写进 JSON** —— 那边四段正文有照录判据，塞编号会触碰判据。
- **relations**：把 `parties` 照录成主体节点（`pid` 原样保留），按材料名筛出客体候选。**一条关系都不生成** —— 关系名与指向必须照录原文。

两份产物都是**骨架，不能直接出图**。脚本跑完会把待办逐条列出来，并且跟上游校验器是一一对应的：填完 `stance / procedural / maturity` 三项，`check_claims.py` 报的 `T2 / P1 / M1` 就会先变绿。

## 移植：mac → mac

另一台机器也是 mac，所以这一路最短：**出包 → 拷过去 → 装 → 体检**，全程不碰 Homebrew。

```bash
python3 <本技能目录>/scripts/pack.py pack --slim                        # 约 1.6 MB，装包用这个
python3 <本技能目录>/scripts/pack.py pack -o 全量.tar.gz                # 含 assets/ 与 tests/，约 15 MB
python3 <本技能目录>/scripts/pack.py verify 包.tar.gz                    # 只读包，核清单与文件指纹
python3 <本技能目录>/scripts/pack.py install 包.tar.gz --to 技能根目录 [--force]
python3 <本技能目录>/scripts/pack.py doctor                             # mac 三段式体检
```

mac 上的五个动作，照这个顺序：

1. **出包前先清垃圾**：`native.py clean .`（Finder 翻过一遍就会有 `.DS_Store`）。`pack.py` 也会过滤，但清一下体积与指纹都干净。
2. **拷过去用 AirDrop / `ditto`**，不要用 `tar` 解来解去；团队共享走网盘时记着它会带 quarantine 属性。
3. **装之前清 quarantine**：`xattr -dr com.apple.quarantine 包.tar.gz`。`install` 落地后也会自动清一次，但解压前就被拦的情况要先解。
4. **`install` 收尾会自动跑 `bind.py --plan` 与 `doctor`**：接不通、缺依赖当场列出来，不留到出图那一步才崩。
5. **体检只看第二段**：mac 上第一段几乎全绿（系统自带），第三段基本可以不装。真要补的通常只有 `openpyxl` 这一两个 Python 库。

三条要记住：

- **包里是原样目录 + 一份清单**，上游一个字节没改；上游的许可文件随包带走（MIT）。
- **探测先认自己旁边的模块。** 包搬到哪，`bind.py` 就先在那个根里找，不回头认原来那台机器——这是「换个地方还能用」的关键。
- **装上了不等于接得通。** 所以 `install` 不打印“成功”就完事，它接着验一遍。

### 备用：非 mac，或原生顶不住

只有在 Linux 上、或者要做**扫描件逐页栅格化**时才走这条：`poppler`（`pdfinfo` / `pdftotext` / `pdftoppm`）、`LibreOffice`（`soffice`）、`node`、`pip install openpyxl cairosvg pypdf python-docx`。这些都能用，只是不该在 mac 上一上来就装。

## 日常用法

```bash
python3 <本技能目录>/scripts/flow.py init 案目录 --title 案件名
python3 <本技能目录>/scripts/flow.py next 案目录
```

`init` 摆出 `材料/` 与 `产物/{大事记,时间轴,关系图,对抗图,课件}`；`next` 按目录里已有的产物判断走到哪一步，把下一步该敲的命令连着绑定好的绝对路径打出来。**它不替你跑上游管线**——那几家都有必须问人的步骤（勾材料、勾时段、定风格），一口气跑完等于替你答了。

## 依赖体检

`pack.py doctor` 分三段，`native.py check` 是它的原生细版：

| 段 | 内容 | 判断标准 |
| --- | --- | --- |
| 一、原生优先 | sips / osascript(PDFKit) / textutil / qlmanage / ditto / xattr | mac 上基本全绿，还实测 PDF 与 SVG 两条通路 |
| 二、确实要装 | `openpyxl`、`python-docx`、`pypdf`、`cairosvg` | 缺哪项少哪种产出；装进 venv，不加 sudo |
| 三、备用 | poppler、soffice、node | mac 上基本可以不装；poppler 仅扫描件逐页需要 |

**唯一不能省的是第二段里 `openpyxl`**——Excel 母表与对抗分析表全靠它；其余缺哪项就少一条产出路径，不崩。

## 缺谁怎么办

| 缺的角色 | 后果 | 怎么办 |
| --- | --- | --- |
| `facts` | 没有 F 编号，后面接不上 | 先装；或从 `structure` 直接进，放弃编号对账 |
| `structure` / `adversary` | 少一张图 | 跳过，其余照跑 |
| `chronology` | 时效、期间这类论点表达不出来 | 要么装，要么在代理意见里用文字写 |
| `deck` | 出图即止，没有成套课件 | 跳过 |
| `data` | 不画统计图 | 跳过；类案研究缺了它意义不大 |
| `redraw` | 只能从头还原，不能重画旧图 | 跳过 |

## 边界

- **不合并上游，也不改上游。** 上游每个模块自带几十到两千多条回归判据、彼此还检查「一个字节没变」，合并即拆守卫。
- **不做法律判断。** 争点、要件、证明前景、立场，全部留给 `adversary` 与人。
- **法域不通用。** 上游写死中国诉讼语境（九步法、民法典条号、A4 与宋体、F 编号、证据编号）。这一层的「通用」只到顺序与交接为止。
- **原生不是万能。** 逐页栅格化、复杂排版转 PDF 这两件事 mac 原生确实弱，该装就装，别为了“零安装”硬撑。

## 交接给自己（换会话、换机器）

先跑 `bind.py --plan`，它按产物判断走到哪一步、缺哪个文件；不要凭记忆接着写。所有中间产物都落成文件，任何能读写文件的 agent 都能接手 —— 这是这一层能跨 agent 的全部原因。
