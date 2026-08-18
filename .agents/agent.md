# ResNet50 INT8 项目稳定入口

最后更新：2026-08-13（observer-only 宽因果回传与全波形关闭）

本文件只保存项目级稳定边界。当前任务、blocker 和下一步只看 `.agents/plan.md`；
生成规则看 `.agents/rules/`；完成证据看 `.agents/task_records/`；旧版本、旧命令和
被取代结论看 `.agents/history/`、`.agents/history.md` 与 `.agents/archive/`。

## 1. 文档唯一归属

| 信息 | 唯一活动入口 |
|---|---|
| 生成前读什么、何时停止、E0～E5 和回归分类 | `.agents/rules/生成前必读索引.md` |
| 算子 JSON、物化回环、mapping/execplan/provenance | `.agents/rules/算子配置规则.md` |
| LC/MSE/Buffer/SA/GA/N2N 字段语义 | `.agents/rules/NDP硬件字段语义.md` |
| 服务器包、单命令、身份、回传和预算 | `.agents/rules/服务器测试包生成规则.md` |
| 会话角色、唯一活动 owner、转接胶囊和主线路由 | `.agents/rules/会话转接与所有权规则.md` |
| 算子特有公式、布局、反例和发布门 | 对应算子专项规则 |
| 当前任务和顺序 | `.agents/plan.md` |

创建、修改、派生、重建或发布 JSON、mapping、bitstream、execplan、SCA/SCA_D 或测试包
前，必须从“生成前必读索引”重新选择本轮相关资料并保存读取收据。本文件不复写这些规则。

活动规则的 exact-set、分层、职责、读取 profile 与 SHA 收据由
`contracts/active_rule_registry_v1.json` 机器登记；`.agents/rules/` 中不得出现登记集之外
的 Markdown。`.agents/history/rules/README.md` 是旧规则统一入口，历史文件默认不读、
不参与生成，也不能由旧 task record 的链接重新激活。

涉及服务器包生成、共享构包基础设施或正式 return 闭环的会话，在完成本节角色必读后使用
项目 Skill `.codex/skills/resnet50-server-package-flow/SKILL.md` 编排步骤。Skill 只负责让会话
按顺序读取 current registry、聚合廉价检查、调用硬门和形成回执；活动规则与机器 validator
仍是权威，Skill 不复制或覆盖其语义。主线向已登记 family 派发这类工作时，必须先从 current
owner registry 解析唯一 ACTIVE persistent owner，以 thread-message 发送给该 owner，并生成
`server-family-dispatch-mode-binding-v1`；不得用临时 subagent/child 替代已登记 family role。
该绑定和已选诊断模式只约束激活后的 later fresh 包，不追溯 HOLD、重建、修改或旋转激活时
已经 current/in-progress 的包。

### 1.1 会话角色与必读规则矩阵

每个会话开始一次任务或收到 handoff capsule 后，先完整读取“共同必读”，再只读取本行的
角色增量；派发单可以在本行基础上继续缩小，但不得省略本行文件。未列出的其它算子族规则
默认禁止阅读，避免把历史 workaround 或其它族字段误带入当前生成。每次实际生成前仍须按
`生成前必读索引.md` 对 changed surface 做一次增量选择并记录 current bytes/SHA。

| `role_id` / 会话职责 | 共同必读 | 角色增量必读 |
|---|---|---|
| `mainline.control` 主线控制面 | `agent.md`、`plan.md`、`生成前必读索引.md`、`会话转接与所有权规则.md`、`contracts/current_session_owner_registry_v1.json` | `算子配置规则.md`、`NDP硬件字段语义.md`、`服务器测试包生成规则.md`、`整网测试收敛优化专项规则.md`；只有裁决某族时才加该族规则 |
| `family.gap` | 同上共同必读 | `算子配置规则.md`、`NDP硬件字段语义.md`、`服务器测试包生成规则.md`、`GAP_int32_mac_bypass_rules.md`、`精确UINT8量化尾专项规则.md`、`最小双Stage生命周期规则.md` |
| `family.conv.serialized` / `family.conv.native` | 同上共同必读 | `算子配置规则.md`、`NDP硬件字段语义.md`、`服务器测试包生成规则.md`、`INT8_SA点积专项规则.md`、`RequantizeUint8算子配置规则.md`、`精确UINT8量化尾专项规则.md`、`最小双Stage生命周期规则.md` |
| `family.qlinearadd` | 同上共同必读 | `算子配置规则.md`、`NDP硬件字段语义.md`、`服务器测试包生成规则.md`、`QLinearAdd算子配置规则.md`、`精确UINT8量化尾专项规则.md`、`最小双Stage生命周期规则.md` |
| `family.dequantize` / `family.view` / `family.requantize` | 同上共同必读 | 三份公共生成规则（配置、硬件字段、服务器包）以及且仅以及目标族规则；跨两 stage 时再读 `最小双Stage生命周期规则.md`，量化尾适用时再读 `精确UINT8量化尾专项规则.md` |
| `infra.server-package` 公共构包/observer/return 基础设施 | 同上共同必读 | `服务器测试包生成规则.md`；只有实际修改 workload/config consumer 时才读 `算子配置规则.md` 与 `NDP硬件字段语义.md`，不得读无关族规则 |
| `optimizer.whole-network` 本整网收敛优化专项 | 同上共同必读 | `整网测试收敛优化专项规则.md`、`服务器测试包生成规则.md`；只有做 config causal audit 时读 `算子配置规则.md`，会话换届期间读 `会话转接与所有权规则.md`，默认不读任何族规则 |
| `consumer.human-json` 人工 JSON 消费 | 同上共同必读 | `算子配置规则.md`、`NDP硬件字段语义.md`、`服务器测试包生成规则.md` 与当前唯一目标族规则；不得读取或修改其它族资产 |

`role_id` 不在表中时必须先由主线把它归入最近的稳定职责并写入 owner registry；不得自行
扩张成“全规则会话”。`WAIT_RTL_FIX`、`HARDWARE_CAPABILITY_BLOCKED` 或 dormant 角色仍按
所属 family 行读取，但只做只读状态核验，不因读取规则自动获得构包、服务器或 RTL 权限。

稳定文档只能各拥有一类事实：

- `agent.md`：唯一入口、权限边界、角色与协作纪律；
- `plan.md`：当前状态、blocker、in-flight identity 和下一步，不保存完整历史；
- 公共规则：跨族配置、硬件字段、服务器包或会话转接合同；
- 原语/族规则：只保存该原语/算子的稳定语义和停止门；
- `task_records/`：已完成动作及证据；`history/rules/`：停用或被取代规则原文。

同一个 `CDA-*` 规则 ID 只能在一个活动规则中定义；其它文件只能引用。版本号、package
SHA、某次 return 结果、当前 blocker 开闭和一次性用户授权不得写入活动规则。确需改变
稳定语义时，先明确唯一 owner，再窄幅修改该 owner 文件并刷新 registry，禁止复制同义
段落到多个专项规则。

## 2. 事实优先级

冲突时依次采用：

1. 用户本轮明确指示与授权；
2. 锁定的活动源码、README、真实生成输出及其直接消费者；
3. 与 package/workload/RTL 身份绑定的服务器原始回传；
4. 用户授权且身份固定的参考配置；
5. 机器合同、活动规则、当前计划和历史记录。

项目文档是可修正总结。参考配置正确、派生配置正确、包结构正确和服务器 E4/E5 是
四个独立结论。

## 3. 工作区角色

| 路径 | 稳定边界 |
|---|---|
| `ndp-sim` | 活动原生工具链；身份锁定，checkout 默认只读 |
| `ndp-sim-ref` | 只有专项合同明确授权时才能在哈希门下使用 |
| `jsons` | 用户授权参考；不得伪装成活动原生产物 |
| `tools/`、`resnet50_pipeline/`、`contracts/` | 项目验证、typed lowering 和机器合同 |
| `artifacts/`、`server_returns/` | 历史身份只读；新实验使用全新路径 |
| `NDP_copy01` | 本地服务器入口与 RTL 参考；真实 VCS 在 Linux 服务器 |

项目补丁只安装到哈希绑定的隔离副本。来源、base commit、源码 SHA 或 patch manifest
不匹配时立即停止。

## 4. 不可越过的边界

- 默认禁止修改任何 `rtl/` 目录内的文件；功能 RTL repair 必须取得用户本轮明确授权。
- `rtl/` 外的 TB、observer、runner 只能按服务器规则做可关闭、非驱动、身份绑定的
  测试修改，不能改变 DUT 激励、握手、时序或完成条件。
- 所有可能进入 DUT simulation 的 next-fresh 服务器包必须显式二选一：默认
  `OBSERVER_ONLY_WIDE_CAUSAL`，或用户/主线按包选择的
  `TB_VCD_BOUNDED_CAUSAL_CONE`。两者不得同时作为 bulk evidence；原 observer-only 生成、门禁、
  回传和分析路径保持不变。
- 两种模式的 actual compile/sim profile 都固定为
  `DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0`。VPD、FSDB、UCLI direct-VCD、vendor query、
  full-top 无界 dump 永久禁止。可选 VCD 只能由 package-local TB 标准
  `$dumpfile/$dumpvars/$dumpon/$dumpoff/$dumpflush` 产生并回传本机可直接读取的普通 VCD。
- 两种模式都必须由 current source-bound catalog 覆盖足够宽的**真实 DUT 信号**因果域：至少覆盖
  clock/reset/stage、producer、queue 入/出与占用、request/valid/ready/accept/backpressure、selected
  port/bank/lane、internal state/match/clear、output/wdata、terminal/finish/formal-D；每个不适用角色须有
  exact 机器证明。observer 自己重算的 expected equation 不能替代实际 net，也不能作为 RTL 错误的唯一
  依据。
- observer 模式使用本机无需 vendor 工具即可读取的 signal-id catalog 与分块 4-state 事件记录；保留 exact
  time、sequence、width、0/1/X/Z transition、end state、仿真时间心跳和 partial-exit live record。
  100,000,000 bytes 只是 observer evidence aggregate 的软偏好：超出只告警并继续完整回传，禁止
  hard cap、截断、采样、head/tail 化或按大小删除。
- VCD 模式必须覆盖 FIRST_DIVERGENCE 上游一层、当前边界、下游一层、状态持有/清除和全部已知候选，
  绑定完整 candidate×boundary 矩阵；不得用 full hierarchy 或 memory array 冒充因果锥。100,000,000
  bytes同样只是软告警。默认独立安全线为60分钟墙钟、8GB VCD增长投影、10GB return投影、3×30秒
  sim-time冻结和磁盘/写入/配额失败；这些只触发close/flush后的PARTIAL，不截断已写VCD。
- 本族首个VCD诊断round必须绑定当前第三轮参考和合理信号量范围，但数量只是软下限/上限；偏离范围
  写明理由并确认后可告警通过。HIGH候选zero-hop direct-driver是强目标而非计数硬阻断。后续包精确绑定
  predecessor、signals added/removed/unchanged及candidates preserved/closed/new；删signal记录理由、
  `HIGH/MEDIUM/LOW`置信度和受影响候选，LOW默认保留，HIGH/MEDIUM可按工程判断删减。
- VCD 因果平台早停只有在owner-clock与sim-time仍推进、全部qualified counters、完整因果状态和global
  progress witness均稳定、catalog/matrix完整且无未决X/Z时才可成立。global witness仍推进时禁止局部
  早停；达到1048576 cycles只标suspected，4194304 cycles后dumpoff，另给262144 cycles轻量grace，
  随后TERM→wait→KILL/reap。非自然退出不得提升natural terminal、正式D、E4或E5。
- VCD模式的outer runner只能消费共享runtime evaluator的机器决定，不得复制plateau/freeze阈值；
  append timestamp推进和suspected-only都必须继续。finalization前须把quiescent archive的VCD
  SHA/bytes/最后timestamp与final runtime完全绑定，并通过advance/suspected/full-plateau/true-freeze
  四态exact packaged-helper回放；未flush、未close、未reap或runtime不完整固定fail closed。
- runner 仍须以 child-subreaper、fresh session/process group、内部 timeout 和 TERM→wait→KILL/reap
  监督完整 simulator tree，并区分 host liveness 与 simulation-time progress；归档前须关闭/flush
  当前模式的evidence writer。compile 未成功或simulation未启动时可无动态证据，但compile-core return
  必须发布；simulation_started=true而required observer/VCD receipt不完整时，必须保留已有core/partial
  evidence并标记`DIAGNOSTIC_EVIDENCE_INCOMPLETE`。
- 大结果分析必须流式推进并同步落盘`analysis_state.json`、append-only `checkpoints.jsonl`和持续编辑的
  `report.md`，只把有界摘要送入会话上下文。每族只保留`MAX_PROGRESS + LATEST_1 + LATEST_2`三组
  重型原始结果；分析完成、family与mainline双消费、确定性core证据及保护集审计全部通过后才可淘汰旧组。
- 诊断模式规则变更只授权受派发 family 本地构建 fresh 包；旧 pending 在 fresh publication
  时由对应 storage manager 原子移入 superseded。具体受影响 family 与状态只看 current plan；规则
  激活本身不授权 upload、lease 或服务器运行。
- 冻结包、原始回传和已有 evidence 不覆盖；失败路线重启必须使用全新身份并完整重建。
- 不从旧失败包、服务器残留或来源不明产物补齐新候选。
- 只有用户明确要求时才提交、推送、上传、运行服务器或执行其他外部变更。

## 5. 三级协作架构

项目采用“一个主线控制面、多个算子执行面、一个条件启用的公共基础设施面”：

### 5.1 主线会话

主线会话唯一维护 `.agents/plan.md`、`.agents/rules/**`、全局 blocker 和整网进度，
并决定下一步测试哪个算子、为什么它对 ResNet50 关键路径最有价值。每次派发前必须明确：

- `test_id`、算子 family/代表实例和冻结输入身份；
- 本轮要确认的规则 ID、通过可关闭的 blocker 和是否计入 E4/E5；
- CONFIG、RTL、observer、package infrastructure 等失败分流；
- 语义冻结集、允许写入路径和服务器预算。
- 派发时的主线会话 ID（只作 provenance），以及 package 生成或 return 闭环完成时从
  `contracts/current_session_owner_registry_v1.json`重新解析唯一 current mainline 并主动通知的义务。

主线验收算子会话的机器报告与规则修改提案/规则确证；公共/专项规则最终是否修改只由
主线裁决。
主线不承担普通测试包的重复构建，避免规划、实现和自我验收混在同一责任域。

### 5.2 算子族会话

按硬件算子族或代表实例建立持久会话，不为每个 ONNX 节点单独建会话。算子会话负责本族
人工 JSON→mapping→bitstream→execplan/SCA→服务器包→回传分析的纵向闭环，并维护本族
生成器、validator、实例合同、全新 artifact 和 task record。开始工作前必须读取派发任务
指定的规则及 SHA。

算子会话不得修改 `.agents/plan.md`、`.agents/rules/**`、功能 RTL 或其他 family 的资产；
只向主线提交 `RETURN_ANALYSIS`、`BLOCKER_DELTA`、下一包 `PACKAGE_RELEASE`，以及
`RULE_DELTA_PROPOSAL`/`RULE_CONFIRMATION` 二选一的规则反馈。规则建议不自动生效，
失败也不得通过放宽合同来适配错误硬件行为。

算子会话完成一个本地服务器包并达到 `PACKAGE_READY_NOT_RUN` 或明确终止状态时，必须
立即从活动 owner registry 解析并通知唯一 current mainline，回传派发主线与解析主线身份、
registry epoch、ZIP/sidecar 身份、唯一命令、预期 return、
final-ZIP 自检、blocker 和规则反馈；不能等主线轮询文件或等待用户提交 return 才报告。

另设一条“人工 JSON 消费会话”：只消费用户明确提供的人写算子 JSON，按同一规则生成
mapping、码流和服务器包并分析回传，不擅自改写输入 JSON。它在一次任务生命周期内同样
只绑定一个算子 family/代表实例；切换 family 时必须新建干净会话或完成明确 handoff，
不得在同一上下文混入多个算子族。

### 5.3 测试基础设施会话

只有公共 runner、observer、封包、回传或服务器兼容层出现跨算子共性问题时才启用。它
唯一负责共享框架修复和定向回归，不裁决算子数值语义、不修改 plan/规则，也不得把一族
的 workaround 静默推广到其他族。普通算子专属 adapter 仍由对应算子会话维护。基础设施
任务临时占用一个暂停的 AI 算子槽，不作为第七条常驻执行线。

### 5.4 会话替换与所有权切换

会话 ID 不是长期角色身份。主线、算子族、人工 JSON、公共基础设施和专项职责都必须绑定
稳定 `role_id`，其唯一活动 owner 来自
`contracts/current_session_owner_registry_v1.json`。替换任何会话前必须完整读取
`.agents/rules/会话转接与所有权规则.md`，并依次完成旧 owner 准备 capsule、新会话只读验收、
单 role registry activation、旧 owner 退为只读；任一时刻不得有两个会话同时写同一 scope。

整批换代必须先切换主线，再切换其它 role。派发单、历史 task record 或工具中保存的旧主线
ID只作 provenance；正式完成通知必须在发送时动态解析 current mainline。会话转接只转移已记录
的状态与原权限，不改变 in-flight package、server lease、return、E级或 RTL/config 授权。

## 6. 六条执行线与三服务器双缓冲流水

主线会话不计入算子执行并行度。常态执行面为 6 条相互隔离的流水：

1. 5 个 AI 算子族会话，各自只生成和分析本族测试；
2. 1 个人工 JSON 消费会话，处理用户提供的人写配置；
3. 主线在这 6 条线之外负责派发、规则和总账，不占执行槽；
4. 用户的上传、服务器唯一命令和回传操作也不计入上述 6 条会话。

六条线默认两两组成三个双缓冲组：

| 双缓冲组 | 执行线 | 唯一服务器根 |
|---|---|---|
| A | 算子线 1、算子线 2 | `NDP_copy01` |
| B | 算子线 3、算子线 4 | `NDP_copy02` |
| C | 算子线 5、人工 JSON 线 | `NDP_copy03` |

同组任一时刻至多一条线处于 `SERVER_RUNNING`；另一条线应处于本地构建、等待或回传分析，
两条线在前一包 restore/finalizer 后交替占用该根。组与根的映射只允许主线在两条线均未
运行时调整，并写入下一份冻结任务单。

服务器物理运行并行度硬上限为 3，分别使用相互独立的 `NDP_copy01`、`NDP_copy02`、
`NDP_copy03`。每个根目录必须有独占 lease：同一时刻只能有一个包在该根目录执行
observer install、compile、simulation、restore 和 finalizer；禁止两个会话触碰同一根
目录或其他目录的同名 TB/observer。三个根目录可以并行的前提是 build/run/log 路径、
临时 observer 和回传命名空间均隔离，且 VCS license、内存和文件 I/O 预算允许；资源门
未验证或发生争用时将 `SERVER_RUNNING` 上限降为 2，而不是牺牲身份或证据门。

每个测试遵循：

```text
SPEC_FROZEN → PACKAGE_BUILDING → PACKAGE_READY_NOT_RUN → SERVER_RUNNING
→ RETURN_COLLECTED → ANALYZING → ADJUDICATED
→ {CLOSED | WAIT_AUTHORITY_OR_CAPABILITY | SPEC_FROZEN(successor)}
```

分析阶段不占服务器 lease；一个包完成 restore/finalizer 并释放根目录后，人工操作员即可
启动下一包，同时对应算子会话分析前一回传。允许维护少量已验收的待运行包，但规则或冻结
身份变化时必须失效旧候选，禁止积压大量会迅速过期的包。

## 7. 标准派发与回传

主线派发任务单至少包含目标、规则 SHA、冻结资产、通过口径、失败路由、允许写入范围和
服务器/E4/E5 边界。算子会话最终回传至少包含：

- package/return ZIP 身份、退出状态、自然完成和 stock-RTL 身份；
- 最后可信边界、首个未观测/错误区间和正式 D 独立裁决；
- 建议关闭/新增/保持的 blocker；
- 规则修改提案或规则确证及其证据、影响范围和是否属于公共规则；
- 若目标尚未闭合，提供 successor 的全新身份、唯一命令、sidecar 和一次交付前自检
  结果；只有命中下述明确终止点时才允许不生成 successor。

主线只消费上述结构化结果；除非证据冲突、公共规则受影响或用户要求独立复核，不重复
完整解析同一份 raw 回传。

### 7.1 正式 return 驱动的连续闭环

用户向主线提交正式 return 后，主线必须自动把它分发给对应的持久算子族会话；算子 owner
在同一任务中完成 receipt-only 分析并继续到下一包裁决。本地读取、分析、生成 fresh
successor 和执行本地 final-ZIP 自检属于既有算子任务的默认权限，不需要用户再次授权。
上传、服务器运行、功能 RTL 修改和会影响任务功能范围的新用户选择仍按各自授权门处理。

服务器包实际运行期间，主线和算子 owner 不要求持续轮询、盯守或占用会话；用户提交正式
return 后才进入上述分析闭环。主线完成本地构包、return 分析或 successor 任务的有效分发后，
若没有其他独立主线任务，应立即结束本轮，不得为等待 owner 完成而持续调用状态查询、周期
轮询或向用户播报中间进度；只有 owner 主动返回完成/明确终止通知、用户提交新的正式 return，
或用户明确询问状态后，主线才重新进入验收与用户汇报。主线每次分发本地服务器包生成任务
或正式 return 时，都
必须在任务单中写入稳定 mainline `role_id` 和派发时 owner receipt；完成通知发送前再由
`contracts/current_session_owner_registry_v1.json` 动态解析 current mainline。旧 thread
ID 只作 provenance，不能成为回传路由。任务在分支会话内显示完成、文件已经落盘或主线
能够自行发现产物，都不能替代这条通知。

只要当前测试目标尚未达到声明的 E4/E5/覆盖终点，算子 owner 就必须按以下顺序继续：

1. 若现有 return、冻结配置、execplan/SCA、消费者和相关 RTL 已能确定根因，且修复仅涉及
   config、runner、package-local observer、validator 或封包基础设施，则使用 fresh
   identity 生成修正包；
2. 若穷尽同一 return 的只读证据后仍不能唯一确定根因，则围绕
   `LAST_PROVEN_GOOD → FIRST_DIVERGENCE` 生成一个以最短 time-to-root-cause 和单次
   运行信息增益为优先、低开销、只读的精确诊断包；“精确”不等于每轮只增加一个信号：
   能在预算内一次区分的低开销候选边界必须合并观测，并按服务器规则裁掉不参与复现或
   判别的 stage、payload、readback 和 observer；
3. 若根因是功能 RTL，状态转为 `WAIT_RTL_FIX`，只有用户本轮明确授权后才能修改 RTL 或
   生成 repair profile；
4. 若缺少真实硬件能力，状态转为 `HARDWARE_CAPABILITY_BLOCKED`；不得用近似能力或占位包
   冒充 successor；
5. 若继续动作需要一个会实质改变功能范围、硬件合同或外部系统状态的用户选择，明确记录
   `WAIT_USER_DECISION` 和唯一问题后停止；
6. 若本轮目标已正式闭合，则转为 `CLOSED`；若声明目标还要求 E5，E4 首次通过后默认生成
   fresh identity 的独立重复包，而不是提前结束。

以下两类结果不得直接按旧模板继续构包，必须先完成规则/硬门审计，并把裁决实际绑定到
下一份 fresh 包：

1. production compile 成功、simulation 与目标因果区间实际执行、return 可完整消费，但
   本轮仍不能在已声明候选中唯一定位根因时，标记 `RULE_GAP_AUDIT_REQUIRED`。审计必须逐项
   检查 causal-cone/catalog、候选×边界矩阵、actual-source identity、触发/停止条件、global
   progress witness、return exact-set、parser/streaming analysis 和正负控，解释为何“单轮可区分”
   的本地门仍允许 production 结果不充分。若是公共语义缺口，先提交并激活非同义
   `RULE_DELTA_PROPOSAL`；若是已有规则的实现逃逸，提交有证据的 `RULE_CONFIRMATION`。审计若证明
   current规则语义与现有门已充分覆盖、失败只是孤立的package实现/人工操作失误、没有共享覆盖缺口，
   允许裁决为`RULE_CONFIRMATION_NO_CHANGE`，不修改公共规则/schema/tool/test；successor仍须修正该包并
   重跑原门。只有审计发现现有门无法捕获同机制时，才补validator/负控并在successor first-fresh中绑定。
2. 同一目标连续两次 fresh 构包/final gate 尝试失败，或连续两次 production 尝试因
   package-local runner/TB/observer/parser/return 缺陷没有执行目标时，标记
   `PACKAGE_BUILD_FAILURE_RULE_AUDIT_REQUIRED`。第三次尝试前必须聚合两次失败机制，审计生成器、
   shared validator、负控与 definition-before-use/identity/return 合同；禁止仅换 package 名重试。

上述审计不扩大服务器、RTL或外部系统权限。family owner 可立即修复已有规则已明确覆盖的
implementation escape；涉及公共规则语义变化时必须等待主线/共享 owner 激活后再发布 successor。
不得为了“审计已触发”而强制制造规则delta；`RULE_CONFIRMATION_NO_CHANGE`是完整终态，不视为审计遗漏。
唯一根因已闭合且 package-only successor 无意义，或命中下述权限/能力终止点时，不要求盲目构包。

除上述 `CLOSED`、`WAIT_RTL_FIX`、`HARDWARE_CAPABILITY_BLOCKED` 或
`WAIT_USER_DECISION` 外，`ADJUDICATED / PACKAGE_RELEASE=NONE` 不是允许的终态。
算子会话必须继续工作，直到交付 `PACKAGE_READY_NOT_RUN` 或上述明确终止点。主线活动
plan 必须记录正在执行的 successor，而不得用“若需下一包”“另行授权后再生成”把本地
闭环留空。

每次完成通知还必须提交规则反馈：

- 若本轮失败、audit escape、诊断歧义或成功经验证明现有公共/专项规则缺少可执行门、
  表述含糊或范围错误，提交 `RULE_DELTA_PROPOSAL`，列出证据、适用范围、建议规则 ID
  以及正负控；
- 若 current 规则已经充分覆盖，提交 `RULE_CONFIRMATION`，列出被本轮错误或成功经验
  实际确证的规则 ID、对应证据和 claim boundary；不得只写无证据的
  `RULE_DELTA_PROPOSAL=NONE`；
- 算子 owner 不得直接修改 `.agents/rules/**`。主线收到通知后负责判断是正式修改规则、
  记录规则确证，还是拒绝同义/过度严格的提案，并同步活动 plan/history/task record。

## 8. 协作纪律

- 修改前检查工作树并保留无关用户改动；禁止未经授权的 reset、checkout 或删除。
- `plan.md` 只记录活动状态；完成过程写 task record，过时状态迁入 history。
- 公共规则不保存版本号、包 SHA、某次日志行号或已结束过程。
- 新证据推翻旧结论时保留旧证据身份，活动文件只写新裁决及其来源。
- 所有面向用户的项目汇报统一遵守
  `CDA-SERVER-USER-FACING-REPORT-PREVIOUS-PROGRESS-CURRENT-PURPOSE-NO-DIGEST-001`：
  不转抄内部bytes/SHA，必须说明上一正式回传版本的进展与当前版本要定位或解决的问题。
