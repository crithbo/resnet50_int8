# Conv node0004 单乘积序列化本地 E2

日期：2026-07-27  
test_id：`r5_conv_node0004_serialized_one_product_local_e2_v1`  
状态：`CONFIG_ONLY_CORRECTNESS_BASELINE`  
candidate_release：`false`  
PACKAGE_RELEASE：`NONE`

## RETURN_ANALYSIS

本轮只闭合冻结的 ResNet50 `node0004 / ConvInt32Accumulate`。最终物理配置把每个原始
四 lane dot4 展开为四个 occurrence；每个 occurrence 最多保留一条可能非零的
`s8(weight) * u8(activation)` lane，其余三 lane 明确置零。这样 stock RTL 第一级
CSA carry 恒为零，单乘积与既有 psum32 路径按模 `2^32` 累加。

最终链路已完成：

```text
typed request
  -> serialized generator
  -> final operator JSON (3 waves)
  -> native mapper / bitstream
  -> execplan / SCA / SCA_D
  -> fully enumerated request addresses
  -> config-bound physical simulator
  -> logical NCHW INT32 inverse
  -> frozen W3 node0004 accumulator
```

关键验收结果：

- 三个 mapping 均为 `penalty=0`、`fallback_used=false`；
- execplan 双运行确定性相等，request/address validator 为 `valid=true`；
- 每个 occurrence 最大可能非零 product lane 数为 `1`，其余 lane 非零计数为 `0`；
- config-bound simulator 的 physical mismatch 和 logical W3 mismatch 均为 `0`；
- logical output payload SHA-256：
  `1ec864892d82279beff561927500f55ebec636daf2fb7c624a1e153dd5e17532`；
- physical output payload SHA-256：
  `fa36cf6417c4dfe0f6c31c1f6a1286ba20d431e84c13065201529327825d6785`；
- stock four-lane 继续作为负控失败：首个冻结实例反例为
  weight `[2,-126,-21,-26]`、activation `[17,27,9,28]`，
  stock=`-32483`、W3 target=`1225`；
- 独立 serialized holdout 覆盖正负值、进位、奇偶 K、K tail、bias、
  非零 `x_zp` 修正和 psum32 wrap，全部通过；
- 定向标准库测试：
  `python -m unittest -v tests.test_conv_node0004_serialized_one_product_local_e2 tests.test_int8_sa_rtl_repair_acceptance`
  共 11 项，通过 11 项；项目 `.venv` 未安装 pytest，因此没有新增依赖；
- 独立 validator：
  `tools/validate_conv_node0004_serialized_one_product_local_e2.py`，
  返回 `valid=true`。

## Materialization / address ownership

活动收据：

- `.agents/rules/生成前必读索引.md`：
  `3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19`；
- `.agents/rules/算子配置规则.md`：
  `407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc`；
- `.agents/rules/INT8_SA点积专项规则.md`：
  `f616db76c74c5a760ac5f02f7fb57f01379555b7dda885adebebf232cc8f8a1d`；
- 主线授权记录：
  `c208dc45c652b0ca420bdf000690f8a32ce85858b53df5daca619d83d15477b1`；
- `.agents/plan.md` 当前 SHA：
  `a1e19c6e84360641205836f6fa0b172fc0405472b8b2dfdc4c580cc2e0875516`，
  仅作 mutable provenance，不作为活动语义绑定。

按 `CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001` 对三个 source JSON 与最终
address-bound JSON 做逐 leaf diff：每 wave 只有四个 `base_addr` 的等值十六进制文本
规范化，共 12 个 raw diff；每项均记录 owner、输入、公式、旧值、期望新值和授权。
语义性 non-base leaf diff 总数为 `0`，non-base allowlist 为空。

按 `CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001`，activation 来自 node0003
正式 W3 producer output，weight/bias 来自冻结 ONNX initializer；物理化只做
value-preserving Conv28 permutation 和 `K group/lane -> serialized group` 重排并补零。
没有 replay scaled、rounded、saturated、accumulated、requantized 或 final tensor。
node0004 W3 INT32 accumulator 只作独立 oracle，明确
`never_consumed_as_compute_input=true`。

正式 D coverage 从最终 occurrence/address 方程重算：

```text
offset = row*3584 + (lc15*8+lc9)*64 + lc13*32 + byte
row=0..55, lc15=0..6, lc9=0..7, lc13=0..1, byte=0..31
```

得到每个 D region 连续且不重不漏的 `200704` bytes；共 64 个 region、每 region
`12544` 个唯一 16-byte request，typed D 总量 `12845056` bytes。该结论来自最终
materialized occurrence/address，而不是静态 stride 推测。

## BYPASS_ANNOTATION

- `bypass_reason`：stock four-lane INT8 SA 对 CSA carry 再左移一次，同时合法四乘积
  reduction 需要 signed18，而现路径只保留 signed17 且忽略 `cout17`。
- `contradicted_or_missing_native_path`：普通 stock
  `s8*u8 dot4 -> psum32` 不 bit-exact；最小 carry 反例为四个乘积均为 1，
  target=4、stock=6；合法 dot4 范围 `[-130560,129540]` 超出 signed17
  `[-65536,65535]`。
- `exact_equivalence_scope`：仅冻结 node0004 accumulate、`x_zp=0`、W3 bias 与
  INT32 modulo accumulation；synthetic holdout 的 nonzero `x_zp`/tail/wrap
  只证明序列化算术，不发布其他节点。
- `materialized_configuration_mechanism`：原 K lane 各自扩成一个四-byte SA
  occurrence，原 lane 原位保留，其余 lane 置零；`LC4/LC6` group count
  从 16 扩成 64。
- `performance_and_resource_cost`：serialized occurrences=`205520896`，
  product-lane slots=`822083584`；compute occurrence、A payload、B payload
  均为 4×；最大有效 lane utilization=`25%`；未增加 barrier 或 scratch stage。
- `unresolved_production_blocker`：
  `B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY`、
  `B_SA_INT8_DUPLICATE_CARRY_SHIFT`、`B_SA_INT8_REDUCTION_WIDTH`、
  `B_CONV_SERIALIZED_BASELINE_PERFORMANCE`、`B_CONV_SERVER_DYNAMIC_RELEASE`。
- `claim_boundary`：仅本地 accumulate-only
  `CONFIG_ONLY_CORRECTNESS_BASELINE`；不是 target、production 或 performance
  release；不关闭本实例外 bias/psum/tiling/tail，不连接 requant，不外推 53 个 Conv；
  QLinearMatMul 只共享单乘积累积结论，不关闭 rank2/tail。

## BLOCKER_DELTA

- close：`B_SA_SERIALIZED_FALLBACK_MATERIALIZATION`；
- keep：`B_CONV_INT8_SA`、`B_MATMUL_INT8_SA`、
  `B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY`、
  `B_SA_INT8_DUPLICATE_CARRY_SHIFT`、`B_SA_INT8_REDUCTION_WIDTH`；
- add：`B_CONV_SERIALIZED_BASELINE_PERFORMANCE`、
  `B_CONV_SERVER_DYNAMIC_RELEASE`。

## RULE_DELTA_PROPOSAL

`NONE`。现有 `CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001`、
`CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001` 与
`CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001` 已覆盖本轮新增证据。

## 冻结身份

- machine contract：
  `contracts/operator_config/r5_conv_node0004_serialized_one_product_local_e2_v1.json`,
  file SHA-256
  `3bfa060ef8598c932d7e456eec4d016ed3f8ff04f2cb9b7744eb8668884f4627`,
  inner contract SHA-256
  `c9e0538d19a2174ead94286b84ca05444cc4773a5aba8090f22de163a778457a`；
- final execplan bundle：
  `artifacts/operator_config_validation/r5_conv_node0004_serialized_one_product_local_e2_v1/execplan_final/bundle_manifest.json`,
  SHA-256
  `b9cf23d99646650ee5e8f46ae573cdc343b4464df041850150cb1ad45854fce9`；
- physical asset：
  `artifacts/operator_config_validation/r5_conv_node0004_serialized_one_product_local_e2_v1/physical_assets.npz`,
  SHA-256
  `d9783701433e923433d2df4e4b598ccb6fed860f5f755a9182f44cad69268c1d`；
- validation report：
  `artifacts/operator_config_validation/r5_conv_node0004_serialized_one_product_local_e2_v1/validation_report.json`,
  SHA-256
  `9a1ea01f9afcccbb86a69deeeab98850559aa9009165b9a344a2956c941460be`。

未修改功能 RTL；未检查服务器文件、名称或 identity；未生成、上传或运行服务器包。
