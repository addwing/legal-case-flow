# 变更记录

格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号参照 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] — 2026-10-26

首个公开版本。此时的形态是「薄编排层」：不合并上游、不修改上游、只读它们的命令行与产物。

### 新增

- **角色制编排**：七个角色（`facts` / `structure` / `adversary` / `chronology` /
  `data` / `deck` / `redraw`）按能力探测绑定，换作者或换目录名只改 `capabilities.json`。
- **`bind.py`**：三验探测（目录 + `SKILL.md` 的 `name` + 关键脚本），支持 `--plan` /
  `--check` / `--json` / `--roots`，可被环境变量与覆盖文件改写。
- **`handoff.py`**：两处机械转接（底稿 → 对抗图输入骨架 / 关系图输入骨架），
  另出《事实挂载表》供要件与事实对账。
- **`pack.py`**：打包 / 校验 / 安装 / 体检。包内是原样目录 + 清单，路径越界与符号链接会被挡。
- **`flow.py`**：案件状态机（`init` / `next`），按产物判断走到哪一步。
- **`native.py`**：macOS 原生替身——`sips` 出 PNG、PDFKit 读 PDF、`textutil` 读 Word、
  `qlmanage` 放大、`clean` 清 `.DS_Store`。
- **`install.sh`**：mac / Linux 通用安装器，自动避开 `/usr/bin/python3`、
  覆盖前备份、清下载隔离标记、装完自动三段验证。
- **文档**：安装、使用、命令、设计、macOS 原生、排错共六篇，附虚构示例与冒烟测试。

### 设计取舍

- **不合并上游**：上游每个模块自带几十到两千多条回归判据，合并即拆守卫。
- **不 vendor 上游**：版本节奏不同，且不应由本仓库代管。用 Release 附件分发，
  版权与许可随包保留，见 `NOTICE`。
- **骨架不猜**：`handoff.py` 只搬运不判断，产物不能直接出图——这是设计，不是未完成。

### 已知限制

- `F` 编号没有真正流到下游（上游两边的 `casefile.json` 是两套结构），只能人工对账。
- `adversary` 与 `facts` 简表不出 `-trace.json`，进课件无逐项出处。
- 法域固定为中国诉讼语境；Windows 仅支持 WSL2。
