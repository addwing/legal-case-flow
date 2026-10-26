---
name: 问题报告
about: 装不上、探测不到、出不了图、文档说错
title: "[bug] "
labels: bug
---

## 现象

<!-- 一句话说清发生了什么，例如「bind --plan 里七个角色全是未安装」 -->

## 期望

<!-- 你以为会发生什么 -->

## 复现

```bash
# 你敲的命令，按顺序
```

## 环境

| 项 | 值 |
| --- | --- |
| 系统 | <!-- macOS 15.7 / Ubuntu 24.04 WSL2 --> |
| 芯片 | <!-- Apple Silicon / Intel / x86_64 --> |
| Python | <!-- python3 -V --> |
| 安装方式 | <!-- git clone + install.sh / Release 包 / --link --> |
| 上游模块 | <!-- 七个都装了 / 只装四个 / 没有 --> |

## 两条诊断输出

```bash
python3 <技能>/scripts/bind.py --plan
python3 <技能>/scripts/pack.py doctor
```

把完整输出贴在这里（不是片段）。

## 附加信息

<!-- 相关日志、截图、你改过的配置 -->

---

**请不要贴真实卷宗。** 当事人姓名、公司名、案号、金额、证据内容请换成虚构值；
确实需要举例时，用 `examples/minimal/` 那种虚构数据。涉及执业保密的内容，
只描述结构、不贴原文。
