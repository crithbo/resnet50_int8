# 归档：生成前必读资料精简前的服务器测试包规则

原标题：`NDP 原生服务器消费文件夹生成与验收规则`。本文件保留 2026-07-24 精简前的
全部版本历史、实例身份和规则原文，只用于审计，不再作为当前必读或发布入口。

> 2026-07-24 最新增量（优先于后文历史描述）：
> 1. `SCA_D` 的每个条目必须精确含 `base_addr/path/length`；`length` 单位为
>    128-bit word。缺失该字段时 TB 会静默跳过该矩阵，包结构通过也不得发布。
> 2. 单命令脚本必须使用 wall-clock timeout，并在 `EXIT/HUP/INT/TERM` 上尽力生成
>    allowlist-only 部分回传；卡死或被终止不能只留下服务器目录。
> 3. 结果门必须核对两条 SCA 回显、preload/dump 数量、自然完成标记以及
>    `Cannot open`、`skip matrix readback`、softmax 默认回退；正式 readback 还要检查
>    LF-only、精确字节数和 golden。
> 4. 当前 GAP 可交付包为 `gap_int32_mac_stock_rtl_onecmd_v5`，旧 v4 因缺
>    `length` 已作废。并行的轻量控制包为 `decode_max_fp32_stockrtl_onecmd_v2`；
>    它只验证 DeepSeek FP32 reduction max，不能替代 ResNet INT8 MaxPool。

> 2026-07-24 最新增量（优先于后文历史描述）：
> 1. `SCA_D` 的每个条目必须精确含 `base_addr/path/length`；`length` 单位为
>    128-bit word。缺失该字段时 TB 会静默跳过该矩阵，包结构通过也不得发布。
> 2. 单命令脚本必须使用 wall-clock timeout，并在 `EXIT/HUP/INT/TERM` 上尽力生成
>    allowlist-only 部分回传；卡死或被终止不能只留下服务器目录。
> 3. 结果门必须核对两条 SCA 回显、preload/dump 数量、自然完成标记以及
>    `Cannot open`、`skip matrix readback`、softmax 默认回退；正式 readback 还要检查
>    LF-only、精确字节数和 golden。
> 4. 当前 GAP 可交付包为 `gap_int32_mac_stock_rtl_onecmd_v5`，旧 v4 因缺
>    `length` 已作废。并行的轻量控制包为 `decode_max_fp32_stockrtl_onecmd_v2`；
>    它只验证 DeepSeek FP32 reduction max，不能替代 ResNet INT8 MaxPool。

最后更新：2026-07-24（GAP int32_mac 单命令服务器操作边界）

> 2026-07-24 操作增量（优先于后文旧的“仅消费目录/不默认 runner”描述）：
> 当用户要求简化服务器操作时，简化对象是服务器端人工步骤，不是测试内容。
> 允许包内提供唯一 `PREPARE_AND_RUN.sh`，用户只传一个绝对 NDP_copy 路径；脚本
> 自动完成 fresh namespace 安装、包/路径校验、身份采集、隔离 RUN_DIR 编译运行、
> 显式 SCA/SCA_D 绑定、结果裁决和 allowlist-only 回传。完整语义、golden、动态门
> 和 provenance 不得为“操作简单”而删除。若不需要 Makefile 的 archive target，
> 应直接运行隔离 RUN_DIR 中的 simv，避免制造无分析价值的大型 archive。该模式
> 仍必须关闭 VCD/FSDB，不得携带或安装功能 RTL patch；需要既有 TB observer 时只做
> fail-closed preflight，不得把 observer/RTL 源文件偷带进声明“无 RTL 文件”的包。

适用范围：当前“先原生复现已通过服务器运行的参考算子，再扩展到最简单 ResNet50 算子，最后处理 Conv”的路线。

本规则中的“测试包”仅指服务器将直接消费的原样目录，不默认包含自定义 overlay、runner、ZIP、barrier 或 freeze。用户已明确改为使用最新 `ndp-sim` 当前格式，只要求服务器能够完成测试，不再要求与旧参考算子目录完全一致；允许使用来源 manifest 和最小数据/graph 桥接脚本，但必须记录其来源并禁止接触 `ndp-sim-ref`。

## 1. 权威来源

按以下顺序解决冲突：

1. `C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim` 中 GitHub 原版 README、源码和真实输出；
2. 用户明确允许调用的工作库其他工具、正式 W3/参考数据和本地资料；
3. 用户手动服务器运行返回的原始文件和日志；
4. `jsons` 中用户确认可在服务器运行的参考目录；
5. 本规则、`agent.md`、`plan.md`、历史合同和 ADR。

当前活动 `ndp-sim` 身份为 `ec12424516ae0304228dd2321d4e604fe225e04e`。身份变化后必须先复核 README、相关源码和输出，不能默认为同一生成链。

`C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim-ref` 暂时停用。当前生成和验收不得导入、执行或复制其中任何工具、JSON、配置、数据和产物。

用户已明确：除 `ndp-sim-ref` 外，工作库其他路径均可按任务调用。调用根仓工具、`artifacts/`、`jsons/` 或 `NDP_copy01` 时必须在 manifest 中记录精确路径、大小和 SHA-256，并确认工具没有间接读取 `ndp-sim-ref`。

## 2. 当前交付目标

首个目标 `decode_summac_fp32N_fp32N` 已完成并由用户确认服务器跑通。原 `node0004_accumulate_wave0_graph` 与 `node0002_maxpool_wave0_graph` 都必须原样保留为失败证据。随后 `decode_max_fp32N_fp32N_graph` 使用仓库已经存在的原生 FP32 max JSON、完整原生控制链和零 ping-pong，在服务器 66 cycles 后自然完成；28 个 slice 均产生 1 个 MSE4 写数据，有效最低 32-bit 与本地 D Golden 28/28 一致。这排除了该短 FP32 max 场景中的公共 transout/outbuffer/MSE4 写回死锁，支持把 node-0002 卡点继续收敛到 INT8 专属分支。该轮因命令漏传 `+SCA_CFG_D` 而跳过正式回读，只达到 E3，不是 node-0002 MaxPool 的语义或数值修复。

交付资格包括：

- 完整生成链只依赖活动 `ndp-sim` 及用户允许的本地来源，且不得直接或间接依赖 `ndp-sim-ref`；
- 使用最新工具生成的 `sca_cfg.json`、`sca_cfg_D.json`、`install/execplan.txt`、`install/cfg_pkg` 和输入数据彼此引用完整；
- 不要求旧参考目录的路径集合、文件命名、哈希或结果数值一致；
- 机械装配和最小 bridge 生成的内容有完整来源记录；没有原生失败后残留或来源不明文件；
- 生成命令、输入身份、工具身份、日志和比较结果可追溯。

本地满足这些条件只叫“当前格式目录自洽”。`decode_summac_fp32N_fp32N_graph` 已由用户于 2026-07-22 确认在服务器完整跑通；其准确重跑规则和与原 README/Makefile 的冲突单独记录在 `ndp-sim/README_SERVER_PACKAGE_LOCAL.md`。其他候选在真实服务器运行自然完成之前仍不得称为服务器通过。

`decode_max_fp32N_fp32N` 的原生单图 ID 是 `op10`，完整 Decode Golden 中唯一同类型实例的 `layer_idx` 是 `op25`。当前原生 `run_single_op_decode.py` 不提供重编号参数，因此本候选允许唯一一项机械 bridge：将本轮新生成的 `op25` 目录原样复制为 `op10`，并逐文件验证相对路径、大小和 SHA-256 一致。该 bridge 不改变数值、dtype、packing、JSON、bitstream、地址、execplan 或 SCA。

## 3. 本地来源使用规则

### 3.1 允许

- 枚举文件和目录的相对路径、类型、大小；
- 计算 SHA-256；
- 生成完成后执行只读二进制 diff、文本 diff 或 JSON 结构 diff；
- 在生成前记录固定的运行结果排除清单。
- 使用正式 W3 tensor、形式模型、根仓工具和已生成本地资料；
- 为活动原版 `ndp-sim` 补充其缺少的最小 graph/数据 bridge，但不得修改原版配置语义或吞掉原版错误。

### 3.2 禁止

- 直接或间接读取、导入、执行、复制 `ndp-sim-ref` 中的任何内容；
- 把旧失败包、诊断残留或来源不明文件伪装成本轮原版输出；
- 过滤原版错误、手改 bitstream/execplan/SCA，或用占位文件掩盖缺失；
- 不记录来源就把本地自定义工具输出称为“完全原生”。

除 `ndp-sim-ref` 外的本地内容均可成为显式 source；必须在交付说明中区分原版 `ndp-sim` 产物、bridge 生成输入和正式/参考数据。

## 4. 首个算子的来源门

`decode_summac_fp32N_fp32N` 当前候选来源为：

- `ndp-sim/jsons/decode_summac_fp32N_fp32N.json`；
- `ndp-sim/generate_python_golden/decode_ops.py`；
- `ndp-sim/generate_python_golden/run_single_op_decode.py`；
- `ndp-sim/generate_python_golden/generate_decode_execplan_inputs.py`；
- `ndp-sim/generate_python_golden/assemble_decode_package.py`。

本轮已确认：

1. tensor/golden 由 `decode_ops.py` 固定 `random_seed=0` 产生；
2. 单算子 relayout 生成 op0/op10/op32，候选单图只消费 op0；
3. 此单图不需要 address remapping；
4. 从 `generate_python_golden` 工作目录调用真实 planner 路径为 `..\model_execplan\main.py`；
5. `assemble_decode_package.py` 形成当前根级与 `install/` 层级；伴随 A/D 文件只从本轮原生 op0 输出机械补齐；
6. bitstream 运行依赖 `matplotlib`；本轮只安装在临时运行目录，不进入候选。

任一后续缺口若只能从参考目录取得，立即停止；不得用参考内容填补。

## 5. 原生步骤约束

执行时必须按目标算子相关的原生 README 顺序：

```text
原生数据/golden 生成
  -> 原生 relayout/packing
  -> 原生 address remapping（仅在 README/源码明确适用时）
  -> 原生 model_execplan
  -> 原生输出目录/安装内容
  -> 本地自洽检查
  -> 与参考目录严格比较
```

必须遵守：

- 原版步骤的命令从当前提交的 README 或源码入口取得；bridge 步骤必须来自本轮可审计脚本；
- 使用全新、算子专属的输出目录，禁止混用旧目录；
- 不修改原生 Python、JSON、配置模板或输出 writer；
- 不增加 completion barrier、freeze、overlay、runner、ZIP 或占位文件；允许最小 graph/数据 bridge 和来源/验收 manifest；
- 记录每条命令的工作目录、完整参数、退出码、stdout/stderr 和输入哈希；
- Python 返回 0 不等于成功：日志中的 placement/bitstream 失败、异常被吞掉、关键输出缺失或重复运行才偶然成功，均必须视为失败并记录。

原生 `model_execplan` 只负责图、地址、配置和指令，不负责凭空产生 tensor 数据。缺少 tensor 数据时必须回到原生数据/relayout 链，不能创建无来源的空文件。

## 6. 服务器消费内容

原生 README 已说明的典型消费内容包括：

- `install/execplan.txt`；
- `install/cfg_pkg`；
- `sca_cfg.json`；
- `sca_cfg_D.json` 或算子原生拆分的 `sca_cfg_op*.json`；
- 可选 `Bank_data`；
- 带基地址的算子 JSON、解释文件和原生流程实际生成的其他文件。

该列表不是允许从参考目录手工补齐的模板。目标相对路径集合以最新版原生工具实际输出和服务器 loader 的真实消费要求确定；旧参考目录存在而当前工具不再生成的 `sca_cfg_op*.json`、旧 bitstream 名和 OS 元数据不属于缺失。

## 7. 当前格式自洽合同

生成前记录活动提交、输入数据来源、目标算子和命令。生成后必须检查：

1. `sca_cfg.json`、`sca_cfg_D.json` 及带基地址 JSON 可以解析；
2. `sca_cfg.json` 中每个预加载/配置/执行计划路径均位于候选目录且文件存在；
3. `install/execplan.txt` 非空，`install/cfg_pkg` 包含每个启用算子的当前 bitstream 和 SFU 系数；
4. 每个启用算子的输入矩阵由本轮 golden/relayout 生成并具有当前 manifest 要求的格式；
5. 当前 pipeline 对 bitstream regeneration 失败会继续，因此必须逐 op 检查日志、`parsed_bitstream.txt` 和最终 128-bit bitstream，不能只看 `main.py` 返回 0；
6. 若服务器直接加载 SCA，目录必须包含所有 SCA 引用文件；若服务器加载 `Bank_data`，必须显式使用最新版 `-b`/`-bc` 选项生成并按服务器格式检查；
7. 同一输入从全新目录重复生成时，控制文件和 bitstream 应稳定；结果/dump 内容可以不同或为空。
8. “包内存在 `sca_cfg_D.json`”与“服务器运行时实际消费该文件”是两道独立门。交接命令必须显式绑定 `+SCA_CFG_D=<本包>/sca_cfg_D.json`，不能依赖 testbench 默认派生文件名。

旧参考目录只用于确认同类算子曾在服务器运行和辅助理解文件类别，不再执行 exact-tree 或逐字节门。

## 8. 失败与停止条件

发生以下任一情况立即停止当前候选：

- 缺少原生输入、命令、依赖或数据来源；
- 必须从参考目录提取内容才能继续；
- 原生工具报告失败、输出不完整或存在 fail-open；
- 同一输入从空目录重复生成不稳定；
- 当前 manifest/SCA 引用缺失、路径越界或格式不符合服务器 loader；
- 需要调用 `ndp-sim-ref`、复制旧参考/旧 W5 文件，或用根仓自定义工具替代原版 bitstream、地址、execplan、SCA/装配流程；允许用户已授权且有完整来源 manifest 的最小 graph/数据 bridge；
- 服务器装载、启动、等待或回读步骤在原生资料中不存在且用户尚未提供。

停止后提交第一处差异、命令、日志、输入哈希和候选原因，不能继续补包猜测。

## 9. 服务器人工交接

本地一致性全部通过后，交付给用户的内容只包括：

- 原样生成目录；
- 目录清单和逐文件 SHA-256；
- 原生生成命令与工具/输入身份；
- 与参考目录的零非结果差异报告；
- 明确声明没有从参考目录提取文件。

用户负责把原样目录放入服务器指定位置并执行其已有的装载、启动、等待和回读命令。未经用户提供，不编造服务器命令，也不把自定义 runner 混入目录。对当前 `tb_NDP_Top_new_phy.sv`，已由源码和真实日志确认的两个 plusarg 名称不属于猜测：每次原生包运行必须同时显式传入：

```text
+SCA_CFG=<本轮服务器消费目录>/sca_cfg.json
+SCA_CFG_D=<本轮服务器消费目录>/sca_cfg_D.json
```

`decode_summac_fp32N_fp32N_graph` 的服务器跑通先例以及当前 GAP 交接目录均把两份
SCA 放在消费目录根部；`install/cfg_pkg` 只保存 bitstream，不应再机械嵌套一份 SCA。
两条参数必须指向同一个本轮消费目录。启动后必须先核对日志中的
`Using SCA cfg file:` 和 `Using SCA cfg D file:`；第二条若出现
`sca_cfg_D_softmax.json` 或其他非本轮路径，应立即停止该轮，不等待长时间仿真。

服务器返回后先保存原始文件和日志，再按用户目标决定是否只验证可运行，或继续做结果比较。本轮用户已确认参考算子完整跑通，但未提供服务器原始命令/日志；该事实足以推进最简单 ResNet50 算子阶段，不足以证明数值正确。

## 10. 阶段推进

1. **单原子 `decode_summac_fp32N_fp32N`**：本地当前格式目录已自洽，用户已确认服务器完整跑通。旧参考目录只提供消费层级参考，不执行 exact-tree/逐字节门。
2. **最简单 ResNet50 算子**：`node-0002` MaxPool 单波次候选在更新 testbench 后仍停在“有读返回和写地址请求、无写数据”；旧包冻结。原生 `decode_max_fp32N_fp32N_graph` 对照包已在服务器自然完成并写出数据，证明 FP32 max/公共写回链可运行；它不能替代 node-0002 数值或语义验证。后续应针对 INT8 专属路径建立修复后的 RTL/全新候选，不再用同一旧 JSON 重复封包裁决公共链。
3. **Conv 单阶段例外**：用户已明确授权 `node-0004 accumulate-wave-0`。旧包必须作为失败证据保留；当前只允许从已有 `conv_1x1_real.json` 派生独立零 ping-pong revision，通过 W3/layout bridge 重新生成 wave0 数据，并由活动原版 `ndp-sim` 重新生成控制内容。不得读取旧失败包、旧 v20/freeze/package 来构造新候选，也不得扩展到完整 Conv 或数值通过声明。

任一候选的本地生成成功不能代替服务器通过，参考算子或其他 ResNet50 算子服务器通过也不能直接证明 node-0004 可运行。

## 11. 诊断目录隔离

- `ndp-sim/model_execplan/output/silu_withbaseaddr`：已观察到非结果字节与参考目录不同，未批准。
- `ndp-sim/model_execplan/output/maxpool_node0002`：曾混入参考目录空占位文件，违反来源规则，永久不得上传或复用。

二者只用于解释历史诊断，不得被复制、改名、补齐或打包成候选。

## 12. SCA_D 回读防复发硬门

当前更新后的 `NDP_copy01/tb_NDP_Top_new_phy.sv` 在未收到 `+SCA_CFG_D=%s` 时，会把 `SCA_CFG` 文件名替换为硬编码的 `sca_cfg_D_softmax.json`。`decode_max_fp32N_fp32N` 的 2026-07-23 实测命令遗漏该 plusarg，导致计算自然完成后出现：

```text
Cannot open .../sca_cfg_D_softmax.json
skip matrix readback
```

从现在起执行以下强制门：

1. 上传前确认本包 `sca_cfg_D.json` 可解析、所有 D 路径位于本包且目标父目录可写。
2. 交接说明和实际 argv 必须同时包含完整的 `+SCA_CFG`、`+SCA_CFG_D`；只给前者判为不可运行交接。
3. 仿真开始后先核对两条 `Using SCA cfg ... file` 回显，二者必须是同一 package，D 文件必须精确为本轮声明的回读配置。
4. 完成后扫描 `Cannot open`、`skip matrix readback` 和意外的 `sca_cfg_D_softmax.json`；任一命中都判回读失败。
5. `Simulation completed successfully!`、自然 `$finish` 或内部 MSE4 写数据只能支持 E3；没有正式 readback 文件和独立 Golden 比较不能升级 E4。
6. 禁止复制、改名或链接 `sca_cfg_D.json` 为 `sca_cfg_D_softmax.json` 来绕过参数遗漏；应修正 argv。

已核验案例、ZIP 哈希、日志行和 28/28 内部写数据对照见 `server_returns/decode_max_fp32_simresults_1/ANALYSIS.md`。

## 13. 通用返回验收与停滞观测

服务器返回统一交给 `tools/analyze_native_ndp_server_return.py`，不得针对 GAP 手工数日志
后直接宣布通过。工具从本轮冻结目录的 `sca_cfg.json`、`sca_cfg_D.json` 推导合同；
GAP 还必须传 `contracts/server_return_profiles/gap_hwop0071_sum_v1.json` 做哈希绑定。
正式通过至少要求：SCA/SCA_D 回显正确、preload 与 Exec_Length 正确、自然完成、正式
D 回读数量正确、所有返回 D 与独立 Golden 逐字节一致，且没有 optional observer 的
`STALL`。

返回包至少含 `sim_results/sim.log` 和所有 SCA_D 指向的实际回读文件。为使未完成测试
仍可定位，还应返回 gexec、各 slice/MSE 的 req/rdata/wdata、SEM event 和
`return_observer.log`；超时/外部终止时保存已经落盘的部分证据，不得只返回波形。

本地 `NDP_copy01` 的 optional observer 只读监测 CONFIG/exec/completion、MSE/bank
握手、buffer4/5、SA 两侧 tag/backpressure 及八个常规 GA PE 的
pipeline0/backpressure。它只在显式传
`+RETURN_OBSERVER` 时写低频日志；旧 simv 不含该观测器，必须先重新 compile。GAP
建议同时传 `+RETURN_OBS_SLICE=0 +RETURN_OBS_STALL_CYCLES=4096
+RETURN_OBS_HEARTBEAT_CYCLES=4096`。完整交接与报告解释见
`contracts/native_ndp_server_return_acceptance.md`。

## 14. GAP GA v7 只读诊断 ZIP 例外

第 5、9 节“不默认增加 runner/ZIP”约束适用于发布级原生消费目录。对已经由原生目录
复现、但必须观察 testbench 内部状态的最小诊断，允许一个显式登记的只读 TB-probe
ZIP；它不构成 candidate config、E4/E5 包或功能 RTL 修复。当前唯一允许实例是：

```text
artifacts/operator_config_validation/r5-server-test-packages/
  gap_hwop0071_sum_probe_v7.zip
```

强制身份与安全门：

1. ZIP SHA-256 必须为
   `c4462033fc4d59ad71121639daed70de1185c5f294264bc3847d22b6bc481893`，
   共 120 个 entry、3,280,763B；对应 `.sha256` sidecar 必须精确匹配；
2. 包内不得包含功能 RTL `.v/.sv`，不得由 installer 修改功能 RTL；只允许复制
   `native_return_observer.svh`、在 TB 最后一个 `endmodule` 前加入 include，并修正
   已知不安全的 TB `RUN_TIME` 常量宽度；
3. observer 为只读，使用与 GA 相同的 `clk_sg`，`GA_ACCUM_STATE` 全局上限 512；
   必须记录 `transout_initial/calculate/counter`、outbuffer valid/count/pointer、
   两个 tag/data slot 和实际 A/B/C；
4. `DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0` 必须显式传入；回传生成器必须采用
   allowlist，拒绝 waveform、build tree、nested archive 和超出预算的日志；
5. 上传前必须运行：

```powershell
.venv\Scripts\python.exe tools\validate_gap_probe_test_package.py
```

该命令必须同时验证解包目录、manifest、ZIP exact file set、逐文件哈希、sidecar、
功能 RTL 排除和安全策略。禁止因为已有 ZIP 而跳过复验，也禁止原地覆盖 v7 身份。

服务器解包后只运行包内：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

脚本会拒绝复用已有 install/run/return 路径，捕获运行前后 RTL/filelist/TB 身份，
显式绑定两份 SCA，并在隔离 `run_gap_hwop0071_sum_probe_v7` 中重新 compile/sim。
用户只需原样返回：

```text
gap_hwop0071_sum_probe_v7_return.zip
gap_hwop0071_sum_probe_v7_return.zip.sha256
```

不得返回整个 run 目录，也不得再包一层。回传只能用于裁决 exact GAP 是否观察到：

```text
matched && trans_init>=2 && !calc && !ob_valid &&
input2==outbuffer_data[rd_ptr] && input2!=0
```

即使观察到该条件，也只闭合 `B_GAP_GA_ACCUM_STATE` 的精确动态根因；没有功能 RTL
修复、全新配置身份、正式 D readback 和重复 E5 前，不得放行 GAP candidate。

## 15. 外部信号与部分回传门

规则 ID：`CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001`

长时间服务器仿真必须区分 DUT 自身结束、仿真时间上限、runner timeout 和外部
`SIGHUP/SIGINT/SIGTERM`。VCS 报告 `Received SIGHUP` 只能证明进程被外部终止，
不得直接写成 RTL 自行卡死或 `$fatal`。

单命令 runner 必须通过 `trap` 或等价机制，在 EXIT/HUP/INT/TERM 时尽最大可能收集：

- simulator/compile/run exit status 与收到的 signal；
- 实际 simulator argv；
- `return_observer.log`；
- pre-install/post-install 以及当时可取得的 post-run identity；
- `sim.log` 的受限头尾摘要；
- 已生成的正式 readback 和分析 gate。

部分回传仍必须 allowlist-only。禁止以 `simv`、`simv.daidir`、waveform、整个 run
目录或 nested archive 代替上述证据。若观察器写在 run 目录之外，部分回传必须显式
包含它；否则只能裁决到“最后一个公开日志事件”，不得猜测内部 ready/valid 根因。

2026-07-24 `gap_int32_mac_stock_rtl_onecmd_v4` 的非规范回传
`sim_results(3).zip` 即为反例：39 个矩阵均装载/读回并到达 `slice start`，随后在
约 57.77 ms 的执行窗口后收到外部 SIGHUP；原始 ZIP遗漏 evidence 目录和 observer，
却包含完整 build tree，因此只能分类为
`RETURN_INCOMPLETE_EXTERNAL_SIGHUP_AFTER_EXEC_START`。

## 15. 外部信号与部分回传门

规则 ID：`CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001`

长时间服务器仿真必须区分 DUT 自身结束、仿真时间上限、runner timeout 和外部
`SIGHUP/SIGINT/SIGTERM`。VCS 报告 `Received SIGHUP` 只能证明进程被外部终止，
不得直接写成 RTL 自行卡死或 `$fatal`。

单命令 runner 必须通过 `trap` 或等价机制，在 EXIT/HUP/INT/TERM 时尽最大可能收集：

- simulator/compile/run exit status 与收到的 signal；
- 实际 simulator argv；
- `return_observer.log`；
- pre-install/post-install 以及当时可取得的 post-run identity；
- `sim.log` 的受限头尾摘要；
- 已生成的正式 readback 和分析 gate。

部分回传仍必须 allowlist-only。禁止以 `simv`、`simv.daidir`、waveform、整个 run
目录或 nested archive 代替上述证据。若观察器写在 run 目录之外，部分回传必须显式
包含它；否则只能裁决到“最后一个公开日志事件”，不得猜测内部 ready/valid 根因。

2026-07-24 `gap_int32_mac_stock_rtl_onecmd_v4` 的非规范回传
`sim_results(3).zip` 即为反例：39 个矩阵均装载/读回并到达 `slice start`，随后在
约 57.77 ms 的执行窗口后收到外部 SIGHUP；原始 ZIP遗漏 evidence 目录和 observer，
却包含完整 build tree，因此只能分类为
`RETURN_INCOMPLETE_EXTERNAL_SIGHUP_AFTER_EXEC_START`。
