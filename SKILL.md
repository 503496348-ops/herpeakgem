---
name: herpeakgem
description: "他山之石智能教育平台 — 多 Agent 协作教学、知识库管理、Web 服务"
triggers:
  - "教育"
  - "教学"
  - "智能教育"
  - "Agent教学"
  - "知识库"
  - "herpeakgem"
  - "他山之石"
---

# HerPeakGem — 他山之石智能教育平台

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
