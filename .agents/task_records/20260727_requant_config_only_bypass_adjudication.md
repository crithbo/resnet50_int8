# RequantizeUint8 / AverageRequantizeUint8 纯配置绕行裁决

日期：2026-07-27  
主线回传目标：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 1. 任务边界

本轮只消费已验收的 54-stage Requant quant-tail 证据，按 33 个 zp0、16 个 even
nonzero-zp、5 个 odd nonzero-zp 裁决纯配置正确性绕行。没有修改
`.agents/plan.md`、`.agents/rules/**`、`rtl/**` 或其他算子族资产；没有检查、上传或运行
服务器，没有生成 operator JSON、mapping、bitstream、execplan/SCA 或服务器包。冻结
event-edge v1 ZIP 保持 78,068 bytes、SHA256
`31877dcf0f11a52a0822525e8f49312d25807f81884377f748425693c89b4a53`。

本轮产物只能称 `FIRST_BREAK_ADJUDICATION_ONLY`。三组
`CONFIG_ONLY_CORRECTNESS_BASELINE` 数量为 0，E2/E4/E5 数量均为 0。

## 2. 活动读取收据

| 路径 | SHA256 | 用途 |
|---|---|---|
| `.agents/agent.md` | `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0` | agent 边界 |
| `.agents/plan.md` | `a1e19c6e84360641205836f6fa0b172fc0405472b8b2dfdc4c580cc2e0875516` | mutable provenance；不作硬语义门 |
| `.agents/rules/生成前必读索引.md` | `3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19` | 路由；新增 Flatten/View 路由不改变本族语义 |
| `.agents/rules/算子配置规则.md` | `407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc` | config-only、禁止计算性 replay 与最终非 base 字段所有权门 |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0` | shared exact tail |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f` | Requant 专项 |
| `.agents/rules/NDP硬件字段语义.md` | `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59` | LC/MSE/Buffer/GA 跨单元语义 |
| `.agents/rules/最小双Stage生命周期规则.md` | `821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171` | scratch/barrier/lifetime |

活动证据输入：

- `contracts/operator_config/requant_quant_tail_evidence_input_v1.json`：
  SHA256 `64aec997e9188ed69a0f0062dd9f66c5377d772fdc8b598dd1b8aa038a036f07`；
- `contracts/operator_config/exact_uint8_quant_tail_capability_v1.json`：
  SHA256 `dedd0e467a31ecb42cd3e76faddb55901286b97fb2311fc4052d0a157dbd8c6e`；
- `contracts/operator_config/exact_uint8_quant_tail_rounding_discriminator_v1.json`：
  SHA256 `82ab3276a8ae9ee35aeda366756dd4525dfac77c6e3ed40cf395d7a011f8a477`；
- `.agents/task_records/20260727_exact_uint8_quant_tail_rounding_mainline_adjudication.md`：
  SHA256 `4704a059b4776e6b671ee949ff3ef7d0c11c3476cb1d523bce365a2c5896d63f`。

## 3. 三组 BYPASS_ANNOTATION

### 3.1 zp0（33 项；代表 `r5:hwop-0001-01`）

- `bypass_reason`：原两 PE `MAC→INT32_SUB` 把应独立存在的 FP32 multiply 舍入点与
  magic add 收缩成一次 FMA。
- `contradicted_or_missing_native_path`：`400 × bits(0x3d828f5c)` 的顺序结果 26、融合
  结果 25；共享 Quant 线已经用 two-stage scratch singleton 区分二者，但完整域
  ordered-rounding、typed transport、mapper 与 terminal 仍未闭合。
- `exact_equivalence_scope`：仅 33 项冻结 W3 数值证据；node0001 旧 fused local E2 不
  外推。
- `materialized_configuration_mechanism`：候选是 guard 后独立 FP32 MUL、固定 magic
  ADD、raw INT32_SUB 和 UINT8 saturation；共享线只对 32 个相同正数 lane 物化
  singleton diagnostic，本族因完整域首断点仍开而未生成 JSON。
- `performance_and_resource_cost`：预计只用 4/8 output lane，增加 PE 深度、FP32 scratch
  读写、traffic 与 barrier。
- `unresolved_production_blocker`：`B_QUANT_TAIL_THREE_PE_TOPOLOGY`、
  `B_QUANT_TAIL_TYPED_BINDING`、`B_QUANT_TAIL_MAPPER_REGISTRATION`、
  `B_QUANT_TAIL_MAGIC_DOMAIN_BOUND`、`B_REQUANT_SERVER_E4_E5`。
- `claim_boundary`：`FIRST_BREAK_ADJUDICATION_ONLY`；不是 baseline、target config、
  E4 或 E5。

首个不可绕能力断点：`B_QUANT_TAIL_THREE_PE_TOPOLOGY`。

### 3.1.1 shared singleton 依赖刷新

Quant 线新增诊断固定为 32 个相同正数 lane：

- `int32=400`、`multiplier_bits=0x3d828f5c`、`zp=0`；
- stage0 scratch bits=`0x41cc0000`；
- two-stage sequential=26，fused negative control=25；
- claim=`LOCAL_CONFIG_BOUND_DIAGNOSTIC_NOT_BASELINE`。

它把“显式 scratch 可分离 multiply 的 binary32 舍入点”从 proposal 提升为 singleton
config-bound diagnostic，但没有完整 33 个 zp0/AverageRequant 冻结域、native typed
transport、mapping/bitstream、execplan/SCA、lifetime/terminal 或完整域 config-bound
simulator。因此本族 33/16/5 分类、baseline=0、首断点顺序与全部 blocker 均不改变。

### 3.2 even nonzero-zp（16 项；代表 `r5:hwop-0003-01,zp=150`）

- `bypass_reason`：非零 zp 的近零负 accumulator 可能输出正 UINT8；zp0 的
  `max(acc,0)` guard 不等价。
- `contradicted_or_missing_native_path`：stock `int32tofp32` 对 `-1` 产生
  `0xcf000000` 而非 `0xbf800000`，负幅值已经丢失；没有从原 typed INT32 输入恢复全部
  负幅值的纯配置路由。
- `exact_equivalence_scope`：16 项冻结 W3、原始 typed INT32 和 qparam；明确排除主机
  预计算 scaled/final tensor。
- `materialized_configuration_mechanism`：无合法物化；重放原输入/常量不能修复 signed
  ingress，主机预计算内部结果会替代算子计算。
- `performance_and_resource_cost`：未物化；未来若有 signed ingress，仍需 zp0 路径的
  scratch、traffic、barrier 与低 lane 利用率。
- `unresolved_production_blocker`：`B_QUANT_TAIL_SIGNED_INT32_INGRESS`、
  `B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN` 及 shared topology/binding/mapper/dynamic 门。
- `claim_boundary`：`SIGNED_INGRESS_FIRST_BREAK_ONLY`；不是 baseline、target config、
  E4 或 E5。

首个不可绕能力断点：`B_QUANT_TAIL_SIGNED_INT32_INGRESS`。

### 3.3 odd nonzero-zp（5 项；代表 `r5:hwop-0014-01,zp=123`）

- `bypass_reason`：同时需要 signed magnitude 与 RNE 后再加 odd zp。
- `contradicted_or_missing_native_path`：signed ingress 反例先发生；把 odd zp 放入
  magic bias 又会翻转 half-tie parity，node0014 正式 W3 有 32 个反例。
- `exact_equivalence_scope`：5 项冻结 W3、原始 typed INT32 和 qparam；排除主机预计算
  scaled/final tensor。
- `materialized_configuration_mechanism`：无合法物化；若未来先关闭 signed ingress，
  固定 magic 加 `raw INT32_SUB(0x4b400000-zp)` 仍只是待闭合 proposal。
- `performance_and_resource_cost`：未物化；未来路径仍需显式 multiply 舍入、post-RNE zp、
  scratch、traffic 与 barrier。
- `unresolved_production_blocker`：signed ingress/nonzero-domain 为首门，
  `B_REQUANT_MAGIC_ZP_TIE_PARITY` 为次级门，另保留 shared topology/binding/mapper/
  dynamic 门。
- `claim_boundary`：`SIGNED_INGRESS_FIRST_BREAK_WITH_TIE_PARITY_SECONDARY`；不是
  baseline、target config、E4 或 E5。

首个不可绕能力断点：`B_QUANT_TAIL_SIGNED_INT32_INGRESS`；tie parity 是未到达的次级门。

## 4. AverageRequant

AverageRequant 的 49-term sum 是 nonnegative、zp0 数值兼容，因此 signed ingress 不是
首门；首个能力断点同 zp0，为 `B_QUANT_TAIL_THREE_PE_TOPOLOGY`。此外仍需
sum→tail typed transport、shape-49 transaction、producer/consumer lifetime 和最终地址
绑定。本轮未生成 AverageRequant JSON。

## 5. 新公共物化字段门集成

合同已绑定
`CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001`。每组 gate 均包含：

- 静态/逻辑配置→最终 address-bound JSON 的逐 leaf diff；
- 每个非 base 变化必须具备 owner、input source、formula、old value、expected new
  value、authorization reason；
- 从最终 occurrence/address 方程重算正式输出 covered-byte set。

由于三组均在新 operator JSON 前停止，这些门严格记录为
`NOT_REACHED_NO_MATERIALIZED_JSON` 和
`NOT_REACHED_NO_FINAL_OCCURRENCE_OR_ADDRESS_EQUATIONS`，而不是 pass。

## 6. 机器资产与验证

- 合同：
  `contracts/operator_config/requant_config_only_bypass_adjudication_v1.json`
  - file SHA256:
    `17f9e1f14e401a9542b1f78d62ce2aebd2e1029357931aaec825e70e100fd05b`
  - semantic/adjudication SHA256:
    `0a63dfbad1a000543dd50289d49d5fc5648a3a2c2dab4b1c1d987d8be3e99851`
- validation report：
  `artifacts/operator_config_validation/r5-requant-config-only-bypass-adjudication-v1/validation_report.json`
  - SHA256:
    `ef9d0719627959dce7a5451d4c8fa1e2d778b359c8a394366be961d3aa3775b8`
- generation receipt：
  `artifacts/operator_config_validation/r5-requant-config-only-bypass-adjudication-v1/generation_receipt.json`
  - SHA256:
    `31e1d9b132bc5a40678f5d7edef026ccb9f4d76a146305ec052c9aec5e6fe1ae`
- 定向测试：`tests.test_requant_config_only_bypass`，8/8 通过。

## 7. RETURN_ANALYSIS / BLOCKER_DELTA / RULE_DELTA_PROPOSAL / PACKAGE_RELEASE

`RETURN_ANALYSIS`：

- 54/54 W3 exact 与 33/16/5 分类未改变；
- 三组均没有形成 baseline；
- zp0/AverageRequant 首断点是 three-PE ordered rounding topology；
- even/odd nonzero-zp 首断点是 signed INT32 ingress；odd tie parity 为次级门；
- 旧 node0001 local E2 与 event-edge 动态历史均未外推。

`BLOCKER_DELTA`：

- add：无；
- close：无；
- keep：shared FMA/domain/signed-ingress/three-PE/typed-binding/mapper，以及 Requant
  nonzero-domain/tie-parity/shape-lifetime/server E4/E5。

`RULE_DELTA_PROPOSAL`：

- 原提案 `CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001` 已被主线写入公共规则
  SHA `407fc032...c2cc`；本轮 `additional_rule_change_requested=false`。
- host 预计算 scaled/rounded/saturated/final tensor 继续被禁止。

`PACKAGE_RELEASE`：

- `release=false`；
- package=`null`；
- 原因：没有组完成最终物化 E2，且本轮禁止服务器包生成/动作。
