# GAP transout outbuffer occupancy 发生无符号下溢

## 1. 问题概述

General Array transout 在压缩 intermediate partial sums 时，会从 outbuffer occupancy
固定减去1、2或3，但没有先证明当前实际存在足够多的有效项。outbuffer 深度为2时，
`count=1` 仍可能执行 `count-2`，无符号计数器回绕成3。

非法 occupancy 会破坏 empty/full、读写指针和后续 feedback 判断。

## 2. RTL 文件与信号路径

云端仓库相对路径：

```text
code/NDP_rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv
```

关键位置：

```text
GA_PE_Outbuffer.sv:284-321
```

信号链：

```text
transout calculate phase
→ write/read pointer update
→ ga_pe_outbuffer_count update
→ empty/full
→ later read/feedback control
```

## 3. 当前错误代码

```verilog
else if (
    ga_pe_transout_calculate &&
    (transout_calculate_cnt==3'b010 ||
     transout_calculate_cnt==3'b101)
) begin
    if (
        ga_pe_outbuffer_cnt_wr_update &&
        ga_pe_outbuffer_cnt_rd_update
    ) begin
        ga_pe_outbuffer_count <=
            ga_pe_outbuffer_count - 2;
    end
    else if (ga_pe_outbuffer_cnt_wr_update) begin
        ga_pe_outbuffer_count <=
            ga_pe_outbuffer_count - 1;
    end
    else if (ga_pe_outbuffer_cnt_rd_update) begin
        ga_pe_outbuffer_count <=
            ga_pe_outbuffer_count - 3;
    end
    else begin
        ga_pe_outbuffer_count <=
            ga_pe_outbuffer_count - 2;
    end
end
```

这些固定减法没有根据 valid tag 数量计算实际移除项数，也没有检查：

```text
count >= remove_count
```

## 4. 正确计算语义

任意周期必须保持：

```text
0 <= occupancy <= OUTBUFFER_DEPTH
```

状态更新应由真实 handshake 和真实有效项变化决定：

```text
next_count =
    current_count
    + accepted_writes
    - actually_removed_valid_items
```

禁止根据 transout phase 固定扣除超过当前 occupancy 的数量。

## 5. ResNet50 中必须使用该功能的计算

Global Average Pooling 需要对每个通道的7×7空间区域求和：

```text
49 values/channel
```

原生 `int32_sum/transout` 路径会把输入分成多个 partial sum block，再通过 outbuffer
feedback 继续归约。一个通道的49项远大于 outbuffer depth，因此必须反复执行：

```text
写入 partial
→ 读取 partial
→ 压缩
→ 更新 occupancy
→ 继续下一 block
```

只要 occupancy 更新错误，第二个及后续 block 的求和状态就不可信。

## 6. 最小错误案例

设：

```text
OUTBUFFER_DEPTH = 2
current_count   = 1
accepted_write  = 0
calculate phase 固定移除2项
```

正确行为：

```text
不能移除2项；
应只移除真实存在的有效项，或等待所需输入。
```

当前无符号运算：

```text
1 - 2 → 3
```

于是出现：

```text
count=3 > OUTBUFFER_DEPTH=2
```

动态观测中该路径曾出现8次 underflow transition，首个可见转换即 `1→3`。

## 7. 对网络结果的影响

非法 occupancy 会导致：

- empty/full 判断错误；
- 读取尚未有效的槽；
- 写入覆盖未消费的数据；
- 指针与有效 tag 不一致；
- 上一个 reduction block 的数据污染下一个 block；
- GAP 输出从后续 block 开始错误。

该错误可能进一步触发 stale-C，但 occupancy 下溢本身就是独立协议错误。

## 8. 修复验收条件

最低验收应包含：

1. 形式或断言保证 `0<=count<=DEPTH`；
2. 所有读写 handshake 组合；
3. count 为0、1、2时的所有 transout phase；
4. 实际 valid tag 数与 count 始终一致；
5. compaction 只能移除有效项；
6. 49项求和跨多个 block；
7. 随机 backpressure；
8. 修复后不得再通过回绕掩盖非法状态。

