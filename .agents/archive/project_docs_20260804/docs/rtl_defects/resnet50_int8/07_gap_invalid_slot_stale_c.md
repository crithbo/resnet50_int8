# GAP 无效 outbuffer 槽的数据被继续作为 DataC 使用

## 1. 问题概述

General Array outbuffer 在消费数据时只清除 tag，不清除 data。保留 data 本身可以是合法
实现，但读取端必须使用 valid/tag 做隔离。当前 transout feedback 路径在 slot 无效时仍
直接把旧 data 送入 ALU 的 `DataC`，导致前一 reduction block 的 partial sum 被重复使用。

## 2. RTL 文件与信号路径

云端仓库相对路径：

```text
code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv
code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv
```

关键位置：

```text
GA_PE_Outbuffer.sv:247-282
GA_PE_Inbuffer.sv:257-267
```

信号链：

```text
outbuffer tag clear
→ outbuffer data remains
→ rd_ptr selects old data
→ ga_pe_outbuffer2alu_data
→ ga_pe_alu_input_data[2]
→ DataC
```

## 3. 当前错误代码

`GA_PE_Outbuffer.sv` 清除 tag：

```verilog
if (ga_pe_outbuffer_rd_en) begin
    ga_pe_outbuffer_tag[
        ga_pe_outbuffer_rd_ptr
    ] <= 'b0;
end
```

data 只在写入时更新，不随 tag 清除：

```verilog
always @(posedge clk) begin
    if (ga_pe_outbuffer_wr_en) begin
        ga_pe_outbuffer_data[
            ga_pe_outbuffer_wr_ptr
        ] <= ga_pe_outbuffer_wr_data;
    end
end
```

读取端始终返回选中 data：

```verilog
assign ga_pe_outbuffer_rd_tag =
    ga_pe_outbuffer_tag[ga_pe_outbuffer_rd_ptr];

assign ga_pe_outbuffer_rd_data =
    ga_pe_outbuffer_data[ga_pe_outbuffer_rd_ptr];
```

`GA_PE_Inbuffer.sv` 的 feedback 末级直接使用：

```verilog
ga_pe_outbuffer2alu_data;
```

源码中保留的注释已经显示原本需要 valid guard：

```verilog
// ga_pe_outbuffer2alu_valid_bit
//     ? ga_pe_outbuffer2alu_data
//     : 0
```

但活动表达式没有这个判断。

## 4. 正确计算语义

无效槽的 data 可以不物理清零，但它在任何情况下都不能影响：

- ALU operand；
- ALU tag；
- partial-sum feedback；
- 当前 reduction block 的计算结果。

语义必须满足：

```text
slot_valid == 0
→ selected_DataC == 0
  或本次运算必须等待有效 feedback
```

具体选择“送0”还是“暂停”应依据 transout 状态机所需阶段决定。

## 5. ResNet50 中必须使用该功能的计算

Global Average Pooling 对每个通道求49项和。由于 outbuffer 很浅，partial sums 会被多次
写入、读取、失效并复用槽位。

正常执行必然包含：

```text
block0 partial 写入 slot
→ block0 partial 被读取
→ slot tag 清除
→ 同一物理 slot 后续被其他 block 使用
```

因此 slot invalid 后的隔离不是异常保护，而是 GAP 多 block 归约必须具备的基本功能。

## 6. 最小错误案例

预置：

```text
slot.data  = 0x000000a6   // 166
slot.valid = 0
rd_ptr     = 该 slot
```

当前路径：

```text
ga_pe_outbuffer2alu_valid_bit = 0
ga_pe_outbuffer2alu_data      = 166
ga_pe_alu_input_data[2]       = 166
```

若当前新 partial 为7：

```text
expected = 7 + 0   = 7
RTL      = 7 + 166 = 173
```

实际动态观测曾记录217次 invalid-slot DataC reuse。

## 7. 对网络结果的影响

该错误会使前一个 reduction block 的值重复加入后续 block。误差取决于历史数据，具有：

- 输入相关性；
- 时序和 stall 相关性；
- block 边界相关性；
- 非确定性外观。

即使第一个 GAP block 正确，第二个及后续 block 仍可能被历史 partial 污染。

## 8. 修复验收条件

最低验收应包含：

1. tag clear 后 data 保留的情况下，invalid slot 绝不影响 ALU；
2. `valid=0` 时分别验证送0和等待策略；
3. tag/data 同拍读写冲突；
4. 两个物理 slot 交替复用；
5. 多 reduction block；
6. 随机 stall 与指针切换；
7. 断言 `invalid slot cannot drive a valid DataC/tag`；
8. 完整49项 GAP 求和。

仅把 data 数组清零可能掩盖问题；仍应修复 valid gating，防止其他未知值传播。

