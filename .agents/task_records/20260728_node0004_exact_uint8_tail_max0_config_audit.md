# node0004 exact UINT8 tail：raw signed max0 配置绕行审计

- 日期：2026-07-28
- 唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`
- ownership：QuantizeLinear/shared exact UINT8 tail
- 结论：`FAIL_CLOSED_RAW_SIGNED_MAX0_NOT_MATERIALIZABLE`
- `PACKAGE_RELEASE=NONE`
- `candidate_release=false`

## 控制面与规则收据

以下文件均已完整复读。plan 只作生成时 mutable provenance，不进入
current-match 语义门；其余规则、授权和硬源进入 fail-closed current-match 门。

- `.agents/plan.md`
  - 生成时 SHA256 `84fab28973b128a409d498898b1750f9cc025224c6694ce3f028ab0a592c9b2d`
  - receipt-only integration refresh SHA256
    `971f3c7d479e6ad80cf39450d0f56bc3bad5a898daca152f2c859593cf27b017`
  - 只作 mutable provenance；变化不触发数值重算。
- `.agents/rules/生成前必读索引.md`
  - SHA256 `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/算子配置规则.md`
  - SHA256 `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/NDP硬件字段语义.md`
  - SHA256 `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59`
- `.agents/rules/精确UINT8量化尾专项规则.md`
  - 生成时 SHA256
    `5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0`
  - 当前 SHA256
    `32c47b83e98d9dd9cbf1f8be7f25dd99d86ddecb583d5972b61b1e72d3b931be`
  - 已发布并绑定 `CDA-QUANT-TAIL-RAW-SIGNED-GUARD-001`。
- `.agents/rules/RequantizeUint8算子配置规则.md`
  - SHA256 `d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f`
- `.agents/rules/INT8_SA点积专项规则.md`
  - 生成时 SHA256
    `61489399f905fb5b8b0fb240f3451a8f0c40e04fc5781537d893fdfcb9bd250d`
  - 当前 SHA256
    `af4eb4c3795c8a8dfaba7dca47839906eb02dbb46bb17ec040f893638005502b`
- `.agents/task_records/20260728_conv_c0_mainline_adjudication_and_composite_c1_authorization.md`
  - SHA256 `6415f8adfdd163a6c360a46e9392371c386b900b85722b9eee8a8d3760a89e2a`
  - `PATH_FRESH_COMPOSITE_CONFIG_C1=AUTHORIZED` 只授权 fresh composite
    C1；本腿未组装 accumulate/full Conv。
- `.agents/task_records/20260728_conv_node0004_composite_c1_mainline_adjudication.md`
  - SHA256 `1f343efe8383b65ffb836427ba4994dcd78f7e0869b98882a831920ff34e9760`
  - 当前裁决为 `C1_TARGET_MATERIALIZATION=BLOCKED_BEFORE_JSON`、
    `PACKAGE_RELEASE=NONE`。

合同还 current-match 绑定 typed lowering、正式 ONNX/W3、授权原生
`quant_from_buffer_int32MN_uint8MN`、execplan/mapper/encoder 以及本次直接审计的
活动 GA RTL。旧 node0004 config/candidate/report/test/server return 均未读取。

## receipt-only integration refresh

主线发布 raw signed guard 规则并完成 C1 裁决后，本资产只执行收据刷新：

```text
numeric_analysis_repeated = false
mathematical_conclusion_changed = false
hardware_conclusion_changed = false
target_or_package_generation_performed = false
```

刷新器只更新 plan mutable receipt、活动规则/裁决/硬源 SHA 和报告；validator 不调用
`_analysis`、不加载 W3 ndarray、不重新执行 3,211,264 元素 replay。原有 W3 计数、
qparam identity、max0 数学等价和 opcode/RTL 无交集结论作为冻结字段逐项校验。

## 实例与 qparam

- request：`r5:hwop-0004-01`
- hwop：`hwop-0004-01`
- logical dtype/shape/layout：
  - ingress `INT32 [16,64,56,56] NCHW`
  - egress `UINT8 [16,64,56,56] NCHW`
  - 3,211,264 elements
- `x_scale=0.021563487127423286`
- `y_scale=0.007307368330657482`
- `y_zero_point=0`
- per-channel multiplier：
  - axis 0，64 个 float32
  - strictly positive and finite
  - SHA256 `e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2`

## max0 数学等价

所审计改写为：

`acc_raw -> max(acc_raw,0) -> INT32-to-FP32 -> sequential FP32 MUL -> RNE -> UINT8 saturation`

在全部 signed INT32 输入、全部 multiplier 为有限正数且 `y_zp=0` 时：

1. `acc>=0`：`max(acc,0)=acc`，后续中间量完全相同。
2. `acc<0`：正 multiplier 使 scaled 值非正；nearest-even 结果非正，UINT8
   saturation 输出 0，与 max0 分支相同。

因此最终 UINT8 数学结果等价。但这只证明改写公式，不证明硬件存在 raw signed
max0。

正式 W3 全张量重算：

- accumulator 范围 `[-1148879,57876]`
- 负值数 `1262480`
- max0 后范围 `[0,57876]`
- 原公式 vs max0 最终 UINT8：0 mismatch
- max0 vs 正式 golden：0 mismatch
- max0 后 W3 最大值小于 `2^24`，条件进入 FP32 时其整数值可精确表示。
- max0 张量只用于 validator 内验证；未写成硬件输入、配置 replay 或内部 tensor
  supply。

## 活动 opcode/RTL 判别

直接绑定并读取活动 encoder 与 RTL：

- `ndp-sim/bitstream/config/general.py`
- `NDP_copy01/rtl/includes/NDP_Parameters.svh`
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv`
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/GA_ALU.v`
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/GA_PE_Float_Control.v`
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/GA_PE_Float_Last.v`
- `NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport.sv`

编码事实：

- symbolic `max=3`，属于 FP32 类；
- `int8_max=11`，是四个独立 8-bit lane 路径，不保持 signed INT32 word；
- INT32 只有 `int32_sum=12`、`int32_sub=13`、`int32_mac=14`；
- encoder 与 RTL 均无 `int32_max`。

五位译码不可满足性：

- INT32 class 要求 `opcode[4:2]==3'b011`；
- max 要求 `opcode[2:0]==3'b011`；
- 两者在 bit2 上矛盾，0..31 的交集为空。

因此 `FP32 max` 必须先把 raw accumulator 变成 FP32，无法绕过已知 signed
converter 缺陷；`int8_max` 也不能充当 signed INT32 word guard。仅用
sum/sub/mac 没有 compare/select/shift/bitwise 证据，不能声称实现 max0。

最小反例为 `acc=-1`：所需 raw max0 输出为 0，但不存在可编码的
signed-INT32 max opcode；最终 saturation 恰好也输出 0 不能替代该中间硬件证据。

## 首断点与后续依赖

首个不可绕能力：

`B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE=OPEN_CONTRADICTED`

后续均未被此审计放行：

- nonnegative INT32-to-FP32：
  - 活动转换原语和 RNE 逻辑存在；
  - 只有在 raw max0 已真实物化后才可达；
  - 不能由本审计扩张成 full legal-domain transport claim。
- sequential MUL -> separate RNE -> saturation：
  - fused FMA 禁止冒充；
  - 仍需 materialized stage boundary 和 26-vs-25 判别；
  - 当前未生成配置。
- per-channel constant transport：
  - typed qparam 身份闭合；
  - native handler 无 qparam 字段/更新；
  - manual materializer 未在不可达路径上伪造。
- mapper/execplan：
  - exact-tail registration 与 typed transport 仍未闭合。
- composite endpoint：
  - `same_storage/base/offset/read_coverage/accepted_lifetime/terminal`
    六项均保持 `null`，等待 fresh composite INT32 endpoint；
  - 不使用 provisional 地址。

## BYPASS_ANNOTATION

- `bypass_reason`：在转换前 raw clamp，以绕开 signed INT32-to-FP32 缺陷。
- `contradicted_or_missing_native_path`：raw signed INT32
  `max(acc,0)` compare/select。
- `exact_equivalence_scope`：node0004 的 finite positive per-channel
  multipliers、`y_zp=0` 下全 signed INT32；正式 W3 全张量亦 0 mismatch。
- `materialized_configuration_mechanism=null`。
- `performance_and_resource_cost`：若未来有真实 signed-word compare/select，
  至少增加一个串行 guard stage。
- `unresolved_production_blocker`：raw max0、顺序舍入、per-channel transport、
  mapper/execplan、composite endpoint。
- `claim_boundary`：不是 `CONFIG_ONLY_CORRECTNESS_BASELINE`；无 target
  JSON、无 tail config、无 full Conv、无包、无 release。

## 资产与验证

- family generator/validator：
  - `resnet50_pipeline/node0004_exact_uint8_tail_max0_audit.py`
  - SHA256 `4d4bca59de2efe73596ca3082edd2df2b865c9919d119c93c980632db4f87001`
- build CLI：
  - `tools/build_node0004_exact_uint8_tail_max0_audit.py`
  - SHA256 `90360508fb01341fc55b3ae72134a320f9c4e1d6caeb9658f129dc0cec0b7dce`
- validate CLI：
  - `tools/validate_node0004_exact_uint8_tail_max0_audit.py`
  - SHA256 `3cf7217529383f54b656f60810d9cc0e165af65fbcccbd7be95c5fe447c39f42`
- receipt-only refresh CLI：
  - `tools/refresh_node0004_exact_uint8_tail_max0_receipts.py`
  - SHA256 `65f5889c9fb49a001421bc6c0a5ffac4435ff31ee0d8e42229e72d6b1263b6f7`
- test：
  - `tests/test_node0004_exact_uint8_tail_max0_audit.py`
  - SHA256 `b8f4ca8c12bb3d2caed83f6fb49baf76f9fd2ba5510ec49b7f90ef9359407752`
- contract：
  - `contracts/operator_config/node0004_exact_uint8_tail_max0_audit_v1.json`
  - SHA256 `adf0a0d9f1a599d8b37bf15f131fe182092ebc4c3e070da0f89bc65156b87f16`
- report：
  - `artifacts/operator_config_validation/node0004-exact-uint8-tail-max0-audit-v1/report.json`
  - SHA256 `c2216810d3bf0085611a34bedcaa9c4b94b5f15fece8934e978ed17993059d2c`

验证命令：

`.\.venv\Scripts\python.exe -m unittest tests.test_node0004_exact_uint8_tail_max0_audit`

结果：5/5 PASS。

`.\.venv\Scripts\python.exe tools/validate_node0004_exact_uint8_tail_max0_audit.py`

结果：`PASS_FAIL_CLOSED_RAW_SIGNED_MAX0_NOT_MATERIALIZABLE`。

receipt-only 刷新命令：

`.\.venv\Scripts\python.exe tools/refresh_node0004_exact_uint8_tail_max0_receipts.py`

结果：`numeric_analysis_repeated=False`。

## RULE_DELTA_INTEGRATION

原提案 `CDA-QUANT-TAIL-RAW-SIGNED-GUARD-001` 已由主线发布，当前合同已把它升级为
current-match 活动规则依赖；无新增规则提案，原数学与硬件结论不变。
