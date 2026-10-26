#!/usr/bin/env bash
# 冒烟测试：不装依赖、不联网、不改系统，20 秒内回答「这个仓库是不是好的」。
# 用法：bash tests/smoke.sh          （CI 与本机都用这一条）
set -u

REPO=$(cd "$(dirname "$0")/.." && pwd)
PY=${PYTHON:-python3}
PASS=0
FAIL=0
TMP=""

ok()   { PASS=$((PASS+1)); printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31m✗\033[0m %s\n' "$*"; }
head_() { printf '\n\033[1m%s\033[0m\n' "$*"; }

cleanup() { [ -n "$TMP" ] && rm -rf "$TMP"; }
trap cleanup EXIT

head_ "1. 仓库结构"
for f in README.md LICENSE NOTICE CHANGELOG.md install.sh .gitignore \
         skill/SKILL.md skill/capabilities.json \
         skill/scripts/bind.py skill/scripts/handoff.py skill/scripts/pack.py \
         skill/scripts/flow.py skill/scripts/native.py \
         docs/install.md docs/usage.md docs/commands.md docs/architecture.md \
         docs/macos-native.md docs/troubleshooting.md \
         examples/minimal/casefile.json examples/minimal/README.md \
         tools/collect-modules.py .github/workflows/ci.yml; do
  [ -f "$REPO/$f" ] && ok "$f" || bad "缺 $f"
done

head_ "2. Python 语法"
if "$PY" -m py_compile "$REPO"/skill/scripts/*.py 2>/dev/null; then
  ok "五个脚本都能编译"
else
  bad "有脚本语法不过"
fi
rm -rf "$REPO"/skill/scripts/__pycache__

head_ "3. capabilities.json"
if "$PY" - "$REPO/skill/capabilities.json" <<'EOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
roles = d["roles"]
want = {"facts","chronology","structure","adversary","data","deck","redraw"}
assert set(roles) == want, "角色不是七个：%s" % (set(roles) ^ want)
for r, e in roles.items():
    assert e.get("candidates"), r
    assert e.get("probe"), r
assert set(d["contracts"]) == {"casefile","relations","matrix"}
assert "platform" in d and "native" in d["platform"]
print("7 个角色、3 份契约、platform 段齐备")
EOF
then ok "结构与契约完整"; else bad "capabilities.json 不合法"; fi

head_ "4. SKILL.md 自报名字对得上"
name=$(sed -n 's/^name:[[:space:]]*\([^[:space:]]*\).*/\1/p' "$REPO/skill/SKILL.md" | head -1)
[ "$name" = "legal-case-flow" ] && ok "name: $name" || bad "SKILL.md 的 name 是「$name」，应为 legal-case-flow"

head_ "5. 探测脚本能跑（空目录应当全 missing，但 JSON 必须合法）"
TMP=$(mktemp -d "${TMPDIR:-/tmp}/lcf-smoke.XXXXXX")
mkdir -p "$TMP/empty"
if out=$("$PY" "$REPO/skill/scripts/bind.py" --json --roots "$TMP/empty" 2>&1); then
  if printf '%s' "$out" | "$PY" -c 'import json,sys; d=json.load(sys.stdin); assert len(d["roles"])==7; print("JSON 合法，7 角色")'; then
    ok "bind.py --json 可用"
  else
    bad "bind.py --json 输出不是合法 JSON"
  fi
else
  bad "bind.py --json 退出码非 0：$out"
fi

head_ "6. 每个子命令的 --help 都能退 0"
for s in bind handoff pack flow native; do
  if "$PY" "$REPO/skill/scripts/$s.py" --help >/dev/null 2>&1; then ok "$s.py --help"; else bad "$s.py --help 退出码非 0"; fi
done

head_ "7. 装到临时目录（真实安装，不碰你的 ~/.workbuddy）"
if bash "$REPO/install.sh" --dry-run >/dev/null 2>&1; then ok "install.sh --dry-run"; else bad "install.sh --dry-run 失败"; fi
if bash "$REPO/install.sh" --to "$TMP/skills" --no-verify >/dev/null 2>&1; then
  if [ -f "$TMP/skills/legal-case-flow/SKILL.md" ] && [ -f "$TMP/skills/legal-case-flow/scripts/flow.py" ]; then
    ok "装出来的目录结构正确"
  else
    bad "装完缺 SKILL.md 或 scripts/"
  fi
  if "$PY" "$TMP/skills/legal-case-flow/scripts/bind.py" --plan --roots "$TMP/skills" >/dev/null 2>&1; then
    ok "装完能跑 bind.py"
  else
    bad "装完 bind.py 跑不起来"
  fi
else
  bad "install.sh 真实安装失败"
fi

head_ "8. 示例底稿能跑通两处转接"
EX="$REPO/examples/minimal/casefile.json"
if [ -f "$EX" ]; then
  if "$PY" "$REPO/skill/scripts/handoff.py" matrix "$EX" -o "$TMP/matrix-input.json" \
        --index "$TMP/事实挂载表.md" >/dev/null 2>&1 \
     && "$PY" "$REPO/skill/scripts/handoff.py" relations "$EX" -o "$TMP/relations.json" >/dev/null 2>&1; then
    ok "matrix 与 relations 都出得来"
    if "$PY" - "$TMP/matrix-input.json" "$TMP/relations.json" <<'EOF'
import json, sys
m = json.load(open(sys.argv[1], encoding="utf-8"))
r = json.load(open(sys.argv[2], encoding="utf-8"))
assert set(m) == {"case", "claims", "parts", "scope"}, set(m)
assert len(r.get("nodes", [])) >= 3, len(r.get("nodes", []))
assert r.get("edges", []) == [], "两处转接不该生成关系"
print("骨架结构正确：%d 段 / %d 个主体 / 0 条关系" % (len(m), len(r["nodes"])))
EOF
    then ok "骨架字段符合契约"; else bad "骨架字段不对"; fi
  else
    bad "示例底稿跑不通（转接脚本或示例结构坏了）"
  fi
else
  bad "缺 examples/minimal/casefile.json"
fi

head_ "9. 本机原生通路（仅 macOS）"
if [ "$(uname -s)" = "Darwin" ]; then
  if "$PY" "$REPO/skill/scripts/native.py" check >/dev/null 2>&1; then ok "native.py check"; else bad "native.py check 失败"; fi
else
  printf '  \033[33m·\033[0m 非 macOS，跳过（原生那套只在 mac 上成立）\n'
fi

printf '\n────────────────────────────────────────\n'
if [ "$FAIL" = 0 ]; then
  printf '\033[32m全部通过：%d 项\033[0m\n' "$PASS"
  exit 0
fi
printf '\033[31m失败 %d 项，通过 %d 项\033[0m\n' "$FAIL" "$PASS"
exit 1
