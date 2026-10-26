#!/usr/bin/env bash
# legal-case-flow 安装器 —— macOS / Linux 通用，不动系统、不装依赖。
#
#   ./install.sh                        装到自动探测到的技能目录
#   ./install.sh --to ~/.claude/skills  指定目录（Claude Code 等）
#   ./install.sh --link                 软链接安装（git pull 之后立刻生效）
#   ./install.sh --modules 包.tar.gz    同时装上游七个可视化模块
#   ./install.sh --dry-run              只看要做什么，不动磁盘
#   ./install.sh --uninstall            卸载（有备份时一并恢复）
#
# 以 bash 3.2 写成（macOS 自带就是这个版本），不依赖 Homebrew、不需要 sudo。
set -u

SELF_DIR=$(cd "$(dirname "$0")" && pwd)
NAME="legal-case-flow"
PKG_VERSION="1.0.1"
STAMP=$(date +%Y%m%d-%H%M%S)

TO=""
LINK=0
DRY=0
MODULES=""
DO_VERIFY=1
DO_UNINSTALL=0

say()  { printf '%s\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\n\033[31m✗ %s\033[0m\n' "$*"; exit 1; }
hr()   { printf '%s\n' "────────────────────────────────────────"; }

usage() {
  cat <<'EOF'
legal-case-flow —— 把七个法律可视化模块串成一条流水线的编排层。

用法：
  ./install.sh [选项]

选项：
  --to DIR         装到哪个技能根目录（默认自动探测，见下）
  --link           软链接安装：仓库是唯一副本，git pull 后立刻生效
  --modules PATH   同时安装上游七个模块（.tar.gz 包，或含模块子目录的文件夹）
  --no-verify      装完不做验证（不推荐，验证正是这个安装器的价值）
  --dry-run        只打印计划，不动磁盘
  --uninstall      卸载本技能；若存在 .backup-* 备份，一并恢复
  -h, --help       看这段说明

默认装到哪：
  1. $WORKBUDDY_SKILLS / $CLAUDE_SKILLS（若已设为环境变量）
  2. ~/.workbuddy/skills   （WorkBuddy）
  3. ~/.claude/skills      （Claude Code）
  4. ~/.codex/skills       （Codex）

示例：
  ./install.sh --dry-run
  ./install.sh --modules ~/Downloads/legal-case-modules-1.0.0.tar.gz
  ./install.sh --to ~/.claude/skills --link
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --to) shift; [ $# -gt 0 ] || die "--to 后面要给目录"; TO="$1"; shift ;;
    --modules) shift; [ $# -gt 0 ] || die "--modules 后面要给路径"; MODULES="$1"; shift ;;
    --link) LINK=1; shift ;;
    --dry-run) DRY=1; shift ;;
    --no-verify) DO_VERIFY=0; shift ;;
    --uninstall) DO_UNINSTALL=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --*) die "不认识的选项：$1（-h 看用法）" ;;
    *) die "多余的参数：$1（-h 看用法）" ;;
  esac
done

# ── 装到哪 ──────────────────────────────────────────────
default_root() {
  if [ -n "${WORKBUDDY_SKILLS:-}" ]; then printf '%s' "$WORKBUDDY_SKILLS"; return; fi
  if [ -n "${CLAUDE_SKILLS:-}" ]; then printf '%s' "$CLAUDE_SKILLS"; return; fi
  [ -d "$HOME/.workbuddy" ] && { printf '%s' "$HOME/.workbuddy/skills"; return; }
  [ -d "$HOME/.claude" ] && { printf '%s' "$HOME/.claude/skills"; return; }
  [ -d "$HOME/.codex" ] && { printf '%s' "$HOME/.codex/skills"; return; }
  printf '%s' "$HOME/.workbuddy/skills"
}
[ -n "$TO" ] || TO=$(default_root)
TO="${TO/#\~/$HOME}"
pdir=$(dirname "$TO")
[ -d "$pdir" ] && TO=$(cd "$pdir" && pwd)/$(basename "$TO")

# ── 找 python3 ─────────────────────────────────────────
# /usr/bin/python3 在没装 Command Line Tools 的 mac 上会弹 2 GB 下载窗，
# 看着像脚本卡死。所以：先看 CLT 在不在，不在就绕开系统 Python。
pick_python() {
  skip_sys=0
  if [ "$(uname -s)" = "Darwin" ] && command -v xcode-select >/dev/null 2>&1; then
    xcode-select -p >/dev/null 2>&1 || skip_sys=1
  fi
  for c in python3 python3.13 python3.12 python3.11 /usr/local/bin/python3 /opt/homebrew/bin/python3; do
    command -v "$c" >/dev/null 2>&1 || continue
    real=$(command -v "$c")
    case "$real" in
      /usr/bin/*) [ "$skip_sys" = 1 ] && continue ;;
    esac
    "$real" -c 'import sys' >/dev/null 2>&1 && { printf '%s' "$real"; return 0; }
  done
  for c in "$HOME"/.workbuddy/binaries/python/versions/*/bin/python3; do
    [ -x "$c" ] && { printf '%s' "$c"; return 0; }
  done
  return 1
}

# 兼容三种包结构：直接放 mqc-*／<顶层>/mqc-*／<顶层>/skills/mqc-*
find_msrc() {
  base=$1
  for cand in "$base" "$base/skills" "$base"/* "$base"/*/skills; do
    [ -d "$cand" ] || continue
    for sub in "$cand"/mqc-*; do
      [ -d "$sub" ] && { printf '%s' "$cand"; return 0; }
    done
  done
  return 1
}

# ── 卸载 ────────────────────────────────────────────────
if [ "$DO_UNINSTALL" = 1 ]; then
  say ""; say "卸载 legal-case-flow"; hr
  say "位置：$TO/$NAME"
  if [ ! -e "$TO/$NAME" ]; then
    die "这里没有 ${NAME}，无需卸载。"
  fi
  if [ "$DRY" = 1 ]; then
    say "（--dry-run）会删掉上面这个目录，并恢复最近的 .backup-* 备份（如果有）。"
    exit 0
  fi
  rm -rf "$TO/$NAME"
  ok "已删除 $TO/$NAME"
  latest=$(ls -dt "$TO"/.backup-* 2>/dev/null | head -1)
  if [ -n "$latest" ] && [ -d "$latest/$NAME" ]; then
    mv "$latest/$NAME" "$TO/$NAME"
    ok "已从 $(basename "$latest") 恢复旧版本"
  fi
  say ""
  say "上游模块（mqc-*）不属于本仓库，未动。要清掉自己删：rm -rf $TO/mqc-*"
  exit 0
fi

# ── 源在哪 ──────────────────────────────────────────────
SRC=""
if [ -f "$SELF_DIR/skill/SKILL.md" ]; then
  SRC="$SELF_DIR/skill"
elif [ -f "$SELF_DIR/SKILL.md" ] && [ -d "$SELF_DIR/scripts" ]; then
  SRC="$SELF_DIR"
fi
[ -n "$SRC" ] || die "这个目录里找不到 skill/（SKILL.md + scripts/）。请在本仓库根目录运行，或把仓库 clone 完整。"

say ""
say "legal-case-flow v$PKG_VERSION · 安装"
hr
say "系统：$(uname -s) $(uname -r) $(uname -m)"
PY=$(pick_python) || die "没找到可用的 python3。装一个（python.org 的安装包最省事）再回来。"
ok "Python：$PY"
ok "源目录：$SRC"
say "装到：$TO/$NAME$([ "$LINK" = 1 ] && echo "（软链接）")"

if [ "$DRY" = 1 ]; then
  say ""
  say "（--dry-run）将执行："
  say "  · 同名目录先备份到 ${TO}/.backup-${STAMP}（若已存在）"
  [ "$LINK" = 1 ] && say "  · 建软链接 ${TO}/${NAME} → $SRC" || say "  · 拷贝 $SRC → ${TO}/${NAME}"
  [ -n "$MODULES" ] && say "  · 上游模块：$MODULES"
  say "  · 验证三连：bind --plan / native check / pack doctor"
  exit 0
fi

mkdir -p "$TO" || die "建不了目录：$TO"

# ── 备份 ────────────────────────────────────────────────
BAK=""
if [ -e "$TO/$NAME" ] && [ "$LINK" = 0 ]; then
  if [ -L "$TO/$NAME" ]; then
    rm -f "$TO/$NAME"            # 旧的软链接不用备份，直接换
  else
    BAK="$TO/.backup-$STAMP"
    mkdir -p "$BAK"
    mv "$TO/$NAME" "$BAK/$NAME" || die "备份失败：${TO}/${NAME}（有程序正打开它？）"
    warn "旧版本已备份到 $(basename "$BAK")/$NAME"
  fi
elif [ -L "$TO/$NAME" ]; then
  rm -f "$TO/$NAME"
fi

# ── 安装本体 ────────────────────────────────────────────
if [ "$LINK" = 1 ]; then
  ln -s "$SRC" "$TO/$NAME" || die "建软链接失败"
  ok "已链接：$TO/$NAME → $SRC"
else
  cp -R "$SRC" "$TO/$NAME" || die "拷贝失败"
  ok "已拷贝到 $TO/$NAME"
fi

# mac：从网盘/U 盘下来的会带下载隔离标记，脚本一跑就被拦
if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "$TO/$NAME" 2>/dev/null && ok "已清苹果的下载隔离标记"
fi

# ── 上游模块（可选） ────────────────────────────────────
if [ -n "$MODULES" ]; then
  MODULES="${MODULES/#\~/$HOME}"
  [ -e "$MODULES" ] || die "找不到模块包：$MODULES"
  TMPM=""
  case "$MODULES" in
    *.tar.gz|*.tgz)
      TMPM=$(mktemp -d "${TMPDIR:-/tmp}/lcf-mod.XXXXXX")
      tar xzf "$MODULES" -C "$TMPM" || die "解包失败：包可能没拷全"
      MSRC=$(find_msrc "$TMPM") || die "这个包里没有 mqc-* 模块目录"
      ;;
    *)
      [ -d "$MODULES" ] || die "不是 tar.gz，也不是目录：$MODULES"
      MSRC=$(find_msrc "$MODULES") || die "这个目录里没有 mqc-* 模块"
      ;;
  esac
  n=0
  for d in "$MSRC"/mqc-*; do
    [ -d "$d" ] || continue
    name=$(basename "$d")
    if [ -e "$TO/$name" ]; then
      [ -z "$BAK" ] && { BAK="$TO/.backup-$STAMP"; mkdir -p "$BAK"; }
      mv "$TO/$name" "$BAK/$name" 2>/dev/null
    fi
    cp -R "$d" "$TO/$name" || die "拷贝模块失败：$name"
    n=$((n+1))
  done
  ok "装了 $n 个上游模块"
  command -v xattr >/dev/null 2>&1 && xattr -dr com.apple.quarantine "$TO" 2>/dev/null
  [ -n "$TMPM" ] && rm -rf "$TMPM"
fi

# ── 验证 ────────────────────────────────────────────────
if [ "$DO_VERIFY" = 1 ]; then
  S="$TO/$NAME/scripts"
  say ""; say "验证一：角色探测"; hr
  "$PY" "$S/bind.py" --plan || warn "探测有报错，看上面哪一行"

  say ""; say "验证二：本机原生通路（mac 上才有意义）"; hr
  "$PY" "$S/native.py" check || warn "原生体检没跑完"

  say ""; say "验证三：第三方依赖"; hr
  "$PY" "$S/pack.py" doctor || warn "依赖体检没跑完"
fi

say ""; hr
say "装完了。开工："
say ""
say "  $PY $TO/$NAME/scripts/flow.py init 案件名 --title \"某某诉某某\""
say "  $PY $TO/$NAME/scripts/flow.py next 案件名"
say ""
say "找不到角色（第七个都是「未安装」）说明只有编排层、没有上游模块，见 docs/install.md。"
say ""
