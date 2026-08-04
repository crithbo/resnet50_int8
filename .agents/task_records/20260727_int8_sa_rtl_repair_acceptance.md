# 2026-07-27 INT8 SA 兼容 RTL / 最小 repair 验收合同

## RETURN_ANALYSIS

P0-B 本轮只新增本地、bit-exact、fail-closed 的验收面，没有修改功能 RTL，也没有生成
Conv/MatMul 目标 JSON 或服务器包。

机器合同：
`contracts/operator_config/int8_sa_rtl_repair_acceptance_v1.json`
（SHA-256
`807aa1edb93c7e6c8c1548b3d41226672c4a6851c46f9d7e7812ef85ea14d22c`）。

proof harness：

- `resnet50_pipeline/int8_sa_rtl_repair_acceptance.py`
- `tools/build_int8_sa_rtl_repair_acceptance.py`
- `tools/validate_int8_sa_rtl_repair_acceptance.py`
- `tests/test_int8_sa_rtl_repair_acceptance.py`

合同固定三栏模型：

| 模型 | 角色 | 本轮裁决 |
|---|---|---|
| `stock_four_lane` | contradicted negative control | 保留 carry/width 失败，不得放行 |
| `proposal_signed18` | 未来兼容 RTL 的 acceptance oracle | 本地 bit-exact proof 通过 |
| `serialized_one_product` | stock-RTL correctness baseline | 本地 bit-exact proof 通过，仍禁止物化 |

`proposal_signed18` 的 occurrence 方程固定为：

```text
pair01_s17 = s16_product0 + s16_product1
pair23_s17 = s16_product2 + s16_product3
dot4_s18   = signext(pair01_s17) + signext(pair23_s17)
result_s32 = (psum32_bits + signext32(dot4_s18)) mod 2^32
```

非零 input zero-point 仍按权威量化恒等式进入初始 psum：

```text
initial_psum = bias - x_zero_point * Σ(weight)
```

每个 acceptance vector 都导出 packed DataA/DataB、输入 psum bits、两个 pair sum、
signed18 dot4、结果 bits 和 tail lane count，未来独立 RTL testbench 可直接逐 occurrence
比较，而不是只比较最终值。

## 缺陷双门验证

### Carry

四个 `1×1`：

```text
stock first CSA: sum17=2, carry17=2
target=4
stock=6
proposal=4
serialized=4
```

### Width

```text
positive dot4 =  4*127*255  =  129540
signed17 narrow             =   -1532
negative dot4 = 4*(-128)*255 = -130560
signed17 narrow              =     512
```

proposal 明确达到并保存这两个 signed18 合法极值，不依赖 `cout` 或模数 carry 的隐式
解释。

## Proof coverage

- small-domain exhaustive：
  - weights `{-3,0,3}`
  - activations `{0,1,7}`
  - K `1..4`
  - bias `{0,-11,INT32_MAX}`
  - input zero-point `{0,2}`
  - 总计 44,280 cases
  - proposal mismatch `0`
  - serialized mismatch `0`
  - stock mismatch `22,134`
  - ordered observation SHA-256
    `50f1ef08ed82512bf1b65621d05b6a526afa46234a04b33c285f00999cc97704`
- 合法单乘积完整域：256 个 s8 weight × 256 个 u8 activation，共 65,536 cases；
  同时以 `INT32_MAX` psum 验证模 `2^32` 加法。
- 四-lane 边界交叉：`weight∈{-128,127}`、`activation∈{0,255}`，
  256 cases，实际达到 `[-130560,129540]`。
- 显式 psum wrap：
  - `INT32_MAX + 1 -> 0x80000000`
  - `INT32_MIN - 1 -> 0x7fffffff`
- 显式 K-tail：K=3、5、6、7，覆盖 1/2/3 个有效 tail lanes。
- 显式 bias 与非零 x_zp：`x_zp=114`、`bias=-123456`、K=5。

## 未来兼容 RTL 身份输入接口

当前 `current_binding=null`。只有用户提供或本轮明确授权的身份才可绑定，所需输入为：

1. identity label；
2. 带 SHA-256 的 immutable source manifest；
3. top module 与 INT8 repair module binding；
4. 本地 compile/simulator command；
5. DataA/DataB/DataC/result 与 valid timing 的 testbench adapter mapping。

不得自动发现或检查服务器路径、目录名称、当前 RTL 身份、服务器 package/return。
未来 RTL pass 还必须把同一向量送入独立 RTL testbench，并逐 occurrence 比较结果和身份
收据；本地 Python proof 不冒充动态 RTL pass。

## RULE_DELTA

仅建议，不修改规则：

1. 兼容 INT8 SA RTL 必须通过 identity-bound、逐 occurrence repair harness；仅最终值相等
   不足以放行。
2. 验收始终同时保留 stock four-lane 负控和 serialized-one-product 独立正确性基线，
   防止 oracle 与 repair 实现共享同一错误。
3. 未来 RTL identity 是用户显式提供的接口输入；不得自动探测服务器位置或当前身份。

## BLOCKER_DELTA

保持：

- `B_CONV_INT8_SA`
- `B_MATMUL_INT8_SA`
- `B_CONV_CONFIG_BOUND_SIMULATOR_RTL_CSA_MISMATCH`
- `B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY`
- `B_SA_INT8_DUPLICATE_CARRY_SHIFT`
- `B_SA_INT8_REDUCTION_WIDTH`
- `B_SA_SERIALIZED_FALLBACK_MATERIALIZATION`

新增：

- `B_SA_COMPATIBLE_RTL_IDENTITY_PENDING`

关闭：无。

## 状态与读取收据

```text
status=LOCAL_BIT_EXACT_PROOF_PASS_RTL_IDENTITY_PENDING
candidate_release=false
server_package_allowed=false
functional_rtl_modified=false
target_json_generated=false
```

生成时读取收据：

- `.agents/plan.md`
  `23f5cef51f73ae4922581b95f04c15610a47b59f0d2fa55de241ce4efdb2449f`
- `.agents/rules/生成前必读索引.md`
  `6ae4c7fe09fcdb39a48357cfef645c272f67e7a81d09b5547ebd9a929e6ce1a4`
- `.agents/rules/INT8_SA点积专项规则.md`
  `f616db76c74c5a760ac5f02f7fb57f01379555b7dda885adebebf232cc8f8a1d`
- `contracts/operator_config/int8_sa_dot_product_adjudication_v1.json`
  `3495e752e2f9658672bf4ca2399a82c4e292e94ad5a6a3dc0983a664f152d8fe`

INT8 SA 专项规则是 active-rule current-match fail-closed 收据；validator 在 SHA 漂移时
直接失败。plan SHA 只保留生成时历史 mutable provenance，即使随后变化也不单独使合同
失效。
