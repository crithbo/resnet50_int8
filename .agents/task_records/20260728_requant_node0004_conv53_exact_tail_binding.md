# RequantizeUint8 node0004 / Conv53 exact-tail binding 记录

日期：2026-07-28  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 任务与边界

本轮仅生成供 shared exact UINT8 tail 会话批量消费的机器可读 binding manifest。
未重做 54-stage 数值分析，未复测模板，未生成 operator target JSON、mapping、
bitstream、execplan、SCA 或服务器包；未检查、上传或运行服务器；未修改 plan、
rules 或 RTL。

用户覆盖要求 node0004 的全部旧本地资料与测试均不可信。node0004 行因此只消费：

- typed lowering/request；
- typed request 中由正式 model initializer 绑定的 qparam；
- 正式 W3 runtime/subop manifest 中的 initializer、accumulator、output tensor 身份；
- 当前活动语义规则。

node0004 旧 candidate/config、mapping/bitstream/execplan/SCA、simulator/comparison、
local E2/test receipt 与旧 54-stage evidence 的 node0004 行均未消费。覆盖记录：
`.agents/task_records/20260728_node0004_untrusted_fresh_rebuild_mainline_override.md`,
SHA256=`6626f3192390fe3b93483746f1dbd6a61cc13f21cd5b55559738cd3dfbad7c06`。

## 活动收据

- mutable plan provenance：
  `e823f9d6cba28fff4659d0e2ba3ab3e0651be989feb0fd560a628095133d3fc9`
- 生成前必读索引：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- 公共算子配置规则：
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- 精确 UINT8 量化尾专项规则：
  `5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0`
- RequantizeUint8 专项规则：
  `d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f`
- typed lowering bundle：
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
- 非 node0004 行复用的 54-stage evidence：
  `64aec997e9188ed69a0f0062dd9f66c5377d772fdc8b598dd1b8aa038a036f07`
- Requant family boundary：
  `c92c14cdcd3b68f2f8c0aff7339602d7ab3784d9b454559ade2317eb5fb0c8c0`
- shared exact-tail capability：
  `dedd0e467a31ecb42cd3e76faddb55901286b97fb2311fc4052d0a157dbd8c6e`
- formal W3 model graph：
  `f030c5d4e43f63fbbcce771e4c4ea9e88b042be0a2c988e7f51de2c0e17ac410`
- formal W3 runtime manifest：
  `f7e90cf1f087acf255e93d98d1788e0fb0b4c77bbe935ea9addb17feea583180`
- formal W3 subop manifest：
  `8bfdd042570408c1df793044407a8e6262bfa261b3cc6f02f64b94ad47d9c1c2`

plan 仅作 mutable provenance；硬语义由上述活动规则 fail-closed。

## NODE0004_BINDING

- request：`r5:hwop-0004-01`
- request SHA256：
  `ed833d0512b0256756f3d7e39cfd79aac04a901d0095f11f103e7216e6dccb5b`
- node / ONNX：
  `node-0004 / fused resnetv17_stage1_conv0_fwd_quant / QLinearConv`
- stage：`RequantizeUint8 / requantize`
- logical input/output：
  `INT32[16,64,56,56] -> UINT8[16,64,56,56]`
- logical layout：`NCHW_TYPED_QLinearConv_LOGICAL`
- physical layout：
  `UNBOUND_TRUSTED_SOURCE_ONLY_REQUIRES_FRESH_MATERIALIZATION`
- producer：`r5:hwop-0004-00`, request SHA256
  `e27e10169168f3889df4c03bf15cb21de074abf3f3767dc4bee288425165874b`
- accumulator tensor：
  `tensor-internal-node-0004-accumulate`, SHA256
  `32de6ea94086ce09da37b4f3c5b12ee51275c7b0f6d7b4a9875b0b9900ca25ac`
- output tensor：
  `tensor-78b29737ada5ce7a`, SHA256
  `b4a4fa9ca2f1384ede29a1c29ba15e21626ccb3f0d3387160942bc58d65f0899`
- direct consumer：`r5:hwop-0005-00`, role=`x`, request SHA256
  `e8cf1fe2006937c15d639867ea67f5eecf0c48189a4b90d78cec495bdf58c11d`
- `x_scale`：FP32 scalar `0x3cb0a5e9`,
  value SHA256=`a1aac7487d3e8f919770415333ea8456ee152f1a343819888671a4395e2e7d02`
- `w_scale`：FP32 per-channel `[64]`,
  value SHA256=`3abf120f4bc983427b0f9699d55fcfbc648a8884501832dbe874b3828968e9b9`
- `y_scale`：FP32 scalar `0x3bef72a6`,
  value SHA256=`9879e417a260e24ba16504cc33214bae92cfc35e5d12f85ba808d40c93a725e0`
- `y_zero_point`：UINT8 scalar `0`,
  value SHA256=`6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d`
- requant multiplier：FP32 per-channel `[64]`,
  formula=`float32(x_scale * w_scale / y_scale)`,
  value SHA256=`e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2`
- typed qparam group：`CONV53_ZP0_SHARED_TAIL_PENDING`
- old numeric classification：
  `NOT_IMPORTED_REQUIRES_FRESH_SHARED_TAIL_BINDING`
- row marker：`trusted_source_only=true`

node0004 仍受 FMA rounding、magic finite-domain、typed transport、layout 与 fresh
shape/lifetime materialization 门约束；本 binding 不构成 E2/E4/E5。

## CONV53_CLASS_COUNTS

按 53 个 typed lowering/request 的 `y_zero_point` 分组：

- `CONV53_ZP0_SHARED_TAIL_PENDING`：33
- `CONV53_EVEN_NONZERO_SIGNED_INGRESS_BLOCKED`：15
- `CONV53_ODD_NONZERO_SIGNED_AND_TIE_PARITY_BLOCKED`：5

仅对其余 52 项复用既有全族数值分类：

- `FULL_LOCAL_E2_MATERIALIZED_EXACT_NODE0001`：1
- `NUMERIC_RECIPE_COMPATIBLE_PHYSICAL_E2_PENDING`：31
- `CURRENT_GUARD_RECIPE_CONTRADICTED_NONZERO_EVEN_ZP`：15
- `CURRENT_GUARD_RECIPE_CONTRADICTED_NONZERO_ODD_ZP`：5

node0004 不计入上述 52 项旧数值分类。

shape counts：

- `[16,64,112,112]`：1
- `[16,64,56,56]`：6
- `[16,128,28,28]`：8
- `[16,256,56,56]`：4
- `[16,256,14,14]`：12
- `[16,512,28,28]`：5
- `[16,512,7,7]`：6
- `[16,1024,14,14]`：7
- `[16,2048,7,7]`：4

全部 53 项 channel tail mod 8 为 0。

## 边界

- MatMul：`r5:hwop-0075-01`, shape=`[16,1000]`, `y_zero_point=60`；
  不属于 Conv53，保留 rank-2 layout 与 signed INT32 ingress 独立 blocker。
- GAP/AverageRequant：不在 54-stage Requant 列表中；49-term sum producer、
  composite lifetime 与 shape-49 transaction 仍由 GAP 路径负责。
- QuantizeLinear：FP32 exact division 路径，不等同于 Conv Requant 的 INT32
  per-channel multiplier 路径。

## 产物与校验

- machine manifest：
  `contracts/operator_config/requant_conv53_exact_tail_binding_v1.json`
  - semantic manifest SHA256：
    `5981e1becd8c8d7d4c3ea10eadf630ad19d13ab08f4955577d056afdf3d47064`
  - file SHA256：
    `075df2abdab13f7c94679b411a9822213f3975bc7341c7415a2c3577d5cdf113`
- validation report：
  `artifacts/operator_config_validation/r5-requant-conv53-exact-tail-binding-v1/validation_report.json`
  - file SHA256：
    `93c969a7e57d1e3abffa396f96360d3ddd29f2e759a6eb4691a36dd619785769`
- generation receipt：
  `artifacts/operator_config_validation/r5-requant-conv53-exact-tail-binding-v1/generation_receipt.json`
  - file SHA256：
    `14d7f06fbba198ab7366d9c7c4423f9b82e17ec3725d0c6fac732d48f29145cc`

校验仅覆盖 schema/数量/分组/typed request/qparam/tensor/producer-consumer 与
formal W3/model 身份链；没有执行数值 replay 或模板测试。

## 结构化裁决

`RETURN_ANALYSIS=CONV53_BINDING_READY_NODE0004_TRUSTED_SOURCE_ONLY_OTHER52_REUSED`

`BLOCKER_DELTA.add=[]`

`BLOCKER_DELTA.close=[]`

`BLOCKER_DELTA.defer=all existing numeric/layout/transport/mapper/lifetime/dynamic blockers`

`RULE_DELTA_PROPOSAL=[]`

`PACKAGE_RELEASE=NONE`

