# 已归档：ResNet50 INT8 旧执行计划（2026-07-22 原生复现路线之前）

最后更新：2026-07-22（补录Conv v19、NJ MaxPool和DeepSeek dg1三组真实服务器证据；DeepSeek已依据新拉取的上游原生仓库建立四片Ring4后继dg3并通过本地Round 1/2，尚待服务器run1；另按用户明确缩减范围生成了不做数值/回读/双轮审计的独立诊断包dg4smoke，只用于确认服务器能否以四片完整Ring4启动并自然退出，不替代dg3或形成G6/G8证据；本对话已把v19停滞闭环到“SA权重输入启用双缓冲但物理buffer3没有任何生产者”，并发现独立的INT8有符号/无符号端口角色反接；所有分支均未新增自然完成的真实服务器证据，G6/G8仍为false）

本文件是新对话的唯一动态执行入口。稳定路线图见 `.agents/agent.md`，历史结论与旧 revision 见 `.agents/history.md`；两份`.agents/rules/`文档是由活动实现、原始入口、consumer/RTL和实证提炼的检查清单，不是独立事实源。使用其中的服务器制品或算子约束前必须与当前实现/证据核对，冲突时及时修正规则，不能为满足旧文字增加校验或修改正确制品。

> v14 已作为诊断包上传并启动 run1，但 preflight 在进入编译/仿真前失败。v15～v17均未上服务器，现已撤权并清理生成制品，不得上传或执行。v18、v19都完成了本地Round 1/2，但真实run1均在全部preload后的首个accumulate stage停滞；v19已经证明修正后的29行配置被服务器实际加载、首波279条gexec与冻结execplan完全一致，仍未产生首个stage完成或readback。NJ MaxPool诊断运行和DeepSeek dg1也在`Start_Comp`之后未产生首个完成；其中只有dg1已定位到确定的启动拓扑生成错误，不能据此把v19/NJ自动归为同一根因。v18/v19/dg1/NJ既有运行身份均不得继续run2或冒充通过证据；DeepSeek只有全新dg3获得run1执行资格，且本地Round 1/2不等于服务器自然完成。目标服务器没有Git，完整性只使用ZIP sidecar、SHA-256、包内manifest和必要的活动入口/`DIR_HOME` provenance。

## 1. 已确认决策

1. 在 `ndp-sim-ref/model_execplan` 原生实现中增加一个可选、默认关闭的 `server` profile。
2. 通用入口 `python main.py input.json` 的 DeepSeek 行为、CLI 和默认输出保持不变；server 行为只能由显式 profile 参数进入。
3. server profile 允许原生工具重新生成 bitstream，但新结果必须建立全新 freeze ID，完成独立 encoder 双跑、parsed evidence、config-bound NDP preflight 后才可冻结和出包。
4. 新结果不得继续称为原 v10r5、已撤权 v11/v12 或中间 v13 数值身份；v14/v18/v19只保留为已执行的历史失败身份。后续诊断若改变配置、bitstream、调度、runner或证据合同，必须建立新revision，当前没有服务器候选。
5. v10r5 只保留为旧闭环对照，不作为新 server package 的冻结 bitstream 来源。
6. v14 显式、内容寻址地复用当前 28-slice 物理地址计划，避免同时改变地址布局和 bitstream 生成链；通用 AddressPlanner 接管放到后续独立 revision。

## 2. 当前目标与最近冻结身份（v19已撤权）

- 唯一硬件目标：`node-0004 / hwop-0004-00~01`，`1×1`、stride 1、`[16,64,56,56] -> [16,64,56,56]`。
- 最近一次 typed request：`artifacts/w5/hwop-0004-00/v19/execplan_request.json`，SHA-256=`105f2bc78556f7ae8a33cd2c20bb3b6e63a4acc40e1138ba90a125b12a577e06`；它只用于复现和分析v19，不再授权服务器执行。
- 当前本地参考仓恢复点：`ndp-sim-ref@d4ffc32c9b29a858d83e13706cd837c5549521a4`、`NDPFuncModel@a1d975ee2d6d9200b8df0deea3e2ffc13ce0d05e`，已写入`repos.lock.json`且只作后续开发恢复点；v19已冻结candidate仍按其原始`056b1c3...`/`cb262bb...`provenance验收，不因本地提交改名或重建。
- v19 accumulate JSON SHA-256=`f26a3346859601055abc9cb88dd0b7c3650e5fcc4fae6d1f85d2562aba0ad8ed`；official mapper commit=`056b1c3c08b24e098636615d9001e8a974beb09f`，mapping key=`2702bd9d31f9efc0`，29行×128-bit规范化逻辑SHA-256=`7d85938215a1d5a5622c38938b5adb64b982c631170604a4ba8285fb5397b255`。
- v19原生candidate位于`v19/encoder_candidate_native_02`：ID=`d5f6af19413919a72d761f99b61d35afdee5278e172a363f28055d937dd37898`，manifest SHA-256=`5146329288431fb970b26e35b70a93c2955515753430026327f36d76fe37589f`，validation SHA-256=`7ddd85d4b3afa9ce08385d588031ff9881fb1a79e7982a753d97a1db9dcc0764`，9条record独立A/B一致。
- v19 config-bound preflight SHA-256=`98febe58038352eefff14b2c88c19e332cdf3fdcf1531a16e91137c5ab0debbc`，Golden/NDP P/D mismatch=0。
- v19 freeze ID=`71686cf225194fbe6f9a0db73e7adf515a02ce252598ac58f6e5090793470b27`，manifest SHA-256=`6da4381275cf1a0e724451eea66e0035fab3e53e13b259af80eb875e77fe3f26`，512个声明文件。
- v19 package manifest SHA-256=`5d118970d4831074da8c8dfee57abdadb48d6bc402bf4aea93864b5dcffef636`；12个runtime stage、314行execplan、28 Bank、434 preload、168 readback和9个bitstream binding均由权威`--check`通过。
- v19不是v14/v18的同一硬件身份；schema 0.3不变性报告SHA-256=`08a6457ee3c8f8f0fa179feb06f81f3df22b6009ea6be771571efcdd303ad1de`只证明264个数值payload/runtime文件保持不变，并显式列出配置、bitstream、execplan和身份文件变化。
- v19 runner SHA-256=`1ae95b832c4273513c152ae453164346563fb2064c15c23255da44b5a7d9d8ee`；ZIP=`artifacts/w5/hwop-0004-00/v19/server_overlay.zip`，2,989,053字节、289个entry、0 HDL，SHA-256=`0874e8eeb8495ca46e3ddda54e1273c05e5c9a10b78c468e4584ba33398f06b2`。
- 下一次在完成定向诊断并决定建立新revision后，overlay输出目录和交付文件名必须显式携带版本号，例如`server_overlay_v20/`、`server_overlay_v20.zip`和`server_overlay_v20.zip.sha256`；runner/README继续使用`RUN_SERVER_V20.sh`/`README_SERVER_V20.txt`。当前不生成该包；v19既有文件名与SHA保持不变，不为改名原地重打包。
- v19 Round 1报告SHA-256=`164a13a7b8fda7dd0e09799e9d3d4e441ec407658a8280a8db516ef48f5df6b8`，20个行为用例全部PASS；Round 2报告SHA-256=`eec85fbd1cc2a5fe98e57a028108c1dac73b8f52545f26607c562670f4683dc2`，从最终ZIP和sidecar全新解包复算PASS。两轮绑定同一最终ZIP SHA。
- v14～v19撤权原因、历史ZIP/runner SHA和服务器失败证据只在`.agents/history.md`追溯；不得把历史路径当作当前可执行输入。

## 3. 目标架构与职责边界

### 3.1 原生 `model_execplan` 负责

- typed request 解析和严格校验；
- 显式 server profile contract 解析；
- config patch 与配置绑定；
- 两次彼此独立的 bitstream/encoder 生成；
- 128-bit 原始/规范化、64-bit packed、parsed evidence 和 placement evidence；
- 提供原生 server completion helper：在普通 `InstructionGenerator` 产物的每个 `Start_Comp` 后按同 mask 插入 opcode `0b110` barrier；默认 profile 不调用；
- 输出 self-contained candidate；独立 validator 重读 exact-set、A/B、parsed、mapping、placement、cache 与全部 SHA，全部 fail closed。

### 3.2 根仓库负责

- ONNX/Golden/lowering/物理输入 staging；
- 将 2 个 ResNet 语义算子展开为 3 个 accumulate wave 与 9 个 fixed-observer runtime stage；该项目特有展开不进入通用 DeepSeek parser；
- config-bound NDP preflight 与 P/D bit-exact 证据；
- 审核并批准新的 freeze ID；
- 调用原生 `InstructionGenerator`、writer、Bank exporter 与 server barrier helper，生成 SCA/SCA_D、Bank_data、4 KiB 报告和只读 freeze-bound package；
- NDP_copy runner/overlay、服务器返回数据逆变换和三方比较；
- 最终 ZIP 双轮独立审计及服务器证据归档。

### 3.3 禁止形成的旁路

- 不新建第三套 execplan 编码器或平行 bitstream 生成器；
- 不让根仓生成器重新解释、修补或默默替换原生 bitstream；
- 不允许 package 阶段重新生成 encoder 或修改 freeze 内容；
- 不允许从旧目录、旧 parsed evidence 或旧 freeze 隐式 fallback；
- 不允许 server profile 通过默认路径、环境变量或固定输出目录影响 DeepSeek 默认流程。

## 4. 原生 server profile 接口

默认调用必须保持：

```text
python main.py input.json
```

server profile 现行显式调用：

```text
python main.py execplan_request.json --profile server \
  --server-action freeze-candidate \
  --server-contract server_profile_request.json \
  --output-dir <new-empty-dir>

```

边界审计确认当前 typed request 只有 2 个语义算子，而服务器运行必须进行 ResNet 特有的 2→12 wave/shard/observer 展开。把该展开硬编码进通用 `main.py` 会污染 DeepSeek 行为，因此原生 CLI 只负责通用 candidate；package 继续由现有根仓入口生成，但指令编码、writer、Bank exporter 和 barrier 全部直接复用原生 API，不存在第三套编码器。接口说明见 `ndp-sim-ref/model_execplan/SERVER_PROFILE.md`。

`server_profile_request.json` 必须是内容寻址、schema-versioned、无隐式默认的合同，至少绑定：

- node/operator/stage 身份和顺序；
- runtime stage 与 semantic operator 的映射；
- config patch 角色、源 SHA 和目标绑定；
- payload、readback、observer 和比较策略；
- 显式 28-slice address plan 及其 SHA；
- transport 最大 burst、4 KiB 页边界策略；
- completion policy（server 为 barrier，default 为 none）；
- 输入 typed request SHA、原生仓库 commit 和输出 schema 版本。

## 5. 当前执行阶段

v19真实run1完成434/434 preload并进入首个accumulate，fixed observer在`0/5 pending=1`停滞约7202秒后由phase watchdog终止。补充gexec与v19首波279条展开指令逐条一致，且v18→v19的56处预期配置差异均已到达硬件。现已由JSON、正式mapping/parsed bitstream和RTL固定连线共同确认：SA `inport1`在index4后必然从buffer2切到buffer3，但v19只有`B→READ_STREAM1→buffer2`，`READ_STREAM2`整段为空且buffer3未启用neighbor，故切换后等待永远不会到达的数据；这是能解释停滞的确定配置生成错误。另有INT8 ALU仅把DataA解释为signed而v19把UINT8 activation接到inport0/DataA的独立数值错误。v19永久撤权并禁止run2；当前没有可运行服务器候选，不生成下一测试包，先修正生成期物理生产者闭合与端口角色合同并完成本地验证。G6/G8保持false。

## 6. DeepSeek 默认行为兼容门

兼容性不是“能运行”即可，至少要求：

- 原命令不增加必填参数，退出码不变；
- 默认输出根和固定目录语义不变；
- operator 顺序、bitstream 生成命令和既有 fail-open/fail-closed 行为不被 server profile 暗改；
- 输出路径集合、文本 ABI、逐文件 SHA 与冻结基线一致；
- server 新模块没有被默认路径导入后产生副作用；
- 原生现有默认路径回归通过；若仓库提供真实DeepSeek fixture，再对其命令、目录集合和逐文件SHA做附加回归。

真实DeepSeek算子能力由用户确认原工具可用。本轮发布门不要求凭空补造fixture，只要求server profile默认关闭、默认路径不被改写且现有原生回归通过；不得把这一边界表述成“已重新完成DeepSeek全量实算回归”。

## 7. 4 KiB AXI 条件风险处理

当前标记：`conditional_risk / trigger_confirmed_for_v14_package`。

- 已确认：AXI4 burst 不得跨越 4 KiB 边界；历史 v9 的确出现过跨页传输并停止。
- 已确认：v14 的 433 个语义运输对象中有 169 个真实触发，264 个未触发；`axi4_4kb_report.json` 可从最终 SCA/SCA_D 独立重算一致。DeepSeek 能正常运行不矛盾，因为其地址、长度、对齐和 TB 调用序列不同。
- 当前实现按“风险存在”处理，但只拆分真实跨页 burst；不跨页对象不得被无条件改写。
- 每次 candidate/package 必须输出机器可读报告，列出对象、原始地址/长度、页内剩余、拆分片段、前后 SHA/语义长度和验证结果。
- 候选数为 0 时报告 `not_triggered`，保留原传输并记录审计结论；一旦出现候选立即给出确切对象和触发原因。
- 后续证据若证明当前链路从约束上不可能跨页，应删除不必要的运行时分段，只保留静态断言与 `not_triggered` 报告，并同步规则和历史。

## 8. 测试门与停止条件

### 必须通过的本地测试

1. 原生默认CLI与仓库现有DeepSeek回归；真实fixture仅在存在时执行。
2. typed transport、config patch、packing 与路径安全测试。
3. server contract schema 正负样本。
4. encoder A/B 独立性、确定性和故意漂移失败测试。
5. barrier：默认 none、server 每个 `Start_Comp` 后同 mask `0b110`。
6. 4 KiB：零候选、恰好到边界、真实跨页、多段和语义长度守恒。
7. freeze candidate/approved freeze/package 生命周期和禁止 package 重生成测试。
8. 根仓 config-bound preflight、package、overlay、runner 真实 Bash 行为与 ZIP 独立审计测试。
9. 服务器完成后 P/staged-D 三方 bit-exact 测试。

### 强制停止条件

- 需要修改 RTL/testbench 或打包任何 `.v/.sv`；
- 找不到或无法验证 typed request、server contract、address plan、freeze 或任一输入 SHA；
- DeepSeek 默认路径出现非预期命令、目录或字节变化；
- A/B encoder、parsed evidence、config-bound preflight 或 P/D 任一不一致；
- package 阶段尝试重生成或从 freeze 外 fallback；
- 4 KiB 报告与真实运输对象不一致；
- 任一定向测试、两轮 ZIP 审计、runner Bash 语法或服务器能力预检失败；
- 当前工作树出现无法安全保留的重叠用户修改。

## 9. 当前阻塞、已知问题与下一步

### 9.1 v14服务器首断点

- v14服务器`run1`止于preflight，未进入compile/sim。已知reason为`server_filelist_member_outside_root`，detail为活动RTL filelist物理解析到`/home/liuyk/Documents/Trassic2.0_RTL/code/NDP_rtl/filelists/NDP_Top_phy_filelist.f`，不在`/home/panqs/ndp/NDP_copy01`下。
- 该门属于v14新增校验导致的启动阻断。v15必须删除“物理路径必须位于服务器根内”和“外部include树同构/数量精确”这类非必要硬门；只保留入口文件可读、包内固定文件身份、Make/TB能力、no-archive/runner/readback合同等真正影响本包运行的门。
- run2保持未执行；v14不得原地修补。

### 9.2 v15历史已闭合问题

1. 正式runner不得从环境继承策略常量；`DIR_HOME`和`SERVER_RUN_ID`是唯一允许外部输入。外部include数量不再作为启动硬门，只记录provenance。
2. Python模板中的CR文件名判断必须避免控制字符先展开再被LF归一化，并用真实带CR路径的Bash样本验证。
3. 正式`SERVER_RUN_ID`只允许`run1`和`run2`；`run3`等必须在其他处理前失败，独立审计不能只查错误字符串存在。
4. v12/v13从未实测的旧package/overlay/ZIP/selfcheck已在v15接替和终审通过后精确清理，共10个目标、1,204个文件、279,594,366字节；两版candidate、preflight、freeze和server-profile输入均保留。

### 9.3 v15历史生成与验收边界

- runner/审计/说明变化必须使用新revision并重跑package、overlay、ZIP、Round 1和Round 2，不得原地改v14。
- 若服务器失败只涉及环境或runner能力，v15可只读复用v14数值freeze；若改变config、bitstream、地址、stage语义或原生candidate内容，必须建立新的A/B candidate、config-bound preflight和freeze。
- v15的服务器source检查为“三个逻辑入口可读 + 实际路径/大小/SHA provenance”。逻辑filelist可解析到服务器根外或symlink目标外；runner不自建HDL/filelist解析器，实际缺失source/include或接口不匹配由VCS/Make自然报错并归档。
- v15正式run1自然完成后才执行run2；两轮逐region稳定后，唯一数值入口仍为`tools/compare_conv_hardware_region_dump.py`，并要求完整physical byte-level及三组三方比较。
- 当前门状态：`node-0004`范围G5=true；G6=false、G8=false；整网与其他算子族的G5仍未闭合。

## 10. v15～v19历史收敛与当前状态

### 10.1 已完成的收敛结果

- runner中的递归filelist/source/include解析、根内物理前缀、外部include数量/树同构、TB源码字符串和`make -n`文本硬门已删除；独立ZIP审计明确禁止这些旧片段回归。
- capability policy、runner、返回验收和Round 2已统一为0.8最小入口策略；三个入口允许symlink和根外目标，只记录非阻断provenance。
- candidate生成时写内容寻址validation sidecar；preflight/freeze只重验报告、manifest和当前exact-set/SHA，Git dirty降为provenance。v14历史资产不回填sidecar、不修改。
- package完整验证只在overlay消费边界运行一次并写入overlay manifest；Round 1只消费其摘要。Round 1的1037 sink用路径dry-run验证，避免Windows创建symlink的低价值耗时，正式runner仍在Linux服务器创建真实`/dev/null` symlink。
- v14固定SHA复核通过且未修改；所有v15中止overlay均在目标边界核验后清理，最终只保留通过两轮审计的制品。

### 10.2 固定校验层级

1. **candidate 数值生成门**：官方 encoder A/B、parsed/mapping/placement、配置与源码闭包身份只在新 candidate 生成时完整执行一次并落盘报告。
2. **preflight/freeze 边界门**：消费上游报告并复验输入摘要、manifest、实际文件 SHA 和 exact set；不得再次运行完整 candidate 语义验证。
3. **package 消费门**：对批准 freeze 完整验证一次并落盘 package validation report；overlay 和 Round 1 只消费并验证该报告身份。
4. **服务器启动门**：只验证固定包身份、runner/launch 合同、实际命令依赖和三个逻辑入口可读；不自建服务器 HDL/filelist 解析器。
5. **最终交付门**：Round 2 从最终 ZIP 和 sidecar 全新解包，独立复算 entry 安全、exact set、SHA、LF、0 HDL、关键合同和 4 KiB 报告。
6. **provenance 层**：服务器物理路径、入口 SHA、外部 include 信息、Git commit/dirty 只记录，不作为服务器启动或无关工作树状态的阻断条件。

### 10.3 runner 保留、降级与删除

必须保留：

- `SERVER_RUN_ID` 在任何目录创建/清理前只允许 `run1|run2`；
- runner 自身、launch manifest、argv、SCA/SCA_D、execplan、Bank_data、stage/readback 合同身份；
- 实际使用的 `bash/make/vcs/timeout/sha256sum/zip` 等命令能力；
- Makefile、testbench、顶层 filelist 三个逻辑入口可读；
- no-archive 入口、墙钟/进程/输出体积上限、统一失败归档、仿真结束后的 stage/observer/readback exact-set 验证。

降为 provenance：

- 三个活动入口的逻辑路径、`readlink -f` 物理路径、大小和 SHA；
- 服务器工具版本与实际编译/仿真命令；
- 外部 include 和服务器源码来源信息，能够取得时记录，不能取得时不得覆盖真实 compile/sim 结果。

删除：

- 物理路径必须位于 `${server_root}`、source/include 不得经 symlink；
- 自定义递归 filelist/source/include 闭包与服务器源码树 exact-set/SHA；
- 外部 vendor include 数量、路径和目录树同构硬门；
- TB 源码字符串数量、日志路径数量和 `make -n` 展开文本逐字符串匹配；
- `expected_external_include_count` 环境变量及其所有校验；
- 对正在追加的半行作失败判断。watchdog只读取LF完整快照；完整行的明确重复/乱序/越界仍可立即失败，进程退出后必须对完整console再做最终严格复验。

### 10.4 工具链精简

- native candidate validator 生成内容寻址 validation report；preflight 只绑定报告身份和实际文件，freeze 只绑定 preflight/candidate manifest 与复制 exact set。
- 删除 freeze 对整个原生仓库 `dirty=false` 的硬拒绝；保留相关源码闭包 SHA，Git commit/dirty 仅作 provenance。相关源码发生变化必须改变闭包 SHA 和后续 candidate ID。
- package 验证只在 package 生成/消费边界运行一次；`build_server_overlay()` 接收该报告，Round 1 不再调用同一全量 validator。
- Round 1报告绑定最终runner、overlay manifest、ZIP和一次package权威检查摘要；builder/测试脚本不另建一套服务器运行身份。后续只运行本次变化波及的定向用例，最终revision生成时再汇总Round 1。
- Round 2 每个最终 ZIP 必须独立执行一次，不能缓存或复用 Round 1 的文件摘要。
- candidate旁已有同名validation sidecar时，原生生成器必须在创建输出目录或启动A/B encoder前拒绝，避免昂贵晚失败和残留候选目录；报告写入点仍保留第二次冲突检查作为竞态保护。

### 10.5 已知问题定向修复与测试

- 根外 filelist/symlink：Round 1构造根外物理解析fixture；Windows无symlink权限时仅在probe PATH中使用`readlink` shim，正式runner不使用shim。真实缺失source由Make/VCS返回并归档。
- 无 Git：Round 1 使用不含 Git 的 PATH，runner 和 README 不得调用 Git。
- run ID：`run3` 必须在任何结果目录变化前失败；`run1/run2` 产生隔离返回名。
- 路径/ZIP解析：只在相关代码发生变化时定向验证绝对路径、`..`、重复entry和非普通对象；不再把真实TAB/LF/CR文件名作为每版发布硬门。
- 环境污染：设置旧 `expected_external_include_count` 等变量不得改变 runner 行为。
- 历史 v14 测试只核对固定 SHA、撤权状态和已知失败，不要求 v14 runner 具备 v15 行为；新行为由临时 runner fixture 或 v15 artifact 验证。
- 4 KiB 继续作为 package 生成期语义门；服务器启动不重复重算。169 个已触发对象在 v15 中必须与 v14 语义分段一致。

### 10.6 v15 数值身份与允许变化

- v15 只读消费 v14 freeze，不调用 candidate、preflight 或 freeze 生成器；freeze ID、freeze manifest、bitstream 和所有数值 payload 保持不变。
- 必须逐项比较 bitstream、execplan、Bank_data、stage、mask、barrier、readback region 和 4 KiB 语义报告。SCA 中仅 revision/install 路径可规范化后比较。
- 只允许 revision、runner、launch identity、overlay manifest、README、自检报告和 ZIP/sidecar 身份变化。
- 若出现 config 字段、bitstream、地址、transport 分段、stage/barrier 或数值 payload 非预期差异，立即停止 v15 复用并重新完成 A/B、config-bound preflight 和新 freeze。

### 10.7 执行与验收顺序

1. [完成] 修复policy/runner/audit/test不一致，定向overlay测试零失败。
2. [完成] 精简candidate/preflight/freeze/package重复验证和全仓dirty硬门，生命周期与漂移负例通过。
3. [完成] 原生server profile/typed transport、根仓相关测试、Python/Bash语法通过。
4. [完成] 从v14只读freeze生成v15 package，机器可读数值不变性报告通过。
5. [完成] 生成v15 overlay/ZIP/sidecar；Round 1和Round 2绑定同一ZIP SHA并通过。
6. [完成] 发布前终审：v14/v15实际package分别通过当前`--check`；最终ZIP再次全新解包独立审计通过；完整28-bank生成回归、其余execplan/freeze/preflight/overlay及原生测试无现行失败；确认runner外部命令均进入能力门且服务器无Git依赖。
7. [历史撤销] 原计划执行`RUN_SERVER_V15.sh`；v15已撤权，禁止执行。

任一步失败都停在最早可证实断点，不生成或发布后续制品。

### 10.8 v15历史终审结论与撤权（2026-07-20～2026-07-21）

- 修复原生candidate生成器的旧validation sidecar晚失败：现在在任何输出目录写入和A/B encoder启动前拒绝，新增回归证明失败后candidate目录不存在。该文件不参与v15只读freeze→package→overlay链，v15 package、runner、ZIP和两轮报告字节均未改变；未来candidate必须使用刷新后的原生source-tree身份。
- 原生`server_profile/typed_transport` 8项通过；完整28-bank package端到端关键用例1项通过（约509秒）；其余execplan 9项、freeze 7项有效用例、preflight 7项、overlay 9项现行用例全部通过。15项跳过均对应已明确删除或退役的历史制品，不是当前能力缺口。
- v14参考package与v15候选package均由当前权威`--check`从实际文件重新验证通过；manifest SHA同为`0608c74065cad019119aa73de33a1b5ef137210b86d977f53020130a53da6c78`，数值不变性报告保持有效。
- 最终ZIP再次从sidecar校验并全新解包独立复算通过：SHA=`d81ed87db41d5c64c8d0a44209c4d2cc08baaa6f24962da2f00b37e7dad1fc27`、2,986,153字节、289个entry、0 HDL；28 Bank、314行execplan、12 stage、5次observer、434 preload、168 readback、9个bitstream binding全部一致。
- 2026-07-21独立复审推翻“本地没有已知问题”的口径：runner身份验证晚于旧证据清理；run1/run2未比较服务器入口provenance；数值不变性工具只比较manifest；当前回归未直接绑定v15及身份门顺序；readback watchdog重复全文扫描；删除TB源码扫描后缺少未知日志运行时保护。数值package和ZIP实文件复验仍通过，但v15不得上传或运行。

### 10.9 v16修复与验收顺序

1. [完成] runner自身份检查移到任何清理/结果目录创建前；损坏runner行为负例证明旧证据逐字节不变。
2. [完成] 统一规则，删除`mktemp/xargs`、TB源码路径扫描和`make -n`文本门的现行残留要求。
3. [完成] run1/run2稳定性增加Makefile、TB、顶层filelist逻辑/物理路径、大小、SHA和关键执行环境一致性比较，物理路径与VCS版本差异负例通过。
4. [完成] 数值不变性工具在比较manifest前分别权威验证参考包与候选包实际exact-set/SHA，参考包实文件损坏负例通过。
5. [完成] 回归绑定当前v16产物并验证runner身份门早于清理；历史v14/v15只作固定身份与撤权回归。
6. [完成] watchdog轮询只做路径/类型/大小，文件首次达到精确大小时完整验证一次，退出后统一终检；未知日志和1 GiB运行总量保护行为负例通过，未恢复TB源码字符串门。
7. [完成] 从同一v14 freeze生成v16 package/overlay/ZIP；bitstream、execplan、Bank_data、stage/mask/barrier、SCA/SCA_D、readback和4 KiB身份保持不变。
8. [完成] v16 Round 1与Round 2由不同入口执行并绑定ZIP SHA-256=`3d4fe99866aa00a0b85caf208fc57db61793d709e7b3a033697f8fb6baefd031`；权威package复验、当前产物回归和发布前本地终审通过。
9. [历史撤销] v16发布后复审发现新的本地缺口，禁止执行`RUN_SERVER_V16.sh`。

### 10.10 v17修复与验收顺序（历史完成后撤权）

1. [完成] 把统一失败函数和ERR trap移到身份验证之后、完整命令门和任何清理之前；为缺失证据原语保留stderr-only且旧证据不变的唯一例外，并增加直接runner故障注入。
2. [完成] 对合并后的静态install执行实际exact-set；清除Make控制环境变量；记录`DIR_HOME`及vendor解析provenance并纳入run1/run2一致性。
3. [完成] 不变性报告执行manifest真实byte比较；overlay ZIP/sidecar/Round 1及Round 2报告在昂贵工作前拒绝冲突，不覆盖旧证据。
4. [完成] 从同一v14批准freeze生成v17 package/overlay/ZIP，数值身份保持不变，并完成Round 1、Round 2和完整node-0004关键回归。
5. [历史撤销] 最终总览发现包内README未完整表述新增运行合同；v17不原地改写，改由v18重新生成。

### 10.11 v18最终生成与服务器结果

1. [完成] 包内README与runner统一表述：无Git依赖；自身份、失败处理、完整命令门、清理的顺序；静态install exact-set；Make环境隔离；`DIR_HOME`/vendor非阻断provenance。
2. [完成] 从v14批准freeze重新生成v18 package/overlay/ZIP；数值manifest原始字节和309个声明文件身份保持不变。
3. [完成] Round 1的20个行为用例和Round 2全新目录独立解包审计均PASS并绑定ZIP SHA-256=`2e669527ccf426c6f940f9f706b41406eb93257f9b722d4af927503e656c25ad`。
4. [失败/撤权] v18在服务器完成preload后进入首个accumulate stage，fixed observer长期为`0/5`；手工终止返回不是自然完成，run2禁止执行。失败ZIP及补充诊断SHA已写入派生规则与历史台账，G6/G8保持false。

### 10.12 v18运行期间完成的非数值工具修复

1. [完成] 后续runner在完整命令门发现任一缺失命令时只向stderr报错并退出，不再调用会清理canonical旧证据的失败归档函数；该改动减少分支和外部命令，不增加服务器校验。
2. [完成] Golden/NDP/RTL比较在本来就读取freeze physical P/D字节时同时核对manifest size/SHA，不调用511文件全量`_verify_freeze()`，不增加第二次文件读取。
3. [完成] 原有`compare_conv_hardware_region_dump.py`增加可选run1/run2原始ZIP输入，只做安全entry、唯一根和run ID绑定，并把ZIP SHA写入比较报告；保留原已解压目录入口，不另建工具链。
4. [口径收敛] 不增加`runtime_identity.json`服务器重复哈希门，不把TAB/LF/CR畸形服务器文件名设为每版硬门，Round 2不再逐项维护第二份外部命令列表；规则旧表明确降为历史记录。
5. [完成] v18原始返回已到达并完成首断点分析；以上runner模板修复已由v19继承，且没有掩盖或绕过新的数值配置身份。

### 10.13 v18 bias停滞修复与v19生成结果

1. [完成] 由真实返回确认：preload通过、首个Start已发生、observer为`0/5`且无自然退出；排除runner/barrier/readback/4 KiB作为最早断点。
2. [完成/边界] 由本地RTL与正式encoder语义确认：`SA_PE_Outbuffer`每个初始组需要指针0～3四次bias握手；v18 `buffer4.buffer_life_time=1`只产生一次消费，stream3又只按Kblock触发两个事务。这是必须修复的硬件语义JSON错误，不是JSON语法错误；但v19修复已实际到达硬件后仍停滞，故不能再把它表述为已证实的唯一或充分根因。
3. [完成] 修改原生`tools/generate_conv_1x1_real.py`：建立独立`Kblock→H→Qblock` bias tile分支；stream3每tile装载一行32 B、地址只随Kblock以32 B变化，H/Qblock stride为0；GROUP2引用同一tile事件；buffer4 JSON lifetime改为4。
4. [完成] 扩展`validate_first_conv_sa_contract`与定向负例，机器证明bias事务数、两个地址、每tile四次消费、terminal/full/last引用链以及64 B边界；没有增加服务器运行时校验。
5. [完成] official mapper/encoder在全新目录独立双跑，placement、128/64-bit、parsed/mapping语义和关键字段全部闭合；正式accumulate变为29行×128-bit的新逻辑身份。
6. [完成] 刷新语义合同和typed request，config-bound Golden/NDP P/D mismatch=0；旧config/bitstream fallback由SHA与合同门拒绝。
7. [完成] 建立v19 candidate、preflight、freeze ID和package；v14/v18 freeze仅作历史负例，v19不冒充原数值身份。
8. [完成] 生成v19 overlay/ZIP并执行Round 1及最终ZIP独立Round 2；289个entry、0 HDL、无Git依赖，未恢复source扫描、`make -n`或额外运行时哈希层。
9. [服务器失败] v19 run1已执行并由phase watchdog以`phase_watchdog_stalled`终止；禁止执行run2，也不得用本地Round 1/2替代服务器自然完成或三方比较。
10. [完成] 按v19活动实现同步仓库说明和两份派生规则，修正A/B角色、LC/PE/stream、bias节拍、server profile及服务器入口能力判定口径；本次未改任何v19包内或身份绑定文件，ZIP身份保持不变。v19已绑定的语义JSON中`evidence_boundaries`仍有旧候选“7/10 LC-PE”以及“typed qparam transport未证明”的自由文本；这些字段不被生成器或runner消费，当前实文件/正式candidate为16个DRAM LC、2个LC-PE、33条连接，typed qparam transport也已由当前项目链闭合。不得原地改写v19；下一次确需建立新数值revision时，语义合同刷新步骤必须同步更新这些说明元数据。

### 10.13.1 v19真实run1与gexec定界（2026-07-21）

1. 主返回`sim_results_v19_run1.zip`为86,784字节，SHA-256=`89bd374c3f357e32857d90bfe511b628fdbe3d2166d09b789165722d95b8501b`；`failure_report.json`记录exit 10、phase=`postrun`、reason=`phase_watchdog_stalled`。preload约25分15秒，首个compute observer停滞约2小时，总计约2小时25分。
2. 运行完成434/434 preload，打印`Exec_Length=314`并发出首波28个slice的`Start_Comp`；随后observer保持`0/5 pending=1`，没有stage完成、自然退出或readback。Makefile、TB和顶层filelist的路径/SHA与v18一致，因此入口变化不是已观察到的差异。
3. 补充证据`v19_run1_gexec_actual_1784631030.zip`为2,845字节，SHA-256=`b9b58afabb55f7166417aead35acdb6550ed6d992fec9310f185c6bf09c6be7c`。其中gexec共有279条有效命令：28条Clock Enable、28条Load Config、195条WREG、28条Start Compute；按slice mask展开本地v19 `instructions_explained.txt`后与服务器记录逐条完全一致。
4. v18与v19首波gexec同为279条，仅有56处预期差异：28条Load Config由28×128-bit变为29×128-bit，28条READ_STREAM3寄存器17写入变为v19 bias tile配置。该证据确认v19新配置已被实际消费，不能再归因为旧bitstream混装、命令漏发或global executor未启动。
5. 当前最窄断点是首波`Start_Comp`之后、任一slice完成之前。RTL完成链为`WR_Data_Channel`最终写数据被接受→`slice_cmpt_finish`→`Slice_Execution_Manager`离开CMPT；现有返回只能说明这条链至少有一个slice未到达终点，尚不能在READ_STREAM3、buffer4、SA输入/outbuffer、buffer5或WR_MSE0之间进一步唯一定位。
6. v19只是证明bias修复“已送达但不足以解除停滞”；它不推翻该静态不变量，也不证明其他配置字段必错。下一步应先设计最小、非HDL、定向内部链证据，再决定是否建立新revision。服务器可能被其他算子占用，当前不生成v20、不安排run2，也不升级G6/G8。
7. [本地暂停前自检] 在不重写制品的前提下重新执行v19 package权威`--check`并通过（28 Bank、314行、12 stage）；`tests.test_conv_sa_hardware_contract + tests.test_ndp_server_overlay`共29项，14项PASS、15项历史制品skip；最终ZIP/sidecar独立审计通过（289 entry、0 HDL、SHA-256仍为`0874e8ee...98f06b2`）；补充gexec再次得到expected=279、actual=279、exact_match=true。上述结论只证明本地制品完整和首波命令一致，不恢复v19执行资格。

### 10.14 学长3×3 Conv隔离分支审计

1. [完成] 保持`.agents/conv_full(2).json/.txt`原件不变；当前正式encoder在44条连接上稳定复现placement失败，首批确定错误包括无效`LC_PE.LC8`来源、GROUP2/GROUP3交叉引用、错误输出producer、outport标签冲突和共享LC fanout不可放置。
2. [完成] 受控`conv_full.json`的13处结构修复在正式encoder A/B两次运行中得到46条连接、constraint cost 0和完全一致输出；128-bit码流为35行，LF规范化逻辑SHA-256=`2f60aac3ea7ee501956d9bad9e6b3a66bd1943edd4c330e53fad05b6b06e21af`。该结果只证明结构可编码，不批准运行语义。
3. [完成/身份边界] 正式模型图确认原件的`64→64、3×3、stride1、pad1、56×56`几何同时匹配`node-0005/node-0009/node-0013`；原件本身不绑定tensor/qparams且缺少per-channel requant，所以不能唯一认定为其中一个完整QLinearConv。本分支显式选择最早的`node-0005/hwop-0005-00~01`，从正式实例表取得全部tensor、参数SHA和qparams；因此“本分支候选是ResNet50 node-0005”已闭合，但“学长原件唯一就是node-0005”仍不成立。
4. [完成] 没有把35行结构修复码流直接升级成硬件包，而是保留其诊断身份，并为正式`node-0005`新增current ABI生成路径：A使用显式pad1 halo物理布局`[storage_sample,HaloH,Cquartet,HaloW,C4]`，SA A/B/bias/P单事务均为32 B，`CONFIG=11101110`，HIGH-4环、batch16三波accumulate及8个per-channel requant shard沿用已审查合同。正式accumulate配置有42条连接、constraint cost 0、33行×128-bit，逻辑SHA-256=`20408a575ba5ebbc69726e479ec272236b5d8840396cc72eab01493a04f9251b`。
5. [完成] typed request SHA-256=`cc8def589770cb3315e19cdb79663083e85f9ed88b5d828c213f592a269d35ee`并携带12个配置制品；原生9-record candidate ID=`60e73f9eec3fd4303126f2c73e490af61a0cc9847159ff091b21271e4ffee969`，manifest SHA-256=`7d7843f10661a9f6b52d9cdef1b312d25120e7e91cde47409ddb561396d1637a`，A/B全部一致。config-bound preflight SHA-256=`5bbe44bc50ad9ef1904919ae42974995bd9b01f876c5d7bc1e6db2da2ca5121b`，Golden/NDP P/D均0 mismatch；freeze ID=`8725221c3986c413b9c827dc9a3fbe96f1e3bb3de637a25c9453f1b381d62189`并绑定1份accumulate和8份requant码流。
6. [完成测试包/待服务器] hardware package权威检查通过：12个runtime stage、314行execplan、28份Bank_data、462个preload、168段readback及9个bitstream binding。最终zero-HDL ZIP=`artifacts/w5/n5v2_overlay.zip`，3,734,347字节、345个entry、SHA-256=`b134b872a114d2d52f4c37f9ce7246f37fbf17321eb78bfe3794a065d9b87fcc`；Round 1报告SHA-256=`b837583c27172adb2467ccb8e94fdcd870517c78ca77bbe3f6ed31c1b5e6b3bc`，20个行为用例PASS；Round 2报告SHA-256=`e1b7b0f22b7add734daafb5e622fff4cab017ad6957b06a235e78299c6127257`，从最终ZIP全新解包复算PASS。尚未执行真实target，G6/G8=false；该包不是v20，也不恢复node-0004 v19资格。

### 10.15 非Conv首例 MaxPool 隔离分支

1. [完成] 正式W3图盘点为`QuantizeLinear=2、QLinearConv=53、MaxPool=1、QLinearAdd=17、QLinearGlobalAveragePool=1、Flatten=1、QLinearMatMul=1、DequantizeLinear=2`。选择唯一的`node-0002/hwop-0002-00` MaxPool：它有精确`C=16,H=W=112,K=3,S=2,P=1`上游模板、无qparams/requant、W3输入输出和W4可逆A/D layout均已存在，是最短的真实计算算子闭环。
2. [完成] 从同一正式模板生成三轮配置，活动slice数为`28/28/8`；正式encoder每轮A/B输出确定一致。配置绑定路径实际消费三份JSON、region-backed physical image和`GeneralPEA`，对W3的3,211,264个UINT8输出及28个slice physical D均为0 mismatch。配置与报告均以确定性UTF-8/LF实际字节绑定；预检状态为`config_bound_functional_passed_three_way_not_comparable`，报告SHA-256=`5c66a0f64c69c4d136f52d33fb3aeb239d03c57bdb35f66c5ddd1a7003c4ffba`，该实例范围G5=true。
3. [完成/边界] 原生`CGRA_SIM` MaxPool以其历史zero-border输入合同执行后与W3为0 mismatch，但它只是额外软件参考，不是current 28-slice target。活动`GA_PE_Float_CSA.v`经Icarus对65,536组输入、262,144个byte lane穷举为无符号max；这只关闭算术kernel语义，不能替代整算子调度、stream/buffer、写回或readback执行。
4. [完成测试包/待服务器] 在全新`artifacts/w5/native_json_maxpool/v2/hardware_execplan_package`生成最小native-JSON硬件包：精确复制上游配置SHA=`a0091f3f...0cb1`，绑定正式双encoder、W3样本0的channel `0:16/16:32`两份真实tile、slice0/1、2个runtime stage、5行execplan、11个preload、4段readback、2份Bank_data及4 KiB分段；权威`--check`通过。该包是先验证真实算子控制链的两tile范围，不是batch16/28-slice三轮全量包。
5. [完成交付审计] 生成`artifacts/maxpool_server_v1.zip`与sidecar，大小640,593字节、31个文件、0 HDL、SHA-256=`a4b3e31cdc3615988eba12ee77c5f1904cbba3c5b66e1a3d39158407603265b8`；Round 1 runner/完整install行为自检和Round 2最终ZIP全新解包独立复算均PASS。服务器合并后执行`SERVER_RUN_ID=run1 bash RUN_SERVER_MAXPOOL1.sh`；run1本地验收通过后才执行同一包run2。
6. [完成回传入口/边界] 新增`tools/analyze_native_json_maxpool_return.py`，安全解包单次服务器ZIP、复核whole-tree/config/runtime身份、自然完成/observer/preload证据，重组4段readback并逐byte比较两份W3 golden；合成成功回传测试0 mismatch。尚未启动真实target、未产生target输出，因此Golden↔target和NDP↔target仍不可比较，G6/G8=false。
7. [完成] MaxPool使用独立bridge，未改写Conv冻结依赖的共享`physical_image_probe.py`（SHA-256=`92799f763f3b1fc9cb7597a42cabc08505b4223d1e21a341eba9a12d52399c7d`）。Conv v19的本地P/D与package复核仍有效，但真实run1已经证明首波配置被消费后停滞，v19永久撤权且不得run2；MaxPool包不复用或修改该Conv身份。

### 10.16 v19、NJ与DeepSeek dg1三组真实运行的共享定界（2026-07-22）

#### 10.16.1 共同可证实边界

1. 三组运行都已越过配置文件存在性、SCA解析和`Start_Comp`派发，随后停在fixed observer的首个完成之前；Bank Frame Monitor创建日志只是`Start_Comp`之后开始等待计算完成的共同可见边界，不是三个算子具有同一内部死锁原因的证据。
2. v19完成434/434 preload，服务器首波279条gexec与本地冻结execplan逐条相等，并以28-bit全mask同时启动七个HIGH-4组；最早未闭合点仍是首波`Start_Comp`之后、任一slice completion之前。原始返回`sim_results_v19_run1.zip` SHA-256=`89bd374c3f357e32857d90bfe511b628fdbe3d2166d09b789165722d95b8501b`，补充实际gexec ZIP SHA-256=`b9b58afabb55f7166417aead35acdb6550ed6d992fec9310f185c6bf09c6be7c`。
3. NJ MaxPool诊断运行的进度证据为preload `6/7`后进入`compute_observer 0/1 pending=1`；`gexec2slice.log`只有4条有效记录，对应slice0/1时钟、slice0 `Load_Config`和slice0 `Start_Comp`，没有完成记录。该MaxPool配置不启用neighbor/N2N通信，因此单slice启动本身不能由DeepSeek Ring4缺少协作slice的错误解释；在取得不可变原始返回ZIP前，该证据只用于断点定界，不授予完整preload、自然退出或数值结论。
4. DeepSeek dg1原始返回`sim_results_dg1_run1.zip` SHA-256=`e65156491099b637e737b33bbb97a8380f9dedf7516102dc5c6d9ece14398065`；5/5 preload均完成AXI写入、读回和逐项匹配，随后打印`Reg Started`及`INFO: slice start`，最终在`compute_observer 0/1 pending=1`停滞7200秒并由phase watchdog归档。未观察到UVM error/fatal，因此JSON/bitstream文件未下发、preload传输失败或Start命令未到达都不是dg1最早断点。

#### 10.16.2 DeepSeek dg1已确认错误及职责分工

1. 上游`prefill_gemm_ring_4slice.json`是四slice协作算子：`neighbor_stream0`、buffer neighbor和SA neighbor入口已启用，ring步数为4。当前`resnet50_pipeline/native_json_ring_gemm_package.py`却为两份运行分别设置`used_slices=1<<slice_id`，生成全局Clock mask `0x3`，先单独`Start_Comp slice0`并等待同mask barrier，只有slice0完成后才会派发slice1。
2. 这不是原生算子JSON或bitstream配置本身被证伪，而是项目包装层把其通信域改成了不可能完成的单slice串行拓扑。slice0已经开始运行，但其他Ring4成员没有同时启动且部分时钟未使能，因而等待邻居数据而无法到达completion；barrier只暴露错误，不是阻止slice0计算的根因。
3. 因此已经确认项目的“JSON/原生bitstream→服务器实际消费execplan/control”适配层存在语义生成缺陷。后续必须在生成期检查：local算子可单slice启动，HIGH-4算子的Start mask必须是完整物理四slice组的并集，LOW-28算子必须覆盖完整28-slice通信域；该检查是轻量本地语义约束，不增加服务器运行时重型校验。
4. dg1保持只读撤权；后继实现没有原地修改`native_json_ring_gemm_package.py`或dg1，而是使用独立v2生成模块和全新dg3 overlay。当前事实见10.16.5。

#### 10.16.3 对v19和NJ的约束与本对话下一步

1. dg1的确定错误不能直接解释v19：v19首波已经使用完整28-bit mask，同时启动全部七个HIGH-4组，且服务器实际gexec与冻结计划精确相等。后续v19定位必须集中在已送达配置的运行语义，例如每slice配置寄存器/地址绑定、逻辑到物理HIGH-4映射、stream/buffer/SA/outbuffer/writeback事件链，不得再重复追查命令丢失、旧bitstream混装或缺少Ring4成员。
2. dg1的确定错误也不能直接解释NJ：NJ使用无neighbor依赖的MaxPool配置，单slice最小运行在拓扑上允许。NJ需要另查GA MaxPool输入/输出地址、buffer与transout配置及写回完成链；没有完整返回ZIP时不扩大结论。
3. 三组证据共同揭示的是现有本地门缺少“配置通信域与生成Start mask/物理分组一致”的语义检查，而不是服务器需要更多通用运行时校验。补充该本地约束后仍必须分别定位v19与NJ，不能用一个共享monitor终点替代算子特定因果证据。
4. 本对话当前只继续v19：先静态重建首stage从JSON字段、parsed bitstream、WREG、物理HIGH-4组、输入地址到完成链的逐项映射，寻找即使279条命令准确送达仍会导致所有slice无法完成的最早不一致；在找到可证实差异前不生成v20、不修改RTL/TB、不延长服务器仿真。

#### 10.16.4 v19已确认的物理生产者缺失与独立数值端口错误（2026-07-22）

1. v19配置只声明4个stream：`A/read`、`B/read`、`D/write`、`C/read`。原生mapper的固定target映射为`A→READ_STREAM0`、`B→READ_STREAM1`、`B'→READ_STREAM2`、`C→READ_STREAM3`、`D→WRITE_STREAM0`；v19正式`mapping_review.json`也只列出READ0、READ1、READ3和WRITE0，没有任何节点占用READ2。正式`parsed_bitstream.txt`的`se_rd_mse`段进一步显示READ_STREAM2对应的10条配置全部为0，排除了“JSON没写但码流另行补齐”的可能。
2. 目标RTL固定把buffer0/1作为READ_STREAM0的成对缓冲；buffer2、buffer3、buffer4则分别只接READ_STREAM1、READ_STREAM2、READ_STREAM3。Array到SA的固定分组又是`buffer[2*g] / buffer[2*g+1] → inport g的source0/source1`，所以SA `inport1`的两路物理源就是buffer2和buffer3。
3. v19同时配置`special_array.inport1.pingpong_en=1`、`pingpong_last_index=4`。RTL `SA_Inport_Connect`初始选择source0，并在所选输入出现last且last_index达到4、下游接受时无条件翻转到source1。buffer2由B/READ_STREAM1填充；buffer3既没有B'/READ_STREAM2生产者，`nbr_enable`又为0，也不可能由neighbor链补充。因此第一次翻转后SA必然等待空buffer3，不能完成首个stage。这一因果链与服务器“Start已到达但所有slice均无completion”的现象一致，已从候选风险升级为v19确定错误。
4. 现有`validate_first_conv_sa_contract`只检查了4个stream的单事务字节数、buffer本地/neighbor标志和SA端口开关，没有检查“每个启用的SA ping-pong source是否存在实际物理生产者”，因此错误配置反而被当作通过。后继工具修复应增加一条轻量生成期语义约束：按目标RTL固定stream→buffer→SA source映射证明生产者闭合；它不应被实现为服务器运行时扫描或额外重型预检。
5. 解除上述停滞仍不足以批准后继包。活动INT8 ALU的DataA逐byte取符号并转绝对值，DataB逐byte按无符号值进入乘法；`SA_PE_ALU`又固定把SA inport0接DataA、inport1接DataB。v19却定义`A/stream0/inport0=UINT8 activation`、`B/stream1/inport1=INT8 weight`，使两个算术角色同时反接。它主要导致数值错误而不是握手死锁，但属于同一revision必须修复的硬错误。当前`NDPFuncModel/component/SpecialPEA.py`第47～54行又恰好硬编码了与v19相同的`uint8 A * int8 B`假设，所以既有config-bound P/D通过只能证明软件adapter自洽，不能旁证真实INT8 SA端口语义；该模型与相应测试必须随新合同一起更正。`.agents/rules/算子配置规则.md`中“历史A=weight/B=activation已被物理合同否定”的旧结论已于本轮按RTL事实撤销，后续不得从旧提交或旧候选恢复。
6. 最小死锁诊断改动可以是为本地权重组补`B'→READ_STREAM2`并让typed `B'`与B共址，原生encoder、execplan和WREG链原本都支持该固定映射；但直接采用它会保留第5项数值反接，所以不能单独生成v20。正式修复必须同时重建`weight signed→inport0/DataA`、`activation unsigned→inport1/DataB`的stream/buffer/ring调度，证明两路ping-pong生产者、地址/lane和HIGH-4通信域闭合，再建立全新config、bitstream双跑、parsed evidence、config-bound preflight、freeze ID和版本化服务器包。当前不修改RTL/TB、不原地改写v19；该Conv后继工作与10.16.5的DeepSeek dg3身份隔离。

#### 10.16.5 DeepSeek Ring4 dg3后继包（2026-07-22）

1. [原生来源闭合] 只保留重新完整克隆的`upstream_recheck_20260722/ndp-sim`，HEAD=`ec12424516ae0304228dd2321d4e604fe225e04e`；`git fsck`通过。目标配置为仓库原有`jsons/prefill_gemm_ring_4slice.json`，原始SHA-256=`6a2ca9f2edd2e9c7b8ebbb558a84dd23c8e583781f8a8ac01c213b78c6737e91`，未改写。配置明确为M64、每片NB32、完整N128、K16、Ring4；仓库硬件trace `address_remapping/golden/ring_gemm/M64NB32KA4KB16`记录cycle 0启动、cycle 819完成并写回256个128-bit字且无X。
2. [严格复用原方法] 在隔离worktree上使用上游未修改的`run_all_slices.py`生成slice0～3四份配置；由于Windows子进程默认GBK不能打印`✓`，只设置`PYTHONIOENCODING=utf-8/PYTHONUTF8=1`后复现。两个独立输出根A/B的generated JSON、mapping review、parsed bitstream和128-bit bitstream逐项一致，且四片最终码流逻辑SHA彼此不同；因此正式包必须四次单片`Load_Config`，不能把一份配置广播或回退到dg1串行单片启动。
3. [执行与数值边界] v2 hardware package位于`artifacts/w5/deepseek_ring_gemm_control/v2/hardware_execplan_package`，manifest SHA-256=`81488d01d0ca79edd61f92bd1e4a9efd51d69db3b0992904682d7b8f06db6bbc`。execplan解码为`Clock 0xF → Load 0x1/0x2/0x4/0x8 → Start 0xF → Barrier 0xF`，共4行128-bit；17个preload、4个readback、4个bitstream binding和4份Bank_data均由权威`--check`闭合。上游Git没有保存该trace的输入张量/模型权重，所以不声称逐位重放原硬件数值；控制测试把A/B/B'输入清零，并在四片D区先写`0xA5`非零哨兵，只有四片都实际写回全零才能通过，未执行/未写回不能以初始零值伪通过。
4. [dg2撤权] 初版dg2的Round 1通过，但旧独立审计器只认识单一`config_sha256`记录格式，Round 2拒绝新的`base JSON + per-slice generated JSON + official encoder`身份链。dg2因此按规则永久撤权，不上传、不执行、不原地补报告。独立审计器已增加窄范围Ring4分支：交叉核对原始JSON身份、四个生成配置摘要、A/B official encoder与最终安装码流的全字段身份、slice ID、四个互异single-slice mask和四个互异逻辑码流。
5. [最终dg3交付] 最终zero-HDL ZIP为`artifacts/w5/dg/dg3_overlay.zip`，50,367字节、34个ZIP entry（33个manifest文件加ZIP根）、SHA-256=`8be435b7d9b7e9b46208c0d5041995d30136bff71d0fbe13a39ba556823535c2`；sidecar同目录。Round 1报告`artifacts/w5/dg/dg3_selfcheck_round1.json` SHA-256=`16d8bbbebdc008ec2094de9b70d396aaf7500d4104d31698044496015642d616`，runner/完整install行为用例通过；Round 2报告`artifacts/w5/dg/dg3_selfcheck_round2.json` SHA-256=`7556cffa2274a17f7ee5cc9f28412489756d92f212b92b392066a33e06bfcb58`，从最终ZIP全新解包、重算集合/大小/SHA/文本ABI/runner/四片binding并通过。`tests.test_native_json_ring_gemm_v2 + tests.test_ndp_server_overlay`为14项PASS、15项退役历史制品skip、0 failure。
6. [待服务器] dg3只获得run1执行资格，入口为`SERVER_RUN_ID=run1 bash RUN_SERVER_DG3.sh`；必须先回传并通过`tools/analyze_native_json_ring_gemm_return.py`对whole-tree身份、17次preload、自然完成、4个D区及哨兵覆盖结果的本地验收，才允许执行同一不可变包run2。当前没有dg3真实target输出，不能把上游历史trace或本地Round 1/2当作本次服务器完成，G6/G8仍为false。

#### 10.16.6 DeepSeek Ring4 dg4smoke精简诊断包（2026-07-22）

1. [一次性诊断范围] 用户明确接受“配置和bitstream保持原生、本地只补最小服务器适配”，并放弃正确输入、golden、输出哨兵、readback、barrier、run1/run2及后续数值校验。本包只回答服务器能否编译、以完整`0xF`通信域启动四片Ring4、越过dg1的单片串行卡点并由活动fixed observer自然退出；任何成功都不能替代dg3数值/写回合同或提升G6/G8。
2. [最小控制链] `server_overlay_dg4smoke`只保留6条64-bit命令，封装成3行128-bit execplan：`Clock 0xF → Load 0x1/0x2/0x4/0x8 → Start 0xF`。SCA只执行9次preload：execplan、四份各自绑定物理slice的原生配置、以及四片共用内容相同的32 KiB零输入；`Repeat_Num=1`，`sca_cfg_D.json`为空对象，不执行输出readback。
3. [来源边界] 四份安装码流继续复用未修改上游`run_all_slices.py`双跑后冻结并LF归一化的v2副本；Clock/Load/Start前缀来自同一v2 execplan并已解码核对为`clock_enable(0xF)`、四次60-word single-slice `load_config`和一次`start_comp(0xF)`。本地适配仅包括零输入、SCA、400 MHz reserved AXI clock TCL、日志sink、no-archive make target、runner和ZIP包装。
4. [交付身份] 目录为`artifacts/w5/dg/server_overlay_dg4smoke`，ZIP为`artifacts/w5/dg/server_overlay_dg4smoke.zip`，共12个文件、8,887字节，SHA-256=`37423f597bc8563f94967228266a629643e0f3e0fff947e603a2492097238ec2`；sidecar同目录。ZIP不含HDL，runner权限为0755；本地只做了源身份、命令解码、路径/ZIP集合、sidecar和文本结构的最低静态检查，没有执行正式Round 1/2，不能称为正式验收包。
5. [运行与回传] 在服务器`NDP_copy01`目录安装overlay后运行`SMOKE_TIMEOUT=6h bash RUN_SERVER_DG4SMOKE.sh`。runner总会尽力生成`run/sim_results_dg4smoke.zip`，其中只保留退出状态、SCA/execplan和最多4 MiB的console/compile/sim/gexec日志尾部；不生成数值结论。后续仅根据自然退出和日志断点判断是否越过当前卡点。

## 11. 后续扩展顺序

首例真实 P/D 三方闭环通过后，依次推进：同类 `1×1` shape family → `3×3/7×7` Conv → 其他算子族 → typed 网络 execplan 与地址生命周期 → 残差块/stage/head/整网三方闭环。通用 AddressPlanner 接管必须作为独立 revision，不能与首个原生 server profile 同时改变。
