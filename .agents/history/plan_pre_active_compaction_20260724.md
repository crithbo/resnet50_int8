# ResNet50 INT8 当前执行计划与接手入口

> 2026-07-24 当前最高优先级状态：GAP `int32_mac` v1～v5 的服务器续测、配置修复和
> 新包生成已全部暂停，历史资产只读。同系列从未有服务器自然完成/正式回读的动态成功
> 基线；v1～v3 未发布运行，v4/v5 均为不完整返回，因此不得再称 v5 为“回归”。
> 旧 local E2 未把最终 stage-1 JSON 反解回 transaction/buffer/bank/lifetime 合同，
> 已重新打开；共享 LC 仅为 `STRUCTURAL_RISK`，不是已证根因。恢复该路线必须先关闭
> `CDA-GAP-INT32MAC-MATERIALIZED-STAGE1-001` 和
> `CDA-GAP-INT32MAC-BRANCH-ISOLATION-001`，再取得用户新授权。
>
> 生成前必读资料已去重：统一入口为 `.agents/rules/生成前必读索引.md`，硬件字段按
> `.agents/rules/NDP硬件字段语义.md` 的实际触发章节条件阅读；完整迁移和 SHA 记录见
> `.agents/task_records/mandatory_read_compaction_20260724.md`。下方旧 v4/v5
> “当前可交付/E2 已闭合”段落只作历史，不再派生任务。

> 2026-07-24 双算子并行增量：GAP 旧
> `gap_int32_mac_stock_rtl_onecmd_v4` 因 `SCA_D.length` 缺失已被本地 TB loader
> 合同否决，不得上传。替代包为
> `artifacts/operator_config_validation/r5-server-test-packages/gap_int32_mac_stock_rtl_onecmd_v5.zip`
>（SHA-256
> `e8b3ae2c694c3a8a516a99541de26f6059ba9b3ba84bc5d8e532ed9db36185b7`）。
> 为并行利用服务器等待时间，第二个独立包为
> `artifacts/operator_config_validation/r5-server-test-packages/decode_max_fp32_stockrtl_onecmd_v2.zip`
>（SHA-256
> `97991bbb4a56d7636c24808cec353b2d813468309d836893cc82a698a01cec12`）。
> 两包均只需一条 `bash PREPARE_AND_RUN.sh /abs/path/NDP_copyXX`，不含功能 RTL；
> 前者是 ResNet GAP pure-config 六级归约，后者只是 DeepSeek FP32 max 控制原子，
> 不得把后者写成 ResNet INT8 MaxPool 通过。

> 2026-07-24 GAP pure-config 增量：六份 `int32_mac` stage JSON、独立
> mapping/bitstream、6×Load_Config/Start_Comp/Barrier 和 16×512 本地 golden
> E2 已闭合；旧 atomic_v1 因服务器操作过多被用户否决，未发布的 onecmd_v2
> 因 CRLF payload 未通过专项门，未发布的 onecmd_v3 因 SCA_D 数字 slice 身份
> 复核未通过而废止。当前可交付无 RTL 文件、无 RTL patch、单命令入口包
> `artifacts/operator_config_validation/r5-server-test-packages/gap_int32_mac_stock_rtl_onecmd_v4.zip`
>（SHA-256
> `51b8fde985372d52133340c88e7dd85000cea3332cfbaa1c93f45b73262b07ff`，
> 86 ZIP entries，两次 fresh build 逐字节一致）。当前仍为
> `candidate_release=false / E2_LOCAL_ONLY`，服务器 E4/E5 动态门保持。

最后更新：2026-07-24（GAP v1～v5 冻结；生成前必读资料已去重）

## 0. 当前唯一有效状态与双对话接手入口

本节是两个后续对话的唯一派工入口，优先于下文所有旧“当前状态”“下一步”和历史诊断文字。W0–W9 总体里程碑、下文第 1～17 节的阶段门、哈希合同、历史结果和禁止事项全部保留；它们继续作为背景、证据和验收边界，但不再各自派生并行任务。后续工作只从本节的“测试分析”或“代码对照分析”接手。

### 0.1 总体状态与共同不变量

- W3 保持 78/78 ONNX 节点独立公式重放匹配；typed lowering 保持 133/133 request，request-set SHA-256 为 `9da4423bb293a047c9a2dac945270d56eab9fe114146a2f6638e43c655fa341b`。
- stage→算子 JSON 的总体架构、原生 `ndp-sim` mapping/bitstream/execplan/SCA 链和代表算子本地包已经建立，但“体系存在”不等于每个字段语义、每个 shape family 或硬件行为均已证明。
- GAP sum 与 node-0004 独立 Requant 已完成本地闭合；node-0004 Conv 三波包已完成生成，但 SA 非对称布局、bias/psum、tail/keep 和跨 stage CONFIG 等语义仍不能视为闭合。
- 正式 target config、E4、E5 的统计不得因本地配置、仿真启动、内部写请求或单次局部数值匹配而擅自升级。只有满足对应合同的真实回读与重复运行才能改变正式状态。
- 服务器只读身份采集已完成：MSE0→Buffer→GA→MSE4 的 14 个关键 RTL 文件全部
  与本地 `NDP_copy01` 一致；其中 10 个与 GitHub 也一致，4 个为服务器/本地一致。
  这 4 个差异只涉及 outbuffer write-enable 暴露和 SFU delay FIFO 推进；当前
  GAP `opcode=0x0c` 不启用 SFU，因此不能解释本次分歧。整棵服务器 RTL tree、
  active filelist 和 Makefile 仍与本地聚合身份不同，且服务器无可用 git metadata，
  所以不得把 14 文件裁决扩大为全仓完全一致。
- 功能 RTL 的 `.v`、`.sv` 默认禁止修改。允许修改 testbench、加入只读探针、生成诊断包和离线分析工具，但必须证明没有改变 DUT 功能语义。用户已在 2026-07-24 明确授权唯一 `repair_v9` 例外：本地 `NDP_copy01` 仍不修改，包内只携带两个哈希门控、可逐字节恢复的 GA repair 文件；该授权不得扩展到其他 RTL 或算子。
- 所有历史失败包和原始返回保持不可变；新实验使用新 revision、新目录和新哈希，禁止覆盖原证据。

### 0.2 任务一：测试分析

**接手名称：`测试分析`**

新对话接手语句：

```text
请接手 .agents/plan.md 第 0.2 节“测试分析”，从 GAP v10 回传、两个 GA RTL blocker
和 node-0077 DequantizeLinear 候选继续。
```

目标：对用户每次返回的服务器结果做可复现的逐层验收，定位第一处真实分歧；本地证据不足时，只增加最小、只读、低扰动的 TB 观测点并生成下一版测试包，直到能够区分配置错误、testbench/loader 错误、RTL 控制错误、RTL 数值错误或身份不一致。

当前接手输入：

- 历史 GAP 返回目录：`server_returns/gap_hwop0071_sim6_20260723`；
- 当前 probe_v4 原始回传归档：
  `server_returns/gap_hwop0071_probe_v4_return_20260723/7.zip`，SHA-256
  `c95730a76449c0134e3b6c6a73919481d07cfd29f796d18dd7a638eafff3799d`；
- 当前 probe_v4 解包证据：
  `server_returns/gap_hwop0071_probe_v4_return_20260723/extracted`；
- 当前数值路径报告：
  `server_returns/gap_hwop0071_probe_v4_return_20260723/gap_numeric_path_report_v4.json`；
- 当前探针分析：
  `server_returns/gap_hwop0071_probe_v4_return_20260723/gap_probe_v4_analysis.json`；
- 当前人工诊断：
  `server_returns/gap_hwop0071_probe_v4_return_20260723/GAP_PROBE_V4_DIAGNOSIS.md`；
- 失败编译包：`gap_hwop0071_sum_probe_v1.zip`；其 installer 虽将 observer
  复制到 TB 同目录，但没有保证 VCS include 搜索路径包含 TB 根目录，服务器在
  `tb_NDP_Top_new_phy.sv` 的 include 处结束，未启动仿真；
- 已运行且冻结的 v4 包：
  `artifacts/operator_config_validation/r5-server-test-packages/gap_hwop0071_sum_probe_v4.zip`，
  SHA-256
  `7964b3715bdbf28640d0404ac8f27ac2c26a73ddc44d72edf95db05018e69f9a`；
- 当前交接物改为只读身份采集包：
  `artifacts/operator_config_validation/r5-server-identity-bundles/gap_rtl_three_way_identity_v1.zip`，
  SHA-256
  `9ea6be0e20947253aa2efe7bcc5dce90dc3139699daa2e76d6a229be27e0f17f`；
- 已生成的 probe_v6 完整测试包保持冻结但暂停，不上传、不运行、不覆盖：
  `artifacts/operator_config_validation/r5-server-test-packages/gap_hwop0071_sum_probe_v6.zip`，
  SHA-256
  `140e0fd22bb272e84c0163806177871823085c112192cbe468d7bb371d0545cf`；
- v4 显式加入 `+incdir+<NDP root>`、安装后 include/observer 预检、独立
  `run_gap_hwop0071_sum_probe_v4` 编译目录，并把 TB 的无尺寸 `RUN_TIME`
  修正为 `64'd100000000000000`；同时记录 pre-install、post-install、post-run
  的 RTL tree、active filelist、Makefile、TB、SCA 和退出状态身份；功能 RTL 不变；
- 构建与分析入口：`tools/build_gap_probe_test_package.py`、`tools/install_native_return_observer.py`、`tools/capture_gap_probe_server_identity.py`、`tools/analyze_gap_sim_path.py`、`tools/analyze_gap_probe_log.py`；
- 只读 TB 观测器：`NDP_copy01/native_return_observer.svh`。
- 当前 v10 observer/身份回传：
  `server_returns/gap_hwop0071_configfix_stockrtl_v10_evidence_20260724/`；证据 ZIP
  SHA-256 为
  `5a51b4a6aaeecdef85b8fa6c3a035b61cbdf2d3b893bd7988b3a4d55006b954d`。

修改登记（`GAP-PROBE-T0-IDENTITY-001`）：由“测试分析”维护
`tools/capture_gap_probe_server_identity.py`、
`tools/capture_gap_rtl_three_way_identity.py` 与
`tools/build_gap_rtl_identity_bundle.py`。当前动作严格收窄为读取服务器入口目录、
活动 RTL 解析路径、git 身份、RTL tree、filelist/Makefile/TB 哈希和 14 个关键文件，
再与 GitHub 锁定提交、本地 `NDP_copy01` 做三方比较。身份采集包不含 workload、
observer、SCA、bitstream、TB 或功能 RTL，不安装任何内容，不编译、不仿真、不修改
服务器文件。probe_v1 保持失败编译证据；probe_v2/probe_v3 是中间 revision；
probe_v4 已完成服务器运行并冻结；probe_v5 与 probe_v6 均保留但当前不得上传或运行。

当前已经确定、不得重新混为一个问题的两条失败分支：

1. **D 写地址配置语义问题**：LC2 在 `[0,1)` 上恒为 0，PE1 为 `LC2*1`，D stream 的 index 使用 PE1、stride=32，因此 MSE4 的 512 次写请求只落到 `0x1884/0x1885` 两个唯一地址。这是配置生成对 LC `src_id` 的含义理解错误；`src_id` 是 trigger/tag 依赖，不是数值继承。
2. **GAP 数值路径问题**：probe_v4 已推翻 sim6 阶段的“MSE0 地址重放”暂定解释。按两个物理请求/返回通道各自 FIFO 关联后，8960 个 MSE0 地址 occurrence、DDR payload 和深层窗口内 256 个 metadata/consume 全部吻合；跨通道合并日志中的 726 个顺序差异不能解释为丢失或重放。probe_v5 同 `clk_sg` 域确认 MSE4 request/wdata 均为 512，旧 511 是原生日志监视器漏记，不是 RTL 丢数。完整 2048 个 `int32` 中第 0 个 C8 block 正确、第 1 个 block 首元素开始分歧；MSE4 packing 和 GA 对给定操作数的整数加法均正确，最早错误已收窄到 block1 的 GA 最终累加操作数。下一步只静态定位 Buffer→GA inbuffer/tag/outbuffer/accumulator 状态，不再把 `clk_db` 快照当作本地 `clk_sg` 请求重放证据。

2026-07-23 接手复验：

- sim6 返回目录共 873 个文件、140885782 bytes；按
  `relative_path\0size\0file_sha256\n` 排序汇总的 tree SHA-256 为
  `e0606ce358f9a4fc0a269f18e5559540de809569b0632c8cca199d90bd4d0d67`；
- 原报告已从原始日志完整复跑：首个一致点为 slice0/request0、timestamp
  `700148000`、地址 `0x000000`；首个分歧为 slice0/request1、timestamp
  `700151000`、channel0、期望 `0x000001`、实际 `0x000002`。旧日志没有逐拍
  observer，cycle 记为 unknown；
- sim6 正常执行到 `$finish`，仿真时间 `760066875 ps`；`sim.log` 命令显示实际
  simv 根为 `/home/panqs/ndp/NDP_copy02`，而它与本地 `NDP_copy01` 等同仍是
  未证实假设，故 sim6 的 RTL/filelist 身份保持 `IDENTITY_UNKNOWN`；
- probe_v4 的 source workload tree SHA-256 仍为
  `8f644eaac10f0994cc657a23a44604de5aa1c55bbbf4371f26f3802a55d18c56`，
  observer SHA-256 仍为
  `5e8b0ebe1c139bdb398e078c9c0accdfb8431bd59740a12c217af46a7dfab22d`；
  相对 v1 未改变 workload 或观测信号，ZIP 中不含功能 RTL `.v/.sv`；
- probe_v4 payload 共 118 个文件，payload tree SHA-256 为
  `4bec69c7823c956e2e00b57ddf5d4eb4c892a75219bd649c8a005e71354b56c2`；
  已通过 13 个定向单元测试、Bash 语法检查、ZIP/manifest 逐文件哈希审计和独立
  重构包逐字节确定性复现。

2026-07-23 probe_v4 返回裁决：

- 回传 ZIP 共 31 个 entry、解压后 342580188 bytes；包 schema、安装名、payload
  tree、workload tree、observer、execplan、SCA 和 SCA_D 身份均与冻结 v4 一致；
  observer 安装前后哈希一致，功能 RTL 未被 installer 修改；
- VCS 编译为 `0 error(s), 1 warning(s)`；仿真以 `$finish` 正常结束于
  `759686875 ps`，退出码 0；
- v4 安装前服务器 TB SHA-256 为
  `00f2fe0913b4f09ef7053fe3bea830ffe026d877e2a278e19698e1b20da788c8`；
  installer 只将无尺寸 `RUN_TIME` 改为定宽声明，安装后及运行后 TB SHA-256
  均为 `e068f7500f0c71c2ba2c756f74a4519c33d13d4afe0fa4cc9f6c9e79b1e3f994`，
  与当前本地 `NDP_copy01/tb_NDP_Top_new_phy.sv` 完全一致；
- GitHub `xlsjdjdk/Trassic2.0_RTL` 当前 `master` 与锁定提交
  `e3bdebba95dec36ee8eba43caa92a326a88392cd` identical。14 个路径关键 RTL
  文件中，GitHub 与本地 10 个规范化文本完全一致；4 个差异仅位于
  `GA_PE_Outbuffer.sv`、`GA_PE/GA_PE.sv`、`GA_SFU_PE.sv` 和
  `GA_SFU_PE_Postprocess.sv`。前两项只暴露既有 outbuffer write-enable；
  后两项把 SFU delay FIFO 的读使能改为实际 outbuffer accept，但当前 GAP
  `int32_sum=5'b01100` 令 `ga_pe_sfu_valid=opcode[4]=0`，该行为差异不作用于
  本次 workload，不能解释当前第二个 C8 block 起的分歧；
- 服务器 RTL tree 为 2279 个文件、SHA-256
  `cb14f70b2766d6a518c2775544fecc5840cafc333f6ab1c231f54952b3cf4dbb`，
  与本地参考的 2265 个文件、SHA-256
  `243134c66eb3921a02b2cb1a2c0902a19a9a4d9fa7de246d74f055bd0fbbdc39`
  不同；该 tree 只统计独立 `rtl/` 目录，不含顶层 TB，因此差异不是 observer/TB
  安装造成的。active filelist 和 Makefile 也不同，且服务器未提供 git/bitstream
  身份，因此精确功能 RTL 身份仍为 `IDENTITY_UNKNOWN`；
- 正确按物理 return channel 关联后，8960/8960 DDR 返回 payload 均等于对应
  `matrix_A[address]`，unmatched/pending 均为 0；深层窗口 256/256 个 MSE0
  consume 地址与 metadata 序列一致，raw data mismatch 为 0；
- MSE4 写数据共 511 个 32-byte record（2044 个 `int32`），Golden 为 512 个
  record（2048 个 `int32`）；第 0 块的 8 个值
  `[330,113,710,43,1560,106,124,57]` 完全一致，第 1 块首元素即首次分歧；
- v6 source workload tree 仍为
  `8f644eaac10f0994cc657a23a44604de5aa1c55bbbf4371f26f3802a55d18c56`，
  observer SHA-256 为
  `491d5c69021649ab70521e5317c3d1f7ec89550474b325a2aa82e5d28bc961ff`，
  payload tree SHA-256 为
  `45d20ff1bc834a7984cf1210718b44bb7df3c87eaa1affeae688e0ab0962e5bf`；
  ZIP 中唯一 RTL-like 文件仍是只读 TB observer，不含功能 `.v/.sv`；18 个定向
  单元测试、Python 编译、Bash 语法、manifest/ZIP 文件集审计和
  `git diff --check` 均通过。

2026-07-23 probe_v5 返回裁决：

- 原始返回目录为 `E:\project\dgic\run_gap_hwop0071_sum_probe_v5`，2391 个文件、
  404 个目录、`2206490516` bytes；分析报告为
  `server_returns/gap_hwop0071_probe_v5_return_20260723/GAP_PROBE_V5_ANALYSIS.md`；
- v5 ZIP、manifest、observer 身份均与本地冻结包一致；VCS 为
  `0 error(s), 1 warning(s)`，退出码 0，`$finish` 时间 `759686875 ps`；
- v5 的四份 slice0 MSE0/MSE4 原生日志与 v4 逐字节相同。MSE0 的 8960 次
  request/return 及 1024 条深层窗口仍全部吻合；
- 同 `clk_sg` v5 observer 记录 MSE4 request=512、wdata=512，两个通道各 256，
  最终计数均衡。原生 `local_mse4_wdata.log` 唯一漏记 channel0 第 45 条
  `0x0000005c000000740000003200000079`，因此 v4 的“511 条写数据”修正为监视器
  漏记，不再作为 RTL 丢数证据；
- 完整 512 条同域写数据解码为 2048 个 `int32`：第 0 个 C8 block 与 Golden
  完全一致，第 1 个 block 首元素开始分歧，总计 match=10、mismatch=2038；
- 前四个 MSE4 block 均逐 lane 等于此前 GA 最终 `input0 + input2` 并符合固定
  packing。最新已知正确点为 `700313000` 的 block0 GA 最终操作数；最早已知错误点
  为 `700388000` 的 block1 GA 最终累加操作数，随后在
  `700413000/700416000` 写出。MSE4 丢握手、数据破坏/重排和 GA 加法算术错误已
  排除；剩余边界为 Buffer→GA 路由、GA inbuffer/tag 或累加状态控制；
- 服务器 TB 在 v5 安装前后哈希均为
  `e068f7500f0c71c2ba2c756f74a4519c33d13d4afe0fa4cc9f6c9e79b1e3f994`，
  与当前本地 TB 一致；9 个 v5 重点 RTL 文件均与本地一致。结合 GitHub 参考，
  其中 8 个三方一致，`GA_PE_Outbuffer.sv` 为服务器/本地一致且只比 GitHub 多暴露
  已有 write-enable；完整 14 文件服务器身份仍待只读身份采集；
- 归档内 `server_identity_post_run.json` 实为残留 v4：Makefile 在 `make sim`
  返回前归档，而 v5 脚本在返回后才写新 post-run JSON。因此 v5 post-run 身份记为
  缺失，不得拿旧文件补值；
- 体积过大的直接原因是 v5 强制 `DUMP_FSDB=1`、README 又要求回传 FSDB，服务器
  Makefile 将同一 338676163-byte 波形复制成三份；三份 SHA-256 均为
  `ca08c9f9aacefe8ffd5dc742df0506ae9e6f949e5d1f1232c2ac07f885964a03`。
  本次真正使用的 13 个文本/JSON 文件仅 3.364 MiB（完整返回的 0.1599%）。

2026-07-23 probe_v7 生成与交接：
- v5 已把首个真实数值分歧收敛到 GA `int32_sum` 的跨 C8 block 累加状态：block0
  最终合并正确；block1 第一个空间元素从 C=0 开始，第二个空间元素却把 block0
  已失效 outbuffer 槽中的旧 partial sum 作为 input C。结合
  `GA_PE_Inbuffer.sv` 的 `transout_initial/end_transout_initial` 选择和
  `GA_PE_Outbuffer.sv` 只清 tag、不清 data 的实现，当前分类为高置信度
  `RTL_CONTROL`；功能 RTL 仍保持只读，尚未授权写入修复。
- 旧 v6 草案因仍强制 `DUMP_FSDB=1` 且要求回传 `wave.fsdb`，冻结为未交付版本，
  不覆盖、不上传、不运行。正式下一版顺延为
  `artifacts/operator_config_validation/r5-server-test-packages/gap_hwop0071_sum_probe_v7.zip`，
  SHA-256 `c4462033fc4d59ad71121639daed70de1185c5f294264bc3847d22b6bc481893`。
- v7 workload tree SHA-256 仍为
  `8f644eaac10f0994cc657a23a44604de5aa1c55bbbf4371f26f3802a55d18c56`，
  与 v5 完全一致；包不含功能 RTL `.v/.sv`。只读 observer 新增 512 条上限的
  `GA_ACCUM_STATE`，记录 `transout_initial/calculate/counter`、outbuffer
  valid/count/pointer、两槽 tag/data 与实际 A/B/C，用于区分“无效旧槽仍被读出”
  和“transout 控制状态未重置”。
- v7 显式设置 `DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0`，服务器脚本结束后直接
  生成 `gap_hwop0071_sum_probe_v7_return.zip` 和 `.zip.sha256`。回传为严格白名单：
  observer、三阶段身份、安装报告、退出码、compile/sim、SCA/SCA_D、正式 D 回读及
  slice0 四份目标日志；禁止波形、`csrc`、`simv.daidir`、完整 run/archive、
  嵌套压缩包和无关 slice 日志。预算固定为 ZIP 16 MiB、解压 32 MiB、单文本 8 MiB。
- 本地构建结果：测试包 ZIP 3,280,763 bytes、120 entries、无重复/禁入文件；
  GAP 相关 22 项测试及 package/installer 10 项测试全部通过，Python 编译通过。
  本机 Icarus 不支持活动 filelist 的 `-F` 语法且不能解析原 TB 中多处 VCS 专用
  SystemVerilog 构造，因此完整 HDL elaboration 留给服务器 VCS；不得把该工具限制
  误记为 v7 编译失败。

2026-07-24 v10 回传、双 RTL blocker 与下一算子选择：

1. 两个 GA 问题固定为正交 blocker，不得合并成“同一个 INT8 问题”：
   - `CDA-GA-INT8-MAX-PIPE-001 / B_GA_INT8_MAX_FLOW`：GA
     `int8_max=0x0b` 的 pipeline0 缺少 INT8 backpressure 分支，影响
     `node-0002 MaxPoolUint8`；
   - `CDA-GAP-GA-ACCUM-STATE-001 / B_GAP_GA_ACCUM_STATE`：GA
     `int32_sum=0x0c` 的 outbuffer count 下溢与 invalid-slot C 复用，影响
     `node-0071 GlobalAverageSumInt32`。
2. v10 corrected-config + stock-RTL 运行中，LC2 地址坍缩已不再是原来的“两地址”
   现象；MSE0 8960/8960 请求/返回 payload 匹配。但 slice0 的 8 个普通 PE 再次于
   `700313000→700316000 ps` 从 `count=1` 回绕为非法 `count=3`，随后在两个 tag
   无效、`ob_valid=0` 时复用旧槽 C。服务器安装前后 RTL tree 均为
   `cb14f70b2766d6a518c2775544fecc5840cafc333f6ab1c231f54952b3cf4dbb`，
   14 个 focused RTL 零差异；包未修改功能 RTL。因此 GAP 根因已确定为
   `ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse`。
3. v10 外部 SIGHUP 前没有自然完成，缺 post-run 身份和完整 16×512 D readback，
   所以只闭合 RTL 根因，不提升 E4/E5；测试 harness 还应在后续新包加入独立的
   no-progress fail-fast，但它不是本次 RTL 根因。
4. 下一计算型 ResNet 算子选定为
   `r5:hwop-0077-00 / node-0077 DequantizeLinear`，形状
   `uint8[16,1000]→float32[16,1000]`。目标结构只允许使用授权
   `add_dequant` 中的 UINT8→FP32、非 transout FP32 `mac` 分支；原模板末级
   `add` 不属于 standalone Dequantize。目标 PE 的
   `transout_last_index=null`，因此不进入上述两个缺陷。
5. `View/hwop-0073-00` 虽完全不触发两缺陷，但只是 zero-copy alias，不选作下一
   计算算子；Requant/AverageRequant 命中独立
   `B_GA_INT32TOFP32_INPUT_DOMAIN`，Conv/MatMul 命中独立 SA INT8 blocker，也不选。
6. Dequantize 当前只是选择结果，不是可上传包。必须先关闭
   `B_DEQUANT_STANDALONE`、`B_DEQUANT_STANDALONE_RECIPE` 和
   `B_EXECPLAN_TYPED_TRANSPORT`，再重新走地址、mapping、bitstream、execplan、
   SCA/SCA_D、独立 golden、E4/E5。完整记录：
   `.agents/task_records/resnet50_dual_ga_rtl_blockers_and_next_operator_20260724.md`。

固定执行循环：

1. **T0 身份冻结**：记录返回 ZIP/目录哈希、服务器命令、SCA/SCA_D 实际路径、workload/package hash、RTL/filelist 身份和仿真结束原因。缺失项明确记为 unknown，不能自行补值。
2. **T1 通用验收**：核对 preload、execplan、dispatch、slice start、read request/return、compute、write address/data、completion、正式 readback 和 Golden；先找最早失败边界，不从末端 mismatch 倒猜。
3. **T2 数值路径定位**：逐 occurrence 比较地址、tag、payload 和握手周期；区分“错误请求导致正确返回错误数据”“正确请求但返回错误”“计算错误”“写回地址错误”。
4. **T3 本地裁决**：若现有日志、配置、Golden 和 RTL 足以唯一解释，形成带原始证据路径的结论，不为重复确认而继续加探针。
5. **T4 最小探针**：仍有两个以上可行假设时，只在 TB/observer 中增加能区分这些假设的信号；给出每个假设对应的预期波形/日志，不做无目标的大规模 dump。
6. **T5 新包与重跑**：从冻结 workload 生成新 revision，记录变更清单和哈希，提供唯一服务器命令与必须返回的文件清单；功能 RTL 默认不得修改，只有用户明确批准且按 `.agents/agent.md` 的 hash-gated install/backup/restore/post-restore 规则登记的 repair 包例外。默认 `DUMP_FSDB=0`，仿真和 post-run 身份完成后再构建独立白名单 return 目录，排除 `csrc/`、`simv.daidir/`、完整 archive/run tree、非目标 slice 日志和重复文件；只有限量文本事件无法裁决时才允许受限波形，且只保留一份。
7. **T6 结果交接**：将结论分类为 `TESTBENCH/LOADER`、`CONFIG_SEMANTICS`、`RTL_CONTROL`、`RTL_NUMERIC` 或 `IDENTITY_UNKNOWN`。其中 `CONFIG_SEMANTICS` 必须交给“代码对照分析”完成规则修正和回归，测试对话不得把单次现象直接推广成全局规则。

每轮必交付：

- 输入返回物身份与完整性；
- 最早一致点、最早分歧点和对应 cycle/slice/request；
- 已排除与未排除假设；
- 是否需要下一次服务器运行；
- 若需重跑：新包路径、SHA-256、与上一版的功能/TB 差异、完整命令、返回文件清单；
- 若发现配置问题：字段、当前值、期望关系、RTL/动态证据和适用范围，作为给“代码对照分析”的 handoff。

已完成步骤：只使用 `gap_rtl_three_way_identity_v1.zip` 从服务器活动 `rtl` 的真实
解析路径取得 git 身份、RTL tree、filelist/Makefile/TB 哈希，并将 14 个关键文件分别
与 GitHub 锁定提交、本地 `NDP_copy01` 做三方比较。该轮没有继续 Buffer→GA→MSE4
探针采集，没有重新包含或运行任何测试包内容，也没有修改 TB、RTL、D 配置或
workload。已执行的唯一采集命令为：

```bash
bash CAPTURE_ONLY.sh /home/panqs/ndp/NDP_copy02
```

服务器只需返回 `server_rtl_three_way_identity.json`。

上述身份采集已完成。返回文件 SHA-256 为
`1c1ad5410781d5fc33737f491bad1f2bf05ed065bca27d7db6ffdf9526a4cb74`，
裁决报告为
`server_returns/gap_rtl_three_way_identity_20260723/SERVER_RTL_THREE_WAY_IDENTITY_ANALYSIS.md`。
当前下一步改为在与服务器一致的本地 14 文件上，结合 v5 的
`700313000` 正确 block0 与 `700388000` 错误 block1，静态追踪
Buffer→GA、inbuffer/tag 和 ping-pong accumulator 控制；身份不再需要服务器重跑，
也不生成新的测试包。

### 0.3 任务二：代码对照分析

**接手名称：`代码对照分析`**

#### 0.3.10 生成前必读去重与 GAP E2 回环重开（2026-07-24）

- 公共必读矩阵集中到 `.agents/rules/生成前必读索引.md`；同一轮同一文件只读一次，
  `.agents/plan.md` 只读目标状态/blocker，不再要求通读历史。
- `算子配置规则.md` 只保留所有算子共有的 strict JSON、物化回环、mapping/execplan
  和地址/provenance；E0～E5 及回归分类由公共索引唯一拥有，LC/MSE/Buffer/SA/GA/N2N
  公式移到条件附录 `NDP硬件字段语义.md`。
- 精简前全文均移动到 `.agents/archive/*_pre_read_compaction_20260724.md`，所以版本
  身份、旧命令和历史细节仍可审计但不再属于当前必读。
- 新增 `CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001`：必须从最终 materialized JSON
  反解 transaction bytes、bank columns、buffer demand/supply、tag/last/lifetime；
  中间公式、address summary 或通用 valid 不能替代。
- GAP stage1 当前 8B 合同模型与 16B materialized JSON 不一致，旧 local E2 声明失效；
  用户已暂停 v1～v5，不生成修复包。完整记录见
  `.agents/task_records/mandatory_read_compaction_20260724.md`。

#### 0.3.9 GAP int32_mac onecmd v4 非规范回传裁决（2026-07-24）

用户提供的 `sim_results(3).zip` SHA-256 为
`1c460e6a5bbf1f7ae9479bb7e7b65cf1423c9c90854d813126a9e5a613350620`；
它是服务器 raw `sim_results`，不是输入包
`51b8fde985372d52133340c88e7dd85000cea3332cfbaa1c93f45b73262b07ff`
本身，也不是 v4 规定的 allowlist return ZIP。

已闭合的运行边界：

- TB 解析 `Repeat_Num=6`；
- execplan、六份配置和 16 slice 的 A/C 共 39 个矩阵全部写入并读回成功；
- `Exec_Base=0x001a0000, Exec_Length=10`，随后到达 `slice start`；
- 从 slice start 到终止约经过 57.77 ms 仿真时间，未观察到 completion；
- 终止原因为 VCS 明示 `Received SIGHUP`，不是 DUT `$fatal` 或自然 100ms 结束。

当前分类为 `RETURN_INCOMPLETE_EXTERNAL_SIGHUP_AFTER_EXEC_START`。这足以把停顿边界
放在 execution launch 之后，但不能在 MSE0/MSE3、buffer pairing、GA backpressure、
MSE4 或 slice completion 中唯一选根因，因为 decisive
`evidence_gap_int32_mac_stock_rtl_onecmd_v4/return_observer.log` 未包含在回传中。
因此本次不关闭任何动态 GAP E4 gate，也不反证本地 JSON/bitstream 语义。

本次新增规则 `CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001`：所有长运行 runner
必须在 EXIT/HUP/INT/TERM 上收集 observer、signal/exit status、命令、身份和受限
日志；部分回传继续禁止 simv/build tree/wave/nested archive。分析文件：
`server_returns/gap_int32_mac_onecmd_v4_return_20260724/`
`V4_PARTIAL_RETURN_ANALYSIS.md`。

#### 0.3.8 GAP 纯配置 `int32_mac` 绕行：本地通用语义进度（2026-07-24）

当前暂停原 `int32_sum/transout` RTL repair、repair_v9/v10 延伸测试和任何含 RTL
patch 的包。唯一活动路线是在 stock RTL 上用六级
`D=int32_mac(A,1,C)` 普通 GA 路径实现显式加法树。下列 E2 本地门现已全部闭合，
并已生成单命令服务器包 `gap_int32_mac_stock_rtl_onecmd_v4`；包内不含 RTL/TB
源文件，也不修改功能 RTL。

已闭合并有回归：

1. GA 三输入：opcode 14、A/C 为两个 buffer operand、B 为常数 1；inbuffer 只有
   A/C 同 tag 同时有效且下游接受时才同步消费。
2. normal outbuffer：opcode 14 不属于 transout；对全部六周期短握手轨迹穷举，
   普通 FIFO occupancy 始终在 `[0,2]`，不触发 v7 的 compaction underflow 路径。
3. 双 MSE occurrence：stock encoder 映射 A→READ_STREAM0、C→READ_STREAM3；
   buffer0/GA group0 与 buffer4/GA group2 独立，逐 stage 的 A/C occurrence、相同
   terminal tag、唯一写回地址均已枚举。
4. 地址友好物理树采用 `64→32→16→8→4→2→1`，逻辑宽度仍为
   `49→25→13→7→4→2→1`；叶 49..63 和每层逻辑尾部为显式零替代。
   6 个相邻、非重叠 region、stage1 128-byte guard、最终每 slice 512 个唯一
   128-bit D line 已在相对地址域闭合。
5. CGRA_SIM `SUM.SUM`、显式 INT32 加法树和独立 W3 golden 对 32768 个向量
   三方逐元素一致，输出 SHA-256 均为
   `f838df652cadb27110ed79084f49fd7e80445277d497e0d6e019c49132b73117`。
   该结论只证明公式/数值，不证明 JSON、bitstream 或动态路由。
6. 本地专项回归 22 项通过。合同：
   `contracts/operator_config/gap_int32_mac_bypass_v1.json`；CGRA 报告：
   `artifacts/operator_config_validation/gap-int32-mac-bypass-v1/cgra_sim_reference.json`。
7. 六份真实 stage 资产已按 config/mapping/parsed bitstream/installed bitstream/
   execplan 哈希回灌机器合同，`B_GAP_INT32MAC_REAL_STAGE_ARTIFACTS` 已从过期的
   `open` 修正为 `closed_local_e2`。RTL 进一步证明 opcode14 的 C/tag 直接来自
   inbuffer，`transout_initial`、invalid-slot stale-C 和固定减法 compaction
   对该 opcode 静态不可达；六份 JSON 已逐份检查三输入、转换、tailing、
   ping-pong 与 16B 基址对齐。机器合同 SHA-256：
   `47134849d4cca92e176c6c32ca25fdb543e0563bbabc656928cf125d46428de4`。

当前交付与仍未闭合边界：

1. 六份 address-bound JSON、通用 validator、专项 occurrence/address、独立
   mapping/bitstream、6×Load/Start/Barrier、pretty SCA/SCA_D 和本轮 local E2
   均已闭合；没有复用 repair/v10 或旧 atomic_v1 payload。
2. 当前唯一交付包为
   `artifacts/operator_config_validation/r5-server-test-packages/gap_int32_mac_stock_rtl_onecmd_v4.zip`，
   SHA-256
   `51b8fde985372d52133340c88e7dd85000cea3332cfbaa1c93f45b73262b07ff`；
   exact-set validator、LF 128-bit 文本门和两次 fresh deterministic build 均通过。
3. 用户在服务器只执行
   `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`；脚本自动安装、校验、运行、
   裁决和生成 `gap_int32_mac_stock_rtl_onecmd_v4_return.zip(.sha256)`。不调用
   Makefile archive target，回传禁止波形、build tree 和 nested archive。
4. 当前仍为 `candidate_release=false / E2_LOCAL_ONLY`。服务器尚须闭合
   16×512 正式 D readback、16 slice 双 MSE occurrence/address、六次 lifecycle、
   stock RTL 四阶段稳定身份；现有 observer 的 normal FIFO 只覆盖 bounded
   accepted-input 样本，不能冒充全周期 occupancy 证明。
5. 若自然运行没有覆盖 skew/stall/resume，须再以最小正交实验补齐；即使 v4 数值通过，
   它也只证明绕行路线，不解除历史 `B_GAP_GA_ACCUM_STATE`，并仍需独立重复 E5。

新对话接手语句：

```text
请接手 .agents/plan.md 第 0.3 节“代码对照分析”，逐项审核不确定的 stage→算子 JSON 语义并与 RTL 对照。
```

目标：对当前 stage→算子 JSON 生成规则中的每个不确定项建立可追溯语义链：

```text
stage 意图
  → JSON 字段/组合
  → bitstream 或寄存器位
  → RTL decode 信号
  → RTL 组合/时序方程
  → 数据、地址、tag、keep、完成条件的硬件效果
  → 静态约束/生成规则/严格校验器
```

证据职责：

1. RTL 用于证明“某个配置在硬件上做什么”；
2. 已测试正确的 DeepSeek 配置用于证明“哪些字段组合真实可用”；
3. ONNX/W3/typed stage 合同用于证明“当前 ResNet50 stage 需要什么”；
4. 动态测试只用于 RTL 静态分析无法唯一裁决的时序、边界或实现歧义。

固定执行循环：

1. **C0 建账**：从当前规则、合同、生成器和 validator 中列出所有 uncertain、sample-only、test-required、contradicted 项，不只检查已暴露错误的字段。
2. **C1 配置链追踪**：逐项追到 encoder/register map/RTL decode，记录位宽、signedness、默认值、枚举、合法组合和跨模块信号路径。
3. **C2 硬件效果证明**：追踪相关组合与时序逻辑，明确循环值、地址、数据、tag、last、keep、backpressure、buffer owner 和 CONFIG lifetime 如何产生。
4. **C3 stage 反向映射**：将硬件效果与 typed stage 的 shape、layout、dtype、padding、tail、quant 参数和跨 stage 连接对齐；不得仅因 DeepSeek 样例有相同字段就认定 ResNet50 应取同值。
5. **C4 规则分级**：每项标记为 `RTL_PROVEN`、`SAMPLE_SUPPORTED`、`TEST_REQUIRED` 或 `CONTRADICTED`，并写明适用 family/shape/边界。
6. **C5 测试请求**：RTL 无法裁决时，不直接猜规则；向“测试分析”提供最小可区分实验，包括互斥假设、所需输入、观察信号、通过/失败判据和对规则的不同影响。
7. **C6 规则回写**：只有证据闭合后才修改 `.agents/rules/算子配置规则.md`、机器合同、生成器或 validator；同时增加正例、反例与回归，避免只修当前算子。

首轮审核优先级：

1. LC：`src_id`、`outmost_loop`、`start/end/stride`、`last_index`，以及 value、trigger、tag、last、same 的传播关系；
2. LC_PE：输入选择、常量、mode/opcode、`keep_last`、signed/truncation，以及 LC→PE 是否传值；
3. MSE/Memory AG：`idx/mode/keep/size/stride`、地址 remapping、split、`valid/vld_d/ready` 和首拍/停顿/恢复行为；
4. padding、tailing、keep、valid mask、数据 reorder 和非对齐边界；
5. buffer spatial stride、full/last、ping-pong、owner 和读写切换；
6. SA 非对称 A/B 布局、signed-A/unsigned-B、bias/psum、row/col/tail；
7. GA opcode、terminal tag、backpressure、reduction/affine/requant；
8. N2N、跨 slice reduction、跨 stage CONFIG 状态、lifetime 和零拷贝物理交接。

首个已知规则修正项：LC `src_id` 必须先按 RTL 证明其 trigger/tag 语义并检查所有现有生成器，禁止继续解释为数值继承；然后检查该错误是否同时影响 GAP D stream、其他 reduction、Conv/Requant 地址和 terminal 条件。

每项必交付：

- JSON 字段路径和一个最小正/反例；
- register/bitstream 位置及 RTL 文件、模块、信号、方程；
- 对 stage 语义的映射和适用范围；
- 证据等级与仍未证明的部分；
- 对规则、生成器、validator、现有候选包和 133-stage 推广的影响；
- 如需测试，给“测试分析”的完整 `TEST_REQUIRED` 说明；
- 如已修正，给出新增回归和受影响产物是否必须重生成。

首轮进度（2026-07-23）：

- C0 台账与首轮 C1～C6 证据已写入
  `contracts/operator_config/stage_operator_semantics_audit_v1.json`，稳定 issue ID 为
  `CDA-LC-SRC-001`、`CDA-GAP-D-INDEX-001`、`CDA-MSE-RD-VALID-001` 和
  `CDA-MSE0-RD-REPLAY-001`。
- `CDA-LC-SRC-001=RTL_PROVEN`：encoder 将逻辑连接映射成 4-bit 相对输入端口选择码；
  RTL 只消费被选源的 `valid/last/same/last_index`，计数值只由本 LC 的
  `start/stride/end` 产生。`outmost_loop=1` 时触发改由 `slice_start_run` 提供。
- `CDA-GAP-D-INDEX-001=CONTRADICTED`：typed stage 每个 active slice 需要覆盖
  2048 个 `int32`，即 256 个 32B 输出事务基址；当前 LC2→PE1→D 链只产生 1 个事务
  基址。stage backend、catalog 和 133-stage system 已加入
  `B_GAP_D_INDEX_CARRIER_SEMANTICS` 并 fail closed；旧 GAP mapping/bitstream/execplan/
  package 均须在新 schedule 闭合后以新身份重建。
- 已检查当前主动构造 LC 链的 Conv 1×1/3×3 生成器：其 `src_id` 用作嵌套触发关系，
  需要数值相同的远端分支使用独立 root，未发现把 `src_id` 直接当数值继承的代码。
  这只排除同类解释错误，不解除其既有 SA/bias/tail/硬件 blocker。
- `C0-LC-PE` 核心语义已闭合并写入同一机器合同：
  `CDA-LCPE-PACK-001`、`CDA-LCPE-ALU-001` 和
  `CDA-LCPE-MODE-TAG-001` 均为 `RTL_PROVEN`。配置固定为两个 48-bit beat；
  add/mul/mac 分别执行低 16-bit 模乘加；唯一 buffer port 携带输出
  `last/last_index`，keep 在 `buffer_last && buffer_last_index <= threshold`
  时 inclusive 释放。
- 已把 LC_PE 的 RTL 必要条件加入严格 validator：被 opcode 使用却置空的 operand、
  被 opcode 忽略却启用的端口、浮点/分数 constant、constant 携带 source、非 keep
  端口携带 threshold 均 fail closed。65 份授权正确配置全部通过新增门；其 193 个
  LC_PE 实例由 151 个 `mul(buffer,constant,null)` 和 42 个
  `mac(keep,constant,buffer)` 构成，没有 add 实例，因此 add 仍不得自动迁移到新
  stage。
- `CDA-MSE-RD-VALID-001=RTL_PROVEN`：RD Memory AG 的 `vld_d || vld` 可在 ready
  清除当前 `vld` 后保留一拍旧地址 valid；该 valid/ready 直接进入 Datahub。
- `CDA-MSE0-RD-REPLAY-001=CONTRADICTED`：probe_v4/v5 的逐物理通道 FIFO
  关联证明 8960/8960 request occurrence、DDR payload 和深层 metadata/consume
  均匹配；旧 sim6 的跨通道位置差异及 TB 推导 `IssueCh/IssueTime` 不能绑定为
  `vld_d` replay。`CDA-MSE-RD-VALID-001` 的通用 delayed-valid RTL 方程仍成立，
  但不再作为当前 GAP 根因，也不再派发旧 probe_v1 实验。
- `C0-MSE-MEMORY-AG` 的静态语义已闭合：
  `CDA-MSE-PACK-MODE-001`、`CDA-MSE-ADDR-001`、
  `CDA-MSE-SPLIT-001`、`CDA-MSE-WR-RMW-001` 均为 `RTL_PROVEN`。
  JSON 三维向量 `[dim0,dim1,dim2]` 映射到 RTL `[port2,port1,port0]`，
  地址严格执行 `low30(Σu16(idx)×u20(stride)) → 去低4位 → 26-bit remap
  → 加 base_addr[29:4]`；`idx_size+1` 是 2 的幂事务维度，事务按 16-byte line
  产生 position/size/valid-mask。
- WR 对 partial 或 tail-mask line 执行同址 read-modify-write，新数据只覆盖
  `valid_mask & ~tail_mask`。RD/WR 的 `vld_d||vld` 动态重放风险仍保留为
  `TEST_REQUIRED`，静态方程闭合不等于首拍/停顿/恢复已证明安全。
- 65 份授权正确配置共含 177 个 stream（112 read、65 write）；全部
  `buf_idx_mode=[keep,buffer]`，即 row keep、col buffer。四个精确 GEMM stream
  的 legacy `mem_idx_mode[2]=0` 由原生 mapper 编码为 null；strict target 仍要求
  typed null 和逐字段编码等价 materialization。memory constant mode 在授权语料中
  没有样例，只有 RTL 方程证据。
- 严格 validator 已新增 MSE companion-field 门：memory buffer/keep 必须有 source，
  null/constant 不得依赖 source，constant 必须给 8-bit pattern；Buffer AG 只允许
  buffer/keep；启用 ping-pong 必须有 inclusive terminal threshold。
- `C0-PADDING-TAIL-KEEP` 的静态链已闭合：
  `CDA-MSE-LANE-BOUND-001` 与 `CDA-PADDING-TAIL-DATA-001` 均为
  `RTL_PROVEN`。per-lane JSON 顺序坐标由 `transfer_bias+lane` 按
  `idx_size+1` 的内层 bit mask/shift 还原；enabled low/up 为 inclusive，三维越界 OR。
- padding/tail conceptual mask 会左移首片非对齐 `position` 后再与 physical valid
  lane 对齐；prefix rank 只压紧 valid lane，不删除 padding/tail replacement。
  RD 固定为 padding byte 优先、tail 置零、否则 DDR；WR 以
  `valid_mask & ~tail_mask` 选择新 byte，其余保留旧 DDR。
- 授权语料只有 3 个启用 padding 的 read stream，没有启用 tailing 的样例；tail
  仍只有 RTL 方程证据。三份 padding 的 null value 原生编码为 0，派生 strict target
  仍需哈希绑定的 padding contract 显式物化该 byte；一份 legacy write 的 read-only
  padding keys 继续走编码等价 materialization。

- `C0-BUFFER` 静态语义已闭合：
  `CDA-BUFFER-AG-001` 与 `CDA-BUFFER-MANAGER-001` 均为 `RTL_PROVEN`。
  Buffer AG 的 lane 地址为 `row_i=row`、
  `col_i=low5(col+stride[i])`，再分解成 `bank=col[4:2]` 与
  `byte=col[1:0]`；列溢出模 32 回绕且不向 row 进位。
- 物理绑定固定为 A/READ0→buffer0/1、B/READ1→buffer2、
  B′/READ2→buffer3、C/READ3→buffer4、buffer5→WRITE0；仅 A/READ0
  有真实 ping-pong 对。write stream 的第二选择是常量 ready/zero data，严格配置
  禁止启用。
- buffer0～4 由 MSE 写、Array 读，buffer5 由 Array 写、MSE 读；
  `dst_port` 实际是 buffer5 的 Array 写源（0=SA、1=GA），对 buffer0～4 不选择
  目的端。`mask` 是 Array/N2N bank mask，不是 MSE spatial lane mask。
- `buffer_life_time=L` 编为 L-1。mode0 按 life 外层、row 内层遍历；mode1 按 row
  外层、life 内层遍历。65 份授权配置共有 193 个 buffer，112 个 read stream 的
  stream/buffer full threshold 全匹配；5 个启用 ping-pong 的样例全为 A/READ0 且
  buffer0/1 配置相同。

- `C0-SA` 静态方程已闭合。`CDA-SA-PACK-TOPOLOGY-001`、
  `CDA-SA-ACCUM-TAG-001`、`CDA-SA-OUTPORT-001` 为 `RTL_PROVEN`；
  `CDA-SA-INT8-CSA-001` 与 `CDA-SA-FP-CONVERT-001` 为 `CONTRADICTED`。
  SA 配置不是旧注释所写的 24 bit，而是 32 bit；gemm=0 启用 8×8 PE，gemv=1
  只启用第 0 行 1×8 PE。
- 三个 SA 输入物理绑定固定：inport0=buffer0/1 且按 PE row 广播，
  inport1=buffer2/3 且按 PE col 广播，inport2=buffer4/常量零且按 col 广播。
  inport2 没有真实 ping-pong 对。切换条件为已接受
  `last && last_index<=pingpong_last_index`；启用 ping-pong 时首源 last 被隐藏，
  只传播第二源 last；`nbr_enable` 再屏蔽该 last，后续完成归 N2N。
- bias 关闭时每个 psum slot 由零初始化；bias 开启时 buffer4/inport2 每次握手将同一
  bias 写入 `p,p+4,p+8,p+12`，四拍填满 16 项。A/B valid 才触发 FMA，inport2
  不参与 operand-match。对于上游 last index `i` 与 transout `T`：
  `i>T` 继续累加，`i=T` 关闭/switch accumulator bank 但不输出 last，
  `i<T` 关闭 bank 并传播 result last。
- INT8 端口方向确为 DataA 四个 signed byte、DataB 四个 unsigned byte、C 为
  32-bit psum，但当前 RTL **不是**普通四项点积。17-bit `CSA_4to2` 的 carry 已左移，
  `SA_PE_Mul_Array` 又在 `last_B` 左移一次，实际为
  `psum + signext(sum17) + (signext(carry17)<<1) mod 2^32`。四个 `1×1`
  得 6 而非 4，四个 `(-1)×1` 得 -6 而非 -4。现有 signed-A/unsigned-B
  Conv/MatMul 合同只能证明角色方向，不能再批准数值等价；必须等待活动 RTL 修正或
  取得与本地源码不同的服务器综合实现身份证据。
- outport 的 legacy JSON `col→bit0` 保持 `[out][source]`，`row→bit1` 执行转置；
  gemm 每端口串行 source0..7，gemv 只消费 source0；FP16/BF16 narrowing 每两个
  16-bit 结果打包为一个 32-bit word。FP16 会把 exponent<=0x70 全部冲成 signed
  zero，没有 subnormal；FP16/BF16 在“保留 fraction 全 1、guard=1、sticky=0”的
  exact-half tie 会把 fraction 清零却不进 exponent，例如 `0x3ffff000→FP16
  0x3c00` 而非 IEEE RNE `0x4000`。因此完整 IEEE narrowing 假设被推翻。
- 65 份授权配置中只有 8 份启用 SA，全部为 FP16、bias=0；没有 INT8/BF16/
  enabled-bias 样例。16 个 inport0/1 ping-pong 实例的阈值均与对应两只物理 buffer
  的 full threshold 相等。validator 已加入 SA companion、bias/inport2、固定物理对和
  threshold 一致性门，并对 INT8 报告精确非普通点积事实。

GA/N2N 静态代码对照已闭合：

- GA 的 20-bit inport、12-bit outport、144-bit PE packing，4×4 邻接/输出路由，
  全部 opcode 的 A/B/C 方程、odd-column SFU 限制、operand mode、transout
  `< / <=` 边界及输出打包已追到 RTL，并由微模型/validator 固化；
- GA 发现两个数值反证组：INT32→FP32 将 `-1` 与真正 `INT_MIN` 的特殊处理颠倒；
  `int8_max` 实为 unsigned bytewise min，且 INT8 pipeline0 缺 ready 分支。原生
  MaxPool 配置仍是正确的配置语料，但当前 RTL 执行语义不能实现其算子合同；
- N2N 已闭合 low 28-slice/high 4-slice ring、`mem_loop-1` 次四行物理传输、
  stream0→buffer0/1 与 stream1→buffer2/3 的固定拓扑。`ping_pong` bit 虽解码但
  未连接，硬件无条件交替；`nse_enable` 完成后也不会自行清除；
- 60 份 GA 配置/511 个 PE 与 3 份 N2N 配置均完成授权身份统计，新增 strict
  validator 规则对两套已授权 JSON 扫描无误判。合同状态进入
  `C1-DYNAMIC-CONFORMANCE`。

#### 0.3.1 二次复核后的整体链路总览（2026-07-23）

本节以下状态优先于第 11～16 节中较早的“candidate JSON=2”“GAP 只待硬件”等叙述。
底层字段方程已经闭合，不等于 typed stage 已能生成可执行配置；后续统一把状态拆成：

1. `json_emitter_ready`：typed stage 能确定地产生完整、严格、address-unbound JSON；
2. `rtl_semantics_compatible`：该 JSON 在当前活动 RTL 上确实实现目标算子方程；
3. `dynamic_release_ready`：地址、mapping、bitstream、execplan、SCA、独立 golden、
   服务器 E4 和重复 E5 均已通过。

当前三层不得再合并成一个 “ready”：

| 链路层 | 当前事实 | 当前缺口 |
|---|---|---|
| ONNX→软件语义 | 78/78 ONNX 节点独立公式重放匹配 | 无本轮新增缺口 |
| ONNX→typed hardware stage | 78 个 node 已拆成 133/133 request，10 个 family，request-set SHA-256 固定 | request 完整不表示物理 schedule/JSON 已实现 |
| typed stage plan | 133/133 均有唯一 family plan、shape signature、typed parameter schema 和字段 owner | 多数 plan 只是 blocker/next-action 声明，还不是逐字段值推导 |
| JSON 字段→RTL | 28 个稳定 finding：20 `RTL_PROVEN`、8 `CONTRADICTED`；LC/LC_PE/MSE/padding/buffer/SA/GA/N2N 静态方程已建账 | 通用 MSE 动态 conformance 仍在 C0 ledger 保持 `TEST_REQUIRED`，但旧 GAP replay finding 已被 v4/v5 推翻 |
| stage→JSON emitter | 133 个 stage 均有三轴；结构上 `json_emitter_ready=2`（MaxPool、GAP），View 为 1 个 zero-copy alias | 结合 RTL 语义 gate 后 candidate JSON=0、alias=1、stage-system blocked=132 |
| 当前 RTL 可执行语义 | MaxPool `int8_max`、Conv/MatMul SA INT8、Requant/AverageRequant 的 INT32→FP32、GAP D-index 与 block1 累加状态均已回灌 blocker | `rtl_semantics_compatible=1` 仅为 View 的本地 alias 语义；所有动态发布仍为 0 |
| formal target / E4 / E5 | 正式 target config 0/133，E4=0，E5=0 | 必须先闭合 emitter＋RTL 兼容，再做动态晋级 |

机器合同已完成 P0 收敛：

- `resnet50_r5_lowering_bundle.json` 对每个 request 记录
  `json_emitter_ready/rtl_semantics_compatible/dynamic_release_ready`，并将历史
  blocker resolution 与新 RTL semantic blocker 分栏保存；
- MaxPool、GAP 均为“结构 emitter 已存在但 RTL 语义阻塞”，
  `candidate_config_emission_allowed_count=0`；
- `stage_backend_catalog_v1.json`、`stage_config_system_v1.json`、
  `resnet50_project_closure.json` 和 `resnet50_e4e5_handoff_readiness.json`
  已重建为一致统计；历史 MaxPool/node0004 包只标记
  `historical_package_integrity`，不再列为当前 E4 可执行候选；
- 当前统一统计为：133 stage、2 emitter-ready、1 RTL-compatible alias、
  0 candidate JSON、1 zero-copy binding、0 dynamic release、E4=0、E5=0。

后续仍必须保持三轴分离，不得再用“本地候选存在”或“resolution overlay 已放行”
替代硬件 stage→JSON→RTL 的完整确认。

#### 0.3.2 十个 family 的当前真实状态

| family（stage 数/shape 数） | 已完成 | 尚未完成 / 当前裁决 |
|---|---|---|
| `MaxPoolUint8`（1/1） | 精确 3×3s2p1 ScheduleIR、`[28,28,8]` wave 和 strict JSON emitter 已实现 | 当前 RTL `int8_max` 实为 unsigned bytewise min，且首项后 pipeline0 锁死；保留为 encoding/config 正例，执行语义 `RTL_BLOCKED`，等待修复版 RTL 身份与重跑 |
| `View`（1/1） | typed 零拷贝 alias 规则已实现 | 还需证明 GAP producer 与 MatMul consumer 的 allocation、byte offset、layout、lifetime 完全同址；不生成 JSON |
| `GlobalAverageSumInt32`（1/1） | `xzp=0`、49 元素、8-lane `int32_sum`、padding identity、单 slice 完整 sample 的逻辑/数值规则已闭合 | 当前 LC2→PE1→D 只产生 1 个而非 256 个事务基址；旧 GAP mapping/bitstream/execplan/package 已失效；v5 的 block1 GA 累加状态分歧仍需独立裁决 |
| `RequantizeUint8`（54/20） | 授权 quant 模板、node-0004 的 64 multiplier/8 lane/24 shard、本地 3,211,264 元素理想公式重放与完整独立包已存在 | 通用 emitter 未接入 backend；Conv→Requant 物理交接未闭合；更重要的是模板使用已被反证 corner 的 `int32tofp32`，现有 numpy replay 不是 bit-accurate RTL converter 证明 |
| `QLinearAddUint8`（17/5） | 有授权 `add_dequant` 相关模板与 GA add/affine 结构证据 | 双输入量化域、两支 dequant、输出 requant、tail/transport 和终止尚未组合成精确 stage recipe |
| `QuantizeLinear`（2/2） | 有 INT32→UINT8 相关模板 | ONNX stage 输入是 FP32；FP32 输入路径、rounding、saturation 和两个 shape 的独立终止未闭合 |
| `DequantizeLinear`（2/2） | `add_dequant` 内嵌分支给出 `(x-zp)*scale` 结构 | 尚未抽出单输入、独立终止、严格可发射的 dequant schedule |
| `AverageRequantizeUint8`（1/1） | GAP sum 和 quant 模板可提供组成部件 | `/49`、output qparam、2048 channel dispatch、sum→requant CONFIG/lifetime 交接尚未反向复现 |
| `ConvInt32Accumulate`（53/20） | node-0004 三波 `[28,28,8]` 控制/地址/包完整；LC、stream、buffer、SA 拓扑方程已闭合 | node-0004 不是授权正确模板；当前 SA INT8 CSA 方程不是普通点积，故 53 stage 全部 `RTL_NUMERIC_BLOCKED`；bias/psum、20 shape 的 wave/padding/tail 和 Conv→Requant 交接仍未形成公共 emitter |
| `MatMulInt32Accumulate`（1/1） | 有授权 FP16 local/ring GEMM 拓扑和 N2N 结构证据 | 目标是 INT8 `M16×N1000×K2048`；当前 SA INT8 同样被 CSA 反证，N1000/K tail、psum 和终止未闭合 |

65 份授权正确 JSON 仍是配置组合的高强度基线；其中 6 份因 legacy inert 字段或
integer-zero/null sentinel 不能直接通过 strict schema，只允许做逐字段编码等价
materialization。这是“原配置正确、派生 strict 副本需裁决”，不是把授权样例降级。

#### 0.3.3 下一步执行计划

按下面 P0→P6 顺序推进。每个包都必须同时产出规则、机器合同、正反例和重建影响；
未达到退出条件不得进入下一层的批量推广。

**P0：收敛机器总账与旧证据（已完成，2026-07-23）**

目标：让 lowering、audit、backend、stage-system、project-closure 和 E4/E5 handoff
对同一 stage 给出一致但分层的状态。

动作：

1. 在 machine contract 中新增或统一三轴状态：
   `json_emitter_ready`、`rtl_semantics_compatible`、`dynamic_release_ready`；
2. 将以下静态反证回灌到 family blocker：
   - MaxPool：`B_GA_INT8_MAX_NUMERIC`、`B_GA_INT8_MAX_FLOW`；
   - GAP：`B_GAP_D_INDEX_CARRIER_SEMANTICS`、`B_GAP_GA_ACCUM_STATE`；
   - Requant/相关 GA affine：`B_GA_INT32TOFP32_INPUT_DOMAIN`；
   - Conv/MatMul：`B_SA_INT8_CSA_NUMERIC`；
   - 真正使用 N2N 的 schedule：`B_N2N_CONFIG_LIFETIME`；
3. 用 probe_v4/v5 已证明的 MSE0 request/return occurrence 全匹配证据复核
   `CDA-MSE0-RD-REPLAY-001`；旧 sim6 “1264 地址 replay”不得继续作为当前根因；
4. 登记新的 `CDA-GAP-GA-ACCUM-STATE-001`，绑定 v5 的 block0 正确点
   `700313000` 和 block1 首个错误点 `700388000`，静态追
   Buffer→GA inbuffer/tag/transout/accumulator bank；
5. 重建 resolution overlay、lowering bundle、backend catalog、stage-system、
   project-closure 和 handoff readiness，禁止保留互相矛盾的 ready 数字。

退出条件：

- 133 个 stage 均同时具有 emitter/RTL/dynamic 三轴状态；
- GAP 不再出现在可发射 JSON 计数中；
- MaxPool 可以保持 emitter-ready，但必须明确 RTL-incompatible；
- 旧 project-closure、0.3 和 stage-system 的统计完全一致。

完成证据：

- audit finding 已更新为 28 条；`CDA-MSE0-RD-REPLAY-001=CONTRADICTED`，
  新增 `CDA-GAP-GA-ACCUM-STATE-001=CONTRADICTED`；
- lowering 三轴统计为 `2/1/0`，candidate JSON=0、zero-copy=1；
- backend 对 MaxPool/GAP materialization 均以精确 RTL blocker fail closed；
- handoff 的当前 server-test candidate=0，历史完整包=2；
- 89 项定向回归通过：audit 13、strict validator 39、resolution overlay 4、
  lowering 5、backend 6、stage-system 6、project-closure 4、handoff 5、
  历史语义合同/包 7。

**P1：建立逐 stage 的“字段值推导矩阵”（已完成，2026-07-23）**

目标：把当前“每字段有 owner”推进为“每字段为什么取这个值”，这是
hardware stage→operator JSON 确认的核心交付。

新增机器入口建议：
`contracts/operator_config/stage_json_derivation_matrix_v1.json`。每个代表 request
至少逐字段记录：

- JSON path；
- semantic owner；
- 值来源类型：typed parameter / shape equation / authorized exact template /
  RTL constant / derived schedule / late-bound address；
- 推导方程和 rule ID；
- 合法域、默认值和 companion fields；
- encoder bit range、RTL consumer/finding ID；
- 当前证据等级和 blocker；
- shape 参数化范围，以及是否允许从代表推广。

首批代表固定为：

1. `r5:hwop-0071-00` GAP；
2. `r5:hwop-0004-01` Requant；
3. `r5:hwop-0002-00` MaxPool；
4. `r5:hwop-0073-00` View（记录为 alias 字段矩阵，不伪造 JSON）。

当前具体落地顺序：

1. 新增 `stage_json_derivation_matrix.py` 与
   `contracts/operator_config/stage_json_derivation_matrix_v1.json`，schema 先固定
   source binding、request identity、leaf JSON path、owner、value-source、
   equation/rule、合法域、encoder/RTL consumer、evidence level、blocker 和
   shape-generalization scope；
2. 第一批先录 GAP 与 MaxPool：从现有 strict JSON 逐叶枚举，区分
   `typed/shape-derived/authorized-template/RTL-constant/late-bound-address`，
   并明确记录它们虽然 emitter-ready、但为何 RTL-incompatible；
3. 第二批录 View alias：证明无 JSON、allocation/offset/layout/lifetime 尚未闭合，
   防止把 zero-copy disposition 误写成动态 release；
4. 第三批录 exact Requant `r5:hwop-0004-01`：先只建值来源和
   `B_GA_INT32TOFP32_INPUT_DOMAIN`，不在 bit-accurate replay 前放行 emitter；
5. 增加逐叶完备性、唯一 owner、typed 参数扰动、绝对地址禁止复制、未知来源
   fail-closed 和 checked-contract hash 回归；
6. P1 只建立可执行推导矩阵，不修改功能 RTL，也不运行冻结 probe_v6。当前
   `tools/analyze_gap_probe_log.py` 已具备 `GA_ACCUM_STATE`/invalid-slot 判别入口，
   但没有 v6 回传前只能作为 P2 的候选判据，不能升级动态 finding。

退出条件：

- 代表 stage 的每个 emitted JSON leaf 均有且仅有一个可执行推导；
- 地址字段明确标为 late-bound，不能从模板复制绝对地址；
- 修改任一 typed shape/qparam 后，要么确定地产生新值，要么以具体 blocker 失败；
- 可由测试重新生成并逐叶比较，不允许自由文本规则替代机器值。

完成证据：

- `contracts/operator_config/stage_json_derivation_matrix_v1.json` 覆盖 4 个代表
  stage、3 份 JSON 投影和 1 份 View alias，共 1368 个 JSON leaf；每个 leaf
  都有唯一 owner、值来源、方程/规则、合法域、encoder/RTL consumer 和 blocker；
- GAP 投影已切换到
  `configs/stage_codegen/hwop-0071-00-d-index-v1/config.json`，并绑定
  `gap_d_index_schedule_v1.json`；矩阵只在该派生配置范围消去
  `B_GAP_D_INDEX_CARRIER_SEMANTICS`，仍保留 `B_GAP_GA_ACCUM_STATE`；
- 绝对地址 6 项全部保持 late-bound；当前 candidate JSON 仍为 0；
- `tests.test_stage_json_derivation_matrix` 6 项通过。

**P2：修复 GAP stage→JSON，并裁决 v5 累加状态（本地完成，服务器观测待回传）**

动作：

1. 从 typed 输出 `[16,2048,1,1]×int32` 推导每 active slice 8192B、
   256 个 32B D 事务，设计显式数值 root/LC/PE 链产生 `0..255`，禁止使用
   `src_id` 数值继承；
2. 同时证明 D carrier 的 tag、last、keep、completion 和 `last_index=0`，
   不能只把 `LC2.end` 改成 256；
3. 对新 schedule 运行 `require_gap_d_index_coverage()`、strict validator、
   地址/mapping/bitstream/execplan/SCA 双跑与独立 D golden；
4. 使用全新 config/candidate/package 身份，旧 GAP 派生产物只保留为 invalidated；
5. 若 `CDA-GAP-GA-ACCUM-STATE-001` 表明 block1 分歧独立于 D carrier，则在发射器
   放行前保留第二 blocker，不用地址修正掩盖 GA 状态问题。

退出条件：

- 静态覆盖恰为 256/256，不是只满足最小地址数量；
- 首末事务、channel block 顺序、terminal chain 与 typed layout 一致；
- 新 JSON 可从 typed request 确定重建，且不读取旧失败 candidate；
- 静态和本地数值均通过后才申请新的 E4/E5 测试。

本地完成证据：

- 新 D-index schedule 使用独立 `LC2` 数值 root：`0..255`，经 `PE1×1`
  产生 256 个互异 32B D 基址，覆盖 8192B/slice；tag/fanout/terminal
  `last_index=0` 同链闭合；
- strict validator issue=0，原生 mapping penalty=0；合同为
  `contracts/operator_config/gap_d_index_schedule_v1.json`；
- GA 静态方程已证明：当 `transout_initial>=2 && !calculate` 时，匹配不要求
  inport2 valid，且 C 直接读取未清零的 outbuffer data、没有 valid guard；
  因而存在 invalid slot stale-data 反例。精确服务器运行是否到达该状态仍须 v7
  `GA_ACCUM_STATE` 观测，不能用静态可达机制冒充动态 occurrence；
- 唯一当前服务器包为
  `gap_hwop0071_sum_probe_v7.zip`，SHA-256
  `c4462033fc4d59ad71121639daed70de1185c5f294264bc3847d22b6bc481893`。

**P3：闭合 GA affine/requant 公共分支（INT32 输入域本地完成，执行解冻待 RTL 决策）**

先做 `r5:hwop-0004-01 RequantizeUint8`：

1. 对精确 W3 accumulator 统计 `-1`、`INT_MIN` 及完整 min/max/domain；把
   `ga_int32_to_fp32_rtl_trace()` 接入 bit-accurate 全张量 replay；
2. replay 必须覆盖 RTL 的 INT32→FP32、乘 multiplier、加 magic、bit reinterpret、
   INT32 subtract 和 UINT8 saturate；当前 numpy 理想转换 mismatch=0 不能替代此门；
3. 若精确输入命中反例，立即标记当前 RTL 不兼容；若精确代表未命中，只能产生带
   输入域 guard 的 exact-stage emitter，不能直接推广到 54 stage；
4. 将 typed `x_scale/w_scale/y_scale/y_zero_point` 映射到 8-lane constants、
   channel shard、stream/GA mask、wave 和 CONFIG transition；
5. 通过原生 `model_execplan` handler 生成，不在根项目复制一套 LC/stream patcher；
6. 将 node-0004 exact emitter 接入 `lower_stage_request()`，再按 20 个 shape variant
   聚类推广。

随后依次闭合：

1. standalone `DequantizeLinear`；
2. FP32-input `QuantizeLinear`；
3. 双 qdomain `QLinearAddUint8`；
4. `/49` `AverageRequantizeUint8`。

每个子族退出条件：

- 先反向生成一个授权模板并达到 bit-identical 或逐字段编码等价；
- 一个非对称 ResNet 代表通过字段矩阵、strict JSON、mapping/execplan 和独立 golden；
- qparam 改动能机械改变对应 constant，不能保留模板常数；
- shape/tail/CONFIG 规则闭合后才批量发射同 shape variant。

当前本地结论：

- node-0004 的 3,211,264 个 accumulator 已完整做 bit-accurate
  INT32→FP32→multiply→magic add→reinterpret→subtract→UINT8 clip；
  128 个 `-1` 命中 RTL 反例，最终虽都被饱和到 0 而保持 UINT8 mismatch=0，
  但中间转换不等价，`B_GA_INT32TOFP32_INPUT_DOMAIN` 不解除；
- `ga_int32_input_domain_matrix_v1.json` 已扫描全部 54 个 Requant 和 1 个
  AverageRequant 的正式 W3 int32 输入，共 169,442,944 元素；45/55 stage
  命中反例，共 6640 个 `-1`、0 个 `INT_MIN`；其余 10 个只证明本次 W3
  未命中，不构成通用输入域证明；
- 因活动 RTL 的通用转换已被反证，继续物化 Add/Quant/Dequant/
  AverageRequant 的发布级 emitter 需要先做功能 RTL/目标版本决策；本轮不以
  模板常量或最终饱和掩盖中间语义缺陷。

**P4：SA INT8 分支按“控制可盘点、数值执行冻结”推进（安全本地边界已闭合）**

动作：

1. 将 `CDA-SA-INT8-CSA-001` 传播到全部 53 个 Conv 和 1 个 MatMul stage；
   在当前 RTL 未修复前禁止任何 formal target/E4 晋级；
2. 不等待 RTL 修复即可继续完成与算术独立的控制工作：
   - 20 个 Conv shape 的 loop、K16/output-channel tile、`[28,28,8]`/其他 wave、
     stride/padding/spatial tail、bias/psum lifetime 和跨 wave CONFIG；
   - MatMul `M16×N1000×K2048` 的 N/K tail、local/ring 选择和 completion；
   - Conv D HWC16→Requant A HWC8 的 K8 half offset、64B spatial stride、
     slice owner、buffer lifetime 和同一 execplan 交接；
3. node0004 只作诊断反例，不作为配置正确性来源；公共规则必须来自授权模板、
   register/encoder 和 RTL；
4. 向“测试分析”交付固定微向量：四个 `1×1`、四个 `(-1)×1`、bias on/off、
   两个 psum wave 和非对称 row/col，要求绑定修复版 RTL/filelist 身份。

数值解冻条件：

- 修复版活动 RTL 对 micro-model 与 conventional dot 均一致；
- bias/psum 跨 wave 回读正确；
- 一个 1×1 非对称代表通过 E4/E5 后，才按
  1×1s1→1×1s2→3×3/padding→channel/spatial tail 推广。

当前本地结论：

- 53 个 Conv 已精确归并为 20 个 logical-geometry signature；MatMul 固定为
  `M16×N1000×K2048`，全部 54 个 SA stage 均继承
  `B_SA_INT8_CSA_NUMERIC`；
- 授权正确 SA 参考全部为 FP16，没有可为这些 INT8 signature 提供物理
  tile/loop/wave/tail/psum/lifetime 方程的 exact template；因此本轮只登记
  完整 shape inventory，不从 ONNX 逻辑 shape 猜造物理 CONFIG；
- 后续物理 schedule 不是遗漏的只读代码检索，而是以修复版/选定目标 RTL 和
  授权 INT8 控制基线为前置的配置开发工作。

**P5：闭合跨 stage 状态、View 和必要的 N2N（逻辑层完成，物理层有前置阻塞）**

动作：

1. 沿 78 个 node stage DAG 生成 ordered `CONFIG update/reuse/disable` 序列，
   对每条 internal edge 明确 buffer owner、layout、地址 alias/copy 和 lifetime；
2. 对 `View` 证明 producer/output 与 consumer/input 的 allocation、byte offset、
   element order 完全相同；任一不同时降级为需要真实 copy/relayout 的 stage；
3. 只有某个 ResNet schedule 实际需要跨 slice 传输时才启用 N2N；同时要求
   physical pair、hard-wired ping-pong、`mem_loop-1` 传输数和
   clear/reconfigure 边界全部显式；
4. GAP 当前每 slice 含完整 sample，不得为“看起来像 reduction”而加入 N2N；
5. 给 N2N stream1/mixed-selector 保留 sample-gap，除非 typed schedule 明确需要，
   不把它作为整网主线的前置工作。

退出条件：

- 133-stage ordered plan 不依赖隐式寄存器残留；
- 每条零拷贝边都有静态地址/layout 等价证明；
- 每条物理 copy/N2N 边都有字节数、次数、终止和清配置证明。

当前本地结论：

- `stage_state_lifetime_contract_v1.json` 已闭合 133-stage 顺序和 148 条 typed
  tensor edge，identity mismatch=0，禁止任何 implicit prior state/reuse；
- View 的 `(16,2048,1,1) FP32 → (16,2048) FP32` 逐字节完全相同，
  131072B SHA 一致，故逻辑 alias 成立；但 producer/consumer 物理 allocation、
  byte offset 和 lifetime 尚不存在，不能升级为物理 zero-copy；
- 当前 typed plan 的 N2N stage/blocker/config 均为 0，GAP 每 slice 已持有完整
  sample，不需要 N2N；
- 由于当前 candidate config=0，132 个计算 stage 的 CONFIG update/reuse/disable、
  地址、buffer owner 和 lifetime 不能在没有物理配置时凭空编码。

**P6：代表放行、family 推广和整网闭环**

固定放行顺序：

1. 完成 P0～P3 后，优先 GAP 与一个 exact Requant；
2. 完成 RTL 修复后，放行 MaxPool；
3. 完成 SA INT8 修复后，放行 Conv 1×1 代表与 MatMul tail 代表；
4. 再放行 Dequant、Quant、Add、AverageRequant；
5. 每个代表必须先 E4，再以同一 package/config/RTL 身份完成重复 E5；
6. 只有某 family 的全部 shape variant 都由同一参数化规则覆盖，才批量生成对应 stage；
7. 最后生成 133-stage ordered config/alias plan，重跑 78-node 地址、layout、
   lifetime、terminal 与独立 golden，之后才组装整网服务器包。

每个工作包的统一验收命令至少包含：

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\build_stage_operator_semantics_audit.py
& $py tools\build_r5_resolution_overlay.py
& $py tools\build_r5_lowering_bundle.py
& $py tools\build_stage_config_backend_catalog.py
& $py tools\build_stage_config_system.py
& $py tools\build_stage_json_derivation_matrix.py
& $py tools\build_gap_d_index_schedule.py
& $py tools\build_gap_ga_accumulator_state.py
& $py tools\build_requant_stage_semantics_evidence.py
& $py tools\build_ga_int32_input_domain_matrix.py
& $py tools\build_stage_state_lifetime_contract.py
& $py tools\validate_gap_probe_test_package.py
& $py tools\build_operator_semantics_local_closure.py
& $py tools\build_project_closure.py
& $py tools\build_e4e5_handoff_readiness.py
& $py -m unittest tests.test_stage_operator_semantics_audit `
  tests.test_operator_config_validator tests.test_stage_config_backend `
  tests.test_stage_config_system tests.test_stage_json_derivation_matrix `
  tests.test_gap_d_index_schedule tests.test_gap_ga_accumulator_state `
  tests.test_requant_stage_semantics_evidence `
  tests.test_ga_int32_input_domain_matrix `
  tests.test_stage_state_lifetime_contract `
  tests.test_build_gap_probe_test_package `
  tests.test_operator_semantics_local_closure tests.test_project_closure `
  tests.test_e4e5_handoff -v
```

上述计划的核心完成定义是：不只拥有 133 条 plan，而是每条 hardware stage 都能从
typed intent 机械推导全部 JSON/alias 字段，当前 RTL 对其数值与控制语义兼容，且代表
shape 已通过独立 golden 和 E4/E5。任何一层被反证都必须 fail closed，不能用模板复制、
候选目录存在或历史服务器日志跳过。

#### 0.3.4 本轮本地收口与唯一下一步（2026-07-23）

机器总入口为
`contracts/operator_config/operator_semantics_local_closure_v1.json`，状态是
`local_static_analysis_exhausted_release_blocked_server_gap_ga_observation_ready`。
它绑定 28 条 audit finding、133-stage system、1368-leaf 推导矩阵、GAP D/GA、
55-stage INT32 输入域、状态/生命周期合同和 v7 服务器包。

需要区分两层 GAP blocker：

- `stage_config_system_v1.json` 继续描述原始 lowering/旧模板基线，因依赖图不能反向
  引用依赖 lowering 生成的 GAP-D 合同；
- 下游 `stage_json_derivation_matrix_v1.json` 和 local closure 对全新
  `hwop-0071-00-d-index-v1` 派生配置消去 D-carrier blocker，只剩
  `B_GAP_GA_ACCUM_STATE`。这不是静默改写旧审计 finding，也不改变 candidate=0。

当前不再有能安全解除 release blocker 的纯本地只读分析项。唯一即时动作是用户在
服务器运行 v7 包，并只返回：

```text
gap_hwop0071_sum_probe_v7_return.zip
gap_hwop0071_sum_probe_v7_return.zip.sha256
```

回传后用 `tools/analyze_gap_probe_log.py` 按
`matched && trans_init>=2 && !calc && !ob_valid && input2==outbuffer_data[rd_ptr] && input2!=0`
裁决精确 occurrence。其余下一步均需
先选择/修复功能 RTL（GA INT32 conversion、GA accumulator、SA INT8 CSA、
GA INT8 max）或在语义解冻后生成物理配置；不得在当前 target 上继续批量发射 JSON。

#### 0.3.5 probe_v7 回传裁决（2026-07-24）

状态：**动态 occurrence 已闭合；无需继续生成定位包。GAP 当前同时被一个
`RTL_CONTROL` blocker 与一个独立 `CONFIG_SEMANTICS` blocker 阻塞。**

1. 回传 ZIP/旁路 SHA256 一致；return manifest、33 项 allowlist、条目 size/hash、
   0 退出码均通过。pre/post/post-run 身份稳定；服务器 14 个 focused RTL 全部与
   本地匹配，TB 与 workload 身份匹配，因此排除 TB/身份漂移。
2. v7 共取得 512 条 `GA_ACCUM_STATE`。700313000→700316000 ps，全部 8 个普通 PE
   在 INT32 transout 归并中从 `count=1` 变为非法 `count=3`（outbuffer depth=2）；
   静态 RTL 对应 `GA_PE_Outbuffer.sv:293-305` 的无 occupancy guard 固定减法。
3. 700316000 ps 下一 block 首项仍正确使用 `C=0`；700318000 ps 在两个 tag 均为 0、
   `ob_valid=0` 时，8 个 PE 全部把各自旧槽 data 作为 input C。动态判据共命中
   217 次，分类为
   `ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse`。
4. 因果链是“count 下溢回绕→tag 清除但 data 保留→
   `transout_initial>=2` 无 valid guard 地反馈旧槽”，故
   `CDA-GAP-GA-ACCUM-STATE-001` 升为服务器动态反证，保留
   `B_GAP_GA_ACCUM_STATE`，等待功能 RTL 修复授权。
5. 数值路径另有独立配置缺陷：MSE0 8960/8960 且 payload 无损；MSE4 512 个请求
   仅有 2 个唯一地址。16 片正式 D 各只有索引 0、1 有效、其余 510 行全 `x`，
   32 个有效位置与 golden 匹配 0。因此现有服务器运行仍命中
   `B_GAP_D_INDEX_CARRIER_SEMANTICS`，不得提升 E4。
6. `local_mse4_wdata` 的 511 条是已知 local monitor 同周期盲点；在 v5
   same-clock observer 已证明 512/512 的前提下，不得把它误判为 RTL 丢写。
7. 详细裁决：
   `server_returns/gap_hwop0071_probe_v7_return_20260724/GAP_PROBE_V7_DIAGNOSIS.md`；
   机器报告为同目录 `gap_probe_v7_analysis.json`、
   `gap_numeric_path_report_v7.json` 和 `native_return_acceptance_v7.json`。
   本次未修改功能 RTL、未生成新包。

#### 0.3.6 repair_v9 生成与服务器交接（2026-07-24）

状态：**配置与 RTL 两个已知问题已分别修复并生成全新服务器测试候选；本地只达到
E2/static preconditions，等待服务器动态门，不能称为 GAP 发布通过。**

生成前已完整阅读：

- `.agents/rules/算子配置规则.md`
- `.agents/rules/GAP_probe_v7_validator_rules.md`
- `.agents/rules/GAP_repair_candidate_rules.md`（规则同步后已复核 v9 身份与边界）
- `.agents/rules/服务器测试包生成规则.md`
- `ndp-sim-ref/model_execplan/readme.md`

v8 草案只替换了配置/mapping/bitstream，却复用了 v7 execplan/SCA，不满足强制
完整重建门，因此未交付、不得上传或运行。v9 的新身份与重建链如下：

1. `CONFIG_SEMANTICS`：address-bound 配置只对 LC2 做四字段精确修复：
   `src_id: "DRAM_LC.LC0"→null`、`outmost_loop: 0→1`、
   `end: 1→256`、`last_index: 1→0`；A=`0x0`、D=`0x18840` 及其余字段受控不变。
2. 使用 `contracts/ndp_patch_toolchain_gap_v1.json` 在两个隔离工具副本中完整重建
   planner、encoder、bitstream、execplan、SCA/SCA_D；双跑 15 个确定性文件一致，
   mapping penalty=0、fallback=false。最终 evidence：
   `artifacts/operator_config_validation/r5-patched-execplan-evidence/gap-hwop0071-sum-d-index-v4`。
3. GAP 专项 request-address 枚举证明 16/16 slice 均有 256 个 32-byte transaction
   base、512 个互异 128-bit D 写地址；每片 SCA_D 和独立 golden 均为 512 行。
   专项报告：
   `artifacts/operator_config_validation/r5-gap-repair-release-v9/GAP_REPAIR_RELEASE_GATE.json`，
   文件 SHA-256
   `a3edce714b3a0fccf6d8ab328f5a9ac95c5fdb4e401a87502b43a735388ed711`。
   后续生成还必须执行新增的
   `CDA-CONFIG-FULL-REBUILD-PROVENANCE-001`、
   `CDA-RTL-REPAIR-TRANSACTIONAL-RESTORE-001`、
   `CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001`、
   `CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001` 与
   `CDA-GAP-REPAIR-RETURN-RECEIPTS-001`。
4. `RTL_CONTROL`：包内 repair 只包含
   `GA_PE_Outbuffer.sv` 与 `GA_PE_Inbuffer.sv`。前者在清除两个 tag 的归并/
   result-last 路径把 occupancy 置零；后者等待有效 INT32 feedback，并把无效槽
   tag/data 隔离为零。本地 `NDP_copy01` 未修改；Icarus 语法、微模型、preimage
   hash gate、精确备份和逐字节恢复测试均通过。
5. 包：
   `artifacts/operator_config_validation/r5-server-test-packages/gap_hwop0071_sum_repair_v9.zip`，
   SHA-256
   `4344b4166540482d12256b1a5893b8e3dbb512a74a7d735237de0ae2bf873864`，
   3,297,090 bytes、125 entries、124 payload files。ZIP exact set、sidecar、
   两文件 RTL allowlist、波形/build tree/nested archive 禁止项和 Bash 语法通过；
   25 项定向测试通过。
6. 服务器脚本在 canonical preimage 精确匹配后才安装 repair，保存逐字节备份；
   采集 pre/post/post-run，运行结束恢复原 RTL 并采集 post-restore，EXIT trap
   也会尝试恢复。全新 install/run/return 身份均为
   `gap_hwop0071_sum_repair_v9`。

服务器唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

只返回：

```text
gap_hwop0071_sum_repair_v9_return.zip
gap_hwop0071_sum_repair_v9_return.zip.sha256
```

仍未解除的动态 blocker：

- `CDA-GAP-D-READBACK-COVERAGE-001`：16×512 正式 D readback 尚未逐行通过 golden；
- `CDA-GA-OUTBUFFER-OCCUPANCY-001`：8 个普通 PE 尚未由服务器证明全周期 count∈[0,2]；
- `CDA-GA-INVALID-SLOT-ISOLATION-001`：服务器 invalid-slot reuse 必须为 0；
- `CDA-GA-CROSS-BLOCK-INIT-001`：服务器新 block 在新 partial 有效前必须 C=0；
- `CDA-MSE4-MONITOR-EVIDENCE-001` 与
  `CDA-SERVER-FOCUSED-IDENTITY-001` 尚待本轮回传；
- 单次 E4 通过后仍需独立 E5 重跑。

交付说明：
`artifacts/operator_config_validation/r5-server-test-packages/GAP_REPAIR_V9_DELIVERY.md`。

#### 0.3.7 corrected-config + server-original-RTL v10 裁决包（2026-07-24）

状态：**已按用户要求生成只修正配置资产、保持服务器功能 RTL 原样的单变量裁决包；
本地专项校验通过，仍为 `candidate_release=false / E2_LOCAL_ONLY`，等待服务器回传。**

生成前已重新完整阅读 0.3.6 所列五份强制规则/原生 execplan 文档。执行边界：

1. v10 使用 v9 已完整重建并哈希绑定的 corrected workload；本轮没有再次修改配置，
   因此不另造 planner/encoder/mapping/bitstream/execplan/SCA 变量。LC2 仍精确为
   `src_id=null`、`outmost_loop=1`、`end=256`、`last_index=0`，每片 256 个
   32-byte transaction base、512 个互异 128-bit D 地址。
2. 包内功能 RTL 文件数为 0，不包含 `rtl_patch/`，不调用
   `install_gap_ga_rtl_repair.py`，不执行 install/restore action；服务器
   `GA_PE_Inbuffer.sv` 与 `GA_PE_Outbuffer.sv` 保持原始字节。
3. TB observer 仍安装在 `rtl/` 外，仅采集有界状态；pre/post/post-run/final
   四阶段身份必须证明整棵 RTL tree 和 focused RTL 全部稳定。服务器 RTL 可与
   本地/GitHub 不同，但本轮前后不得变化。
4. 专用规则包含
   `CDA-CONFIG-FULL-REBUILD-PROVENANCE-001`、
   `CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001`、
   `CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001`、
   `CDA-GAP-ORTHOGONAL-DEFECTS-001` 和六项 GAP 动态/身份门。
   `CDA-RTL-REPAIR-TRANSACTIONAL-RESTORE-001` 不触发，因为本包不是 repair；
   patch receipts 不伪造，改为强制 `stock_rtl_identity_receipt.json`。
5. 包：
   `artifacts/operator_config_validation/r5-server-test-packages/gap_hwop0071_sum_configfix_stockrtl_v10.zip`，
   SHA-256
   `86cd391a4178258bd9f4068583db979f3ddd74f737841a3ca41f07bd9f71e907`，
   3,291,066 bytes、122 entries、121 payload files；功能 RTL 文件数 0。
   专项 validator、ZIP exact-set/sidecar、Python 编译、Bash 语法和 14 项定向/
   回归测试均通过。

服务器唯一命令：

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

只返回：

```text
gap_hwop0071_sum_configfix_stockrtl_v10_return.zip
gap_hwop0071_sum_configfix_stockrtl_v10_return.zip.sha256
```

裁决边界：若原始 RTL 下仍出现 count=3、invalid-slot C reuse、跨 block 初始 C
非零或正式 D 回读错误，则配置修复不能解除相应 RTL blocker；若 16×512 D golden、
8 PE occupancy、invalid-slot、cross-block-init 和 focused identity 全部通过，只能
形成“本 workload 不需要 RTL patch”的单次 E4 候选证据，仍需规则复核与独立 E5。

交付说明：
`artifacts/operator_config_validation/r5-server-test-packages/GAP_STOCK_RTL_DECISION_V10_DELIVERY.md`。

### 0.4 两个任务的交接协议

| 来源 | 交接给 | 必须包含 | 接收方动作 |
|---|---|---|---|
| 代码对照分析 | 测试分析 | issue ID、互斥假设、最小输入、观察点、判据、禁止改变项 | 生成/执行最小 TB 探针包并返回原始证据 |
| 测试分析 | 代码对照分析 | 包/返回哈希、首个分歧、cycle/slice/request、实际与期望、置信度、适用范围 | 与 RTL/stage 合同复核后回写规则和 validator |
| 测试分析 | 用户 | 唯一测试包、完整服务器命令、预期返回清单 | 用户在服务器运行并原样返回结果 |
| 任一任务 | 总体计划 | 已闭合项、仍阻塞项、证据等级、需重建产物 | 只更新本节相应任务状态，不改写另一任务结论 |

交接纪律：

- 动态结果不得跳过 RTL/stage 复核直接成为全局生成规则；
- RTL 静态推导不得跳过 stage 意图就决定 JSON 值；
- 某一测试失败必须同时保留“被测配置/包身份”和“服务器/RTL 身份”，否则只能记为 identity incomplete；
- 新证据推翻旧规则时，旧规则、受影响配置和历史结果标记为 superseded/invalidated，不静默覆盖；
- 同一问题必须使用稳定 issue ID，防止两个对话重复开题或各自修补。

### 0.5 文件所有权与并行冲突控制

- “测试分析”主要写入 `server_returns/**`、`artifacts/operator_config_validation/r5-server-test-packages/**`、TB observer、包构建器和返回分析工具；功能 RTL 默认不得修改，唯一 repair_v9 例外只生成独立 hash-gated patch 资产且不修改本地 preimage；不直接提交全局配置规则。
- “代码对照分析”主要写入 `.agents/rules/算子配置规则.md`、`contracts/**`、stage/config 生成器、严格 validator 和对应测试；不得覆盖服务器原始返回或冻结测试包。
- 两个任务都可以读取全部证据；涉及同一工具文件时，先在本节登记 ownership/issue，再修改，避免两个对话同时编辑。
- `.agents/plan.md` 由两个对话分别只维护其命名小节的状态与交接项；不得删除 W0–W9 总体计划或另一对话的未完成事项。
- 本地功能 RTL `.v/.sv` 永久只读；用户授权 repair 包只能携带独立 patched copy，
  并按 preimage hash gate、backup、restore、post-restore 流程临时安装。TB `.sv`
  修改必须独立列入 package diff，并可通过 plusarg 关闭。

### 0.6 汇合条件与整体推进

单个语义项只有同时满足下列条件才算闭合：

1. 硬件行为有 RTL 路径或受控动态实验支持；
2. stage 意图和物理布局/数值合同明确；
3. JSON 字段组合、默认值和边界条件明确；
4. 规则已写入机器合同或生成器，严格 validator 能拒绝已知反例；
5. 受影响代表算子重新生成并通过本地回归；需要硬件裁决的项取得 E4，发布级结论再取得独立 E5。

两个任务不是互相等待的串行关系：

- “测试分析”持续处理已经返回的 GAP/后续服务器结果和 probe 包；
- “代码对照分析”持续审核尚未确定的 LC、MSE、padding/tail/keep、SA、GA 和跨 stage CONFIG 语义；
- 只有出现 `TEST_REQUIRED` 或 `CONFIG_SEMANTICS` handoff 时才在对应 issue 上同步；
- 汇合后的规则优先反哺 GAP、Conv＋Requant，再按 shape family 推广到 107/133 个 Conv/Requant stage，最后闭合剩余算子族和 W7–W9；
- 在 133-stage 规则、生成、严格本地验证、E4/E5 及整网三方比较全部满足前，不得宣称项目完成。

## 1. 当前目标

首轮已使用最新版原版 `ndp-sim` 的单硬件原子算子 `decode_summac_fp32N_fp32N` 验证服务器加载与执行链。它是 RMSNorm 的 sum-of-squares 子步骤，只有一个外部 A、一个 D，无模型权重依赖；本轮不要求数值正确，只要求 shape、dtype、128-bit packing、地址、配置、指令和目录格式有效并能在服务器完成运行，该目标已由服务器实测完成。

本地生成文件夹不再要求与旧参考目录 exact-tree 或逐字节一致。候选只需采用最新工具的当前格式，包含服务器实际装载和运行所需的全部配置、指令、输入数据及输出/回读描述，并通过本地路径、文件存在性、bitstream/execplan 生成和重复生成自洽检查。之后由用户手动加载到服务器指定位置并执行服务器命令。

`decode_max_fp32N_fp32N_graph` 单算子诊断包使用仓库既有 `jsons/decode_max_fp32N_fp32N.json`、固定 seed 合成 Golden、28-slice 原生 relayout、原版 planner/encoder/SCA/assembler；所有 stream/GA 输入均为零 ping-pong。它已经在服务器自然完成，因此本轮诊断目标已达到：该短 FP32 max 场景的 transout/outbuffer/MSE4 写回链能够完成。下一步不能把它误写为 node-0002 修复，而应针对 INT8 `int8_max` pipeline0 或相应 RTL revision继续裁决。若需要把 Decode 从 E3 升为 E4，必须用同一包重跑并显式传入正确的 `+SCA_CFG_D`，取得正式回读文件；MaxPool 旧包和 node-0004 两个 revision继续保持原样。

INT8 包已经完成有效裁决，不再通过延长超时或更换数据重复运行未修复 RTL。下一步应记录服务器实际 `GA_PE_Inbuffer.sv` 与 filelist 哈希，给 GA INT8 pipeline0 增加正确下游反压分支，再用完全相同的 `native_int8_maxpool16_r1_graph` 做修复后反事实复测；成功标准是出现 MSE4 写数据、slice completed、28 项 D 回读和自然退出。

FP32 对照已完成，INT8 包也已在正确加载和启动后停滞；当前 A/B 结果强力支持 INT8 专属路径问题。由于两份 ZIP 尚未绑定服务器 RTL/filelist 哈希且没有 pipeline0 内部信号探针，精确 RTL 唯一根因仍须通过身份记录、信号观测和修复后同包复测闭合。详细证据见 `server_returns/native_int8_maxpool16_sim4_2_20260723/ANALYSIS.md` 与 `contracts/ga_int8_pipeline_backpressure_defect_report_20260723.md`。

## 2. 当前事实来源与目录

事实优先级：

1. 活动 GitHub 原版仓库 `ndp-sim` 的原生 README、源码及其真实输出行为；
2. 已通过服务器运行的参考算子目录，只读用于目录、哈希和差异比较；
3. 用户之后手动执行得到的服务器原始返回；
4. 本项目的 `agent.md`、`plan.md` 和规则文件等派生总结。

| 角色 | 路径/身份 | 当前权限 |
|---|---|---|
| 唯一活动原生工具仓库 | `C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim`，提交 `ec12424516ae0304228dd2321d4e604fe225e04e` | 只按原生 README/源码使用 |
| 服务器已运行参考目录 | `C:\Users\15383\Desktop\Codex\project\resnet50_int8\jsons` | 只读比较；不得作为生成输入 |
| 暂停使用的旧参考仓 | `C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim-ref` | 暂时停用；不得导入、调用或复制其工具/产物 |

如活动 `ndp-sim` 的提交、工作树或原生 README 发生变化，必须先重新记录身份和差异，不能沿用本计划中的结论。

## 3. 首个基线算子

当前首个服务器候选为 `decode_summac_fp32N_fp32N`，原因是本地原版仓库同时具备：

- `ndp-sim/jsons/decode_summac_fp32N_fp32N.json` 静态配置；
- `decode_ops.py` 中固定 seed 的算子语义和数据；
- `run_single_op_decode.py --target-op decode_summac_fp32N_fp32N` 的 28-slice 原生入口；
- `generate_decode_execplan_inputs.py` 生成的单算子 graph；
- `assemble_decode_package.py` 的自包含装配入口。

参考目录 `jsons/rmsnorm` 只用于确认服务器消费层级包含顶层 SCA/说明、`install/execplan*`、`install/cfg_pkg` 和 `install/opN/sliceNN`；候选没有复制其中任何内容。该 Decode 原子目录现已有用户确认的服务器完整跑通记录，但尚未做数值正确性比较，因此它是服务器加载/运行格式基线，不是严格的数值正确配置对照。具体重跑规则与原 README 冲突见 `ndp-sim/README_SERVER_PACKAGE_LOCAL.md`。

## 4. 来源隔离与可运行合同

### 4.1 禁止事项

- 不得复制、移动、链接、解包、转码或以脚本读取后重写参考目录中的任何文件来构造新目录。
- 参考目录不得作为生成命令的输入路径；不得从参考文件反推数值并手填到本地 JSON、配置、地址、数据或指令中。
- 不得调用 `ndp-sim-ref`，也不得调用根仓自定义的 server profile、freeze、package、overlay、runner、补 barrier、补占位文件或重打 ZIP 工具。
- 不得为了“看起来像旧参考目录”手改原生输出、复制参考文件、过滤原生错误或把失败后残留目录当作成功结果。
- 在当前格式目录自洽、服务器消费方式明确前，不得上传服务器。

允许对参考目录执行的操作只有只读清单、文件类型、大小、哈希和 diff；这些信息只用于验收，不得回流为生成输入。

### 4.2 当前候选定义

必须满足：

1. 使用最新 `ndp-sim@ec124245...` 的当前 `op_json`、静态 JSON、remapping、bitstream 和 execplan 实现；
2. `sca_cfg.json` 中所有预加载路径、`cfg_pkg` 路径和 `execplan.txt` 均实际存在；
3. 每个启用算子的输入数据由 golden/relayout 流程生成，不能从旧参考服务器目录提取；
4. 每个算子的 bitstream 生成成功；不能只看 `main.py` 的退出码，因为当前 pipeline 对部分 regeneration 失败会继续；
5. 输出/回读文件可以为空或与参考数值不同，但服务器 loader 需要的路径、长度和文件格式必须存在；
6. 参考目录只用于确认服务器曾能执行同类算子和辅助理解消费文件类别，不再作为文件集合、命名或字节验收基线。

## 5. 已执行的原生生成方案

本轮实际执行链只使用活动 `ndp-sim` 原生实现和本轮合成数据：

1. 通过 `deepseek1.5b_decode_golden.py` 已存在的 `use_real_weights=False` 参数生成固定 seed 合成 Golden；CLI 没有暴露该参数，且默认 KV cache 回退仍错误依赖 `model_weights_32`，因此直接调用原生函数参数，未修改源码。
2. `run_single_op_decode.py --target-op decode_summac_fp32N_fp32N` 生成 op0/op10/op32 三个同类型实例；候选单图只引用 op0。
3. `generate_decode_execplan_inputs.py` 生成 `generate_python_golden/model_execplan/op_json/decode_summac_fp32N_fp32N_graph.json`。
4. README/Makefile 从该目录写成 `model_execplan/main.py`，真实 planner 位于上一级；实际执行 `..\model_execplan\main.py`。
5. bitstream 首次因本地缺 `matplotlib` 失败；依赖仅安装到临时运行目录，设置 `PYTHONPATH` 后干净重建，日志确认 `Regenerated bitstream + JSON for 1 operator(s)`。
6. `assemble_decode_package.py` 从本轮 `install_decode/op0` 装配 28 个 SCA 输入；为匹配参考消费目录的伴随文件类别，又从同一本轮原生 op0 输出机械补齐 A/D 的 `.bin`、128-bit `.txt` 和 decimal 文件。
7. 对服务器消费文件重复重建并比较 SHA-256；除 manifest 的“copied/unchanged”运行统计外全部一致。最终候选从空目录干净重建，使 manifest 固定为 copied=28、unchanged=0。

原生 README 目前只明确生成 `install/execplan.txt`、`install/cfg_pkg`、`sca_cfg.json`、`sca_cfg_D.json` 和可选 `Bank_data` 等消费内容；完整的服务器装载、启动、等待完成和回读方法仍以用户掌握的服务器流程为准，本项目不擅自补写。

## 6. 阶段门

### 阶段 A：已测参考算子原生复现

- A1：完整本地原生来源链已找到；**完成**。
- A2：最新版原生工具完成合成 golden、relayout、bitstream 和 execplan；**完成**。
- A3：当前格式服务器目录自洽，所有服务器消费路径和文件完整；**完成**。
- A4：用户手动加载服务器并确认自然完整跑通；**完成**（用户口头结果已记录，服务器原始命令/日志未归档）。

A1～A4 已完成。无需与旧参考目录逐字节一致；`decode_summac_fp32N_fp32N_graph` 现作为已通过服务器的当前格式基线，后续可以进入 ResNet50 阶段。

### 阶段 B：最简单 ResNet50 算子

阶段 A 已通过。`node-0002` MaxPool 单波次候选已使用活动 `ndp-sim` 静态 JSON、正式 W3 batch16 A/D 张量和根仓最小桥接脚本全新生成；没有调用、读取或复制 `ndp-sim-ref`。更新 testbench 后的服务器重跑仍无写数据，旧目录冻结。FP32 max 对照已经自然完成且实际产生写数据，因此不再重复封装同一 node-0002 JSON来检查公共写回链；后续应修复或更换包含 INT8 pipeline0 修复的 RTL，再建立全新 MaxPool revision。

### 阶段 C：Conv

用户已明确授权先做一个边界受限的 `node-0004 accumulate-wave-0` 单阶段冒烟例外。旧的同哈希配置 revision 已在服务器表现为不自然完成，必须冻结为失败证据。新 `nopp-r1` 只从同一既有配置派生零 ping-pong 拓扑；graph 和 W3 物理输入由可审计 bridge 重新生成；地址、bitstream、Write_Reg、Start_Comp、SCA 和装配仍由活动原版 `ndp-sim` 完成。不得从旧失败包或历史 Conv revision/freeze/v20/package 提取配置、数据、execplan 或 barrier，也不得把该例外扩展为完整 Conv 或数值验证。

## 7. 当前状态与隔离项

- 当前已通过服务器的基线：`ndp-sim/model_execplan/output/decode_summac_fp32N_fp32N_graph`。
- 本地验收：1 operator、28 slices、30 个 SCA 加载引用、28 个 D 回读引用、29 行 128-bit execplan、18 行 128-bit config、30 条 manifest 记录、185 文件、353068 bytes。
- 最终 `decode_package_manifest.json` SHA-256：`56621f68a59d0962ab627c689982c566e571c54eb278846ff3ffcc6b2c9dfd1f`。
- 成功基线没有 `Bank_data`，且用户确认服务器完整跑通，因此当前这条已验证 loader 链不需要 `Bank_data`；该结论不得外推到其他 loader 或算子。

- 当前 MaxPool 单波次候选：`ndp-sim/model_execplan/output/node0002_maxpool_wave0_graph`。
- 来源：活动配置 `ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json`、W3 输入 `tensor-f6c1a8fb6fd529e8.npy`、W3 输出 `tensor-8d2f28c80ac24676.npy`、桥接脚本 `tools/generate_active_ndpsim_maxpool_smoke_inputs.py`。
- 覆盖范围：首波 28 个真实 NHWC tile；每 tile 为 1 个 batch 的 16 个通道。完整 node-0002 共 64 tile，后续仍有 36 tile，需要第二波 28 和第三波 8。
- 本地验收：逐 tile W3 数值 mismatch=0；30 个主 SCA 文件引用、28 个 D 回读引用、168 个 A/D 数据文件、29 行 128-bit execplan、30 行 128-bit config、186 文件、81407600 bytes；无 `Bank_data`。
- 重复生成稳定：execplan SHA-256 `cf6fb01495acc50c913745bba6f436325f9708e16376f2dc44c98c1d444592bb`；bitstream SHA-256 `13931520925a6a10ccd821340a2fab39db8bbd44be7cf99394d0fc562001dcb3`。
- 更新 testbench 后服务器仍未自然完成；28 个 slice 均有读返回、写地址请求但无写数据。该目录现作为失败证据保留，不再覆盖或重复封包。

- 当前 FP32 max 对照包：`ndp-sim/model_execplan/output/decode_max_fp32N_fp32N_graph`。
- 原生配置：`ndp-sim/jsons/decode_max_fp32N_fp32N.json`，使用 `alu_opcode=max`，无 `int8_max`，stream/GA 输入 ping-pong 启用数为 0。
- 本轮新生成 Golden：`ndp-sim/generate_python_golden/python_golden_decode_maxdiag_r1`；单算子数据：`single_op_data/install_decode_maxdiag_r1`。
- 原生编号缺口：完整 Golden 产出 `op25`，原生单图消费 `op10`；本轮只做 `op25 -> op10` 逐字节机械复制，168 个文件逐一 SHA-256 一致，不改变数值或配置。
- 本地验收：28 slices、每片 6 个 A/D companion 文件、168 个数据文件、30 个主 SCA 引用、28 个 D 回读项、29 行 execplan、17 行 config、185 文件、314861 bytes；无 `Bank_data`、overlay、runner、barrier 或 ZIP。
- 稳定身份：execplan SHA-256 `ab6c5fb65be546d8b12e8714c5f26b3cef2c755b4c60747c5f22ca3d2dd4f302`；bitstream SHA-256 `8c46c4989591b397ad76a11cd2f19c596fc092299a0cb12214d82c82ff275346`。
- 服务器原始返回：外部 `simresults(1).zip`，23148389 bytes，SHA-256 `3D8FECF803A64E2A6F378E82CEEB7B4099D66F28C7F2C70BE2743CB53D1CB33A`；分析副本为 `server_returns/decode_max_fp32_simresults_1`。
- 服务器裁决：30 个 preload 对象和 29 行 execplan 成功装载；57 个 gexec 命令握手；28 slice 在 66 cycles 后完成，均有 1 个 MSE4 写数据，pending read=0；testbench 约 15.259 us 自然 `$finish`。实际写出的有效最低 32-bit 与本地 D Golden 28/28 一致。
- 回读缺口：服务器命令只有 `+SCA_CFG=.../sca_cfg.json`，没有 `+SCA_CFG_D=.../sca_cfg_D.json`；testbench 因而尝试不存在的 `sca_cfg_D_softmax.json` 并 `skip matrix readback`。本轮保持 E3；内部 MSE4 数值对照不替代正式 SCA_D/DDR 回读。
- 防复发：所有后续手动运行必须显式同时传入 `+SCA_CFG` 与 `+SCA_CFG_D`，并在日志开头核对两条实际路径。`Cannot open`、`skip matrix readback` 或意外 softmax 文件名均为回读失败，即使计算自然完成也不能记 E4。不得复制/改名伪造 `sca_cfg_D_softmax.json`。
- 结果解释：本包排除了该短 FP32 max 场景中的公共 transout/outbuffer/MSE4 写回死锁，支持 INT8 专属路径故障；它仍不能声明 node-0002 MaxPool 数值正确或已修复。

- 当前原生 UINT8 MaxPool INT8 路径裁决包：`ndp-sim/model_execplan/output/native_int8_maxpool16_r1_graph`。
- 静态配置：`ndp-sim/jsons/maxpool_config_16_16_16_stride2_padding1.json`，Git 跟踪原文件 SHA-256 `624d675ddde6f386474289d473d1c69559691794f3c1ea775dfc99325cc8f072`；没有读取 `ndp-sim-ref` 或旧失败 MaxPool 包。
- 语义/数据：28 slice；每 slice 为 UINT8 HWC `[16,16,16]`，C4HWC4 物理输入包含 68-byte 前 guard、4096-byte payload、12-byte 后 guard；输出为 UINT8 C4HWC4 `[8,8,16]`、1024 bytes。逐片输入公式和独立 3×3/stride2/pad1 MaxPool Golden 均通过本地重算。
- 原生控制：8 个 GA PE 均为 `int8_max`、编码 `01011`；stream/GA inport ping-pong 均为 0；1 Clock_Enable、1 Load_Config、54 Write_Reg、1 Start_Comp、0 barrier。
- 包闭合：30 个主 SCA 引用、28 个 D 回读引用、29 行 execplan、30 行 bitstream、168 个 A/D 数据文件；所有 SCA 目标存在，无 `Bank_data`。
- 稳定身份：execplan SHA-256 `651eca0897ed0907d38733b26c3f527c3023893ed081c87ee1ab8e92a86cae6b`；bitstream SHA-256 `350c7d8757434a7a84ce50301cea2952ddf5950bd699015b77b3411c5d04a635`。独立全新 r2 原生生成的 183 个服务器消费文件与 r1 逐文件 SHA-256 全部一致。
- 本地验证报告：`ndp-sim/model_execplan/output/native_int8_maxpool16_r1_graph/native_int8_maxpool16_r1_validation.json`；状态仅为本地结构/来源/数据/Golden 通过、服务器尚未运行。
- 服务器强制参数：`+SCA_CFG=install/cfg_pkg/native_int8_maxpool16_r1_graph/sca_cfg.json` 与 `+SCA_CFG_D=install/cfg_pkg/native_int8_maxpool16_r1_graph/sca_cfg_D.json`。两者缺一不可。

- 当前 DeepSeek FP32 对照包：`ndp-sim/model_execplan/output/native_deepseek_fp32_max_control_r1_graph`。
- 来源配置：`ndp-sim/jsons/decode_max_fp32N_fp32N.json`，SHA-256 `ab73710698892ed8e1062e4b5ac66fe310f99609dac89ea96ce8fa6e4bd3a1c2`；全新固定 seed 合成 Golden 为 `python_golden_fp32max_control_r1`，单算子数据为 `install_deepseek_fp32max_control_r1`。
- 原生编号桥接：完整 Decode 实例 `op25` 机械复制为原生单图固定 ID `op10`，168 个文件路径和 SHA-256 全同；不改变数据、dtype 或 packing。
- 控制语义：GA `max` 编码 `00011`，`int8_max` 数量为 0；2 个 stream 和 3 个 GA inport 的 ping-pong 均为 0；原生 encoder 独立检查报告 zero violations。
- 本地闭合：28 slice，每片 8 个 FP32 输入、1 个 FP32 max 输出；168 个同轮数据文件，独立 FP32 max mismatch=0；30 个主 SCA 引用、28 个 D 回读项、29 行 execplan、17 行 bitstream，无 `Bank_data`。
- 稳定身份：execplan SHA-256 `ab6c5fb65be546d8b12e8714c5f26b3cef2c755b4c60747c5f22ca3d2dd4f302`；新 bitstream SHA-256 `5450c1d32c04d3ce0435100cce7f2c2f25b06efa1a42cb608f48f0843532bd7c`；全新 r1/r2 的 184 个核心文件逐哈希一致。
- 旧硬件证据边界：此前自然完成包的 execplan 与本轮相同，bitstream 为 `8c46c498...`；本轮新 bitstream 的差异仅来自另一套零违规 LC placement。旧结果支持算子类别适合作为对照，但不能替代新包实测。
- 验证报告：`ndp-sim/model_execplan/output/native_deepseek_fp32_max_control_r1_graph/native_deepseek_fp32_max_control_r1_graph_validation.json`。
- 服务器参数：`+SCA_CFG=install/cfg_pkg/native_deepseek_fp32_max_control_r1_graph/sca_cfg.json` 与 `+SCA_CFG_D=install/cfg_pkg/native_deepseek_fp32_max_control_r1_graph/sca_cfg_D.json`。

- 旧 node-0004 目录 `ndp-sim/model_execplan/output/node0004_accumulate_wave0_graph` 已冻结为服务器失败/疑似死锁证据，不得覆盖、清理、改名为候选或用作新包输入。其 execplan SHA-256 为 `d61253c090d812e7ecb22e2520c840165d880e49ac300d20a4b2058b8cac3c57`，bitstream SHA-256 为 `a7296e83dee267c0ad23f8d914dd02af39f3a7ad2e732e15636d9ab033088992`；完整树快照为 355 文件、125340121 bytes、路径/大小/文件哈希聚合 SHA-256 `be9e069f3a28fe17aed2b0bc5a5cc0f01cbc524b187d21fcbbf93bb9afeccd8c`。
- 失败报告 `simresults.zip` 为 18246313 bytes，SHA-256 `3f48eb9ed79c9e8f564d9e77a9e2c7684a8c84642781de7ee8343ba97baba629`。当前最强解释是旧配置的 SA inport0 启用 ping-pong，但 A/READ_STREAM0 只生产 buffer0，切换到无生产者的 buffer1 后无法继续；服务器当轮 testbench 版本不确定，因此该解释仍需新 revision 的服务器结果裁决。
- 当前 node-0004 候选：`ndp-sim/model_execplan/output/node0004_accumulate_wave0_nopp_r1_graph`。派生配置为 `ndp-sim/jsons/node0004_accumulate_wave0_nopp_r1.json`，SHA-256 `0706ad05233d03f43b800797b1be40390c718f58d34c13df89a0208d75bba45e`。
- 新配置关闭 4 个 stream 和 3 个 SA 输入的全部 ping-pong，删除 B′/READ_STREAM2/GROUP2；物理闭合为 A→READ0→buffer0→SA.in0、B→READ1→buffer2→SA.in1、C→READ3→buffer4→SA.in2、SA→buffer5→WRITE0→D，buffer1/buffer3/READ2 不启用。
- 正式数据仍来自 W3 `golden_batch16`、`subop_batch16`、形式 ONNX 和当前 signed-A Conv28 layout；新 bridge 为 `tools/generate_active_ndpsim_node0004_accumulate_nopp_r1_inputs.py`，显式拒绝 `ndp-sim-ref`、`artifacts/w5` 和旧失败包作为来源。每片 A/B/C/D 字节为 1024/200704/64/200704，逻辑样本为 `[0,3,6,8,10,12,14]`。
- 原版输出：1 Clock_Enable、1 Load_Config、108 Write_Reg、1 Start_Comp、0 barrier；56 行 128-bit execplan、30 行 128-bit config、84 个主 SCA tensor 引用、28 个 D 回读项、336 个同轮伴随数据文件，无 `Bank_data`。
- 原版 pipeline 连续两次生成稳定：execplan SHA-256 `a5d9edf2fbd51f2107b9fe7845f4716786a61797be7c9e38aca3ede9009a0711`；bitstream SHA-256 `fce569a7da456ea1b93c82b812c3857b7e2495e849775c54f332ddab6edad998`。
- 本地验证报告：`ndp-sim/model_execplan/output/node0004_accumulate_wave0_nopp_r1_graph/node0004_accumulate_wave0_nopp_r1_validation.json`。状态仅为零 ping-pong 结构/来源通过、服务器尚未运行；不得称为死锁已经由硬件验证修复或数值通过。

- `ndp-sim` 已放在工作库根目录，原中间目录 `upstream_recheck_20260722` 已清理。
- `ndp-sim-ref` 已暂停使用。
- 之前产生的 `ndp-sim/model_execplan/output/silu_withbaseaddr` 和 `ndp-sim/model_execplan/output/maxpool_node0002` 仅为诊断输出，均未通过本计划的一致性门，不得上传。
- `maxpool_node0002` 中还混入过从参考目录复制的空占位文件，明确违反当前“参考目录不得作为生成来源”规则；该目录永久不能成为候选或后续输入。
- 当前原生 `silu` 复现已观察到非结果字节与参考目录不一致，因此下一次工作必须先做来源/版本/命令审计，不能复制或修改参考文件强行对齐。

## 8. `rmsnorm` 原生来源核对结果（2026-07-22）

### 8.1 已在当前 GitHub 原生仓库找到

- 图 JSON：`model_execplan/op_json/rmsnorm.json`；
- 四份静态原子算子 JSON；
- golden 主脚本：`generate_python_golden/deepseek1.5b_3_time_golden_smallsize.py`；
- relayout：`generate_python_golden/single_op_data/relayout_rmsnorm.py`；
- 原生调度器：`generate_python_golden/run_single_op.py`；
- 地址重映射：调度器对 `rmsnorm` 调用 `address_remapping.cli fill-remapping`；
- execplan：调度器随后调用 `model_execplan/main.py`；
- SFU 系数文件和全部 bitstream/execplan 源码。

### 8.2 README/源码给出的意图命令

从 `ndp-sim/generate_python_golden` 执行 `make`，实际展开为：

```text
python generate_seq_input.py
python weight_gen.py
python deepseek1.5b_3_time_golden_smallsize.py
python run_single_op.py
```

若只处理 RMSNorm，README 要求先把 `generate_python_golden/config.json` 的 `target_op` 改为 `rmsnorm`，再执行 `make single_op`；但该 target 依赖 `golden`，所以仍会先执行完整的前三步。`run_single_op.py` 的实际子流程是：

```text
relayout_rmsnorm.py
address_remapping.cli fill-remapping model_execplan/op_json/rmsnorm.json
model_execplan/main.py model_execplan/op_json/remapped/rmsnorm.json
```

`model_execplan/README.md` 中的 `python main.py examples/rmsnorm.json -b` 不能直接采用，因为当前仓库不存在 `model_execplan/examples/rmsnorm.json`；活动调度器已改用 `model_execplan/op_json/rmsnorm.json`。

### 8.3 当前原生链未闭合

1. 仓库不包含 `generate_python_golden/inputs_good/`，`generate_seq_input.py` 因此没有 8-token 基础输入。
2. 仓库不包含 `DeepSeek-R1-Distill-Qwen-1.5B-f16/`；README 只说手动下载，没有 URL、版本、文件清单、哈希或从官方 checkpoint 转换为自定义 `.bin` 命名的脚本。
3. `weight_gen.py` 当前写入 `model_weights_full/`，但 Makefile 调用的 golden 主脚本硬编码读取 `model_weights_small/`。
4. `generate_seq_input.py` 当前写入 `python_golden_custom_seq/`，但 golden 主脚本硬编码读取 `inputs_32/`。
5. 当前 clone 中 `inputs_good`、`inputs_32`、`model_weights_small`、`model_weights_full`、`python_golden` 均不存在；仅 RoPE cos/sin 表被 Git 跟踪。
6. `relayout_rmsnorm.py` 把数据写到 `model_execplan/data/rmsnorm/<prefix>/install/`，而 Prefill 原生代码没有把该目录装配进 `model_execplan/output/rmsnorm/install/` 的 assembler/copy 步骤；只有 Decode 路线存在单独 assembler。
7. 当前 pipeline 在 bitstream 子进程失败或 `parsed_bitstream.txt` 缺失时会打印错误后 `continue`，所以顶层返回码不能单独证明候选完整；必须逐算子检查日志和当前 manifest/SCA 引用。

### 8.4 旧参考目录版本差异（不再阻塞）

参考目录来自较旧的原生工具状态；其 `REC_SQRT.txt`、`sca_cfg` 拆分方式和 bitstream 命名均与当前 HEAD 不同。用户已明确允许使用最新工具且不要求完全一致，因此不再定位或使用历史提交，`sca_cfg_op*.json`、旧 bitstream 名和 `.DS_Store` 均不属于当前候选必需内容。

## 9. 当前真正缺少的内容

### 9.0 当前单算子候选

本地内容已经闭合，不再缺输入、权重、golden、relayout、bitstream、execplan、SCA、输出描述或目录装配。当前不执行完整 43-op Decode，也不执行旧 Prefill RMSNorm。

### 9.1 外部数据

以下内容只在仍限定旧 Prefill `rmsnorm` 路线时缺少：

1. RMSNorm golden 的原始输入：优先提供原参考数据源的 `inputs_good/*.bin` 或可直接供主脚本读取的 `inputs_32/`；若仅做冒烟，也可改用仓库原生 `create_dummy_inputs.py`，再接到主脚本读取目录。
2. 原始模型权重：`DeepSeek-R1-Distill-Qwen-1.5B-f16/*.bin`，必须符合 `weight_gen.py` 解析的 `<name>__dtype=<f16|f32|i32>__shape=<shape>.bin` 格式。Prefill golden 会运行完整单层 Transformer，当前仓库没有只生成复合 RMSNorm golden 的独立入口，也没有原始权重下载 URL、转换脚本、清单或哈希。

### 9.2 旧 Prefill RMSNorm 路线内部需要接通的步骤

1. 将 `generate_seq_input.py` 生成的 `python_golden_custom_seq/` 提供给硬编码读取 `inputs_32/` 的 golden 主脚本。
2. 将 `weight_gen.py` 生成的 `model_weights_full/` 提供给硬编码读取 `model_weights_small/` 的 golden 主脚本。
3. 从 `model_execplan/data/rmsnorm/<prefix>/install/` 选择本轮新生成的 RMSNorm 实例，并机械装配到 `model_execplan/output/rmsnorm/install/`；当前 Prefill 路线没有原生 assembler。
4. 明确服务器使用 `sca_cfg.json + sca_cfg_D.json` 直接加载，还是要求额外导出 `Bank_data`。`run_single_op.py` 默认不传 `-b`。

若改用 9.0 的完整 Decode 路线，上述 1～3 不再缺；第 4 项仍由服务器 loader 决定。

### 9.3 服务器侧仍缺少的接口信息

仍需用户提供/执行候选目录的服务器放置位置，以及装载、启动、判断完成、超时处理和按 `sca_cfg_D.json` 回读的命令。还需确认服务器直接消费 `sca_cfg.json`，还是另需 `Bank_data`。没有这些信息，本地最多能证明目录自洽，不能证明服务器能完成测试。

当前不再缺历史提交、旧 `sca_cfg_op*.json`、旧 bitstream 文件名、参考结果数值或 `.DS_Store`。

## 10. 规则修正分支：算子配置语义与 ResNet50 生成闭环

### 10.1 分支目标、边界与当前状态

本分支用于修正 `.agents/rules/算子配置规则.md` 过度偏重来源/复现、尚未定义“模型算子如何降低成硬件配置”的缺口。当前状态为**R3 本地闭环和 R4 活动规则切换已完成，尚未修改原生实现或启动正式 lowering**。在用户批准 R5 来源策略前：

- 不修改活动 `ndp-sim@ec124245...`，不把本分支自动解释成允许根仓生成新静态 JSON；
- 不重写或覆盖已经生成的 Decode、MaxPool、node-0004 候选及其哈希；
- 不把历史服务器运行成功、自然结束、本地数值匹配和 bitstream 可编码混成同一种证据；
- 可以与用户手动执行现有 MaxPool/node-0004 服务器测试并行，但新的配置生成、整网 lowering 和新 Conv 变体必须等待本分支对应阶段门；
- 若影子验证发现会影响当前候选的确定性致命错误，候选只标记为“待裁决”，不得静默修补后沿用旧身份。

本分支的最终目标不是增加一份说明文档，而是形成以下闭环：

```text
目标硬件身份
  -> RTL/loader/encoder 字段真值表
  -> 严格、可机检的配置规则
  -> fail-closed 验证器与负例
  -> 算子 lowering/量化/布局合同
  -> 独立数值微测与服务器回读
  -> ResNet50 78 节点覆盖清单和整图验收
```

### 10.2 对原修正顺序的调整

之前的 P0/P1/P2 建议遗漏了三个前置逻辑：

1. **先冻结目标身份，再裁定冲突。** 本地 `NDP_copy01` 是服务器参考资料，不自动等于服务器当前活动 RTL。`MAX_ROWS=8192` 与本地 RTL `DDR_ROW_SIZE=6144` 是已复现的跨源矛盾，但在改 planner 前必须记录目标服务器 RTL/loader/profile 的可用版本或哈希；无法取得时按最小公共容量 6144 fail closed，而不是把 8192 或 6144 任一方直接写成无条件永久事实。
2. **先把事实分级，再写规则。** 已确认错误、命名歧义、缺失能力、过时注释和未测试猜测必须分开；只有活动 consumer/RTL、可复现编码结果或真实服务器证据支持的结论才能升级为强制规则。
3. **先建立外围拦截，再决定是否修改原生仓。** 当前路线以未修改原版 `ndp-sim` 为基线。初期采用只读审计和外围 fail-closed preflight；若确需修改 planner/encoder，必须在“向上游修复”与“切换到明确标识的补丁版本并重跑基线”之间做显式决策，不能在原版目录中静默打补丁。

因此最合理的依赖顺序改为：**身份与证据冻结 → 字段/行为真值表 → 规则草案 → 影子验证器 → 样例裁决 → 实现修复 → 微型硬件证明 → 算子族与整网闭环**。

### 10.3 初始问题台账

| ID | 初始发现 | 当前分类 | 进入强制规则前的裁决要求 |
|---|---|---|---|
| TGT-001 | planner `MAX_ROWS=8192`，本地 RTL `DDR_ROW_SIZE=6144` | 确认存在的跨源矛盾 | 冻结目标 profile；无服务器身份时按 6144 做地址上限负例和外围拦截 |
| ENC-001 | placement 最大重试后接受非零 penalty | 确认的 fail-open 实现 | 非零 penalty、fallback 物理 ID 和无效连接必须由外围验证器判失败 |
| ENC-002 | 未知字段可忽略，位宽溢出可截断，非法地址字符串可回退为 0 | 确认的 fail-open 实现 | 增加严格字段集合、条件必填、精确数组长度、范围和解析失败负例 |
| SA-001 | encoder `col=0,row=1`，RTL 宏 `row=0,col=1` | 物理行为已裁决；算子 layout 绑定仍阻塞 | 非对称微模型证明 legacy `col` 不转置、`row` 转置；开发模式必须从外部 layout contract 给出期望，不按名称猜 |
| CFG-001 | CONFIG 的 enable/update/clear 跨阶段继承未进入规则 | 静态状态机与外围序列已裁决；服务器 E4 待补 | 已写 update/reuse/disable 状态合同；跨 stage 推广前补真实两阶段回读 |
| LIVE-001 | 旧 Conv ping-pong 输入缺 B′/READ2 生产者 | 确认的负向结构样例 | 建立 stream→buffer→array→buffer→write 的生产者/消费者和完成性检查 |
| QNT-001 | quant/add handler 只 patch shape/stride，固定 JSON 常数未由模型 qparam 驱动 | 确认的能力缺口 | 定义每个量化参数的来源、编码、舍入、溢出和回读证明；未覆盖不得声明对应 ONNX 算子 |
| COV-001 | W3 有 78 节点；Conv 含 7×7 stride2 和 1×1 stride2，当前活动链无完整覆盖 | 确认的覆盖缺口 | 生成 node→lowering template→配置版本→证据等级的全覆盖清单 |
| DOC-001 | register CSV、expanded RTL 和若干 encoder 注释与活动代码不一致 | 文档漂移 | 只在活动字段真值表建立后修正文档，不用旧注释反向修改实现 |

### 10.4 R0：冻结目标身份和证据等级

状态：**已完成。** 身份、关键 SHA、候选哈希和 E0～E5 证据台账见 `.agents/decisions/ADR-010-operator-config-rule-r0-identity-evidence.md`。服务器 RTL 按用户确认暂视为与 GitHub/本地 `NDP_copy01` 一致，服务器侧 SHA 尚未机械核验。

1. 记录活动 `ndp-sim` commit、工作树差异、Python 依赖和 encoder/model_execplan 入口 SHA。
2. 记录本地 `NDP_copy01` 中活动 filelist 可达的 RTL、参数宏、loader/TB 入口 SHA；若用户能提供服务器活动身份，再记录服务器侧逻辑路径、版本或 SHA。无法取得服务器身份时显式标记 `server_rtl_identity=unknown`。
3. 建立证据等级：
   - E0：静态 JSON 可解析/可编码；
   - E1：本地结构、来源和重复生成通过；
   - E2：独立软件公式与正式输入/golden 一致；
   - E3：服务器装载、启动并自然完成；
   - E4：服务器真实回读与独立 golden 数值一致；
   - E5：同一语义覆盖边界、尾块、跨阶段状态并可推广到一个算子签名。
4. 为 `jsons/*`、Decode、MaxPool、node-0004、v18/v19 和根仓旧 Conv 样例逐项登记证据等级；服务器“能运行”不得自动升级为 E4/E5。
5. 冻结现有候选哈希，只读审查产生新报告路径，不向原候选目录写入审计结果。

R0 退出门：目标身份已记录或明确 unknown；每项结论有证据路径和等级；没有把历史说明文字当作活动 RTL 事实。

### 10.5 R1：建立 JSON→bit→RTL→数据布局真值表

状态：**静态退出门已达到，动态阻塞项显式保留。** 真值表见 `.agents/decisions/ADR-011-operator-config-rule-r1-field-truth-table.md`。已裁决资源数量/聚合位宽、固定拓扑、SA signedness 与物理转置、正向 loop、terminal-tag/keep、padding/tailing、空间 lane、CONFIG 跨 stage 状态及 completion 唯一终点；GA constant 特殊值、neighbor 动态计数、最终 DDR 握手、服务器两阶段/非对称回读和服务器 SHA 保留为 E4/E5 阻塞，不设默认值。

真值表按实际硬件模块覆盖 CONFIG、DRAM/ROW/COL LC、LC-PE、read/write stream、neighbor stream、6 个 buffer、SA、GA in/outport 和 GA PE。每个字段至少记录：

- JSON 完整路径、类型、是否必填、缺省值和条件启用关系；
- encoder `FIELD_MAP`、mapper、位宽、元素顺序、物理资源编号和最终 bit range；
- RTL configure register、宏、复位/clear/update 行为及数据通路作用；
- 合法枚举、signedness、单位、对齐、`value` 还是 `value-1`、精确数组长度和溢出策略；
- 与 shape/layout/slice/wave/last-index 的关系；
- 已验证样例、负向样例和仍未裁决项。

R1 必须单独解决或保留为阻塞项：

1. 地址格式、字节/word/subword 单位、bank/row/col 上限、remapping 前后身份和对齐；
2. stream target 到 READ0～3/WRITE0、buffer0～5、SA/GA inport 的固定拓扑；
3. SA A/B/C 端口的有符号性、bias、ping-pong 和 row/col 输出布局；
4. GA opcode、输入/输出转换的真实算术边界；
5. CONFIG enable/update 与前一 stage 状态的继承；
6. last bit/index、buffer lifetime、neighbor 计数与自然完成条件。

R1 退出门：所有活动字段都有唯一真值来源；冲突字段明确标记“已裁决”或“阻塞”，不得用默认 0 掩盖未知语义。

### 10.6 R2：起草新的可执行配置规则

状态：**已完成，并已在 R4 合入活动规则。** 设计、模式边界和验证顺序见 `.agents/decisions/ADR-012-strict-operator-config-rules-and-validator-design.md`；活动版本见 `.agents/rules/算子配置规则.md`。

新规则必须区分两条模式：

- **复现模式**：继续执行当前“只使用已有静态 JSON”的原版链，适用于已有候选和参考基线；
- **开发模式**：只有用户明确批准后，才允许从算子语义合同生成或修改静态 JSON；产物、工具身份和证据不能冒充原版配置。

规则正文至少补齐以下合同：

1. **目标 profile 合同**：RTL/loader/encoder 身份、slice/bank/row/col、buffer/SA/GA 规模；profile 不匹配即停止。
2. **严格 schema 合同**：未知字段、缺字段、错误 arity、非法 enum、非幂尺寸、位宽/有符号范围溢出、解析 fallback 全部失败。
3. **模型语义合同**：ONNX 输入顺序、shape axes、属性、dtype 和量化参数必须有唯一来源，禁止按文件名猜测。
4. **量化算术合同**：零点修正、bias 域、累加位宽、overflow、per-tensor/per-channel scale、舍入模式、饱和和输出零点逐项定义。
5. **物理布局合同**：NCHW/NHWC/blocked 变换、128-bit packing、通道/空间尾块、padding 值、slice/wave ownership 和 D 逆布局。
6. **stage DAG 合同**：一个 ONNX op 可降低为 accumulate/requant/relayout 等多个硬件 stage；依赖、部分和驻留地址、CONFIG 更新、自然完成和回读点必须显式。
7. **拓扑与活性合同**：每个启用输入、ping-pong 半区和输出必须有生产者/消费者；无悬空 buffer、提前覆盖、last-index 不闭合或写回未 drain。
8. **placement 合同**：零 penalty、无 sequential-ID fallback、同输入确定映射、所有连接在 RTL 可达集合内。
9. **地址与生命周期合同**：按目标 profile 校验容量、对齐、重叠、alias、remapping 和释放；Flatten 等 view 必须有显式 alias/lifetime 证明。
10. **独立 golden 合同**：golden 不能读取硬件输出、配置生成结果或同一实现的中间结果；公式、输入哈希、代码入口和比较域必须可审计。
11. **证据声明合同**：E0～E5 的允许措辞固定，不能用“mismatch=0”代替硬件执行或用“服务器运行”代替数值正确。
12. **覆盖合同**：每个 ResNet 节点必须绑定 lowering template 版本、配置哈希、参数、目标 profile 和代表性硬件证据。

R2 退出门：规则草案能把当前已知正例接受、已知负例拒绝，并对 SA-001 等未裁决项明确停止，而不是猜测默认值。

### 10.7 R3：实现外围 fail-closed 验证器并影子运行

状态：**本地退出门已达到。** 完整裁决见 ADR-013～ADR-015、ADR-018。当前 55 份活动 JSON 为 46 strict-valid、9 intentional-reject，55/55 的 D terminal 静态链包含 last_index=0；9/9 规范化副本均 strict-valid 且已取得零 penalty、无 fallback 的完整 mapping evidence。原始 9 份 legacy JSON 仍保持 intentional-reject，不被改写；其规范化副本分别通过字段编码等价、受限算子语义合同或固定参考提交 cache 的原生零代价复验。外围验证已经闭合 JSON、逐字段 encoded bit、mapping、真实 execplan/CONFIG、SCA、remap 后逐请求地址、qparam/layout/tail/stage/provenance 和隔离双跑确定性。

验证器只读取源 JSON、patched JSON、mapping、bitstream、execplan、SCA、target profile 和 provenance，输出独立报告。必须覆盖：

- schema、条件必填、枚举、范围、精确 arity 和派生字段；
- 编码前值与编码后 bit 的逐字段对照，拒绝 wrap-around、默认 0 和未知字段；
- mapping penalty、fallback ID、重复/别名资源和 RTL 不可达连接；
- stream/buffer/SA/GA producer-consumer、ping-pong、lifetime、last-index 和完成性；
- 地址 row<profile 上限、容量、对齐、重叠、alias、remapping 和 no-free 峰值；
- CONFIG 跨 stage 状态模拟；
- 量化参数、layout、尾块和 stage DAG 的来源闭包；
- 同输入双跑的 JSON、mapping、bitstream 和 execplan 确定性。

必须加入故障注入负例：未知字段、少/多一个数组元素、位宽溢出、非法地址字符串、非零 placement penalty、缺 B′/READ2、非法 row、错误 CONFIG 复用、尾块越界和 qparam 未绑定。每个负例都要证明验证器在原生 encoder 可能继续时仍 fail closed。

R3 退出门：当前实际 55 份活动 JSON 和选定硬件正/负样例均有报告与明确预期身份；所有失败可定位到第一个字段/连接/stage；验证器本身有正负测试且不改写输入。

### 10.8 R4：样例裁决与规则正式切换

状态：**已完成。** 切换前规则归档为 `.agents/archive/operator_config_rules_pre_r4_20260723.md`；活动 `.agents/rules/算子配置规则.md` 已纳入复现/开发模式、严格 JSON/CONFIG、零 penalty mapping、逐 bit/execplan、逐请求地址、SCA/语义合同和 E0～E5 声明边界。

1. 对每个影子失败区分：真实配置错误、目标 profile 不匹配、encoder fail-open、文档漂移或验证器误报。
2. 当前成功基线若被新规则拒绝，先解释差异并用最小样例裁决，不能为了保持“通过”放宽规则。
3. 只有正/负样例结果稳定后，才用补丁更新 `.agents/rules/算子配置规则.md`；服务器包规则只补与配置证据交接直接相关的部分，避免职责重叠。
4. 正式切换时记录旧规则归档、变更理由、受影响候选和重新认证范围。

R4 退出门：活动规则、验证器和证据等级一致；旧候选是继续有效、限制声明还是撤权均有明确裁决。

候选裁决：已服务器完成的 Decode 保留 E3，且新本地 evidence 通过严格链，但不升级为 E4/E5；9 份 legacy 原始 JSON 保持 intentional-reject；MaxPool/node-0004 的失败证据和待测候选身份不因规则切换改变；两 stage Decode 仅是本地 CONFIG/address 诊断证据，不是服务器候选。

### 10.9 R5：实现修复与算子 lowering

状态：**依赖 R4，且修改 `ndp-sim` 前需要用户明确批准活动来源策略。**

优先顺序：

1. 目标 profile/地址容量和所有 fail-open 路径；
2. SA row/col、CONFIG 状态、stream-buffer 活性等会导致错误数据或停滞的公共语义；
3. 统一 typed lowering request，显式携带 shape、layout、dtype、qparam、stage 和 slice/wave 参数；
4. Conv 完整 accumulate+requant，并补 7×7 stride2、1×1 stride2、3×3 和尾块；
5. QLinearAdd、QuantizeLinear、DequantizeLinear、GlobalAveragePool、QLinearMatMul；
6. Flatten/view alias 和跨节点内存生命周期。

若选择修改原生仓，只有两种允许路径：向固定上游提交修复并更新锁定 commit，或建立明确标识的项目补丁版本；两者都必须重跑 Decode 格式基线和受影响算子，禁止继续称为未修改原版。

### 10.10 R6：最小 RTL/服务器语义证明

状态：**依赖相应 R5 修复。**

硬件测试按“能区分候选语义”的非对称小数据设计，而不是只测试全零或对称矩阵。最低测试集合：

1. SA row/col 非对称矩阵与 D 逆布局；
2. INT8 A 有符号、B 无符号及边界值；
3. CONFIG update/reuse/disable 两阶段序列；
4. ping-pong 两个半区、缺生产者负例和自然完成；
5. uint8 MaxPool 边界/padding；
6. requant 非零 zero-point、per-channel scale、正负 accumulator、ties-to-even、0/255 饱和；
7. stride2、padding、通道/空间尾块；
8. 地址接近 6144 行边界以及非法行拒绝。

每项必须保存正式输入、独立 golden、配置/bitstream/execplan 哈希、服务器原始回读和逆布局比较。只有 E4/E5 证据才能批准对应语义推广。

### 10.11 R7：ResNet50 覆盖与整图门

状态：**最后阶段。**

1. 从 W3 `model_graph.json` 机械生成 78 节点覆盖表，至少覆盖 53 Conv、17 QLinearAdd、2 QuantizeLinear、2 DequantizeLinear、1 MaxPool、1 GlobalAveragePool、1 QLinearMatMul、1 Flatten。
2. Conv 同时按 4 种几何类别和 20 种完整 shape 签名检查；不允许只用“1×1/3×3 已支持”替代 stride、pad、通道和尾块证明。
3. 每个节点绑定 typed request、lowering template/version、stage DAG、配置哈希、qparam、布局、slice/wave、地址和证据等级；任何空项都阻塞整图声明。
4. 在目标 6144-row profile 下执行全图内存生命周期、alias 和峰值检查；若 no-free planner 不满足容量，先实现可证明的释放/复用策略，不能提高虚构容量。
5. 先做逐算子/逐 stage 回读，再做代表性 block，最后做整网；首个差异按节点、stage、slice、物理 offset 和公式定位。
6. 只有 78/78 节点覆盖、全部目标地址合法、无未裁决语义项且最终输出与独立 W3 golden 满足约定比较标准后，才能声明“能够正确生成 ResNet50 对应算子配置”。

### 10.12 本分支当前下一步

R0～R4 已完成；详细本地闭环见 ADR-015。最终两 stage Decode bundle 为 `artifacts/operator_config_validation/r3-execplan-evidence/decode_summac-two-stage-seed42-v4/`：113 条 64-bit 指令、2 Load_Config、2 Start_Comp、每 stage 54 条 base Write_Reg、1848 次请求、504 个唯一地址、25 个确定性文件双跑一致，execplan SHA-256 为 `5885868d008ef3de16e65aef11df2e47f5ce386a68f096af370ea37bf9c84344`。它闭合连续两次真实 update，不冒充服务器 reuse/disable 证明。

当前下一步是 R5，但修改活动 `ndp-sim` 或建立正式配置 lowering 前必须由用户在以下来源策略中明确选择：

1. **上游修复**：在固定 GitHub `ndp-sim` 仓提出/合入修复，更新 `repos.lock.json` 后重跑 Decode 和全部受影响证据；
2. **项目补丁版本**：保留上游 clean commit，建立明确命名、哈希锁定的项目 patch/toolchain 身份，所有新配置和候选不得再称为“未修改原版”。

获得授权后，R5 的首批实现顺序为：先封堵 `MAX_ROWS=8192`/6144 profile 和 mapper fail-open，再实现 typed lowering request 与 SA/CONFIG/stream 活性公共语义，随后补 MaxPool、Conv accumulate+requant 和其他 ResNet50 算子族。R6 的服务器 E4/E5 与 R7 的 78 节点覆盖仍后置。

原先 4 个 mapping-blocked legacy 规范化配置已全部闭合；仍可并行接收的外部项只剩 MaxPool/node-0004/CONFIG 边界的服务器原始结果，且不得改写现有候选身份。

### 10.13 R5 项目补丁策略执行状态（2026-07-23）

用户已选择“项目补丁版本”，R5 不再等待来源策略授权。活动 `ndp-sim@ec124245...` 保持只读；项目补丁身份为
`resnet50-ndp-toolchain-6144-v1`，清单见 `contracts/ndp_patch_toolchain_v1.json`，决策见 ADR-016。

已完成：

1. 修正 6144-row profile、DRAM LC 编号解析、零 penalty 漏 return，以及退火成功后丢失显式 `GROUP` 绑定；
2. mapping/execplan evidence 生成器支持在隔离副本中应用补丁并把清单及 SHA-256 绑定进证据；
3. patched Decode mapping 通过零 penalty、无 fallback、独立 bit 镜像；不再依赖第二轮缓存重试；
4. patched Decode execplan 两个隔离运行的 15 个确定性文件完全一致，execplan、包、语义合同和逐请求地址均通过；
5. `contracts/resnet50_project_closure.json` 已机械绑定 78 节点、133 stage、93 runtime edges、55 个内部 tensor 和全部 W3 独立公式结果。
6. 全量本地回归已在项目 `.venv` 中通过：2026-07-23 最终结果为共 460 项，443 项通过、17 项按环境条件跳过、0 失败，测试框架耗时 999.012 秒（外层命令墙钟约 1005.3 秒）；其中 v20 Conv 硬件包、resolution overlay、MaxPool/node0004 候选包均已纳入回归，本地重建、回读或严格包校验通过。
7. v20 页对齐执行计划不再沿用 v19 的 4-KiB 头尾拆分假设；runner/parser 合同会按 `ExecutionPlan` 是否实际含 `chunked_transport` 动态声明。测试回读镜像也改为从 `dump_contract.json` 取得 P/两个 staged-D half 的地址和长度，避免布局合法变化导致假失败。
8. 历史 W5 transport 合同继续绑定其真实验证来源 `NDPFuncModel@a1d975e...`；协作者 bootstrap 锁选择的较早可分发版本不得反向改写历史证据身份。
9. `contracts/resnet50_r5_lowering_bundle.json` 已把全部 133 stage 转成哈希绑定的 typed request；request set SHA-256 为 `9da4423bb293a047c9a2dac945270d56eab9fe114146a2f6638e43c655fa341b`。每项保留 dtype/shape/axis/value hash、前驱 DAG、补丁身份和 blocker；当前 133 项均 fail closed，不能把“request 完整”误写为“target config 已生成”。
10. `contracts/resnet50_e4e5_handoff_readiness.json` 已覆盖 10 种硬件 stage 代表，固定 E4 run1/E5 run2 证据要求；`tools/run_e4e5_server_protocol.py` 只接受用户批准的 load/start/wait/readback argv，以 `shell=False` 执行并收集哈希回执。模板故意不可执行，正式配置 0/133 时 ready package 仍为 0/10。
11. `node-0004 accumulate-wave-0 nopp-r1` 已形成受限本地候选链：严格物化、最终地址绑定、重新 mapping、双运行 execplan、SCA、逐请求地址和 typed qparam/layout/stage 合同均通过。最终 execplan SHA-256 为 `a5d9edf2fbd51f2107b9fe7845f4716786a61797be7c9e38aca3ede9009a0711`，请求按 multiplicity 枚举 748160 次、704368 个唯一地址；该链明确不是正式配置或服务器通过。
12. execplan evidence 在仍逐条枚举并验证所有请求的前提下，只发布每 stream 的 count/hash/首尾样本，不再保存 2.65 亿字节的逐地址明细；node-0004 请求报告缩小为 229259 字节，验证强度不变。
13. 9/9 legacy 规范化配置现均有零 penalty mapping：3 份 GEMM 使用 `ndp-sim-ref@d4ffc32...` 的 `fab05601add9259e` cache；16×16 MaxPool 使用同一固定提交的 `dc65063f38e8722f` cache。两类 cache 都只复制进隔离工具副本，并由原生 mapper 实际加载、重新计算 exact cost=0 后才接受。
14. MaxPool 的 `padding_reg_value:null→0` 只由 `contracts/maxpool_uint8_zero_padding_contract.json` 对单一源 SHA 授权：W3 输入 dtype 为 uint8，隔离 RTL 对 65536 个字节对/262144 lane 检查证明无符号 max，读流 RTL证明越界字节由 padding 寄存器替换。此合同只清除 legacy 规范化阻塞，不代表完整 MaxPool target completion、E4 或 E5。

当前精确状态：W3 软件公式 78/78；W4 两个整网候选场景通过；typed lowering request 133/133；本地候选 execplan 链 2 条；legacy 规范化 mapping 9/9；正式 ResNet50 target config 0/133；历史候选涉及 11 个 stage，但只具有候选身份；正式服务器 E4=0、E5=0。因此本地可独立闭合的身份、规则、映射、请求和交接审计已经闭合，“能够生成并在 RTL 正确运行完整 ResNet50”仍被正式配置来源与服务器执行入口阻塞。

下一执行顺序：typed request 层已经闭合，但活动 execplan handler 对这些 qparam/constant 的正式消费仍未闭合；继续按 Conv accumulate、requant、Add、Quant/Dequant、MaxPool、GAP、MatMul 各闭合一个非对称代表。每类只有服务器 E4 与重复 E5 通过后才推广到同类 shape；最后生成 133 stage、重跑 78 节点地址/生命周期、组装整网并做两次服务器运行。真实服务器 loader/启动/等待/回读入口未保存在本仓库，仍须通过已提供的严格协议模板由用户填写，不能自行发明。

## 11. 配置语料审计与 stage→JSON 后端进度（2026-07-23）

用户已明确批准从 `ndp-sim/jsons`、根仓服务器参考包和寄存器表提炼配置语义并推进开发模式。详细决策见 ADR-019。

本轮已完成：

1. 55 份活动 `ndp-sim/jsons` 与根仓 `jsons` 中 12 份可识别算子配置已形成规范语料及来源合同。依据 ADR-021，其中根仓 12 份和固定上游提交原生且未改变的 53 份，共 65 份按正确、高强度参考基线处理；两份后加 `node0004*` 不在授权内。
2. 新发现并绑定 `server_returns/decode_max_fp32_simresults_1/simresults/sim.log`：28 slice preload、start、66-cycle completed、每片 1 个 MSE4 写数据和自然退出均存在；有效最低 32-bit 与本地 D Golden 28/28 一致，`decode_max_fp32N_fp32N` 升为 E3。启动命令遗漏 `+SCA_CFG_D`，testbench 默认寻找 `sca_cfg_D_softmax.json` 并跳过正式 D readback，故仍非 E4；详见同目录 `ANALYSIS.md`。
3. `node0004_nopp_r1_sim_results_2` 缺失多份 A/B/C 和 bitstream，随后跑到 100 ms；该服务器尝试无效，不能判配置通过或失败。
4. Excel 已机械转换成寄存器语义合同，并与 55 份 JSON 及当前 encoder `FIELD_MAP` 交叉。表内保留 13 项 declared-width/range 冲突，不能直接作为位偏移真值。
5. 已对两个 MaxPool shape 和 10 个模板→服务器实例做逐叶差分。MaxPool shape 变化包含拓扑变化，证明必须有 ScheduleIR，而不是只 patch 数值。
6. 首个 stage backend 已实现：
   - `hwop-0002-00 MaxPoolUint8` → ScheduleIR + strict address-unbound JSON，64 tile 分三波 `[28,28,8]`；
   - `hwop-0073-00 View` → 零拷贝 alias；
   - 其余 8 种 hw op type 按 catalog 中 blocker fail closed。
7. 首个生成物为 `configs/stage_codegen/hwop-0002-00-v1`，状态严格保持 candidate/non-formal；正式 target config 仍为 0/133，E4/E5 仍为 0。

机器入口：

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\build_operator_config_corpus.py
& $py tools\build_register_semantics_contract.py --workbook <register-map.xlsx>
& $py tools\build_operator_config_rule_evidence.py
& $py tools\build_stage_config_backend_catalog.py
& $py tools\generate_stage_operator_config.py `
  r5:hwop-0002-00 configs\stage_codegen\hwop-0002-00-v1
```

下一实现顺序：

1. Conv accumulate：从 node-0004 strict JSON 提取 loop/stream/SA 结构，闭合 signed A、unsigned B、非对称 SA layout、K tile/psum 和 shape schedule；
2. Requant：闭合 per-channel constant 放置、round、saturate、zero-point；
3. Add 与 Quant/Dequant；
4. GAP sum + average requant；
5. MatMul INT8 SA 与 tail；
6. 每族生成一个非对称微测包，取得 E4 和重复 E5 后才推广到同类 stage。

## 12. Conv / requant 后端推进状态（2026-07-23）

本轮已按 ADR-019 的实现顺序完成以下工作：

1. 完成两个配置目录的授权及运行证据分层：
   - `ndp-sim/jsons` 55 份中，53 份与固定云端提交逐文件一致并接受为正确、已测试
     参考；两份 `node0004*` 是项目后加文件，不在授权内；
   - 根仓 `jsons` 中 12 份可识别参考配置继续按用户授权正确配置处理；
   - 逐文件原始回执仅用于审计本项目具体运行：精确正向 E3=2、精确硬件负证据=2、
     无效硬件尝试=1、精确数值 E4=0，不再否定或阻塞参考配置语义提炼。
2. 完成 node-0004 accumulate wave-0 静态调度合同：
   - 完整逻辑算子 64 tile；
   - 当前证据覆盖 28 tile，剩余 36 tile；
   - signed-A/unsigned-B、C=bias、D=INT32 psum、SA 三输入零 ping-pong、
     零罚分 mapping、确定性 execplan 和 748160 次请求均已哈希绑定；
   - 完整 Conv emitter 继续阻塞。
3. 完成 node-0004 requant 本地语义合同：
   - 64 个 multiplier、8 个 GA lane、8 组 channel shard 完整覆盖；
   - W3 3,211,264 元素重放 `mismatch=0`；
   - 只读取活动 `ndp-sim` 量化模板，未读取 `ndp-sim-ref` 或旧 requant 产物；
   - 活动量化模板的 rounding/saturation/GA 放置按授权正确语义采信；
   - node-0004 派生 requant 实例尚未物化并通过严格链，emitter 继续阻塞。
4. 复核 `node0004-nopp-r1-v2` 服务器候选：
   - 378 个 payload 文件；
   - 28 slice、336 个 A/B/C/D 伴随文件；
   - `install/cfg_pkg` bitstream 存在；
   - 本地完整性和缺文件注入测试通过。

当前下一步按“参考规则闭合”和“派生运行放行”两条线推进：

1. node-0004 wave-0 不是上游授权正确配置，只能作为静态诊断线索。Conv 应优先从
   53 份上游原生已测配置、RTL 和 register map 提炼 SA/LC/stream/CONFIG 规则，再
   用这些独立规则反向审查 node-0004，并补齐 `[28,28,8]` 三波 schedule、36 个新增
   tile、跨 wave CONFIG 状态和地址生命周期；
2. 从授权正确的活动 quant 模板物化 node-0004 requant 派生实例，闭合 typed qparam、
   地址绑定、mapping、bitstream、execplan 和独立 uint8 golden；
3. 不再等待上述参考模板逐文件 E4，即可继续提炼 Add、Quant/Dequant、GAP、MatMul
   的 exact-template 语义和 ScheduleIR；每族必须先反向复现已授权配置，再开放
   address-unbound candidate emitter；
4. `node0004-nopp-r1-v2` 及后续派生候选仍须用完整候选树取得新原始回执。
   服务器 E4 与重复 E5 继续作为派生 ResNet50 配置晋升 formal 的放行门。

## 13. 完整 stage→算子 JSON 配置体系（2026-07-23）

状态：**规则覆盖已完成，发射器实现进行中。** 决策见 ADR-022，机器入口为
`contracts/operator_config/stage_config_system_v1.json`。

本轮结果：

1. 133/133 typed stage 均生成唯一 plan，覆盖 10 个 hardware stage family；每项绑定
   request hash、logical geometry、shape signature、typed parameter schema、前驱、
   candidate blocker 和 formal blocker。
2. 顶层 JSON 的 `CONFIG`、LC/PE、stream、buffer、SA、GA、n2n 已分配单一规则所有者，
   stage→JSON 被拆成 logical schedule、physical schedule、numeric kernel、
   boundary/keep/tail、跨 stage CONFIG、地址后绑定和 E4/E5 九层。
3. 规则实现按四条公共分支组织：control/alias、GA reduction、GA affine/requant、
   SA INT8 accumulate；避免为 133 个 stage 重复编写独立生成器。
4. 当前状态为 candidate JSON 2、zero-copy 1、blocked 130、formal 0；完整体系不等于
   全部 emitter 已实现。
5. GAP 精确模板已闭合本地中心化求和的特例：`hwop-0071-00` 的
   `x_zero_point=0`、49 元素、8-lane `int32_sum` 和 zero-padding 单位元均有哈希合同，
   严格物化配置位于
   `configs/native_ndp_sim/avgpool_config_2048_7_7_strict_v1/config.json`。
   该 stage 的 typed zero-point transport、跨 slice 判定和 terminal completion 已由
   DeepSeek reduction 规则及精确 schedule 闭合；地址/mapping/execplan/SCA 和 E4/E5
   未解除。第二个 candidate 位于 `configs/stage_codegen/hwop-0071-00-v1`。
6. GAP 合同改为直接绑定不可变 typed stage，避免 lowering 与 resolution overlay
   互相引用形成哈希循环。

下一实施顺序：

1. 为 GAP candidate 补地址绑定、mapping/bitstream/execplan/SCA 和服务器 E4/E5；
2. 完成 Requant 全 batch/wave dispatch 和派生实例严格链，再提取 GA affine 公共层给
   Add、Quant、Dequant、AverageRequant；
3. 从授权上游模板、RTL 和 register map 闭合 SA INT8 公共层，再审查 Conv/MatMul；
4. 每族完成非对称边界微测、E4 与重复 E5 后才批量展开相同 shape family。

重建与定向验证：

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\build_deepseek_stage_ir.py
& $py tools\build_deepseek_reduction_rules.py
& $py tools\build_deepseek_primitive_rules.py
& $py tools\build_gap_sum_padding_contract.py
& $py tools\build_r5_resolution_overlay.py
& $py tools\build_r5_lowering_bundle.py
& $py tools\build_conv_stage_schedule_evidence.py
& $py tools\build_requant_stage_semantics_evidence.py
& $py tools\build_stage_config_backend_catalog.py
& $py tools\build_stage_config_system.py
& $py tools\build_project_closure.py
& $py tools\build_e4e5_handoff_readiness.py
& $py -m unittest `
  tests.test_gap_sum_padding_contract `
  tests.test_r5_resolution_overlay `
  tests.test_r5_lowering_bundle `
  tests.test_stage_config_backend `
  tests.test_stage_config_system `
  tests.test_project_closure `
  tests.test_e4e5_handoff -v
```

## 14. DeepSeek stage 反向提炼进度（2026-07-23）

状态：**StageIR、归约选择和 GA/SA/N2N 审计已机器化；执行复用原生 ndp-sim，
INT8 派生仍 fail closed。** 决策见 ADR-023、ADR-024。

已完成：

1. `deepseek_stage_ir_crosswalk_v1.json` 将 47 份固定上游授权模板精确绑定到 87 个
   graph、158 次 stage 出现和 40 种 stage type；每项保存 graph location、operator id、
   shape/dtype/source、used-slice mask、模板 SHA、base info 和可用服务器实例。
2. `deepseek_reduction_rules_v1.json` 证明 RMSNorm 的
   `local summac → remote sum → mac_SFU → mul` DAG。remote reduction 只在一个
   reduction domain 被 slice 分割时插入；ResNet GAP 每个活动 slice 获得一个完整 sample，
   所以不需要 remote sum。
3. GAP 精确 schedule 为 16 个活动 slice、每 slice 一份 sample、256 次 32-byte 写传输，
   共覆盖 2048 个 int32 channel；`x_zero_point=0` 是编译期特化，terminal 链到
   `last_index=0`。因此 GAP 已成为第二个 address-unbound candidate。
4. `deepseek_primitive_rules_v1.json` 覆盖 22 份 GA add/mul/mac 模板（61 次 stage 出现）
   和 6 份 SA GEMM/GEMV 模板（17 次 stage 出现）；两组 local/ring 对都证明：
   CONFIG mask 和 SA 核心模式保持一致，但 K 分块、loop/stream、`nbr_enable` 与 N2N
   必须联动，不能只给 local JSON 增加一个 `n2n` 字段。
5. 发现 4 份授权正确模板与当前 strict target schema 不兼容：一份 vector-add 在 write
   stream 保留四个原生不编码的 read-only 字段；三份 prefill GEMM 使用 legacy
   `mem_idx_mode[2]=0` sentinel。它们的精确上游身份仍有效，但不得静默规范化为派生
   target；严格物化前必须由 encoder/RTL 等价合同逐项裁决。
6. 回查原仓确认 `ndp-sim/model_execplan` 已提供完整执行骨架：原生 graph parser、
   48 个按 op type 的 shape-driven control handler、静态 JSON patch、地址规划、
   bitstream、Write_Reg/Start_Comp、execplan 和 SCA。全部 40 种 graph-referenced
   DeepSeek stage type 已在原生 handler registry 中；`deepseek_primitive_rules_v1.json`
   因此改为 native capability/provenance 审计，不是第二个生成器。

下一步：

1. 对上述四类 strict-compatibility 差异建立显式 legacy-field 裁决；保持原模板只读，
   不放宽未知字段和 enum 的全局 fail-closed 规则。
2. 对能精确映射到 native op type 的 Requant/Add stage，只生成原生 op_json 适配并调用
   `model_execplan/main.py`；本项目不再另写 LC/stream/GA patcher。INT8 qparam、
   rounding、saturation 仍由 typed contract 独立验证。
3. 对 native registry 尚无精确类型的 SA INT8 Conv/MatMul，先结合 RTL/register map
   闭合非对称 A/B、bias/psum、tail tile 和跨 wave CONFIG；获批后在隔离
   `ndp-sim` 补丁副本中新增原生 handler，而不是在主项目建立平行生成器。
4. 任何新派生配置继续依次经过 strict materialization、address/mapping/bitstream、
   execplan/SCA、独立 golden、E4 和重复 E5。

## 15. GAP 原生闭合与 Conv＋Requant 优先分支（2026-07-23）

状态：**GAP 与 node-0004 Requant 已达到“本地闭合、只待硬件”；node-0004 Conv
完成全三波原生打包，但仍有 SA/bias-psum 语义门，不能误报为只待硬件。**

本轮完成：

1. GAP `hwop-0071-00`：
   - 原生 execplan 双跑一致，execplan SHA-256 为
     `7b221b48a43ddd630f90c2f653f675b5f72d01bd3eb4a984c8cef27b14fc7ba5`；
   - 143392 次逐请求地址校验全部通过，logical/padding mismatch 均为 0；
   - 32 个 A/D 矩阵文件齐全，候选位于
     `artifacts/operator_config_validation/r5-server-candidates/gap-hwop0071-sum-v1`，
     payload tree SHA-256 为
     `87f78f547f89bd6b7b8840dd36e7bc0464719e2b73d7a6198528981b86a64c8b`；
   - 状态为 local-valid/server-not-claimed，是第二个真正只待硬件的算子。
2. node-0004 Requantize：
   - 从活动、授权正确的
     `ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json` 派生 3 wave×8 shard，
     24 个精确 operator type 和 24 份地址绑定 strict JSON；
   - 16 个样本、64 个通道完整覆盖；W3 独立 INT32→UINT8 重放
     3211264 元素 mismatch=0；
   - 24 份原生 mapping 均 penalty=0、fallback=false；原生双跑 245 个确定性文件
     一致，execplan SHA-256 为
     `3fc2851fb0dbc3dff255fd5c530f0a9f139fc8e9c5e5a127ec0a8c3b68b65662`；
   - 1003520 次逐请求地址校验 issue=0，256 个 A/D 矩阵齐全；候选位于
     `artifacts/operator_config_validation/r5-server-candidates/node0004-requant-full-v1`，
     payload tree SHA-256 为
     `607539c2ef6dd962214f1905539c32d75695a60f1de924e04e878e7c655645d3`；
   - 该包使用独立 W3 accumulator，Requant 算子自身只待硬件，但不包含 Conv 前驱执行。
3. node-0004 Conv accumulate：
   - 从当前 strict 零 ping-pong 配置只派生地址，形成 `[28,28,8]` 三波，
     样本分派为 `7+7+2`，不读取历史失败包或 `ndp-sim-ref`；
   - 3 份 mapping 均 penalty=0、fallback=false；原生双跑 35 个确定性文件一致，
     execplan SHA-256 为
     `e89da926d71d9c155e508235fdfda246dc8c12ea943cf49c0028c9bf22d02526`；
   - 1710080 次逐请求地址校验 issue=0，256 个 A/B/C/D 矩阵齐全；候选位于
     `artifacts/operator_config_validation/r5-server-candidates/node0004-conv-three-wave-v1`，
     payload tree SHA-256 为
     `5d95edcce50345919a0ddde3147bed99c64a25fc34e7a80657203953c6d8bf42`；
   - 该配置是项目后加、未经授权为已测正确配置；当前只解除 full-wave/package
     缺口，不解除 `B_CONV_INT8_SA`、`B_CONV_BIAS_PSUM` 或 E4/E5。
4. 新增 patchset 都只作用于隔离工具副本：
   - `resnet50-ndp-toolchain-6144-requant-v1` 注册 24 个精确 Requant handler；
   - `resnet50-ndp-toolchain-6144-conv-v1` 注册 3 个精确 Conv wave handler；
   - handler 只做 ABI/slice fail-closed 校验，语义寄存器继续来自各自哈希绑定 JSON，
     地址、bitstream、execplan 与 SCA 仍由原生 `model_execplan` 生成。
5. 定向回归 26 项通过；Conv 与 Requant 的 matrix-complete package validator 均
   `valid=true`、missing matrix=0。

当前不能越过的边界：

1. 两个候选是独立执行包，不是同一 execplan 中的 Conv→Requant 零拷贝链。
   Conv D 为 HWC16 INT32，独立 Requant A 为紧凑 HWC8 INT32；直接交接还缺 K8
   half 基址偏移、64-byte spatial stride、slice owner 和跨 stage CONFIG/lifetime
   的机器合同。现有 graph source schema没有子 tensor byte-offset，禁止静默拼接。
2. 53 个 Conv accumulate 与 54 个 Requantize 共 107/133 stage，但当前只闭合
   node-0004 这一对代表。Requant 的 per-channel 参数、channel shard 和空间 shape
   推广，以及 Conv 的 27 种 shape/tile、3×3、stride/padding/tail 均未批量生成。
3. 正式 target config 仍为 0/133，E4=0、E5=0；本轮本地包不改变 formal 计数。

下一执行顺序：

1. 先对 GAP 与独立 Requant 包各取得 E4、重复 E5；它们已没有本地结构/数值缺口。
2. 对 Conv 三波包做非对称 SA signed-A/unsigned-B、bias/psum 和 row/col 回读，
   用原始 P dump 裁决三个剩余语义门；失败时定位到具体 wave/slice/物理 offset。
3. 在 Conv 语义门通过后，扩展原生 graph/source 合同表达 K8 half offset，生成
   HWC16-strided Requant 变体并闭合同一 execplan 的 Conv→Requant 物理交接；
   不以 host 重排冒充零拷贝。
4. 以已通过的 1×1 代表提取 shape-parametric 公共层，按
   1×1 stride1 → 1×1 stride2 → 3×3/padding → channel/spatial tail 的顺序覆盖
   Conv/Requant 107 stage；每个新 shape family 仍须非对称微测和 E4/E5。

## 16. GAP 硬件启动预检（2026-07-23）

状态：**本节是服务器运行前的历史预检，已被 0.3.5 的 v7 动态根因和本轮 v10
stock-RTL 复现取代。GAP 确实不走 `int8_max` 缺陷，但命中独立的
`B_GAP_GA_ACCUM_STATE`，当前不得继续称为“只待 E4/E5”。**

1. GAP-sum 走 `uint8toint32=true` 与 8 路 `int32_sum`，不走已确认有缺陷的
   `int8_max` pipeline；RTL 对 INT32 pipeline0 的 backpressure 与 terminal tag 有独立
   路径，但这不能证明 INT32 transout/outbuffer 安全。v7/v10 已证明其
   count-underflow 与 invalid-slot C reuse。49 个 UINT8 的最大和为 12495，不存在
   INT32 溢出；本例
   `x_zero_point=0`，补到 56 元素的 0 padding 是严格加法单位元。
2. 专项 6 项回归与 `validate_gap_server_candidate` 通过；候选仍绑定
   payload tree SHA-256
   `87f78f547f89bd6b7b8840dd36e7bc0464719e2b73d7a6198528981b86a64c8b`，
   execplan SHA-256
   `7b221b48a43ddd630f90c2f653f675b5f72d01bd3eb4a984c8cef27b14fc7ba5`。
3. 该结论只覆盖 GAP 的 INT32 sum stage；完整 QLinearGlobalAveragePool 的 `/49`
   与 UINT8 requant 仍由 `B_GAP_DIV_REQUANT` 阻塞，不能用本次 sum 硬件结果代替。
4. 用户已把本轮范围收窄为只生成服务器消费文件夹，不要求本地发明或执行服务器
   runner。交接目录为
   `artifacts/operator_config_validation/r5-server-workloads/gap_hwop0071_sum_graph`：
   顶层文件类别与已跑通的 `decode_summac_fp32N_fp32N_graph` 一致，SCA 直接位于根部；
   GAP 按真实 used-slice mask 保留 16 个 slice，每个 slice 均有 A/D 各三份伴随表示，
   没有伪造其余 12 个 slice，也没有 overlay、ZIP、runner、barrier 或 Bank_data。
5. 该目录含 113 个文件（manifest 外 112 个），34 条 SCA path 全部存在，服务器读取的
   128-bit payload 全部为 LF，`Exec_Length=17` 与 execplan 17 行一致；`.bin` 与
   128-bit 文本逐字反解一致，十进制视图按 A=UINT8、D=INT32 逐元素一致。payload tree
   SHA-256 为
   `8f644eaac10f0994cc657a23a44604de5aa1c55bbbf4371f26f3802a55d18c56`。
6. 真实运行时仍必须把同一消费目录根部的 `sca_cfg.json` 与 `sca_cfg_D.json` 同时显式
   绑定到 testbench；在用户返回原始服务器日志与 readback 前只记本地交接完成，不记
   E4/E5。
7. 预检同时发现新增诊断 graph 使配置语料索引过期；已机械刷新 corpus、StageIR、
   primitive/reduction、R5 overlay/lowering、backend 与 stage-config system。全局
   project-closure 的再生成停在旧 MaxPool semantic/candidate 对旧 lowering 哈希的绑定，
   这是全局旧候选重冻结事项，不影响 GAP 候选自身验证，但不得误报全局交接已恢复。

## 17. GAP 返回验收与通用故障定位（2026-07-23）

状态：**通用返回验收器、GAP 严格 profile 和 optional 低频观测器已完成本地实现与
历史回归；等待真实 GAP 返回，尚未形成 E4。**

1. `tools/analyze_native_ndp_server_return.py` 可直接读取任意原生 NDP 返回目录或 ZIP，
   从工作负载两份 SCA 自动推导 preload、Exec_Length、活动 slice 和 D 回读合同；GAP
   额外绑定 `contracts/server_return_profiles/gap_hwop0071_sum_v1.json`。
2. 工具依次定位 invocation、SCA、preload、execplan、dispatch、slice start、读请求、
   读返回、compute finish、写地址、写数据、全局完成、正式回读和数值比较，并对历史
   FP32 缺回读、错误 SCA、INT8 MaxPool 无写数据三类返回给出不同分类。
3. `NDP_copy01/native_return_observer.svh` 是 plusarg 门控的只读观测器；当前本地 TB
   只新增一条 include，不改 RTL 功能。它监测目标 slice 的 CONFIG/exec/completion、
   MSE/bank 握手、buffer4/5、SA 输入/输出与 buffer↔SA tag/backpressure，以及八个
   GA PE 的 pipeline0/backpressure，并以 heartbeat 和持续 `STALL` 低频落盘。前者
   覆盖历史 Conv 在 READ_STREAM3→buffer4→SA→buffer5 区间的定位缺口；观测到 STALL
   时验收器 fail closed，不能被完整主日志或碰巧匹配的 D 覆盖。
4. 下一步只需服务器用同一冻结 GAP 目录、同时显式绑定 SCA/SCA_D，并在重新 compile
   后加入 observer plusarg；返回 `sim.log`、实际 D、gexec/local/SEM/observer 日志。
   本地随后生成 run1 报告并人工核对；只有数值、运行和服务器/RTL identity 同时闭合
   才升级 E4，再用独立 run2 形成 E5。
