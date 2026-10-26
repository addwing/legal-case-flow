# 安装

前置条件只有两件：**一个 python3（≥ 3.9）**，和**一个放技能的目录**。
不需要 root，不需要 Homebrew，不需要联网装包。

---

## 一、git clone（推荐）

```bash
git clone https://github.com/addwing/legal-case-flow.git
cd legal-case-flow
./install.sh --dry-run          # 先看它要干什么
./install.sh                    # 真装
```

装完它会自动跑三段验证：角色探测、原生通路、第三方依赖。

## 二、没有 git：下 Release 包

到 [Releases 页](https://github.com/addwing/legal-case-flow/releases/latest) 下载
`legal-case-flow-<版本>.tar.gz`，解开后同样两条命令：

```bash
tar xzf legal-case-flow-1.0.1.tar.gz
cd legal-case-flow-1.0.1
./install.sh
```

从浏览器下载的包在 mac 上会被打上「来自互联网」的标记，第一次跑可能被拦。
`install.sh` 会自己清一次；如果连脚本都被拦住进不去，先手工：

```bash
xattr -dr com.apple.quarantine legal-case-flow-1.0.1.tar.gz
```

## 三、给同事一份（他那边已装过上游模块）

只发编排层这一份，别重复装他那七个模块：

```bash
./install.sh --to ~/.workbuddy/skills     # 他若用 Claude Code 就 ~/.claude/skills
```

装完 `bind.py --plan` 会认出他已经有的模块，一个都不用重装。

## 四、开发者：软链接安装

改代码后不想每次重装：

```bash
./install.sh --link
```

技能目录里是一个指向仓库的软链接，`git pull` 或改完文件立刻生效。
**注意**：软链接下 `.backup-*` 备份不会生成（没有旧副本可备份）。

---

## 装到哪：探测顺序

`install.sh` 不指定 `--to` 时，按这个顺序取第一个成立的：

1. 环境变量 `WORKBUDDY_SKILLS`（WorkBuddy）
2. 环境变量 `CLAUDE_SKILLS`（Claude Code）
3. `~/.workbuddy/skills` —— 存在 `~/.workbuddy` 就用它
4. `~/.claude/skills`
5. `~/.codex/skills`
6. 都没有就建 `~/.workbuddy/skills`

想装到别处（比如项目级技能目录）：

```bash
./install.sh --to ./我的项目/.workbuddy/skills
```

---

## 上游七个模块：不在这个仓库里

本仓库是**编排层**（角色探测、转接、打包、状态机、mac 原生替身），
不含那七个可视化模块。原因写在 [NOTICE](../NOTICE)：它们是缪奇川的独立作品，
版本节奏与我们不同，我们只读它们的命令行，不 fork、不打补丁。

三种拿法，任选：

**A. 你机器上已经有**（装过 WorkBuddy 技能包、或同事给过）
什么都不用做，`bind.py --plan` 会自己认出来。

**B. 从本仓库的 Release 附件装**

在 [Releases 页](https://github.com/addwing/legal-case-flow/releases/latest) 下载
`legal-case-modules-1.0.0.tar.gz`（约 1.6 MB，七个模块原样打包），然后：

```bash
./install.sh --modules ~/Downloads/legal-case-modules-1.0.0.tar.gz
```

**C. 从别人的机器上收集一份**

在**已装好模块**的那台机器上：

```bash
python3 tools/collect-modules.py -o ~/Desktop/legal-case-modules-1.0.0.tar.gz
```

然后把这个包拷到新机器，按 B 装。

一个都没有也能用一半：`flow.py init/next` 照常跑，`bind.py` 会把七个角色都标成
「未安装」，并按阶段跳过。只是出不了图。

---

## 验证装好了没有

```bash
python3 ~/.workbuddy/skills/legal-case-flow/scripts/bind.py --plan     # 七个角色认不认得出
python3 ~/.workbuddy/skills/legal-case-flow/scripts/native.py check    # mac 原生通路（PDF/SVG）
python3 ~/.workbuddy/skills/legal-case-flow/scripts/pack.py doctor     # 第三方依赖缺哪几个
```

三段的判读标准：

| 输出 | 正常长什么样 | 不正常怎么办 |
| --- | --- | --- |
| bind --plan | 七个角色全是「已绑」 | 显示「未安装」= 没上游模块，见上一节 |
| native check | PDF 通路与 SVG 两行是 OK | 报 `sandbox initialization failed` 不影响 sips 那条路 |
| doctor | 第一段全绿，第二段可能缺 1-2 个库 | 缺 `openpyxl` 必须补，其余缺了只少一种格式 |

---

## 升级

```bash
cd legal-case-flow
git pull
./install.sh            # 旧版自动备份到 .backup-<时间戳>/
```

软链接安装的，`git pull` 就完事，不用重跑。

## 卸载 / 回滚

```bash
./install.sh --uninstall        # 删掉技能目录里的编排层
```

如果目录里有 `.backup-*`，卸载时会**自动把最近一次的旧版本恢复回来**。
上游七个模块不属于本仓库，`--uninstall` 不会动它们；要清就自己：

```bash
rm -rf ~/.workbuddy/skills/mqc-*
```

手工回滚某一版：

```bash
mv ~/.workbuddy/skills/.backup-20261026-195102/legal-case-flow ~/.workbuddy/skills/legal-case-flow
```

---

## 一台机器、多个 agent

WorkBuddy、Claude Code、Codex 各自读自己的技能目录。三种选择：

- 各装一份（磁盘各占约 200 KB，互不干扰）
- 只装一份，另一个 agent 用软链接指过来
- 用 `--to` 装到它们共同认的目录（少见）

`bind.py` 的搜索根默认覆盖 `~/.workbuddy/skills`、`~/.claude/skills`、`~/.codex/skills`
以及当前目录下的同类目录，所以装在哪个都不影响它找模块；找不到时加：

```bash
export LEGAL_CASE_FLOW_ROOTS="$HOME/.workbuddy/skills:$HOME/别的目录"
```

---

## 内网 / 无网络

整套东西没有一个字节依赖联网。把仓库目录用 U 盘拷过去即可，
连 `git clone` 都省了。注意两点：

- 从网盘拷来的清一次隔离标记：`xattr -dr com.apple.quarantine 目录`（mac）
- 别用 `tar` 在两个 mac 之间打包，中文名与扩展属性容易丢，用 `ditto 源 目标`

## Windows

官方只支持 macOS 与 Linux。Windows 上请用 WSL2（Ubuntu），
里面的安装方式与 Linux 完全一样。原生 PowerShell 没测过，别指望。

---

## 安全说明

安装器只做四件事：**读仓库里的文件、往技能目录拷一份、建备份、跑三个只读的检查脚本**。
它不联网、不写系统目录、不装任何包、不改 PATH、不需要 `sudo`。
想核实就看 `install.sh`，一共不到三百行。
