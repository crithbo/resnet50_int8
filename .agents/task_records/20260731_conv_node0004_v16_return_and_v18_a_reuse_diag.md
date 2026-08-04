# Conv node0004 v16 formal return 与 v18 A-reuse 窄诊断交付

## Ownership 与停止门

- family: Conv / SA
- mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- numeric_analysis_repeated: `false`
- node0004_workload_rebuilt: `false`
- configuration_rebuilt: `false`
- functional_rtl_modified: `false`
- public_rule_or_plan_modified: `false`
- server_action: `false`
- package classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`

## 活动规则 post-generation current-match

| 路径 | SHA256 |
|---|---|
| `.agents/rules/生成前必读索引.md` | `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f` |
| `.agents/rules/服务器测试包生成规则.md` | `507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d` |
| `.agents/rules/INT8_SA点积专项规则.md` | `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce` |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` |
| `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` | `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7` |

绑定 rule IDs 至少包括：

- `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`
- `CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001`
- `CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`
- `CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001`
- `CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`
- `CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`
- `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`
- `CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001`
- `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`
- `CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001`
- `CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001`

## RETURN_ANALYSIS

Formal return:

- ZIP: `r5_n4_hw_v16_abpe_runnerpc_return.zip`
- bytes: `77352`
- SHA256: `561e29d888b8970d44ff90405d8709cc6e9aae63393d02261652aa5ff7888d4f`
- adjacent sidecar SHA256:
  `a008d8eb75a328dd5543adf90c584212798a0bef11f578e462aabea7e67ca513`
- source ZIP SHA256:
  `e0f6d1effba71e505d22203ec2a43b4a538aaeeb515b806f6953603a342bcec1`

Envelope、sidecar、CRC、single-root、exact-set、allowlist、package/install
preflight、observer identity 与 runtime binding 全部有效。compile exit `0`，
run exit `0`，signal `NONE`。仿真启动并由四个连续零增量窗口触发受控诊断
fatal；没有 DUT natural terminal，也没有任何 formal D member。

唯一 canonical decision:

`LONG_RUNNING_HANG_AT_BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS`

- active cycles: `1310720`
- window cycles: `262144`
- qualified progress: `144`
- delta sequence: `144,0,0,0,0`
- ABPE accepted: A group `1`、B group `1`、C group `8`、ALU `64`
- PE out accepted: `0`
- SA group out accepted: `0`
- masked A snapshot: `0x0`
- masked B snapshot: `0xffffffffffffffff`

E3=`true`；E4=`false`；E5=`false`。`mismatch=0` 与 formal D 全部缺失不构成
通过。

机器分析：

- `tools/analyze_node0004_v16_return.py`
  SHA256=`109f42974eead0f39cd93ac508733ab3e5c3e95845516157e2476c526241e576`
- `contracts/operator_config/node0004_v16_return_analysis_v1.json`
  SHA256=`ea4a4b304a15ce2452aa52696fe126de659d5da2b8d0a09b608faf90407f09c4`

## FIRST_DIVERGENCE / HANG_ROOT_CAUSE

last-good：MSE0/1/3 已返回数据，A/B/C 到达 SA，64 个 PE 全部接受恰好一次
A/B 配对。

first-bad：此后没有第二次 A/B issue；A 消失、B 保持；PE output、SA group
output、Buffer5 write 均为零并持续四个 qualified window。

最窄已证失败区间：

`MSE0_RETURN_TO_BUFFER0_1_TO_SA_INPORT0_SECOND_ACCEPT`

`transout_last_index=2` 已排除：该值要求在上游 `last_index>2` 时继续累加，
仅完成首个 product 时没有输出是正常现象，不能解释第二个 A 未到达。

本地冻结配置与活动 RTL 的静态证据不能在以下候选中唯一裁决：

1. MSE0 producer 对 Buffer0/1 的 selector 与 accepted write；
2. Buffer0/1 的 clear/full/valid/reuse/lifetime；
3. SA inport0 source0/source1 selector 与 accepted event；
4. PE pipeline0 到 ALU-to-outbuffer write handshake。

因此当前 `HANG_ROOT_CAUSE=UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT`。
没有确定功能 RTL 缺陷，也没有确定配置错误；只允许窄诊断后继。

## PACKAGE_RELEASE

唯一可运行身份：

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v18_a_reuse_diag.zip`
- bytes: `5816603`
- SHA256:
  `aa12edc55f10e28133e843e3ddeff832831a8d8c71cef47c5bc69e7c48f73fc1`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v18_a_reuse_diag.zip.sha256`
- sidecar file SHA256:
  `c7d78b285579ee23e34dc29ac78ba0dee8a2dff75a3c52760c4f42065a1c6aae`
- observer SHA256:
  `db36700079225c70b2811f674791a2fd9d08aa3878f85f7bfd6e8d879c03172b`
- status: `PACKAGE_READY_NOT_RUN`
- classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- expected return:
  `r5_n4_hw_v18_a_reuse_diag_return.zip`

服务器单命令：

```bash
bash r5_n4_hw_v18_a_reuse_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

v18 只在 canonical decision 处追加唯一 `A_REUSE_BOUNDARY_V1`，记录 accepted
Buffer0/1 request/write/read、memory/array clear、SA inport0 source0/source1
accept、ALU-to-outbuffer write cycle，并分离 MSE0 selector、SA selector、
Buffer tag、pipeline0 valid、write mask、psum-ready snapshot；这些 snapshot
不计入 monotonic progress。

v17 SHA256
`dd0f3fa647388be64d601b861fc99728440acf6a5f9cba753b2b870ad8cd0e16`
因 return classification 被旧 runtime 硬编码成“功能修复”而隔离，禁止运行。

## FINAL ZIP 独立自检

正向 runner 控制：

- report:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v18_a_reuse_diag.runner_positive_control.json`
- report SHA256:
  `9d30323bbab10325907cfcab58db44e05ebec225434b15e75fd782c217ab5457`
- validator exit: `0`
- safe compile-stub expected/observed exit: `73/73`
- compile-stub invocation count: `1`
- actual argv 同时包含
  `+define+NATIVE_RETURN_OBSERVER_ENABLE` 与 package-local `+incdir`
- wrong observer identity negative: runner exit `5`，compile-stub count `0`

最终 ZIP 审计：

- validator: `tools/validate_node0004_v18_final_zip.py`
- report:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v18_a_reuse_diag.final_zip_rule_self_audit.json`
- validator exit: `0`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- all required negatives fail closed: `true`

定向负控及退出码：

| 负控 | observed exit |
|---|---:|
| missing observer source | 1 |
| missing package-local `+incdir` | 1 |
| missing enable macro | 1 |
| missing runtime/return binding | 1 |
| missing current rule ID | 1 |
| diagnostic mislabeled as functional fix | 1 |
| compile stub not reached | 1 |
| missing unique A-reuse boundary | 1 |

## BLOCKER_DELTA

- 保持：node0004 natural terminal / 320 formal D / E4 / E5 未关闭。
- 收窄：hang 从 coarse Buffer4→Buffer5 区间收窄到第一次成功 PE 配对后的
  A producer / Buffer0-1 reuse / SA inport0 second-accept 区间。
- 新增可执行判别：v18 可一次性区分 producer-selector、Buffer lifetime、
  SA selector 和 PE pipeline/outbuffer 四类候选。
- 未新增公共 rule delta。

