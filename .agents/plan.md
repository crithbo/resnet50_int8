# ResNet50 INT8 当前执行计划与接手入口

最后更新：2026-07-21（v15～v17均为未授权历史revision；v18真实运行停在首个accumulate stage并已撤权；v19已完成bias调度/生命周期修复、新数值身份、config-bound preflight、package及两轮本地审计，等待服务器run1；G6/G8仍为false）

本文件是新对话的唯一动态执行入口。稳定路线图见 `.agents/agent.md`，历史结论与旧 revision 见 `.agents/history.md`；两份`.agents/rules/`文档是由活动实现、原始入口、consumer/RTL和实证提炼的检查清单，不是独立事实源。使用其中的服务器制品或算子约束前必须与当前实现/证据核对，冲突时及时修正规则，不能为满足旧文字增加校验或修改正确制品。

> v14 已作为诊断包上传并启动 run1，但 preflight 在进入编译/仿真前失败。v15～v17均未上服务器，现已撤权并清理生成制品，不得上传或执行。v18虽通过本地Round 1/2，却在真实run1完成preload后长期停在首个accumulate stage；手工终止返回和本地RTL/encoder反查已确认bias每tile握手不足，v18不得执行run2或原地修改。v19已从原生配置生成器完成全链重建和本地交付审计，是当前唯一允许上传并执行run1的候选；它尚未取得服务器自然完成证据。目标服务器没有Git，完整性只使用ZIP sidecar、SHA-256、包内manifest和必要的活动入口/`DIR_HOME` provenance。

## 1. 已确认决策

1. 在 `ndp-sim-ref/model_execplan` 原生实现中增加一个可选、默认关闭的 `server` profile。
2. 通用入口 `python main.py input.json` 的 DeepSeek 行为、CLI 和默认输出保持不变；server 行为只能由显式 profile 参数进入。
3. server profile 允许原生工具重新生成 bitstream，但新结果必须建立全新 freeze ID，完成独立 encoder 双跑、parsed evidence、config-bound NDP preflight 后才可冻结和出包。
4. 新结果不得继续称为原 v10r5、已撤权 v11/v12 或中间 v13 数值身份；v14/v18只保留为已执行的历史失败身份，v19是全新数值/硬件身份和当前唯一服务器候选。
5. v10r5 只保留为旧闭环对照，不作为新 server package 的冻结 bitstream 来源。
6. v14 显式、内容寻址地复用当前 28-slice 物理地址计划，避免同时改变地址布局和 bitstream 生成链；通用 AddressPlanner 接管放到后续独立 revision。

## 2. 当前目标与冻结身份

- 唯一硬件目标：`node-0004 / hwop-0004-00~01`，`1×1`、stride 1、`[16,64,56,56] -> [16,64,56,56]`。
- 当前 typed request：`artifacts/w5/hwop-0004-00/v19/execplan_request.json`，SHA-256=`105f2bc78556f7ae8a33cd2c20bb3b6e63a4acc40e1138ba90a125b12a577e06`。
- 当前本地参考仓恢复点：`ndp-sim-ref@d4ffc32c9b29a858d83e13706cd837c5549521a4`、`NDPFuncModel@a1d975ee2d6d9200b8df0deea3e2ffc13ce0d05e`，已写入`repos.lock.json`且只作后续开发恢复点；v19已冻结candidate仍按其原始`056b1c3...`/`cb262bb...`provenance验收，不因本地提交改名或重建。
- 当前accumulate JSON SHA-256=`f26a3346859601055abc9cb88dd0b7c3650e5fcc4fae6d1f85d2562aba0ad8ed`；official mapper commit=`056b1c3c08b24e098636615d9001e8a974beb09f`，mapping key=`2702bd9d31f9efc0`，29行×128-bit规范化逻辑SHA-256=`7d85938215a1d5a5622c38938b5adb64b982c631170604a4ba8285fb5397b255`。
- 当前原生candidate位于`v19/encoder_candidate_native_02`：ID=`d5f6af19413919a72d761f99b61d35afdee5278e172a363f28055d937dd37898`，manifest SHA-256=`5146329288431fb970b26e35b70a93c2955515753430026327f36d76fe37589f`，validation SHA-256=`7ddd85d4b3afa9ce08385d588031ff9881fb1a79e7982a753d97a1db9dcc0764`，9条record独立A/B一致。
- 当前config-bound preflight SHA-256=`98febe58038352eefff14b2c88c19e332cdf3fdcf1531a16e91137c5ab0debbc`，Golden/NDP P/D mismatch=0。
- 当前freeze ID=`71686cf225194fbe6f9a0db73e7adf515a02ce252598ac58f6e5090793470b27`，manifest SHA-256=`6da4381275cf1a0e724451eea66e0035fab3e53e13b259af80eb875e77fe3f26`，512个声明文件。
- 当前package manifest SHA-256=`5d118970d4831074da8c8dfee57abdadb48d6bc402bf4aea93864b5dcffef636`；12个runtime stage、314行execplan、28 Bank、434 preload、168 readback和9个bitstream binding均由当前`--check`通过。
- v19不是v14/v18的同一硬件身份；schema 0.3不变性报告SHA-256=`08a6457ee3c8f8f0fa179feb06f81f3df22b6009ea6be771571efcdd303ad1de`只证明264个数值payload/runtime文件保持不变，并显式列出配置、bitstream、execplan和身份文件变化。
- v19 runner SHA-256=`1ae95b832c4273513c152ae453164346563fb2064c15c23255da44b5a7d9d8ee`；ZIP=`artifacts/w5/hwop-0004-00/v19/server_overlay.zip`，2,989,053字节、289个entry、0 HDL，SHA-256=`0874e8eeb8495ca46e3ddda54e1273c05e5c9a10b78c468e4584ba33398f06b2`。
- 下一次建立新revision并生成服务器测试包时，overlay输出目录和交付文件名必须显式携带版本号，例如`server_overlay_v20/`、`server_overlay_v20.zip`和`server_overlay_v20.zip.sha256`；runner/README继续使用`RUN_SERVER_V20.sh`/`README_SERVER_V20.txt`。v19既有文件名与SHA保持不变，不为改名原地重打包。
- v19 Round 1报告SHA-256=`164a13a7b8fda7dd0e09799e9d3d4e441ec407658a8280a8db516ef48f5df6b8`，20个行为用例全部PASS；Round 2报告SHA-256=`eec85fbd1cc2a5fe98e57a028108c1dac73b8f52545f26607c562670f4683dc2`，从最终ZIP和sidecar全新解包复算PASS。两轮绑定同一最终ZIP SHA。
- v14～v18撤权原因、历史ZIP/runner SHA和服务器失败证据只在`.agents/history.md`追溯；不得把历史路径当作当前可执行输入。

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

v18已完成真实run1但没有自然退出：preload完成后首个accumulate stage长期停在fixed observer `0/5`，随后手工终止。v19已修复该配置根因并完成原生A/B candidate、parsed/mapping/placement evidence、config-bound P/D、新freeze、package和两轮本地交付审计。当前阶段只允许上传不可变v19并执行run1；服务器自然完成和原始P/D尚未取得，run1验收通过前不得执行run2或升级G6/G8。

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

## 10. v15～v18历史收敛与v19当前交付

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
2. [完成] 由本地RTL与正式encoder语义确认：`SA_PE_Outbuffer`每个初始组需要指针0～3四次bias握手；current `buffer4.buffer_life_time=1`只产生一次消费，stream3又只按Kblock触发两个事务，导致psum tag在指针2处无效并阻断SA输出。这是硬件语义JSON错误，不是JSON语法错误。
3. [完成] 修改原生`tools/generate_conv_1x1_real.py`：建立独立`Kblock→H→Qblock` bias tile分支；stream3每tile装载一行32 B、地址只随Kblock以32 B变化，H/Qblock stride为0；GROUP2引用同一tile事件；buffer4 JSON lifetime改为4。
4. [完成] 扩展`validate_first_conv_sa_contract`与定向负例，机器证明bias事务数、两个地址、每tile四次消费、terminal/full/last引用链以及64 B边界；没有增加服务器运行时校验。
5. [完成] official mapper/encoder在全新目录独立双跑，placement、128/64-bit、parsed/mapping语义和关键字段全部闭合；正式accumulate变为29行×128-bit的新逻辑身份。
6. [完成] 刷新语义合同和typed request，config-bound Golden/NDP P/D mismatch=0；旧config/bitstream fallback由SHA与合同门拒绝。
7. [完成] 建立v19 candidate、preflight、freeze ID和package；v14/v18 freeze仅作历史负例，v19不冒充原数值身份。
8. [完成] 生成v19 overlay/ZIP并执行Round 1及最终ZIP独立Round 2；289个entry、0 HDL、无Git依赖，未恢复source扫描、`make -n`或额外运行时哈希层。
9. [待服务器] 只上传v19 ZIP与sidecar并先执行run1；run1自然完成且返回验收通过后才执行同一不可变包的run2，随后完成Golden/NDP/RTL三方比较。
10. [完成] 按v19活动实现同步仓库说明和两份派生规则，修正A/B角色、LC/PE/stream、bias节拍、server profile及服务器入口能力判定口径；本次未改任何v19包内或身份绑定文件，ZIP身份保持不变。v19已绑定的语义JSON中`evidence_boundaries`仍有旧候选“7/10 LC-PE”以及“typed qparam transport未证明”的自由文本；这些字段不被生成器或runner消费，当前实文件/正式candidate为16个DRAM LC、2个LC-PE、33条连接，typed qparam transport也已由当前项目链闭合。不得原地改写v19；下一次确需建立新数值revision时，语义合同刷新步骤必须同步更新这些说明元数据。

## 11. 后续扩展顺序

首例真实 P/D 三方闭环通过后，依次推进：同类 `1×1` shape family → `3×3/7×7` Conv → 其他算子族 → typed 网络 execplan 与地址生命周期 → 残差块/stage/head/整网三方闭环。通用 AddressPlanner 接管必须作为独立 revision，不能与首个原生 server profile 同时改变。
