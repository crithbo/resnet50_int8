# DequantizeLinear 算子配置规则

## 1. 适用范围与权威输入

本文约束 ResNet50 `node-0077 / hwop-0077-00` 的 standalone
`DequantizeLinear(uint8 -> fp32)` 垂直链路：

`ONNX -> typed lowering request -> stage schedule -> operator JSON ->
bitstream/mapping -> execplan/SCA -> RTL dynamic evidence`。

生成前先完整阅读 `.agents/rules/生成前必读索引.md`，再按其配置开发 profile 读取本文件、
`算子配置规则.md`、`NDP硬件字段语义.md` 的 LC/MSE/Buffer/GA 相关章节，以及本轮实际
调用的 typed parser、mapper、encoder、execplan/SCA 直接消费者。未参与本轮命令或字段
验收的原生文档不重复列入专项规则。

固定权威输入为：

- lowering request：`contracts/resnet50_r5_lowering_bundle.json` 中
  `r5:hwop-0077-00`
- W3 输入：`artifacts/w3/golden_batch16/tensors/tensor-02aeb7457d1ccf49.npy`
- W3 输出：`artifacts/w3/golden_batch16/tensors/tensor-bff07c95eb9f8609.npy`
- 原生已确认正确参考：
  `ndp-sim-ref/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json`
- typed transport 权威实现：
  `ndp-sim-ref@d4ffc32c9b29a858d83e13706cd837c5549521a4`

`ndp-sim-ref` 与 `ndp-sim` 都是只读上游源码。若当前 handler 不支持
standalone 类型，只能在有源码 hash 门的隔离副本中扩展，不能修改活动源码。

## 2. 数值语义

### CDA-DEQUANT-ONNX-ORDER-001

逐元素语义必须是：

```text
q_i = float32(uint8(x_i)) - float32(uint8(x_zero_point))
y_i = float32(q_i * float32(x_scale))
```

本实例固定：

```text
x_scale      = float32 bits 0x3e01622d
x_zero_point = uint8 60
-x_zero_point as fp32 = 0xc2700000
```

比较标准是与 W3/ONNX 输出逐 bit 相等，不得只比较容差。

### CDA-DEQUANT-NO-AFFINE-MAC-001

不得把本实例改写为：

```text
float32(float32(x * scale) + float32(-zero_point * scale))
```

也不得用一个 GA `mac` PE 实现上述表达式。该形式改变 ONNX 的舍入顺序，
在真实 W3 的 16000 个输出上存在逐 bit 反例。

### CDA-DEQUANT-TWO-STAGE-GA-001

standalone 拓扑固定为两个普通 GA stage：

1. `PE00/PE02/PE20/PE22`：
   `add(uint8tofp32(A), constant(-60.0f))`
2. `PE10/PE12/PE30/PE32`：
   `mul(previous_PE, constant(x_scale))`

对应关系固定为：

```text
PE00 -> PE10
PE02 -> PE12
PE20 -> PE30
PE22 -> PE32
```

两个常量都必须进入各 PE 的 `inport1`。第一层 `inport0` 只能来自
GA `inport0` 的 A buffer；第二层 `inport0` 只能来自对应第一层 PE。
所有 `inport2` 必须禁用。

输出 mask 固定为 `[0,1,0,1,0,1,0,1]`，只发布第二层结果。

### CDA-DEQUANT-NORMAL-OUTBUFFER-001

本算子只允许 GA 普通 `add`/`mul` 路径：

- 禁止 `transout`、`transout_last_index`
- 禁止跨 block feedback
- 禁止无效槽作为 ALU 输入
- 禁止依赖 GA transout compaction

因此 transout occupancy/stale-C 缺陷不属于本算子的已授权数值数据流；任何派生 JSON
若引入 transout，必须重新进入 RTL_CONTROL 审核。

## 3. 物理布局

### CDA-DEQUANT-LAYOUT-HIGH4-001

对本规则覆盖的 `[16,1000]` 实例，网络布局固定为：

- 7 个 HIGH4 group
- group 样本数为 `(3,3,2,2,2,2,2)`
- 每个 group 的 4 个 owner 将 1000 个 feature 固定分为每片 250 个
- 每片保存 3 个 sample slot，逻辑 payload 为 `3 * 250 = 750` 个元素

硬件 CWH 形状固定为 `[C=16,W=47,H=1]`：

- A 每片 752 bytes；尾部 2 bytes 必须填 `x_zero_point=60`
- D 每片 752 个 fp32，即 3008 bytes；尾部 2 个值必须为 `+0.0f`
- 前 750 个元素必须逐字节等于既有 simple-layout payload
- inverse 必须丢弃最后 2 个 pad 元素后无损还原 `(16,1000)`

禁止把 750 当成循环终点、禁止让尾部读越界、禁止用非零 D tail。

### CDA-DEQUANT-STREAM-LIFECYCLE-001

只允许一条 A read stream 和一条 D write stream，不得保留原
Add-Dequant 模板中的 B stream、B buffer 或 B loop group。

固定局部字节数：

```text
A = 16 * 47 * 1 * 1 = 752
D = 16 * 47 * 1 * 4 = 3008
```

LC、buffer-loop、stream stride、buffer lifetime 与 completion tag
必须共同覆盖恰好 752 个输出元素。JSON 结构 validator 通过不能替代该
覆盖证明。

### CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001

D write 的 memory transaction 大小与 D buffer 向 MSE4 提供的数据量必须按
每个 occurrence 守恒，不能只在整片 DDR 地址总量上守恒：

```text
d_transaction_bytes
  = stream2.idx_size[2] + 1
  = 64

d_buffer_bytes_per_request
  = stream2.buf_spatial_size
  = 16

trip_count(GROUP2.ROW_LC)
  = d_transaction_bytes / d_buffer_bytes_per_request
  = 4
```

因此本实例固定要求：

- `buffer5.buf_end_row_addr = 3`，对应 D buffer 的 row `0..3`；
- `GROUP2.ROW_LC = {start:0, end:4, stride:1}`；
- `GROUP2.COL_LC = {start:0, end:16, stride:16}`；
- 每个逻辑 occurrence 必须向 MSE4 提供 4 个 16-byte buffer row，并形成
  4 个 128-bit accepted write；
- `last` 只能随第 4 个 row/beat 到达。任一 slice 在 accepted write 少于 4
  或 MSE4 尚有 outstanding address/data 时产生 completion，均不得视为该
  occurrence 完成。

上述方程同时受可信原生
`add_dequant_uint8CWH_uint8CWH_fp32CWH.json` 和 RTL 消费者约束：

- 原生配置使用 `GROUP2.ROW_LC.end=4`、`buffer5.buf_end_row_addr=3`；
- `RD_Buffer_AG.sv` 每个 row 请求按 `buf_spatial_size` 发布有效 byte；
- `WR_Data_Channel.sv` 把 buffer 侧 `last` 放入 write-data bitmap，并用该
  last beat 产生 `slice_cmpt_finish`。

不得把 DRAM occurrence 数 `LC3/LC4` 与 occurrence 内部的 4 个 D buffer row
混为一层循环。前者决定有多少个 64-byte transaction，后者决定每个 transaction
是否有完整的 64-byte 数据供给。

## 4. typed constants 与映射

### CDA-DEQUANT-TYPED-CONSTANT-001

execplan 必须携带两个、且仅两个标量 fp32 constant：

- `negative_zero_point`：`0xc2700000`
- `x_scale`：`0x3e01622d`

每个 constant 必须具有：

- 原始或派生 parameter ID
- dtype、shape、values、float32_bits
- little-endian value SHA-256
- 4 个显式 `control_register:` target binding
- 对应 operator config artifact ID

禁止从文件名、legacy integer `params`、或未声明的默认值恢复常量。

### CDA-DEQUANT-MAPPING-BINDING-001

bitstream mapper 后必须重新核对 GA logical PE 到 physical PE 的映射。
满足以下任一条件才可通过：

1. typed constants 已在 mapper 输入 JSON 中逐 bit 烘焙，且 bitstream
   解码证明映射后的物理 PE 常量正确；或
2. execplan 的 instance mapping 明确覆盖 `GA_PE.PErc -> ga_peN`，
   且动态 Write_Reg 指向实际物理 PE。

仅看到 execplan 中有 8 个 logical register key 不构成闭环证据。

### CDA-DEQUANT-MATERIALIZED-CONSTANT-NORMALIZATION-001

typed handler 把 fp32 bit-string 常量规范化为十进制或其他文本形式时，必须在
static→materialized 逐 leaf diff 中声明 owner、输入 bits、变换公式、旧值、期望新值
和授权，并把最终文本重新解析为 binary32 验证 exact round-trip bits。

`-0.0` 规范化为 `+0.0` 不按普通文本等价自动放行。只有目标实例的 typed 输入域证明
负零符号不可观察，且完整冻结域最终输出逐 bit 等价时才允许；该批准不得外推到可能产生
负值、signed zero 可观察或 NaN/Inf 的实例。node0072 的 uint8、zp=0 非负域和
32,768 元素全域 bit-exact 证明满足此窄门。

## 5. 本地 E2 与服务器 E4/E5 门

### CDA-DEQUANT-E2-001

本地 E2 必须全部通过：

1. 真实 W3 16000 元素逐 bit golden
2. affine-MAC 负例确实不等
3. 28 片 A/D payload 大小、padding、prefix、inverse
4. strict operator-config validator
5. exact topology validator
6. 官方 bitstream encoder 至少双跑且逻辑输出一致
7. mapping 后常量与 PE 关系审计
8. 官方 typed parser round-trip
9. 完整 execplan pipeline 生成 `execplan.txt`、addressed graph、
   install manifest、每算子 regenerated JSON/bitstream
10. 最终 materialized JSON 逐 occurrence 反解并验证
    `D transaction bytes = GROUP2 row trips * buf_spatial_size`，且
    `GROUP2.ROW_LC.end=4`
11. 活动 `ndp-sim-ref` 与所有 `rtl/` 文件身份保持不变

### CDA-DEQUANT-E4-E5-001

本地 E2 只允许声明 `candidate_release=false`。服务器至少还需：

- 28 片逐片执行
- 每片 752 个 D 值正式回读
- 前 750 个值逐 bit 对比 W3 分片 golden
- 末尾 2 个值逐 bit 为 `0x00000000`
- 无 hang、无 timeout、无越界请求
- E5 重跑一致

在 E4/E5 完成前，不得声明正式 target config 或硬件数值闭合。

服务器 package 必须按 `生成前必读索引.md` 的 profile 选择文件；专项数值门保持不变，
包内任何路径均不得修改服务器 `rtl/` 文件夹内的文件。

版本化 local E2、E4、E5 通过结果及其 ZIP/SHA 只保存在 `.agents/plan.md` 与对应
`.agents/task_records/`。它们可以作为身份绑定证据被引用，但不得重新定义本文件的稳定
数值、布局或发布门，也不得自动外推到其他 shape、实例或整网。
