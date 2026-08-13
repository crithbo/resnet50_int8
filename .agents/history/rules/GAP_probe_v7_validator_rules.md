# GAP hwop-0071 probe_v7 validator rules

最后更新：2026-08-02（增加多输入握手 conjunction 的逐因子可观测门）

证据版本：`gap_hwop0071_probe_v7_return_20260724`。本文件只定义规则与
发布门，不修改功能 RTL，也不替代回传目录中的测试分析结论。

## 规则 ID

- `CDA-GA-OUTBUFFER-OCCUPANCY-001`：任意周期必须满足
  `0 <= count <= DEPTH`。transout compaction 只能移除实际有效项，写入只能按
  实际接受握手增加；occupancy 不足时禁止固定无符号减法。v7 的反例是 depth=2
  时 8 个普通 PE 在 700313000→700316000 ps 从 1 回绕到 3。
- `CDA-GA-INVALID-SLOT-ISOLATION-001`：tag/valid 无效的槽不得影响 ALU tag
  或 input C。清 tag 而保留 data 仅在所有 consumer 都以 valid gating 时安全。
- `CDA-GA-CROSS-BLOCK-INIT-001`：新 block 在新 partial 有效前必须保持 C=0；
  `transout_initial` 不能单独授权 feedback。v7 在 700318000 ps 首批 8 PE 已复用
  invalid-slot，完整分析共命中 217 次。
- `CDA-GAP-ORTHOGONAL-DEFECTS-001`：GA stale-C 属于 `RTL_CONTROL`；
  D-index carrier 属于独立 `CONFIG_SEMANTICS`。修复或验证其中一项不得解除另一项。
- `CDA-GAP-D-READBACK-COVERAGE-001`：每个正式 D slice 必须覆盖全部 512 条
  128-bit 地址并逐条通过 golden。请求总数正确不构成发布证据；v7 的 512 请求只有
  2 个唯一 D 地址，16 个 slice 均未通过。
- `CDA-MSE4-MONITOR-EVIDENCE-001`：本地 monitor 的 request/wdata 相差 1
  不能单独定性 RTL 丢写。结论必须由同一时钟域 observer 或正式 D 回读支持；v5
  same-clock observer 已给出 512/512。
- `CDA-SERVER-FOCUSED-IDENTITY-001`：全树 hash 不同不能单独否决服务器结果。
  必须联合检查 pre/post/post-run 稳定性和 focused RTL 逐文件一致性；本次 focused
  RTL 为 14/14 一致，TB、workload 与包身份稳定。
- `CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001`：双输入 GA 在已经进入执行、
  但 joint accept 长时间保持为 0 时，诊断证据必须分别统计两条正式 producer→buffer
  的 qualified acceptance、每个启用 operand 的 inbuffer capture/tag match，以及
  joint GA accept。只证明其中一路进入 Buffer、只观察 aggregate GA accept，或把
  ready/valid/buffer occupancy 等持续高 level 当作逐周期新事务，均不足以给配置或
  RTL 定责。若 formal D 全部缺失，则 `mismatch=0` 必须标记为 unevaluable，不能写成
  数值通过。

  node0071 v7 的冻结动态反例为：MSE4 D write-address request 已接受，MSE0→Buffer0
  也有 qualified acceptance，但 8 个启用 regular GA PE 在 128,450,560 active
  cycles 内 joint input accept 始终为 0，随后 GA output、MSE4 write-data、terminal
  和 48 项 formal D 全部缺失。旧包未观测 MSE3→Buffer4 与逐 operand capture/tag，
  因此根因只能收窄为
  `MSE0_TO_BUFFER0_ACCEPTED + READ_STREAM3_PATH_UNOBSERVED ->
  GA_DUAL_OPERAND_ACCEPT_ABSENT`，不得越界归责。
- `CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001`：双输入 GA 在已经进入执行、
  但 joint accept 长时间保持为 0 时，诊断证据必须分别统计两条正式 producer→buffer
  的 qualified acceptance、每个启用 operand 的 inbuffer capture/tag match，以及
  joint GA accept。只证明其中一路进入 Buffer、只观察 aggregate GA accept，或把
  ready/valid/buffer occupancy 等持续高 level 当作逐周期新事务，均不足以给配置或
  RTL 定责。若 formal D 全部缺失，则 `mismatch=0` 必须标记为 unevaluable，不能写成
  数值通过。

  node0071 v7 的冻结动态反例为：MSE4 D write-address request 已接受，MSE0→Buffer0
  也有 qualified acceptance，但 8 个启用 regular GA PE 在 128,450,560 active
  cycles 内 joint input accept 始终为 0，随后 GA output、MSE4 write-data、terminal
  和 48 项 formal D 全部缺失。旧包未观测 MSE3→Buffer4 与逐 operand capture/tag，
  因此根因只能收窄为
  `MSE0_TO_BUFFER0_ACCEPTED + READ_STREAM3_PATH_UNOBSERVED ->
  GA_DUAL_OPERAND_ACCEPT_ABSENT`，不得越界归责。

- `CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001`：当 GAP 停点被收窄到
  多输入 ready/backpressure conjunction 时，诊断证据必须给出该 conjunction 的 RTL
  方程，并分别返回每个 conjunct 的语义 owner、qualified/rate-limited edge 或状态证据、
  采样时钟域与覆盖窗口。conjunction output 为 0 只能证明至少一个输入阻塞，不能单独
  指认某个叶因。

  若任一 conjunct 未独立返回，正式裁决必须保留剩余叶因的析取，并标记
  `PENDING_LEAF`；稳定 level、下游零计数或较早事务不能补齐缺失因子，也不得据此归咎
  CONFIG、RTL、服务器环境或先延长 timeout。只有逐因子证据与 conjunction output、
  queue dequeue/address-write 等 qualified 边界相互一致时，才能把首分歧推进到唯一
  leaf owner。

最终动态分类固定为
`ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse`。

上面的历史分类只适用于其绑定的 `gap_hwop0071_probe_v7_return_20260724` 证据。
2026-07-31 的 node0071 完整配置回传属于新的双输入 ingress 卡死边界，必须按
`CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001` 独立裁决，不得沿用历史分类。

上面的历史分类只适用于其绑定的 `gap_hwop0071_probe_v7_return_20260724` 证据。
2026-07-31 的 node0071 完整配置回传属于新的双输入 ingress 卡死边界，必须按
`CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001` 独立裁决，不得沿用历史分类。

机器执行入口：

- `resnet50_pipeline.gap_ga_accumulator_state.outbuffer_occupancy_transition`
- `resnet50_pipeline.gap_ga_accumulator_state.feedback_operand_is_legal`
- `resnet50_pipeline.gap_d_index_schedule.d_index_release_decision`
- `contracts/operator_config/gap_ga_accumulator_state_v1.json`
- `contracts/operator_config/gap_d_index_schedule_v1.json`

证据绑定：

- `server_returns/gap_hwop0071_probe_v7_return_20260724/GAP_PROBE_V7_DIAGNOSIS.md`
- `server_returns/gap_hwop0071_probe_v7_return_20260724/gap_probe_v7_analysis.json`
- `server_returns/gap_hwop0071_probe_v7_return_20260724/gap_numeric_path_report_v7.json`
- `server_returns/gap_hwop0071_probe_v7_return_20260724/native_return_acceptance_v7.json`

