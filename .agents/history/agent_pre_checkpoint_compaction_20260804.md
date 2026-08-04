# ResNet50 INT8 项目稳定入口

最后更新：2026-08-04（诊断后继改为 time-to-root-cause / 信息增益优先）

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
| 算子特有公式、布局、反例和发布门 | 对应算子专项规则 |
| 当前任务和顺序 | `.agents/plan.md` |

创建、修改、派生、重建或发布 JSON、mapping、bitstream、execplan、SCA/SCA_D 或测试包
前，必须从“生成前必读索引”重新选择本轮相关资料并保存读取收据。本文件不复写这些规则。

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
- 当前唯一主线会话 ID，以及 package 生成或 return 闭环完成后主动通知该主线的义务。

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
立即主动通知派发单绑定的当前主线，回传 ZIP/sidecar 身份、唯一命令、预期 return、
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
return 后才进入上述分析闭环。主线每次分发本地服务器包生成任务或正式 return 时，都
必须把当前唯一主线会话 ID 写入任务单，并明确要求 owner 完成后主动向该主线发送结构化
完成通知。任务在分支会话内显示完成、文件已经落盘或主线能够自行发现产物，都不能替代
这条通知。

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
