# Conv node0004 v6 hangloc return analysis

## Scope and receipts

- Operator owner: Conv/SA.
- Source package: `r5_n4_hw_v6_hangloc.zip`,
  SHA256 `2a0ecf7e0218a2a65d37d281ef46343f66e20ca4359cfacf062bf88f89dd1021`.
- Return ZIP:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n4_hw_v6_hangloc_return.zip`,
  SHA256 `787f68073da9d283f7862b1eb44c086c3158e207a1e082cee5f736d29a5ad606`.
- Adjacent return sidecar matches. Its file SHA256 is
  `56c4e9e08c45204dbe15a3d06303e1e1de2b51f13a70e621f72adbbd76b7ffb`.
- Mutable plan receipt:
  `c81e728358f50c4118fba2d4076612caf4ccfb3c28faadb7a0a7f5f9a7540f7f`.
- Active server-package rule:
  `06ec5cde2920f6aa0f11e4a2ec23d9cec2621015afe706ab8ec83e3d4603089c`.
- Applied gates:
  `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001` and
  `CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001`.

No node0004 W3 numeric analysis was repeated and the frozen workload was not
rebuilt. No server path outside the returned ZIP was inspected, and no server
upload or run occurred.

## Return integrity and execution gate

The ZIP CRC passes. It has one root, 13 entries, and the 12 allowlisted payload
records plus `RETURN_ALLOWLIST.json` form an exact set. All recorded sizes and
SHA256 values match.

Package and install preflight pass: 94 package files, 86 c0 input leaves, 28
formal-D targets initially absent, and observer payload/XMR identity valid.
Compilation and elaboration succeed. The simulator loads all 86 matrices,
prints `Reg Started.` and `[2446089000] INFO: slice start`, then ends with
`run_exit_status=125` and `signal_status=INT`. There is no natural terminal and
no formal D readback, so E3, E4, and E5 remain closed.

The host progress log contains 103 samples from monotonic 185214.27 to
191334.51 seconds: 6120.24 seconds, or about 102 minutes. Every sample reports
`observer_bytes=0` and `last_progress=NONE`. There are zero `PROGRESS_WINDOW`
records and no `DIAG_DECISION`.

## FIRST_DIVERGENCE

This return exposes a package-side compile-binding error before any Conv stall
boundary can be measured:

```text
v6 source PREPARE_AND_RUN.sh:
VCS_EXTRA_OPTS="+incdir+$package_root/tb_probe"

returned compile_driver.log:
... +incdir+/home/panqs/ndp/r5_n4_hw_v6_hangloc/tb_probe
```

Neither source nor executed compile command contains
`+define+NATIVE_RETURN_OBSERVER_ENABLE`. The runtime argv does contain
`+RETURN_OBSERVER` and `+RETURN_HANG_DIAG`, but those plusargs cannot select a
compile-time optional include. Consistently, there is no time-zero
`[RETURN_OBSERVER] enabled` record and no observer output file.

`observer_precompile.json` verifies only the package-local observer payload,
include directory, and static XMR form. It does not prove that VCS selected the
optional observer branch. This is exactly the distinction required by the
active long-run progress rule.

## PROGRESS_ADJUDICATION and HANG_ROOT_CAUSE

- `PROGRESS_ADJUDICATION=PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE`.
- It is not `C0_STILL_PROGRESSING_NOT_FINISHED_AT_BUDGET`: no qualified windows
  were captured, so no rate or completion estimate exists.
- It is not `LONG_RUNNING_HANG_AT_<boundary>`: the four-window rule never ran,
  so none of the eight boundaries is proven.
- `HANG_ROOT_CAUSE` for the original Conv execution remains
  `UNRESOLVED_BECAUSE_V6_DIAGNOSTIC_WAS_NOT_COMPILED_IN`.
- The diagnostic failure itself has a definite root:
  `V6_PACKAGE_OMITTED_NATIVE_RETURN_OBSERVER_ENABLE`.
- A longer/full run is not justified until the bounded diagnostic is actually
  compiled in and returns a decision.

## Package-side repair

The unique successor is `r5_n4_hw_v7_hangloc_bind`. It adds exactly
`+define+NATIVE_RETURN_OBSERVER_ENABLE` to `VCS_EXTRA_OPTS`, retaining the
package-local include directory, c0 workload, observer, counters, four-window
stall rule, and 8,388,608-cycle maximum diagnostic budget.

- Classification:
  `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`.
- ZIP SHA256:
  `7752d9023f0ddae7cb506f44b4cde44f8fc8308b3b85594d0a8aae5a2b5eadc2`.
- ZIP bytes: `5803877`.
- Sidecar file SHA256:
  `4f19cd23a2d444838fd15bf636bf91e7e572dc99e5e4a5eae2bbac7db694daac`.
- Validation SHA256:
  `ad43c46625b2e5834693ead990bbe601bfea932d8554a8af80344ff3b183f15e`.
- Package files: 94; ZIP entries: 95; single root and CRC pass.
- Repeated package trees and deterministic ZIPs are byte-identical.
- Focused unit tests: 5/5 PASS.
- Functional RTL entries: 0; server TB modified: false.
- `candidate_release=false`; no E4/E5 claim.

## BLOCKER_DELTA

- ADD `B_CONV_NODE0004_V7_PROGRESS_BIND_DYNAMIC_VERIFICATION`.
- QUARANTINE v6 as `PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE`; its package-side
  compile-binding defect is corrected in v7 but not yet dynamically verified.
- KEEP `B_CONV_NODE0004_C0_LONG_RUNNING_HANG_ROOT_CAUSE`.
- KEEP `B_CONV_SERVER_DYNAMIC_RELEASE`.
- KEEP `B_CONV_SERVER_RTL_IDENTITY`.
- KEEP `B_CONV_INT8_SA`.
- CLOSE none until a valid v7 return proves the repaired observer binding.

## RULE_DELTA_PROPOSAL

None. The active rule already says that an include directory without explicit
enable-macro/compile receipt is not a valid observer binding.

## PACKAGE_RELEASE

Functional package: `NONE`.

Diagnostic package:
`r5_n4_hw_v7_hangloc_bind.zip`,
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`.

## Evidence assets

- Machine report:
  `artifacts/operator_config_validation/r5_conv_node0004_v6_hangloc_return_analysis_v1/report.json`,
  SHA256 `839e4e18bbbc56ed0ef7db0d0d9a82a3c203f51de85e7db3024c1d959b05a355`
  at the time this task record was written.
- Runtime:
  `tools/node0004_hang_localization_runtime_v7.py`,
  SHA256 `5e5b6b4e0880c4632f7789a888937228d65d44f214657c682919f606835b0151`.
- Builder:
  `tools/build_node0004_v6_hang_localization_bind_fix_package_v7.py`,
  SHA256 `144c400eaf39580fbffa1dd104fcbf6623b075e8eceaae118596671ffa57c773`.
- Focused test:
  `tests/test_node0004_v6_hang_localization_bind_fix_package_v7.py`,
  SHA256 `563c66102e577afe673bf351f61f1dd3580dc10a916d25ca4c7f699caa4ce422`.
