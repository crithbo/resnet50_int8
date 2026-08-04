# QLinearAdd mutable plan warning 测试修复

日期：2026-07-27

## RETURN_ANALYSIS

最终联合自检发现仓库合同测试把 `warnings=[]` 写成绝对断言；主线合法更新 plan 后，
validator 正确返回：

```text
valid=true
warnings=["mutable read receipt drift: .agents/plan.md"]
```

测试现改为：

1. checked-in 合同允许零 warning，或只允许上述唯一 mutable plan warning；
2. warning 列表最多一项，任何其他 warning 仍失败；
3. 新增强制 plan receipt 漂移测试，要求 `valid=true`、唯一 warning 精确匹配、
   `materialization_allowed=false`；
4. 新增 active QLinearAdd rule SHA 漂移测试，要求 `valid=false` 并出现精确
   `current-match rule SHA mismatch`；
5. 既有两条 active rule current-match、P0-A、17-instance、lifetime 和
   fail-closed 检查保持不变。

本轮不追写 plan SHA，不修改 plan/rules/RTL，不生成目标或服务器资产。
