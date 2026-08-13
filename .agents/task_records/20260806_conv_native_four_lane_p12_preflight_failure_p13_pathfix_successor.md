# Conv native-four-lane p12 preflight failure → p13 pathfix successor

## Scope and ownership

- Operator family: Conv node0004 native four-lane performance candidate only.
- Mainline / structured return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- Serialized Conv, materialized workload/config, numeric/W3/golden, diagnostic
  observer, timeout, package runtime, functional RTL, public rules and plan were
  not modified.
- No server upload, execution or lease action was performed.

## Current authority receipts

- `.agents/agent.md`: bytes `13174`, SHA256
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`.
- `.agents/plan.md`: bytes `40135`, SHA256
  `43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70`.
- `.agents/rules/生成前必读索引.md`: bytes `14875`, SHA256
  `1253c18b0008f3a06d509ae15ddaf2c4cd1e95c88f7cd73ec48adaafc7249500`.
- `.agents/rules/服务器测试包生成规则.md`: bytes `93382`, SHA256
  `b1a29b114c57a89dadd56dbb293aeba545cd3acfb3200cadc15058126f359724`.
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`: bytes `6044`, SHA256
  `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`.

## p12 formal return-equivalent analysis

Classification:

`PACKAGE_HELD_PACKAGE_LOCAL_RUNTIME_PREFLIGHT_PATH_BUDGET_MALFORMED`

The user actually invoked exact p12 on the server. It failed before production
compile or DUT simulation at
`node0004_assumed_hardware_server_runtime.py:path_budget`, with
`RuntimeErrorContract("path budget is malformed")`. No return ZIP or sidecar
was published because p12 installed its shared finalizer and signal traps only
after path-budget and package preflight.

The exact p12 manifest declared:

- `max_projected_relative_path_chars = 112`;
- longest projected path
  `install/cfg_pkg/r5_n4_0cc_p11f_pubord/runs/c0/install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin`;
- actual Python string length `115`.

The exact runtime requires
`len(longest_projected_relative_path) ==
max_projected_relative_path_chars`, so p12 was deterministically rejected. With
the correct value `115`, the declared 96-character target-root projection is
`212/240`; the actual `/home/panqs/ndp/NDP_copy02` projection is `142/240`.
This was manifest self-inconsistency, not a server path-length overflow.

The local release audit escaped because it ran exact `preflight` but did not run
exact `path-budget`; its runner harness replaced `path-budget` with an
unconditional success stub and had no preflight-failure publication scenario.

Formal return-equivalent analysis:

- `outputs/conv_native_four_lane_0ccae916_p12_preflight_failure_analysis/report.json`
- bytes `3395`
- SHA256
  `278c24eb540340e2c82451d049d7829f24b3b62c169ce1b493a309da69a60de4`

Claim boundary: no DUT/RTL/config/numeric/natural-terminal/formal-D/correctness
or performance inference is made from this compile-before failure.

## Fresh p13 correction

Fresh package identity: `r5_n4_0cc_p13_pathfix`.

Changed surface:

1. Final path budget is regenerated from the final exact package and records
   `115/115`.
2. Shared EXIT/HUP/INT/TERM finalizer is installed before exact path-budget and
   package preflight.
3. Package-local preflight stage/status and bounded stderr receipts are added
   to the return allowlist.
4. Path-budget/preflight failure now produces a partial return under the fixed
   server result root without reaching compile.
5. Fresh package/return/work-root identity consumers are normalized to p13.

Exact source p12 ZIP:

- bytes `45883980`
- SHA256
  `ab8f13aaa2e66f01bd9c5461f8131b9cf0f89fb1706feb5fcd6aac0f15957646`

Frozen-surface comparison found exactly five changed paths:

- `PREPARE_AND_RUN.sh`
- `README.md`
- `TEST_PACKAGE_MANIFEST.json`
- `package_manifest.json`
- `package_tools/fixed_simresult_publisher.py`

All 98 frozen members under workload/runtime, diagnostics, tb_probe, package
runtime/base runtime, observer guard/finalizers and root gate were byte-equal.

Build tool:

- `tools/build_conv_native_four_lane_0ccae916_p13_pathfix_package.py`
- SHA256
  `c9273984721b64b24e2a630e3975e5d31933905cf2ef1ca7be85349221ed314b`
- deterministic double build: PASS.

Final audit tool:

- `tools/validate_conv_native_four_lane_0ccae916_p13_pathfix_package.py`
- SHA256
  `cec4621655b8629d50687d602bc6903c8407e9c4f2d3cbc6ffdc14dcdde0ea60`

## Final release gates

Final audit status: `PACKAGE_READY_NOT_RUN`.

- final ZIP CRC/sidecar/manifest exact-set: PASS;
- exact runtime `path-budget` on final ZIP: PASS;
- exact runtime full package `preflight` on final ZIP: PASS;
- stale count, changed-longest and actual-over-limit path-budget negatives:
  fail closed;
- package file mutation preflight negative: fail closed;
- exact runner control-flow matrix:
  normal / compile-fail / HUP / INT / TERM / path-budget-fail /
  preflight-fail all PASS;
- both package-local failure scenarios publish bounded partial return with
  compile/simulation not started;
- every runner scenario preserves NDP-root direct-child names+types exact-set;
- fixed-result sidecar and duplicate-absence conjunction: PASS;
- package-local HDL: `RECEIPT_REUSE`;
- materialized config: `RECEIPT_REUSE`;
- diagnostic semantics: `RECEIPT_REUSE`;
- no DUT was executed locally, so natural terminal, formal 320D and E3/E4/E5
  remain unclaimed.

Final audit receipt:

- `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p13_pathfix/r5_n4_0cc_p13_pathfix.final_zip_audit.json`
- bytes `37249`
- SHA256
  `8342ba8cb5cb966af449773cc259337e12b610e447f1333c1566ed2d22efb77e`

## Storage rotation and operator handoff

p12 was actually run and its formal stderr-equivalent evidence was consumed, so
its complete package/receipt set was preserved under:

`artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p12_rootgate/`

The p12 archived ZIP retains SHA256
`ab8f13aaa2e66f01bd9c5461f8131b9cf0f89fb1706feb5fcd6aac0f15957646`.

p13 is the unique pending native-four-lane package:

- pickup:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p13_pathfix.zip`
- bytes `45888225`
- SHA256
  `a2c9e849bf57bc96d05ceb50c22351ae512470343bf1c96928d5b57962c8fe01`
- sidecar remains receipt-only under `pending_receipts`;
- storage audit: PASS;
- `PACKAGE_STORAGE_INDEX.json`: bytes `118185`, SHA256
  `2e1ab0cdf78afeba0ba684db6f026dd505f4676d1608bc5da17ce4382a5208aa`.

Server command after extracting the ZIP:

`bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`

Expected server result:

`/home/panqs/ndp/simresult/r5_n4_0cc_p13_pathfix_return.zip`

The matching `.sha256` is published beside the return on the server. No
same-name return ZIP/sidecar is permitted under NDP_copy0x, package root,
install namespace, run root or launch cwd.

## Rule feedback

`RULE_CONFIRMATION`

The current path-length-budget, strict exact preflight, runner-to-compile
positive control, fixed simresult atomic publication, NDP-root top-level
exact-set and package storage rotation rules are sufficient. The p12 escape was
an implementation/audit omission: the final manifest length invariant was not
executed by exact runtime, and the harness stubbed the changed predicate. No
non-synonymous public rule delta is proposed.
