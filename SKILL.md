---
name: herpeakgem
description: "他山之石智能教育平台 — 多 Agent 协作教学、知识库管理、Web 服务"
license: MIT
metadata:
  author: 503496348-ops
  version: 1.0.0
---

# HerPeakGem — 他山之石智能教育平台

## 触发条件

- "教育"
- "教学"
- "智能教育"
- "Agent教学"
- "知识库"
- "herpeakgem"
- "他山之石"

Agent-Native 的个性化教学平台，支持多 Agent 协作教学、知识库管理、Web 服务。

## 核心能力

| 命令 | 说明 |
|------|------|
| `herpeakgem serve` | 启动 Web 服务 |
| `herpeakgem setup` | 初始化 PocketBase 集合 |
| `herpeakgem skills` | 列出内置技能 |
| `herpeakgem doctor` | 健康诊断 |
| `herpeakgem update` | 检查更新 |
| `herpeakgem info` | 产品信息（模块/技能统计） |

## 快速开始

```bash
# 启动 Web 服务
python3 scripts/cli.py serve --port 8080

# 查看内置技能
python3 scripts/cli.py skills

# 健康诊断
python3 scripts/cli.py doctor
```

## 架构

- `herpeakgem/agents/` — 多 Agent 管道（research/question/session）
- `herpeakgem/services/` — 核心服务（session/turn_runtime/config）
- `herpeakgem/api/` — API 路由
- `herpeakgem/runtime/` — Web 运行时
- `herpeakgem/skills/builtin/` — 内置技能（docx/pptx/xlsx/pdf/skill-creator）

## 测试

```bash
python3 -m pytest tests/ -q
```

## J-Space 增强（深度推理/模式路由）

基于 J-Space Cognition Suite v3.2 的深度推理协议增强教学推理：
- 解释门（歧义分离→承诺解释）
- 七种工作模式路由（AUTO/FOCUS/DEEP/DENSE/EXTERNAL/EMPIRICAL/RECOVERY）
- 深度循环（Frame→Bridge→Derive→Stress→Commit→Checkpoint）
- 顺序检查（结论先行回退）

详见 `references/j-space-deep-reasoning.md`

## DNA Memory 融合（跨session学习+偏好记忆）

基于 [DNA Memory](https://github.com/AIPMAndy/dna-memory) 跨session学习增强：
- 教学场景记忆分型（学生偏好/已掌握知识点/错误模式/教学策略）
- 跨session学习循环（recall→调整→提取→写入）
- 有界记忆原则（只记结论不记transcript）

详见 `references/dna-memory-learning-pattern.md`
