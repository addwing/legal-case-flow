# 最小示例：一个虚构的买卖合同纠纷

这是**全案虚构**的底稿，只为演示字段长什么样、两个转接脚本吃什么、吐什么。
里面的公司、人名、金额、日期都是编的，不要当真实案例引用。

## 它是什么

一份合规的 `casefile.json`（`mqc-casefile/1`）：3 份材料、3 个当事人、5 条事实、1 条不确定项。
这是 `facts` 角色（大事记）最后吐出来的底稿；有了它，下游才能接。

## 跑一遍

```bash
# 1. 转成庭审对抗图的输入骨架，另出一份事实挂载表
python3 skill/scripts/handoff.py matrix examples/minimal/casefile.json \
        -o /tmp/matrix-input.json --index /tmp/事实挂载表.md

# 2. 转成法律关系图的输入（只出主体，不出关系）
python3 skill/scripts/handoff.py relations examples/minimal/casefile.json \
        -o /tmp/relations.json
```

## 你会看到什么

`matrix-input.json` 有四段：`case` / `claims` / `parts` / `scope`。**标题、材料范围、对账锚、
事实索引是自动填的，其余留空**，脚本会逐条列出待办：

```
□ case.stance：我代理谁（原告向 / 被告向）—— 必须问律师，底稿推不出来
□ case.procedural：管辖 / 主体 / 重复起诉，三项都要写到
□ scope.maturity：L0／L1／L2／L3，按材料齐备程度定
□ claims：诉请逐条固定，类型取自封闭表，金额要有构成明细
□ parts／elements：请求权基础 → 要件拆解 → 四段攻防，四段正文照录
```

`relations.json` 有 3 个主体节点、1 个客体候选（按材料名「买卖合同」筛出来的）、**0 条关系**：

```
□ edges 一条都没有 —— 关系名与指向必须照录原文，脚本猜不出来
```

## 为什么故意留空

这两份产物是**骨架，不能直接出图**。底稿里有的照搬，底稿里没有的一律留空。
编号、关系名、诉请类型、金额构成这些一旦被脚本「猜」出来，就会带着错一路走到交付物上。
留空是设计，不是没做完。

## 别把真实卷宗放进仓库

真要提 issue 附带材料时，把当事人姓名、公司名、案号、金额换成虚构值。
律师的卷宗涉隐私与执业义务，公开仓库不是放它的地方。
