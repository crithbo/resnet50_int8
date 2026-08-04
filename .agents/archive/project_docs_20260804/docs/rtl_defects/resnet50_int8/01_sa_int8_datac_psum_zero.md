# SA INT8 模式丢弃 DataC，导致卷积 partial sum 和 bias 无法累加

## 1. 问题概述

Specialized Array 的 INT8 运算路径会在乘法流水线中把 `DataC` 清零。其实际计算变成：

```text
result = dot4(A, B)
```

而 ResNet50 的卷积和矩阵乘需要：

```text
result = DataC + dot4(A, B)
```

其中 `DataC` 承载前一次 partial sum，第一次运算时还可能承载 bias 或输入零点修正。
只要一个输出需要超过四个乘积，该功能就是必需的。

## 2. RTL 文件与信号路径

云端仓库相对路径：

```text
code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_ALU.sv
code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v
code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v
```

关键位置：

```text
SA_PE_Float_Control.v:253-258
SA_PE_Mul_Array.v:204-212
SA_PE_Mul_Array.v:294-296
```

信号链：

```text
DataC
→ gr_DataC
→ o_AddExp / o_AddNZero / o_AddFract
→ i_AddNZero / i_FractC
→ pipe_FractC
→ last_C
→ final integer CSA
```

## 3. 当前错误代码

`SA_PE_Float_Control.v`：

```verilog
assign o_AddExp   = gr_DataC[30:23] & {8{i_Mode}};
assign o_AddFract = i_Mode
                  ? {8'b0, o_AddNZero,
                     gr_DataC[22:0] & {23{o_AddNZero}}}
                  : gr_DataC;
assign o_AddNZero = |o_AddExp;
```

INT8 路径中 `i_Mode=0`，所以：

```text
o_AddExp   = 0
o_AddNZero = 0
```

`SA_PE_Mul_Array.v` 随后执行：

```verilog
pipe_FractC[31:0] <=
    i_AddNZero ? i_FractC[31:0] : 32'b0;
```

因此：

```text
pipe_FractC = 0
last_C      = pipe_FractC = 0
```

虽然 `o_AddFract` 在 INT8 模式表面上传递了 `gr_DataC`，下一流水级仍依据
`i_AddNZero=0` 将其清零。

## 4. 正确计算语义

整数路径不应借用浮点 exponent 是否非零来判断 32-bit `DataC` 是否有效。只要当前
INT8 运算声明需要 partial sum，整数 `DataC` 应逐 bit 进入最终 32-bit 加法：

```text
result32 =
    DataC
    + signed_product_0
    + signed_product_1
    + signed_product_2
    + signed_product_3
    mod 2^32
```

这里的修复目标是计算语义，不限定具体门级实现。修复时仍需保持现有 pipeline valid、
stall 和 modulo-2^32 行为。

## 5. ResNet50 中必须使用该功能的计算

ResNet50 的每个卷积输出都是对 kernel 空间和输入通道的累加。例如：

```text
3×3 convolution, input_channels=64
K = 3×3×64 = 576 products/output
```

一次四 lane 运算最多处理四个乘积，因此每个输出至少需要：

```text
576 / 4 = 144 次 partial-sum 更新
```

即使是 `1×1, input_channels=64` 的卷积，也需要16次四乘积累加。

最终全连接矩阵乘的 K 维为2048，每个输出需要512次四乘积累加。因此：

- 全部53个卷积计算必须使用 partial sum；
- 最终1000类矩阵乘必须使用 partial sum；
- 卷积 bias 和输入零点修正也必须加入同一 INT32 累加域。

## 6. 最小错误案例

为避免同时触发四乘积 carry 和位宽问题，只启用一个非零乘积 lane。

### 正数 DataC

```text
A lanes = [1, 0, 0, 0]
B lanes = [1, 0, 0, 0]
DataC   = 7
```

期望：

```text
1×1 + 7 = 8
```

当前 RTL：

```text
pipe_FractC = 0
result      = 1
```

### 负数 DataC

```text
A lanes = [-1, 0, 0, 0]
B lanes = [ 1, 0, 0, 0]
DataC   = -5
```

期望：

```text
-1 + (-5) = -6
```

当前 RTL：

```text
-1
```

## 7. 对网络结果的影响

未经修复时，硬件只能得到每次局部 dot4，不能得到完整 K 维卷积和。典型后果包括：

- 前一轮 partial sum 丢失；
- bias 丢失；
- multi-wave 累加失效；
- K-tail 无法加入已有结果；
- 后续激活、残差加法和输出量化都建立在错误 accumulator 上。

后续饱和或激活不能恢复已经丢失的 partial sum。

## 8. 修复验收条件

最低验收应包含：

1. 单非零乘积分别叠加正、负、零 `DataC`；
2. 四乘积叠加任意 `DataC`；
3. `DataC` 接近 `INT32_MAX/INT32_MIN` 时验证 modulo-2^32；
4. 连续多个 occurrence 验证每次输出成为下一次 `DataC`；
5. 1×1 和3×3卷积完整 K 维累加；
6. bias on/off 和输入零点修正；
7. 最终矩阵乘 K=2048 的连续 partial sum。

只验证 `DataC=0` 的单乘积不能证明本问题已修复。

