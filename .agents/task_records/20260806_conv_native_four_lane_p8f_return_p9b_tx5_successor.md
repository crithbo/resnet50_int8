# Conv native-four-lane p8f formal RETURN → p9b tx5 successor

日期：2026-08-06  
owner：`019fc783-1146-7901-9e40-64d0ed8e052d`  
唯一主线/return target：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 1. 正式 p8f RETURN_ANALYSIS

- 正式 return：
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_0cc_p8f_return.zip`
- bytes：`123440`
- SHA256：`7a2de4c7551f40ed8ab4c82bd6a6efddd985c8e70a6704e9cdc451d2a4d870b9`
- exact source p8f：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p8f.zip`
- source bytes：`66231520`
- source SHA256：
  `1e214ba277992d4ab08795dd35f4db3082ccad4e17bebc2aaf6e473b1bc7c224`
- internal receipt、source manifest、allowlist、exact-set、逐文件
  size/SHA、package/install preflight：全部闭合。

实际执行结果：

```text
compile_exit_status = 0
run_exit_status = 125
signal_status = INT
natural_terminal = 0 / 27
formal D present = 0 / 320
formal D missing = 320
formal mismatch bytes = 0（无有效D，不能解释为数值通过）
result conjunction = false
E3/E4/E5 = false/false/false
```

public-boundary observer 在第一个有效窗口累计 `52,859` 个 qualified
事件后冻结；从 cycle `2,359,296` 到最后 sample cycle `276,561,920`
均为 zero-delta，连续 `261` 个 long-hang 窗口。host 收据跨度
`36,963 s`，所以 p8f 不再是 p7 的“仍前进但一小时超时”，而是
`LONG_RUNNING_HANG_AT_EXEC_TO_SLICE_FINISH`。

actual production identity 收集有效。八个 causal leaves 中七个与云端
`0ccae916ef61904a64d6cf8ec1d1931b45e428d8` 一致；唯一差异为：

```text
Array_Request_Manager.sv
actual SHA = 7892b4345b3a71024126b57a3a0126c489e0bffa2f520e64fa6cf2ed705f9894
cloud  SHA = 026019ed9643b3b7d83bc0888c4f5b89fc4776015524df1c69bacbab5315e557
```

compile 成功后该差异只作 nonblocking provenance，但它仍位于当前
exec→slice_finish causal cone，须由后继动态结果裁决。

机器报告：
`outputs/conv_native_four_lane_0ccae916_p8f_return_analysis/report.json`  
SHA256：
`dd11613617a78d6a580ee84bef0e0a4e0d010582d7ae0190a68224452c4c4c07`

## 2. LPG / FD / HANG_ROOT_CAUSE

```text
LAST_PROVEN_GOOD =
  c0 exec start plus initial 52,859 qualified request/rdata/bank events

FIRST_DIVERGENCE =
  all qualified progress freezes before c0 slice_finish; no formal D

HANG_ROOT_CAUSE =
  KNOWN_TRANSOUT_THRESHOLD_DEFECT_MUST_BE_REMOVED;
  p8f trace itself未到达terminal classifier，
  且actual/cloud唯一差异是causal ARM leaf

root_cause_uniqueness = TWO_CAUSAL_CANDIDATES_REMAIN
```

p8f final Conv bitstream 仍编码
`special_array.transout_last_index=2`。既有正式 trace 已证明真实 accepted
terminal index 为 `4 ×64`、`5 ×192`：threshold2 使 `256/256`
进入 ignore。它是确定配置缺陷，不能继续带入后继。

## 3. p9b changed-causal-slice 修正

仅修改一个逻辑叶：

```text
special_array.transout_last_index: 2 -> 5
```

从 final typed config 重新生成 mapping、bitstream、execplan、SCA。
相对 p7/p8f 的旧 Conv bitstream：

```text
old SHA = 6996170d1c1c3c6b02b9a1980c612c2b207255f2bb1f7fe5e202709acf3ea55b
new SHA = cb12f3345c42d89d17188102bd80cbeef224ddff26fd5726ed1a16af49d14e73
changed offsets = [4459, 4460, 4461]
```

execplan SHA 保持：
`dafcaada34fc48785ea6c9b8e8a224da36dca35e7ee44bdb8e745e337a817934`。
矩阵 payload、地址、W3、numeric、golden、public observer 和 functional
RTL 全部冻结；没有重复运行 numeric/W3/golden。

使用 final RTL 5-bit subtract/classifier 公式的边界 microtrace：

```text
threshold2: released=0, ignored=256
threshold4 negative: released=64, ignored=192
threshold5: released=256, ignored=0
index4 < T -> out/release
index5 = T -> matched/release
index6 > T -> ignore
```

证据：

- local rebuild：
  `artifacts/operator_config_validation/r5-conv-native-four-lane-0cc-p9-tx5-c0/local_rebuild_report.json`,
  SHA `ab491ae3589b01177d29177ca3aea6b0051630543a62050dd564cd90fe18ce7b`
- changed-slice ledger：
  `artifacts/operator_config_validation/r5-conv-native-four-lane-0cc-p9-tx5-c0/causal_transaction_ledger.json`,
  SHA `f6e23cbbc19901598ef2982614774e72aa48714cb9475ce5fad5263984daba6c`
- boundary microtrace：
  `artifacts/operator_config_validation/r5-conv-native-four-lane-0cc-p9-tx5-c0/boundary_microtrace.json`,
  SHA `c8c42869c97cee8babcabffb6383739f9d91bd181cb46bac238f25521d75ffd2`

12h 预算用于让同一个 c0 到达历史 terminal boundary。byte-equal p7
public-surface observer 保留以下唯一判别矩阵：

```text
同一早期public boundary再次冻结 -> actual ARM/source path为首动态分歧
到达SA output或Buffer5              -> tx5修正确实越过旧terminal边界
c0 natural terminal                -> 下一fresh直接提升27-run/320D
```

## 4. PACKAGE_RELEASE

唯一可运行 fresh successor：

```text
identity r5_n4_0cc_p9b_tx5
class    CONFIG_FUNCTIONAL_FIX_WITH_PUBLIC_CAUSAL_DIAGNOSTICS
status   PACKAGE_READY_NOT_RUN
release  candidate_release=false
ZIP      artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p9b_tx5.zip
bytes    5,814,296
SHA256   d85429b61e8270d0c4108bfdcdf3a66bce44a437b8aab96b0412a5555dffb085
sidecar  artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p9b_tx5.zip.sha256
sidecar SHA256 0c1cde9f25adf0deaf4993d64f30710ba8a0bbecf1b2e85b97505265d574effe
```

唯一服务器命令：

```bash
bash r5_n4_0cc_p9b_tx5/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

预期 return：`r5_n4_0cc_p9b_tx5_return.zip`

`r5_n4_0cc_p9_tx5` 是 final preflight 捕获 runtime 候选类型硬编码漂移前的
失败构建，未通过 final audit，不得运行或回传。

final audit：
`artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p9b_tx5.final_zip_audit.json`  
SHA256：
`8e2dc7a04debb2c9b7a809b9279df77a975f9eec7176a374450f8f2064849493`

审计状态：

- deterministic dual build / deterministic ZIP replay：PASS
- exact set / CRC / sidecar / path budget / actual consumer closure：PASS
- changed runtime candidate-class preflight：PASS
- final runner compile→simulator→finalizer safe-stub 正控：PASS
- `TERM` return 与错误 observer SHA 负控：PASS
- package-local HDL：p7 production compile receipt reuse，PASS
- materialized config ledger / boundary microtrace：PASS
- observer/parser/canonical predicate：byte-equal receipt reuse，PASS
- return/result joint gate：PASS
- server action：false

## 5. 性能与 claim boundary

冻结 local E2 反演保持：

```text
logical products                         205,520,896
serialized occurrences                  205,520,896
native four-lane occurrences             51,380,224
compute occurrence reduction                    4.0x
weight payload reduction                         4.0x
activation per-producer reduction                4.0x
B+B' total physical activation reduction         2.0x
serialized maximum useful lane utilization      25.0%
native maximum useful lane utilization         100.0%
```

这些仅是 final config/occurrence 的冻结 E2 反演。p8f 未闭合 natural
terminal/formal D，p9b 尚未上机，所以不得宣称 server 实测性能、E3、E4
或 E5。

## 6. blocker delta

关闭/修正：

- `B_CONV_NATIVE4_P8F_COMPILE_OR_SIMULATOR_LAUNCH_UNPROVEN`
- `B_CONV_NATIVE4_P8F_PROGRESSING_ONLY_NOT_HANG`
- `B_CONV_NATIVE4_TRANSOUT_THRESHOLD_BELOW_ACCEPTED_TERMINAL`

保留：

- `B_CONV_NATIVE4_ACTUAL_ARRAY_REQUEST_MANAGER_IDENTITY_CAUSAL_RISK`
- `B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN`
- `B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN`
- `B_CONV_NATIVE4_FORMAL_320D_MISSING`
- `B_CONV_NATIVE4_E3_E4_E5_UNPROVEN`

## 7. 规则反馈

`RULE_CONFIRMATION`

- `CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001`
- `CDA-CONFIG-BOUNDARY-MICROTRACE-001`
- `CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001`
- `CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001`
- `CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`

`RULE_DELTA_PROPOSAL=[]`

构包后 current receipts：

- plan SHA：
  `96f69d90e79273b1a580790723c73d5810587e8b42a4e92f4582db2730e6c44a`
- server-package rule SHA：
  `36f6596c913120c24725da95e269200ecff4b25130d4eefe8d99d21c7b2e7457`
- config rule SHA：
  `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
