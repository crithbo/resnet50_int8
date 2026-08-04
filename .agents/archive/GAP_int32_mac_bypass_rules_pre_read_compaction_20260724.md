# 归档：精简前的 GAP int32_mac pure-config bypass rules

本文件保留 v1～v5 历史状态、重复增量和原本的 E2 声明，仅用于审计。当前专项规则仍在
原路径；历史 E2 已因最终 stage-1 JSON 回环缺口重新打开。

> 2026-07-24 最新增量（优先于下文历史状态）：`gap_int32_mac_stock_rtl_onecmd_v4`
> 因 16 个 `sca_cfg_D.json` 条目均缺少 testbench 必需的 `length` 字段而作废；
> 该包会得到 `JSON_D config: 0 matrices dumped`，不得上传或复用。当前唯一可交付版本为
> `gap_int32_mac_stock_rtl_onecmd_v5`，ZIP SHA-256
> `e8b3ae2c694c3a8a516a99541de26f6059ba9b3ba84bc5d8e532ed9db36185b7`。
> v5 的每个回读条目精确包含 `base_addr/path/length=512`，并同时加入 wall-clock
> timeout、异常/信号部分回传、SCA/SCA_D 回显和 loader 计数、正式 D 文件 LF/精确大小、
> dual-MSE 全地址序列及旧日志污染拒绝门。它仍为
> `candidate_release=false / E2_LOCAL_ONLY`，服务器 E4/E5 未解除。

## `CDA-SCA-D-TB-READBACK-LENGTH-001`

- 每个 `SCA_D` 条目必须精确包含 `base_addr`、`path`、`length` 三个字段；
- `length` 的单位是 128-bit word，不是 byte；GAP 正式回读固定为每片 512；
- 缺字段、类型错误、非 512 或回读目标预先存在时必须 fail closed；
- 服务器日志必须同时证明正确的 `SCA_CFG_D` 回显和
  `JSON_D config: 16 matrices dumped`，不能仅凭仿真自然结束声称回读成功；
- 每片输出还必须是 512×129 bytes 的 LF-only 128-bit 文本并逐行匹配 golden。

> 2026-07-24 最新增量（优先于下文历史状态）：`gap_int32_mac_stock_rtl_onecmd_v4`
> 因 16 个 `sca_cfg_D.json` 条目均缺少 testbench 必需的 `length` 字段而作废；
> 该包会得到 `JSON_D config: 0 matrices dumped`，不得上传或复用。当前唯一可交付版本为
> `gap_int32_mac_stock_rtl_onecmd_v5`，ZIP SHA-256
> `e8b3ae2c694c3a8a516a99541de26f6059ba9b3ba84bc5d8e532ed9db36185b7`。
> v5 的每个回读条目精确包含 `base_addr/path/length=512`，并同时加入 wall-clock
> timeout、异常/信号部分回传、SCA/SCA_D 回显和 loader 计数、正式 D 文件 LF/精确大小、
> dual-MSE 全地址序列及旧日志污染拒绝门。它仍为
> `candidate_release=false / E2_LOCAL_ONLY`，服务器 E4/E5 未解除。

## `CDA-SCA-D-TB-READBACK-LENGTH-001`

- 每个 `SCA_D` 条目必须精确包含 `base_addr`、`path`、`length` 三个字段；
- `length` 的单位是 128-bit word，不是 byte；GAP 正式回读固定为每片 512；
- 缺字段、类型错误、非 512 或回读目标预先存在时必须 fail closed；
- 服务器日志必须同时证明正确的 `SCA_CFG_D` 回显和
  `JSON_D config: 16 matrices dumped`，不能仅凭仿真自然结束声称回读成功；
- 每片输出还必须是 512×129 bytes 的 LF-only 128-bit 文本并逐行匹配 golden。

> 2026-07-24 最新状态增量（优先于本文后续旧状态）：六份真实 JSON、独立
> mapping/bitstream、6×Load_Config/Start_Comp/Barrier 和正式 W3 golden 本地
> E2 已闭合。stage1 的 `C=A+8` 已被 16B 对齐门反证，改为 A-even/C-odd
> 双对齐 preload（base `0x0/0x20000`）；物理树为
> `64→32→16→8→4→2→1`。旧
> `gap_int32_mac_stock_rtl_atomic_v1` 因服务器操作暴露过多步骤而被用户否决，
> 不再发布；未发布的 `onecmd_v2` 草稿因 128-bit 文本残留 CRLF 未通过本地专项门；
> 未发布的 `onecmd_v3` 草稿因 SCA_D key 的字典序枚举不能保证数字 slice 身份，
> 在本地复核门被废止。当前唯一允许交付的是
> `gap_int32_mac_stock_rtl_onecmd_v4`：正式回读按解析后的数字 slice ID 0..15
> 精确绑定，内容仍保留完整六 stage 测试、身份和动态裁决，
> 服务器只需执行一条 `bash PREPARE_AND_RUN.sh /abs/path/NDP_copyXX`。它不含任何
> RTL/TB 源文件，不安装 observer，不写功能 RTL，仍为
> `candidate_release=false / E2_LOCAL_ONLY`。服务器仍须验证双流
> skew/stall/resume、normal FIFO 全周期、真实 barrier drain/可见性、
> invalid-slot reuse=0、16×512 D golden 和独立 E5。

目标：在不修改功能 RTL 的前提下，用普通 GA `int32_mac` 多 stage 显式加法树
实现 49 元素 UINT8→INT32 求和，绕开 `int32_sum` transout/outbuffer feedback。

服务器包生成门已于 2026-07-24 由六份真实 JSON、独立 bitstream、六 stage
生命周期和正式 W3 golden 本地 E2 闭合。当前只允许
`gap_int32_mac_stock_rtl_onecmd_v4` 这一无 RTL patch、单命令入口测试；它仍为
`candidate_release=false / E2_LOCAL_ONLY`。操作简化不得删除正式 D 回读、双 MSE、
normal FIFO、barrier/lifecycle、stock RTL 身份或白名单回传证据。

## `CDA-GAP-INT32MAC-NONTRANSOUT-001`

- opcode 必须为 `int32_mac=14=5'b01110`。
- RTL `alu_op_is_transout` 对 opcode 14 必须为 false。
- 每个 PE 的方程固定为 `D=int32(A*B+C)`，B 必须为常数 1。
- 禁止使用 `int32_sum`、`sum`、`summac` 或任何 outbuffer feedback 完成归约。

## `CDA-GAP-INT32MAC-DUAL-INPUT-001`

- A 使用 GA inport group0 的 buffer0。
- C 使用 GA inport group2 的 buffer4。
- B 使用 PE constant 1。
- buffer5 只作为 GA 写回目标，不得同时作为 C 输入。
- A/C occurrence 必须同时 valid 才允许 PE match；一次 match 必须同拍消费同一
  pair 的 A/C，任一侧 stall 时另一侧不得越过。
- A/C 的 last、last_index 必须相同；不一致时配置或测试必须 fail closed。

物理依据：buffer `i` 映射为 `GA group=i/2, ping-pong slot=i%2`，因此 buffer0、
buffer4、buffer5 分别是 `(group0,slot0)`、`(group2,slot0)`、
`(group2,slot1)`。

## `CDA-GAP-INT32MAC-NORMAL-FIFO-001`

- opcode 14 必须走 normal outbuffer。
- normal count 只允许由实际 accepted write/read 按
  `next=count+write-read` 更新。
- 任意周期必须满足 `0<=count<=2`。
- 在合法 FIFO 状态下，同时 read/write 时读写指针不得指向同一 occupied slot。
- 测试必须覆盖 empty、single-entry、full、stall 和同时 read/write。

## `CDA-GAP-INT32MAC-TREE-001`

49 项归约固定为六层：

```text
49 -> 25 -> 13 -> 7 -> 4 -> 2 -> 1
```

每层将相邻 pair 映射为 `int32_mac(left,1,right)`；奇数尾项的 right 必须使用显式
零值，禁止读取越界或复用旧 buffer data。对 UINT8 输入，最终和范围为
`0..49*255=12495`，不会发生 INT32 overflow。

## `CDA-GAP-INT32MAC-STAGE-MEMORY-001`

在允许生成候选前，每层必须证明：

- 输入/输出 shape、dtype、layout 和逐 C8 block 地址；
- A/C 两条读 stream 的有序地址一一配对；
- 中间 INT32 写回区域完整、互不覆盖且下一层可见；
- 256 个 C8 channel block 在 16 个 slice 上覆盖完整；
- terminal tag 精确结束当前层，不早停、不跨层泄漏；
- 每次 stage 重配置有独立 config/bitstream/execplan/SCA provenance；
- 最终层输出仍满足每片 512 条 128-bit D 地址及 golden 合同。

stage1 的真实编码补充：

- MSE 请求基址必须 16-byte 对齐，因此旧的同一区域 `C=A+8` 计划已被通用
  validator 反证并废弃；
- preload bridge 将 49 叶拆成两个独立、对齐的 A-even/C-odd 区域；
- 每个 occurrence 为 16 bytes，其中低 8 bytes 是 C8 operand，高 8 bytes
  为零 guard；A base=`0x00000`，C base=`0x20000`；
- physical tree 固定为 `64→32→16→8→4→2→1`，叶 49..63 显式为零；
- 六级输出基址依次为
  `0x40000,0x80000,0xA0000,0xB0000,0xB8000,0xBC000`。

## 当前证据边界

本地已经闭合：

- opcode 编码与 non-transout 分类；
- `A*1+C=A+C` 的 INT32 方程和边界值；
- 49 项六层调度及随机 UINT8 数值；
- buffer0/buffer4 双输入物理分组；
- A/C 同时 valid 的 match/backpressure 静态方程；
- 相同 terminal tag 的非 transout 传播；
- normal FIFO 六周期全枚举握手不变量。
- 六份真实 JSON 均通过通用 validator；
- 六份 mapping 固定 A→READ_STREAM0、C→READ_STREAM3、D→WRITE_STREAM0；
- 六份独立 parsed/64b/128b bitstream；
- execplan 含 6 次完整 Load_Config、6 次 Start_Comp、6 次同 mask Barrier，
  不含跨 stage Write_Reg 基址偷换；
- CGRA_SIM、物理 INT32 六级树和独立 W3 golden 对 32768 个向量一致；
- 最终每 slice 2048 个 INT32，即 512 条 128-bit readback。

2026-07-24 本地静态证据增量：

- stock RTL 对 non-transout 的 tag 与 input C 均在多路器第一分支直接选择
  `ga_pe_inbuffer2alu_tag` / `ga_pe_inbuffer_data[2]`；opcode 14 不会进入
  `transout_initial`、invalid outbuffer slot 或 stale-C feedback 分支。
- `add_transout_initial` 显式受 `alu_op_is_transout` 门控，因此 opcode 14 不会积累
  transout 初始化状态。
- normal FIFO 的写/读更新分别来自 accepted write/read handshake；非 transout
  分支仅执行 `count+1`、`count-1` 或同时握手保持，v7 固定减 2/3 的 compaction
  分支不可达。
- 六份真实 JSON 逐份确认：8 个 PE 均为 `int32_mac`，A/C 为 buffer、B 为常数 1，
  `transout_last_index=null`；三条 stream 固定为 read A、read C、write D，所有基址
  16B 对齐，tailing/ping-pong 均关闭；只有 stage1 对 A/C 启用 UINT8→INT32。
- 机器合同已绑定 `LOCAL_E2_REPORT.json` 及六份 config/mapping/parsed
  bitstream/installed bitstream/execplan 哈希；真实 stage 资产 blocker 已改为
  `closed_local_e2`。该升级不等于 cycle-level RTL 执行或服务器数值通过。

服务器仍待闭合：

- cycle-level 双输入 first/skew/stall/resume；
- normal FIFO 全周期 occupancy 与 invalid-slot 隔离；
- 六次 Barrier 对应的真实 drain/写可见性；
- 16×512 正式 D 回读逐行 golden；
- 独立重复 E5。
