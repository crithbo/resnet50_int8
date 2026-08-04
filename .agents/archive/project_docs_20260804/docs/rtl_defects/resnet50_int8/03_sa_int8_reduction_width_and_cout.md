# SA INT8 四乘积归约位宽不足且丢弃 cout

## 1. 问题概述

四个合法 `signed8×unsigned8` 乘积的完整和需要 signed18 表示。当前 Specialized
Array 使用17位 `CSA_4to2`，并且没有连接最高位 `cout`。因此合法输入会在第一级
归约中丢失最高位，后续再扩展到32位也无法恢复。

## 2. RTL 文件与信号路径

云端仓库相对路径：

```text
code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v
code/NDP_rtl/utils/CSA/CSA_4to2.v
```

关键位置：

```text
SA_PE_Mul_Array.v:279-292
CSA_4to2.v:25-32
```

## 3. 当前错误代码

`SA_PE_Mul_Array.v`：

```verilog
CSA_4to2 #(
    .csa_4to2_width(17)
) CSA_4to2_int (
    .sum   (sum_int[16:0]),
    .carry (carry_int[16:0]),
    .cout  (),
    .op0   (...),
    .op1   (...),
    .op2   (...),
    .op3   (...),
    .cin   (1'b0)
);

assign sum_int[31:17] =
    {15{sum_int[16]}};

assign carry_int[31:17] =
    {15{carry_int[16]}};
```

问题包括：

1. compressor 输入输出宽度只有17位；
2. `cout` 悬空；
3. 后续从 bit16 做符号扩展，默认17位结果已经完整。

## 4. 正确位宽分析

单个乘积范围：

```text
signed8  ∈ [-128, 127]
unsigned8 ∈ [0, 255]

product ∈ [-32640, 32385]
```

四个乘积总和范围：

```text
minimum = 4 × (-128 × 255) = -130560
maximum = 4 × ( 127 × 255) =  129540
```

signed17 范围只有：

```text
[-65536, 65535]
```

signed18 范围为：

```text
[-131072, 131071]
```

所以四乘积归约最低必须保留18位有效有符号结果。不能用“通常数值较小”作为缩窄依据，
因为上述边界全部属于合法 INT8/UINT8 输入。

## 5. ResNet50 中必须使用该功能的计算

量化卷积通常把 signed INT8 权重与 UINT8 activation 相乘。每次 SA dot4 都可能同时
遇到大幅值权重和激活。

该归约用于：

- 全部卷积的通道点积；
- 3×3 kernel 的空间点积；
- 下采样和 projection 卷积；
- 最终矩阵乘的 K 维点积。

即使网络实际数据没有每次都达到理论极值，也不能把合法输入域之外的假设固化在 RTL 中。
不同模型输入、校准范围或权重都可能触发溢出。

## 6. 错误案例

### 最大正向 dot4

```text
A lanes = [127, 127, 127, 127]
B lanes = [255, 255, 255, 255]
```

期望：

```text
4 × 127 × 255 = 129540
```

如果只保留 signed17，129540 的17位截断解释为：

```text
-1532
```

最高位信息已经在第一归约级丢失。

### 最大负向 dot4

```text
A lanes = [-128, -128, -128, -128]
B lanes = [ 255,  255,  255,  255]
```

期望：

```text
4 × (-128) × 255 = -130560
```

signed17 截断解释为：

```text
512
```

结果不仅幅值错误，符号也变成正数。

当前完整 RTL 还叠加了 carry 重复左移，因此最终可观察结果会进一步偏离；上述截断值用于
单独说明位宽与 `cout` 问题。

## 7. 对网络结果的影响

该错误可能造成：

- Conv INT32 accumulator 突然变号；
- 大正值变为负值或小负值；
- 大负值变成正值；
- 后续 bias、ReLU、requant 无法恢复真实值；
- 最终 UINT8 saturation 可能把错误值推到完全相反的端点。

它不是精度损失，而是整数点积计算错误。

## 8. 修复验收条件

最低验收应包含：

1. 归约内部至少覆盖完整 signed18 dot4；
2. `cout` 必须被纳入结果或由等价结构完整吸收；
3. 正负最大边界必须逐 bit 正确；
4. 覆盖全部单乘积合法域和四 lane 边界组合；
5. 与 carry 权重修复组合验证；
6. sign-extension 到32位后必须等于 exact dot4；
7. 再与任意32位 DataC 做 modulo-2^32 累加。

