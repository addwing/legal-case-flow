# 排错

按症状查。每条都写「怎么确认」和「怎么修」，不确定原因时先跑这两条：

```bash
python3 <技能>/scripts/bind.py --plan
python3 <技能>/scripts/pack.py doctor
```

---

## 安装

### `install.sh: 找不到 skill/`

不在仓库根目录跑。`cd` 到有 `README.md` 与 `install.sh` 的那一层再执行。

### `Operation not permitted` / 弹「无法验证开发者」

从浏览器、网盘、U 盘来的文件带 `com.apple.quarantine`，Gatekeeper 拦住了脚本。

```bash
xattr -dr com.apple.quarantine 那个文件夹
xattr -l 某个脚本.sh          # 确认标记已清（应当没有输出）
```

### `python3` 一敲就弹窗要下 2 GB

那是 `/usr/bin/python3` 缺 Command Line Tools。

```bash
xcode-select -p        # 有输出就说明装了；报错就是没装
```

没装的话，用 python.org 的安装包，或 Homebrew 的 `python3`。
`install.sh` 会自动避开系统 Python，无需你处理。

### `install.sh` 把目录装到奇怪的位置

`--to` 的父目录不存在时，早期版本会拼错路径。当前版本已修，若仍异常，
用绝对路径重试：`./install.sh --to "$HOME/.workbuddy/skills"`。

---

## 角色探测

### 七个角色全是「未安装」

编排层装好了，但上游模块不在搜索根里。

```bash
ls ~/.workbuddy/skills | grep mqc     # 有没有那七个目录
```

没有 → 见 [安装 · 上游七个模块](install.md#上游七个模块不在这个仓库里)。
有但探测不到 → 加根：

```bash
export LEGAL_CASE_FLOW_ROOTS="$HOME/你的目录"
python3 <技能>/scripts/bind.py --plan
```

### 显示「探测不过：SKILL.md 的 name 是 X，不是 Y」

那一份不是它自称的模块——可能是同名但换了作者，或拷贝时改过目录名。
**不要强行用**。要么找到正确的一份，要么用覆盖文件指定：

```bash
mkdir -p ~/.legal-case-flow
echo '{"facts": "/绝对/路径/mqc-chronicle-master"}' > ~/.legal-case-flow/bindings.json
```

### 显示「探测不过：缺脚本 scripts/xxx.py」

版本不匹配（目录是新的，脚本是旧的），或是精简版没带脚本。
换完整的一份。

---

## 出图与读文件

### `sandbox initialization failed`

`qlmanage` 在无 GUI 会话、或被沙箱限制时出不了图。**不影响 `sips` 那条路**：

```bash
python3 <技能>/scripts/native.py svg2png 图.svg 图.png
```

`sips` 出的是 SVG 固有尺寸；要放大才需要 qlmanage，放大失败可以用
`rsvg-convert` 或 `soffice` 兜底。

### `PDFKit 读得到页数、读不到文字`

大概率是扫描件——扫出来的图没有文字层，任何工具都取不到。两条路：

1. 先 OCR（`pdftoppm -r 150 -png` 逐页 → OCR）
2. 手动转写，转写稿放 `材料/`，底稿里标 `medium: transcript`

### `mdls` 返回 `(null)`

Spotlight 没索引那个位置（`/tmp`、外部盘、网络卷都常见）。
用 PDFKit 那条路，别用 mdls 取文字。

### 图里的中文变成方框或方块

字体名不匹配。上游写「宋体」，mac 上要 `Songti SC`。
详见 [macOS 原生优先 · 字体](macos-native.md#字体为什么图里会掉方框)。

---

## 依赖

### `externally-managed-environment`

mac 的系统 Python 拒绝 `pip install`。

```bash
# 不要 sudo，不要改系统目录
python3 -m pip install --user openpyxl
# 或者用 venv
python3 -m venv ~/.venvs/legal && ~/.venvs/legal/bin/pip install openpyxl
```

### `doctor` 说缺 `cairosvg`，但图都出得来

因为出图走的是 `sips`，不走 cairosvg。cairosvg 只在**上游脚本自己 import 它**
的路径上需要。要出 PDF 版简表、或要批量转图时再装。

### 缺 `openpyxl`

这个不能省——Excel 母表和庭审对抗分析表全靠它。装。

---

## 转接与产物

### `handoff.py` 报「底稿缺 materials / parties / facts」

不是 `mqc-casefile/1` 结构的底稿。看两处：

- 是不是把 `matrix-input.json` 当成底稿了（名字很像）
- 大事记那一步是否真的跑完了（`产物/大事记/casefile.json` 存不存在）

### `handoff.py` 报「底稿不是合法 JSON」

文件被截断或编码不是 UTF-8。用 `python3 -c "import json;json.load(open('x.json'))"`
看具体错误位置。

### 两份骨架「什么都不全，能出图吗」

不能，这是设计。见 [使用 · 第 2 步](usage.md#第-2-步两处机械转接)。

### `flow.py next` 说「材料目录是空的」

`材料/` 里没东西，或你把材料放到了 `产物/` 下面。

---

## 打包分发

### `verify` 说「文件数 N，清单写 M」

两边不一致。三种常见原因：

1. 打包后又往目录里加了文件
2. 打包时目录里有 `.DS_Store`（Finder 翻过一遍就会有）
3. 包被重新压缩过

先清垃圾再重打：

```bash
python3 <技能>/scripts/native.py clean .
python3 <技能>/scripts/pack.py pack --slim -o 新包.tar.gz
```

### 同事那边装完，探测全「未安装」

他只装了编排层，没有上游模块。要么用 `--modules` 给他一份模块包，
要么让他在 `bind.py --plan` 里看缺哪些，逐个补。

### 卸载后想回滚

```bash
ls ~/.workbuddy/skills/.backup-*      # 看有哪些备份
mv ~/.workbuddy/skills/.backup-20261026-195102/legal-case-flow ~/.workbuddy/skills/
```

---

## Windows

不支持原生 Windows。用 WSL2（Ubuntu），里面与 Linux 一致。
PowerShell 下 `install.sh` 跑不了，别试。

---

## 还是不行

开 issue，附上这三样：

1. `python3 <技能>/scripts/bind.py --plan` 的完整输出
2. `python3 <技能>/scripts/pack.py doctor` 的完整输出
3. 系统与 Python 版本（`sw_vers`；`python3 -V`）

**别附真实卷宗**。需要举例就把姓名、公司、案号、金额换成虚构值。
