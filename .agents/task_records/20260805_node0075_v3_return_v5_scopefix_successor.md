# QLinearMatMul node0075 v3 return → v5 observer-scope successor

日期：2026-08-05  
owner：QLinearMatMul / node0075 independent owner  
唯一主线 / 结构化回传目标：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 1. current 读取与身份

本轮在 dirty 共享工作树中只新增 node0075-scoped analyzer、observer、builder、audit、
report/package 和本记录；未修改 `.agents/plan.md`、`.agents/rules/**`、functional RTL
或其它 family 资产，未 reset/checkout/clean/覆盖/删除历史资产。

生成及最终自检使用的 current receipt：

- `.agents/agent.md`
  SHA256=`32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md`（mutable provenance）
  SHA256=`1185bc9aca4d033bca553df987192ee6d43cf5882a9ad4950352a67e56692211`
- `.agents/rules/生成前必读索引.md`
  SHA256=`93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
- `.agents/rules/算子配置规则.md`
  SHA256=`d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0`
- `.agents/rules/服务器测试包生成规则.md`
  SHA256=`68fafe7c33e8ac037d94308a0902cdb52afec32f1325d6cee9bc14f70ca9d69d`
- `.agents/rules/NDP硬件字段语义.md`
  SHA256=`603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/INT8_SA点积专项规则.md`
  SHA256=`54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/精确UINT8量化尾专项规则.md`
  SHA256=`1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  SHA256=`e82f51c73f658fa567d47c8ab277c1cfb2cdf6d7cd2b4debefb3d0543e2228ba`

current RTL binding 保持用户/主线指定的 `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`。
本轮实际消费的 current source bytes：

- `NDP_copy01/rtl/NDP_Top_phy.sv`
  SHA256=`ce8e699db43d15f1609574257435007fab3c9f1cccbb5ce75b2109fad3ea0782`
- `NDP_copy01/rtl/clk_freq_new.sv`
  SHA256=`c8c61856de53d377e7611bafee5d6d9d68050ef331e96aae9e39edb099f7a411`
- `NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f`
  SHA256=`5d55c6257458d614b670f67259f8190a9e2daa70498e18952290df28dee68b27`
- `NDP_copy01/tb_NDP_Top_new_phy.sv`
  SHA256=`e068f7500f0c71c2ba2c756f74a4519c33d13d4afe0fa4cc9f6c9e79b1e3f994`

普通 runner 不增加服务器源码 preflight；actual production compile identity 仍由正式
return 自然回收。

## 2. v3 正式 return receipt

正式 return：

```text
C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n71_n75_e1f_native_v3_return.zip
bytes   42083
SHA256  56e2a60ed7edfdea381cb1b72d528e922aaeac19d4a1d938cc6bb1ab555ece31
```

相邻 sidecar 不存在；仅按用户担保豁免外部 transport sidecar。ZIP CRC、single root、
path safety、duplicate/symlink、内部 `RETURN_MANIFEST.json`、allowlist exact-set、
逐文件 receipt 和 frozen source binding 均通过。

冻结 source：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_n75_e1f_native_v3.zip
bytes   3753949
SHA256  cfd37a380bc862a6a3c2d22bff01d0fe9b2ec2a25c04e9bae2bd7982971efae6
```

returned manifest、`sca_cfg.json`、`sca_cfg_D.json` 与 source bytes 精确相等；
package/install preflight 通过，A preload=`0`、external input=`16`、config=`32`、
B destination=`128`、formal D target=`144`，且 runtime D pre-sim 全部不存在。

机器分析：

```text
artifacts/operator_config_validation/
  r5-node0071-node0075-e1fb0f7-native-ordering-v3-return-analysis/report.json
SHA256  09c31a2fdea7c9e90e71339118620bf206f0a0ba541353058be9052786258aaf
status  RETURN_VALID_COMPILE_FAIL_SUCCESSOR_REQUIRED
```

analyzer：

```text
tools/analyze_node0071_node0075_e1fb0f7_native_v3_return.py
SHA256  7a5f82d2da56e9073ec2ec7123dae5fb33660806e44656e0112e44733bd19a2f
```

## 3. RETURN_ANALYSIS / LPG / FD / HANG

actual compile argv 精确进入：

```text
make -C /home/panqs/ndp/NDP_copy02 -f Makefile.tb_NDP_Top_new_phy compile
RUN_DIR=/home/panqs/ndp/NDP_copy02/run_r5_n71_n75_e1f_native_v3
VCS_EXTRA_OPTS=+define+NATIVE_RETURN_OBSERVER_ENABLE
               +incdir+/home/panqs/ndp/r5_n71_n75_e1f_native_v3/obs
```

状态：

```text
compile_exit_status = 2
simulation_status   = 125 sentinel / NOT STARTED
runner_exit_status  = 2
signal_status       = NONE
dynamic_attempt     = false
```

`LAST_PROVEN_GOOD`：
package/install exact-tree preflight、144-target runtime-D absence通过；VCS 已解析服务器
design/TB并进入 exact package-local observer include。

`FIRST_DIVERGENCE`：

- observer line 211：`always @(posedge clk_sg)`，VCS 报 bare `clk_sg` undeclared；
- observer line 218：bare `rst_n_sg`，VCS 独立报 undeclared。

实际 TB scope 只有 `clk/rst_n`，而目标 SG domain 位于
`u_NDP_Top_new.clk_sg/rst_n_sg`。v3 focused wrapper 人工声明了两个 bare leaf，导致
本地正控错误放行。

分类：

```text
PACKAGE_LOCAL_DELIVERY_SELF_AUDIT_ESCAPE
```

`HANG_ROOT_CAUSE`：

```text
NOT_A_HANG_SIMULATION_NOT_STARTED;
compile failure is uniquely caused by package-local observer TB-scope
clock/reset binding.
```

这不是 arithmetic、recurrence、config、instance ordering 或 functional RTL 失败。

## 4. 动态门裁决

仿真未启动，因此所有动态事实固定为未到达/未观测，而不是“实际为零”：

- producer downstream/hub acceptance → node0075 pass00 first read：
  `NOT_REACHED_UNOBSERVED`；
- node0075 actual A accepted reads：`null`，不是0；
- configured reload 仍为恰好8 pass、`8192 × 32B = 262144B`、
  unique A byte set=`32768B`，但这些仍只是 config-bound E2；
- actual per-pass/slice ordered hash：未观测；
- formal D：`0/144` produced，missing=`144`；mismatch=`0`不构成数值通过；
- natural terminal=false；E3/E4/E5=false。

没有 opcode110 barrier claim，没有把 command order 升级为通用 fence，也没有新增 RTL
故障结论。

## 5. v4 规则漂移隔离

v4 deterministic build 在 final release 前遇到 current 配置/服务器规则更新，因此保留为：

```text
HELD_RULE_DRIFT_BEFORE_RELEASE
```

未删除、未覆盖、不可运行：

```text
artifacts/operator_config_validation/r5-server-test-packages/
  r5_n71_n75_e1f_native_v4.zip
bytes   3754618
SHA256  a695384142d75e706246ab9be961fa8544a9343148ac78e681c5e39fc21cca1a
```

该身份不冒充 current successor。

## 6. fresh v5 最小修正

v5 只改变：

1. fresh package/install/run/return identity；
2. observer progress clock：
   `posedge u_NDP_Top_new.clk_sg`；
3. observer reset：
   `u_NDP_Top_new.rst_n_sg`；
4. final validator 的真实 TB-scope/XMR、actual-consumer、predicate trace 和
   current release-gate matrix。

observer source：

```text
tests/rtl/node0071_node0075_e1fb0f7_native_ordering_observer_v4.svh
SHA256  662f5017ea4e183361cebf3e6b38ee269f5703e0c3394416a69865100f983eec
```

DB-domain public `clk` 不等价于 `clk_freq_new` 产生的 SG-domain clock；改用 DB clock 会
改变 SG accepted-handshake 的采样语义。因此保留必要的 current private XMR，并绑定 exact
TB/top/filelist/clock bytes、实例路径、1-bit width、owner clock/reset。TB 已有多个相同
XMR consumer；删除/改名目标 leaf及错误 sibling path 三类负控均 fail closed。focused
wrapper 对外部 XMR 的 specialization 明确不作为 leaf 存在证明。

final actual-consumer closure：

```text
consumer expressions = 5
unique package-local identifiers = 17
uncovered = 0
focused Icarus positive = PASS
XMR target proof = PASS
```

predicate trace 使用 final observer expression及 production runtime `_parse_canonical`：

```text
predicate_count = 3
class_count     = 3
uncovered       = 0
exit            = 0
trace_sha256    = 0e3b76f8563358ecbe827fb9144e93aa9a8348640676421a60c77cffb459ab34
```

覆盖 final success 每个 AND conjunct 近邻反例、producer boundary 前/中/后、
req+wdata+finish和start+finish同时事件、stable rising level、连续SG accepted
handshake、reset、无SG edge、inactive stage gap及v3 bare-scope escape。

## 7. frozen config / causal-slice receipt

相对 frozen v3 共比较498个 causal/numeric/config成员：

- missing=`0`；
- unexpected changed=`0`；
- 除 `workload/sca_cfg.json` 与 `workload/sca_cfg_D.json` 外逐字节相等；
- 两个 SCA 只把 package namespace 从v3改为v5；归一化 namespace 后逐字节等于v3；
- config、mapping、bitstream、execplan、golden及causal transaction语义未变。

因此 current 新门裁决为：

- `CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001`：
  `not_applicable / receipt_reuse`；
- `CDA-CONFIG-BOUNDARY-MICROTRACE-001`：
  `not_applicable / receipt_reuse`；
- 未重跑 numeric/W3/golden，也未伪造新 ledger/microtrace PASS。

## 8. PACKAGE_READY_NOT_RUN

final ZIP：

```text
artifacts/operator_config_validation/r5-server-test-packages/
  r5_n71_n75_e1f_native_v5.zip
bytes   3755005
SHA256  c2189b3d7f1153f2c47cee6887ea44603e6683ddada77d0eb7d2a57748c3e08b
```

sidecar：

```text
artifacts/operator_config_validation/r5-server-test-packages/
  r5_n71_n75_e1f_native_v5.zip.sha256
bytes   95
SHA256  d88a824a0ac16391ff673d3a48a88e1058e32f1789e3065bf7953661bb8c710b
```

deterministic build report：

```text
artifacts/operator_config_validation/
  r5-node0071-node0075-e1fb0f7-native-ordering-package-v5/build_report.json
SHA256  22652e5adb9a33963a2fe3ce9961f7e769e2b54c3b6cfc7d647119d9950526d5
deterministic_double_build = true
```

current final-ZIP audit：

```text
artifacts/operator_config_validation/
  r5-node0071-node0075-e1fb0f7-native-ordering-package-v5/
  final_zip_self_audit.json
SHA256  369c8c3fb0afaa33543c05c4e9c218082ce79db3bc89e57456748b35d9816d9d
FINAL_ZIP_RULE_SELF_AUDIT_PASS = true
errors = []
blocking_failures = []
```

单一 `release_gate_matrix`：

- core_always：applicable/blocking/PASS；
- runner：fresh extract→compile stub→EXIT与TERM finalizer PASS；
- package_local_hdl：applicable/blocking/PASS；
- materialized_config：package-namespace-only changed surface，
  normalized frozen receipt PASS；ledger/microtrace not-applicable/reuse；
- diagnostic_semantics：applicable/blocking/PASS；
- return_result：applicable/blocking/PASS；
- record_only：mutable plan与return-time server source identity，不阻断。

唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期正式回传：

```text
r5_n71_n75_e1f_native_v5_return.zip
```

状态固定：

```text
PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN
candidate_release=false
diagnostic_only=true
evidence_level=E2_LOCAL_ONLY
functional_rtl_modified=false
server_uploaded=false
server_run=false
lease_taken=false
```

## 9. BLOCKER_DELTA

本地关闭：

- `B_MATMUL_NODE0075_V3_PACKAGE_LOCAL_OBSERVER_TB_SCOPE_CLOCK_RESET_UNRESOLVED`
- v3 focused wrapper 人工 bare clock/reset leaf 的 self-audit escape。

保持开放：

- `B_MATMUL_NODE0075_SERVER_NATURAL_TERMINAL`
- `B_MATMUL_NODE0075_FORMAL_D`
- `B_MATMUL_NODE0075_PRODUCER_ACCEPT_TO_PASS00_FIRST_READ_ORDERING`
- `B_MATMUL_NODE0075_ACTUAL_A_READS_8192_AND_HASH`

不重开 arithmetic/recurrence、handler/registry、materializer、config-bound E2；
v5 仍需正式服务器 return 才能裁决8-pass actual acceptance、144项D和自然终态。

## 10. RULE_CONFIRMATION

`RULE_CONFIRMATION`，不是新规则提案：

- `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`
- `CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`
- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`
- `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`
- `CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001`
- `CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001`
- `CDA-CONFIG-BOUNDARY-MICROTRACE-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`

证据是 v3 actual production VCS bare-scope compile escape、v5 exact current TB/top/filelist
XMR正负控、source-bound predicate trace、单一 release matrix、frozen causal-slice
receipt及current final-ZIP PASS。claim boundary 仅覆盖 package-local delivery、
diagnostic/result trust 和冻结配置适用性；不证明服务器 functional RTL、自然终态、
actual A acceptance、formal D、E3/E4/E5或通用visibility fence。
