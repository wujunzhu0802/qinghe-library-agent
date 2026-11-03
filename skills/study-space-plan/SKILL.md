---
name: study-space-plan
description: 当用户要求推荐学习地点时，按人数、用途和场地规则给出可核对的建议。
---

1. 确定人数和用途；缺任一信息就追问。讨论用 discussion=true；安静自习用 false。
2. 使用 search_spaces 筛选。无匹配时说明原因，建议拆分小组或调整用途。
3. 使用 lookup_policy 查询 booking；需要开放时间时另查 hours。
4. 按“建议 → 预约 → 来源”输出，引用空间和规则 ID。注明为模拟数据，不声称有实时空位或已预约。
