# ResNet50 INT8 当前状态与短期计划

最后更新：2026-08-22。四份最新 return 均已确认在 VCS license 连接阶段被外部 INT 中断，未进入仿真；GAP v80 与 serialized v113 已作为 runner/return-only fresh 后继进入各自 sole managed pending，其余两族按最小后继或共享门禁继续处理。

## 0. 本文件职责

- 这里只保留 current 状态、直接 blocker 和唯一下一步，不记录版本过程。
- 动态 owner、任务和 package 指针以 `contracts/current_session_owner_registry_v1.json` 为准。
- current mainline token：`019ff027-e7db-72a3-b282-cfad8708da05`；registry_epoch: 50；完成通知仍须先从registry复核。
- 存储发布政策（用户指令）：本地门禁完成且状态为 `PACKAGE_READY_NOT_RUN` 的待测包直接进入对应族 managed pending，无需逐包额外许可；上传、运行、lease 仍须用户明确授权。
- 返回包政策（用户指令）：所有下一轮测试包的正式 return 必须是单个 ZIP，所有附加物（如 sha256）必须放在 ZIP 内部，不得再出现 ZIP 与旁置文件并存。
- 支线执行模式：长期（continuable）子代理，每个已注册 role 一个持久会话；主线用 send_message 直接派发，支线回传主线。用户创建的顶层会话不再作为 registry owner，仅可人工查阅工作区。
- 邮箱文件 `outputs/session_mailbox_v1/` 保留为人工审计镜像，不作为主派发通道。
- 精确过程在 `.agents/task_records/`、机器报告和 Git 历史；规则入口在 `.agents/agent.md`。
- 正式 E4/E5 闭环：`1/78`，仅 DequantizeLinear node0077。其余不得提前宣称通过。
- 当前没有 `SERVER_RUNNING` lease；上传、运行、lease 仍须用户明确授权。

## 1. 整网 current 总账

| 算子/范围 | current 状态 | 直接结论或 blocker |
|---|---|---|
| GAP node0071 | `PACKAGE_READY_NOT_RUN / V80_CFIFO_RETURNCORE_TBVCD` | v79 因 license 连接失败后外部 INT 停在 compile 前；v80 只修 signal-safe compile-core/return，冻结 overlay、配置、RTL 修复与 3531-signal 锥，已发布为 sole GAP pending |
| QLinearAdd node0007 | `FORMAL_RETURN_CONSUMED / V83_LICENSE_INTERRUPT` | v83 未进入仿真；错误是 license 连接失败，另有中断回传核心条目缺失；功能面与 GA 数值机制均未裁决，fresh runner/return 后继仍待 mode binding/构建 |
| MaxPool node0002 | `DEFERRED_BY_USER / COMPLETE_JSON_COMPLETE` | strict 1/1、461 leaves闭合；padding `null→0`的动态因果证据不足 |
| Conv node0004 serialized | `PACKAGE_READY_NOT_RUN / V113_COMPILE_SIGNAL_CORE` | v112 未进入仿真；v113 只修 compile INT 时的 compile-core/return 归一化，153-signal tuple-leaf 锥和冻结面不变，已发布为 sole serialized pending |
| Conv native four-lane | `PACKAGE_READY_NOT_RUN / P58_COMPILEINTERRUPT` | 共享 contract/result schema 接口已窄修；exact p58 最终 admission PASS，p57 已归档 tested，p58 已发布为 sole native pending |
| QuantizeLinear node0074 | `APPROVED_EQUIVALENT / FROZEN_HARDWARE_HARD_BLOCKED` | 通用FP32→UINT8至少需82 segments，超过current SFU 66项；node0074成对消除路径保持 |
| DequantizeLinear | `NODE0077_E4_E5_PASS_FROZEN / COMPLETE_JSON_COMPLETE` | node0072/0077 strict 2/2；node0077仍是唯一正式E4/E5正控 |
| RequantizeUint8 node0001 | `COMPLETE_LOCAL_STRICT_JSON_54_OF_54 / LOCAL_W3_EXACT_PASS / NATIVE_BACKEND_OPEN` | 169,410,176个W3 elements本地双跑mismatch=0；native mapper/encoder、RTL cycle与natural terminal未闭合 |
| View node0073 | `APPROVED_EQUIVALENT_UINT8_ALIAS / COMPLETE_JSON_COMPLETE` | metadata-only alias 1/1、161 leaves闭合；accepted lifetime仍待联合return |
| QLinearMatMul node0075 | `WAIT_GAP_PRODUCER_CLOSURE / COMPLETE_JSON_COMPLETE` | v9只到node0071 stage01；不得重复运行同一长前缀 |
| 整网测试收敛 | `SINGLE_ZIP_POLICY_ACTIVE / MULTI_RETURN_INCIDENT_FIXED` | optimizer 已把 durable/cleanup/sha256 全部改为 return ZIP 内部成员，simresult 只允许一个 ZIP |

## 2. current owner 与唯一动作

所有新会话先解析 current owner registry；不得用旧thread ID或聊天记忆替代动态指针。

| role | current 任务 | 唯一下一步 |
|---|---|---|
| `mainline.control` | 维护plan、owner路由、storage与release裁决 | ready 后继自动发布 pending；当前只维持控制面/存储一致，不执行服务器动作 |
| `family.conv.serialized` | v113 pending owner | 等待服务器运行并只消费 exact v113 formal return |
| `family.qlinearadd` | v83 return owner | 取得 fresh mode binding 后只修中断回传面并构建后继；冻结 4/2 与 GA 数值锥 |
| `family.gap` | v80 pending owner | 等待服务器运行并只消费 exact v80 formal return |
| `family.conv.native` | p58 pending owner | 等待服务器运行并只消费 exact p58 formal return |
| `optimizer.whole-network` | shared admission maintenance | 本次接口事故已闭合，待命处理新共享事故；不接管 family、不运行服务器 |

## 3. 当前 pending

- `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p58_compileinterrupt.zip`
- `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v113b_compile_signal_core.zip`
- `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v80_cfifo_returncore_tbvcd.zip`
- `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tr_v83_ga_numeric.zip`

storage current：pending/tested/superseded=`4/81/25`；四个族各一个 sole physical pending，其中 GAP v80、serialized v113 与 native p58 可测；QAdd v83 已消费且等待 fresh v84 替换。

## 4. 后续构包与诊断策略

1. 构包、修runner/observer、分析return或设计successor时必须调用
   `resnet50-server-package-flow` Skill。
2. 未发布candidate优先同身份patch；未变PASS receipt复用；先一次聚合廉价错误，再做一次final-ZIP admission。
3. blocking项必须映射到`server_start / actual_input / state_safety / return`之一；否则只能record-only。
4. 新的动态诊断successor默认显式选择`TB_VCD_BOUNDED_CAUSAL_CONE`；已有ready包模式不追溯改变。
5. observer与TB-VCD互斥。TB-VCD只采source-bound bounded causal cone；禁止VPD/FSDB/UCLI/full-top dump。
6. 本地不得因服务器可执行文件或环境资产“未发现”而阻断；只验证package自带入口和必需输入关系。
7. return分析按candidate×boundary增量落报告；命中唯一根因后停止无关扫描。

## 5. 最短整网闭环顺序

1. 等待 serialized/QAdd runner-return 后继与 native shared-admission 修正；三者成为 `PACKAGE_READY_NOT_RUN` 后按用户政策自动轮换 pending。
2. 用户明确授权后运行 GAP v80 与其余 fresh 后继；按 exact package/execution identity 流式分析，命中唯一根因即停止无关扫描。
4. GAP生产者闭合后再推进node0075 accepted reads/hash、natural terminal与144D。
5. 最后闭合133-stage integration assembly、shared allocator/execplan/lifetime与整网formal D。

## 6. 接管检查

新Agent依次读取：

1. `.agents/agent.md`
2. 本文件
3. `contracts/current_session_owner_registry_v1.json`
4. `.agents/rules/生成前必读索引.md`路由出的职责规则
5. 对应role的latest task record与current package receipt

开始写入前运行：

- `python tools/audit_active_rule_registry.py --registry contracts/active_rule_registry_v1.json`
- `python tools/validate_project_takeover_readiness.py --state-root <canonical-root> --report <report.json>`

失败只修复current指针或真实hard gate，不通过添加同义规则、全量重建或重复服务器长前缀绕过。

## 7. 权限与证据边界

- 不得自行上传、运行、取lease、改functional RTL/hardware/ISA、改numeric/config/workload/golden。
- 本地strict JSON、backend导出或observer证据不等于production natural terminal、正式D或E4/E5。
- current package、plan与owner registry由mainline裁决；family owner只维护本族资产和报告。
- 事故先判定规则语义错误、实现逃逸或会话执行不合规；只有非同义语义缺口才修改规则，且修改必须可删可换。
