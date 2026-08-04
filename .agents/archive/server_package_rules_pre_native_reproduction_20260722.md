# 已归档：NDP 自定义服务器测试包生成与验收规则（原生复现路线之前）

最后更新：2026-07-22（v15～v19 Conv均已撤权；v19首波279条gexec与冻结execplan逐条一致但仍停滞；当前可执行候选包括`node-0002` MaxPool两tile最小native-JSON包和DeepSeek Ring4 dg3，两者都已通过本地Round 1/2但尚未上服务器；G6/G8仍为false）
适用范围：`node-0004`、`node-0002`、DeepSeek Ring4及后续由本项目生成的 NDP RTL/VCS 服务器运行包
定位：从原始仿真README、活动生成器/runner、包内合同、服务器Make/TB接口及真实返回中提炼的当前工程约束；不是脱离这些事实的独立权威来源。冲突时必须修正错误规则，禁止为迎合旧文字增加无收益校验或改坏可运行入口。

## 0. 修改前事实核对与纠错顺序

1. 修改前读取`.agents/plan.md`、原仿真`model_execplan/README.md`、包内README模板及本文件中与本次变化直接相关的生成/运行/回传章节；历史revision段只在追溯对应故障时读取，不要求每次完整重读。
2. 如果修改触及算子JSON、配置生成器、bitstream、layout、qparams或runtime stage语义，再读取算子规则中的对应字段合同和证据边界；不得从无关历史故障推导新的服务器硬门。
3. 已由真实返回或静态证据确认的新错误，应先同步`.agents/plan.md`并形成针对该错误的最小生成门或测试；若本文件与实现/证据冲突，必须同时更正本文件。
4. 修改完成后复核最终目录和ZIP实际合同。发现规则、实现或产物不一致时先确定事实来源并修正错误项；不得默认规则正确，也不得仅为文档一致而重建数值身份。
5. 每个新revision在进入上传/服务器运行等下一步之前必须通过分层自检：若runner、overlay模板或生成工具有变化，第一轮为生成链/合同和真实目录行为自检；第二轮始终为从落盘ZIP重新解包、重新计算集合与身份的独立交付审计。两轮必须使用不同检查入口并分别保留结果；不得把同一命令重复执行、复用第一轮预计算摘要或仅重新读取第一轮报告冒充“两次检查”。任一轮失败即撤销该revision执行资格，先修复并重新生成最终产物，再从第一轮重新开始。

## 1. 目标与完成定义

服务器测试包必须是**由冻结输入一次生成、可独立校验、只合并运行文件、不修改服务器 HDL、失败时可定位**的交付物。生成成功只表示包具备启动资格；只有服务器自然完成、回传集合完整且 Golden/NDP/RTL 三方 P/D 全部 bit-exact，才可升级硬件数值门。

必须区分：

1. `package_ready`：数值身份、配置、execplan、SCA 和读回合同静态闭合。
2. `overlay_ready`：最小服务器 overlay、runner、manifest 和 ZIP 自洽。
3. `simulation_completed`：VCS/Make/testbench 自然结束且运行证据完整。
4. `hardware_numeric_passed`：回传 P/D 经 inverse 后与 Golden、NDP 全部一致。

前一级不得冒充后一级；CPU 占用、固定等待时间、单个 `Start_Comp`、Make 返回 0 或 testbench 单句“成功”都不是硬件数值通过证据。

## 2. 不可突破的边界

- `NDP_copy01/rtl/**`、主 testbench 及其他 `.v/.sv` 均只读，测试包不得包含、覆盖或现场修改 HDL。
- 用户提供的新服务器快照可以机械同步为本地只读兼容性基线；同步不能夹带本地补丁。
- 服务器源码允许更新。runner只要求主 Makefile、主 testbench、主 filelist 三个逻辑入口可读，并记录各自逻辑路径、`readlink -f`物理路径、大小和SHA-256；同时记录`DIR_HOME`状态/值摘要及固定vendor相对路径的解析状态/物理路径。不得在服务器启动路径中自建递归filelist/source/include解析器，也不得用Make/TB源码字符串扫描或`make -n`文本匹配替代真实工具链。物理目标位于服务器根外、入口由symlink/mount承载、外部include数量变化或vendor树不同均不得在compile前失败；真实缺失source/include、Make接口或TB能力由现有Make/VCS自然报错并进入统一失败归档。缺失三个逻辑入口、缺失包内合同、缺失必须命令或包内固定文件身份不一致仍然fail closed。
- 目标服务器没有Git，正式runner和README操作步骤不得要求`git`可执行文件、`.git`目录、Git HEAD、`git status/diff/ls-files/rev-parse`或任何基于Git对象的完整性判断。服务器侧固定运行文件完整性只使用包内manifest/内容寻址合同、`sha256sum`与ZIP sidecar；服务器活动源码只记录三个逻辑入口和`DIR_HOME`/vendor解析的运行时provenance。原生工具commit只属于本地生成身份，不是服务器依赖。
- package、overlay、runner、SCA、execplan、TCL 和回传合同必须内容寻址；服务器 RTL/TB 的实际 SHA 只记录为 provenance，不作为启动阻断条件。
- 已撤权revision不得原地修改或改名复用。任何语义、调度、runner或输入变化都生成新revision；历史保留按第10节归档策略执行，原始服务器结果ZIP永不改写。
- 从v19之后的下一新revision开始，生成器的overlay输出名必须包含同一revision token，使交付物固定形如`server_overlay_<revision>.zip`及`server_overlay_<revision>.zip.sha256`，overlay目录、`RUN_SERVER_<REV>.sh`、`README_SERVER_<REV>.txt`、安装目录和返回ZIP版本必须一致。sidecar正文必须引用带版本号的ZIP basename。历史制品不得仅为改名重打包；现有builder已由`--output`派生ZIP/sidecar名称，生成时传入带版本号的output即可，无需增加第二套重命名脚本。
- 禁止手填 JSON、`Repeat_Num`、地址、长度、manifest 或 SHA。正式包只允许由受测试生成器产生。

## 3. 唯一生成链

```text
ConvInstanceSpec / typed request
  -> config-bound preflight 与 P/D
  -> versioned hardware freeze
  -> hardware execplan package
  -> package authoritative check
  -> runtime-only server overlay
  -> ZIP exact-set audit + SHA-256 sidecar
  -> Linux/VCS服务器运行
  -> 原始结果ZIP
  -> readback重组与三方P/D比较
```

正式生成时必须显式给出 node、freeze、typed request、输出 revision 和观察模式，不依赖脚本默认值猜版本。`tools/generate_conv_hardware_execplan.py`是硬件包唯一入口，`tools/build_ndp_server_overlay.py`是 overlay 唯一入口；不得从旧 ZIP 复制后手改成新版本。

## 4. 生成前输入冻结

生成器启动前必须一次确认：

- node/hwop、shape、dtype、量化参数、layout ABI 和 28-slice 拓扑属于同一 typed request；
- accumulate/requant JSON 已经正式 encoder 双跑一致，parsed evidence 与 bitstream 对应；
- 每份配置JSON都必须绑定正式encoder输出的原始SHA、规范化逻辑SHA、有效行数和每行位宽；freeze副本及最终安装副本的规范化逻辑SHA、行数和位宽必须与该encoder记录逐项相等；
- Golden/NDP 的 P 与 staged-D 已在 config-bound 路径 bit-exact；
- freeze manifest 中每个输入、配置、bitstream、地址表和输出合同都存在且哈希正确；
- 正式非历史 freeze 的导出目录必须全新或为空；验证器必须重算不含`freeze_id`字段的规范 JSON 摘要并与`freeze_id`相等，同时要求`manifest.json + manifest.files`与目录普通文件exact-set完全相等，任何额外文件、缺失文件、symlink或伪造ID都立即失败；
- candidate 的内容身份不得吸收工作区绝对路径、Python解释器绝对路径或临时输出根；正式命令证据必须使用稳定的仓库相对路径/占位符描述，绝对路径只能作为不参与candidate ID的本地运行诊断。相同仓库commit、typed request、server contract、address plan和生成内容在不同工作区必须产生相同candidate ID；
- 新包引用的所有文件来自同一 freeze/typed request，不混入旧 SCA、旧 runner 或旧输出目录；
- 工作树既有用户修改不被生成或清理命令覆盖。

任一项不满足时停止生成，不通过服务器试跑猜配置。

## 5. 历史问题与当时修复口径

本节保留问题演进用于追溯，不是现行硬门清单。旧行中的TB源码扫描、`make -n`文本匹配、vendor树同构和批量外部命令等要求已被后续事实推翻；与第2、9、12、13节冲突时，以这些现行章节为准，不得为了复现历史行重新增加服务器预检。

| 历史问题 | 当时修复口径或后续结论 |
|---|---|
| v1：raw `.bin` 被逐行文本 loader 误读 | 每个 SCA/SCA_D payload 必须匹配 TB parser ABI；当前数据统一为每行固定宽度 `0/1` 文本，并校验行数、位宽和字符集 |
| v2：P/staged-D scratch 未初始化导致 X | 所有读改写目的区必须显式初始化；manifest 声明初始化对象和期望行数，禁止依赖仿真器默认值 |
| v3：SA accumulate producer route 错 | 生成前验证 SA/GA producer、`buffer5.dst_port`、outport 和消费端 invariant，并以 parsed bitstream 反证字段确实编码 |
| v4～v6：route/outport/mask/batch 不完整；会话 SIGHUP 被误认算子故障 | runtime stage 必须覆盖完整 batch/shard，mask/barrier 精确；runner 独立记录 timeout、signal、make、tee 和 simulator exit |
| v7：只有部分 weight token 链推进 | 静态合同必须同时覆盖 A/B/bias/P、N2N selector、neighbor count、ready/tag 和最终写回，不以单路 token 作为完成门 |
| v8：局部单元完成但 group1/整体不推进 | 完成合同必须覆盖全部 stage 和最终输出，不以 MSE1 或任一局部完成信号代替整体完成 |
| v9：AXI burst 跨 4 KiB；`Repeat_Num`手填；stage 数过期 | 所有 preload/readback 段逐段验证 4 KiB 安全；observer count 由生成器推导；manifest、SCA、runner 三方绑定 runtime/observer 数 |
| v10：Git/整树 hash 阻断正常服务器更新；真实 TB 能力与本地假设不符；新增`m_axi_reserved_clk`未驱动 | 服务器只对入口，不锁源码；新快照先做 filelist/端口/TB parser/observer 能力审计；缺失环境驱动只能用窄范围非 HDL runtime 机制并清理旧编译缓存 |
| v10r1：Windows生成的package有44个CRLF文本，overlay仍带13个；服务器在compile前以`invalid_reserved_clock_ucli`退出 | 把换行定义为正式ABI；生成、复制、manifest和ZIP entry全部按原始字节验证LF-only，错误报告必须指出实际文件、CR字节数和检查阶段，禁止只检查runner/TCL或用错误类别掩盖其他文件 |
| 返回验证器仍按capability policy 0.1验收，而completion overlay已生成含observer/clock策略的0.2 | 生成端与返回验收端必须消费同一policy schema；根据package冻结的observer mode精确复建预期策略并逐字段相等比较，禁止把合法0.2返回误判为身份错误，也禁止宽松接受未知字段/版本 |
| v10r2：runner生成模板中的Python `\015`转义先变成真实CR，再被LF归一化成换行，使CR计数命令实际统计LF | runner的字节检查不得在生成语言字符串中嵌入CR/LF控制转义；使用`od`十六进制字节扫描等无控制字符模板，并以一个纯LF样本应为0、一个含CR样本应为1的真实Bash行为测试验证，`bash -n`和“runner自身无CR”不能替代语义测试 |
| v10r3最终回传：433/433个preload传输全部完成写入、读回及一致性校验，`Exec_Length=313`后28个slice进入首个`Start_Comp`；每个slice发生2次确定性零值P读回并发出2次P写请求，但28个slice合计56次写请求之后MSE4 write-data握手仍为0、slice completion为0，完成stage为0/11。三个accumulate wave在`0x00101c00/0x00102000/0x00102400`实际各加载35行旧e0码流；运行最终命中86400秒墙钟，process exit=124，随后才出现0/168 readback。 | 正式freeze必须显式指定当前encoder输出根，禁止通过默认/fallback选择旧encoder目录；对JSON记录的official encoder输出、freeze bitstream、package安装bitstream执行规范化逻辑内容三方相等检查，并同时绑定config SHA、parsed evidence、行数和位宽。回传判因必须把“预装完成→首stage启动→P读改写写请求→无write-data/无完成”作为最早断点；24小时超时和0/168 readback是后续状态，不得倒置为根因。任何身份项缺失或不等立即拒绝生成，不能只验证package文件等于freeze文件。 |
| v10r4：runner按固定slice0-start/slice1-finish的5对observer验收，离线返回解析器却仍无条件要求11条`RUNTIME_STAGE_COMPLETE`；最后一对只证明slice1完成，不能证明最终mask内全部slice完成后才readback；requant绑定仍可对一个陈旧encoder目录自洽 | 返回解析必须由package冻结的observer mode分支，fixed observer精确重算start/finish/自然结束/保留时钟计数且不得要求不存在的runtime marker；最终stage必须有不修改RTL/TB的全mask完成证据并先于readback；每个requant JSON必须像accumulate一样由独立semantic/encoder-run contract绑定正式encoder输出、parsed evidence、freeze和安装副本，禁止用同目录文件互证代替配置到输出的来源证明 |
| v10r5交付前复审：不可变TB默认生成数百MB高频bank-frame日志；reserved-clock成功marker在force后无条件打印；runner只有24h总墙钟且完整复制/压缩`sim_results` | 不修改TB/RTL，使用服务器Makefile已有的编译宏接口启用`BANK_FRAME_LOG_SLICE_START_ONLY`；reserved-clock必须在UCLI中证明force命令成功且低/高采样发生翻转后才打印唯一成功marker；runner按preload/首Start/observer/readback/归档阶段记录进度并在停滞超时后fail closed；返回ZIP只收最小诊断allowlist、运行元数据、console和readback exact set，禁止复制全量原始`sim_results` |
| v10r6交付后复审：start-only宏只保护hub-frame分支，112个`mc_rdata`日志仍逐拍`fwrite/fflush`；Make的`sim`目标仍无条件执行`archive_sim_results`并复制完整结果树；watchdog用原始`grep -c`把重复/越界marker当进度且丢弃异常退出；诊断无单文件/总量上限；离线验收未约束整体返回集合；实际Make argv未与批准身份绑定 | 不修改TB/RTL：runner只在本次临时`sim_results`内把已审计的高频诊断路径预建为精确指向`/dev/null`的symlink，overlay/return仍禁止symlink，并在启动前核对TB仍声明全部受审计日志路径模式；用单独受manifest约束的非HDL附加Makefile定义新的no-archive simulation target，复用服务器`SIMV/SIM_OPTS`且不定义/覆盖compile、sim或archive target；watchdog按有序状态机验证preload索引、start/finish交替、上限和readback集合，重复/乱序/越界立即失败且异常退出必须传播；诊断实行单文件和总量硬上限；返回根生成全文件exact-set/size/SHA合同；实际执行argv从内容寻址合同逐行加载并记录其SHA |
| v10r7最终静态复审：watchdog只在轮询体内验marker，进程退出前最后一段console可能未终检；轮询会读取`tee`正在追加的半行；readback按目录中文件数推进并把`$fopen`创建当作完成，最后文件仍写入时即进入短完成超时；额外文件/符号链接可伪造进度；argv未显式关闭VCD；Make dry-run未证明最终有效命令；返回`config/metadata`可自纳入额外文件；`set -e`意外退出可能没有失败归档 | live marker检查只消费换行完整的稳定快照，`tee`结束后对完整console再做一次最终有序校验；readback进度只认可合同exact-set内、普通文件、达到冻结精确字节数的完整对象，额外路径/符号链接立即失败，全部168个完整对象后才能进入completion-exit；命令合同显式冻结`DUMP_VCD=0`；Make预检须检查实际`compile + noarchive`展开包含批准宏、UCLI和SCA plusarg；runner只复制批准的config/metadata exact set；所有意外退出由统一失败归档处理；runner启动前验证自身内容寻址身份 |
| v10r8最终本地复审：`inspect_readback_progress`扫描整个`${install_root}/install`，把启动前已存在的272个合法execplan/config/input/scratch预装文件当成非合同readback，首次watchdog轮询必报`unexpected_readback_file`并终止；原行为测试只构造空白install树而漏检。进程退出后的runner `awk`和离线验证器又接受最后一行无LF的128字节文件；CLI默认request/output仍指向旧v10/v10r7；若干显式`exit`绕过统一失败归档 | readback exact-set只能审计由冻结合同推导出的revision输出命名空间（当前为`${install_root}/install/hwop-*`），预装输入由launch合同单独验收，二者不得混扫。运行中、进程退出后和离线验收必须共用同一精确记录ABI：每行128个`0/1`、每行LF、总大小=`line_count×129`、路径exact set；正式行为测试必须在最终overlay的完整真实install基线上执行并证明272个预装文件不触发readback错误。正式CLI必须显式传入freeze/request/output/revision/observer，旧默认值不得参与current生成；所有预检、运行和后处理失败均进入统一最小失败证据路径。两轮自检中至少一轮必须执行这些真实目录行为负例，纯静态ZIP重算不能替代。 |
| v11交付后本地复审：runner的三个GNU awk程序把内建函数名`index`用作循环变量，GNU awk 5.3.2在建runtime日志sink及完整readback校验时直接语法失败；目录中没有规则要求的`selfcheck_round1`，却被文档和manifest误记为两轮PASS；freeze验证器只查manifest声明项且不重算`freeze_id`，可接受额外文件和伪造ID；candidate manifest把本机Python/config/output/repository绝对路径纳入candidate ID | awk脚本除`bash -n`外必须在GNU awk真实执行，变量名不得与awk内建函数冲突，并以完整sink集合和至少一个合法完整readback对象验证；第一轮报告必须由正式生成入口落盘、绑定最终ZIP SHA并覆盖完整真实install的272预装+0 readback、合法完整readback、额外输出、缺末尾LF和进程退出后终检；freeze导出/验证执行全目录exact-set与ID重算；candidate身份使用跨工作区稳定的路径中性命令证据。v11永久撤权，全部修复从新原生commit和新v12身份重跑。 |
| v14发布前复审：目标服务器没有Git；真实活动NIC filelist含`${DIR_HOME}`外部vendor include，旧规则却无条件禁止include逃逸；新增批量树摘要使用`xargs`/`mktemp`，runner能力门未声明，README也未说明环境前提 | 正式runner永久禁止Git依赖，固定包完整性仅用SHA/manifest/sidecar；只允许精确NIC vendor路径，并要求它与in-tree活动副本全树同构且写入provenance；`basename`、`mktemp`、`xargs`等实际外部命令必须全部进入启动前能力门；README必须明确`DIR_HOME`要求。修复后删除中止产物并从Round 1、Round 2重新开始。 |
| v14再次复审与诊断run1：外部include期望数量可由同名环境变量覆盖；Python runner模板中的`$'\r'`先展开为控制字符又被LF归一化，生成脚本实际重复检查LF；正式run ID接受任意安全字符串；两轮审计只检查字段/字符串存在。v14随后在服务器preflight失败：`server_filelist_member_outside_root`，活动filelist物理解析到服务器根外，未进入compile/sim | 除明确合同允许的`DIR_HOME`和固定`SERVER_RUN_ID`外，正式runner的数量、路径和策略常量不得从环境继承；外部include数量/树同构和source物理根内前缀不得作为启动硬门，只记录provenance或交给VCS/Make自然诊断。模板中的控制字符匹配必须双重转义或使用十六进制字节法，并以真实CR文件名行为测试。正式ID只允许`run1/run2`，`run3`必须在其他处理前失败并归档；Round 1和Round 2都要验证行为而非字符串。v14不得原地修补或重跑，结合原始失败ZIP建立v15。 |
| v15独立复审：runner在验证自身SHA前删除同run ID旧返回目录/ZIP/inventory；两轮稳定性只比较readback而不比较服务器入口provenance；数值不变性报告只比较manifest记录；回归硬编码v14且未验证身份门早于清理；168个约162 MiB readback在每次轮询重复全文扫描；删除TB源码路径扫描后缺少未知高频日志运行时保护 | v15保持不可变并撤销发布资格。v16必须在run ID最小校验后只用`sha256sum`先验证runner自身，验证成功前不得创建、删除或覆盖任何证据；run1/run2稳定性必须要求Makefile、TB、顶层filelist的逻辑路径/物理路径/大小/SHA及冻结的关键执行环境一致；不变性报告生成前必须分别权威验证参考包和候选包的实际exact-set/SHA；当前revision产物测试必须验证身份门执行顺序；watchdog进度轮询只查路径、类型和大小，文件首次达到精确大小时完整验证一次，退出后统一终检；不恢复TB源码扫描，改用运行时未知日志和总量上限保护。修复后建立v16并从Round 1、Round 2重跑。 |
| v16发布后本地复审：身份验证虽已早于清理，但`mkdir/rm`清理仍早于统一错误函数和ERR trap，受控`rm`失败可删除旧return后无报告退出；合并后的install根只逐项验声明文件而不拒绝额外文件；`MAKEFLAGS/MAKEFILES/GNUMAKEFLAGS/MFLAGS/MAKELEVEL`可改变内容寻址argv的实际Make行为；双跑未记录`DIR_HOME`及vendor解析路径；不变性报告文字称manifest字节相同但只比较JSON对象；overlay/两轮报告存在晚冲突或覆盖旧报告的路径 | v16保持字节不变并撤销发布资格。v17允许复用同一批准数值freeze，但必须把函数/trap和完整命令门放在任何清理前；永久缺失`rm/mkdir`等证据原语时只允许stderr失败并保持旧证据不变，具备证据原语后的任何清理异常必须统一归档；启动时校验静态install实际exact-set；清除Make控制环境变量；把`DIR_HOME`值和vendor解析结果作为非阻断provenance纳入run1/run2一致性；manifest执行真实byte比较；所有生成报告和ZIP/sidecar在昂贵工作前拒绝路径冲突且不得覆盖。修复后建立v17并重跑Round 1、Round 2。 |
| v18真实run1：全部preload后进入首个accumulate stage，fixed observer长期为`0/5`；手工终止证据表明未到达SA transout/buffer5 write-data。静态反查确认stream3只按两个Kblock装载bias且buffer4 lifetime=1，而SA outbuffer每个输出matrix tile需要四次bias握手才初始化完整16项组 | v18保持返回ZIP只读并撤销run2/继续运行资格。该错误改变JSON、bitstream和调度，下一revision不得复用v14/v18数值freeze；必须在原生生成器中建立Kblock/H/Qblock bias tile分支、32 B行、零地址stride触发维、buffer4 lifetime=4及对应静态门，再执行official encoder A/B、parsed evidence、config-bound P/D、新freeze/package和Round 1/2。runner服务器校验不因此增加；在后续硬件反事实前只能称为必要静态修复或候选根因。 |
| v19本地交付审计：原生Kblock/H/Qblock bias tile分支、32 B行、H/Qblock零地址stride、GROUP2同源和buffer4 lifetime=4均通过静态负例；official encoder A/B、parsed/mapping/placement、config-bound P/D、新freeze/package和Round 1/2全部通过 | 服务器运行前v19仅取得`overlay_ready`；本地静态/交付闭环不能替代自然完成、run2稳定性或三方P/D。 |
| v19真实run1与补充gexec：434/434 preload和首波28个slice Start完成，fixed observer在`0/5 pending=1`停滞约7202秒；补充日志中的279条gexec与冻结execplan逐条一致，v18→v19的56处预期Load Config/READ_STREAM3变化全部到达硬件 | v19永久撤权并禁止run2。最早断点位于Start之后、任一slice completion之前；不能再归因为旧bitstream混装、首波命令漏发或global executor未启动，也不能把bias修复写成已证实的唯一/充分根因。下一Conv revision须先取得能区分READ_STREAM3→buffer4→SA→buffer5→WR_MSE0链路的最小证据；这不禁止独立、身份隔离的MaxPool包。 |

## 6. SCA、地址和 AXI 运输

### 6.0 JSON、正式encoder、freeze与安装bitstream强绑定

- 每个配置实例必须在语义合同或encoder evidence中记录：配置JSON SHA-256、正式encoder输出路径、原始文件SHA-256、规范化逻辑SHA-256、有效行数、每行位宽以及parsed evidence SHA-256。
- 逐行文本bitstream的规范化逻辑内容定义为：先拒绝空行、非`0/1`字符和错误位宽，再把所有有效行按原顺序用单个LF连接并以LF结尾。原始SHA用于来源追溯和运输完整性；规范化逻辑SHA用于跨平台证明码流内容相同。禁止仅因CRLF/LF导致原始SHA不同就跳过语义绑定。
- 正式非历史freeze导出必须显式传入当前`accumulate_encoder_root`以及每个requant encoder根。默认旧目录或fallback只允许只读历史重建入口；当前revision缺少显式encoder根必须fail closed。
- freeze生成时必须证明：当前JSON SHA等于语义合同记录；encoder根中的bitstream规范化逻辑SHA等于合同记录；复制进freeze后的规范化逻辑SHA、行数和位宽仍相等。package生成时再次证明安装副本与同一freeze/合同相等。
- authoritative package `--check`必须从package内绑定的semantic contract/encoder evidence重新计算上述关系，不能只消费manifest中预填的期望SHA，也不能只证明安装文件和freeze文件彼此相同。
- accumulate与每个requant shard都必须拥有独立、不可由freeze反向自填的semantic/encoder-run contract；合同至少绑定config SHA、正式encoder命令/输出根、双跑一致状态、128-bit原始与规范化逻辑身份、行数/位宽和parsed evidence SHA。package `--check`必须逐record从typed request内嵌合同重新建立这些关系，不能只对accumulate执行独立重根。
- 对首个1×1 accumulate，v14/v18历史码流为`rebuild-v9`对应的28行×128-bit逻辑内容，LF规范化SHA-256=`44fb091f0013dbccfc376154ea53d074d08bc945e3d276810579766e8c45fa8f`；它已因bias tile节拍错误撤权，不再是current身份。v19正式码流为29行×128-bit，LF规范化SHA-256=`7d85938215a1d5a5622c38938b5adb64b982c631170604a4ba8285fb5397b255`，必须由当前semantic contract、native candidate、freeze和package逐层命中。旧`e0-rebuild`的35行码流仍是固定负向样本，LF规范化SHA-256=`4dabcb3879fe4968019ee0c7e5461dfb5892ac4e6aaef4a1e3d69ec9e69361a2`。禁止把行数写成脱离revision的永久常量；原始文件因CRLF/LF产生的SHA差异不得绕过规范化逻辑身份。

### 6.1 跨平台文本 ABI

- 所有由 Linux shell、VCS/UCLI、testbench、`$readmemb`/逐行loader、JSON parser、`awk`或`grep`消费的文本都必须是 UTF-8/ASCII 且仅使用 LF；原始字节中禁止出现`0x0D`。范围至少包括 shell、TCL、JSON、TSV、TXT、逐行二进制payload以及虽以`.bin`命名但内容是`0/1`文本的bitstream。
- Windows上的Python生成器必须显式使用`newline="\n"`或直接写确定性bytes；`Path.write_text()`、源文件复制成功或Git属性都不能单独证明LF-only。
- overlay复制已知文本文件时必须按文本ABI重新写入，不能用`copy2/copytree`原样传播CRLF；真正的二进制payload保持原字节，禁止对未知文件盲目替换`\r`。
- 权威package检查必须扫描全部声明文本文件的原始字节并要求`cr_byte_count=0`；overlay生成后再次扫描实际目录；ZIP生成后直接读取每个entry字节做第三次独立检查。三层检查任一失败都停止发布。
- runner启动时仍应对关键shell/TCL/合同做窄范围LF检查，但它只是传输后的防御门，不能替代生成端审计。失败报告必须写出精确相对路径、CR字节数、期望SHA和实际SHA；不得把非TCL文件的换行错误归类为`invalid_reserved_clock_ucli`。
- runner内的CR计数实现必须按原始十六进制字节识别`0d`，生成模板源码和生成后的shell都不得携带用于匹配的真实CR控制字节；发布测试必须实际调用该函数验证LF样本返回0、单CR样本返回1，不能只断言字符串或只做`bash -n`。
- 包内生成的合同相对路径和原始返回ZIP entry必须拒绝绝对路径、`..`、重复entry和非普通对象；固定TSV字段不得由未约束的文件名生成。活动服务器物理路径只作provenance，不为TAB/LF/CR等畸形文件名增加每版发布硬门；只有修改路径解析代码时才运行相应定向负例。
- 正式包的README和`.sha256`侧车也使用LF；服务器解压前校验ZIP SHA，解压后不得用会自动文本转换的工具或参数。

### 6.2 地址、payload与AXI分段

- 地址统一声明单位，显式区分 byte 地址、16-byte word 地址和 128-bit line；禁止仅凭日志数字猜单位。
- 每个 128-bit payload 行必须恰为 128 个 `0/1`字符；32-bit Bank 行必须遵守冻结的低 32 到高 32 组合顺序。
- **当前风险标注（2026-07-20）**：AXI4单burst不得跨4 KiB边界以及v9的`0x00104800/256`历史触发事实保持有效。4 KiB问题仍标记为“可能并非所有服务器链路都实际存在，但按存在处理”；每个正式revision必须从最终SCA/SCA_D逐对象重算，报告语义运输对象、真实触发数、未触发数及拆分前后payload/descriptor SHA。DeepSeek算子正常运行不构成反例，因为其地址、长度、对齐和TB调用序列不同；后续若服务器证据证明当前链路从约束上不可能跨页，应立即定位并删除不必要的运行时分段，只保留静态断言和`not_triggered`报告。禁止把任何旧revision的169计数硬编码成先验。
- preload 与 readback 都必须按 4 KiB 边界拆段。对 16-byte word，总段长不得超过：

```text
min(remaining_words, hardware_max_burst_words,
    floor((4096 - (byte_address & 4095)) / 16))
```

- 段起点已经在页边界时页内余量按 4096 字节计算；任何段都必须满足首末 byte 位于同一 4 KiB 页。
- `sca_cfg.json`、`sca_cfg_D.json`、嵌套 execplan head/tail、实际 payload 和 manifest 记录必须使用相同拆分结果。
- 每个传输对象生成唯一标签、目标地址、word 数、payload SHA；runner 要求精确 preload PASS 数，不能只检查“至少一次成功”。

## 7. runtime stage 与不可变 TB 观察合同

- runtime operator count 由 execplan 中真实 `Start_Comp`产生；每个 stage 后必须有同 mask barrier，禁止用 sleep 代替依赖。
- `Repeat_Num`由目标 TB 的实际 observer 语义生成：mask-aware TB 使用 runtime stage 数；固定 slice observer 使用经静态证明的观察对数。两者不得混为一个计数。
- 为固定 observer 重排 stage 时，只能交换互不共享资源且无数据依赖的分组；组内顺序、输入、输出地址和数值身份必须保持不变。
- 静态 observer 合同必须列出每一对 start/finish 对应的 runtime stage，并证明最后观察对落在最终 barrier-ordered stage；否则不得发布。
- “最后观察对落在最终stage”只证明被观察slice，不自动证明最终mask内其他slice已经完成。不可变TB在最后一对后固定等待再readback时，package必须给出可机检的全mask完成/全局barrier完成证据及其发生在readback之前的顺序；缺少该证据不得把observer pair冒充全部runtime stage完成。
- runner 同时验证真实 runtime stage 数、observer 精确计数和唯一自然完成 marker。fixed observer的运行元数据必须保留并验收`observed_slice0_start_count`、`observed_slice1_finish_count`和`reserved_clock_force_marker_count`；mask-aware模式才要求逐stage/all-stage marker。缺任一适用项即失败。
- 离线返回解析必须读取package冻结的`testbench_observer_mode`：fixed模式重解析精确5对observer、唯一自然完成和退出顺序，不得要求TB不会产生的`RUNTIME_STAGE_COMPLETE`；mask-aware模式继续逐条验证stage/mask/all marker。未知模式一律fail closed，并为两种模式各保留正负回归。

## 8. 服务器快照兼容性审计

收到新服务器目录后，在生成正式包前只做一次高价值审计：

1. 确认主 Makefile、主 TB 和主 filelist 三个逻辑入口；记录可取得的逻辑/物理路径与身份供人工分析。symlink、mount、根外物理目标、`${DIR_HOME}`外部vendor路径、外部include数量和vendor树差异只作兼容性provenance，不成为正式runner的compile前硬门。
2. 只有取得完整、可信的服务器源码快照时，才在本地只读分析中检查活动compile closure，重点审查top端口、时钟/复位、TB实例连接、SCA parser、burst算法、observer和完成条件；快照不完整时不得用自建解析器猜测闭包，实际能力由服务器Make/VCS运行判定。
3. 将用户明确提供的服务器文件机械同步到本地只读镜像，用于生成器兼容性分析；不把它们打进overlay，也不夹带本地补丁。
4. 把确认的新增端口或TB行为变化转成package/runner能力合同。无法通过非HDL方式可靠适配时fail closed，请求服务器侧明确能力，而不是猜测。

该审计用于发现能力变化，不得演变成 runner 的整树一致性门。

## 9. runner 和环境规则

- runner 必须从现有 `NDP_copy01` 根目录运行，路径相对化；overlay 语义只能是 merge-only，不能删除或替换服务器根目录。
- 启动前验证合并后静态install实际路径exact set和普通文件类型；launch manifest声明的运行文件继续核对大小/SHA，runner继续核对自身份。`runtime_identity.json`作为生成端和返回端身份记录，不再额外增加一轮服务器启动哈希门。运行产生的`install/hwop-*`输出命名空间按本run合同清理后单独审计；额外静态文件、symlink或非普通对象均失败。检查三项服务器入口；服务器不具备Git，runner不得调用或探测`git`/`.git`，禁止`git rev-parse/status/diff/ls-files`、RTL/TB预置SHA比较或把Git对象当完整性证据。
- runner在run ID最小校验后只允许先用Bash builtin执行`command -v sha256sum`能力检查，并立即验证自身内容寻址身份；身份验证成功前不得创建、删除、移动或覆盖任何证据。身份通过后安装ERR trap并逐项`command -v`检查实际使用的外部命令，全部通过后才允许清理。命令清单只由生成器中的单一常量渲染，独立ZIP审计无需再次维护或逐项匹配另一份列表。缺少任一必需命令时统一stderr退出并保持旧证据不变；能力门尚未通过时不得调用会清理canonical结果路径的失败归档函数。
- 正式运行时的包级外部输入只允许`DIR_HOME`指向活动vendor根、`SERVER_RUN_ID`精确等于`run1`或`run2`；VCS许可证、`PATH`、`VCS_HOME`等服务器工具环境属于执行能力，不得被误称为包策略输入。其他策略值、路径、超时和计数均由package/manifest冻结，不得用`${name:-default}`从服务器环境继承。runner在启动Make前必须清除`MAKEFLAGS`、`MAKEFILES`、`GNUMAKEFLAGS`、`MFLAGS`和`MAKELEVEL`，防止dry-run、并行目标或额外makefile改变冻结argv；测试必须在这些变量被设置时证明实际合同不变。`DIR_HOME`及固定vendor相对路径的逻辑值、解析状态和物理路径只写入provenance，不作compile前内容硬门，并必须纳入run1/run2一致性比较。外部include数量不是策略常量，不得再通过环境变量或manifest整数作为启动门。
- `run1`和`run2`是同一不可变包的两次完整重复实验，不增加单次stage或数据内容。runner必须拒绝任何其他run ID，并让两轮使用互不覆盖的返回根、缓存清理范围和ZIP名。
- 每次正式编译前清理当前运行的 `run/csrc` 和本`revision + SERVER_RUN_ID`所属的旧返回目录、旧归档及临时source inventory，避免 `-Mupdate`/缓存或同名旧ZIP掩盖接口变化；`run1`不得删除`run2`结果，反之亦然。共享`sim_results`若必须清理，只允许证明它是本次临时日志sink树或先归档，禁止删除其他run ID/revision证据和服务器源码。
- 正式验收默认不采全量波形、不固定仿真退出时间；诊断包与正式完成包必须使用不同 revision 和明确 observation mode。
- UCLI/TCL 只能承担已经审计且无法由 package 表达的窄范围运行环境动作，例如驱动悬空的`m_axi_reserved_clk`；不得改设计逻辑、修改 TB、伪造完成信号或固定时间宣告成功。
- 对当前固定observer TB，runner仍须通过Makefile的`VCS_EXTRA_OPTS`启用已有`BANK_FRAME_LOG_SLICE_START_ONLY`编译宏；但不得把该宏解释成MC日志也被抑制。对已审计且不参与完成/数值判定的高频日志，生成器把固定sink相对路径写入内容寻址合同，runner只在本revision新建的临时`sim_results`中预建精确指向`/dev/null`的symlink，使不可变TB的`$fopen`成功但不落盘。服务器启动不得扫描TB源码来重新证明路径字符串；仿真期间改为检查`sim_results`中合同外普通文件和总字节数，未知或超限日志立即fail closed并归档。该豁免只适用于临时运行诊断sink，overlay、install、readback及返回根仍严格禁止symlink。
- 服务器Makefile的`sim`目标若无条件依赖全量`archive_sim_results`，runner必须通过内容寻址的附加Makefile定义一个新的no-archive simulation target并直接调用它；该target只复用服务器原有`SIMV`、`SIM_OPTS`和传入参数，不得定义或覆盖compile、sim、`archive_sim_results`、HDL/filelist变量。附加Makefile路径、SHA、target名和实际argv进入launch合同。启动只检查逻辑Make入口、附加target合同和实际命令能力；不得执行`make -n`后扫描展开文本。接口不兼容由真实Make/VCS命令失败并统一归档。不得修改服务器Makefile，也不得在正式仿真结束后复制完整原始结果树。
- reserved-clock UCLI不得在`force`命令后无条件打印成功。脚本必须捕获force与采样错误，在两个已知相位读取目标层次并证明值发生翻转；仅在全部成立时打印一次`RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING`。runner同时要求成功marker精确为1、失败marker为0，并把实际层次记录到元数据。服务器源码可更新，但目标端口、实例层次或UCLI读写能力缺失时必须以能力错误fail closed。
- 除总墙钟外，runner必须有分阶段停滞保护：preload阶段按`JSON: Loading matrix[N]`从0连续递增并与每次唯一PASS成对；首个`Start_Comp`只能出现在全部preload完成后；fixed observer的start/finish必须严格交替、不得超出冻结对数；readback只能由exact-set内新增普通文件推进；归档阶段单独受限。重复、乱序、跳号、越界、提前进入后阶段或finish先于start都必须立即fail closed，不能重置计时。超时/协议错误报告必须保存`phase`、最后合法进度、停滞秒数、原因和进程退出状态。
- live console校验只能消费以LF结尾的完整记录快照，不得把`tee`正在追加的末尾半行判为协议错误；仿真及`tee`退出后必须对完整console执行一次最终有序校验，终检失败必须覆盖正常进程退出结论并生成失败归档。
- readback进度集合必须由冻结合同逐路径生成。扫描边界只能覆盖合同共同输出命名空间，当前为`${install_root}/install/hwop-*`；`${install_root}/install`中的execplan、cfg_pkg、输入和runtime scratch属于预装/launch集合，不得因不在readback合同内而被拒绝。输出命名空间内任何非合同路径、符号链接或非普通文件都立即失败。轮询阶段只检查路径、普通文件类型和当前大小；合同文件首次达到该region冻结行数×129字节时完整验证一次128-bit/LF/行数ABI并记入本次watchdog的已验证集合，后续轮询不得重复全文扫描。文件大小超过期望立即失败；全部合同对象完成后才允许进入自然退出等待。进程与`tee`退出后必须对全部168个对象统一重新执行exact-set、末尾LF、内容格式、行数、精确大小和SHA终检；final/offline验收不得信任live缓存。
- phase watchdog自身是受验收进程：正常观察到仿真进程退出时必须写完成sentinel并返回0；协议失败/停滞必须写失败记录并返回非0；无失败记录的异常退出同样使主runner失败。主runner不得捕获`$?`后无条件改写为0。
- runner 必须分别保存 process、make、tee、simulator、timeout/termination 状态；任何未知退出、SIGHUP、wall timeout 或交互式 `ucli%` 停留均失败。
- CPU 利用率仅是进程活跃信号；进度只能由新的合法 AXI 完成、stage marker、observer pair、readback 或自然结束证明。
- `process_exit_status=124`、`termination_kind=wall_timeout`和`simulator_exit_status_observed=false`的组合表示外层超时终止，不能写成模拟器自然退出或HDL fatal；若终止前长期没有新的合法阶段进度，只能报告“功能停滞后命中墙钟”，并保留最后合法事务时间和阶段。
- 终止后出现的readback缺失必须按因果顺序解释。若preload已经精确PASS、首个`Start_Comp`已经发生而completion尚未发生，则随后`make ... Terminated`和0/N readback是未完成计算的后果，不得把“补readback文件”“延长总墙钟”或“只改归档器”列为首因修复。
- 同一revision的中间ZIP与最终ZIP大小或entry数不同不代表仿真取得新进展。比较时必须先剥离单层归档前缀，再按逻辑路径、大小和CRC/SHA核对共同trace；若共同事务trace不变而只新增console/metadata/exit status，应把新增内容用于补齐终止判定，不得声称stage继续推进。
- 返回ZIP不得递归复制全量`sim_results`。正式包仅允许归档console、preflight/运行元数据、身份/状态、readback exact set，以及规则中声明的少量诊断日志allowlist；不得包含波形、simv/csrc、全量bank-frame或Makefile已保留的archive副本。成功态`run_sim_results/`必须恰好包含同revision前缀的console、exit status、phase progress和watchdog done四个文件，任何phase timeout记录或额外同模式文件都与成功状态矛盾并须拒绝。失败态若已有允许的普通文件`gexec2slice/slice_all/gexec2slice.log`，应在单文件/总量硬上限内保存其有界副本；缺失时只记录缺失，不得覆盖主失败原因或成为新的运行硬门。这只是复制已经生成的定向证据，不要求扫描TB源码、增加trace或验证命令内容。每个诊断文件和诊断总量都必须有硬上限，超限时只能按声明策略截取或拒绝，不能无界`cp -a`。打包前必须拒绝返回根内symlink/非普通文件，并生成覆盖返回根除合同自身外所有普通文件的`path/size/SHA-256` exact-set合同；离线验收必须复算整体集合和每项身份，而不只检查readback子树。生成ZIP仍须有独立归档超时。
- 实际仿真命令不得由README展示字符串或runner内另一套字面量隐式决定。overlay必须携带“一行一个argv元素”的LF-only命令合同，launch manifest冻结其SHA；runner复验后从该合同加载数组并原样执行，返回元数据记录同一SHA，离线验收与批准launch identity逐项核对。
- 正式命令合同必须显式传入`DUMP_VCD=0`、`DUMP_FSDB=0`和`TB_DUMP_FSDB=0`，不得依赖服务器Makefile当前默认值。launch manifest和argv合同必须直接冻结批准的编译宏、reserved-clock UCLI、SCA plusarg和no-archive目标；服务器不执行`make -n`文本门，实际Make/VCS调用是接口能力的权威判据。
- runner自身必须由install内独立内容寻址身份在启动任何预检/清理前校验，避免传输后脚本被改而仍生成一套“自洽”返回身份。验证前除run ID语法/枚举和`sha256sum`存在性外不得执行其他外部命令或文件系统变更；runner身份错误只向stderr返回，不得由不可信runner删除旧证据或生成自证归档。返回`config/`和`metadata/`只允许复制批准清单，离线验收必须对其执行exact-set比较，禁止整目录复制后由runner为额外文件自生成合同。
- runner必须为身份通过后的预检、清理、编译、仿真、归档各阶段建立统一错误收口；`set -e`、具备证据原语后的`mkdir/mv/rm/vcs`失败、未预期信号，以及已分类的tee/超时/watchdog/进程/marker/readback非零状态都必须映射为明确原因并产生run-ID隔离的最小失败归档，不得先生成成功形状的return ZIP再只靠退出码表示失败，也不得无报告退出。只有身份不可信或永久缺少生成证据所需的`rm/mkdir`原语时允许stderr-only退出，此时必须保持既有证据不变。

## 10. overlay、manifest 与 ZIP

正式 overlay 必须满足：

- 只含运行 package、内容寻址合同、runner、README，以及经批准的最小非 HDL runtime 文件；
- `.v/.sv`数量严格为 0，不含 symlink，不含绝对路径、`..`、旧日志、波形、`run/`缓存或服务器源码副本；
- `OVERLAY_MANIFEST.json`列出除自身外每个 payload 的相对路径、字节数和 SHA-256；实际集合与声明集合完全相等；
- manifest 记录 freeze ID、package manifest SHA、stage/observer/readback/launch identity、运行入口和预期返回名；
- ZIP 内 entry 数、路径、大小和 SHA 与目录重新独立核对，不能只相信打包脚本返回 0；
- manifest必须声明文本文件集合及其`line_ending=lf`合同；目录与ZIP审计都要求这些文件`cr_byte_count=0`，并拒绝未分类的可疑逐行文本。
- 同目录生成 `<zip>.sha256`侧车。侧车只用于传输完整性，不是仿真通过证明；服务器解压前执行 `sha256sum -c`。

### 10.1 历史revision与服务器结果归档

- 当前工作目录只保留一个最新待修/待发revision的package、overlay、ZIP、sidecar和自检报告；该revision撤权后仍可作为下一轮静态修复输入，直到新revision生成并接替。
- 从未上服务器实测的更早revision，确认错误已写入本规则和`.agents/history.md`后，删除其package、overlay、ZIP、sidecar、preparation/selfcheck和展开分析目录；不得为了“可能有用”长期保留同一数值payload的重复副本。
- 已上服务器实测的revision只保留原始返回结果ZIP作为不可变证据，并在`.agents/history.md`记录文件名、大小、SHA-256、执行终点和已确认错误；删除对应生成package/overlay及结果展开/派生分析目录，避免ZIP与完整展开树并存。若原始返回ZIP当前不在工作区，只保留已核验的外部SHA/错误记录，不以服务器输入包冒充结果证据。
- 数值freeze、typed request、config-bound preflight、官方encoder合同和下一revision明确依赖的输入不属于“服务器生成包”，不得因清理旧overlay而删除。删除前必须先列出精确目标并验证所有目标都位于项目工作区和指定artifact根内；删除后记录删除数量/字节数和剩余最新revision。

## 11. 高效检查分层

为避免低价值重复检查拖慢进度，固定三层，并把两轮交付自检设为发布硬门：

1. **日常修改**：只跑受影响生成器/runner 的定向单测、语法和最小合同检查。
2. **第一轮自检——受影响链路定向自检**：只运行本次代码变化实际波及的测试。runner身份/清理变化检查旧证据保护，readback变化检查完整install基线，数值生成变化才执行权威package重建/检查；不得因为文档或离线适配器变化重复运行无关的完整28-Bank生成。生成新最终revision时把已通过的定向结果汇总为`selfcheck_round1`，不把同一全量validator重复调用多次。
3. **第二轮自检——一次独立交付审计**：只在最终ZIP生成后执行一次，从ZIP及sidecar全新解包，复算entry安全、exact set、逐文件大小/SHA、LF-only和0 HDL/0 symlink；不重复模拟runner全部行为，也不维护第二份外部命令清单。输出独立的`selfcheck_round2`结果。

两轮结论必须均为PASS且指向同一ZIP SHA；任一FAIL时不得继续服务器步骤，修复后重新生成ZIP并把两轮都从头执行。两轮自检用于发现本地可证实问题，不冒充真实VCS/UCLI运行或G6/G8。

全量仓库回归仅在新冻结身份或正式发布边界集中执行一次。相同文件集的哈希/大小/exact-set 证据由一个阶段生成，后续阶段消费摘要，不重复遍历整个服务器源码树。

## 12. 发布检查表

只有以下项目全部为真才允许把 ZIP 标为当前唯一候选：

- [ ] typed request、preflight、freeze 和 package 属于同一 revision 身份。仅对byte-exact复用上游原生JSON的最小控制包，允许以“原JSON路径/SHA/commit + 正式双encoder + 具名W3 tensor/tile范围 + config-bound数值记录 + freeze manifest”代替项目派生typed request；manifest必须声明非全实例范围，不能外推batch/shape/其他slice。
- [ ] config-bound Golden/NDP P/D 全部 mismatch=0。
- [ ] JSON→bitstream→parsed evidence 关键字段一致。
- [ ] 每份JSON的config SHA、official encoder规范化逻辑SHA/行数/位宽、freeze副本和最终安装副本已逐项强绑定；未使用current revision的默认/fallback encoder目录。
- [ ] scratch、batch/shard、mask、barrier 和 output region 完整。
- [ ] 所有 SCA/SCA_D 段 parser-compatible 且 4 KiB 安全。
- [ ] runtime stage count 与 observer contract 分别正确，`Repeat_Num`非手填。
- [ ] 返回解析器按冻结observer mode走对应分支；fixed模式的三项计数进入required metadata，且存在最终mask全slice完成先于readback的机器证据。
- [ ] 新服务器快照的活动入口、端口、时钟和 TB observer 已审计；活动filelist/source物理路径、外部include数量和vendor树内容只作为provenance，不作为compile前硬门。
- [ ] runner 不锁服务器 Git/源码内容，且会清理本次编译缓存。
- [ ] runner自身份验证、ERR trap和完整命令门均早于任何证据清理；缺少任一必需命令时stderr退出且旧证据保持不变，命令门通过后的清理异常才进入归档。
- [ ] 合并后的静态install路径exact-set/普通文件类型通过，launch manifest声明文件的size/SHA和runner自身份通过；不重复预检`runtime_identity.json`，运行输出命名空间另行审计。
- [ ] runner已启用不可变TB现有的start-only日志宏，并按包内固定合同对已知高频日志使用只存在于本次临时运行目录的精确`/dev/null` sink；服务器启动不扫描TB源码，运行时未知日志/总量上限保护已通过行为测试；overlay/return无symlink，入口能力检查不比较服务器源码SHA。
- [ ] reserved-clock成功marker只能由force成功及低/高采样翻转产生；失败marker为0、成功marker期望精确为1。
- [ ] 受合同约束的非HDL附加Makefile只定义新的no-archive simulation target并复用服务器`SIMV/SIM_OPTS`；未定义或覆盖compile、sim、archive target，RTL、TB和服务器Makefile均未修改。
- [ ] preload、首Start、observer、readback和归档阶段均由有序状态机保护；重复/乱序/越界marker不算进度且立即失败，watchdog完成sentinel与退出状态均被主runner验收。
- [ ] 返回ZIP采用有单文件/总量硬上限的最小诊断allowlist，不递归复制全量`sim_results`、波形、simv/csrc或bank-frame全日志；失败态在已有gexec定向日志时保存有界副本，缺失不覆盖主失败；整体返回文件合同经exact-set/size/SHA复核。
- [ ] 仿真实际argv由launch manifest冻结的命令合同加载执行，返回元数据中的合同SHA与批准身份一致。
- [ ] overlay 为 merge-only、0 HDL、无 symlink/旧日志/绝对路径。
- [ ] manifest/目录/ZIP exact set、大小和 SHA 全部一致。
- [ ] `OVERLAY_MANIFEST.json`自身直接记录freeze ID、package SHA、stage/observer/readback/launch identity、runner路径与预期返回名，不只通过README或嵌套文件间接表达。
- [ ] package、overlay目录和ZIP entry三层文本审计均为LF-only，所有声明文本的CR字节数为0。
- [ ] runner bash 语法与受影响定向测试通过。
- [ ] runner的LF门已用真实Bash样本验证：纯LF通过，含CR失败且报告精确`cr_byte_count`。
- [ ] 若本revision修改了路径解析或ZIP解包代码，已定向验证绝对路径、`..`、重复entry和非普通对象；未修改时不重复执行畸形文件名测试。
- [ ] README 只给出一个版本化脚本入口、两个固定正式run ID（`run1`/`run2`）、两个互不覆盖的返回ZIP名和禁止手改项；runner行为测试证明`run3`在其他处理前失败。
- [ ] 服务器环境中预置与冻结策略同名的变量不会改变超时、路径或验收门；允许的`DIR_HOME`和`SERVER_RUN_ID`已经逐项列明；外部include数量不再作为策略门。
- [ ] `MAKEFLAGS/MAKEFILES/GNUMAKEFLAGS/MFLAGS/MAKELEVEL`在launch前被清除并有行为负例；`DIR_HOME`状态/值摘要和vendor解析结果进入run1/run2一致性比较。
- [ ] 第一轮生成链/合同自检与第二轮全新目录独立解包审计均为PASS，报告使用不同检查入口、未复用预计算摘要，且绑定同一ZIP SHA。
- [ ] 旧revision已撤销运行许可，并按10.1完成“未实测删除、已实测只留原始结果ZIP、仅最新工作revision保留生成包”的归档。

## 13. 服务器运行与回传验收

操作者只能：校验 SHA、把 overlay 内 `NDP_copy01/`合并到已有目录、分别执行`SERVER_RUN_ID=run1 bash RUN_SERVER_<REV>.sh`和`SERVER_RUN_ID=run2 bash RUN_SERVER_<REV>.sh`、回传两个原始结果 ZIP。不得 `sed`、手改 SCA/TCL、替换 HDL、补跑交互式 UCLI 或从旧包拷文件。

回传验收必须依次确认：

1. 两个ZIP路径安全、根目录不同，分别声明且只声明`server_run_id=run1`和`run2`，并绑定同一package/runner/freeze身份；两轮Makefile、TB、顶层filelist的逻辑路径、物理路径、大小、SHA-256，`DIR_HOME`状态/值摘要、vendor解析结果以及冻结的关键执行环境摘要必须完全相同，不同服务器源码或执行环境不得冒充重复实验；
2. 两轮各自的preload PASS数精确，模拟器/Make/tee/timeout状态明确；
3. 两轮各自的stage/observer/自然完成证据满足合同；
4. 两轮readback region各自为exact set，行数和128-bit文本格式正确；
5. 在入口provenance和关键执行环境一致的前提下，逐region比较两轮相对路径、行数、大小和SHA完全相同，稳定性门通过；
6. 只在稳定性门通过后重组28 Bank并inverse；
7. Golden、NDP和RTL的P/staged-D三方mismatch全部为0。

离线比较在读本地freeze前必须先验证其`freeze_id`和manifest SHA等于package冻结身份。最终报告必须显式保存`golden↔NDP`、`golden↔hardware`、`NDP↔hardware`三组结果；除inverse后的逻辑元素外，还必须对返回的完整物理P/staged-D与freeze物理参考做byte-level比较，inactive slot、padding和tail被改写也必须失败。

若失败，只根据最早可证实断点创建下一 revision。不得把后果当根因，也不得在服务器现场逐字段试错。

### 13.1 v10r5已闭合的数值基线（runner已撤销）

- v10r5历史结构为12个runtime stage、5对fixed observer、434个preload运输段和168个readback运输段；最终两阶段是同一requant shard的`non_observer_slices`后接`finish_slice_only`，最终mask为`0x0000002`。该结构后来由v14重新推导，不能把历史计数当作新revision先验。
- v10r5历史requant合同SHA-256=`cb5f54d068f390ae89be874f9fb0cff0aac603a836eff9347305e48becdfe060`，freeze ID=`73d4081dddffc541067ee028d55b25a7acb245e042733ea6ef18a7afd380fce7`，manifest SHA=`0426311e8e3ffe52d7c59bceac224022460404f69c411ca7f3b33afe93c012f6`。旧package/runner永久禁止执行；v10r6～v10r8身份和清理记录只看`.agents/history.md`。

### 13.2 失败首断点与因果排序

- 回传分析必须按`编译/入口→preload写入与读回→execplan启动→首个及后续stage→observer完成→readback→自然退出/归档`顺序寻找最早失败，不得从终端最后一条错误逆推首因。
- 屏幕曾停在某个AXI burst不能证明AXI卡死；最终日志若给出冻结期望数量的连续加载索引、逐传输PASS和总完成摘要，就必须把preload判为通过，并从后续stage重新定位。
- 已发出全部目标slice的`Start_Comp`但没有任何completion时，应继续检查输入读取、输出读改写请求、write-data握手和最后有效事务。像v10r3这样出现确定性P读回和P写请求、但write-data为0且所有slice未完成的情况，首断点是计算链的输出write-data生成之前，不是TB observer或post-run readback。
- 总墙钟、CPU占用和ZIP大小都不是进度证据；墙钟命中只证明runner停止等待。只有模拟器自然结束marker、阶段/observer合同和完整readback共同成立时，才允许把长时间运行解释为完成。
- 如果返回包没有冻结的服务器RTL内容身份，只能把RTL版本记为未锁定来源；已证明的错误码流仍必须先修复，但单次失败不得宣称数学上排除了所有并存RTL问题。只有使用批准码流身份的新revision通过或在同一精确断点复现后，才能进一步收敛因果边界。

### 13.3 v12历史修复边界（已撤权）

- v11/v12只作撤权输入和反事实证据，禁止原地修改、改名或继续执行。路径中性candidate、freeze新空目录/exact-set/ID重算、真实GNU awk行为和独立Round 1等有效要求已并入第4、9、11、12节。
- 原生`main.py --profile server`、`tools/generate_conv_hardware_execplan.py`和`tools/build_ndp_server_overlay.py`仍是candidate、package和overlay唯一入口；旧身份、ZIP/runner SHA和撤权原因只在`.agents/history.md`追溯。

### 13.4 v14数值身份与诊断状态（正式发布资格已撤销）

- typed request：`artifacts/w5/hwop-0004-00/v14/execplan_request.json`，SHA-256=`a4d6e56ab85271cae8870a3ed667f3c7aa24dee9bc5bc9b4ffefe97c553e4990`。
- 原生本地生成身份：commit=`056b1c3c08b24e098636615d9001e8a974beb09f`，source-tree SHA-256=`ce7fcb683f2b816ec3bbc06dd4ac0f982c3b3dfcd5f52bee893625b88ac190e6`。该commit只用于本地candidate/freeze追溯，服务器不得要求Git、`.git`或commit验证。
- candidate ID=`d7d1f57d9f113ad500cf2008fe93f773a751e5f31f07f01b19b29b4b247984ad`，manifest SHA-256=`2b6e3f12639da0f9551faa005cf207247c5ea9d660c3d69c5d623fd47eea2c47`，revision=`v14-candidate-02`，9个record，独立A/B完全一致。
- config-bound preflight SHA-256=`fed3d9f2f986b5d8d0b4da1138dec2e58aab0c2602d7b2aa3ee334f4b9c66cb7`，Golden/NDP P/D mismatch=0。
- freeze ID=`052270e61d7e8adf7216e807b34cb612bd3ddb543ca755a9d9d294aee6cbbb7a`，manifest SHA-256=`83d0b05bec72f10ab5356ca3d47cd1e39c72173f21ff3d8b317735b05140408c`，511个声明文件。
- requant encoder contract位于freeze的`configs/requant/encoder_contract.json`，SHA-256=`55f07956c3a6bbf7bfaa8d9c363e49d48a13b5f074d7ac43d3ff87fac1d940fe`；8个record各自绑定config、A/B official输出、parsed evidence和mapping semantic摘要。
- package manifest SHA-256=`0608c74065cad019119aa73de33a1b5ef137210b86d977f53020130a53da6c78`；12个runtime stage、`Repeat_Num=5`、314行128-bit execplan、28个Bank、434个preload transport segment、168个readback transport region、84个semantic readback region。
- 4 KiB报告对433个语义transport确认169个触发、264个不变；继续按“可能存在且本包真实触发”处理，后续若发现前提不成立必须立即定位并新建revision。
- runner SHA-256=`d5a4b65e65b0644dc0a63189fe9619fc2d244120ac087c30be839f11601b383b`。runner不含Git调用；启动命令能力门覆盖其实际使用的`awk basename bash cp date dirname find grep head ln make mkdir mkfifo mktemp mv od readlink rm sed sha256sum sleep sort stat tail tee timeout tr vcs wc xargs zip`。
- 历史最终ZIP为2,989,930字节、289个entry、0 HDL，SHA-256=`c95435f01d4a6c1b719334d80762ee7a137efd76fb2dd5e370d07e314ab1ae1a`；本地输入副本已按归档规则删除，只保留身份记录和服务器失败证据。
- Round 1报告SHA-256=`1bf7d6c04e607bed2dec68cf058788677ff691c3d158f8be4231fdead066c67f`，Round 2报告SHA-256=`00ebaef039f30c3a0bd62b2a7da614bd4829cc9dd6fcbf7bfea3b2f6c7d85b8d`；它们当时均为PASS并绑定同一ZIP/runner，但未覆盖本次新增的三类行为缺口，不能继续作为发布授权。
- v14已在服务器执行诊断性run1并于preflight失败，服务器生成`run/sim_results_v14_run1.zip`；外部回传SHA-256=`6c103919c1258e241751dc8e4331f63ef35694c5a664b4c5c174451db337fb72`，`preflight_report.json`的`reason=server_filelist_member_outside_root`，detail显示活动filelist物理路径`/home/liuyk/Documents/Trassic2.0_RTL/code/NDP_rtl/filelists/NDP_Top_phy_filelist.f`位于`/home/panqs/ndp/NDP_copy01`外。run2未执行。不得原地修补或重跑v14；后续revision已经删除该过度校验。simulation/hardware numeric均未通过，G6/G8保持false。

### 13.5 v15历史本地身份（正式发布资格已撤销）

- v15只读复用v14 typed request、freeze ID=`052270e61d7e8adf7216e807b34cb612bd3ddb543ca755a9d9d294aee6cbbb7a`和freeze manifest SHA-256=`83d0b05bec72f10ab5356ca3d47cd1e39c72173f21ff3d8b317735b05140408c`；未运行candidate/preflight/freeze生成器。
- v15 package manifest SHA-256仍为`0608c74065cad019119aa73de33a1b5ef137210b86d977f53020130a53da6c78`。`numeric_invariance_report.json` SHA-256=`6cbb05727a379e546fe728e59073729bdd642acc5d687b71a7c6a80501e59f12`，证明manifest及其声明的bitstream、execplan、Bank_data、stage/mask/barrier、SCA/SCA_D、readback和4 KiB身份与v14逐项一致。
- 服务器runner SHA-256=`4680f1409769fdc26821927835630fe1e67a3a350d97a0fba04379682354eeb7`；只要求三个逻辑入口可读并记录逻辑/物理路径、大小、SHA，不递归解析服务器HDL/filelist，不扫描TB源码，不调用Git。实际命令能力门为`awk basename bash cp date dirname find grep head ln make mkdir mkfifo mv od readlink rm sed sha256sum sleep sort stat tail tee timeout tr vcs wc zip`。
- 历史最终ZIP为2,986,153字节、289个entry、0 HDL，SHA-256=`d81ed87db41d5c64c8d0a44209c4d2cc08baaa6f24962da2f00b37e7dad1fc27`；本地生成副本已清理。
- Round 1报告SHA-256=`34f7ff1a21ed6c9369293f25958c197760ef9a0995f291d18d47708f54e00917`，Round 2报告SHA-256=`3f4f4211b5af16555f3b7b4a602b0e9b88ce6e4df9de79ba3c8be757737ada63`；均`passed`并绑定同一最终ZIP SHA。Round 2重新确认28 Bank、314行execplan、12 stage、`Repeat_Num=5`、434 preload、168 readback和9个bitstream binding。
- 4 KiB报告仍为433个语义对象中169个触发、264个不变；服务器启动不重复解析该语义，最终ZIP独立审计会重算并核对报告。
- v15尚未在服务器运行，且因13.5所列身份未覆盖2026-07-21新确认的runner顺序、双跑provenance和实文件不变性缺口，正式发布资格已撤销。不得上传、执行或原地修改v15；simulation/hardware numeric和三方P/D均未完成，G6/G8保持false。

### 13.6 v16历史本地身份（正式发布资格已撤销）

- v16只读复用v14 typed request、freeze ID=`052270e61d7e8adf7216e807b34cb612bd3ddb543ca755a9d9d294aee6cbbb7a`和freeze manifest SHA-256=`83d0b05bec72f10ab5356ca3d47cd1e39c72173f21ff3d8b317735b05140408c`；package manifest SHA-256仍为`0608c74065cad019119aa73de33a1b5ef137210b86d977f53020130a53da6c78`。
- `numeric_invariance_report.json`使用schema 0.2，在比较相同manifest前分别对v14参考包和v16候选包执行权威actual exact-set/size/SHA复验；报告SHA-256=`d6850da79933fdc5ae5e8f72636e2a4a1961c9626613447bd7504d2ed74685a8`，状态为`exact_package_manifest_and_declared_file_identity_preserved`。
- v16 runner SHA-256=`28eea621b304add4867fb773f7b05817ee849dfcd60fa681b4f13d0a734cbf11`。最小run-ID检查后立即验证runner内容寻址身份，成功前不创建、删除、移动或覆盖任何证据；损坏runner行为负例证明同run ID旧返回目录、ZIP和source inventory逐字节不变。
- runner只要求三个逻辑入口可读并记录逻辑路径、物理路径、大小、SHA，不递归解析服务器HDL/filelist，不扫描TB源码，不执行`make -n`文本门，不调用Git。watchdog对readback执行live首次到位全文验证和退出后全部终检；runtime日志执行1037个固定sink、未知普通文件拒绝和1 GiB总量上限。
- 历史最终ZIP为2,987,442字节、289个entry、0 HDL，SHA-256=`3d4fe99866aa00a0b85caf208fc57db61793d709e7b3a033697f8fb6baefd031`；本地生成副本已清理。
- Round 1报告SHA-256=`66d413f34a7c69a24451e5af3f3bb3b30e93e295464552b619a162fedb83bd23`，Round 2报告SHA-256=`f42d9acf5473f044140601159a5044e312c14ab993d159be2a23518078f6cdf9`；均`passed`并绑定同一最终ZIP SHA。Round 2重新确认28 Bank、314行execplan、12 stage、`Repeat_Num=5`、434 preload、168 readback、9个bitstream binding和0 HDL。
- v16从未在服务器运行。后续故障注入确认清理异常收口、合并态exact-set、Make环境、`DIR_HOME`双跑provenance和报告不可覆盖仍有缺口，故不得上传、执行或原地修改；其生成制品已在v18接替后按第10.1节清理。G6/G8保持false。

### 13.7 v17历史本地身份（正式发布资格已撤销）

- v17只读复用同一v14 typed request和freeze；package manifest SHA-256仍为`0608c74065cad019119aa73de33a1b5ef137210b86d977f53020130a53da6c78`，数值内容未改变。
- v17修复了v16确认的runner顺序、清理故障归档、静态install exact-set、Make环境隔离、`DIR_HOME`provenance、manifest原始字节比较和报告冲突问题，并完成过Round 1/2。
- 最终总览发现包内README未完整表述上述新增运行合同。该问题不改变数值或正常runner行为，但规则、实现、交付说明三者不一致时不得发布；因此v17未上传、未执行、不原地改写，生成制品已在v18接替后清理。

### 13.8 v18历史本地身份与真实run1停滞（正式发布资格已撤销）

- v18只读复用v14 typed request、freeze ID=`052270e61d7e8adf7216e807b34cb612bd3ddb543ca755a9d9d294aee6cbbb7a`和freeze manifest SHA-256=`83d0b05bec72f10ab5356ca3d47cd1e39c72173f21ff3d8b317735b05140408c`；package manifest原始字节SHA-256仍为`0608c74065cad019119aa73de33a1b5ef137210b86d977f53020130a53da6c78`。
- `numeric_invariance_report.json`使用schema 0.2，分别权威复验v14参考包和v18候选包的实际exact-set/size/SHA，再比较manifest原始字节和声明记录；报告SHA-256=`c8ce8d40411bcbf77d82128ca07cfeef68059ba0e35f77927f338ed12ac8a23d`。
- v18 runner SHA-256=`db744be4f84d4b105e5f10838d7980d9725c612f5aef3a04935017859df398ae`。最小run-ID检查和自身份验证早于任何证据变更；随后安装失败函数/ERR trap、完成命令门，再执行本run清理。静态install执行actual exact-set；Make控制变量在内容寻址launch前清除；三个入口和`DIR_HOME`/vendor解析只作非阻断provenance。
- 最终ZIP=`artifacts/w5/hwop-0004-00/v18/server_overlay.zip`，2,989,114字节、289个entry、0 HDL，SHA-256=`2e669527ccf426c6f940f9f706b41406eb93257f9b722d4af927503e656c25ad`；sidecar为同目录`server_overlay.zip.sha256`，服务器完整性不依赖Git。
- Round 1报告SHA-256=`5013282e87972d2b407481b1fe909727666176c32d75f839d3acfc74be1c922f`，20个行为用例全部PASS；Round 2报告SHA-256=`d344bb00a8fe4ede4b3e7574e367e2a85f6b6a3cd9d73e32751a988b8b8f54d0`，从最终ZIP全新解包复算PASS。两轮绑定同一最终ZIP SHA，并确认28 Bank、314行execplan、12 stage、`Repeat_Num=5`、434 preload、168 readback和9个bitstream binding。
- v18已在服务器执行run1并完成全部preload，进入首个accumulate stage后fixed observer长期停在`0/5`；操作者手工终止并回传`sim_results_v18_run1.zip`（86,794 B，SHA-256=`2f33f34f626b2b1fe71502da5fe10e87eb67fb21d3a13404c528fbc130dbfeca`）及`v18_run1_deadlock_extra_1784611151.zip`（217,860 B，SHA-256=`6b833a69ae92e9fb9c9147d783d01ece803e7c4f98c3c0d62721b8824c574dc7`）。该运行不是自然完成，run2禁止执行。
- 静态RTL/encoder反查确认v18 accumulate的bias调度错误：stream3只由Kblock分支产生两个运行期事务，buffer4 JSON lifetime=1只产生一次SA读取；目标SA outbuffer每个Q8×K8输出tile需要四次bias握手才能初始化完整16项psum组，第三次读取时会遇到无效tag并在SA输出前停滞。下一revision必须建立新的JSON、official encoder双跑、parsed evidence、typed request、config-bound preflight、freeze ID和package；不得继续声称v14/v18数值身份不变。G6/G8保持false。

### 13.9 v19历史身份、真实run1与撤权边界

- v19只修改已确认的accumulate bias tile调度、buffer4生命周期及其语义/encoder身份链；未修改RTL/TB，未增加服务器source/filelist扫描、Git门、`make -n`或新的运行时哈希层。runner沿用v18之后的必要模板修复和精简校验口径。
- typed request SHA-256=`105f2bc78556f7ae8a33cd2c20bb3b6e63a4acc40e1138ba90a125b12a577e06`；native candidate ID=`d5f6af19413919a72d761f99b61d35afdee5278e172a363f28055d937dd37898`，manifest SHA-256=`5146329288431fb970b26e35b70a93c2955515753430026327f36d76fe37589f`，validation SHA-256=`7ddd85d4b3afa9ce08385d588031ff9881fb1a79e7982a753d97a1db9dcc0764`，9个record独立A/B一致。
- config-bound preflight SHA-256=`98febe58038352eefff14b2c88c19e332cdf3fdcf1531a16e91137c5ab0debbc`且Golden/NDP P/D mismatch=0；freeze ID=`71686cf225194fbe6f9a0db73e7adf515a02ce252598ac58f6e5090793470b27`，manifest SHA-256=`6da4381275cf1a0e724451eea66e0035fab3e53e13b259af80eb875e77fe3f26`，512个声明文件。
- package manifest SHA-256=`5d118970d4831074da8c8dfee57abdadb48d6bc402bf4aea93864b5dcffef636`；schema 0.3数值不变性报告SHA-256=`08a6457ee3c8f8f0fa179feb06f81f3df22b6009ea6be771571efcdd303ad1de`只证明264个数值payload/runtime文件保持不变，不把新的配置/bitstream/execplan误称为v18同一身份。
- runner SHA-256=`1ae95b832c4273513c152ae453164346563fb2064c15c23255da44b5a7d9d8ee`；最终ZIP为2,989,053字节、289个entry、0 HDL，SHA-256=`0874e8eeb8495ca46e3ddda54e1273c05e5c9a10b78c468e4584ba33398f06b2`。Round 1报告SHA-256=`164a13a7b8fda7dd0e09799e9d3d4e441ec407658a8280a8db516ef48f5df6b8`，20个行为用例PASS；Round 2报告SHA-256=`eec85fbd1cc2a5fe98e57a028108c1dac73b8f52545f26607c562670f4683dc2`，从最终ZIP/sidecar全新解包审计PASS。
- v19真实run1完成434/434 preload、`Exec_Length=314`和首波28个slice的`Start_Comp`，fixed observer随后保持`0/5 pending=1`约7202秒，由watchdog以`phase_watchdog_stalled`终止；主返回为86,784字节、SHA-256=`89bd374c3f357e32857d90bfe511b628fdbe3d2166d09b789165722d95b8501b`，没有stage完成、自然退出或readback。
- 补充gexec ZIP为2,845字节、SHA-256=`b9b58afabb55f7166417aead35acdb6550ed6d992fec9310f185c6bf09c6be7c`；279条有效命令与v19首波execplan展开逐条一致。v18→v19的28条Load Config和28条READ_STREAM3变化都已实际送达，故不能归因于旧码流混装、命令漏发或global executor未启动。
- v19永久撤权并禁止run2。现有证据只把断点缩小到Start之后、任一slice completion之前，不能唯一判定READ_STREAM3、buffer4、SA输入/outbuffer、buffer5或WR_MSE0中的哪一级失效。当前没有Conv服务器候选；后续若改变Conv配置、调度、runner或证据合同，必须建立带版本号的新revision，禁止原地改v19。独立MaxPool包不得复用v19身份或被其故障外推。

### 13.10 node-0002 MaxPool最小服务器包当前身份

- 当前MaxPool候选只覆盖正式W3样本0的channel `0:16`与`16:32`两份真实tile，分别运行在slice0/1；它复用上游原生`maxpool_config_16_112_112_stride2_padding1.json`的精确字节（SHA-256=`a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`），不改写源JSON。范围声明为两tile控制链验证，不冒充batch16/28-slice三轮全实例。
- hardware package位于`artifacts/w5/native_json_maxpool/v2/hardware_execplan_package`，manifest SHA-256=`5ddd41120b89cad426bd50ea314316246030832431a26332ab9fd6a10a809476`，freeze ID=`98e1c0faf2ff1edd6c9664bcd8ce29963b8a147f2b6e25c11029b7f564bb728b`；权威检查确认2个runtime stage、5行execplan、11个preload、4段readback、2个bitstream binding与2份Bank_data。
- 最终zero-HDL overlay为`artifacts/maxpool_server_v1.zip`，640,593字节、31个entry、SHA-256=`a4b3e31cdc3615988eba12ee77c5f1904cbba3c5b66e1a3d39158407603265b8`。Round 1行为自检与Round 2全新解包独立审计均PASS；runner为`RUN_SERVER_MAXPOOL1.sh`，安装名`node0002-maxpool1`，只允许run1通过本地回传验收后再执行同一不可变包run2。
- 本地回传入口`tools/analyze_native_json_maxpool_return.py`复核ZIP安全、whole-tree/config/runtime身份、自然完成、固定observer、11次preload及4段readback，并把两份50,176-byte输出逐byte比较W3 golden。当前尚无真实服务器返回，G6/G8保持false。

### 13.11 node-0005 3×3 Conv分支服务器包身份

- 该候选绑定`node-0005/hwop-0005-00~01`，不是node-0004的后续revision。typed request SHA-256=`cc8def589770cb3315e19cdb79663083e85f9ed88b5d828c213f592a269d35ee`；native candidate ID=`60e73f9eec3fd4303126f2c73e490af61a0cc9847159ff091b21271e4ffee969`，9个accumulate/requant record均独立A/B一致。
- 批准freeze位于`artifacts/w5/hwop-0005-00/senior3x3-v2/hardware-freeze-native-02`，freeze ID=`8725221c3986c413b9c827dc9a3fbe96f1e3bb3de637a25c9453f1b381d62189`；package位于同级`hardware-package-native-02`，必须权威复验12 stage、314行execplan、28 Bank、462 preload、168 readback和9个bitstream binding。
- 最终交付是`artifacts/w5/n5v2_overlay.zip`及同名`.sha256` sidecar，安装名`r50-n5-v2`，revision=`v2`，0 HDL。ZIP大小3,734,347字节、345个entry、SHA-256=`b134b872a114d2d52f4c37f9ce7246f37fbf17321eb78bfe3794a065d9b87fcc`；Round 1/2报告分别为`artifacts/w5/n5v2_selfcheck_r1.json`和`n5v2_selfcheck_r2.json`，两者必须绑定这一个最终ZIP身份。
- 服务器只执行不可变最终ZIP；run1自然完成并完成回传数值验收前不得执行run2。当前没有真实target输出，simulation/hardware numeric及三方P/D未闭合，G6/G8保持false。

### 13.12 DeepSeek Ring4 dg3服务器包身份

- 新拉取的上游`ndp-sim@ec12424516ae0304228dd2321d4e604fe225e04e`中，原有`prefill_gemm_ring_4slice.json`的SHA-256=`6a2ca9f2edd2e9c7b8ebbb558a84dd23c8e583781f8a8ac01c213b78c6737e91`，原始字节未改写。正式使用上游`run_all_slices.py`独立生成slice0～3四份互异配置，A/B运行的generated JSON、mapping、parsed和128-bit输出逐项相等。
- hardware package位于`artifacts/w5/deepseek_ring_gemm_control/v2/hardware_execplan_package`，manifest SHA-256=`81488d01d0ca79edd61f92bd1e4a9efd51d69db3b0992904682d7b8f06db6bbc`；4行execplan只允许`Clock 0xF → Load 1/2/4/8 → Start 0xF → Barrier 0xF`，17个preload、4个readback、4个bitstream binding。零输入控制测试先把四个D区域填入`0xA5`哨兵，未执行或任一片未写回不能以初始零值伪通过。上游未保存硬件trace的原输入张量，因此本包不声称原trace数值逐位重放。
- dg2因Round 2旧审计器不识别每片generated-config身份链而被拒绝，已永久撤权，禁止上传/执行/补报告。独立审计现在只对新Ring4 status显式核对base JSON、四个generated JSON摘要、official encoder/install全字段身份、slice ID、四个singleton mask和四个互异逻辑码流。
- 最终交付为`artifacts/w5/dg/dg3_overlay.zip`与sidecar，50,367字节、34个ZIP entry、0 HDL，SHA-256=`8be435b7d9b7e9b46208c0d5041995d30136bff71d0fbe13a39ba556823535c2`。Round 1报告SHA-256=`16d8bbbebdc008ec2094de9b70d396aaf7500d4104d31698044496015642d616`，Round 2报告SHA-256=`7556cffa2274a17f7ee5cc9f28412489756d92f212b92b392066a33e06bfcb58`；两轮均PASS并绑定同一ZIP。
- 服务器只先执行`SERVER_RUN_ID=run1 bash RUN_SERVER_DG3.sh`；run1必须经`tools/analyze_native_json_ring_gemm_return.py`本地验收通过才允许run2。当前尚无dg3真实服务器返回，G6/G8保持false。
