# 命令参考

五个脚本，全部零第三方依赖，`python3 <脚本> -h` 都能看用法。
**退出码**统一是：`0` 成功、`1` 检查不过、`2` 用法或环境错误。

下文 `<技能>` 指安装目录，通常是 `~/.workbuddy/skills/legal-case-flow`。

---

## `flow.py` —— 案件状态机

| 命令 | 作用 |
| --- | --- |
| `init 案目录 [--title 名称]` | 建 `材料/` 与 `产物/{大事记,时间轴,关系图,对抗图,课件}` |
| `next 案目录` | 按已有产物判断走到哪一步，打印下一步的完整命令 |

```bash
python3 <技能>/scripts/flow.py init 案件-甲诉乙 --title "甲诉乙买卖合同纠纷"
python3 <技能>/scripts/flow.py next 案件-甲诉乙
```

`next` 不替你跑上游管线：那几家都有必须问人的步骤（勾材料、勾时段、定风格），
一口气跑完等于替你答了。它只告诉你「现在该敲哪一条」。

---

## `bind.py` —— 角色探测

| 参数 | 作用 |
| --- | --- |
| （无） | 打印绑定表：哪个角色绑在哪个目录、什么版本 |
| `--plan` | 按阶段打印整条链，标出已绑 / 缺失，并附每个角色的下一步提示 |
| `--check` | 必需角色没绑上就退出 1 |
| `--require facts,structure` | 指定哪些算必需（默认只有 `facts`） |
| `--json` | 机器可读（`pack.py` 与 `handoff.py` 靠它拿路径） |
| `--roots A:B` | 只在这几个根里找；迁移、交接时用 |

```bash
python3 <技能>/scripts/bind.py --plan
python3 <技能>/scripts/bind.py --check --require facts,structure
```

探测看三样，**有一项不过就报出来，不硬用**：目录在不在、`SKILL.md` 的 `name`
是不是它自称的那个、关键脚本齐不齐。同名但换了作者的模块会被拦在门外。

覆盖方式（优先级从高到低）：`--roots` → 环境变量 `LEGAL_CASE_FLOW_ROOTS` →
`~/.legal-case-flow/bindings.json`（格式 `{"facts": "/abs/path"}`）→ 默认搜索根。

---

## `handoff.py` —— 两处机械转接

| 命令 | 输入 | 输出 |
| --- | --- | --- |
| `matrix` | `casefile.json` | `matrix-input.json`（四段骨架）+ 可选《事实挂载表》 |
| `relations` | `casefile.json` | `relations.json`（主体节点 + 客体候选，**0 条关系**） |

```bash
python3 <技能>/scripts/handoff.py matrix 底稿.json -o matrix-input.json --index 事实挂载表.md
python3 <技能>/scripts/handoff.py relations 底稿.json -o relations.json
```

**它只做搬运，不做判断**：底稿里有的照抄，没有的留空并列成待办。
两份产物都不能直接出图，这是设计，不是没做完。

`--index` 那一份是给人看的表：`F` 编号 + 日期 + 证据 + 出处 + 原文，填要件时照着挂。

---

## `pack.py` —— 打包、校验、安装、体检

| 命令 | 作用 |
| --- | --- |
| `pack [-o 路径] [--slim]` | 把编排层与已绑定的模块打成一个可校验的包 |
| `verify 包.tar.gz` | 只读包，核对清单与文件指纹 |
| `install 包.tar.gz --to 目录 [--force]` | 校验通过才装；装完自动跑探测与体检 |
| `doctor` | 运行依赖体检（mac 上分三段：原生 / 要装 / 备用） |

```bash
python3 <技能>/scripts/pack.py pack --slim -o /tmp/bundle.tar.gz
python3 <技能>/scripts/pack.py verify /tmp/bundle.tar.gz
python3 <技能>/scripts/pack.py install /tmp/bundle.tar.gz --to ~/.workbuddy/skills
python3 <技能>/scripts/pack.py doctor
```

`--slim` 去掉上游的 `assets/` 与 `tests/`，体积从约 15 MB 降到约 1.6 MB。
分发给同事时用精简版；要连上游测试资源一起带走才用全量。

包里是**原样目录 + 一份清单**，上游一个字节没改。`install` 会挡住路径越界、
带符号链接的包，并自动清 mac 的下载隔离标记。

---

## `native.py` —— macOS 原生替身

| 命令 | 作用 | 顶替谁 |
| --- | --- | --- |
| `check` | 原生工具清单 + 现造 PDF/SVG 实测 | — |
| `pdfpages 文件.pdf` | 页数 | `pdfinfo` |
| `pdftext 文件.pdf [-o 输出] [--page N]` | 全文或单页文字 | `pdftotext` |
| `doc2txt 材料.docx [-o 输出]` | 取文字（表格摊平） | python-docx（仅读文字） |
| `svg2png 图.svg 图.png [--size 2400]` | SVG 转 PNG | cairosvg / rsvg / soffice |
| `pdf2png 卷.pdf 目录/ [--size 1600]` | PDF **首页**栅格化 | `pdftoppm`（仅首页） |
| `clean 目录` | 清 `.DS_Store` 与 `._` 分身 | — |

```bash
python3 <技能>/scripts/native.py check
python3 <技能>/scripts/native.py svg2png 产物/时间轴/时间轴.svg /tmp/时间轴.png
python3 <技能>/scripts/native.py pdftext 卷.pdf -o 卷.txt
python3 <技能>/scripts/native.py clean .
```

只在 macOS 上成立。Linux 上这些命令仍会尝试，但会失败并给出装 poppler /
LibreOffice 的提示——那是**备用路径**，不是首选。

---

## 组合用法

### 换机器后确认状态

```bash
python3 <技能>/scripts/bind.py --plan && python3 <技能>/scripts/pack.py doctor
```

### 一次性出一份可给同事的包

```bash
python3 <技能>/scripts/pack.py pack --slim -o ~/Desktop/legal-case-bundle.tar.gz
python3 <技能>/scripts/pack.py verify ~/Desktop/legal-case-bundle.tar.gz
```

### 只重画一张外部旧图

```bash
python3 <技能>/scripts/bind.py | grep redraw     # 先看它绑在哪
# 然后直接用那个模块自己的命令，不必进这条流水线
```
