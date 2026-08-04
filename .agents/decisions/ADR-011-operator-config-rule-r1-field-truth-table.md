# ADR-011：算子配置规则分支 R1 字段真值表草案

日期：2026-07-22

状态：draft-0.2；R1 静态真值核对已闭合，仍有明确列出的 E4/E5 动态阻塞项。本文件不是活动规则；R2/R3 只能把已裁决项设为强制条件，对阻塞项必须 fail closed。

依赖：ADR-010。当前目标 profile 按用户确认暂视为服务器与本地 NDP_copy01 一致，服务器侧 SHA 尚未机械核验。

## 1. 真值来源顺序

1. 当前目标 profile 的活动 RTL consumer、配置寄存器和真实数据通路。
2. 活动 ndp-sim encoder/model_execplan 实际读取和编码的字段。
3. 当前 JSON、mapping、bitstream 和服务器回读实证。
4. register CSV、expanded RTL、README、注释和历史样例只能辅助解释；与前三项冲突时不作真值。

每个字段必须最终闭合为：JSON 路径 → 原始类型/单位 → mapper/派生 → bit range/分块 → RTL register → 数据通路作用 → 正/负样例。当前只完成其中可由活动源码直接证明的部分。

## 2. 当前目标 profile

| 资源 | 当前值 | 本地 RTL 来源 | 规则状态 |
|---|---:|---|---|
| slices | 28 | GLB_SLICE_NUM/SLICE_NUM | provisional required |
| banks per slice | 4 | BANK_NUM_PER_SLICE | provisional required |
| DDR columns | 64 | DDR_COL_SIZE | provisional required |
| DDR rows | 6144 | DDR_ROW_SIZE | required；planner 的 8192 不得放宽此上限 |
| read buffers | 5 | RD_BUFFER_NUM | required |
| write buffers | 1 | WR_BUFFER_NUM | required |
| memory read streams | 4 | MEMORY_RD_STREAM_ENGINE_NUM | required |
| memory write streams | 1 | MEMORY_WR_STREAM_ENGINE_NUM | required |
| neighbor streams | 2 | NEIGHBOR_STREAM_ENGINE_NUM | required |
| SA | 8x8 | SA_ROW_PE_NUM/SA_COL_PE_NUM | required |
| GA | 4x4 | GA_ROW_PE_NUM/GA_COL_PE_NUM | required |

## 3. 模块数量与聚合位宽

下表由活动 encoder FIELD_MAP 求和，并与本地 RTL port width/count 宏对照。聚合位宽一致只证明装载长度相容，不证明字段顺序和语义正确。

| JSON 模块 | 物理数量 | encoder 类 | 单实例编码位数 | RTL 对照 | 初判 |
|---|---:|---|---:|---|---|
| root CONFIG | 1 | parse mask | 8 | Slice_Config_Manager PARSE_INIT=8 | 一致 |
| dram_loop_configs | 20 | DramLoopControlConfig | 60 | IGA_LC_CFG_PORT_WIDTH=60 | 一致 |
| buffer_loop_configs ROW_LC | 5 | BufferRowLCConfig | 17 | IGA_ROW_LC_CFG_PORT_WIDTH=17 | 一致 |
| buffer_loop_configs COL_LC | 5 | BufferColLCConfig | 26 | IGA_COL_LC_CFG_PORT_WIDTH=26 | 一致 |
| lc_pe_configs | 10 | LCPEConfig | 96 | IGA_PE 2 chunks x 48 | 一致；常数/配置分块顺序仍需逐 bit 核对 |
| stream_engine read | 4 | ReadStreamEngineConfig | 580 | SE_RD_MSE 10 chunks x 58 | 一致 |
| stream_engine write | 1 | WriteStreamEngineConfig | 496 | SE_WR_MSE 8 chunks x 62 | 一致 |
| n2n | 2 | NeighborStreamConfig | 8 | SE_NSE 1 chunk x 8 | 一致 |
| buffer_config | 6 | BufferConfig | 26 | BMC_CFG_PORT_WIDTH=26 | 与 live RTL 一致；expanded RTL 的 21 为过时快照 |
| special_array | 1 | Mode+3 Inport+PE+Outport | 32 | SA_CFG_PORT_WIDTH=32 | 与 live RTL 一致；encoder 注释的 24 为过时说明 |
| general_array inport | 3 | GAInportConfig | 20 | GA_INPORT_CFG_PORT_WIDTH=20 | 一致 |
| general_array outport | 1 | GAOutportConfig | 12 | GA_OUTPORT_CFG_PORT_WIDTH=12 | 一致 |
| general_array PE | 16 | GAPEConfig | 144 | GA_PE 4 chunks x 36 | 一致 |

## 4. CONFIG 八位状态语义

位序按配置字符串从左到右对应 bit7..bit0：

| bit | 字段 | PARSE_INIT 行为 | clear 条件 | 当前规则要求 |
|---:|---|---|---|---|
| 7 | IGA enable/use | 1 表示本 stage 使用 IGA | !enable 或 update | 必须由 stage DAG 显式给出 |
| 6 | LSU enable/use | 1 表示本 stage 使用 stream/buffer/n2n | !enable 或 update | 必须由 stage DAG 显式给出 |
| 5 | SA enable/use | 1 表示本 stage 使用 SA | !enable 或 update | 必须由 stage DAG 显式给出 |
| 4 | GA enable/use | 1 表示本 stage 使用 GA | !enable 或 update | 必须由 stage DAG 显式给出 |
| 3 | IGA update | 1 时清除并重载 | !enable 或 update | 不得仅由模块是否存在推断 |
| 2 | LSU update | 1 时清除并重载 | !enable 或 update | 同上 |
| 1 | SA update | 1 时清除并重载 | !enable 或 update | 同上 |
| 0 | GA update | 1 时清除并重载 | !enable 或 update | 同上 |

结论：enable=1/update=0 会保留上一 stage 配置；enable=0 会清除；enable=1/update=1 会清除并重载。单 JSON 静态检查不足以证明多 stage 正确，R3 必须按 execplan 顺序模拟状态。

## 5. 固定 stream→buffer→array 拓扑

活动 encoder 按 stream target 固定映射；本地 BMC RTL 再按 buffer index 固定连接到 array 端口：

| 逻辑 target | 物理 stream | 写入/读取 buffer | array 侧角色 | 初始语义 |
|---|---|---|---|---|
| A | READ_STREAM0 | buffer0/buffer1，stream 自选 ping-pong 半区 | SA/GA inport group0 | SA DataA；INT8 路径按 signed A |
| B | READ_STREAM1 | buffer2 | SA/GA inport group1 half0 | SA DataB；INT8 路径按 unsigned B |
| B-prime | READ_STREAM2 | buffer3 | SA/GA inport group1 half1 | B 的第二 ping-pong 生产者 |
| C | READ_STREAM3 | buffer4 | SA/GA inport group2 half0 | SA inport2/bias |
| D | WRITE_STREAM0 | 从 buffer5 读出 | array outport group0 写 buffer5 | 外部结果写回 |

强制不变量草案：read mode 只能使用 A/B/B-prime/C 且 target 唯一；write mode 必须使用 D；启用 SA inport1 ping-pong 时 buffer2 和 buffer3 都必须有可达生产者；任何启用 buffer 都必须有唯一生产者、至少一个消费者和闭合的 last/completion 关系。该不变量解释旧四 stream Conv 的结构风险，但不把它宣称为 v19 唯一根因。

## 6. SA 已核对语义

| JSON 字段 | encoder | 本地 RTL | 状态 |
|---|---|---|---|
| special_array.mode | gemm→0，其他→1 | SA mode 1 bit | gemv 非字符串/非法字符串当前会被归 1，R3 必须限定 enum |
| special_array.inport0 | enable/pingpong/last/nbr 共 7 bit | sa_pe_alu_inport[0] | DataA |
| special_array.inport1 | 同上 | sa_pe_alu_inport[1] | DataB |
| special_array.inport2 | 同上 | bias_enable ? inport2 : 0 | bias/C |
| special_array.data_type | int8=0, fp16=2, bf16=3 | SA datatype 宏一致 | 已核对枚举 |
| special_array.outport.mode | col→0，row→1 | RTL 宏 row-major=0，col-major=1；`SA_Outport_Connect` 中 bit=0 不转置，bit=1 交换两级索引 | SA-001 已确认为 JSON label/encoder 映射与 RTL 物理位语义相反；现有配置仍禁止未经数值裁决就批量翻转 |
| fp32tofp16/fp32tobf16 | 各 1 bit | SA outport conversion | 互斥关系尚未写入 encoder，R3 应拒绝同时为 1 |

INT8 SA 数据路由已由 RTL 证明：DataA 每个 byte 按符号位取绝对值并保留 sign，DataB byte 不取符号。因此 Conv 权重放 A、UINT8 activation 放 B 在端口 signedness 层面成立；这仍不证明循环、布局、部分和与 requant 正确。

SA-001 的剩余问题已不是“这一 bit 在 RTL 中什么意思”，而是现有生成器是否用反向 label 有意补偿了 D 的逻辑布局。R2 需用非对称矩阵同时记录 JSON label、encoded bit、RTL 转置行为和 D physical layout；在此之前对旧配置保持字节级复现。新 schema 应改用 `physical_transpose`/`encoded_major_bit` 这类无歧义字段，而不再让 `row`/`col` 直接决定 bit。

## 7. GA 已核对语义

| 类别 | JSON/encoder | RTL | 状态 |
|---|---|---|---|
| GA opcode | add0/sub1/mul2/max3/sum4/summac5/mac6/int8_max11/int32_sum12/int32_sub13/int32_mac14/rec17/sqrt18/rec_sqrt20/sfu_activation24 | NDP_Parameters opcode 宏与 GA_PE_ALU decode | 已核对列出的活动 opcode |
| inport mode | null0/buffer1/keep2/constant3 | GA inport mux | 已核对 enum；未知字符串当前 get(...,0) 会降为 null，R3 必须拒绝 |
| uint8→int32 | 4 个 byte 逐个零扩展 | GA_Inport | 是数据类型转换，不包含 zero-point 减法 |
| uint8→fp32 | 无符号数值转换 | GA_Inport | 不包含 scale/zero-point |
| int32→uint8 | 负数钳 0，超过 255 钳 255，否则低 8 bit | GA_Outport | 只做饱和，不做 scale/round/zero-point |
| int8_max opcode | 实际对四个 uint8 lane 比较并选大值 | GA_PE_Float_CSA | 当前 MaxPool 基本算术原语成立 |

由此得到 QNT-001：Quantize/QLinearAdd/GAP/Conv requant 不能只依赖 conversion flag，必须在 GA/SA/LC stage 中显式完成 scale、zero-point、rounding 和 saturation，并绑定模型 qparam。

## 8. 字段编码与严格校验草案

| 类别 | 活动 encoder 行为 | R3 fail-closed 要求 |
|---|---|---|
| 未知字段 | BaseConfigModule 只遍历 FIELD_MAP，额外字段被忽略 | 每层 allowed-key exact set；未知字段失败 |
| 缺字段 | 多数字段保留 0/None | 按模块和 enable 条件定义 required-key；不能用 0 猜测 |
| 位宽 | Bit 统一 value & mask | 编码前验证 unsigned/signed 合法域；禁止 wrap-around |
| list | width // len(list) 推导每项宽度 | 精确 arity、每项宽度和范围；空 list/过长 list 失败 |
| DRAM LC | src4/outmost1/start17/stride17/end17/last4；RTL 对 start/stride/end 做 17-bit 有符号加法/比较 | 启用时 `stride>0` 且 `start<end`；start/end 限制为 17-bit signed，stride 限制为 1..65535；序列等价于正步长 `range(start,end,stride)` |
| ROW LC | src4/start3/stride3/end3/last4；RTL 为无符号加法/比较 | 启用时 0≤start<end≤7，1≤stride≤7；负值和回绕失败 |
| COL LC | src4/start6/stride6/end6/last4；RTL 为无符号加法/比较 | 启用时 0≤start<end≤63，1≤stride≤63；负值和回绕失败 |
| LC PE | opcode2、三端 src/last/mode、3x16 constant | opcode 仅 add/mul/mac；constant 的整数/FP16 编码域需按 mode 裁决 |
| ROW/COL LC | row 17 bit、col 26 bit | key 必须按数值 ID 排序，不能依赖普通字符串排序 |
| stream idx | mem 三维、buf 二维；多项由 list 编码 | mem list arity=3、buf arity=2；所有 None 只在 mode=null 时允许 |
| stream idx_size | 三个 size-minus-one；total_size 为三维乘积，8 bit | 每维正数；派生乘积<=255；idx_size_log 的每级累计尺寸必须为 2 的幂，或由 RTL 另行证明 |
| stream base_addr | 30 bit；纯 0/1 字符串被当二进制，解析失败回 0 | 地址只接受整数或带 0x/0b 前缀字符串；失败、负数、超 30 bit 均失败 |
| address_remapping | 26x5 bit，encoder 反序 | arity=26、每项 0..31、映射矩阵有效性和 profile 对齐 |
| padding/tailing | enable 3；每维 low/up 12 bit | arity 和 low<=up；仅对应 enable=1 的维度允许范围；padding value 与算子语义绑定 |
| buf_spatial_stride | 最多 16x5 bit；encoder 反序后在高位补到 16 lane | 必须恰好 `buf_spatial_size` 项，长度 1..16；每项 0..31 且活动 lane 不别名。要求固定 16 项会错误拒绝活动的 size=2/4 配置 |
| buf_spatial_size | 5 bit 原样编码；write data channel 用它把 terminal last flag 移到对应的 spatial lane | 启用 stream 时 1..16；0 会把 last flag 留在 discard bit，>16 会移出有效 bitmap，两者都可使 Slice 永不完成 |
| stream idx_size | JSON 为 3 个“各维 size-1”；活动格式以 `None` 表示未使用维度并派生为 size=1；encoder 从它派生 `total_size=∏size[d]` 和 `idx_size_log=[log2(dim0),log2(dim0*dim1),0]` | 必须恰好 3 项；每项为 `None` 或 0..255，非空项 `idx_size+1` 是 2 的幂，乘积 1..255；`total_size`/`idx_size_log` 禁止从 JSON 外部指定 |
| stream dim_stride | JSON 3 项原样编码为 3x20 bit，未使用维度可为 `None`；RTL 计算 `idx[d] * stride[d]` 后相加 | 恰好 3 项，每项为 `None` 或 0..2^20-1；单位是全局 DDR 地址的最小 8-bit 数据单元，需与 tensor dtype/shape 步幅交叉校验 |
| stream chunk order | read 为 580=10x58 bit，write 为 496=8x62 bit；encoder 按 FIELD_MAP 从 MSB 到 LSB 切块 | RTL 第一个接收 chunk 写入最高索引 reg，与当前 encoder 一致；R3 必须断言总位宽可整除 chunk 数，不允许 `split_config` 静默生成额外块 |
| address_remapping | 物理为 26x5 bit；RTL 对每个输出地址位 i 选择一个输入位 | 显式值必须恰好是 0..25 的一个排列；缺省时只允许明确语义的 identity permutation |
| neighbor mem_loop | JSON 正整数 n 编码为 `n-1`；RTL `nse_cnt_size` 是计数器末值 | 逻辑 group size 允许 1..32；1 编码为 0 表示无实际 neighbor hop；0/None 只在模块禁用时允许 |
| buffer_life_time | JSON 逻辑次数 n 编码为 `n-1`，4 bit；RTL counter 从 0 数到该末值且包含端点 | 启用 buffer 时 1..16；0 会经 `x-1` wrap 成 15，必须失败 |
| buffer_nbr_cnt | 5 bit，None 默认 27，当前不减一；RTL `arm_finish_cnt==buffer_nbr_cnt` 时结束 | 该字段是 encoded last/count-minus-one，不是逻辑次数；新 schema 应显式命名 `neighbor_finish_last` 或从逻辑次数统一减一 |
| buf_full_last_index | 4 bit，encoder 原样写入；memory/buffer 通路以 `last_index <= configured_last` 触发 finish | 它是 last-index 阈值而非 count；允许 0..15，必须与 stream 空间宽度和有效 bank mask 联合校验 |
| buf_end_row_addr | 2 bit，encoder 原样写入；RTL row counter 在相等时回绕 | 它是 inclusive last row address，非 row count；允许 0..3 |
| placement | 最大重试后仍可接受 penalty；未映射资源可顺序编号 | penalty 必须 0；禁止 fallback ID；每条连接必须在 RTL 可达集合 |

### 8.1 Slice completion 真值链

本地 RTL 的计算完成不是“SA/GA 已无数据”，而是如下单一通路：

`upstream terminal tag` → `WRITE_STREAM0 / RD_Buffer_AG` 看到 `last=1 && last_index==0` → `buf_ag_last_req_flag` → `WR_Data_Channel` 按 `buf_spatial_size` 把 flag 放到对应数据 lane → 最终写数据与 `mem2mse_wdata_ready` 握手 → `slice_cmpt_finish` 单拍脉冲 → `Slice_Execution_Manager` 从 CMPT 回到 IDLE。

因此新规则必须同时保证：

1. 存在且启用 target D，并唯一映射到 `WRITE_STREAM0`→buffer5。
2. 嵌套 loop/array 的 last 传播能在最终样本产生 `last_index=0`；“某个内层 last=1”不足以完成。
3. write stream `buf_spatial_size` 在 1..16，且 terminal flag 所在 lane 不被 tailing/valid mask 逻辑破坏。
4. 最终 DDR 写握手必须真正发生；只观察到 write request valid 不能宣称完成。

这也给出了 hang 的分层诊断点：terminal tag 未生成、tag 在 buffer 链丢失/last_index 不为 0、spatial bitmap 丢 flag、或最终 DDR ready 不握手，都会表面卡在 CMPT，但不是同一故障。

### 8.2 terminal tag、keep 与 SA tag 的静态闭环

按活动 RTL 的实际优先级，terminal tag 传播为：

1. `IGA_LC_Inbuffer` 给 outmost loop 的启动输入固定 `last=0,last_index=0`；每级 DRAM/ROW/COL loop 在本级结束时产生自己的 `last_index`，若上游同时带 `last=1`，则透传上游较外层的 `last_index`。因此一个 `last_index=0` 的 outmost loop 可以穿过所有内层 loop 到达 D。
2. `IGA_PE_Inbuffer` 只从第一个 buffer-mode 输入携带 tag；`Memory_AG_Idx_Queue` 三个输入和 `Buffer_AG_Idx_Queue` 两个输入也采用第一个物理 buffer-mode 输入作为 tag carrier。严格规则要求每处恰有一个 carrier，不能依赖物理优先级掩盖重复 carrier。
3. JSON list 进入 packed array 时反序。对 buffer AG，JSON 两项的语义顺序是 `[ROW,COL]`，对应 RTL `[1]=ROW,[0]=COL`；活动 D stream 的 `['keep','buffer']` 因而选择 COL 链携带 tag，不是 ROW 链。
4. keep 释放条件在 LC PE、memory AG 和 buffer AG 中均为 `last && last_index <= configured_last_index`，阈值是 inclusive，不是相等比较或 count。
5. SA `transout_last_index` 会比较并消费/透传 SA 自己的数据 tag；活动值为 1..3，外层 terminal 0 会被保留。但 Slice 的唯一完成源仍是 D buffer-AG tag，不是“SA 为空”或 SA tag 本身。

外围递归分析器已对当前 55 份 `ndp-sim/jsons/*.json` 求出 D carrier 的可能 tag 集合：55/55 均包含 0，集合分布为 `{0,1,2,3,4}` 24 份、`{0,1,2,3}` 23 份、`{0,1,2,3,4,5}` 5 份、`{0,1,2}` 2 份、`{0,2,3}` 1 份。这只证明静态可达，不代替最终 DDR ready 的 E3/E4 动态证据。

### 8.3 SA 非对称布局裁决

`special.py` 确定 legacy JSON label 为 `col→bit0,row→bit1`；`SA_Outport_Connect.sv` 确定 bit0 执行 `out[o][s]=in[o][s]`，bit1 执行 `out[o][s]=in[s][o]`。使用非对称矩阵

```text
1   2   3
10  20  30
100 200 300
```

外围微模型得到：JSON `col` 原样输出，JSON `row` 输出转置矩阵。由此 SA-001 的**物理行为已裁决**：旧 label 只是反向历史别名，不能再按自然语言解释。仍不能从 JSON 自身推断某个 ONNX 算子期望哪一种 D layout；开发模式必须由算子/layout contract 显式给出 `expected_sa_transpose`，缺失或冲突都停止。复现模式只重放旧 label 的已知物理 bit，不批量改名或翻转。

### 8.4 padding、tailing 与空间尾 lane 裁决

1. read padding 的有效区间是每个启用维度的 inclusive `[low_bound,up_bound]`；范围外 byte 由 `padding_reg_value` 替换。padding 不抑制 DDR read request，所以即使整个 lane 最终被 padding 覆盖，原始请求地址仍必须合法。
2. tailing 对应 RTL branch mask，范围同样 inclusive。read 范围外 byte 置零；若同一 byte 同时命中 padding 与 tailing，padding 优先。write 范围外 lane 不直接写零，而是把旧 DDR read data 合并回来，形成条件写屏蔽。
3. 禁用维度必须使用 `enable=0,low=null,up=null`；启用维度必须显式给出 12-bit unsigned 边界且 `low<=up`。read padding 启用时必须显式绑定 8-bit padding 值及算子 dtype/zero-point；不得依赖 `None→0` 的 encoder 缺省。
4. `buf_spatial_size` 必须在 1..16，`buf_spatial_stride` 长度必须与之相等。0 会把 terminal flag 留在 discard bit，>16 会把它移出 16-lane bitmap；tailing 不直接删除 terminal flag，但最终合并写仍必须握手。

### 8.5 CONFIG 跨 stage 状态裁决

`Slice_Config_Manager` 在 `PARSE_INIT` 读取 bit7..0=`IGA/LSU/SA/GA enable` + `IGA/LSU/SA/GA update`，且 `cfg_clear = !enable || update`。可执行状态规则为：

- `enable=1,update=1`：清空旧寄存器并装入本 stage 完整子系统配置，产生新的持久状态指纹；
- `enable=1,update=0`：不清空、不解析该子系统，继续使用上一 stage 已初始化状态；首 stage 复用、禁用后复用均失败；若 JSON 仍携带不同 body，则是“文件意图与硬件保留态漂移”，失败；
- `enable=0,update=0`：清空子系统，后续不得直接复用；严格格式不允许同时携带会被忽略的 body；
- `enable=0,update=1`：RTL 最终仍清空且 finish 被 enable mask，payload 没有清晰 stage 语义，严格规则拒绝。

当前 55 份活动 JSON 的 CONFIG 仅有 `11011101` 47 份、`11101110` 6 份、`11111111` 2 份；它们均对所有启用子系统设置 update=1，可作为独立首 stage 装载。两阶段 update/reuse/disable 的外围状态微测已通过，但服务器真实寄存器/数值 E4 仍是推广到跨 stage 优化的阻塞项。

### 8.6 R3 初始影子扫描

外围 validator 不 import、不写入 `ndp-sim`，已用 18 个正负微测覆盖本节四类语义及地址/位宽/B′ 边界。对 55 份活动 JSON 的首轮结果为 46 valid、9 invalid；失败集中为：

- 3 份 Pool/AvgPool 配置启用了 padding，但 `padding_reg_value=None`，原生 encoder 会静默编码为 0；数值上可能恰为预期零 padding，但来源合同缺失，严格模式不能猜。
- node0004 两份 write stream 携带 read-only padding 字段，另有一份 prefill write stream 携带 4 个 read-only 字段；WriteStream `FIELD_MAP` 不消费这些字段，属于静默忽略。
- 3 份 prefill GEMM 的 `mem_idx_mode` 使用整数 `0` 代替枚举 `null`；当前 mapper 会编码成相同 0，但 typed schema 不允许两种表达混用。

这 9 份是“需裁决/规范化”，不是已经证明数值错误；原文件和原生输出均未被 validator 改写。聚合报告为 `artifacts/operator_config_validation/r3-shadow-active-jsons-20260723.json`。

## 9. 地址真值表草案

model_execplan 地址格式声明为 slave5/bank2/row13/col6/subword4。13 个 row bit 只能说明可表达 0..8191，不说明物理 DDR 有 8192 行。当前 target profile 物理上限是 row<6144。

R3 地址检查至少包括：slave 在启用 slice 集合内、bank<4、row<6144、col<64、subword<16；base/length 单位一致；tensor、config、SFU、readback 区间不越界且按声明对齐；remapping 前后可逆；alias 有显式所有权；no-free 峰值不得按 8192 虚构容量通过。

## 10. R1 未裁决项

1. SA outport 物理转置已由非对称矩阵微模型裁决；具体算子的期望 D layout 必须由外部 layout contract 绑定，服务器非对称回读仍是 E4 阻塞项。
2. DRAM/ROW/COL loop 的正向 start/end/stride 与 terminal tag 静态传播已裁决；非整除边界和最终 DDR 握手仍需动态用例。负/0 stride 不纳入支持域。
3. buffer 主要 off-by-one 已静态裁决；剩余是 `buffer_nbr_cnt` 与 partner finish 事件的端到端动态计数。
4. read/write stream 的 chunk 顺序、dim_stride 单位、`idx_size_log` 幂约束、padding/tailing/keep 与 base-address 低 4 bit 约束已静态裁决并有外围边界微测；真实 DDR 请求/合并写与 completion 仍需 E3/E4 动态用例。
5. GA constant 的 float/int bitcast 规则、rounding 与特殊值。
6. CONFIG update/reuse/disable 状态机已静态裁决并有外围序列微测；两阶段服务器寄存器/数值回读仍待 E4。
7. server loader 当前实际读取的参数/bitstream 顺序与本地 filelist/profile SHA。用户已确认服务器 RTL 应与 GitHub/本地一致，但服务器侧 SHA 仍待机械核验。

## 11. 当前判定与下一步

R1 静态退出门已达到：活动字段要么已有唯一 RTL/encoder 真值，要么在上节显式列为 E4/E5 阻塞项；没有用默认 0 填补未知语义。活动 JSON 中无负 stride；node0004 两个空 LC 槽 `start=end=stride=0,src_id=null` 且不在活动链；全部派生 stream total_size 最大 128；`buf_spatial_size` 实际覆盖 2/4/16 且 stride 长度与 size 相等；55/55 D terminal chain 静态包含 last_index=0。R2 规则草案和 R3 外围 validator 已开始，当前不得把 46/55 shadow valid 解释为 E4，也不得自动修改其余 9 份遗留配置。
