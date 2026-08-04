# GA signed INT32 转 FP32 的负数转换错误

## 1. 问题概述

General Array 输入端的 INT32→FP32 转换逻辑错误处理负数幅值，并把 `-1` 错认成
INT32 最小值。结果是合法 signed INT32 accumulator 无法被正确转换为 FP32。

这会直接影响卷积和矩阵乘输出的量化阶段，因为量化前必须对 signed INT32 accumulator
乘以 scale。

## 2. RTL 文件与信号路径

云端仓库相对路径：

```text
code/NDP_rtl/Slice/General_Array/GA_Inport/GA_Inport.sv
```

关键位置：

```text
GA_Inport.sv:258-316
```

信号链：

```text
32-bit signed input
→ sign / magnitude extraction
→ zero/min detection
→ leading-zero normalization
→ exponent/fraction rounding
→ FP32 output
```

## 3. 当前错误代码

```verilog
assign ga_inport_int32_sign =
    ga_inport_ib_data[31];

assign ga_inport_int32_data =
    ga_inport_int32_sign
        ? ~ga_inport_ib_data[30:0] + 1
        :  ga_inport_ib_data[30:0];

assign ga_inport_int32_zero =
    ~(|ga_inport_ib_data[31:0]);

assign ga_inport_int32_min =
    &ga_inport_ib_data[31:0];

assign ga_inport_int32tofp32_exp =
    ga_inport_int32_zero ? 8'h00 :
    ga_inport_int32_min  ? 8'h9E :
                           ga_inport_not_inf_fp32_exp;
```

存在两个直接问题：

1. 负数取绝对值时只对 `[30:0]` 做二补码，不能表示 `abs(INT32_MIN)=2^31`；
2. `&input[31:0]` 检测的是 `0xffffffff`，即 `-1`，不是
   `0x80000000`，即 `INT32_MIN`。

## 4. 正确计算语义

目标是 IEEE-754 binary32 的 correctly-rounded signed integer conversion：

```text
fp32_out = round_to_nearest_even(float32(signed_int32_in))
```

负数幅值需要在至少32位无符号域内正确表示：

```text
magnitude =
    sign ? unsigned_abs_32(input) : input
```

INT32 最小值必须由：

```text
input == 32'h80000000
```

识别，而不是全位 AND。

## 5. ResNet50 中必须使用该功能的计算

量化卷积和矩阵乘首先产生 signed INT32 accumulator，随后通常执行：

```text
scaled = float32(accumulator) × multiplier
output = saturate_uint8(round_to_even(scaled) + zero_point)
```

accumulator 出现负值是正常情况：

- signed 权重同时包含正数和负数；
- bias 可以为负；
- input zero-point correction 可以改变符号；
- residual 或矩阵乘结果也可能为负。

当输出 zero-point 非零时，靠近零的负 accumulator 可能量化成正的 UINT8，不能简单把
所有负值提前钳位为零。

## 6. 最小错误案例

### 输入 `-1`

```text
input bits     = 0xffffffff
expected FP32  = 0xbf800000   // -1.0
RTL FP32       = 0xcf000000
```

原因：

```text
&0xffffffff = 1
```

所以 `-1` 被 `ga_inport_int32_min` 错认成特殊最小值。

### 输入 `INT32_MIN`

```text
input bits     = 0x80000000
expected FP32  = 0xcf000000   // -2147483648.0
RTL FP32       = 0xce800000
```

原因：

```text
&0x80000000 = 0
```

真正的 INT32 最小值没有进入特殊路径，同时 `[30:0]` 幅值计算无法保留 `2^31`。

## 7. 对网络结果的影响

转换错误发生在 scale 乘法之前，会破坏 accumulator 的真实幅值。后续步骤无法恢复：

- scale 乘法使用错误 FP32；
- rounding 基于错误值；
- zero-point 加法不能补偿；
- saturation 可能掩盖部分 `zero_point=0` 的负数，但不能证明转换正确；
- 非零 output zero-point 时会直接产生错误 UINT8。

## 8. 修复验收条件

最低验收应包含：

1. `0, ±1, ±2`；
2. `INT32_MIN, INT32_MAX`；
3. 2 的幂及其相邻值；
4. 需要 FP32 rounding 的大整数；
5. 全 signed INT32 域的参考模型随机对比；
6. 验证 round-to-nearest-even；
7. 使用正 multiplier 和不同 output zero-point 验证最终量化结果。

只验证最终 UINT8 饱和为0不能作为该转换模块的通过依据。

