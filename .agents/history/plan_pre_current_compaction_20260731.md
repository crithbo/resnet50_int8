# ResNet50 INT8 执行计划历史快照

> 归档于 2026-07-31；当前状态与命令请查看 `.agents/plan.md`。

## 0.0K 2026-07-31 三算子最新动态裁决与唯一可运行包

三条主线均继续遵守：不重复已接受 numeric/workload；超时或人工中断先按长时间卡死
审计；本地无法唯一定位时才生成窄诊断包；最终 ZIP 必须 current-rule 自检、
真实 runner 到安全 compile stub 正控及全部负控 fail closed。

### Conv/SA node0004

- v18 正式 return 的 receipt/CRC/exact-set/allowlist/preflight/compile 均通过；
  `compile=0, run wrapper=0`，但由四个 qualified 零增量窗口触发诊断 fatal，
  非 DUT natural terminal；formal D=0，E4/E5=false。
- `A_REUSE_BOUNDARY_V1` 证明 MSE0 request/data 向 Buffer0/1 接受次数为2/0、2/0，
  Buffer read为1/0，SA source accept为1/0，ALU→outbuffer为1。两个16B payload
  已组成首个32B Buffer0 row并成功完成第一次计算；随后没有第二次 Buffer read/SA accept。
- producer 与 SA consumer 都选择 Buffer0，selector 错位已排除。最窄停点变为
  `BUFFER0_FIRST_READ_TO_BUFFER0_NEXT_ROW_VALID_OR_READ`；仍不能唯一分辨
  WR_Buffer_AG 下一行未生成/入队、Buffer0 row-valid/full 阻断，或
  Array_Request_Manager address/lifetime 未推进。
- 因只缺上述一条内部边界，唯一窄诊断后继为
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v19_buffer0_flow_diag.zip`
  （bytes=5819648，
  SHA-256=`0420907934a5a603ea40a127128664affe0182b7d6bc986107e0b0b04303adf3`）。
  它只增加 `BUFFER0_FLOW_BOUNDARY_V1`，不修改配置、workload 或功能 RTL；v18 已消费，
  不再作为下一轮运行身份。

### GAP node0071

- 旧 v10 手工 run/evidence 双目录快照无相邻 sidecar、缺正式 return manifest/result gate
  和48项 D，保持 `RETURN_SNAPSHOT_NONAUTHORITATIVE`，不得升级 E3/E4/E5。
- 快照可消费的动态边界为：MSE0→Buffer0 与 MSE3→Buffer4 均已接受，随后长期
  `GA operand0/2 capture=0`，最窄区间为
  `BOTH_PRODUCER_TO_BUFFER_ACCEPTED→ANY_GA_INBUFFER_CAPTURE_ABSENT`；其后仿真时间
  冻结原因仍未确定。
- current-rule、canonical、observer 四向、dual-ingress 和真实 runner→safe compile
  stub 均复核通过，未发现包侧确定错误。唯一可运行身份保持
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v12_minruntime.zip`
  （bytes=1793432，
  SHA-256=`a1e149e7e4a20cd254e84a8fd7199607beeafb11fd71cfe4d548226825b06d06`）。

### QLinearAdd node0007

- v12 return 无相邻 sidecar和 `RETURN_MANIFEST.json`，且缺 observer/canonical 等4项
  required allowlist，因此是
  `RETURN_SNAPSHOT_NONAUTHORITATIVE_AND_PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE`；
  compile=0，人工 INT，约73.83分钟，无自然终止，formal D=0/28。
- 37条 `FIRST_REQUEST_CLOCK` 证明 EXEC_START 后 `clk_sg` 持续产生边沿，关闭
  “目标时钟未启动”候选；但 `FIRST_REQUEST_CHAIN` 为0，功能根因仍位于
  `slice_start_run→LC4→LC2/6→LC13/18→MSE0/MSE4→first request`。
- 确定包侧错误是 `FIRST_REQUEST_CLOCK` 在 heartbeat gate 外每个 `clk_db` 负边沿
  输出，造成无界日志并阻止正式 observer/canonical 回收。v12 已隔离。
- 唯一后继为
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_obsrate_v13.zip`
  （bytes=38031273，
  SHA-256=`fe65a96ad6365872f2f004f6702b197f33fc6b5fcd4397df716714f443b28858`）。
  它只把 `FIRST_REQUEST_CLOCK` 移入与主链相同的 heartbeat gate，不改十级握手链、
  workload/config/canonical/formal-D 合同。

当前三包均为 `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / PACKAGE_READY_NOT_RUN`，
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0，真实 runner 正控和全部要求负控通过。
同一服务器根不得并发；Group-B 中建议先运行 Conv v19，再运行 QAdd v13。GAP v12
只可在另一干净服务器根并行。每次只回传 runner 生成的正式 return ZIP 与直接相邻
sidecar，不手工压缩 run/install/evidence 目录。

## 0.0J 2026-07-31 服务器测试原则收敛：严格本地自检、最小服务器预检

用户明确服务器测试的目标是尽快进入真实 compile/run，定位配置语义或 RTL；不得因测试包
自身低级错误或无必要的服务器环境自检反复浪费轮次。主线已将公共服务器包规则调整为：

1. 最终 ZIP 交付前继续严格检查 sidecar/CRC/exact-set、manifest-bound payload、真实
   runner 正负启动链、SCA/SCA_D、runtime-D absent、observer 四向绑定、canonical
   decision、联合结果门和 return allowlist；
2. 本地可以发现的 observer 语法、硬编码 SHA、namespace、路径、入口、预置 D、runner
   提前退出必须在交付前关闭；
3. 服务器 runner 默认不枚举、哈希或要求既有 RTL/TB/Makefile/filelist/Git/README/
   observer/特定文件；只校验用户参数、fresh namespace、本包自身安装完整性、正式 D
   未预置和通用命令可调用，然后直接进入真实 compile/run；
4. package-local observer 的 expected identity 必须来自 final manifest 单一事实源，不得
   在 runner 里维护第二份硬编码 SHA；
5. 只有用户明确要求独立服务器源码身份审计，或明确授权事务式修改唯一服务器 TB 文件时，
   才检查该精确目标；可选源码审计不再成为普通算子包的运行前门。

新增/修订的主规则为
`CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001`、
`CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001` 和默认启用的
`CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001`。

Conv/GAP 后继已经一次吸收本规则，未重复 numeric/workload：

- Conv v15 formal return 在 package-local observer task 末端再次由 VCS 证明缺
  `endtask`；compile=2、simulation 未启动、formal D=0，v15 已隔离。唯一可运行后继为
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v16_abpe_runnerpc.zip`
  （bytes=5814860，
  SHA-256=`e0f6d1effba71e505d22203ec2a43b4a538aaeeb515b806f6953603a342bcec1`）。
  observer 语法最小 TB 通过，runner identity 来自 manifest；安全 compile stub 正控实际
  到达唯一 compile 调用点，错误 identity 负控在 compile 前 fail closed。
- GAP v10/v11 分别因旧规则收据和 runner 第二份硬编码 observer SHA 隔离。唯一可运行
  后继为
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v12_minruntime.zip`
  （bytes=1793432，
  SHA-256=`a1e149e7e4a20cd254e84a8fd7199607beeafb11fd71cfe4d548226825b06d06`）。
  runner 不再含 observer SHA 字面量，服务器端不检查既有源码文件。

两个最终 ZIP 均 `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0、全部负控 fail closed，
状态 `PACKAGE_READY_NOT_RUN`。当前仍以 Conv v16 优先；GAP v12 只在独立干净服务器根
并行。QAdd v10 已因 runner 在 manifest 外硬编码 install identity 且缺真实 runner
正控而隔离。其后提交的正式 v10 return 仍提供了可消费动态证据：compile=0，simulation
约69.96分钟后由 INT 中断；16个完整 stall window 内 qualified req/rdata/wdata 均为0，
formal D=0/28，因此是已证明卡死而不是仅未跑完。功能根因仍被限定在
`EXEC_START→first request`，不能猜测 shared-LC 或地址错误。

v10 的 FIRST_REQUEST_CHAIN 没有输出另有确定 observer 根因：qualified counter/打印绑定
门控 `clk_sg`，却用 `clk_db` 域的 `active_cycles % period == 0` 作为唯一发出门；门控
时钟未启动或跨域错过整点会令整段诊断静默。复用同一 observer 的 QAdd v11 因而也已撤销
运行资格。fresh 窄后继为
`artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_obsclk_v12.zip`
（SHA-256=`87c4089d56dbd082d825b2575285e9ec48276402c25bbe9e648f4165e4a461f3`）。
它保留 source-clock qualified counters，由持续存活的 `clk_db` 发出快照并回收
`clk_sg` edge/level；冻结 workload/config/canonical progress 语义不变。最终 ZIP 自检
`PASS=true`、errors=0，状态 `PACKAGE_READY_NOT_RUN`。若与 Conv 共用 Group-B 根，
QAdd v12 排在 Conv return 之后。

本次新增 `CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001`；同时允许对规则漂移做
内容中性复验：只有新规则不要求改变任何包内字节、runner 行为、manifest 合同、负控或
return schema 时，才可保留原 ZIP 并发布外部复验收据，避免无意义 fresh identity。

Conv v16、GAP v12 与 QAdd v12 均已针对 current server rule
SHA=`507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d`
完成 `RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS`，原 ZIP SHA/bytes 不变。Conv/GAP 的
正式 canonical 链使用自由运行的同域 `clk_db`，新门控域前提不命中；QAdd v12 已直接实现
source-domain qualified counters + `clk_db` snapshot，并通过异域 modulo 唯一 emitter
负控。三只包均保持 `PACKAGE_READY_NOT_RUN`，无需因本次规则增量重建。

## 0.0I 2026-07-31 Conv v14 return、ping-pong-off 裁决与 GAP v9 启动链修复

### Conv node0004

v14 formal return 的 ZIP/sidecar、CRC/exact-set/allowlist、source package、package/install
preflight 和 observer identity 均通过，但 VCS 在 package-local
`tb_probe/native_return_observer.svh:2405` 报 `token '['` 语法错误；compile=2、
run=125，simulation 未启动、formal D=0，E3/E4/E5 均为 false。该首分歧属于包内只读
observer，不是 Conv 配置、数值或功能 RTL 的动态反证。v14 已隔离。

最小修复将 observer 的 A/B monitor 拆分为 generate 实例，外层 group/slice 使用
unpacked 数组、内层 ROW/COL 保持 packed；冻结 JSON、mapping、bitstream、execplan、
SCA、输入和 golden 均未改变。唯一可运行 Conv 后继为
`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v15_abpe_syntax_fix.zip`
（bytes=5813960，
SHA-256=`65e5b50b00046d662d219b71054f7f3f64c5794c98bf87dc134b5b3dd09a2130`）。
最终 ZIP current-rule 自检 `PASS=true`、errors=0、全部负控 fail closed，状态
`PACKAGE_READY_NOT_RUN`。

用户提出的“生产端与 SA 消费端双方都关闭 ping-pong”在架构上可另行设计，但不等价于
当前 node0004，且不能作为两 leaf 修改继续：

- 第一个 accepted source0 terminal（`last=1,last_index=4`）在 matched-on 路线中用于
  切换 source1，并屏蔽 logical last；双方关闭会立刻传播 terminal 并停留 source0；
- 若全部 ingress 关闭，B 路仍有 stream1→buffer2、stream2→buffer3 两个固定 producer，
  关闭 SA inport1 ping-pong 会遗留 buffer3/B'；
- 若未来改为单 buffer0 串行 refill/clear/reuse，必须 fresh 重建 occurrence、GROUP0
  terminal、buffer reuse、A/B/C tag 对齐、地址/lifetime/terminal 和完整 local E2。

因此当前不采用默认关闭方案，也不替换 v15 的 matched producer/consumer 路线。

### GAP node0071

用户截图证明 v9 在 package preflight 输出 `valid=true` 后立即返回 shell。根因是 runner
的 package-local observer guard 写死 expected SHA=`47f0d667...09f49`，而最终 ZIP 内
observer 实际 SHA=`0a1621d2...eccc8`；guard 输出被重定向到 evidence，随后显式
`exit 7`，所以 compile/simulation 从未开始。v9 已隔离。

fresh 后继为
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v10_runner_guard.zip`
（bytes=1792702，
SHA-256=`1293d2f3868974edefad562bc28d9128a23bf3ff609df096bd68c11fd6a3a2b8`）。
安全 full-run mock 正控证明 package/installed preflight 与 observer guard 均通过并实际
到达 compile stub；错误 identity 负控在 compile 前 fail closed。最终 ZIP 自检
`PASS=true`、errors=0，状态 `PACKAGE_READY_NOT_RUN`。

本次已把 `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001` 写入公共
服务器包规则：今后最终 ZIP 必须用真实 runner + 安全 compile stub 正向证明
preflight→install→全部 guard→compile 调用点可达；静态脚本/manifest 检查不能替代。

当前运行顺序继续 Conv 优先：先运行 Conv v15；GAP v10 仅可在独立干净服务器根并行；
QAdd v10 若与 Conv 共用 Group-B 根，则等待 Conv return 后运行。所有 return 必须同时
提交 ZIP 与直接相邻 `.zip.sha256`，仍由原算子族会话正式分析。

## 0.0H 2026-07-31 Conv/GAP 正式回传与 QAdd 本地定位后继

在上传或运行本节三只后继包前，用户新增一次强制本地复核门。各原算子族已经再次
完整核对：

1. current 生成前索引、公共算子配置规则、NDP 硬件字段语义、本族专项规则和对应
   动态/服务器规则；
2. 冻结最终 JSON、mapping、execplan、SCA/SCA_D 中卡死相关字段的 owner、编码和
   实际物理编号；
3. 活动 RTL 从 `Start_Comp` 或最后 qualified 正证据到第一坏边界的 ready/valid、
   tag/match、queue full/empty、buffer capture、ALU/GA/SA accept/result 与 terminal；
4. 必要的最小定向 RTL/TB 或静态可达性反例。

本轮没有重复 W3/qparam/golden/全算子数值分析。QAdd v10 与 GAP v9 均回传
`LOCAL_EXHAUSTIVE_REAUDIT_NO_DETERMINISTIC_ERROR_FOUND` 并恢复原字节身份的运行资格；
Conv v13 则发现确定配置错误，已隔离并生成 fresh v14。

用户提交的 Conv node0004 v12 与 GAP node0071 v7 正式 return 已分别由原算子族会话
完成分析；QLinearAdd node0007 也已按授权完成本地穷尽定位和必要的窄诊断包生成。
三条线都未重复冻结数值分析、未修改功能 RTL，也没有把 `all missing + mismatch=0`
写成通过。

### Conv node0004

v12 return 的 ZIP/sidecar/source、CRC/exact-set/allowlist、package/install/observer
preflight 全部通过；compile=0、run=0。observer 在 1,310,720 active cycles 的有界
stall 门主动停止：第一个窗口 qualified 进度为 144，随后四个窗口完全不增长；
formal D 全缺，E3/E4/E5=false。

最后正证据为 A/B/C request/read-data 和一个 Buffer4 read-edge witness；第一坏边界
位于首个 Buffer5 write/SA group result 之前。强制本地复核发现此前“单侧 ping-pong
错配已排除”的结论引用了错误的历史 artifact root，必须撤回。v13 实际冻结配置中：

```text
stream_engine.stream0.ping_pong=0
stream_engine.stream0.pingpong_last_index=null
special_array.inport0.pingpong_en=1
special_array.inport0.pingpong_last_index=4
```

因此 MSE0 永远只写 Buffer0，而 SA A 消费者在第一次 tag4 边界后切到从未写入的
Buffer1；A 不再到达 PE，B 保持等待，Buffer0 随后填满并反压内存。两个 focused RTL
TB 已证明只要 A 真正到达，B 等待后仍能完成 ALU accept，且 Buffer0/2 地址/clear/
finish 序列可达；所以根因是生产者/消费者 ping-pong 合同不一致，不是 PE 匹配逻辑、
Buffer 地址机或功能 RTL 缺陷。

原 observer-only 后继
`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v13_abpe_boundary.zip`
（SHA-256=`a9e941dbb108f3672d05005ce04e02314dbfb87b410626a0233f1e07c830e5c9`）。
现固定为 `QUARANTINED_DETERMINISTIC_CONFIGURATION_ERROR`，禁止运行。

最小修复只改变两个 owner 明确的 leaf：`stream0.ping_pong: 0→1` 与
`stream0.pingpong_last_index: null→4`，使 MSE0 producer 与 SA inport0 consumer
严格一致。已从 fresh root 重建 C0 JSON→mapping→bitstream→execplan/SCA；84 个冻结
A/B/C 矩阵和 golden 不重算。唯一可运行后继为
`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v14_a_pingpong_fix.zip`
（SHA-256=`4bf890b5ad57d8952226125de4979e96e0c00a1d347d2fb59aec7cabb1cf44b2`）。
最终 ZIP current-rule 自检 `PASS=true`、errors=0、全部负控 fail closed，状态
`PACKAGE_READY_NOT_RUN`。

### GAP node0071

v7 return 的完整身份、25 preload、SCA/SCA_D、observer 四向绑定均通过；
compile=0，人工 INT 前 simulation wall 为 14,176.19 秒。128,188,416 个 flat
active cycles、122.25 个完整 stall window 内没有后续 qualified 进度；48/48 formal D
全缺，E3/E4/E5=false。

最后正证据为 MSE4 D write-address request、MSE0→Buffer0 acceptance 与 consume；
8 个 regular GA PE 的 joint input accept 始终为 0。现有证据缺 MSE3→Buffer4 与逐
operand capture/tag，因此精确根因仍未闭合，区间固定为
`MSE0_TO_BUFFER0_ACCEPTED + READ_STREAM3_PATH_UNOBSERVED
→ GA_DUAL_OPERAND_ACCEPT_ABSENT`。

唯一后继为 observer-only
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v8_dual_ingress.zip`
（SHA-256=`cb1b43b3e8228951a2c62e8de02b36f17291a2561048cb1b36c0a9ed876b5a0f`）。
它冻结 v7 数值树，只补两路 producer、operand0/2 capture 和 joint accept；
生成时 `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0。主线随后依据本次动态证据
发布 `CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001`，触发 post-generation
current-rule drift；因此 v8 当前状态改为
`QUARANTINED_POST_GENERATION_RULE_DRIFT`，不得上传或运行。

原 GAP 会话已完成 current-rule refresh。唯一可运行身份改为
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v9_ingress_rule.zip`
（SHA-256=`d37f40e768001d3588cd22f25040ba4e229ffc138221a42b13d7e446436e644c`）。
v9 仅更新 identity、SCA namespace、manifest/README/runner rule receipt；73 个 numeric
文件和 120 个非收据 payload 文件逐字节不变，observer 也保持同一 SHA。
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0，新规则及全部既有负控均 fail closed，
状态 `PACKAGE_READY_NOT_RUN`。

强制本地复核进一步逐项核对 MSE0/MSE3/MSE4、Buffer0/4/5、GA operand0/2、
opcode14 joint accept、lifetime-minus-one、write terminal 与 barrier，并以两个最小
RTL TB 证明 MSE3→Buffer4→GA operand2 路由和 A/1/C 联合接收可达；未发现确定配置或
RTL 语义错误。裁决为 `LOCAL_EXHAUSTIVE_REAUDIT_NO_DETERMINISTIC_ERROR_FOUND`，
v9 字节不变并恢复运行资格。

### QLinearAdd node0007

本地审计确认旧 v6 observer 把全局 `sem2iga_exec_start` 当作 actual
`slice_start_run`，并且固定探测的 LC 编号没有覆盖最终物理映射
LC2/LC4/LC6/LC13/LC18。空 MSE queue 可以接收初始 selected-index work，
所以本地仍不能在 actual start、LC 链和 MSE 链之间唯一选出配置修复 leaf；精确根因
保持
`UNRESOLVED_AFTER_EXHAUSTIVE_LOCAL_AUDIT_WITHIN_OP_A_DEQUANT_START_COMP_TO_FIRST_MSE_REQUEST`。

唯一后继为 observer-only
`artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_first_request_chain_v10.zip`
（SHA-256=`573121def027a04b33650122e82d6c32cb8fbc4c9162cfc6cc831237a01869cf`）。
它不改冻结 workload/config/timeout/ready/backpressure，只补 actual slice-start rising
edge、LC2/4/6/13/18 与 MSE0/MSE4 qualified 链；
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0、18/18 负控 fail closed，状态
`PACKAGE_READY_NOT_RUN`。v6/v7/v8/v9 均保持隔离。

强制本地复核进一步证明 Start_Comp→SEM CMPT→`slice_start_run`、物理
LC4→LC2/6→LC13/18、MSE0/MSE4 packed ports/keep/last_index、初始 AG/FIFO、
buffer/GA bank mask 与 final-write terminal 均静态可达；新增语义审计和原 v10 自检
共 8/8 通过。裁决为 `LOCAL_EXHAUSTIVE_REAUDIT_NO_DETERMINISTIC_ERROR_FOUND`，
v10 字节不变并恢复运行资格。

当前建议运行顺序仍以 Conv 优先：先 Conv v14；QAdd v10 与 Conv 同属原 Group-B
服务器根时不得并发，待 Conv return 后再运行 QAdd v10。GAP v9 可在独立干净服务器根
并行；若没有独立根，则仍排在 Conv 之后。每次必须同时交回 return ZIP 与直接相邻
`.zip.sha256`，仍由原算子族会话分析。

## 0.0G 2026-07-30 QLinearAdd v6 动态卡死裁决与运行队列修正

QLinearAdd node0007 的正式 v6 return 已由原算子族会话完成分析。return ZIP 与相邻
sidecar、source v6 ZIP、CRC、exact-set、allowlist、package/install preflight 均通过；
compile=0，simulation 实际启动后由外部 INT 中断。正式 D 为 0/28，全部 missing 时
`mismatch=0` 不可评价，E3/E4/E5 均为 false。

这次回传已经排除“只是没有跑完”：

- observer 四向绑定、time-0 marker 与实际 compile/runtime argv 均闭合；
- 88.78 分钟 simulation wall time 内得到 90 个 heartbeat；
- 连续 23,330,816 active cycles，即 22 个完整 stall window；
- qualified `req/rdata/wdata` 始终为 0，`COMP_FINISH=0`，地址入队、GA input/output、
  buffer activity 也均为 0；
- 因此动态裁决固定为
  `LONG_RUNNING_HANG_AT_OP_A_DEQUANT_START_COMP_TO_FIRST_MSE_REQUEST`，延长 timeout
  不能作为修复。

当前最后正证据是 `op_a_dequant EXEC_START` 已接受；第一坏边界是其后始终没有首个
DRAM LC address enqueue/MSE request handshake。精确根因仍为
`UNRESOLVED_WITHIN_OP_A_DEQUANT_START_COMP_TO_FIRST_MSE_REQUEST`。冻结配置中 read/write
分支确实共用 LC0，RTL 也有 AND-backpressure，但空 MSE index/request queue 可以先接收
初始索引，因此不得仅凭共享 LC 拓扑宣称组合环已经证明。下一步若继续 QAdd，只允许生成
带 active LC enable/output handshake、selected MSE index input/match/full/request-ready
qualified 观测的窄定位包；在精确首阻塞点闭合前禁止地址-only、LC-only 猜测修包。

包状态同步修正：

- v6 保持隔离：缺 canonical/final self-audit，且已实证动态卡死；
- v7 保持隔离；
- v8 `r5_qadd_n7_progress_canon_v8.zip` 虽通过包侧 canonical/self-audit，但复用了同一
  冻结 workload，现改为
  `QUARANTINED_NOT_RUN_SAME_FROZEN_WORKLOAD_HAS_PROVEN_DYNAMIC_HANG`；
- 当前 QLinearAdd 没有可上传或运行的测试包。

当前服务器运行队列只保留通过最终 ZIP current-rule 自检且未被动态反证的
Conv node0004 v12 与 GAP node0071 v7；QLinearAdd 从队列撤下。

用户现已授权 QLinearAdd 继续按以下顺序执行：

1. 先在本地沿活动最终 JSON、execplan/SCA 与 RTL 消费者穷尽
   `op_a_dequant Start_Comp → active LC output → selected MSE index input/match/queue
   → first request` 的 ready/valid/enable 链，并用最小定向仿真或静态反例确定第一阻塞点；
2. 若本地确定根因，只允许实施与根因一一对应的最小配置修复；随后从空 mapping state
   重建并重新证明 occurrence/address/coverage/barrier/lifetime、config-bound golden
   和全部既有 QAdd 数值合同；
3. 若本地穷尽后仍不能确定根因，才允许生成唯一窄定位包。定位包不得猜测修改
   workload/config 数值语义，必须默认携带 LC/MSE qualified 内部观测、host/sim time、
   stall window、signal trap、canonical partial decision 与正式 return allowlist；
4. 任何新包形成后，必须完整复读 current 索引、服务器包规则与 QAdd 专项规则，并以
   最终 ZIP/sidecar 独立自检；只有
   `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0、全部负控 fail closed 才能报告
   `PACKAGE_READY_NOT_RUN`。

机器报告：
`artifacts/operator_config_validation/r5-qlinearadd-node0007-progress-bind-v6-return-analysis/report.json`
（SHA-256=`9252437ccfc3d4dfb62a3cddf5e9a9a378441637f1c808508beb8b4b7d230bca`）。
任务记录：
`.agents/task_records/20260730_qlinearadd_node0007_progress_bind_v6_return_analysis.md`
（SHA-256=`8b42afeb095dcd2377d271e78d82844af7ac1b730a7de13df08fcf69bff43980`）。

## 0.0F 2026-07-30 最终 ZIP 规则复读与自检当前门

公共规则 `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001` 已发布并通知全部当前责任会话。
任何包完成生成后，必须重新完整读取 current 索引、公共服务器包规则和本族专项规则，
直接对最终 ZIP/sidecar 执行独立自检；只有
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true` 才能报告 `PACKAGE_READY_NOT_RUN`。规则漂移时
旧自检失效；若需修改包内容，旧包隔离并用 fresh identity 重建，禁止包外追写 receipt。

首次执行已经命中三个真实缺口：

- Conv v10：包内 Python runtime 在导入同包 helper 前未设置
  `sys.dont_write_bytecode=True`；shell 环境变量不能单独满足 bootstrap immutability。
  v10 隔离，唯一 v11 只修 bootstrap/self-audit 入口与元数据；
- QLinearAdd v6 缺 canonical decision，v7 又因生成后 active-rule 漂移，均已隔离。
  fresh v8 的 canonical/four-way/负控、bootstrap preflight 虽全部通过，但后续 v6
  正式动态回传证明其复用的冻结 workload 在首个 `op_a_dequant Start_Comp` 后进入
  零请求卡死；因此 v8 已撤销运行资格并隔离；
- GAP v6 canonical 的最终 manifest 仍绑定前一版规则 SHA，且缺
  `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001` 收据，已隔离。fresh v7
  `r5_n71_gap_v7_finalaudit.zip` 只更新 identity/SCA namespace/manifest/README rule
  receipts，73 个冻结 workload 文件逐字节相等；最终 ZIP current-rule 自检
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`、errors=0、全部 canonical/four-way/bootstrap/
  path/return 负控 fail closed，现为 `PACKAGE_READY_NOT_RUN`。

当前可运行的未运行诊断包为 GAP v7 与 Conv v12；QLinearAdd 当前无可运行包。
冻结数值 workload、golden、config、observer 算法与功能 RTL 均不因本门重做。

## 0.0E 2026-07-30 Conv v7 有效动态卡死边界与 observer 裁决修复

Conv v7 return 的内部身份、compile/runtime observer 绑定与动态日志可消费；相邻
sidecar 缺失仅使 formal receipt 独立 fail-closed。真实执行为 compile=0、run=0，
observer 在 time 0 启用，并在 8,388,608 active-cycle 预算处主动停止；无 natural
terminal、COMP_FINISH=0、formal D=0，因此 E3/E4/E5 均为 false。

有效 qualified 证据已经把卡死收窄为：

```text
LONG_RUNNING_HANG_AT_READ_DATA_ACCEPTED_TO_BUFFER5_WRITE_ABSENT
```

- 最后正证据：qualified read-data accepted，stream0=12、stream1=12、stream3=16；
- 第一坏边界：Buffer5 write witness 始终为 0，qualified D write-data 始终为 0，
  terminal 始终为 0；
- 后续 31 个窗口的真实 qualified I/O 增量均为 0，超过 4-window stall 门；
- 当前只能证明 `read-data accepted → Buffer5 write absent → D write-data absent`，
  尚不能把 Buffer4 read enable 改写为 SA input accepted，也未证明精确 SA 内部 RTL 子根因。

v7 observer 同时暴露两个确定诊断缺陷：把 Buffer4/5 持续高的 `buf_*_en` level 每周期
计为新进度，伪造每窗 delta=524288；runtime 又用最后一条 summary-only
`DIAG_DECISION` 覆盖前一条含 `reason/boundary` 的 canonical 裁决。v8 与 v7 使用相同
observer SHA，故 v7/v8 均隔离。

公共规则已新增 `CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`：monotonic
progress 只能消费 qualified event；机器裁决必须是含完整 reason/boundary/window/
counter snapshot 的唯一 canonical record，禁止 last-line-wins 和 summary 覆盖，并增加
持续高 level、summary append、冲突裁决、缺字段四类负控。

按用户最新要求，问题定位从“曾 timeout/预期长任务才启用”提升为所有新服务器测试包
的默认组成，规则 ID=`CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`。以后每个新包在
首次运行前就必须携带低开销 qualified progress、stage/terminal 边界、墙钟/sim time、
stall window、signal trap 与 canonical partial return；只有 manifest 给出明确短任务/
已有相同动态身份通过的豁免依据并经独立 validator 验证，才可关闭。

v9 虽已修 qualified progress，但 canonical decision 仍不合格：summary-only 继续复用
机器前缀，完整裁决缺 schema/version/window/digest，冲突双裁决与缺字段未固定返回
`PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS`。v9 状态为
`QUARANTINED_CANONICAL_DECISION_CONTRACT_DEFECT`，服务器处置固定为
`WITHDRAW_DO_NOT_UPLOAD_OR_RUN`。

唯一 successor 为
`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v10_hangloc_canonical.zip`，
SHA-256=`9dad438724489b56d4a2546631f4de8a8ee6fc76f2133072a3868a33ba10f0c4`。
v10 使用唯一 `CANONICAL_DIAG_DECISION_V1`，summary 改用 `DIAG_SUMMARY`，完整记录
schema/version/decision/reason/boundary/window、qualified counter snapshot/delta 与可重算
digest；持续高 level、summary append、冲突裁决、缺 reason、缺 boundary 五类负控和四向
绑定四负控全部 fail closed。冻结 c0 workload 不变，状态
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`。

## 0.0D 2026-07-30 长任务观察器四向绑定硬门

本轮两次互补失败已经证明，仅检查 observer 的单个组成部分不足以放行测试包：

- QLinearAdd node0007 v5 含 compile enable macro，但最终包未携带可解析的
  `native_return_observer.svh`/package-local `+incdir`，因此 compile=2、simulation 未启动；
- Conv node0004 v6 含 observer source 和 package-local `+incdir`，但最终 compile 参数缺
  `+define+NATIVE_RETURN_OBSERVER_ENABLE`；运行 102 分钟后 observer 仍从未实例化，
  不能区分持续前进与停滞，诊断包本身判定失败。

公共服务器包规则已新增 `CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`。任何依赖
package-local observer 的候选，必须由独立 validator 直接解析最终 ZIP，同时闭合：

1. observer source 唯一路径、大小、SHA 与 fresh-extract 可读性；
2. 指向该目录且不越出 package root 的 `+incdir`；
3. 选择 TB optional observer 分支的 compile-time enable macro；
4. runtime enable、time-0 receipt、actual argv、progress log、signal-trap/allowlist 回收。

release 测试还必须分别删除 source、`+incdir`、enable macro、runtime/return binding，
证明四个负控都会 fail closed。缺一固定为 `PACKAGE_OBSERVER_BINDING_INCOMPLETE`，禁止
发布、上传或运行，不得再等到服务器 compile/timeout 才发现。

当前状态：

- Conv v6-v9 已因 observer/qualified/canonical 缺陷隔离；v10 又被最终规则复读命中
  Python bootstrap 缺 `sys.dont_write_bytecode=True`，已隔离；fresh v11 自检中；
- QAdd 旧 progress/canonical successor 被最终 manifest current-rule self-audit 门隔离，
  fresh successor 自检中；
- GAP v4-v6 已隔离；唯一
  `r5_n71_gap_v7_finalaudit.zip` 已通过最终 ZIP current-rule self-audit。

## 0.0C 2026-07-30 node0004/QLinearAdd 最新动态首分歧与下一包

用户提交的 Conv node0004 v3 与 QLinearAdd node0007 v2 最新 return 已分别交回原算子
会话分析。两份 return 的直接相邻 `.zip.sha256` sidecar 均缺失，因此正式 receipt
fail-closed；但 ZIP 内 exact-set/allowlist、package/install preflight 与源包身份均通过，
可用于定位本次执行首分歧。两项均未重复数值分析或重建冻结 workload。

Conv node0004 v4 return 已确认此前路径修复真实生效：

- return ZIP 与直接相邻 sidecar 身份、CRC、exact-set、allowlist、package/install
  preflight 全部通过；
- `compile_exit=0`、86/86 matrix transfer 成功，SCA/SCA_D 均从 v4 root 解析，
  `Reg Started.` 与 `INFO: slice start` 已出现；旧 846 个 stale path leaf blocker 关闭；
- runner 在 12 小时外部 timeout 后返回 124，无 natural terminal，formal D=0/320；
  全 missing 时 `mismatch=0` 不可评价；
- v4 observer 虽编译并通过 198 项静态 XMR guard，但 simv argv 未传
  `+RETURN_OBSERVER`，collector 也未回收 observer 日志，因此 slice-start 后的内部
  handshake 观测缺失。按 2026-07-30 用户新门，本次执行默认登记为
  `LONG_RUNNING_HANG_PENDING_ROOT_CAUSE`，不得仅以“observer 未启用”结束裁决；
- 原 Conv/SA 裁决已按同一 v4 return 完成重审：27 runs/54 份 SCA/SCA_D、240 条 LC、
  c0 occurrence/address/coverage/lifetime、terminal/last、静态 ready 图与活动 RTL
  均已穷尽；未发现可静态证明的不可达条件。最窄区间为首个 c0 slice start 后、任何
  natural terminal 或 formal D 之前，结论为
  `UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT`，不把责任无证据归给 RTL 或配置；
- 已生成的
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v5_observe.zip`，
  SHA-256=`fb7a36e380c1329c29faf9170a0e117715bdc0d0198bc0568e47298d517844cb`，
  改为 `QUARANTINED_PENDING_HANG_REVIEW`，禁止上传或运行。v5 仅启用并限流
  package-local observer、回收 observer 日志，并按新 identity 重绑 SCA root；
  矩阵、bitstream、execplan、golden、observer source 与 RTL 均不变，因此不是功能修复。
- 现有证据穷尽后已生成唯一 c0-only 有界诊断包
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v6_hangloc.zip`，
  SHA-256=`2a0ecf7e0218a2a65d37d281ef46343f66e20ca4359cfacf062bf88f89dd1021`，
  状态 `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`。每 262144 sim cycles
  记录限定事务计数，连续 4 窗无进展即在 8 类边界中锁定停点；若计数持续增长到预算
  结束，则明确返回 `C0_STILL_PROGRESSING_NOT_FINISHED_AT_BUDGET`。signal trap 同时
  回收 host 墙钟、simulation time、stage/Start_Comp 与最后边界。

QLinearAdd node0007 同样已越过旧 observer/include 编译阻断：

- `compile_exit=0`、85/85 preload 完成、execplan 启动并观察到 slice start；
- v2 的 12 小时 simulation watchdog 返回 124，未自然结束，D=0/28；全 missing 时
  `mismatch=0` 不可评价，不能解释为数值通过；
- 已由最终 JSON 与活动计数器 RTL 确证首个 hang：stage0 `op_a_dequant` 的
  LC1/LC3 为 `start=0,stride=1,end=37632`，但 DRAM LC 对外 feedback 只有 16 bit
  且下一轮按 signed 值解释；计数达到 32768 后反馈成为 -32768，永远无法到达
  terminal threshold 37631。因此 LC last、write terminal 与
  `slice_cmpt_finish` 均不可达；
- 全 workload 共 7 个同类非法 LC：stage0 LC1/LC3、stage1 LC1/LC3、
  stage3 LC1/LC2/LC3。首分歧正式改为
  `QADD_DRAM_LC_SIGNED_FEEDBACK_WRAP_HANG`；
- 旧 `B_QADD_NODE0007_POST_SLICE_START_NO_PROGRESS_ROOT_CAUSE_UNRESOLVED` 已关闭，
  新 blocker 为 `B_QADD_NODE0007_DRAM_LC_SIGNED_FEEDBACK_WRAP`；
- `r5_qadd_n7_relocated_v3.zip` 仅延长 watchdog、没有功能修复，现状态为
  `QUARANTINED_NOT_RUN_NO_FUNCTIONAL_FIX`，禁止上传或运行；
- fresh v4 已完成联合修正：dequant 采用 `4×9408`，FP32 add 采用 `8×18816`；
  所有正 stride LC 最大 end=18816，派生 outer stride 均可编码；
- 6/6 mapping 从空状态生成，37,352,448 requests、20,493,312 unique addresses、
  max row=6143、地址/coverage/terminal/barrier/lifetime 与冻结 golden 全部闭合，
  physical/logical/padding mismatch=0/0/0；
- 唯一新包为
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_nested_lc_v4.zip`，
  SHA-256=`dfe6ab0e11482d9af7954ba3e87911b770f8d80efa4148352b63d27bf7df2361`，
  状态 `PACKAGE_READY_NOT_RUN`。

GAP node0071 v2 截图首分歧也已闭合：runner 以 `make -C "$server_root"` 编译，但直接从
package caller cwd 执行绝对路径 `simv`，导致 TB 相对路径
`install/cfg_pkg/r5_n71_gap_v2_obs/sca_cfg.json` 从错误 cwd 解析。`Reg Started.` 与
monitor creation 出现在 Cannot open 之后，不构成数值执行证据。fresh runner-only 包为
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v3_cwd.zip`，
SHA-256=`3d6c8c580e178717b1c0a9bf70f5c55fd8cbcc8a74c7e9b5673f36b743604c80`，
状态 `PACKAGE_READY_NOT_RUN`；仅在 simv 子 shell 先 `cd "$server_root"`，冻结
payload/golden/config 数值语义不变。

当前无未运行的功能候选；已验证可运行的仅有 0.0D 所列三个有界诊断包。Conv node0004
v6 已由原 Conv/SA 会话确认是 observer compile-enable 缺失的诊断包失败；GAP node0071
v4 也确认相同 compile-enable 缺失。QAdd v5
return 分析已完成：sidecar/ZIP
身份通过，但 compile=2，VCS 因 `native_return_observer.svh` 无法解析而停止，simulation
未启动，D=0/28；这是 package observer source/include 绑定缺陷，不是 QAdd 功能根因。
GAP node0071 v3 正式 return 已完成分析：compile0、12h timeout、
D=0/48；25 preload、Reg Started 与首个 slice start 已证明，但 actual argv 未启用
observer，缺 accepted/completion、last/terminal、stall window 与 host timing。静态
execplan/SEM/finish 链未发现确定不可达反例，裁决为
`UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT`。QAdd v4 return 已完成分析：
compile0、人工中断、D=0/28；
从首个 slice start 后 simulation time 推进约 19.382 µs，但没有 accepted/completion
单调计数和 stall window，无法区分仍在前进与已停滞。静态审计排除旧 signed-feedback
wrap、u20 stride、包身份/preload/SCA/address/lifetime 回归，最窄区间为首个
`op_a_dequant Start_Comp` 到首个 `slice_cmpt_finish`。Conv node0004 v5 继续隔离。

QAdd v5 诊断包为
`artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_nested_lc_progress_v5.zip`，
SHA-256=`f184410ced99830d4737bea58ccd0590e87ae0525c77d95265b0ef756a184a8e`，
现状态 `ADJUDICATED_COMPILE_FAILURE`，禁止重跑。其冻结 v4 workload/JSON/mapping/
bitstream/execplan/SCA/golden 不变，不延长 12h timeout；实际 compile/runtime 启用
observer 的目标未实现，因为 package 未绑定 include source。

QAdd v5 已隔离；其已验证 successor 诊断包为
`artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_nested_lc_progress_bind_v6.zip`，
SHA-256=`9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90`，
状态 `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`。独立 validator 已直接解析
最终 ZIP，闭合 source、`+incdir`、compile enable、runtime/return 四向绑定；删除
source、`+incdir`、enable macro、runtime/return binding 的四个负控全部 fail closed。
workload 与 timeout 不变。

GAP v4-v6 已因 compile-enable、canonical 与 current-rule self-audit 缺口依次隔离。唯一
successor 诊断包为
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v7_finalaudit.zip`，
SHA-256=`6ae39b218e622f9937753dd4d4d649b1d2a7420c49ec5ed71d00fe8c26abd068`，
状态 `PACKAGE_READY_NOT_RUN`。73 个冻结 workload 文件不变；最终 ZIP current-rule
self-audit pass、errors=0，canonical/four-way/bootstrap/path/return 全部必需负控 fail closed。
E3/E4/E5 与正式三方计数不变。回传必须同时交付 ZIP 与直接相邻
`.zip.sha256` sidecar，并交回原算子会话分析。主线不重复解析 raw return。

2026-07-30 起，曾 timeout/人工中断或预期长时间运行的后续包必须默认带低开销进度
定位：同时记录墙钟、simulation time、stage/Start_Comp、真实 accepted/completion
单调计数与最后 terminal/last 边界，并在 signal trap 的部分 return 中回收。人工中断
可能只是尚未跑完，因此分析必须用声明的 `stall_window` 区分“仍持续前进”和“长时间
无进展卡死”；没有这类证据的包不得作为下一轮长任务候选。

记录：

- `.agents/task_records/20260730_conv_node0004_v3_return2_path_root_and_v4_package.md`
- `.agents/task_records/20260730_conv_node0004_v4_timeout_and_v5_observer_package.md`
- `.agents/task_records/20260730_conv_node0004_v4_hang_rootcause_reaudit.md`
- `.agents/task_records/20260730_qlinearadd_node0007_v3_no_fix_lc_signed_wrap_rootcause.md`
- `.agents/task_records/20260730_qlinearadd_node0007_nested_lc_v4_return_analysis.md`
- `.agents/task_records/20260730_qlinearadd_node0007_progress_v5_return_analysis.md`
- `.agents/task_records/20260730_qlinearadd_node0007_v6_four_way_binding_validation.md`
- `.agents/task_records/20260730_conv_node0004_v6_hangloc_return_analysis.md`
- `.agents/task_records/20260730_conv_node0004_v7_four_way_binding_review.md`
- `.agents/task_records/20260730_conv_node0004_v7_hangloc_return_analysis.md`
- `.agents/task_records/20260730_conv_node0004_v9_canonical_rule_receipt.md`
- `.agents/task_records/20260730_gap_node0071_v2_screenshot_sca_path_failure_v3_cwd_package.md`
- `.agents/task_records/20260730_gap_node0071_v3_timeout_v4_hangloc.md`
- `.agents/task_records/20260730_gap_node0071_v4_hangloc_return_analysis.md`
- `.agents/task_records/20260730_gap_node0071_v5_canonical_receipt_and_v6_successor.md`
- `.agents/task_records/20260730_gap_node0071_v7_final_zip_rule_self_audit.md`
- `.agents/task_records/20260730_server_observer_four_way_binding_rule_publication.md`

## 0.0B 2026-07-29 GitHub master b7acbe5 同步与 QLinearAdd 当前首分歧

已按用户要求从私有仓库 `xlsjdjdk/Trassic2.0_RTL` 取得最新
`master=b7acbe55340ca7e98ead70335156f555929c0777`，并将
`code/NDP_rtl` 同步到活动 `NDP_copy01/rtl`。同步前活动目录完整保存在
`NDP_copy01/rtl_pre_github_b7acbe5_20260729`；新快照源与活动目录均为
2242 个文件，逐路径 SHA 差异为 0，树 SHA-256 均为
`62cc16b630046e7a1ed09351de8065e37764e2afb4c881f44d2f84e57c55bdc7`。
机器收据见
`contracts/rtl_sync/trassic2_master_b7acbe5_local_sync_v1.json`。

本次同步没有消除已知 global compile blocker：最新 GitHub
`SA_PE_Float_Control.v:50-51` 仍为最后一个 ANSI port
`o_Config,` 后直接闭合 `);`；focused Icarus 在同步后的活动源码上仍报
`Superfluous comma in port declaration list`。在硬件组提交真正删除该
尾逗号的源码并完成 full VCS compile/elaboration 前，不把
`b7acbe5` 记为 compile release。

QLinearAdd node0007 v2 新 return 已交给原算子会话分析。正式收据因相邻
`.sha256` sidecar 缺失 fail-closed；执行首分歧则是服务器
`tb_NDP_Top_new_phy.sv:5854` 无条件 include
`native_return_observer.svh`，而编译环境没有该 include 文件，
因此 compile=2、simulation 未启动、readback=0/28。该问题位于服务器
TB/include 环境，不是 QAdd 数值或包内 workload；现有 v2 包不重建。
服务器 owner 应使 observer include 在活动 filelist 中可解析，或取消
对不携带 observer 的包的无条件 include，然后用原包、fresh namespace
重跑并一并交回匹配 sidecar。

独立审计已完成：

1. `b7acbe5` 与 `1c49bd1` 的全部共同活动 RTL 路径内容差异为 0；
   少掉的 16 项仅是 15 个 AXI 仿真归档 `.so` 和一份旧日志。因此提交
   说明不能替代 source-current-match 修复证据；
2. 原样源码首个确定 blocker 仍是 `SA_PE_Float_Control.v:50` 尾逗号；
   只在隔离诊断副本删掉该字符后，`SA_ALU → SA_PE_ALU → SA_PE →
   SA_PE_Group` 全部通过，未发现第二个确定的 SA module/port/width
   编译 blocker；
3. `slice_rst` caller/callee 在当前源码已闭合；
4. `SA_PE_Float_CSA.v:49-50` 的 negative-psum 全域边界错误仍存在，
   但本轮不声称 ResNet W3 命中；`GA_PE_Inbuffer.sv:527-557` 的
   INT8 pipeline0 ready 缺口仍存在并直接影响 MaxPool；
5. QAdd 的 `native_return_observer.svh` 缺失属于服务器 TB/include
   环境，文件和引用均不在 `b7acbe5` RTL 树中。

审计报告：
`.agents/task_records/20260729_conv_sa_b7acbe5_latest_source_compile_audit.md`。
当前执行顺序是：硬件组先把尾逗号修复真正提交到 `code/NDP_rtl` 并完成
full VCS compile/elaboration；服务器运行环境同时补齐或取消无条件
observer include；随后使用原 QAdd v2 包、fresh namespace 重跑并交回
匹配 sidecar。主线只维护同步身份、总账和硬件组清单，不重复算子数值分析。

2026-07-29 TB 授权与因果修正：用户明确允许修改服务器 `rtl/` 外的 TB
和支持文件。只读历史核验确认，`tb_NDP_Top_new_phy.sv:5854` 的无条件
`native_return_observer.svh` include 是本项目在 2026-07-23 为 GAP/通用
return 定位有意加入的观测器接口；0718 服务器快照不含该行，项目历史记录明确
写有“本地 TB 只新增一条 include”。QAdd v2 后续按 TB/observer entries=0
封装，未携带 observer 或 include path，而服务器仍使用修改后的 TB，因而形成
本次 compile=2。该失败重新分类为
`PRIOR_PROJECT_TB_INSTRUMENTATION_CONTRACT_MISMATCH`，不是 QAdd 数值或硬件
RTL 问题。推荐把 TB include 改为
`NATIVE_RETURN_OBSERVER_ENABLE` 宏控制：普通包不定义宏；需要 observer 的包
事务式安装 package-local observer，并显式传 `+define`、`+incdir` 和恢复收据。
完整裁决见
`.agents/task_records/20260729_server_tb_observer_include_causality_adjudication.md`。
直接修补脚本为
`tools/patch_server_tb_optional_observer_include.py`：只操作用户传入
`NDP_copyXX` 根下的唯一 `tb_NDP_Top_new_phy.sv`，自动创建 preimage
备份、加入宏保护并输出 SHA 收据；不搜索或修改 `rtl/**`。

## 0.0A 2026-07-29 GitHub master 1c49bd1 RTL 审计与硬件组交接

用户要求在继续服务器测试前审查最新 GitHub RTL 是否仍含会造成编译、
仿真停滞或数值错误的问题。主线已绑定
`xlsjdjdk/Trassic2.0_RTL@1c49bd1155a89ff187e29016dc4415e59a55f991`，
只读审计快照为
`Trassic2.0_RTL_master_1c49bd1_audit/Trassic2.0_RTL-master/code/NDP_rtl`。
活动 `NDP_copy01/rtl` 与快照原件均未修改；诊断试修仅位于 `outputs/`。

当前裁决：

1. P0 公共编译阻断已确认：
   `code/NDP_rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v:50-51`
   的最后一个 ANSI port `o_Config` 后多余逗号。Conv node0004 与 GAP
   node0071 的新 return 均因此 `compile_exit=2`、simulation 未启动、
   正式 readback 分别为 `0/320` 与 `0/48`。包侧无合法修复；原包均无需
   重建。
2. P1 通用 INT8 MAC 全域算术缺陷已确认：
   `SA_PE_Float_CSA.v:49-50` 的负 psum 拆分重构在
   `C=-5,dot=+5` 与 `C=INT32_MIN,dot=0` 时错误。当前冻结 ResNet50
   数据尚未证明命中，因此不作为本次无法启动的原因，但已提交硬件组。
3. P1 MaxPool 动态 flow blocker 在最新快照仍 current-match：
   `GA_PE_Inbuffer.sv:527-557` 的 `alu_pipeline0_bp_post` 缺失 INT8
   分支；定向仿真复现首个 INT8 token 后
   `P0_BP_POST/P0_ENABLE/P0_CLEAR=0/0/0`，第二项后输入反压停止。
4. `SA_PE_Mul_Array.v:184-236` 的 reset/data-register 不对称仅记为
   local observability risk；尚未证明 X/旧值越过 valid/tag 成为
   accepted output，不升级为 ResNet blocker。
5. 只删 P0 逗号的隔离诊断副本已使
   `SA_ALU -> SA_PE_ALU -> SA_PE -> SA_PE_Group` compile/elaboration
   通过；最新 10 个 changed files 内未发现第二个确定的 module/port/
   width 编译阻断。由于本地无生产 VCS，完整 top 仍需硬件组实际
   compile/elaborate/start-only smoke。

硬件组交接报告：
`docs/trassic2_rtl_hardware_group_handoff_1c49bd1_20260729.md`；
机器合同：
`contracts/rtl_sync/trassic2_master_1c49bd1_remaining_blockers_v1.json`。

调度停止门：先由硬件组删除尾逗号并完成生产 VCS full-filelist
compile/elaboration。完成后原身份重跑 Conv node0004 v3 与 GAP
node0071 v2；MaxPool 在补齐 INT8 handshake 后重跑原 GitHub JSON
测试。所有正式 return 必须同时提供匹配 ZIP 的 `.sha256` sidecar。
在此之前不计 E4/E5，不把 missing=全部且 mismatch=0 解释为数值通过。

## 0.0 2026-07-29 服务器对齐 RTL 已覆盖并复现编译错误

按用户明确授权，活动 `NDP_copy01/rtl` 已由 GitHub/服务器对齐快照
`xlsjdjdk/Trassic2.0_RTL@5f2f8d3a2358c090143caa35957c07ff3650ff4c`
覆盖；原目录完整保存在
`NDP_copy01/rtl_pre_server_aligned_5f2f8d3a_20260729`，未删除。覆盖后 source 与活动目录
2257 个文件逐路径 SHA-256 差异为 0。

实际 Icarus elaboration 在活动 RTL 上稳定复现服务器 VCS 的同一首分歧：

```text
SA_ALU.v:124: port `slice_rst` is not a port of u_SA_PE_Mul_Array.
```

原因是 `SA_ALU.v:124-127` 仍向 `SA_PE_Mul_Array` 连接
`.slice_rst(slice_rst)`，而 commit `5f2f8d3a` 的 `SA_PE_Mul_Array.v:1-6`
已经删除该端口，并同时删除原有 slice-reset pipeline branch。该 revision 的
`last_B=carry_int[31:0]` 是需要保留的 carry 修复，不能通过整体回退文件解决。

主线当前停止门：

1. 硬件 owner 在同一 commit 中统一 caller/callee 的 `slice_rst` 接口和 reset 语义；
2. 优先恢复 callee 端口及所需 reset branch，同时保留 `last_B=carry_int[31:0]`；
3. 用活动 NDP filelist 完整 compile/elaborate；
4. 通过后原身份重跑 node0004 v3 与 GAP node0071 v2，不重建数值 workload；
5. 在此之前不生成新包，不把 compile 前失败计为数值失败。

详细记录：
`.agents/task_records/20260729_server_aligned_rtl_overwrite_and_compile_reproduction.md`。

2026-07-29 最新外部状态覆盖：用户已确认服务器侧上述 RTL 编译接口问题完成修复。
该确认解除“不得发起服务器重跑”的调度停止门，但尚不是动态通过证据；最终仍以新 return
中的 compile=0、simulation=0、natural terminal 和正式 readback 为准。本地
`NDP_copy01/rtl` 仍是修复前 GitHub commit `5f2f8d3a` 的可复现快照，在下一次明确
同步新 commit 前不得用其旧 compile failure 反向阻止服务器测试。现有包若不包含功能
RTL/旧接口 overlay，可保持原 ZIP/SHA 直接运行，不得仅因服务器 RTL 修复重建数值
workload。

### 0.0.1 Conv stem accumulate 本地 E2 已闭合

Conv/SA 分支已完成 `r5:hwop-0001-00` stem 的 fresh serialized accumulate
物化，机器合同
`contracts/operator_config/r5_conv_stem_serialized_local_e2_v1.json`
SHA-256=`5ae714695b732e062193e3a1cbca818bad3a825bb8da077a1ad363c9b3331e12`。
主线接受其 `CONFIG_ONLY_CORRECTNESS_BASELINE / LOCAL_E2_ACCUMULATE_COMPLETE`
边界，不重复数值分析：

- 真实 `7x7/stride2/pad3`、K147→K148；每 occurrence 至多一个非零 product lane；
- 完整 12,845,056 个 INT32 accumulate 输出与冻结 W3 mismatch=0；
- 1,901,068,288 serialized occurrences，代价为 4× occurrence、
  24.831081% lane utilization；
- 三个 fresh native waves 28/28/8，最终
  JSON→mapping→bitstream→execplan/SCA、地址覆盖和本地 config-bound W3 已闭合；
- 本轮只关闭 stem accumulate 的 handler、物理覆盖、W3 与 local E2 子门。

该结果不是完整 UINT8 Conv：stem accumulate D→Requant A 的同图 zero-copy
address/barrier/lifetime 尚未组合，E3/E4/E5 均为 false，也没有生成 stem 服务器包。
服务器对齐 RTL 的 `slice_rst` 编译接口错误仍是所有动态运行的共同停止门；本地 stem
E2 不改变 node0004 v3 的 `SERVER_RTL_INTERFACE_COMPILE_MISMATCH`，也不授权批量封包。
完整记录：
`.agents/task_records/20260729_conv_stem_serialized_local_e2_complete.md`。

### 0.0.2 QLinearAdd node0007 nested-LC v4 本地 E2 与测试包已就绪

QLinearAdd 分支已关闭 node0007 FP32 SUM `row=6144` 越界：在 FP32 ADD 前插入
不承载 QAdd 计算结果的硬件 relocation spacer，把完整 SUM_F32 搬移到新 bank。
17/17 stage0 数值分析未重复。主线已核验并接受：

- `E2_LOCAL_COMPLETE / CONFIG_ONLY_CORRECTNESS_BASELINE`；
- 6/6 bundles 从空 mapping state 重建，penalty=0、fallback=false；
- 37,352,448 requests，所有 row≤6143，issue_count=0；
- 最终逻辑、物理与 padding mismatch 均为 0；
- static→final 只有 allocator-owned base address 变化，non-base diff=0；
- runtime D 预置为 0，PASS 由 compile/run/terminal/loader/readback/missing/mismatch
  逻辑与控制。

v2 已真实 `compile=0` 并启动 slice，但首个 Start_Comp 的 LC1/LC3 使用
`start=0,stride=1,end=37632`。活动 DRAM LC 将计数截断为 16-bit feedback，并在
下一轮按 signed 值解释；32768 回绕为 -32768 后无法到达 terminal threshold 37631。
因此 v2/v3 的物理执行合同不具备动态可终止性。fresh v4 未照抄 `2×18816`：
该方案会产生 `18816×64=1204224` 的 write outer stride，超过 unsigned 20-bit
上限。最终采用 dequant `4×9408` 与 FP32 add `8×18816`，从空 mapping state
重建并完成 occurrence/address/order/coverage/terminal/barrier/lifetime、
mapping→bitstream→execplan/SCA 与冻结 golden 复验。v3 继续隔离；唯一候选为
`r5_qadd_n7_nested_lc_v4.zip`，SHA-256=
`dfe6ab0e11482d9af7954ba3e87911b770f8d80efa4148352b63d27bf7df2361`，
状态 `PACKAGE_READY_NOT_RUN`。

完整记录：
`.agents/task_records/20260730_qlinearadd_node0007_nested_lc_v4_package_ready.md`。

### 0.0.3 修复后服务器运行队列

用户已确认服务器 RTL 编译问题解决，并授权“包体无需更改则运行”。三条原算子会话均已
完成 receipt-only/package-boundary 复核，未重复数值分析：

- Conv node0004：v6-v9因observer/qualified/canonical缺陷隔离，v10又因bootstrap
  current-rule自检失败隔离；fresh v11 自检中；
- GAP node0071：v4-v6隔离；唯一 v7 finalaudit 已通过最终 ZIP current-rule自检；
- QLinearAdd node0007：旧 progress/canonical 包已隔离；fresh successor 自检中。

运行调度遵守每组最多一项：

1. 当前 Conv 未运行诊断包为 v10；QLinearAdd/GAP 正在按新 canonical 规则复核各自
   successor。每个服务器根
   同时只运行一个，回传必须同时提供 ZIP 与直接相邻 sidecar；
2. QLinearAdd 只允许 nested-LC v4，禁止运行 relocated v1/v2/v3；
3. 任一根的下一项必须等待当前包 restore/finalizer 与 return sidecar 完成。

主线没有服务器 shell/上传连接，因此这里的“运行授权”状态为
`RUN_AUTHORIZED_AWAITING_SERVER_COMMAND`，不能伪写为 `SERVER_RUNNING`。只有用户在
服务器实际启动命令后才登记对应 lease。两项运行候选都要求 fresh namespace；Conv v5
保持隔离。真实 return
必须交回对应原会话分析，主线不直接解析。

最后更新：2026-07-29（按用户硬件可用假设恢复正常 Conv 路径；node0004 fresh 完整单算子包已就绪）

本文件只记录仍能派生工作的状态、blocker、顺序和交接。版本过程、旧命令、包 SHA、历史服务器裁决和被取代的“当前状态”已迁入 `.agents/history/plan_pre_active_compaction_20260724.md`；完成工作的详细证据继续看 `.agents/task_records/`。

## 0. 2026-07-29 硬件可用假设与执行覆盖

用户明确要求：本地主线不再等待云端仓库清理、最终 RTL SHA 或硬件组对历史问题
2/5/6/7/8 的进一步解释；按服务器侧 RTL 已可编译、已修复 Conv 必需的 DataC/psum、
carry handoff 和 signed INT32→FP32 语义继续推进整网。该指示覆盖本计划后文仍保留的
C0 历史阻塞结论，执行优先级以本节为准。

执行边界如下：

- `HARDWARE_SEMANTICS_ASSUMED_AVAILABLE=true`：本地生成、config-bound 验证和测试包生成
  不再以云端当前源码冲突标记、云端 commit 清理或服务器 RTL identity 核验为前置门；
- 该假设只解除“停止生成”的控制面门，不把未运行包计为 E4/E5，不把服务器侧假设写成
  已验证动态证据；正式计数仍以真实回传、完整 readback 和 sidecar 为准；
- node0004 继续执行“旧本地资产全部不可信”的覆盖：历史 JSON、mapping、bitstream、
  execplan/SCA、package、simulator output 和测试收据均不得复用；
- node0004 的可信软件域审计已覆盖 3,211,264 个输出、51,380,224 个实际 dot4 group；
  在修复后的 carry 语义下 mismatch=0，因此首个 Conv 优先使用正常 four-lane SA，
  不再把 SA-product→GA-tree 复合路线作为默认路径；
- 对后续每个新 Conv schedule signature，在最终 lane packing 上执行实际 dot4 域检查。
  若命中 signed17/`cout` 反例，才切换为 one-product-lane + DataC psum 的配置绕行，并
  明确记录约 25% lane utilization、至少四倍 occurrence 的代价；
- signed INT32→FP32 视为已由硬件修复，node0004 exact UINT8 tail 不再走 raw
  `max(acc,0)`；默认采用 `INT32→FP32 MUL→FP32 scratch/barrier→独立 RNE/saturation`
  两阶段纯配置路线；
- MaxPool 继续复用 Git 原始 JSON，不修改、不因历史问题 5/6/7/8 预先阻塞整网；
  GAP 继续使用非 transout `int32_mac` sum tree。只有真实单算子或整网回传出现首分歧时，
  才回到相应 RTL/flow 路径诊断；
- 本地主线允许一直执行到 `PACKAGE_READY_NOT_RUN`。不检查服务器现有文件、服务器名称、
  Makefile/filelist/RTL identity，不上传、不运行；服务器运行仍由用户实际操作或另行授权。

当前恢复后的主顺序：

1. 完整复读生成前规则，fresh 物化 node0004 正常 four-lane INT32 accumulate；
2. 物化 node0004 两阶段精确 UINT8 tail，并完成完整 UINT8 节点 config-bound 比较；
3. 生成 node0004 单算子服务器测试包，状态止于 `PACKAGE_READY_NOT_RUN`；
4. node0004 通过后按 schedule signature 扩展 53 个 Conv；可复用的非 Conv 资产不复测；
5. 并行收敛 shared exact tail、QLinearAdd/GAP output、Flatten endpoint 和全局
   allocator/address/lifetime，随后一次性组装 133-stage 整网；
6. 首次整网比较只回查首分歧 owner，不提前重测已接受复用的算子。

截至 2026-07-29，本节第 1–3 项已经完成：

- node0004 已从 typed/ONNX/W3 与活动通用模板 fresh 生成，未消费任何历史 node0004
  JSON、mapping、bitstream、execplan/SCA、simulator output 或 package；
- accumulate 采用 3 个 normal four-lane SA wave；exact UINT8 tail 采用 24 个
  `MUL→FP32 scratch/barrier→独立 RNE/saturation` pair，共 51 份 mapping、
  3+24=27 份独立 execplan；
- 完整 W3 共 3,211,264 个输出、51,380,224 个 dot4 group，accumulate 与 tail
  mismatch 均为 0；实际 dot4 范围为 `[-25736,20597]`，magic-domain 有限；
- v1 服务器包已生成并运行，但真实回传确认 compile=2、simulation 未启动；v1 的
  320/320 来自包内预置 runtime D，已裁决为结果门 fail-open，不是动态 readback；
- v2 不预置 320 个 D target，并正确把 compile/run/terminal/readback 做逻辑与；
  正式 return 已确认 gate fail-closed，但编译停在服务器 TB 无条件 include 的
  `native_return_observer.svh` 缺失；
- 包侧已继续修复为
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v3_obs.zip`，
  SHA-256=`84c834de989c7912edfd711cd5fb2bdfe51e40998bb493d3e4ec5b99da9a331c`，
  v3 只新增 package-local observer、precompile SHA/XMR guard 和显式 `+incdir`，
  冻结 v2 的 823 个 workload/validation payload；
- v3 正式 return 已证明 observer 身份、XMR、include 与 runtime-D-absent 门通过，
  但 compile=2、simulation 未启动、formal readback=0/320。首分歧为服务器
  `SA_ALU.v:124` 向 `SA_PE_Mul_Array` 连接 `.slice_rst(slice_rst)`，而本次编译的
  `SA_PE_Mul_Array` 没有该端口。分类为 `SERVER_RTL_INTERFACE_COMPILE_MISMATCH`，
  不是 Conv 数值、配置或包侧 observer 问题；v3 状态为
  `ADJUDICATED_COMPILE_FAILURE`，不生成 v4，E4/E5 与正式三方计数不变。

下一主线动作从原第 4 项开始：服务器 owner 先统一 `SA_ALU`/`SA_PE_Mul_Array`
的 `slice_rst` 端口接口并确认 RTL 可编译；随后可原身份重跑 node0004 v3，不需要因
本次编译前失败重建数值 workload。与此同时继续在不重测已接受非 Conv 算子的前提下，
按 schedule signature 物化其余 Conv，并收敛整网 allocator/address/lifetime。

GitHub 私有仓库 `xlsjdjdk/Trassic2.0_RTL` 的 `master` 已同步为本地独立只读快照
`Trassic2.0_RTL/`，HEAD=`5f2f8d3a2358c090143caa35957c07ff3650ff4c`。相对
`NDP_copy01/rtl` 的 2,010 个 source，GitHub 快照有 2,008 个，13 项不同：
11 项同路径内容变化、2 项仅历史本地存在。GitHub master 的
`SA_PE_Mul_Array.v` 已修正 INT8 carry 二次左移，但同时删除 `slice_rst` port/reset
branch；`SA_ALU.v` 仍连接该端口，因此 GitHub master 自身与两个服务器 return
一致地存在 compile-interface mismatch。该快照不覆盖 `NDP_copy01`，也不作为
compile release；详细记录见
`.agents/task_records/20260729_trassic2_github_master_sync_and_interface_adjudication.md`。

### 0.1 2026-07-29 分族重新规划与同步基线

本节是当前唯一分发基线，覆盖第 4 节及第 6.1 节中仍保留的过期“等待生成 node0004”
描述。硬件侧最新信息按以下边界消费：

- 硬件组已报告历史问题 1/3/4 完成修补，问题 2/5/6/7/8 判断为非当前必需缺陷；
- 本地主线据用户指示按 Conv 所需 RTL 语义可用、服务器可编译继续推进，但未绑定
  `Trassic2.0_RTL` 的最终 commit，也未把 Git 拉取成功、服务器 compile 成功或动态
  readback 视为既成事实；
- 当前 node0004 v3 与 GAP node0071 v2 return 已把服务器 compile 状态裁决为
  `SERVER_RTL_INTERFACE_COMPILE_MISMATCH`：caller `SA_ALU` 连接 `slice_rst`，
  compiled callee `SA_PE_Mul_Array` 不含该端口；Windows `.git/FETCH_HEAD:
  Permission denied` 属于另一项仓库写权限问题，不改变算子数值结论；
- node0004 fresh 完整 Conv 包已经生成，故任何分支不得重复生成同身份包。下一次只在
  真实回传命中 package/compile/config 首分歧，或主线批准新身份时重建。

重新规划后的并行任务如下：

| 优先级 | 责任任务 | 立即工作 | 完成边界 |
|---|---|---|---|
| P0 | Conv/SA | v7有效动态证据确认qualified read-data后Buffer5/D write/terminal长期全零；v6-v10依次因observer/qualified/canonical/bootstrap门隔离 | fresh v11完成最终ZIP current-rule自检后，才可进一步收窄read-data→Buffer5区间；有效node0004动态结果前不批量封包 |
| P0 | Requant | Conv53 tail signature binding 已完成：53 个 multiplier payload/精确 signature 全部唯一，归并为 9 个 physical schedule profile、24 个 shape+zp group；node0004 配方可复用但其常量不能复制 | manifest/validator 24/24 PASS；其余 52 项必须 fresh multiplier/address/lifetime binding，不重复 node0004 包 |
| P1 | QLinearAdd | v6缺canonical decision，v7因生成后active-rule漂移，均隔离；QAdd功能根因无新证据 | 唯一v8 progress-canon已通过最终ZIP current-rule自检，可用于有界定位 |
| P1 | QLinearGlobalAveragePool | v4-v6依次命中compile-enable、canonical与current-rule门并隔离；功能hang根因仍未闭合 | 唯一v7 finalaudit冻结73个workload且已通过最终ZIP current-rule自检，可用于有界定位 |
| P1 | Dequant + Flatten/View + Quantize | Dequant 与 Quantize owner sections 已写入 canonical，Flatten requirement projection 已完成；不重测 node0072 或 View。node0074 已确证无 direct/equivalent binary32 DIV entry，REC→MUL 有同 scale 159→158 反例 | canonical=`resnet50_node0072_node0074_shared_endpoint_v1.json`；等待 Flatten owner section。node0074 exact division 与 consumer endpoint 保持 fail-closed，不生成 target/package |
| P2 | MaxPool | 直接保留 Git 原始 JSON 复用，不再进行算子数值复测，不修改 JSON，不消费历史 MaxPool 物化资产 | 等整网或用户提供的新原始回传命中首分歧时再分析；当前不重建 |
| HOLD | 人工 JSON | 保持 corrected-v3/stride overwrite 历史裁决冻结；不把硬件假设外推为人工 JSON 修复 | 仅在用户提供新人工 JSON 或新 return 时执行 fresh 消费/分析 |

共同执行规则：

1. 已接受复用的非 Conv 算子不做预防性复测；整网首次比较只重开首分歧 owner。
2. 分支只维护本族 generator/validator/config/contract/artifact/task record，不修改
   `.agents/plan.md`、公共规则或功能 RTL；规则变更只提交 `RULE_DELTA_PROPOSAL`。
3. 新包可以由对应算子族直接生成到 `PACKAGE_READY_NOT_RUN`，但不得上传、运行、检查
   服务器文件/名称或自行取得 lease。
4. 所有回传统一提交 `RETURN_ANALYSIS`、`BLOCKER_DELTA`、`RULE_DELTA_PROPOSAL`、
   `PACKAGE_RELEASE`，并明确是否重复数值分析、是否消费复用资产以及 package/ZIP SHA。
5. 曾 timeout/人工中断或预期长时间运行的包必须消费
   `CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001`；实际 argv 启用并在 return 回收
   低开销进度摘要，能简要区分持续前进、超过 stall window 停滞及最后卡住的边界。

### 0.2 node0004 首次真实回传覆盖

node0004 v1/v2 return 已依次关闭两个基础设施问题：

- 活动服务器 `SA_PE_Float_Control.v:1` 含 `<<<<<<< HEAD`，VCS
  `compile_exit_status=2`，simulation 未开始，正式动态 readback=0；
- 失败分类为 `SERVER_SOURCE_MERGE_CONFLICT_COMPILE_FAILURE`，不是 Conv 数值或配置失败；
- 原 v1 包把全部 320 个 runtime D 目标预置在 workload 中，compile 失败后仍与
  golden 相等并误报 PASS，分类为 `PACKAGE_RESULT_GATE_FAIL_OPEN`；
- v1 包撤销运行资格，只保留 merge-conflict 与预置 D 假通过证据；
- v2 已关闭预置 D、结果门 fail-open 和递归 return 收集；其正式 return 越过原
  merge-conflict 位置，故 `B_NODE0004_SERVER_SOURCE_MERGE_CONFLICT` 已关闭；
- v2 新首分歧为 package 未携带服务器 TB 无条件 include 的
  `native_return_observer.svh`，compile=2、simulation未启动、320项全missing，gate
  正确失败；
- 主线唯一候选改为 `r5_n4_hw_v3_obs.zip`。v3 使用 package-local observer 与显式
  include dir，不安装或修改服务器 TB/RTL；
- 本地硬件语义可用假设仍可用于 52 Conv 的合同/物化规划，不得再表述为服务器源码
  已可编译。52 Conv 在 node0004 获得有效动态结果前不得批量封包。

此次证据已写入公共服务器包规则：

- `CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001`

## 1. 当前总状态

| 层级 | 当前状态 | 声明边界 |
|---|---:|---|
| ONNX 独立软件公式 | 78/78 | 不证明硬件配置 |
| typed hardware request | 133/133 | 不证明 JSON 已物化 |
| hardware stage family | 10 | 各 family 独立放行 |
| 非 Conv 节点复用路径已指定 | 25/25 | 每个非 Conv 节点都有 exact、approved-equivalent 或 structure/primitive reuse binding；不等于完整后端通过 |
| 完整节点直接复用候选 | 3/78 | Dequant×2、Flatten×1 直接进入整网；MaxPool 只复用 Git 原始 JSON，旧物化资产已按用户覆盖撤出 |
| 整网 133-stage integration assembly | 0/1 | 尚未生成；下一主线工作是冻结 reuse manifest 后一次性组装 |
| 精确物化 JSON | 4/133 | Dequant node0077 已正式；Dequant node0072、Requant node0001、GAP sum hwop0071-00 为本地 candidate/baseline；MaxPool/node0004 历史物化资产已撤出计数 |
| CONFIG_ONLY_CORRECTNESS_BASELINE | 3 | 完整节点：Dequant node0072、GAP node0071、QLinearAdd node0007 nested-LC v4；MaxPool/node0004 历史 baseline 已撤销，node0004 fresh 另按硬件可用假设记 config-bound E2 |
| 完整 ONNX 节点本地 config-only E2 | 4/78 | Dequant node0072、GAP node0071、QLinearAdd node0007 nested-LC v4；node0004 为硬件可用假设下的 fresh config-bound E2 |
| 服务器测试包 | 2 项已验证未运行诊断，1 条family复核中 | GAP v7 finalaudit、QLinearAdd v8 progress-canon 已通过最终ZIP current-rule自检；Conv successor 正在同门复核；旧包隔离，不计E3/E4/E5 |
| 正式 ResNet50 target config | 1/133 | Dequant node0077/v6 |
| 正式服务器 E4 | 1 | Dequant node0077/v6 首次完整通过 |
| 正式服务器 E5 | 1 | Dequant node0077/v6 全新身份重复通过 |
| 已验收的服务器 E4 尝试 | 4 | Dequant node0077/v6 第四项首次通过；前三项均失败/不完整 |
| 正式 ResNet 节点三方闭环 | 1/78 | Dequant node0077/v6 的 golden、config-bound simulator、E4/E5 hardware 已逐 bit 闭合 |

Dequant node0077/v6 已取得首个正式 stock-RTL E4+E5 重复通过：两次均为 28/28 slice 自然完成，
28×188=5,264 行正式 D 全部逐 bit 对 golden，layout inverse 无损还原
`float32[16,1000]`，5,264 request/5,264 write-data temporal raw count、return exact-set
及 stock RTL 身份全通过。E4 是 `FIRST_DYNAMIC_PASS`，E5 是
`REPEATED_DYNAMIC_PASS`；`B_DEQUANT_SERVER_E5` 已关闭，node0077/v6 已升级为第一个
正式 target config。配置绑定 simulator 已消费最终 v6 JSON、bitstream、execplan/SCA、
physical I/O 与批准 inverse；16,000 个 fp32 元素在 golden、simulator、E4、E5 间逐 bit
一致，`B_DEQUANT_CONFIG_BOUND_SIMULATOR_LEG` 已关闭，正式三方节点计数为 1/78。

Dequant node0072 已新增本地 `CONFIG_ONLY_CORRECTNESS_BASELINE`：真实
`uint8[16,2048,1,1]→fp32[16,2048,1,1]` 经两级普通 GA 完成 final address-bound
JSON、mapping、bitstream、execplan/SCA、28×4736B physical D、logical inverse 与 W3
逐 bit 闭合。该路线比数值足够的单层 MUL 多一层、使用 8 PE，并产生 384 padding
elements；只计本地 materialized E2，不计正式 target、E4/E5 或三方节点。

GAP node0071 已取得完整 `CONFIG_ONLY_CORRECTNESS_BASELINE`：复用六级
`49→25→13→7→4→2→1` non-transout int32_mac sum tree，并新增
`INT32→FP32 MUL→8192B/slice scratch→独立 RNE/int32_sub/saturation` 两级 tail。
32,768 个最终 UINT8 元素 config-bound mismatch=0；完整本地 E2 已闭合并生成
fail-closed 服务器包，但未运行，不增加正式三方计数。

MaxPool `node0002 / r5:hwop-0002-00` 的旧完整节点本地物化资产已按用户
2026-07-28 覆盖全部撤出正证据：除 Git tracked 原 JSON 外，不再复用此前的 mapping、
bitstream、execplan、SCA/SCA_D、local-E2 或测试包。fresh-v3 已从空 cache 两次独立生成，
覆盖两个真实 ResNet channel tile、100,352 个 UINT8 元素，config-bound golden
mismatch=0；该范围仅为两-tile 动态诊断包，不恢复完整节点 E2 计数。
活动 RTL 聚焦审计已翻案旧“`int8_max` 极性为 min”结论：数值路径按 byte 选择 unsigned
max；真正成立的源码缺陷是 pipeline0 ready 方程缺 INT8 分支，故动态 flow blocker 仍开。

用户已明确推翻 node0004 的既有本地放行：历史 JSON、mapping、bitstream、execplan/SCA、
package、local simulator 与测试结论全部视为不可信/失败资产，只保留为负面历史，不能作为
新生成输入或证据收据。Conv 精确物化与 baseline 计数各减 1；首个完整 node0004 必须从
typed request、活动规则和锁定原生工具链全新重建。

Requant 54/54 stage 已按 W3 公式分类：33 项 `y_zero_point=0` 数值兼容，21 项被当前
guard 反证；仅 node0001 完成物理 E2 与 config-bound simulator。其硬件 guard 输出仍全零，
最新证据已逐事务证明 64/64 条 BST data 与 coeff address 正确；待查范围收窄到
系数 SRAM 输出经 ALU/postprocess/normal outbuffer 到 MSE4 的数值路径。包内把持续为高的
level qualifier 当事务导致的 parser route 已废弃为 observer 事件限定错误。
独立原生 SiLU control 又证明共同 stock-RTL 的 coeff→ALU→postprocess→normal
outbuffer→MSE4 payload 逐 bit 正确；该 control 的正式 D 因 occurrence/address 覆盖
只保留最后值而失败，不得冒充 Requant 通过。
GAP `int32_mac`、GAP repair 和功能 RTL patch 服务器路线继续冻结。

Human MAC corrected-v3 fd2 已自然完成但数值失败：28/28 D 中每片仅前
256/1,024 bytes 逐 bit 正确，其余 768 bytes 全 X。首分歧不是 GA `src_id` 或
`LC2.last_index=1`，而是 native control-register handler 在编码前把
`stream2.dim_stride[1]` 从 256 覆盖为 1024；最终 occurrence 地址与正式 D 的交集
精确解释全部 X 区间。该返回分类为
`FIRST_DYNAMIC_FAILURE/NO_DYNAMIC_BASELINE/FORMAL_D_PARTIAL_COVERAGE`，且因相邻
return SHA sidecar 缺失继续身份 fail closed；不计正式动态通过。

## 1.1 核心目标与三方口径

最终目标是同一冻结 ResNet50 输入在三个执行侧逐层得到一致的逻辑 tensor：

```text
ONNX/W3 golden ↔ config-bound simulator ↔ stock-RTL hardware
```

- `CGRA_SIM` 作为旧 ResNet/QNN 软件算子和公式参考，证明算式；它若未消费当前
  28-slice JSON、地址和码流，就不能单独证明 stage→JSON→bitstream；
- simulator 正式一侧必须由 `NDPFuncModel` 或等价配置绑定执行器消费当前最终配置、
  物理布局和输入，输出 physical D 后按获批 layout inverse；
- hardware 一侧必须消费同一冻结 workload/bitstream/execplan/SCA，正式回读 physical D
  并使用同一个 inverse；
- 比较器分别报告 golden↔simulator、golden↔hardware、simulator↔hardware；整数
  bit-exact，浮点逐 tensor 显式容差，按 topology index 定位首个分歧。

DeepSeek 已验证 JSON 只作为生成 ResNet50 算子规则的硬件 oracle，不是最终三方中的独立
交付目标；只有能关闭明确 ResNet blocker 的 DeepSeek 对照才继续。

## 1.2 纯配置正确性优先策略

用户已明确冻结所有功能 RTL 修改路线。当前目标是先让 ResNet50 以纯配置方式数值跑通：
原生并行路径被反证、缺少精确变体或受冻结 RTL 限制时，允许采用多 stage、显式 scratch、
单乘积序列化、地址重放、额外 barrier 与低利用率等配置绕行；吞吐和资源效率暂不作为
放行条件。

所有绕行必须遵守 `CDA-CONFIG-ONLY-CORRECTNESS-BYPASS-001`，并在机器合同、validator
报告和 task record 中同时记录：原路径为何不可用、精确等价范围、实际物化机制、性能/
资源代价、仍未解决的 production blocker 与声明边界。只有在冻结合法域逐 bit 等价、
最终 JSON 回读及 mapping→bitstream→execplan/SCA/address/lifetime/config-bound simulator
闭合后，才可称 `CONFIG_ONLY_CORRECTNESS_BASELINE`；不得称 production、性能可接受或整网
正式通过。

主线只维护计划、公共规则、全网计数、依赖和 lease；各算子族并行维护本族
generator/validator/config/contract/artifact/task record。当前不检查服务器文件或名称，
不上传、不运行、不授予 `SERVER_RUNNING` lease。权威授权记录为
`.agents/task_records/20260727_config_only_correctness_first_parallel_mainline_policy.md`。

## 1.3 ndp-sim 复用审计后的缺口口径

ResNet50 的 78 个 ONNX 节点分为 8 类：53 QLinearConv、17 QLinearAdd、
2 QuantizeLinear、2 DequantizeLinear，以及各 1 个 MaxPool、
QLinearGlobalAveragePool、Flatten、QLinearMatMul。ndp-sim 当前 55 份 JSON 中，
53 份被元数据标为用户授权的上游硬件测试参考，2 份为项目 candidate。该资产足以显著
复用字段和拓扑，但不自动证明目标 qdomain、mapper、物化回环或 E4/E5。

按“精确 ONNX backend”统计，除 Conv 外仍缺 QuantizeLinear、QLinearAdd 与
QLinearMatMul 的完整后端；按“独立工程共因”统计，当前优先级收敛为：

1. `R5_GAP_EXACT_UINT8_QUANT_TAIL`（P0）：FP32/INT32→UINT8、任意 zero-point、
   float32 scale、nearest-even、saturation 与 typed transport 的统一精确量化尾；
2. `R5_GAP_INT8_SA_DOT_PRODUCT`（P0）：Conv 与 QLinearMatMul 共用的可靠
   UINT8×INT8→INT32 SA 点积；
3. `R5_GAP_COMPOSITE_BACKEND_INTEGRATION`（P1）：复用已有原语，完成
   QLinearAdd、GAP、MaxPool 与 View 的 handler/mapper/address/lifetime 物化。

其中 `R5_GAP_*` 是规划 gap ID，不自动成为公共 blocker 或规则 ID。Dequant 不缺新算术
原语；MaxPool 与 GAP 不再称“库中缺算子”，其剩余问题分别是 flow/动态闭环和两级控制
物化；Flatten 是物理 view 合同。权威审计为
`contracts/operator_config/resnet50_ndpsim_reuse_gap_audit_v1.json` 与
`.agents/task_records/20260727_ndpsim_resnet50_reuse_audit_and_replan.md`。

## 1.4 复用优先、免算子复测的整网执行策略

用户于 2026-07-28 明确要求：已经可复用的算子/原语直接用于整网，不再进行算子级复测；
只有最终整网集成的首分歧命中该资产时，才返回对应 family 查验。活动规则为
`CDA-REUSE-FIRST-DEFERRED-RETEST-001`。

当前复用口径：

- 25/25 个非 Conv ONNX 节点均已有复用路径：相同完整算子直接 binding；近似算子只绑定
  已相同的字段、拓扑和 transport，缺失计算归入共享 gap，不重复测试已有部分；
- 直接完整节点候选为 Dequant×2、Flatten×1，共 3/78；MaxPool 只保留 Git 原始 JSON
  source reuse，旧完整节点物化资产不再计数；
- QLinearAdd×17 已复用 dequant/add stage0，GAP×1 已复用 sum tree；两者只等待共享
  exact UINT8 tail 与整网边界绑定，不再重跑已完成前半段；
- Quantize×2、54 个 Requant/AverageRequant stage 与 QLinearAdd/GAP/MatMul output
  统一消费一次实现的 exact UINT8 tail；
- 53 个 Conv 与 1 个 MatMul 在旧本地 RTL 身份上的普通 SA/SA 内 serialized-psum
  反例保留为历史证据；按本计划第 0 节的用户硬件可用假设，node0004 改走 fresh
  normal four-lane SA，并在最终 packing 上完整枚举实际 W3 dot4 域。只有 node0004
  完整节点通过后，才按 schedule signature 判断哪些实例可批量复用；
- MaxPool 的 stock RTL pipeline0 flow blocker、Flatten endpoint blocker 等保留为
  `DEFERRED_TO_INTEGRATION`，不因免测而 close。

下一执行顺序固定为：

1. 冻结 reuse binding manifest，不运行已有算子的 operator test/golden/simulator；
2. 只完成两个不可复用的公共能力：node0004 direct signed two-stage exact UINT8
   tail、fresh normal four-lane Conv 物化；
3. 一次性组装 133-stage graph、全局 allocator/address/lifetime、execplan/SCA；
4. 做首次整网 config-bound 比较；若有分歧，只回查首分歧 owner；
5. 服务器动作仍等待用户另行授权，本策略本身不生成包、不检查服务器。

`REUSE_ACCEPTED_FOR_INTEGRATION` 是装配状态，不增加 E2/E4/E5 或正式三方计数；因此
“可直接进入整网”与“已正式验证”两套计数并行保留。

机器策略为
`contracts/operator_config/resnet50_reuse_first_integration_policy_v1.json`；主线记录为
`.agents/task_records/20260728_reuse_first_no_operator_retest_mainline_policy.md`。

## 1.5 Conv 优先：按硬件可用假设恢复 fresh 正常路径

用户已明确修正执行顺序：

- 已存在且可信的复用算子直接进入整网，不做无意义复测；
- 其他算子可按风险逐个测试，或用一个代表覆盖完全相同的参数类别；
- Conv 首个完整节点必须单独测试；
- 在详细分析本地活动 RTL、mapper/encoder/control/packing 代码并穷尽其他精确入口前，
  不得开始新的 Conv 配置绕行生成。

当前 Conv 执行门（覆盖下文 C0 历史裁决）：

```text
C0_RTL_AND_ENTRY_AUDIT = COMPLETE_DUAL_REPORTS_ACCEPTED
HARDWARE_SEMANTICS_ASSUMED_AVAILABLE = true
CLOUD_RTL_CLEANUP_AND_IDENTITY_GATE = DEFERRED_NOT_LOCAL_BLOCKER
NORMAL_EXACT_ENTRY = ENABLED_FOR_FRESH_NODE0004
NODE0004_DOT4_W3_AUDIT = PASS_0_OF_51_380_224_MISMATCH
SA_SERIALIZED_PSUM = CONFIG_FALLBACK_IF_FINAL_PACKING_DOMAIN_FAILS
SA_PRODUCT_PLUS_GA_TREE = DEPRIORITIZED_DIAGNOSTIC_FALLBACK
C1_COMPOSITE_PREDESIGN = PASS_PROPOSAL_ONLY
C1_TARGET_MATERIALIZATION = AUTHORIZED_FRESH_NORMAL_PATH
FIRST_ACCUMULATE_PHYSICAL_WORK = FRESH_NORMAL_SA_MATERIALIZATION
FIRST_TAIL_WORK = TWO_STAGE_SIGNED_INT32_TO_FP32_EXACT_UINT8_TAIL
NEW_CONV_GENERATION_ALLOWED = THROUGH_PACKAGE_READY_NOT_RUN
EXISTING_NODE0004_LOCAL_ASSETS = UNTRUSTED_NEGATIVE_HISTORY_ONLY
FIRST_COMPLETE_CONV_NODE = node0004
FIRST_COMPLETE_CONV_PASS = false
PACKAGE_RELEASE = NONE
```

### C0：本地 RTL 缺陷与替代入口双重审计

由 Conv/SA 会话主审，另设独立 RTL 审计会话复核。两条线都只读，不生成 Conv 配置，
不修改 RTL，不访问服务器。

主审必须从 node0004 typed request 逐级追踪：

```text
typed request
→ operator JSON
→ mapper / bitstream fields
→ SA control mode
→ DataA=s8 / DataB=u8 / DataC=psum32 packing
→ active filelist / module hierarchy
→ multiplier array / CSA reduction
→ psum32 output
```

必须绑定本地活动 filelist、RTL/module、mapper、encoder 和 handler 的不可变 SHA，并逐项
回答：

1. 当前 node0004 是否确实到达目标 `s8×u8→int32` 路径；
2. JSON、mapping、bitstream、control mode 与 operand packing 是否已排除配置/编码错误；
3. `CSA_4to2` carry 是否已经对齐，而 `SA_PE_Mul_Array` 是否再次左移；
4. 四个合法乘积总和是否需要 signed18，现路径是否只保留 signed17 或丢弃 `cout`；
5. 四个 ones、最大正负合法域、正负混合、psum32 wrap、K-tail、bias 和 nonzero
   input zero-point 是否都能被同一源码方程解释；
6. 是否存在任何不经过该错误 compressor 的精确 SA opcode/mode、lane/packing 配置、
   GA `int32_mac` 路径或其他原生 handler/mapper registry 入口；
7. FP16/BF16/FP32 路径是否保持目标 INT32 语义，不能仅因可运行就算替代入口。

独立复核不得直接复述既有 task record，必须从活动本地 filelist 和直接消费者重新建立
code path 与 capability matrix。若本地可用独立 RTL 编译/仿真工具，可增加最小只读
testbench；若不可用，必须明确区分 static RTL proof 与 dynamic RTL proof，不得虚构动态
结果。

C0 已收到主审与独立复核两份结构化报告，并由主线逐项验收：

```text
RTL_DEFECT_CONFIRMED = true
NO_EXACT_ALTERNATIVE_ENTRY = true
SERIALIZED_CONFIG_FALLBACK_IS_ONLY_AVAILABLE_EXACT_ROUTE = false
NORMAL_EXACT_ENTRY = false
SA_SERIALIZED_PSUM = false
SA_PRODUCT_PLUS_GA_TREE = proposal-only
```

活动 INT8 SA 同时存在三项功能缺陷：`DataC/psum32` 被清零、`CSA_4to2` carry 被二次
左移、四乘积 signed17/断开 cout 不足。真实 `SA_ALU` Icarus 反例证明普通四 lane 与
SA 内 serialized psum 都不能完成 Conv accumulate；旧“单乘积序列化即可跨 occurrence
累加”结论已正式撤回。

两份报告也证明复合配置所需原语可表达：`DataC=0` 的 SA 单产品精确、32-bit SA
outport 可写 INT32 scratch、GA opcode14 `int32_mac(A,1,C)` 对 signed/mixed/wrap 逐 bit
精确，且 node0071 已证明 stage2+ INT32 scratch reload/same-mask barrier 的本地物化能力。
因此主线选择 `PATH_FRESH_COMPOSITE_CONFIG_C1`，授权设计和本地物化，不把 proposal
冒充现成 exact entry：

- stage P：每 occurrence 至多一个非零乘积 lane，`DataC=0`，逐产品正式写 INT32 scratch；
- stage R：GA `int32_mac(A,1,C)` 显式加法树，逐级 scratch/reload/drain/barrier；
- correction：bias 与 `-x_zp*Σw` 作为有 owner 的 INT32 additive leaf；
- stage Q：消费 fresh node0004 qparam/W3 绑定，物化完整 UINT8 tail；
- 先关闭 `(n,oc,oh,ow,k)→byte`、bank/coverage/terminal、typed/manual materializer、
  dual-stream/tag/FIFO、address/lifetime 与资源可完成性，再生成任何测试包。

该授权仅覆盖 node0004 fresh composite C1；不授权功能 RTL 修改，不允许复用旧
node0004 资产，也不把该路线外推到其他 Conv/MatMul。

### C1 历史裁决与 2026-07-29 覆盖

fresh C1 已执行到配置生成前停止门：

- 全量 fresh INT32 accumulate 对正式 W3 的 3,211,264 个元素逐 bit 0 mismatch；
- 205,520,896 个 scalar product；全局 product scratch 822,083,584 bytes，超过
  28-slice aggregate 704,643,072 bytes；
- `(n,oc_group8)` 切成 128 tile 后每 tile 13,046,304 bytes，小于单 slice
  25,165,824 bytes，可用五波 `[28,28,28,28,16]`，所以容量不是首阻塞；
- 六级 GA tree `64→32→16→8→4→2→1` 加 bias correction 的逻辑地址、容量和
  3,686,535,168-byte accumulate traffic lower bound 已闭合；
- 但没有获批 materializer 将单产品绑定到最终 LC/MSE/Buffer bank、SA lane、
  last/last_index、direct INT32 scratch write 与 205,520,896 occurrence inverse，
  故 `B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL` 为 accumulate 首断点；
- tail 的 `max(acc,0)` 数学改写对全 signed INT32 域及正式 W3 均等价，但活动 opcode
  不存在 raw signed 32-bit max：FP32 max 必须先转换、int8_max 只是 byte lane，
  INT32 只有 sum/sub/mac。因此
  `B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE=OPEN_CONTRADICTED` 为完整节点更硬的首断点。

上述结论保留为旧 RTL 身份下的负面历史，不再作为当前生成停止门。按第 0 节用户覆盖，
本轮视 DataC/psum、carry handoff 与 signed INT32→FP32 为服务器侧已修复能力，恢复
normal four-lane accumulate 和直接 signed tail。旧 composite predesign 仅作为正常路径
失败后的资源/拓扑参考，不得反向成为默认实现。任何新产物仍必须从可信 typed/model/W3
和活动规则 fresh 生成，不增加 E2/E4/E5/三方计数，直到对应证据真实通过。

### C1：node0004 首个完整 Conv 单节点测试

本轮已由第 0 节解锁。首个目标必须覆盖完整节点，而不是只覆盖 accumulate：

```text
hwop-0004-00 ConvInt32Accumulate
→ hwop-0004-01 RequantizeUint8
→ node0004 complete UINT8 logical output
```

- node0004 的全部历史本地资料不可信：禁止复用旧 JSON、mapping、bitstream、
  execplan/SCA、package、simulator output、local E2 或测试收据；
- 唯一允许的语义输入是锁定 typed request/lowering、正式 W3/model tensor、活动规则、
  本轮 C0 代码审计和获得授权的原生静态模板/工具源码；
- 默认路径改为 fresh normal four-lane SA + DataC/psum32 accumulate；必须从算子配置
  JSON 开始使用全新目录、全新 identity 重建。最终 lane packing 必须重新执行 node0004
  实际 dot4 域检查；只有该检查失败时，才切换 one-product-lane + DataC psum 绕行；
- SA-product→INT32 scratch→GA tree 仅保留为更后级诊断备选，不在 normal/serialized
  两条路径均未失败前生成；
- exact UINT8 tail 会话使用 node0004 真实 scale/zero-point/rounding/saturation 全新生成
  `hwop-0004-01`，不得引用旧 node0004 tail/candidate；
- 完成 full-node final JSON、mapping、bitstream、execplan/SCA、address/lifetime、
  stage barrier 和 config-bound inverse；
- 通过口径是完整 node0004 UINT8 tensor 对 W3 逐 bit 一致；
- stock four-lane 与 `single-product+nonzero DataC` 改为硬件假设下的正向聚焦验收；
  legal-domain signed17 反例继续作为 negative control；
- accumulate-only 不计首个完整 Conv 通过；
- 本地 config-bound 通过后才进入测试包生成；生成配置和测试包前分别重新完整读取
  `.agents/rules/生成前必读索引.md`、`算子配置规则.md`、`NDP硬件字段语义.md`、
  `INT8_SA点积专项规则.md`、`精确UINT8量化尾专项规则.md`、
  `RequantizeUint8算子配置规则.md`，以及测试包阶段的
  `服务器测试包生成规则.md` 和本地活动 package 入口 README，并保存 current SHA 收据；
- 本轮执行止于 `PACKAGE_READY_NOT_RUN`；不检查服务器现有文件/名称/RTL identity，
  不上传、不运行，服务器执行仍需用户另行授权。

### C2：Conv 参数类别扩展

typed lowering 与最终 packing 清单已经完成：其余 52 项共 22 个 exact schedule
signature，完整枚举 15,375,532,032 个实际 dot4 occurrence。

- 51 项普通 four-lane 域兼容；除 stem 外最宽负侧为 `hwop-0018-00`
  `[-47035,36864]`；
- 唯一例外为 stem `hwop-0001-00`：7×7/stride2/pad3、K=147、37 dot4 groups、
  tail=3、x_zp=114；475,267,072 个 dot4 中 2,499,984 次越过 signed17，首反例
  `[-21808,-27559,-24354,0]`，dot4=`-73721`；
- stem 使用 one-product-lane + DataC psum，serialized padded occurrence=
  1,901,068,288，是 normal 的 4.0 倍，lane utilization=`24.831%`；
- stem symbolic schedule、64 个 slice-region 容量和 802,816B D 连续覆盖方程已闭合；
  当前首阻塞不是算术或容量，而是活动工具只批准1×1/3×3和node0004固定尺寸 handler，
  缺少 `hwop-0001-00` 的 typed semantic owner/patch registry identity；
- 主线已按用户“继续本地生成整网算子、由主线直接下发必要分支工作”的授权，批准在
  hash-bound 隔离 ndp-sim 副本中增加窄 stem patchset/handler；活动 checkout 与功能
  RTL 继续只读，禁止借用node0004 op identity、常量或尺寸；
- 22 个 signature 后续各选代表，但 node0004 有效动态结果前只允许本地物化/验证，
  不批量封包；同 signature 也必须 fresh 绑定 multiplier、地址和 lifetime。

### C3：其它算子并行边界

- Quantize/exact-tail 会话：优先完成 node0004 所需 INT32→UINT8 tail，再一般化；
- Requant 会话：复用既有 54-stage 分类，只生成 node0004/53-Conv qparam binding，
  不重做原有数值分析；
- 整网 assembly 会话：建立 133-stage/93-edge 骨架与全局 allocator/lifetime，
  不运行复用算子的单算子测试；
- QAdd/GAP/Dequant/View：冻结现有可信资产供整网直接引用；只有整网首分歧命中时
  才回查，或新计算边界确实没有被已有资产覆盖时按类别测试。MaxPool 仅冻结 Git
  原始 JSON；其余物化资产必须使用 fresh-v3 之后的新链或重新生成。

exact UINT8 tail 属于新共享能力，可做一次公共反例/能力验证；禁止演变为 53 次重复的
Conv tail 单算子测试。

### C4：整网装配与失败回查

Conv 类别覆盖完成后，一次性组装 133-stage graph、93 runtime edges、全局
allocator/address/lifetime、CONFIG/terminal、execplan/SCA，并运行首次整网
config-bound 比较。失败时按 topology index、tensor identity 和 address occurrence
只重开首分歧 owner；其他复用资产继续冻结。

本计划不授权修改功能 RTL、检查服务器文件/名称、生成或运行服务器包。活动授权记录为
`.agents/task_records/20260728_conv_rtl_audit_before_config_bypass_mainline_authorization.md`。

## 2. 已完成任务：DequantizeLinear 正式 target 与 stock-RTL 动态闭环

状态：`LOCAL_E2_V6_COMPLETE_SERVER_E4_E5_PASS`，`candidate_release=true`，
`formal_target_instance_allowed=true`，`dynamic_baseline=REPEATED_DYNAMIC_PASS`，
`evidence_level=SERVER_E5_FORMAL_D_PASS`。

- `uint8[16,1000] → float32[16,1000]` 使用两级普通 GA；28 slice×750 有效元素物理补齐
  到 752。最终 JSON、mapping、bitstream、execplan/SCA 和 occurrence 回放已闭合。
- 原子诊断曾定位 D buffer 每 occurrence 只供 16/64 bytes；规则
  `CDA-DEQUANT-D-BUFFER-SUPPLY-CONSERVATION-001` 固定 4×16-byte row。
- 完整 E4 已自然完成：28×188 formal D、每片有效 750 fp32 与两个 `+0.0f` tail、
  全 tensor inverse、5,264 request/5,264 write-data 和 stock RTL identity 全通过。
- 全新身份 E5 复验相同的 28×188 formal D、inverse、temporal count、自然完成和身份门；
  关闭 `B_DEQUANT_SERVER_E5`，确认
  A read→GA add/mul→normal outbuffer→MSE4→completion 的重复动态闭环。
- 不再生成 Dequant 服务器包。config-bound simulator 已明确消费最终
  JSON/bitstream/execplan/SCA/physical I/O/layout inverse，并与 E4/E5 完成逐 bit 闭环。
- 记录：`.agents/task_records/20260727_dequant_node0077_full_v6_e4_pass.md`、
  `.agents/task_records/20260727_dequant_node0077_full_v6_e5_pass.md`。

## 3. 冻结路线与未解除 blocker

| 路线/family | 当前边界 | 重新启动条件 |
|---|---|---|
| GAP `int32_mac` pure-config | node0071 完整 local E2 已闭合；v4-v6依次暴露compile-enable、canonical、current-rule自检缺口并全部隔离；功能hang根因仍未闭合，动态基线仍无 | 唯一v7 finalaudit已通过最终ZIP current-rule自检，等待有界进度return；GAP→node0072 consumer endpoint保持 |
| GAP `int32_sum` / repair | 历史证据只读；配置 D-index 与 GA accumulator/invalid-slot 是正交问题；功能 RTL repair 未授权 | 分别关闭 CONFIG_SEMANTICS 与 RTL_CONTROL，且用户明确恢复对应路线 |
| MaxPoolUint8 | 旧完整节点 local E2/物化资产已撤出正证据。fresh-v3 只从 Git tracked 原 JSON、正式输入与空 cache 双构建，覆盖两个真实 ResNet tile，100,352 元素 config-bound mismatch=0；活动源码数值极性已证 unsigned max，旧 min 结论关闭，pipeline0 ready 缺 INT8 分支仍为确证缺陷 | `PACKAGE_READY_NOT_RUN`：`maxpool_node0002_original_json_fresh_v3.zip`，SHA `17164af2...0eed`。只允许用户提供绝对服务器根后运行，不检查服务器源码身份；结果仅作 `NO_DYNAMIC_BASELINE` 诊断，不称 E4/E5 |
| Requant/AverageRequant | 54/54 W3 与 33 zp0/16 even nonzero/5 odd nonzero 分类不变；本轮三组纯配置裁决均未物化，baseline=0。zp0/AverageRequant 首断点是 three-PE ordered-rounding topology；even/odd nonzero 首断点是 signed INT32 ingress，odd tie parity 为次级门；仅 node0001 保留实例级旧 E2 | 等待 shared topology 或 signed-ingress 能力闭合；禁止 host 预计算内部 scaled/final tensor 冒充重放，event-edge 包继续冻结 |
| Conv/MatMul | v7有效动态证据确认read-data accepted后Buffer5/D write/terminal长期全零；精确SA内部子根因仍未证明。v7-v9 observer/裁决缺陷均已确认并隔离。其余52 Conv已归并22 signatures | 唯一v10 canonical等待进一步收窄read-data→Buffer5区间；有效node0004动态结果前不批量封包；MatMul仍需独立layout/tail闭合 |
| View | node0073 已物化为 metadata-only zero-copy alias。node0072 已提供 standalone owner、strides/span、28片 base/coverage 与 addressed identities；node0074 endpoint 字段仍为 null | 等待 shared multi-op allocator/execplan、跨节点 visibility/lifetime、node0073 consumption，以及 node0074 同 storage/base+offset/131072B read coverage，才能 integrated local E2 |
| QuantizeLinear / shared quant tail | 两阶段 scratch singleton diagnostic 已配置绑定区分顺序 26 与 fused 25：stage0 scratch bits=0x41cc0000，三份 strict JSON 的 222 个 leaf diff 与全部 byte coverage 已闭合；范围仅为 32 个相同正数 lane，不是 baseline。node0074 的首个不可绕断点是 exact binary32 division：2-vs-1 | shared tail 继续补完整域、signed/magic domain、native transport/mapping/terminal；node0074 exact division 无精确原语前不生成 target |
| QLinearAdd | 17/17 stage0 数值资产继续复用；v5-v7依次因observer/canonical/rule-drift门隔离，未形成有效动态attempt | 唯一v8 progress-canon已通过最终ZIP current-rule自检，等待qualified/canonical进度return |

冻结表示不得继续修包、重编码、上传或运行；读取历史证据和完善不产生候选的 validator
仍可进行。

## 4. 面向全网三方比较的重规划主线

已完成前置继续有效：Dequant node0077 三方闭环 1/78；最小双 stage 生命周期（本地 E2 已完成）；
Requant 54/54 W3 分类与 node0001 物理 E2；DeepSeek/ndp-sim 可信模板的字段和拓扑 oracle。
本次重规划暂停普通封包与服务器路线，先消除重复造算子，把工作收敛到共因合同。

1. **P0-A：统一 exact UINT8 quant tail**：
   - 12-cell capability matrix 与五类 consumer 映射已完成，当前裁决为
     `NO_UNCONDITIONAL_PURE_CONFIG_PROVEN`；
   - 可直接复用的仅是 raw FP32 GA ingress、quant-from-buffer 的 LC/MSE/Buffer/two-PE
     骨架、raw FP32/INT32 constants、有效 integer decode 后的 UINT8 saturation 和
     generic typed envelope；固定 rank-3 schedule、zp-in-magic bias、placeholder handler
     与未注册 mapper 均不得复用；
   - 任意 zero-point 的 proposal 固定 magic bias=`12582912.0`，把 zero-point 放入
     `INT32_SUB` raw constant `0x4b400000-zp`，但尚未批准。若必须保留 multiply 与
     magic-add 两个 float32 舍入点，则三 PE/四 lane 拓扑仍待证明；
   - GA rounding singleton config-bound 判别已完成：
     `int32=400,multiplier_bits=0x3d828f5c,zp=0` 经 stage0 独立 MUL 后 scratch bits
     为 `0x41cc0000`，两阶段顺序结果为 26，一阶段 fused negative control 为 25；
     222 个 leaf diff、128B scratch 与两份 32B output coverage 已按最终 JSON 闭合；
   - node0004 `zp=0` 的 raw `max(acc,0)` 绕行已完成全域数学与 W3 审计：
     3,211,264 元素、1,262,480 个负值，原公式↔max0↔golden 均 0 mismatch；但活动
     opcode 无 signed INT32 max，INT32 class 与 max decode 在 bit2 上矛盾，故
     `B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE=OPEN_CONTRADICTED`，未生成 tail target；
   - 该结果仅覆盖 32 个相同正数 lane，属于
     `LOCAL_CONFIG_BOUND_DIAGNOSTIC_NOT_BASELINE`；不能关闭完整域、signed ingress、
     magic domain、native transport/mapping/terminal。node0074 的最先断点已收敛为
     exact binary32 division：`x=0x3d0f81f1,scale=0x3cbf57ec` 的精确 divide+RNE=2，
     reciprocal-FMA-magic=1，因此不生成 node0074 target；
   - `B_QUANT_NODE0074_FLATTEN_ENDPOINT_BINDING` 是从属门：node0074-A 最终必须与
     node0073 output 同 storage/base+offset，覆盖 32,768 FP32/131,072 bytes accepted
     reads 并保持 allocation lifetime；exact division 未闭合时六个 endpoint 字段必须
     为 null，禁止 provisional 地址提升 Flatten integrated E2；
   - exact FP32 division、signed INT32 ingress、magic finite-domain、three-PE topology、
     typed binding 与 mapper registration blocker 全部保持开放，close none；
   - capability 合同已把 mutable `.agents/plan.md` 的生成时读取收据与 12 项硬语义
     source identity 分层：历史 plan SHA 不追写，硬语义源继续 current-match fail-closed；
   - 四条共享规则已写入 `精确UINT8量化尾专项规则.md`；既有
     `CDA-REQUANT-ROUND-MAGIC-001` 已收窄为 node0001 正式 W3 输入域的实例级条件式
     本地 E2，不再解释为全族 FMA 能力。共享能力格闭合前，不生成
     Quantize/Requant/QLinearAdd/GAP 目标 JSON 或服务器包。
2. **P0-B：INT8 SA dot-product 共因**：
   - C0 双重活动代码审计已确认 53 个 Conv 与 1 个 MatMul 的正常 INT8 SA 入口存在三项
     独立缺陷：DataC/psum32 清零、carry 二次左移、signed17/断开 cout；
   - 普通四 lane 与 SA 内 serialized-psum 路线都关闭。每 occurrence 单非零 lane 只在
     `DataC=0` 时精确地产生一个 product，不能独立完成 bias/K-tail/multi-wave accumulate；
   - `SA product→INT32 scratch→GA int32_mac tree` 的 primitive/source/config 可表达，
     node0071 为 stage2+ scratch/reload/barrier 提供非 node0004 正证据；node0004
     stage1 产品地址/coverage/terminal 与完整 typed topology 尚待 C1 物化；
   - 主线已执行 node0004 fresh composite C1 predesign：fresh W3 accumulate
     3,211,264 元素 0 mismatch；205,520,896 scalar products；全局 scratch 超容量，
     但 128 个 OC8 tile、每 tile 13,046,304 bytes、五波可行；
   - 六级 GA tree、bias correction、逻辑地址和 traffic lower bound 已闭合；首个物理
     blocker 是 `B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL`，没有最终
     LC/MSE/Buffer lane/terminal/direct scratch write/occurrence inverse；
   - 完整节点同时被 exact-tail raw signed max0 opcode 硬门阻塞，因此 target JSON、
     local E2 与测试包均未生成；其他 Conv/MatMul 不批量外推；
   - 兼容/修正 RTL 只保留为长期 production blocker 与验收 oracle，不是当前执行路线；
     用户已冻结所有功能 RTL 修改；
   - 兼容 RTL/repair 的可执行验收合同与 bit-exact proof harness 已完成：
     44,280 small-domain cases 中 signed18 proposal 与 serialized baseline 均 0 mismatch，
     stock negative control 22,134 mismatch；另覆盖完整单乘积合法域、四 lane 边界、
     psum32 wrap、K=3/5/6/7 tail 和 nonzero x-zp+bias；
   - future RTL identity 当前为 null，只接受用户提供/本轮授权的 immutable identity、
     top/module、compile/sim command 与 TB adapter，禁止自动探测服务器文件、名称或身份；
   - `B_SA_COMPATIBLE_RTL_IDENTITY_PENDING` 作为长期 production blocker 保持；
     它不阻断 node0004 composite config-only C1，但当前不得修改 RTL；
   - 历史 node0004 serialized accumulate JSON、下游产物、local simulator 与全部测试
     当前统一为 untrusted/failed negative history；不得复用或计本地 E2，
     `B_SA_SERIALIZED_FALLBACK_MATERIALIZATION` 对 node0004 重新打开；
   - C0 已关闭。当前只执行 fresh SA-product→GA-tree 复合路线，先完成 node0004
     accumulate+requant 完整单节点本地测试与测试包，再按
     schedule signature 选择每类一个代表并批量复用同类节点；
   - 完整 QLinearConv 仍被 shared exact UINT8 tail 阻塞，不生成服务器包或
     production 声明。
3. **P1-A：QLinearAdd 复合后端**：
   - 17/17 预设计内容已完成：16 个同 shape residual、1 个 `[1000]→[16,1000]`
     broadcast bias、五类 shape、六 qparam transport envelope、same-shape/broadcast DAG、
     A/B/Y symbolic allocation/lifetime 和 two-stage FP32 scratch；
   - W3 逐操作 float32 顺序是当前唯一数值 owner；对 17 组 qparam 穷举后，
     node0007 与 node0070 出现最终 UINT8 反例，禁止复用 add-dequant 的
     `x*scale + (-zp*scale)` affine 重关联；
   - stage0 project-stage config-bound candidate 已对 17 个实例物化为 51 个串行
     physical stage：A exact dequant、B exact dequant、paired FP32 add；51 个
     concrete non-alias scratch 共
     1,059,849,152 physical bytes，stage0 logical scratch traffic 1,766,395,200 bytes；
   - node0076 B 保持 1000 元素，B-dequant 末 occurrence 为 8 个有效元素/32 bytes，
     allocation 为 4000 typed + 32 padding；add stage 已枚举 16,000 个 `%1000`
     replay 地址，不展开 16 倍 copy；
   - 13/13 定向测试与 config-bound negative control 通过，只局部闭合 W3 DAG、
     readiness、scratch/barrier/lifetime 和 broadcast replay。完整输出仍停在
     `SUM_F32`；shared tail、native handler/final leaf diff、mapping/bitstream、
     execplan/SCA、Y 与 E4/E5 全部开放，不声明完整 baseline。
4. **P1-B：Requant 一般化**：
   - 机器可读 evidence input 已完成并通过 8/8：54/54 W3 exact，33 个 zp0 保留
     current-guard 数值兼容，但 33/33 均被 FMA rounding 与 finite-domain 阻塞；
   - 21 个 nonzero-zp 细分为 16 个 even-zp（signed ingress+rounding+domain）和
     5 个 odd-zp（再加 zero-point-after-RNE/tie parity）；node0014 的正式 W3 有
     32 个 `scaled=4.5,zp=123` 反例；
   - 三组 config-only 裁决均在新 operator JSON 前停止，baseline=0、E2/E4/E5=0：
     zp0 与 AverageRequant 首断点是 `B_QUANT_TAIL_THREE_PE_TOPOLOGY`；even/odd
     nonzero-zp 首断点是 `B_QUANT_TAIL_SIGNED_INT32_INGRESS`，odd tie parity 是次级门；
   - node0001 仍是唯一旧物理本地 E2，不能关闭共享 P0 门；MatMul requant
     `r5:hwop-0075-01,zp=60` 另有 rank2 layout blocker。input/constant replay 不得
     host-precompute scaled/rounded/saturated/final tensor 替代算子计算；
   - 既有 event-edge 包保持冻结待命，不把服务器诊断作为本次语义重规划的前置条件。
5. **P2：直接复用整网装配**：
   - Flatten node0073 metadata-only zero-copy 合同已完成：零 arithmetic JSON/
     instruction/request，32,768 元素映射、strides/span、ownership 与 lifetime 已闭合；
     node0072-D 已提供 standalone owner/base/coverage/addressed identities，但 shared
     multi-op allocator/execplan、跨节点 visibility/lifetime 与 node0073 consumption
     仍缺；node0074-A endpoint 因 exact division 保持 null，故 integrated E2 仍 false；
   - Dequant node0072 与完整 GAP node0071 均已完成本地 materialized E2；node0072
     当前只重放冻结 node0071 output，`B_GAP_NODE0071_TO_NODE0072_INTEGRATED_BINDING` 等待最终
     storage/address/coverage/lifetime；MaxPool 旧完整 local E2 已撤出，fresh-v3 仅为
     两-tile 诊断；当前源码 numeric max 已局部通过，pipeline0 ready/flow blocker 保持；
   - 上述复用资产全部标记 `REUSE_ACCEPTED_FOR_INTEGRATION`，不再派发 family 复测；
     只在统一整网 graph/allocator/execplan 中建立 immutable binding；
   - 模板身份不变时复用已有收据，不重复 operator test、golden、config-bound simulator
     或与整网首分歧无关的原生模板检查；
   - 首次整网比较失败后，仅按 topology index、tensor identity 和 address occurrence
     回查首分歧 family，其他复用资产继续冻结。
6. **恢复服务器与逐级组网的条件**：
   - 只有某一精确 ResNet candidate 已满足专项规则、完整 E2 与一次交付前自检，且用户
     实际上机时，才授予对应 lease；
   - 每族一个真实三方代表后，按 residual block→ResNet stage→head→整网扩展；
   - 最终生成 133-stage ordered plan，复验 78 节点、93 runtime edge、全局
     address/layout/CONFIG/lifetime/terminal，并完成两次独立服务器运行。

任何优先级都不能越过专项 blocker；“公式一致”“JSON可解析”“原子测试通过”或
“覆盖 stage 多”均不能单独成为正式节点/整网三方放行依据。

## 5. 当前执行门

公共生成门、证据等级、完整重建和 RTL 边界不在 plan 复写，分别由
`.agents/rules/生成前必读索引.md`、目标规则和 `.agents/agent.md` 唯一拥有。

效率门：普通编辑只做受影响检查，不在每个中间步骤重复全量重建、双隔离或全项目回归；仅在服务器候选首次形成或身份改变时做一次完整自检，身份未变复用收据，失败后按首分歧选择最小诊断合同。

服务器包交付硬门：所有责任会话在包生成完成后，必须重新完整读取 current 生成前索引、
公共服务器包规则和本族专项规则，并直接对最终 ZIP/sidecar 执行独立交付前自检；保存
规则路径/SHA/rule IDs、validator/负控命令和报告收据。只有
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true` 才能向主线报告 `PACKAGE_READY_NOT_RUN`。生成期间
active rule 漂移时必须复读并重验；新规则若要求改包，旧包隔离并使用新 identity，禁止
只追写 receipt。主线缺少该收据时不把包加入运行队列。

当前特有停止门：

- Dequant E4/E5 与 config-bound simulator 腿均已关闭并计入 1/78；不得继续生成
  Dequant 服务器包或重复执行已闭合腿。
- node0004 fresh normal accumulate、两阶段 exact tail 和完整单算子测试包生成已由第 0 节
  解锁，可执行到 `PACKAGE_READY_NOT_RUN`；其它既有 Requant event-edge 和 human JSON
  variable-root 包保持冻结只读，服务器运行仍只有用户实际上机且主线授予 lease 时恢复。
- P0-A/P0-B 的历史共因裁决继续保留；Quantize、QLinearAdd、Requant/GAP output quant
  仍需 rounding/typed binding/mapper 闭合。node0004 不再被旧 stock RTL 身份阻塞，
  按硬件可用假设 fresh 物化；MatMul 和其余 Conv 只在各自实际域/packing 检查后解锁。
- 下游完整非零正证据支配较早缺失 checkpoint；formal D 与 observer 分栏裁决。
- CGRA_SIM/公式、原子测试、shape holdout 都不得冒充完整节点或整网三方通过。
- 第 3 节冻结路线未取得表中证据和新授权前不得恢复；功能 RTL patch 继续冻结。

## 6. 协作与交接

| 工作 | 主要写入范围 | 交付 |
|---|---|---|
| 配置/规则维护 | `.agents/rules/`、`contracts/`、`resnet50_pipeline/`、生成器和测试 | rule ID、最终物化证据、blocker 变化、需重建范围 |
| 返回分析 | `server_returns/`、返回分析工具和 task record | 身份、最早分歧、退出原因、正式 readback 裁决 |
| 服务器包 | 新的 package/install/run/return 命名空间 | ZIP/sidecar、单命令、allowlist return、动态门 |

同一文件同时被其他任务修改时先协调 ownership。原始回传、冻结包和历史快照只读。

调度思考强度默认使用 `high`；只有规则冲突、证据翻案或跨算子架构裁决时，才在对应
轮次按用户/上游指示临时提升为 `xhigh`，不默认使用 `max/ultra`。

服务器双缓冲组 A/B/C 继续作为逻辑 lease；实际运行根由用户在唯一命令中提供绝对路径，
basename 不受 `NDP_copy01/02/03` 限制。启用 variable-root profile 时不核验服务器现有
RTL/Makefile/filelist/TB/Git/README/全树身份，真实编译不兼容由 compile 自然失败；
因此回传只作版本未绑定诊断，不计正式 E4/E5。

### 6.1 当前执行线（硬件假设覆盖后的交接）

| 双缓冲组 | 执行线 | Codex 任务 | 当前首要工作 |
|---|---|---|---|
| A / 用户运行时根 | RequantizeUint8 | `019fa2bf-95cd-7502-82c8-6a48cf12d648` | Conv53 tail signature binding 已完成：53 unique multiplier payload、9 physical profiles；保持合同只读，等待 Conv 按实例消费 |
| A / 用户运行时根 | QuantizeLinear / exact tail | `019fa2c0-572b-7f21-ac5a-96e773dde534` | node0074 capability audit 完成：无 exact binary32 DIV entry，REC→MUL 被同 scale 反例否决；Quantize canonical owner section 已写入但 final consumer endpoint 全 null |
| 独立用户运行时根 | QLinearAdd | `019fa2c0-b647-7a91-93bf-d21a173487e3` | v5-v7隔离；唯一v8 progress-canon已通过最终ZIP current-rule自检，待服务器运行 |
| 独立用户运行时根 | Conv/SA | `019fa2c1-17df-7122-bcbd-a727aaf173f5` | v7确认read-data→Buffer5/D write区间卡死；v7-v9隔离，唯一v10 canonical通过新门待运行；stem accumulate local E2保持 |
| C / 用户运行时根 | DequantizeLinear | `019fa2bf-f9a5-7a73-ada3-b2b910721de3` | canonical shared endpoint 的 Dequant producer section 已完成；storage/base/offset/coverage 已冻结，shared allocator/visibility/lifetime 与 consumer sections 仍开 |
| C / 用户运行时根 | 人工 JSON | `019fa241-0250-7fa3-b2de-1c8951df5aa5` | corrected-v3 fd2 自然结束但仅 256/1024B coverage；native stride 256→1024 为首分歧，所有包继续冻结 |
| LOCAL_ONLY | MaxPool | `019fa366-be0a-7db2-82ff-558fbd3bce68` | 仅复用 Git 原始 JSON；不改 JSON、不复测、不消费历史物化资产，等待整网首分歧或新原始 return |
| C / 用户运行时根 | QLinearGlobalAveragePool | `019fa366-cb1f-7ae2-880c-f527be0680cd` | v4-v6隔离；唯一v7 finalaudit已通过最终ZIP current-rule自检，待服务器运行；GAP→Dequant producer endpoint完成 |
| LOCAL_ONLY | Flatten/View | `019fa366-d218-7122-839c-0b52d83faf13` | canonical 三个 owner section 已齐，producer/View projection READY；exact division、Quantize consumer endpoint 与 shared allocator/lifetime 仍阻塞 integrated E2 |
| LOCAL_ONLY | 独立 RTL 审计 | `019fa490-cfb5-7211-b911-2c59b812c74a` | C0 独立复核与 DataC 勘误已完成；保持只读，不参与 C1 物化 |

既有算子族任务保留各自上下文并切换到纯配置正确性优先策略；MaxPool、GAP、Flatten
独立任务在本轮新增后写回本表。所有执行线均未取得 `SERVER_RUNNING` lease；本轮只允许
本地生成、验证和 config-bound simulator，不得检查服务器文件或名称。算子任务不得修改
plan/公共规则，只向主线提交结构化增量建议。

## 7. 当前记录入口

- 旧测试修复任务分族证据交接：
  `20260727_test_repair_to_family_threads_handoff.md`（Dequant/Requant/SiLU/GAP 与公共
  基础设施历史边界；第 0 节已同步 Dequant 三方闭环后的 1/78 状态）
- Dequant E4：`20260727_dequant_node0077_full_v6_e4_pass.md`
- Dequant E5：`20260727_dequant_node0077_full_v6_e5_pass.md`
- Dequant config-bound 三方闭环：
  `20260727_dequant_node0077_config_bound_three_party_closure.md`
- Dequant node0072 config-only local E2：
  `20260727_dequant_node0072_config_only_e2.md`、
  `20260727_dequant_node0072_mainline_adjudication.md`（新增本地 baseline/E2；
  不增加正式 1/78 计数；node0073 integrated binding pending）
- Requant direct signal：`20260727_requant_guardonly_directsig_v1_return_analysis.md`
- Requant SFU readiness：`20260727_requant_guardonly_sfu_ready_v1_return_analysis.md`
- Requant SFU numeric：
  `20260727_requant_guardonly_sfu_numeric_v1_return_analysis.md`
- 原生 SiLU control：
  `20260727_decode_silu_control_stock_v1_return_analysis.md`
- Requant SFU event-edge 包：
  `20260727_requant_guardonly_sfu_eventedge_stock_v1_package.md`
- Requant variable-root v2 包：
  `20260727_requant_guardonly_sfu_eventedge_runtime_root_v2_package.md`
- Human MAC corrected-v3 包：
  `20260727_human_mac_corrected_v3_package_release.md`
- Human MAC variable-root v2 包：
  `20260727_human_mac_runtime_root_v2_package_release.md`
- Human MAC corrected-v3 fd2 正式回传与主线裁决：
  `20260727_human_mac_v3_fd2_formal_return_analysis.md`、
  `20260727_human_mac_v3_fd2_mainline_adjudication.md`（自然完成但正式 D 仅 1/4
  coverage；native materializer stride overwrite；无 package release）
- ndp-sim ResNet50 复用审计与重规划：
  `20260727_ndpsim_resnet50_reuse_audit_and_replan.md`
- 复用优先、算子免复测、整网失败再回查：
  `20260728_reuse_first_no_operator_retest_mainline_policy.md`（25/25 非 Conv 节点已有
  复用路径；其中旧 serialized SA 能力假设已被 2026-07-28 C0 DataC 证据取代；整网
  assembly 尚未生成）
- P0-A exact UINT8 quant-tail capability matrix：
  `20260727_exact_uint8_quant_tail_capability_matrix.md`（12 cells；
  `NO_UNCONDITIONAL_PURE_CONFIG_PROVEN`；mutable plan receipt 已与 12 项硬语义身份分层）
- Exact UINT8 quant-tail 26-vs-25 config-only discriminator：
  `20260727_exact_uint8_quant_tail_rounding_config_only_discriminator.md`、
  `20260727_exact_uint8_quant_tail_rounding_mainline_adjudication.md`
  （两阶段 singleton=26、fused negative control=25；非 baseline；node0074 exact
  division 2-vs-1 仍阻塞）
- Requant P1-B quant-tail evidence input：
  `20260727_requant_p1b_quant_tail_evidence_input.md`（54/54；33 zp0 与 16 even/5 odd
  nonzero-zp 的共享 blocker 映射；8/8）
- Requant config-only bypass adjudication：
  `20260727_requant_config_only_bypass_adjudication.md`（三组 baseline=0；zp0/
  AverageRequant 首断点 three-PE topology，nonzero 首断点 signed ingress）
- P0-B INT8 SA dot-product 共因裁决：
  `20260727_int8_sa_dot_product_common_cause_adjudication.md`（carry 重复左移 +
  signed17 位宽不足；production 需兼容/修正 RTL）
- P0-B compatible RTL/minimal repair acceptance：
  `20260727_int8_sa_rtl_repair_acceptance.md`（三模型逐 occurrence oracle；
  `LOCAL_BIT_EXACT_PROOF_PASS_RTL_IDENTITY_PENDING`）
- Conv serialized pure-config mainline authorization：
  `20260727_conv_serialized_config_baseline_mainline_authorization.md`（node0004 accumulate；
  历史授权已被 C0 DataC/psum 反例撤销，只作负面历史）
- Conv node0004 serialized local E2 与主线裁决：
  `20260727_conv_node0004_serialized_one_product_local_e2.md`、
  `20260727_conv_node0004_serialized_mainline_adjudication.md`（历史 accumulate-only
  结论已撤权且被 C0 推翻，不计 E2/baseline，只作负面历史）
- Conv 配置绕行前 RTL/入口双重审计授权：
  `20260728_conv_rtl_audit_before_config_bypass_mainline_authorization.md`（C0 两份独立报告
  未经主线同时验收前，`NEW_CONV_BYPASS_GENERATION_ALLOWED=false`；首个完整 Conv
  固定 node0004 accumulate+requant）
- node0004 历史本地资产不可信覆盖裁决：
  `20260728_node0004_untrusted_fresh_rebuild_mainline_override.md`（撤销历史 accumulate
  local E2/baseline 计数；C0 后无论 normal/alternative 或 serialized 路径均从 JSON
  开始全新重建，并在本地测试包处停止）
- Conv C0 主审与独立复核：
  `20260728_conv_sa_c0_local_rtl_and_alternative_entry_audit.md`、
  `20260728_c0_independent_rtl_audit.md`（确认 DataC/psum 清零、carry 二次左移、
  signed17/断 cout；撤回 SA 内 serialized-psum fallback）
- Conv C0 主线裁决与 fresh composite C1 授权：
  `20260728_conv_c0_mainline_adjudication_and_composite_c1_authorization.md`
  （只授权 node0004 SA-product→INT32 scratch→GA-tree 本地配置研发；完整 local E2 前
  禁止封包）
- Conv node0004 fresh composite C1 predesign：
  `20260728_conv_node0004_composite_c1_predesign.md`（fresh W3 accumulate 0 mismatch；
  128 OC8 tile/五波容量可行；物理 SA scalar-product materializer/terminal 首阻塞）
- node0004 exact-tail raw signed max0 审计：
  `20260728_node0004_exact_uint8_tail_max0_config_audit.md`（全域数学/W3 等价，但活动
  opcode 无 signed INT32 max；tail target/package fail-closed）
- Pure-config correctness-first parallel mainline policy：
  `20260727_config_only_correctness_first_parallel_mainline_policy.md`（功能 RTL 全冻结；
  所有绕行强制记录原因、等价范围、物化机制、代价和声明边界）
- GAP INT32 sum-stage config-only local E2：
  `20260727_gap_sum_config_only_local_e2_v1.md`、
  `20260727_gap_sum_config_only_local_e2_mainline_adjudication.md`（六级 sum tree
  本地闭合）；完整节点与测试包见
  `20260729_gap_node0071_complete_local_e2_package_ready.md`
- MaxPool node0002 历史 local E2、fresh-v3 与活动 RTL 裁决：
  `20260727_maxpool_node0002_config_only_e2.md`、
  `20260727_maxpool_node0002_mainline_adjudication.md`（历史记录，物化正证据已撤出）、
  `20260728_maxpool_int8_max_active_rtl_mainline_adjudication.md`（numeric unsigned-max
  局部通过；pipeline0 ready 缺 INT8 分支）、
  `20260728_maxpool_node0002_original_json_fresh_v3_package.md`（仅 Git 原 JSON+
  空 cache 双构建，两-tile `PACKAGE_READY_NOT_RUN`）
- QLinearAdd P1-A 复合后端预设计：
  `20260727_qlinearadd_p1a_composite_backend_predesign.md`（17/17 内容验收）、
  `20260727_qlinearadd_predesign_standalone_cli_fix.md`（CLI 3/3；P0-A dependency 已绑定；
  materialization 禁止）、
  `20260727_qlinearadd_rule_dependency_receipt_refresh.md`（QLinearAdd+shared tail 规则
  current-match；3/3）、
  `20260727_qlinearadd_mutable_plan_warning_test_fix.md`（mutable plan 漂移非阻塞、
  active rule 漂移 fail-closed；5/5）、
  `20260727_qlinearadd_stage0_config_only_materialization.md`（17/17、51 physical
  stages、1.06GB scratch；只到 SUM_F32）
- Flatten/View node0073 zero-copy：
  `20260727_flatten_node0073_zero_copy_physical_view.md`（metadata-only；32,768
  元素地址映射闭合；endpoint binding pending）
- 本轮 Flatten/QAdd/Requant 主线裁决：
  `20260727_flatten_qadd_requant_parallel_mainline_adjudication.md`
- 历史总入口：`.agents/history/plan_pre_active_compaction_20260724.md`
- 以上任务记录均位于 `.agents/task_records/`；未列出的旧过程不再从活动计划派生。
