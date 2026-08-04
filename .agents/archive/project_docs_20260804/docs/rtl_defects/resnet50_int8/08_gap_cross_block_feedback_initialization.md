# GAP 跨 reduction block 的 feedback 初始化条件错误

## 1. 问题概述

General Array transout 使用 `transout_initial` 阶段计数决定何时从 outbuffer 取得
`DataC`。当前匹配条件在阶段计数非零时允许绕过 input2 valid，随后又只根据
`end_transout_initial` 选择 outbuffer data，没有确认新的 partial sum 是否已经有效。

进入新 reduction block 时，控制器可能过早授权 feedback，把上一 block 的状态作为新
block 的初始 `DataC`。

## 2. RTL 文件与信号路径

云端仓库相对路径：

```text
code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv
code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv
```

关键位置：

```text
GA_PE_Inbuffer.sv:181-198
GA_PE_Inbuffer.sv:231-267
GA_PE_Outbuffer.sv:281-283
```

信号链：

```text
ga_pe_inbuffer_matched
→ transout_initial
→ end_transout_initial
→ input2 valid bypass
→ outbuffer feedback selection
→ DataC
```

## 3. 当前错误代码

输入匹配条件：

```verilog
assign ga_pe_inbuffer_matched =
       ga_pe_enable
    && ((!ga_pe_inport_enable[0])
        || ga_pe_inbuffer_valid_bit[0])
    && ((!ga_pe_inport_enable[1])
        || ga_pe_inbuffer_valid_bit[1])
    && ((!ga_pe_inport_enable[2])
        || ga_pe_inbuffer_valid_bit[2]
        || (alu_op_is_transout
            && (transout_initial[0]
                || transout_initial[1])));
```

只要 `transout_initial` 任一 bit 为1，即使 input2 无效也可以 matched。

阶段终止条件：

```verilog
assign end_transout_initial =
    alu_is_fp32
        ? (transout_initial == 2'b11)
        : (alu_is_int32
            ? (transout_initial >= 2'b10)
            : (transout_initial >= 2'b01));
```

DataC 选择：

```verilog
assign ga_pe_alu_input_data[2] =
    !alu_op_is_transout
        ? ga_pe_inbuffer_data[2]
    : !alu_is_int8
      && transout_initial==2'b00
        ? ga_pe_inbuffer_data[2]
    : ga_pe_transout_calculate
        ? (...)
    : !end_transout_initial
        ? 0
    : ga_pe_outbuffer2alu_data;
```

最后一支没有同时检查：

```text
ga_pe_outbuffer2alu_valid_bit
```

## 4. 正确计算语义

每个新的 reduction block 必须从明确定义的初始状态开始：

```text
尚无本 block partial sum
→ DataC = 0
```

只有当前 block 已经产生有效 partial 并写入 outbuffer 后，才允许：

```text
DataC = current_block_partial
```

阶段计数只能描述控制进度，不能代替数据有效性证明。feedback 授权至少需要同时满足：

```text
phase_requires_feedback
&& outbuffer_slot_valid
&& slot_belongs_to_current_block
```

## 5. ResNet50 中必须使用该功能的计算

Global Average Pooling 的49项求和必须分多个 reduction block 执行。典型过程：

```text
block0: values 0...k
block1: values k+1...m
...
final : 49-value sum
```

每个 block 都需要明确区分：

- 本 block 尚未产生 partial；
- 本 block 已有可反馈 partial；
- 上一 block 已经结束。

如果跨 block 初始化错误，每个通道从第二个 block 开始都可能携带上一 block 的残留状态。

## 6. 最小错误案例

假设 block0 完成后：

```text
old outbuffer data = 100
old slot valid     = 0
transout_initial   = 2
```

block1 第一个输入：

```text
new input          = 7
current block 尚无 partial
```

正确初始化：

```text
DataC  = 0
result = 7
```

当前控制路径可能得到：

```text
matched = 1
end_transout_initial = 1
DataC  = old outbuffer data = 100
result = 107
```

此后 block1 的所有累加都建立在错误初始值上。

## 7. 对网络结果的影响

该错误会导致：

- 第一个 reduction block 可能正确；
- 第二个及后续 block 出现固定或历史相关偏移；
- 不同 stall 时序可能选择不同旧槽；
- 每个通道的 GAP sum 被污染；
- 后续除以49和 UINT8 量化无法消除错误。

这是 block 生命周期错误，不只是单个 data bit 错误。

## 8. 修复验收条件

最低验收应包含：

1. 每个新 block 第一次运算必须使用 `DataC=0`；
2. 只有本 block 的 valid partial 可反馈；
3. `transout_initial` 不能单独授权 feedback；
4. 上一 block slot 即使保留非零 data 也不能参与；
5. block 边界处随机 stall；
6. outbuffer 两槽交替及指针 wrap；
7. 连续多个通道和多个49项归约；
8. 断言 feedback 的 tag/valid/block identity 一致。

该问题应与 occupancy 下溢和 invalid-slot stale data 分别修复、分别验收。

