# DNA Memory 学习模式融合

> 来源: [DNA Memory](https://github.com/AIPMAndy/dna-memory) — 跨session学习记忆
> 融合目标: 学生偏好记忆、历史错误追踪、教学决策记录

## 教学场景记忆分型

| 类型 | 教学应用 |
|------|---------|
| preference | 学生学习偏好（视觉/听觉/实践） |
| fact | 已掌握知识点 |
| insight | 学习规律（某学生在X方面容易犯错） |
| decision | 教学策略选择及理由 |
| project_state | 学生当前学习进度 |
| open_loop | 待补强知识点 |
| workflow | 有效教学流程 |
| error_lesson | 常见错误模式 |

## 跨session学习循环

```
新session开始
  → recall学生偏好/历史错误/进度
  → 调整教学策略
  → session结束
  → 提取新认知（掌握/未掌握/新错误模式）
  → memory_remember写入
```

## 有界记忆原则

- 只记结论不记transcript："学生在分数运算中常忘记通分"
- 不记："学生问了3+5等于几，我回答8"
- 权重随使用反馈调整：recall命中+useful=强化
