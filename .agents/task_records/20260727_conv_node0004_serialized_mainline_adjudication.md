# Conv node0004 serialized local E2 主线裁决

日期：2026-07-27

## 裁决

主线接受 `r5:hwop-0004-00 / node0004 ConvInt32Accumulate` 为
`CONFIG_ONLY_CORRECTNESS_BASELINE`，证据等级为本地 `E2`。该结论只覆盖冻结
node0004 的 INT32 accumulate stage，不把完整 `QLinearConv`、其 UINT8 requant
output、其他 52 个 Conv、QLinearMatMul、production、性能或服务器动态门计为通过。

因此更新全网计数：

- 精确物化 hwop JSON：增加 1；
- `CONFIG_ONLY_CORRECTNESS_BASELINE`：增加 1；
- 完整 ONNX 节点本地 config-only E2：不增加；
- 正式 target、E4、E5、正式三方节点：均不增加。

## 接受证据

- family task record：
  `.agents/task_records/20260727_conv_node0004_serialized_one_product_local_e2.md`
  @ `a746d20e1c7b7cea2eb3d4bc88c0a2bb085d4e8d4f89e58778ddee0e7a7cb589`；
- machine contract：
  `contracts/operator_config/r5_conv_node0004_serialized_one_product_local_e2_v1.json`
  @ `3bfa060ef8598c932d7e456eec4d016ed3f8ff04f2cb9b7744eb8668884f4627`；
- validation report：
  `artifacts/operator_config_validation/r5_conv_node0004_serialized_one_product_local_e2_v1/validation_report.json`
  @ `9a1ea01f9afcccbb86a69deeeab98850559aa9009165b9a344a2956c941460be`；
- 三个 wave 的 mapping 均为 `penalty=0`、`fallback_used=false`；
- 最终 JSON→bitstream→execplan/SCA/SCA_D→完整 request address→config-bound
  physical output→logical inverse→冻结 W3 accumulator 已闭合，physical 与 logical
  mismatch 均为 0；
- 每 occurrence 至多一个可能非零 `s8×u8` product lane；64 个 D region 各精确覆盖
  200,704 bytes，总 typed D 为 12,845,056 bytes；
- stock four-lane negative control 保持失败：
  weight `[2,-126,-21,-26]`、activation `[17,27,9,28]`，
  stock=`-32483`、W3 target=`1225`。

## 绕行与边界

- 原因：stock four-lane INT8 SA 同时有 carry 重复左移和 signed17 reduction
  位宽不足；
- 机制：把原 dot4 展开成四个 occurrence，每次只保留一个可能非零 product lane；
- 等价范围：仅冻结 node0004 accumulate、`x_zp=0`、W3 bias/psum32 modulo 累加；
- 代价：205,520,896 serialized occurrences，A/B payload 和 compute occurrence
  约 4 倍，product-lane 利用率上界 25%；
- production blocker：stock four-lane 算术能力、性能、其他实例物化与服务器动态门
  均保持开放。

## 规则与 blocker

主线已把 `.agents/rules/INT8_SA点积专项规则.md` 更新为
`f5607f396abd5c706ca60568c0b967e746b5ff8f40efe6c33a95a50f705a7622`。

- close（仅冻结 node0004 identity）：
  `B_SA_SERIALIZED_FALLBACK_MATERIALIZATION`；
- keep：
  `B_CONV_INT8_SA`、`B_MATMUL_INT8_SA`、
  `B_CONV_CONFIG_BOUND_SIMULATOR_RTL_CSA_MISMATCH`、
  `B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY`、
  `B_SA_INT8_DUPLICATE_CARRY_SHIFT`、`B_SA_INT8_REDUCTION_WIDTH`、
  `B_SA_COMPATIBLE_RTL_IDENTITY_PENDING`；
- add：
  `B_CONV_SERIALIZED_BASELINE_PERFORMANCE`、
  `B_CONV_SERVER_DYNAMIC_RELEASE`。

`PACKAGE_RELEASE=NONE`。未检查服务器文件、名称或 identity，未上传、未运行，
未修改功能 RTL。
