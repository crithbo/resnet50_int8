# QLinearAdd 17-instance stage0 config-only materialization

Date: 2026-07-27

Status: `STAGE0_MATERIALIZED_TAIL_BLOCKED_NOT_RELEASED`

## RETURN_ANALYSIS

本轮只物化 QLinearAdd 的 W3 前半段，输出停在显式 `SUM_F32` scratch；没有把尚未闭合的
UINT8 quant tail、Y 输出或服务器结果冒充完整 QLinearAdd。

17 个逻辑 QLinearAdd 被拆成 51 个串行物理 stage：

1. A: `uint8 -> float32(A-zpA) -> round_float32(*scaleA)`；
2. B: `uint8 -> float32(B-zpB) -> round_float32(*scaleB)`；
3. `round_float32(A_SCALED+B_SCALED)`，A/B 只在 pair 同时 ready 且 D ready 时接受。

每个实例使用 A-scaled、B-scaled、sum 三个不 alias 的 FP32 scratch，arena 为
`[0x0000000400000000, 0x000000043f2c03c0)`，51 个 allocation，共
1,059,849,152 physical bytes / 1,059,849,120 logical bytes；当前 stage0 scratch traffic
为 1,766,395,200 logical bytes（不含未来 tail read）。代价是 51 个物理 stage、显式
DRAM round trip、每阶段 barrier 与低 GA 利用率。

node0076 不物化 16x B copy：

- 原始/缩放后 B 的逻辑 region 都只有 1000 元素；
- B-dequant 为 63 occurrence，末 occurrence 8 个有效元素 / 32 个有效输出 bytes；
- B-scaled physical allocation 为 4032 bytes，其中 4000 typed bytes、32 padding bytes；
- FP32-add 按 `logical_output_index % 1000` 重放同一 B-scaled region 16 次；
- validator 枚举并核对全部 16,000 个 replay 地址。

物化文件：

- `configs/qlinearadd_stage0_config_only/qlinearadd_stage0_config_only_v1.json`
- `contracts/operator_config/qlinearadd_stage0_config_only_contract_v1.json`
- `artifacts/qlinearadd_stage0_config_only/validation_report.json`
- `resnet50_pipeline/qlinearadd_stage0_config_only.py`
- `tools/build_qlinearadd_stage0_config_only.py`
- `tools/validate_qlinearadd_stage0_config_only.py`
- `tests/test_qlinearadd_stage0_config_only.py`

公共规则在派发后合法漂移。实际完整复读并绑定：

```text
0c8c1963e7bf0967748ce6a41336eeb6163cbc23260dea157556c5d37464ebc9  .agents/rules/算子配置规则.md
c4c355d8f4a2ba4b2b0b34310b46b8696a87514a78c4a798c91262f2addee74e  .agents/rules/QLinearAdd算子配置规则.md
5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0  .agents/rules/精确UINT8量化尾专项规则.md
```

`CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001` 已进入 current-match 门。
本族 project-stage 配置逐 stage 记录 qparam、shape/occurrence、base、replay、readiness 和拓扑
owner，并从最终 occurrence 重算每个 scratch 正式输出的 unique byte coverage。由于 native
address-bound JSON 尚未生成，native static/final leaf diff、mapping、bitstream、execplan/SCA
仍明确为 open；没有用 project schema 回读替代该门。

共享 tail 合同 SHA 漂移到
`d75f5aa3bfd5038ca4e53da1568fb651358d6f34f5de20fdfb01cc095f0e0b69`，
但状态、决策与首个 FMA rounding 反例均未改变；P1-A 只刷新依赖收据，未重做数值分析。

## BYPASS_ANNOTATION

### bypass_reason

功能 RTL 被用户冻结；native `add_dequant` 在 FP32 输出结束且把分支仿射式重关联。全
uint8 标量域证明 node0007 和 node0070 存在最终 UINT8 反例。

### contradicted_or_missing_native_path

禁止复用 native `add_dequant` 的常数 1、MAC 仿射重关联和缺失的输出量化；native FP32 add
只作结构 oracle，不是完整 QLinearAdd 数值授权。

### exact_equivalence_scope

覆盖冻结的 17 个实例、A/B 各自完整 256 标量域、每实例 65,536 个 A/B FP32-sum 标量对、
stage0 occurrence/terminal、node0076 broadcast replay、scratch non-alias、barrier 与
accepted-handshake lifetime。明确不覆盖 UINT8 output tail。

### materialized_configuration_mechanism

每实例三个串行 physical stage：W3 A-dequant、W3 B-dequant、paired FP32 add；使用显式
FP32 DRAM scratch、completion barrier、normal outbuffer 与 node0076 B-region replay。

### performance_and_resource_cost

17 个逻辑算子变成 51 个物理 stage；51 个 scratch allocation 共约 1.06 GB physical
capacity，stage0 约 1.77 GB logical scratch traffic，增加两次 dequant write/read round
trip、barrier 和低 GA 利用率。

### unresolved_production_blocker

共享 exact UINT8 tail 仍为 `NO_UNCONDITIONAL_PURE_CONFIG_PROVEN`；native final JSON、
static-to-address-bound leaf diff、mapping/bitstream、execplan/SCA、最终 Y 与服务器 E4/E5
均未生成或闭合。

### claim_boundary

不对完整 QLinearAdd 声称 `CONFIG_ONLY_CORRECTNESS_BASELINE`。当前只是一份结束于
`SUM_F32` 的 stage0 configuration-bound correctness candidate；Y 的 UINT8 rounding、
zero-point addition、saturation 和物化链全部在范围外。

## Validation

```text
python tools/build_qlinearadd_stage0_config_only.py
valid=true

python tools/validate_qlinearadd_stage0_config_only.py \
  configs/qlinearadd_stage0_config_only/qlinearadd_stage0_config_only_v1.json \
  --contract contracts/operator_config/qlinearadd_stage0_config_only_contract_v1.json
valid=true

python -m unittest \
  tests.test_qlinearadd_stage0_config_only \
  tests.test_qlinearadd_predesign -v
13/13 passed
```

Config-bound coverage:

```text
instances=17
physical_stages=51
scratch_allocations=51
branch_scalar_values_checked=8704
fp32_sum_scalar_pairs_checked=1114112
node0076_replay_elements_checked=16000
native negative controls=node0007(2), node0070(1)
```

## RULE_DELTA_PROPOSAL

建议 QLinearAdd 专项规则后续补充：

1. correctness-first QLinearAdd 前半段在 stock topology 下是三个 physical stage，而不是把
   两支 Dequant 和 add 误称为一个静态 stage；
2. broadcast B 可只物化原始长度 scratch，再由 add stage 地址重放；tail valid bytes 与
   physical padding 必须分开计账；
3. complete baseline claim 必须等待共享 UINT8 tail 与 native final materialization chain；
   stage0 config-bound pass 只能声明其精确子范围。

本任务没有修改 `.agents/rules/**`。

## BLOCKER_DELTA

部分闭合（只限 stage0 子范围）：

- 17-instance W3 A/B dequant + FP32 sum DAG；
- paired readiness/shared-LC backpressure 方程；
- node0076 1000-element replay 和 B-dequant tail；
- scratch concrete address/non-overlap/barrier/lifetime；
- project-stage config-bound simulator 与 native reassociation negative control。

继续保持：

- `B_QADD_QUANT_TAIL_P0A_UNRESOLVED`
- `B_ADD_UINT8_REQUANT`
- `B_QADD_NATIVE_TYPED_HANDLER`
- `B_EXECPLAN_TYPED_TRANSPORT`
- `B_ADD_REQUANT_E5`
- `B_SERVER_E4_E5`
- native static/address-bound non-base leaf ownership and final byte coverage gate

没有关闭完整 QLinearAdd blocker。

## PACKAGE_RELEASE

```json
{
  "status": "NOT_GENERATED_NO_LEASE_AND_COMPLETE_QADD_UNCLOSED",
  "server_inspected": false,
  "uploaded": false,
  "run": false
}
```

本轮未修改 plan、公共/专项规则或 RTL；未检查任何服务器文件、名称或身份；未生成服务器包。
