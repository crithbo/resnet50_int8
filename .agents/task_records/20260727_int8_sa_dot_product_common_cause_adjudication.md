# 2026-07-27 INT8 SA dot-product 共因裁决

## RETURN_ANALYSIS

- 范围：ResNet50 typed lowering 中 53 个 QLinearConv accumulate 与 1 个
  QLinearMatMul accumulate 共享同一 INT8 SA 算术门。
- 普通目标方程为：

  ```text
  int32_acc = bias_or_psum + Σ(s8(weight_i) * u8(activation_i))
  ```

- 配置 `mode=gemm, data_type=int8` 已按预期编码并到达 SA；操作数方向也是
  `DataA=s8`、`DataB=u8`、`DataC=psum32`。mapper、编码和 operand packing
  不是 `model=4 / RTL=6` 的根因。
- stock RTL 的第一层 INT8 reduction 同时存在两个算术问题：
  1. 第一层 `CSA_4to2` 输出的 carry 已经左移一位，但在交给第二层前又左移；
  2. 四个合法 s8×u8 乘积总和需要 signed 18 bit，现有第一层只有 signed
     17 bit 且 `cout` 未被消费。
- 因而本轮只关闭了“首处分歧定位和三路裁决”，没有关闭硬件兼容性 blocker。
  按停止门，未继续 bias/psum/tiling/tail，也未物化 Conv/MatMul 正式 JSON 或
  服务器包。

机器合同：
`contracts/operator_config/int8_sa_dot_product_adjudication_v1.json`
（SHA-256
`3495e752e2f9658672bf4ca2399a82c4e292e94ad5a6a3dc0983a664f152d8fe`）。

## FIRST_DIVERGENCE

逐字段路径：

1. `ndp-sim/jsons/node0004_accumulate_wave0_nopp_r1.json:790-793`：
   `gemm / bias_enable=1 / int8 / transout_last_index=2`。
2. `ndp-sim/bitstream/config/special.py:7,37`：`gemm -> mode 0`，bias 仅编码
   enable；生成的 `special_array` 位串见
   `artifacts/operator_config_validation/r5-server-candidates/node0004-nopp-r1-v2/config/op0/parsed_bitstream.txt:123-124`。
3. `Specialized_Array_Config.sv:114-116` 直接解包 computation type 与 bias；
   `SA_PE_Control_Block.sv:173-175` 把三个输入分别送入 ALU。
4. `SA_PE_ALU.sv:23-34` 固定连接 DataA/DataB/DataC；整数 packing 在
   `SA_PE_Float_Control.v:199-227`，方向与目标量化域一致。
5. `SA_PE_Mul_Array.v:279-281` 用 17-bit `CSA_4to2_int`。公共
   `CSA_4to2.v:31` 已输出 `carry={carry_temp[..],1'b0}`。
6. **首处分歧**在 `SA_PE_Mul_Array.v:295`：
   `last_B={carry_int[30:0],1'b0}` 再次左移已经移位的 carry。

最小反例为四个 `1×1`：

```text
ordinary = 4
first CSA = sum17 2 + carry17 2 = 4
stock handoff = sum17 2 + (carry17 << 1) 4 = 6
```

扩展矩阵覆盖正/负值、双 lane 进位、K=3/K=5、bias off/on、非零 x_zp
和正负满范围。单 lane 无进位可通过，但这不构成四 lane 点积兼容证明。

独立位宽反例：

```text
4 * 127 * 255  =  129540 > signed17 max  65535
4 * -128 * 255 = -130560 < signed17 min -65536
```

所以仅删除 line 295 的额外移位仍不足以覆盖合法 INT8 域。

## CONFIG_ONLY_OPTION

- 普通四 lane SA：**不可行**。现有 `gemm/gemv`、bias、transout、major
  字段均不改变整数 compressor；FP16/BF16 会重解释数据域，不能提供精确
  INT32 点积。
- 可证明的 stock-RTL correctness fallback：每个 SA occurrence 最多只允许
  一个非零乘积 lane。此时第一层 carry 恒为 0，后续 product+psum 的
  32-bit 路径对模 2^32 累加精确。
- 代价：product-lane 利用率 1/4；最少 4 倍 occurrence；若不能复用则最多
  4 倍 operand traffic；名义 SA 吞吐上界约 25%。
- 当前状态仅为源码和 bit-exact replay 证明，未获授权物化 JSON，不能标为
  E2/E4/E5 或 release。

## ALTERNATIVE_TOPOLOGY_OPTION

- GA opcode 14 的标量方程 `int32_mac=A*B+C` 在算术上可构造精确树。
- 当前不可发布：没有获批的 opcode-14 Conv/MatMul 样例；non-transout normal
  FIFO 双流、stage barrier、s8 byte 到 int32 的符号扩展入口均未动态闭合。
- 性能不适合作为生产 Conv 路径：16 个 GA scalar MAC 对比名义
  `64 SA PE × 4 products = 256` products/occurrence，原始乘积吞吐上界约
  6.25%。可保留为诊断拓扑，不建议作为 ResNet Conv production fallback。

## RTL_OPTION

仅给提案，未修改任何功能 RTL：

- INT8 路径必须形成 signed 18-bit 的四乘积精确和，再与 signed psum32
  做精确的模 2^32 累加。
- 最小安全修复必须同时：
  1. 在 `SA_PE_Mul_Array.v:279-296` 的 INT8 branch 中，以两个 signed
     17-bit pair sum 和一个 signed 18-bit `dot4` 替代现有第一层
     `CSA_4to2_int` 交接；
  2. integer `last_A=signext32(dot4)`、`last_B=32'b0`，
     `last_C=pipe_FractC[31:0]` 保持不变，继续使用现有 32-bit
     `CSA_3to2` 做 psum 累加；
  3. 保持 `DataA=s8 / DataB=u8 / DataC=psum32`；
  4. 不修改公共 `CSA_4to2.v`，也不改变 FP16/BF16 branch、配置编码或接口。
- 不建议仅把 `CSA_4to2_int` 从 17 改成 18 bit：若不另外证明 signed
  carry/cout identity，仍可能错误解释模数 carry；显式 signed adder tree
  直接表达所需恒等式，补丁语义更窄。
- 接受门：本合同全部反例、small-domain exhaustive、合法边界值，以及后续
  独立 RTL testbench/observer 动态证明。

## RECOMMENDED_CONV_PATH

- production：选择新的/修正后的兼容 RTL identity（方案 C），恢复名义 SA
  lane 利用率。
- interim correctness baseline：若主线/用户后续明确授权，可先实验每
  occurrence 单乘积序列化（方案 A）；它是正确性基线，不是性能 release。
- 不推荐方案 B 作为生产 Conv 路径。

## BLOCKER_DELTA

保持：

- `B_CONV_INT8_SA`
- `B_MATMUL_INT8_SA`
- `B_CONV_CONFIG_BOUND_SIMULATOR_RTL_CSA_MISMATCH`
- `B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY`

新增：

- `B_SA_INT8_DUPLICATE_CARRY_SHIFT`
- `B_SA_INT8_REDUCTION_WIDTH`
- `B_SA_SERIALIZED_FALLBACK_MATERIALIZATION`

关闭：无。

## RULE_DELTA_PROPOSAL

仅提案，不修改规则：

1. INT8 SA 算术批准必须同时覆盖 carry 重复移位与四乘积完整 signed
   range；仅凭四个 `1×1` 反例被修复不足以放行。
2. 在兼容 RTL identity 获批前，stock-RTL config-only correctness
   fallback 每个 SA occurrence 最多一个非零乘积 lane；在 E2/E4/E5
   物化前仍只算 candidate。
3. QLinearConv 与 QLinearMatMul 共用此算术门；任一都不得先行进入
   bias/psum/tiling/tail 或封包。

## 验证与边界

- `tests.test_int8_sa_dot_product_adjudication`：
  small-domain K=1..4 exhaustive、显式 K=5、x_zp 静态修正和满范围反例。
- `candidate_release=false`
- `server_package_allowed=false`
- 未修改 `.agents/plan.md`、`.agents/rules/**` 或 `NDP_copy01/rtl/**`。
