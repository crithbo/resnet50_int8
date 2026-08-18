# ResNet50 INT8 当前状态与短期计划

最后更新：2026-08-18。current disk 中 serialized Conv v106 与 QLinearAdd v80 是仅有的两份
`PACKAGE_READY_NOT_RUN`；GAP 与 native Conv 已闭合根因，等待用户授权修复方向。

## 0. 本文件职责

- 这里只保留 current 状态、直接 blocker 和唯一下一步，不记录版本过程。
- 动态 owner、任务和 package 指针以 `contracts/current_session_owner_registry_v1.json` 为准。
- 精确过程在 `.agents/task_records/`、机器报告和 Git 历史；规则入口在 `.agents/agent.md`。
- 正式 E4/E5 闭环：`1/78`，仅 DequantizeLinear node0077。其余不得提前宣称通过。
- 当前没有 `SERVER_RUNNING` lease；上传、运行、lease 仍须用户明确授权。

## 1. 整网 current 总账

| 算子/范围 | current 状态 | 直接结论或 blocker |
|---|---|---|
| GAP node0071 | `VALIDATED_ROOT_CAUSE / WAIT_EQUIVALENT_C_PATH_CONFIG_EXTENSION_AUTHORIZATION` | v73证明A/C两侧Buffer_AG列FIFO跨slice reset保留旧索引，当前绕行不具端到端可用性；无观察型successor |
| QLinearAdd node0007 | `PACKAGE_READY_NOT_RUN / V80_W15KQF` | 4/2目标已动态推进；v80采用15000秒测量绑定wall、86400秒硬上限、qualified progress和两阶段return，是唯一QAdd pending |
| MaxPool node0002 | `DEFERRED_BY_USER / COMPLETE_JSON_COMPLETE` | strict 1/1、461 leaves闭合；padding `null→0`的动态因果证据不足 |
| Conv node0004 serialized | `PACKAGE_READY_NOT_RUN / V106_RETURN2PFLIGHT` | v106冻结LC9→LC3、52信号因果锥和功能面，只修64位时间、accept-qualified计数、单一3660秒wall及durable return；是唯一serialized pending |
| Conv native four-lane | `VALIDATED_ROOT_CAUSE / WAIT_FUNCTIONAL_FIX_AUTHORIZATION` | p52证明MSE4 input1 buffer-tag stream少一笔32-unit transaction；无successor |
| QuantizeLinear node0074 | `APPROVED_EQUIVALENT / FROZEN_HARDWARE_HARD_BLOCKED` | 通用FP32→UINT8至少需82 segments，超过current SFU 66项；node0074成对消除路径保持 |
| DequantizeLinear | `NODE0077_E4_E5_PASS_FROZEN / COMPLETE_JSON_COMPLETE` | node0072/0077 strict 2/2；node0077仍是唯一正式E4/E5正控 |
| RequantizeUint8 node0001 | `COMPLETE_LOCAL_STRICT_JSON_54_OF_54 / LOCAL_W3_EXACT_PASS / NATIVE_BACKEND_OPEN` | 169,410,176个W3 elements本地双跑mismatch=0；native mapper/encoder、RTL cycle与natural terminal未闭合 |
| View node0073 | `APPROVED_EQUIVALENT_UINT8_ALIAS / COMPLETE_JSON_COMPLETE` | metadata-only alias 1/1、161 leaves闭合；accepted lifetime仍待联合return |
| QLinearMatMul node0075 | `WAIT_GAP_PRODUCER_CLOSURE / COMPLETE_JSON_COMPLETE` | v9只到node0071 stage01；不得重复运行同一长前缀 |
| 整网测试收敛 | `PATCH_FIRST_ACTIVE / DUAL_DIAGNOSTIC_MODE / RELEASE_ADMISSION_REQUIRED` | hard blocking仅限server start、actual input、state safety、return；transport SHA/bytes只作provenance |

## 2. current owner 与唯一动作

所有新会话先解析 current owner registry；不得用旧thread ID或聊天记忆替代动态指针。

| role | current 任务 | 唯一下一步 |
|---|---|---|
| `mainline.control` | 维护plan、owner路由、storage与release裁决 | 等待用户授权运行v106/v80，或授权GAP/native修复方向 |
| `family.conv.serialized` | v106 pending owner | 只消费v106正式return；不得另起同目标successor |
| `family.qlinearadd` | v80 pending owner | 只消费v80正式return；不得缩短source-bound预算 |
| `family.gap` | 保存v73根因 | 等待等价C-path配置扩展授权 |
| `family.conv.native` | 保存p52根因 | 等待functional fix授权 |
| `optimizer.whole-network` | 维护共享gate、Skill和整网闭环方法 | 不接管family，不构包、不运行服务器 |

## 3. 两份唯一 pending

- `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v106b_lcdup_return2pflight.zip`
- `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tr_v80_w15kqf.zip`

storage current：pending/tested/superseded=`2/61/24`，每族pending最多一份。现有两包不因后续
规则变化追溯重建；只有实际命中会导致服务器错误的changed surface才patch。

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

1. 用户服务器运行v106与v80；family owner各自分析正式return并主动回主线。
2. serialized：裁决tuple10/downstream/natural terminal/Formal-D；QAdd：裁决target完成与28D。
3. 用户选择GAP等价配置扩展或native functional fix后，仅为获授权的changed surface生成successor。
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
