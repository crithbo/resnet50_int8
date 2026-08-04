# GAP node0071 v4 hangloc return 裁决与 v5 observer binding 包

日期：2026-07-30

唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

正式 return：

```text
C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n71_gap_v4_hangloc_return.zip
bytes=61643
SHA256=3708beafb70675f9f838cd38d01170241775ba78e2e1f1cf3d53949c69b60d44
sidecar SHA256=0cecd35cbec4c5ff92e8af4e76dc32578f818f207bad5da6978ba1501342eca2
```

相邻 sidecar 内容精确；ZIP CRC、safe paths、19 项 exact-set、18 项
manifest records 逐项 size/SHA、return allowlist subset 与 49 项 required-missing
delta 全部通过。

绑定冻结 source package：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v4_hangloc.zip
SHA256=3c49472421dbf9e7a1cfc9bab42bdc677db6d2dc2781fb4ad18ff119968ac730
```

returned package manifest、SCA、SCA_D 与 source package 逐字节相等；
package/install preflight valid，runtime D 在仿真前不存在。

执行联合门：

```text
compile_exit_status=0
simulation_exit_status=125
runner_exit_status=125
signal=INT
natural_terminal=false
formal_D=0/48
missing_count=48
mismatch_byte_count=0 (不可评价)
all_terms_true=false
E3=FAIL
E4=FAIL
E5=FAIL
```

主机总墙钟 2384.724212281 s；仿真墙钟 2316.142636341 s。slice start
为 702678000 ps，人工中断为 16119663125 ps；slice start 后 event time
前进 15416985125 ps（15.416985125 ms）。

## PROGRESS_ADJUDICATION

```text
PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE
```

40 个 host 采样全部为：

```text
observer_bytes=0 OBSERVER_NOT_CREATED
```

没有 stage/Start_Comp、qualified accepted、qualified completion、last/terminal
或 stall-window 证据。event time 前进和人工 INT 不能区分 DUT 仍前进与 stall，因此禁止
裁决 `STILL_PROGRESSING_NOT_FINISHED` 或 `LONG_RUNNING_HANG_AT_<boundary>`。

observer 四向绑定：

1. source：PASS；最终 source package 中唯一
   `tb_probe/native_return_observer.svh`，SHA256
   `47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`。
2. include：PASS；runner 与实际 compile log 均带 package-local `+incdir`。
3. compile enable：FAIL；runner 与实际 compile log 均缺少
   `+define+NATIVE_RETURN_OBSERVER_ENABLE`。
4. runtime/return：实际 argv 带 `+RETURN_OBSERVER` 与输出路径，但没有 time-0 enabled
   marker、observer log 或 returned observer evidence，故 FAIL。

## HANG_ROOT_CAUSE / FIRST_DIVERGENCE

```text
HANG_ROOT_CAUSE=UNRESOLVED_DUE_TO_PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE
FIRST_DIVERGENCE=PACKAGE_OBSERVER_ENABLE_MACRO_NOT_BOUND_AT_COMPILE
BOUNDARY=compile command construction before simulation
```

compile-time guarded include 未被选择；runtime plusarg 不能替代 compile enable macro。
这是一处明确、合法的包侧诊断基础设施修复，不是 GAP 数值/config/RTL 分歧。

## BLOCKER_DELTA

新增：

```text
B_GAP_NODE0071_V4_PACKAGE_OBSERVER_COMPILE_ENABLE_MISSING
```

重分类：

```text
B_GAP_NODE0071_LONG_RUNNING_HANG_ROOT_CAUSE
-> UNRESOLVED_DUE_TO_PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE
```

保持：

```text
B_GAP_NODE0071_DYNAMIC_RESULT
B_GAP_SERVER_RTL_IDENTITY_UNBOUND
B_GAP_E4_E5
```

## RULE_DELTA_PROPOSAL

`ALREADY_COVERED`。本轮防重犯验收项已由
`CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001` 覆盖：

- 最终 ZIP 内唯一 manifest-bound observer source；
- 最终 compile driver 的 package-local `+incdir`；
- 最终 compile driver 的精确 enable macro；
- runtime argv、time-0 marker、observer log、actual compile/simulator argv、
  progress summary、allowlist 与 signal trap 的联合收据；
- 分别删除 source、incdir、macro、runtime-return 的四个负控均 fail closed。

服务器包规则完整读取 SHA256：

```text
4c960c5cee73355d08f17d9d1a17edb2931b6a0336ae3831372b41f6af4dc8dc
```

plan receipt 仅 mutable provenance：

```text
c81e728358f50c4118fba2d4076612caf4ccfb3c28faadb7a0a7f5f9a7540f7f
```

## PACKAGE_RELEASE

唯一 fresh successor：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v5_obsbind.zip
bytes=1782093
SHA256=159bebac586be3a40ae937736b0368593ced34c7b8128fde7858930b53ebef8d
status=DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN
```

该包只修复 observer compile/runtime/return 四向绑定。73 个冻结 numeric workload
文件逐字节相等；sum/tail/golden/config 未重建、未重跑。两次独立构建 ZIP 相等，
fresh-extract package preflight valid，`bash -n` PASS。最终 ZIP 独立四向 validator
PASS，四个负控全部 fail closed。

服务器唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期回传：

```text
r5_n71_gap_v5_obsbind_return.zip
r5_n71_gap_v5_obsbind_return.zip.sha256
```

未上传、未运行、未检查服务器文件、未取得 lease；未修改功能 RTL、plan 或公共规则。
本轮没有重复 GAP sum/tail 数值分析；消费冻结 node0071 complete local E2、v4 source
package 与 v4 return 证据。
