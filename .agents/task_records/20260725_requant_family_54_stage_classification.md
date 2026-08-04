# RequantizeUint8 全 54-stage 数值分类与动态 alias 门

日期：2026-07-25

## 结论

验证方案中的全体 54 个 `RequantizeUint8` typed request 已逐项完成：

```text
ONNX initializer
→ typed qparam/hash
→ W3 int32 accumulator
→ 独立标准 requant replay
→ 当前 guard+magic recipe replay
→ 精确分类/blocker
→ backend/local closure/project ledger
```

数值分类已经结束，但没有扩大 JSON emission：

- 54/54 multiplier 均为有限正数；
- 54/54 的独立标准公式
  `clamp(round_to_nearest_even(acc*multiplier)+y_zero_point)` 与正式 W3 golden
  完全一致；
- 33 项 `y_zero_point=0` 与 node0001 guard recipe 数值兼容；
- 其中只有 `r5:hwop-0001-01` 已完成 JSON、W4 lifetime、bitstream、execplan、SCA
  与双隔离重建的物理 E2；
- 其余 32 项仍为
  `NUMERIC_RECIPE_COMPATIBLE_PHYSICAL_E2_PENDING`，没有生成新 JSON；
- 21 项 `y_zero_point!=0` 全部被当前 clamp guard 反证；
- 正式 target config、E4、E5 仍均为 0。

## 全量数据

- request：54；
- W3 元素：169,410,176；
- 负数：81,098,912；
- `-1`：6,640；
- 零：6,304；
- 标准公式 mismatch：0；
- nonzero-zero-point guard mismatch：47,844,816；
- zero-point-zero stage：33；
- nonzero-zero-point stage：21，其中 even 16、odd 5；
- 完整物化 E2：1；
- 数值兼容但物理 E2 待完成：32；
- 当前 guard 反证：21。

机器资产：

- `artifacts/operator_config_validation/r5-requant-family-classification-v1/generation_receipt.json`
- `artifacts/operator_config_validation/r5-requant-family-classification-v1/report.json`
- `contracts/operator_config/requant_family_classification_v1.json`

report 完整枚举 54 个 request 的 request SHA、shape、qparam、W3 输入/输出文件身份、
元素统计、三种 replay mismatch、分类和 blocker；没有抽样放行。

## 新裁决

### 1. nonzero zero-point 不能复用 node0001 guard

目标是：

```text
clamp(round(acc * multiplier) + y_zero_point)
```

当 `y_zero_point>0` 时，部分负 accumulator 应映射为正 UINT8。先执行
`max(acc,0)` 会丢失负数幅值，21 个 stage 的正式 W3 全部命中差异。

规则：

- `CDA-REQUANT-NONZERO-ZP-GUARD-001`
- blocker：`B_REQUANT_NONZERO_ZP_SIGNED_DOMAIN`

不得用最终饱和或某次输入未命中边界解除。

### 2. odd zero-point 的 magic tie parity

旧路径把 zero-point 加在 magic-rounding 内：

```text
magic_round(scaled + zero_point)
```

它不总等于：

```text
round_to_nearest_even(scaled) + zero_point
```

当 zero-point 为奇数时，exact-half 的偶数基准发生翻转。`r5:hwop-0014-01`
在正式 W3 命中 32 个反例：`scaled=4.5`、`zero_point=123` 时 golden=127，
旧 magic=128。

规则：

- `CDA-REQUANT-ZP-TIE-PARITY-001`
- blocker：`B_REQUANT_MAGIC_ZP_TIE_PARITY`

### 3. shape 兼容不能代替物化 E2

33 个 zero-point-zero stage 覆盖五种 shape：

- `[16,64,112,112]`：1；
- `[16,64,56,56]`：6；
- `[16,128,28,28]`：8；
- `[16,256,14,14]`：12；
- `[16,512,7,7]`：6。

node0001 只关闭第一种。其余四种即使数值公式相同，也必须分别验证 occurrence、地址、
W4 lifetime、transaction、buffer、bitstream、execplan 和 SCA；若直接按三 wave、
HWC8 两级展开，32 个 request 预计产生 5,712 个物理 stage。没有这些 E2 证据前，
批量生成只会制造未经证明的候选，因此按公共停止门未生成。

blocker：`B_REQUANT_SHAPE_LIFETIME_MATERIALIZED_E2`。

`r5:hwop-0075-01 [16,1000]` 虽然 1000 可被 8 整除，但属于 MatMul 二维输出，
另保留 `B_REQUANT_MATMUL_2D_LAYOUT`；不得当作 HWC8。

## alias-aware 动态门

测试修复会话发现 node0001 的 guard D/round A 按 slice 复用地址。run 末 SCA_D
只能证明最后驻留值，不能复制为 24 个历史 occurrence 的正式 readback。

新增 `CDA-REQUANT-TRANSIENT-GUARD-E4-001`：

1. 历史 guard：same-clock actual accepted MSE4-write 只读 observer，全量记录并对
   occurrence golden；
2. 最终 UINT8：正式 SCA_D；
3. 每 slice 最后驻留 guard：唯一地址正式 D。

三类证据必须分栏。observer 不得冒充 end-of-run formal D，alias SCA_D 不得冒充历史
guard。observer 只允许事务式修改 `rtl/` 外入口；`rtl/` 文件必须始终逐字节不变，
安装、编译、运行、恢复和 post-restore 身份缺一即失败。

## 读取边界

本轮分类是只读数值审计，没有创建或修改算子 JSON、mapping、bitstream、execplan、
SCA/SCA_D 或服务器包，因此读取收据明确省略 native planner/encoder/execplan
consumer 和服务器包规则。node0001 的历史物化 E2 只作为冻结证据被绑定。

当前专项规则 SHA-256：
`bb428f79966d197e1df8b63b0ed3072fbc40edd74a25a434d707e9eb0b5de4f6`。

本轮未修改任何 `rtl/` 文件，未生成服务器包，未上传或运行服务器。

## 最终身份与回归

- 专项规则文件 SHA-256：
  `bb428f79966d197e1df8b63b0ed3072fbc40edd74a25a434d707e9eb0b5de4f6`；
- 读取收据文件 SHA-256：
  `1c3af25e077cf3312b9a520ad0726f63701b78ffd479f4b99ffe4684cda9576f`；
- 全量 report 文件 SHA-256：
  `a5cfd039cc18c813f84436a45b45524f95b57d3e64fa607847b5055a2db93ee8`；
- family contract 文件 SHA-256：
  `5bfbb6cb08f6fb91bcecb2edf3ecb9089dfe96039ed05d86428f2a3e6f6acb4f`；
- local closure 文件 SHA-256：
  `4a851e84b819ec873e19681300eb6f979149dce9c4c0d6768d1a69eebc48be9f`；
- project closure 文件 SHA-256：
  `9d24a9145118a9351b6e8e8fd5817b2ab26539929365e814103948137cce0e00`。

最终执行 111 项相关 Python 回归，全部通过；另重放
`ga_sfu_affine_identity_tb.vvp`，七个 RTL 方程向量和总门均通过。
`git diff --check` 通过。总账保持 2 个 candidate、0 formal、0 E4、0 E5。

## 下一步

1. 依次选择四个 zero-point-zero holdout shape，每个完成独立物化 E2 后才扩展 emission；
2. nonzero-zero-point 需要 magnitude-preserving signed-domain 路径；
3. odd zero-point 还必须把 zero-point 移到 round-to-even 之后或证明等价硬件拓扑；
4. node0001 E4/E5 继续由“测试修复”会话按 alias-aware 三类动态证据执行。
