# ResNet50 INT8：常态触发式因果观测合同 v1

日期：2026-08-06  
owner task：`019fd276-14c5-7800-94db-87ebfb9ce632`  
回传主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`  
状态：`DESIGN_VALID_BINDING_AND_CALIBRATION_PENDING`

## 1. 用户裁决与实现范围

用户批准把“低成本常态计数 + 异常触发有界快照 + 因果切面判别”写入规则并实现共享合同。随后明确修正性能口径：

- 不把 10%–20% 设成强制范围；
- 以一轮内完成足够观测、尽可能确定问题为优先目标；
- 50% slowdown 是建议上限而非硬门；
- 超过 50% 必须报告、解释并继续优化，但不得为了压开销删除定位所需的观测边界。

本轮仅实现公共规则、schema、registry、五条当前测试线的设计基线、validator 与 synthetic tests。没有修改五个 current ZIP，没有生成或修改 mapping/bitstream/execplan/SCA/服务器测试包，没有上传、运行、取 lease，没有修改 functional RTL 或 `.agents/plan.md`。

## 2. 新增公共合同

规则：

- `CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001`
- `CDA-WHOLE-NET-ONE-ROUND-OBSERVABILITY-COMPLETENESS-FIRST-001`

适用范围是**下一份会实际进入 DUT simulation 的 fresh successor**。冻结的 current 五包仅作为历史证据和设计基线，不因本规则重建。

统一因果切面为：

`source produce → queue enqueue/dequeue → consumer request/accept → internal match/compute → output accept → terminal propagation → formal D`

常态路径只允许 stage-gated、read-only counter/first-last timestamp/max occupancy/outstanding/tag/digest/mask 等低频状态。下列六类事件触发有界 snapshot：

1. `FIRST_QUEUE_FULL`
2. `FIRST_BRANCH_DIVERGENCE`
3. `NO_PROGRESS_WINDOW`
4. `TERMINAL_GAP`
5. `STAGE_TRANSITION`
6. `EXIT_OR_SIGNAL`

禁止 per-event 文本 I/O、默认全量 VCD/FSDB、DUT drive、输入/背压/时序/timeout 语义改变、host 内部 tensor replay。v1 的 no-progress 只触发 snapshot 并沿用既有 timeout，不自动终止 simulation。

标准裁决分类：

- `TEST_INFRASTRUCTURE_FAILURE`
- `SIM_NOT_STARTED`
- `TARGET_STAGE_NOT_REACHED`
- `DYNAMIC_FLOW_CONTROL_STALL`
- `TERMINAL_PROPAGATION_FAILURE`
- `RESULT_COLLECTION_FAILURE`
- `NUMERIC_MISMATCH`
- `NATURAL_SUCCESS`
- `EVIDENCE_INCOMPLETE`

## 3. 五条测试线设计基线

| family | boundary | hypothesis | 主要判别边界 |
|---|---:|---:|---|
| GAP | 9 | 5 | request/prepared、Buffer_AG enqueue/dequeue、Memory accept、LC ack、terminal、48D |
| serialized Conv | 9 | 6 | Buffer source、LC9、PE1 accept/match、Memory MSE4/ROW4、global-last0、formal D |
| QLinearAdd | 10 | 6 | 双操作数 byte supply/mask、row-ready、ARM/GA/MSE、FP32 output、tail、28D |
| native Conv | 9 | 6 | sim/exec/config、request、Buffer/ARM、SA、MSE4、slice finish、formal D diagnostic |
| node0071→node0075 | 10 | 6 | node71 final write、node75 first A read/request/accept、accum/scale/round、terminal、144D |

合计 47 个边界、29 个互异故障假设、每 profile 6 类触发器。registry 登记 10 类共享机制，并绑定 22 份历史失败/成功证据来源。

五份 profile 均为：

- `maturity=DESIGN_READY_BINDING_AND_CALIBRATION_PENDING`
- `release_eligible=false`
- `calibration.status=PENDING_FRESH_BOUND_PROFILE`

因此设计基线不会被误认作 final-ZIP release receipt。

## 4. 性能与发布语义

- `decision_priority=ONE_ROUND_HYPOTHESIS_DISCRIMINATION_FIRST`
- `preferred_max_slowdown_percent=50`
- `slowdown_limit_hard=false`
- `over_preferred_action=REPORT_JUSTIFY_AND_OPTIMIZE_WITHOUT_DROPPING_REQUIRED_BOUNDARIES`

有同事件轨迹 A/B 基线时，fresh owner 应实测 wall-clock slowdown；没有合格基线时必须保持 `PENDING_FRESH_BOUND_PROFILE`，不得编造百分比。`WITHIN_PREFERRED` 与 `ABOVE_PREFERRED_REPORTED` 均为非阻断性能分类；能否发布仍由 exact final-source binding、family validator、production compile/simulation、natural terminal、正式 D、E4/E5 等原门共同裁决。

## 5. 工具与收据

| artifact | bytes | SHA256 |
|---|---:|---|
| `.agents/rules/服务器测试包生成规则.md` | 82375 | `4ff581d2add191c6345948489b90d3ccaa43fcae9c31eab8b75bcc99fae2de0b` |
| `.agents/rules/整网测试收敛优化专项规则.md` | 11059 | `e7c760305c334a277c04806e53a673d9c2a0e539159d667d22f4a24a1adf67bd` |
| `.agents/rules/生成前必读索引.md` | 12516 | `350631c45ef3dbbc75d26205359b9f93c59a088db0993cc9cf14c4999a51bcf5` |
| `schemas/server_triggered_causal_observability_v1.schema.json` | 12273 | `98416b147767555441390b42744c033d3688b2eb403301020b21023b13aa188e` |
| `contracts/server_triggered_causal_observability_registry_v1.json` | 5557 | `89dd8e879078e8cbbde4069fc132d398fea8e14836a6f9e40c70640b01231831` |
| `contracts/server_triggered_causal_observability_current_five_v1.json` | 56619 | `82a6a9166f055a209557d23ac4aed9dd8f7b7566022037ac9748a5e223c8708a` |
| `tools/validate_server_triggered_causal_observability.py` | 28938 | `c8f688ff3b4ec28bbea372fb59a803e88ea75556f916351662979a158fe621e4` |
| `tests/test_server_triggered_causal_observability.py` | 8030 | `bb23d1995b3fc210c3bddf6ba5fb696f16973c62c3c36f8699cb091d6366b27d` |
| `artifacts/operator_config_validation/r5-triggered-causal-observability-v1/report.json` | 7579 | `8a83588236344f6656d6600617c6ccd10487a273880a89bb47a117bd812bb610` |

machine report：

- `valid=true`
- `errors=[]`
- `status=DESIGN_VALID_BINDING_AND_CALIBRATION_PENDING`
- `current_packages_modified=false`
- `server_package_generated=false`
- `server_action_performed=false`

## 6. 验证

- JSON/schema/registry/profile validation：PASS
- `py_compile`：PASS
- 新增 causal-observability tests：14/14 PASS
- 与 shared final-ZIP shadow、shared RETURN adjudicator 合并回归：26/26 PASS
- `git diff --check`：PASS

负控覆盖：缺机制、未知历史反例、硬 slowdown gate、自动 no-progress termination、per-event text/full-wave、host replay、hypothesis 引用未知边界、两个 hypothesis 同观测签名、缺触发器、超声明存储、current-five scope 缺族、fresh-successor 单族兼容等。

## 7. Fresh successor 迁移方法

1. family owner 在 fresh final ZIP 内把 profile 绑定到 exact final HDL source、owner clock/reset、actual consumer 与真实 predicate。
2. family final-ZIP audit 先保持权威；共享 validator 对 bound profile 做同包审计。
3. 若有同事件轨迹基线，执行带/不带观测 A/B calibration；否则保留 pending 并在首次实际 run 后补收据。
4. 一轮 RETURN 同时输出边界计数、触发快照、因果假设裁决与标准 outcome；不得用性能偏好替代 natural terminal、正式 D、E4/E5。

## 8. Claim boundary

本轮只证明共享观测合同、机制 registry、五条设计 profile 和 validator/test 的静态一致性。尚未证明任何 profile 对 fresh final ZIP 的 exact binding，也未证明实际 slowdown、production compile/simulation、natural terminal、正式 D、E4/E5 或服务器结果正确性。
