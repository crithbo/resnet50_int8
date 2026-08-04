# SA INT8 四乘积归约的 carry 被重复左移

## 1. 问题概述

`CSA_4to2` 已经把 carry 输出左移一位，使其具备正确的二进制权重；上层
`SA_PE_Mul_Array` 又把该 carry 左移一次。最终 carry 权重变成正确值的两倍，普通
四 lane INT8 点积产生错误结果。

## 2. RTL 文件与信号路径

云端仓库相对路径：

```text
code/NDP_rtl/utils/CSA/CSA_4to2.v
code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v
```

关键位置：

```text
CSA_4to2.v:25-32
SA_PE_Mul_Array.v:279-295
```

信号链：

```text
four INT8 products
→ CSA_4to2_int
→ sum_int / carry_int
→ last_A / last_B
→ final CSA_3to2
```

## 3. 当前错误代码

`CSA_4to2.v`：

```verilog
assign carry_temp =
    (cin_array & s_temp) | (~s_temp & op3);

assign carry =
    {carry_temp[csa_4to2_width-2:0], 1'd0};
```

此处 `carry` 已经是：

```text
carry_temp << 1
```

但 `SA_PE_Mul_Array.v` 又执行：

```verilog
assign last_A =
    pipe_IsFloat ? attend_sum1 : sum_int;

assign last_B =
    pipe_IsFloat
        ? attend_sum2
        : {carry_int[30:0], 1'b0};
```

即：

```text
last_B = carry_int << 1
       = carry_temp << 2
```

## 4. 正确计算语义

Carry-save 表示应满足：

```text
integer_sum = sum_int + carry_int
```

前提是 `carry_int` 已经由 `CSA_4to2` 对齐到正确权重。上层不得再次移位。

如果接口约定希望上层负责移位，则应让 `CSA_4to2` 输出未移位的 `carry_temp`；两处只能
选择一处完成权重对齐，不能同时执行。

## 5. ResNet50 中必须使用该功能的计算

ResNet50 的 INT8 卷积和最终矩阵乘都会把四个 `signed8×unsigned8` 乘积组成一个
dot4。只要四个 lane 中至少两个乘积同时非零，carry-save 归约就可能产生 carry。

这种情况在下列计算中是常态：

- 所有卷积 kernel 与输入通道的点积；
- 1×1 卷积的通道归约；
- 3×3 卷积的空间和通道归约；
- 最终 K=2048 的矩阵乘。

## 6. 最小错误案例

```text
A lanes = [1, 1, 1, 1]
B lanes = [1, 1, 1, 1]
DataC   = 0
```

期望：

```text
1+1+1+1 = 4
```

当前 RTL：

```text
6
```

负数对称案例：

```text
A lanes = [-1, -1, -1, -1]
B lanes = [ 1,  1,  1,  1]
DataC   = 0
```

期望：

```text
-4
```

当前 RTL：

```text
-6
```

该案例的乘积总和位于 signed17 范围内，且 `DataC=0`，因此可以独立证明 carry 权重
错误，不依赖 DataC 丢失或四乘积位宽溢出。

## 7. 对网络结果的影响

错误不是固定偏置，而是取决于每组乘积形成的 carry pattern。不同输入、权重和通道会
产生不同误差，无法在 bias 或输出量化阶段统一补偿。

卷积的每个输出需要大量 dot4，误差会在 K 维累加过程中持续传播。

## 8. 修复验收条件

最低验收应包含：

1. 四个 `1×1` 和四个 `(-1)×1`；
2. 正负混合且产生 carry 的向量；
3. 随机完整 `signed8×unsigned8` dot4；
4. 检查内部恒等式 `sum_int + carry_int == exact_dot4`；
5. 与 DataC 修复组合后验证 `DataC + exact_dot4`；
6. 不得只比较最终饱和后的 UINT8，必须比较 INT32 accumulator。

