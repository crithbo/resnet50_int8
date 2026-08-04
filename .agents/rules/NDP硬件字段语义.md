# NDP 硬件字段语义

最后更新：2026-07-30

本文件保存从 encoder/RTL/授权配置得到的稳定字段语义。它是
`算子配置规则.md` 的条件附录：只需完整阅读本轮实际触发的章节；跨单元 schedule 必须
同时阅读所有相关章节。规则状态和具体算子 blocker 仍看专项规则、机器合同与当前计划。

## 1. DRAM LC

1. `dram_loop_configs.LC*.src_id` 是 trigger/tag/backpressure 的逻辑连接，不传递
   numeric data。mapper 将其转换为目标 LC 的 4-bit 相对输入选择码。
2. LC 配置为 60 bit：
   `src_id[59:56]`、`outmost_loop[55]`、`start[54:38]`、
   `stride[37:21]`、`end[20:4]`、`last_index[3:0]`。register spreadsheet 中三个
   17-bit 值的旧 13-bit 图示不得作为 packing 依据。
3. `outmost_loop=1` 由 `slice_start_run` 触发，`src_id` 不参与触发；非 outmost LC
   从所选源取得 `valid/last/same/last_index`。`start/end/stride` 始终定义本 LC
   本地计数域。
4. RTL 以 signed 17-bit 计算 `previous+stride` 和 `next>=end-stride`，对外 data
   截断为 16 bit。批准生成子集要求正 stride、`start<end`。
5. 上游未宣告 last 时输出本地 `last_index`；上游 last 时继承上游 index。上游
   `same` 抑制重复摄取，输出 `same` 用于下游停顿重放。terminal validator 可沿
   trigger/tag 图追踪 last，不得沿该图推断数值。
6. `last_index` 是循环终止/tag 层级，不是 LC 编号、连线跳数或 LC_PE 深度。插入
   恒等 LC_PE fanout 不增加循环层级。必须先从目标 LC 的父子循环与 terminal
   occurrence 反解该值；参考 JSON 的同名字段只能交叉检查，禁止因值不同直接判风险
   或照抄。
7. `CDA-IGA-LC-SIGNED-FEEDBACK-END-BOUND-001`：当前 DRAM LC recurrence 的对外
   feedback data 只有 16 bit，下一轮又按 signed 值解释。因此批准生成子集中的正
   stride LC 必须满足 `end<=32768`；配置字段本身为 17 bit 不构成更大 `end` 的
   放行依据。`end>32768` 会使计数在到达 32768 后以 `-32768` 反馈，可能永远无法
   到达正数 terminal threshold。冻结反例为 QLinearAdd node0007 的
   `start=0,stride=1,end=37632`：反馈回绕后无法到达 37631，LC last、write
   terminal 与 slice completion 均不可达。
8. 逻辑 occurrence 超过上述直接计数域时，必须拆成嵌套 LC 或 tile；不得仅延长
   watchdog。拆分后须从空 mapping state 重建，并对最终 JSON 的 occurrence、
   address/order、coverage、terminal、barrier/lifetime 以及
   mapping→bitstream→execplan/SCA 全链重新证明。
9. LC 拆分产生的每个 stream `dim_stride` 必须重新按 unsigned 20-bit 字段验证，
   即 `0<=dim_stride<=1048575`；循环因子合法不代表派生地址步长合法。冻结反例为
   QLinearAdd node0007 dequant 的 `2×18816`：write outer stride
   `18816×64=1204224` 超界；合法修正为 `4×9408`，write outer stride
   `9408×64=602112`。不得截断、回卷或依赖 encoder 低位保留。

## 2. LC_PE

1. 每个 LC_PE 为 96 bit、两个 48-bit beat。第一拍含 16-bit reserved 和
   `opcode/src_id/keep_last_index/mode`；第二拍为 `constant2/1/0` 三个 16-bit lane。
2. `src_id` 是 4-bit 物理选择：LC 邻居 0～5、LC_PE 邻居 6～9。不可达逻辑边必须
   失败，禁止 encoder fallback 0。
3. mode：`null=00`、`buffer=01`、`keep=10`、`constant=11`。enabled port 全 valid
   才运算。strict target 必须恰有一个 buffer terminal carrier；输出 tag 只来自它。
4. keep 在 `buffer_last && buffer_last_index<=keep_last_index` 时释放；比较 inclusive。
   keep 自身 tag 不成为输出 tag。非 keep 端口不得携带 keep threshold，constant
   端口不得携带 `src_id`。
5. 方程为：
   `add=low16(s16(p0)+s16(p1))`、
   `mul=low16(s16(p0)*s16(p1))`、
   `mac=low16(s16(p0)*s16(p1)+s16(p2))`。乘法 carry 丢弃。
6. add/mul 必须启用 port0/1 且 port2=null；mac 必须启用三端。被 opcode 忽略但
   enabled 的端口仍参与 matching/backpressure。
7. constant 只批准 signed int16 十进制或 `0x0000..0xffff` bit pattern。浮点字面量
   被取 FP32 编码低 16 bit，不代表 LC_PE 浮点运算，必须拒绝。

## 3. Memory Stream / MSE

1. read stream 为 580 bit（10×58），write stream 为 496 bit（8×62）。向量按 JSON
   列表从高到低打包；JSON `[dim0,dim1,dim2]` 对应 RTL `[port2,port1,port0]`。
   Buffer AG 的 JSON `[row,col]` 对应 RTL `[port1,port0]`。
2. memory index mode：`null=00`、`buffer=01`、`keep=10`、`constant=11`。
   null=0 且 always-valid；buffer 每次消费；keep 的释放比较 inclusive；constant
   将 8-bit pattern 符号扩展为 16 bit，但后续地址乘法按 `u16` 使用。
3. memory index 三端必须恰有一个 buffer terminal carrier；buffer/keep 必须有 source，
   null/constant 不得有 source。Buffer AG 只允许 buffer/keep，row/col 必须恰有
   一个 buffer 和一个 keep。
4. Memory AG tag owner 优先 port0→1→2；Buffer AG 优先 col→row。strict target 的
   “恰一个 buffer”用于消除歧义。
5. 地址方程：

   ```text
   B = low30(sum(u16(idx[i]) * u20(dim_stride[i])))
   T = low30(B + transfer_bias)
   U = T[29:4]
   R[o] = U[address_remapping[o]]
   request = low26(R + base_addr[29:4])
   ```

   remap 作用于 transaction bias，base 在其后相加；base 必须 16-byte 对齐。
   null remap 是 identity，显式 remap 必须是 0～25 的置换。
6. `idx_size[j]` 编码事务维度 `S[j]-1`，不是 loop 范围；null 表示 `S=1`。每个 S
   必须是 2 的幂，总 transaction size 必须落在非零 8-bit 域。
7. transaction 按 16-byte DDR line 切分：
   `position=B[3:0]`、`try_size=16-position/16`、
   `final_size=min(remaining,try_size)`，
   `valid_mask=low16(((1<<final_size)-1)<<position)`。
8. write 的 partial 或 tail line 必须先读旧 line 再同址 merge write；只覆盖
   `valid_mask & ~tail_mask`。
9. RD/WR request outbuffer 对外 `valid=vld_d||vld`，且 `vld_d` 无显式 reset。
   first/stall/resume 下 delayed-only valid 是否被再次接受必须用周期证据裁决，禁止用
   JSON 地址补偿。

## 4. Padding / Tailing

1. read padding 含 value、3-bit enable 和三组 inclusive bounds；read/write tailing
   含 3-bit enable 和三组 inclusive bounds。write 没有 padding 位。
2. conceptual lane `l` 令 `q=transfer_bias+l`：

   ```text
   idx0=low16(base0+(q&(S0-1)))
   idx1=low16(base1+((q>>log2(S0))&(S1-1)))
   idx2=low16(base2+((q>>log2(S0*S1))&(S2-1)))
   ```

   enabled 维在 `idx<low || idx>up` 时越界；bounds 为 zero-extended 12 bit。
3. conceptual mask 再按 line 起点左移为 physical mask；它与 line split 的 valid mask
   独立。
4. read 数据优先级为 `padding value > tail zero > DDR`；有效 physical lane 按
   `popcount(valid_mask[0:i])` 压紧。padding/tail 是替换值，不删除输出，也不抑制
   DDR read。
5. write tail lane 从旧 DDR line 合并；完全 tail 的 line 仍执行 read-modify-write。
6. strict target 的 padding value 必须由哈希绑定的算子 padding contract 显式给出。
   tailing 当前只有 RTL 方程证据，必须保留动态边界门。

## 5. Buffer AG / Buffer Manager

1. `buf_spatial_size=N` 启用低 N 个 lane；RTL 中
   `stride_rtl[i]=stride_json[i]`。地址为
   `row_i=row`、`col_i=low5(col+stride[i])`，col 模 32 回绕而不向 row 进位。
2. `bank=col[4:2]`、`byte=col[1:0]`、`strobe=1<<byte`。同 bank strobe OR 合并；
   strict target 要求有效 stride 不重复，除非有精确 alias 合同。
3. 固定物理拓扑：
   A/READ_STREAM0→buffer0（仅它可 ping-pong 到 buffer1）；
   B/READ_STREAM1→buffer2；B′/READ_STREAM2→buffer3；
   C/READ_STREAM3→buffer4；WRITE_STREAM0←buffer5。
   B/B′/C read 和 write stream 的第二选择不得启用 ping-pong。
4. ping-pong 初值为 slot0，在已接受的
   `last && last_index<=pingpong_last_index` 后切换；比较 inclusive。write data 选择
   比 request 选择晚一拍以配合同步 Buffer。
5. read stream 与映射 buffer 的 `buf_full_last_index` 是两条独立通知，strict target
   要求相等。
6. Buffer 配置为 26 bit：
   `buf_src_id[25]`、`buf_full_last_index[24:21]`、
   `buffer_nbr_cnt[20:16]`、`nbr_enable[15]`、
   `life_time_minus_1[14:11]`、`mode[10]`、`mask[9:2]`、
   `end_row[1:0]`。对象存在即 enable；lifetime 合法域 1～16。
7. buffer0～4 的 MSE 方向为写、Array 方向为读；buffer5 相反。MSE 写等待目标 byte
   invalid，MSE 读等待 valid，接受后只清本次 strobe。`mask` 是 Array/N2N active bank，
   不是 stream spatial mask。
8. JSON `dst_port` 实际连接 `buf_src_id`，只对 buffer5 选择 0=SA、1=GA；对 buffer0～4
   不选择消费端，SA/GA backpressure 取 AND。
9. Array Request Manager：
   mode0=`for life: for row`；mode1=`for row: for life`。buffer0～4 在最后 life 的
   accepted read 后到期；neighbor 模式还需本地/partner 完成协同。

## 6. Specialized Array

1. SA 配置为 32 bit：
   `mode[31]`、三个 7-bit inport、`dtype[9:8]`、`transout[7:4]`、
   `bias[3]`、`major[2]`、两 conversion bit。dtype 只允许 int8=00、fp16=10、
   bf16=11；01 必须拒绝。
2. gemm 启用 8×8；gemv 只启用 row0 的 1×8。inport0 来自 buffer0/1，inport1
   来自 buffer2/3，inport2 来自 buffer4/zero。inport2 不得 ping-pong。
3. inport ping-pong 的切换比较 inclusive；source0 last 会被隐藏，source1 last
   才传播，`nbr_enable` 还会清 last，必须由 N2N completion 补边界。
4. SA 以 inport0/1 配对启动。`bias=0` 时 initial port=0；`bias=1` 时必须启用
   buffer4，四拍填 16 accumulator slot。bias 与 inport2 必须一致。
5. transout 是 loop-depth 比较：`i>T` 继续；`i=T` matched、切 bank 但不传播 last；
   `i<T` 输出 last。双输入同时 last 时 inport0 index 优先。
6. 当前 INT8 算术存在固定反例：
   `psum + signext32(sum17) + (signext32(carry17)<<1)`；
   四个 `1×1` 得 6 而非 4，四个 `(-1)×1` 得 -6 而非 -4。
   `CDA-SA-INT8-CSA-001=CONTRADICTED`，不得批准普通 INT8 dot。
7. legacy `col` 编 major0 且不转置；`row` 编 major1 且转置。不能按标签字面猜。
8. FP16/BF16 narrowing 的 subnormal 和 exact-half exponent carry 存在反例，
   `CDA-SA-FP-CONVERT-001=CONTRADICTED`；不得声明完整 IEEE narrowing。

## 7. General Array

1. GA inport 为 20 bit、outport 12 bit；每个 PE 为 144 bit、四个 36-bit beat。
2. PE 为 4×4 三输入。外部 inport 编号为 `row+4*floor(col/2)`；其余 selector 是邻接
   PE。SFU 只位于奇数列，错误放置以 `GA.SFU_PLACEMENT` 拒绝。
3. 方程：
   `add=A+B`、`sub=A-B`、`mul=A*B`、`max=max_fp32(A,C)`、
   `sum=A+C`、`summac/mac/int32_mac=A*B+C`、
   `int32_sum=A+C`、`int32_sub=A-B`。
4. `max/sum/summac/int8_max/int32_sum` 进入 transout；未被算术使用但 enabled 的端口
   仍参与 matching/backpressure。
5. 普通输出 last 为 `buffer_last && index<T`；reduction flush 为
   `buffer_last && index<=T`。flush 调度：FP32/SFU 8 拍、INT32 4 拍、INT8 1 拍。
6. port mode：null0、buffer1、keep2、constant3。keep 比较 inclusive；constant
   不请求上游。GA inport `src_id=1` 只有单一 SA source，不得开 ping-pong。
7. FP16/BF16 低半先出，UINT8 byte0→byte3，仅末项带 last。conversion flag 在 strict
   JSON 中必须互斥。
8. INT32→FP32 有固定反例：
   `-1→0xcf000000`、`INT_MIN→0xce800000`，
   `CDA-GA-INPORT-CONVERT-001=CONTRADICTED`。
9. 当前活动源码身份下，`int8_max` 的完整
   `GA_PE_ALU→GA_ALU→GA_PE_Float_CSA→GA_PE_Float_Last` 聚焦测试按 byte
   选择 unsigned max；旧“实际 lane 极性为 min”结论已被源码绑定反例翻案，
   `CDA-GA-INT8-MAX-NUMERIC-001=LOCAL_SOURCE_PASS`。但 pipeline0 ready 方程仅含
   INT32/FP32、缺少 INT8 分支：首个 INT8 token 占住 pipeline0 后不能 clear/overwrite，
   第二个 token 只能停在 inbuffer，随后输入被反压；
   `CDA-GA-INT8-MAX-PIPE-001=CONTRADICTED`。
10. 上一项与 GAP `int32_sum` 的 occupancy underflow/stale-C
    `CDA-GAP-GA-ACCUM-STATE-001` 正交。规避候选必须检查实际 opcode、conversion 和
    transout，不能只看 tensor dtype。
11. `int32_mac` opcode14 是 non-transout；只有最终物化 JSON 的 A/B/C producer、
    matching、tag、normal FIFO 和 writeback 全部证明后，才能声明绕过 transout 缺陷。

## 8. N2N

1. 每个 neighbor stream 为 8 bit：
   `src_sel[7]、dst_sel[6]、ping_pong[5]、nse_cnt_size[4:0]=mem_loop-1`。
   stream0 固定 buffer0/1，stream1 固定 buffer2/3。
2. selector0 是 28-slice low ring，selector1 是七条 4-slice high ring；全环端点必须
   兼容，具体映射由 `CDA-N2N-ROUTE-TRANSFER-001` 合同决定。
3. `mem_loop=L` 实际执行 `L-1` 次四行完整传输；不是 alias/zero-copy。
4. 发送/接收 buffer 每次四行完成后无条件交替。RTL 的 ping-pong enable 未连接，
   strict target 在启用 N2N 时只接受 `ping_pong=1`。
5. 物理 buffer pair 必须都存在、neighbor enabled、`end_row=3` 且配置一致。
6. incoming/outgoing controller 独立计数；`nse_enable` 不自动清除。跨 stage 复用必须
   证明 reset、slice reset、configure clear 或明确 reconfigure 边界。
7. 未有授权样例的 stream1、mixed selector 和新拓扑必须保留独立动态证明。

## 9. 跨单元覆盖门

1. 从 typed output shape/dtype 求每 active slice 输出字节数，再以 write transaction
   size 求所需 transaction 数；可证明的不同 base 数不得少于需求。
2. 最终物化 JSON 必须反解回 occurrence 合同，逐项验证：
   transaction bytes、loop 数值域、stream 地址顺序、buffer spatial bank/byte、
   producer/consumer 数量、tag/last、lifetime 和 write visibility。
3. read 供给字节数、Buffer AG 请求字节数和 Array 消费 occurrence 必须相等；结构
   validator、公式模型或请求总数不能替代该守恒检查。
4. 共享 LC 会把所有下游 ready 以 AND 反馈；多个 read/write 分支共享 root 时，必须
   提供无环和进度证明，否则使用已授权模板的独立 branch roots。
5. 大规模地址报告可以压缩，但 validator 必须完整枚举并保存 multiplicity、唯一地址数、
   有序哈希及边界样本，不能抽样放行。
6. 动态失败先按首分歧裁决。若已证明“上游输入完成、下游首个数据未产生”，不得用发生
   在更晚阶段的参考字段差异稀释首因；次级风险也必须有目标自身的 occurrence/tag/
   lifetime 推导，不能仅凭可信参考不同而成立。
