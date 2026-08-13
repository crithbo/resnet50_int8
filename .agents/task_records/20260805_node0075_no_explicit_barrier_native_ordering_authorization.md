# 2026-08-05 node0075 no-explicit-barrier native-ordering authorization

## 用户裁决

- owner：QLinearMatMul/node0075 `019fc775-8de0-7f10-bc4a-026a4673776f`
- mainline：`019fbec2-fe93-7e03-9314-cff6f222f33d`
- status：`AUTHORIZED_DIAGNOSTIC_INTEGRATION_BUILDING`
- functional RTL modification：`false`
- server action：`false`
- mainline plan SHA256 after adjudication：
  `5767a496a0aaa33d2a1b55d5cfc237e9cc5a9192da59a25079a97d0e602779a9`

用户要求先假设 node0071 前序可以正常完成。现有 current source 足以证明 opcode110 没有
live barrier decode，DataHub RD/WR 使用独立 queue 与 round-robin arbitration；但缺少
确切架构规格时，不再把“没有显式通用 fence”定性成 RTL bug，也不等待 RTL 修改。

## 授权实现

允许 owner 在同一 simulator、同一 execplan 中物化：

```text
graph-external typed input
→ real node0071 ordered 8 stages
→ normal config/command transition
→ node0075 24 stages with exact 8-pass A reload
```

边界：

- opcode110 不计为 barrier，不声称存在 producer visibility fence；
- 不允许两次仿真间 dump/reload；
- 不允许 A internal preload、host copy/precompute/replay；
- producer base 不得冒充 node0075 consumer acceptance；
- package 固定为 `DIAGNOSTIC_ONLY`、`candidate_release=false`；
- observer 只读记录 node0071 final write 的 downstream/hub acceptance、node0075 pass00
  first read、8192×32B actual accepted reads与必要顺序边界；
- formal D 独立裁决，compositional E2 不升级为服务器 E3/E4/E5；
- 动态顺序或 D 失败先分类为 instance scheduling/ordering failure，不自动归因 RTL。

## Blocker delta

- 旧 `B_MATMUL_NODE0075_E1FB0F7_PRODUCER_VISIBILITY_BARRIER_FIELD_UNEXPRESSIBLE`
  不再作为本实例生成前硬停门；其“opcode110无live barrier”事实仍保留。
- 旧 `B_MATMUL_NODE0075_SERVER_SELF_CONTAINED_PRODUCER_BARRIER_UNMATERIALIZED`
  由同一仿真真实 producer prefix 的诊断路径取代，不宣称通用 barrier 能力关闭。
- 新 active：
  `B_MATMUL_NODE0075_NATIVE_ORDERING_INTEGRATION_MATERIALIZATION`。
- 后续动态门：
  `B_MATMUL_NODE0075_SERVER_NATURAL_TERMINAL`、
  `B_MATMUL_NODE0075_FORMAL_D`。

## 规则边界

`CDA-EXECPLAN-BARRIER-OPCODE-LIVE-DRAIN-SEMANTICS-001` 继续有效：本路径明确不把
no-op opcode110、Start_Comp 串行或 ingress acceptance 冒充 visibility barrier。
该用户授权只允许验证 frozen instance 的自然顺序，不关闭通用 barrier 语义门，也不授权
修改 GAP 功能 workload、公共规则或 functional RTL。
