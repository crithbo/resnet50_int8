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

因此 GAP v7 中的 transout occupancy/stale-C 缺陷不属于本算子的数值
数据流；任何派生 JSON 若引入 transout，则必须重新进入 RTL_CONTROL 审核。

## 3. 物理布局

### CDA-DEQUANT-LAYOUT-HIGH4-001

网络布局沿用
`w4_group4x7_batch_channel28_candidate_v1`：

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

### CDA-DEQUANT-NODE0072-CONFIG-ONLY-E2-001

node0072 `uint8[16,2048,1,1]→fp32[16,2048,1,1]`、scale bits
`0x3cbf57ec`、zero-point 0 已完成本地
`CONFIG_ONLY_CORRECTNESS_BASELINE`：

- 28 slice，hardware CWH `[16,74,1]`，每片 74 occurrence；
- two-stage 4 ADD(`-0.0`)→4 MUL(scale)，只复用 node0077 的结构；
- final address-bound JSON、mapping、bitstream、execplan/SCA、address/lifetime、
  physical D、logical inverse 与 W3 逐 bit 闭合；
- 每片最终 D coverage 为 `74×64=4736` bytes，28 片 physical 132,608 bytes，
  其中 logical valid 131,072 bytes、padding 1,536 bytes；
- static→materialized 10 个变化全部有 owner，unexpected=0；
- 两份空 cache 隔离物化的语义产物逐 SHA 相同。

该规则只批准 node0072 的 local materialized E2，不批准正式 target、production、
performance、E4/E5 或 node0072→node0073 integrated binding。保持：

- `B_DEQUANT_NODE0072_NATIVE_STANDALONE_PATH`
- `B_DEQUANT_NODE0072_FORMAL_LAYOUT_APPROVAL`
- `B_DEQUANT_NODE0072_HARDWARE_E4_E5`
- `B_DEQUANT_NODE0072_TO_NODE0073_INTEGRATED_BINDING`

权威机器合同：
`contracts/operator_config/node0072_dequant_config_only_correctness_baseline_v1.json`。

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

### CDA-DEQUANT-NODE0077-E4-V6-DYNAMIC-PASS-001

`dequant_node0077_stockrtl_e4_onecmd_v2` 是 node0077/v6 的第一份正式 E4 通过证据：

- return ZIP 为 252,634 bytes，SHA256
  `79b3ea77d7a1651ee77181cffe7264d86da59f47fffa17277d603d8a727272d4`；
  来源 package SHA256 为
  `2ac27a4856b36bb660c0293ff53f84794464283712f20fe0d84dabfa16b699e0`；
- 内部 `RETURN_RECEIPT` 的 105 项 payload exact-set、size、SHA 和 allowlist 全部通过；
  compile/sim/run 均为 0，28/28 slice 全部自然 start/finish，无 timeout、critical
  marker 或越界；
- 正式 D 为 28×188 个 128-bit 行，共 5,264 行；地址唯一、未 preload，28 片全部
  逐 bit 对各自 golden。每片前 750 个 fp32 正确，末尾两个为 `+0.0f`；
- layout inverse 完整且唯一地还原 `float32[16,1000]`，actual/expected SHA256 同为
  `d5aa938813ec8ef7fe51cc2288df5f0e1782c19729a184cef248718ce83a311d`；
- temporal observer 独立记录 5,264 request 与 5,264 write-data，每片各 188，
  finish summary 一致；未做未经证明的 request/data 配对，也未丢弃 accepted data；
- stock RTL、focused RTL、observer 和安装命名空间在声明的全部阶段保持稳定，
  `functional_rtl_unchanged=true`。

包内 `FIRST_DYNAMIC_RUN` 归一化为 `FIRST_DYNAMIC_PASS / NO_PRIOR_DYNAMIC_BASELINE`，
不得称为 regression。该结果解除 `B_DEQUANT_SERVER_E4_E5` 中的 E4 部分，当前唯一
动态 blocker 为 `B_DEQUANT_SERVER_E5`；`candidate_release=false` 仍保持。

允许从完全相同的 v6 语义资产生成全新 package/install/run/return 身份的 E5。E5 必须
复验相同的 28×188 正式 D、layout inverse、自然完成、temporal raw count、return
exact-set 和四阶段身份；只有 E5 再次通过，node0077 才能升级为正式 target config
和该节点的 stock-RTL 动态闭环。此放行仅覆盖 Dequant node0077，不外推到其他算子或
整网。

### CDA-DEQUANT-NODE0077-E5-V6-DYNAMIC-PASS-001

`dequant_node0077_stockrtl_e5_onecmd_v1` 是与上述 E4 绑定、使用全新身份完成的正式
E5 通过证据：

- return ZIP 为 253,442 bytes，SHA256
  `ae993cbf7cc51757a6be24f89e72a3e77ac98cba8953ef1510f93e736a71ca66`；
  来源 package SHA256 为
  `83cd2db78f99d27f02c2b65a46f9f5c43e94b9ff9a5c50ef0273a0409f1cab68`；
- 内部 `RETURN_RECEIPT` 的 105 项 payload 与 ZIP 实际 payload 逐项 size/SHA
  相同，allowlist 和必需文件齐全；返回的 package manifest 与来源 package
  逐字节一致；
- compile/sim/run 均为 0，28/28 slice 各自然 start/finish 一次，无 timeout、
  critical marker 或越界；
- 正式 D 为 28×188=5,264 行，128-bit 文本 ABI 全通过；28 份 readback 与来源包内
  独立 golden 逐字节一致，地址唯一且未 preload；
- layout inverse 完整且唯一还原 `float32[16,1000]`，actual/expected SHA256 均为
  `d5aa938813ec8ef7fe51cc2288df5f0e1782c19729a184cef248718ce83a311d`；
- temporal observer 独立记录 5,264 request 与 5,264 write-data，每片各 188；
  stock RTL、focused RTL、observer 和安装命名空间身份门通过，
  `functional_rtl_unchanged=true`；
- E5 manifest 将 61 个 E4 workload 文件绑定为 60 个逐字节相同项和 1 个仅安装
  namespace 归一化的 SCA 项；严格 JSON、mapping、bitstream、execplan、输入、
  golden、inverse、地址与长度语义全部冻结。

包内 `REPEAT_DYNAMIC_RUN` 归一化为 `REPEATED_DYNAMIC_PASS`。独立验收后
`B_DEQUANT_SERVER_E5` 已关闭，node0077/v6 可计为正式 ResNet50 target config，并完成
该节点的 stock-RTL E4/E5 动态闭环。该结论仍不自动补齐项目总账中独立
config-bound simulator 一腿，也不外推到其他 Dequant shape、算子或整网。
