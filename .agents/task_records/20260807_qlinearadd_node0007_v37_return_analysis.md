# QLinearAdd node0007 v37 formal return analysis

Date: 2026-08-07

## Provenance

- analysis owner thread:
  `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target thread:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`
- return:
  `C:\Users\15383\Downloads\r5_qadd_n7_cout32_rootclean_v37_return.zip`
- return bytes/SHA256:
  `56899633` /
  `d0dbdfd7fbe38457a0cd22918dbd30eff2dd6b23203eedce7c6cf7edb9203cd2`
- bound source:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_cout32_rootclean_v37.zip`
- source bytes/SHA256:
  `26178383` /
  `699696dcf59e1453669aa0af12c599963d05ed176f417858ddf2095fee4fcf87`

The absent adjacent return sidecar is accepted only for the external
transport under
`CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`.
It does not relax any internal receipt.

## RETURN_ANALYSIS

`SPLIT_C_NATURAL_TERMINAL_28D_STRUCTURAL_PASS`

Independent checks pass for:

- ZIP CRC, one exact root, safe paths, no duplicates or symlinks;
- `RETURN_MANIFEST` exact-set, allowlist and every file size/SHA receipt;
- returned package manifest byte equality to the frozen source ZIP;
- package/install preflight and runtime formal-D initial absence;
- observer source/macro/argv/time-0/returned-log binding;
- compile exit `0`, simulation exit `0`, signal `NONE`;
- four ordered stages ending at `op_fp32_add COMP_FINISH`;
- canonical decision digest and
  `NATURAL_TERMINAL_OBSERVED / ORDERED_FINAL_STAGE_COMP_FINISH`;
- fixed `/home/panqs/ndp/simresult` publication and unchanged NDP root
  direct-child exact-set;
- result-gate conjunction `all_terms_true=true`.

Host runtime was approximately `23650.2138 s` total and `23573.1060 s`
inside simulation. The DUT ended with `$finish`, not timeout or external
interrupt.

## 32B Buffer5 to 16B MSE proof

The target evidence is taken from the final `op_fp32_add` stage, not an
earlier stage and not a held level.

```text
Buffer5 qualified write delta = 1,166,332 - 1,091,068
                              = 75,264 rows
Buffer5 bytes                 = 75,264 * 32
MSE4 ch0 accepted wdata       = 75,264 * 16 bytes
MSE4 ch1 accepted wdata       = 75,264 * 16 bytes
MSE4 outstanding ch0/ch1      = 0 / 0

75,264 * 32 == (75,264 + 75,264) * 16
```

This dynamically closes the v36 eight-lane/32-byte FP32 output-supply
blocker within split C.

## Formal D and evidence level

- scope: split-C `op_fp32_add` stage-local FP32 output only;
- expected/present/missing/invalid: `28/28/0/0`;
- every target decodes to `2,408,448` bytes and `150,528` 128-bit lines;
- server result conjunction: pass;
- `mismatch_evaluable=false`.

The package binds no independent golden for these stage-local readbacks.
Therefore the returned `mismatch_bytes=0` is structural bookkeeping and is
not a numeric comparison.

- E3: `true` (bound production compile/run reached a natural terminal);
- E4: `false` (independent-golden equality is not evaluable);
- E5: `false` (no fresh-identity repeat after E4).

## LPG / FD / root

- `LAST_PROVEN_GOOD=OP_FP32_ADD_ORDERED_COMP_FINISH`
- `FIRST_DIVERGENCE=NONE_WITHIN_SPLIT_C_DECLARED_SCOPE`
- next unproven boundary:
  `op_tail_mul -> op_tail_round -> final UINT8 D`
- `HANG_ROOT_CAUSE=NO_HANG_NATURAL_TERMINAL`

## BLOCKER_DELTA

Closed:

- `B_QADD_SPLIT_C_FP32_ADD_32B_BUFFER5_SUPPLY`
- `B_QADD_SPLIT_C_NATURAL_TERMINAL`
- `B_QADD_SPLIT_C_28D_STRUCTURAL_COMPLETENESS`

Kept open:

- `B_QADD_NODE0007_FULL_CHAIN_TAIL_NATURAL_TERMINAL_28D`
- `B_QADD_NODE0007_INDEPENDENT_GOLDEN_E4`
- `B_QADD_NODE0007_FRESH_IDENTITY_E5`
- `B_QADD_SERVER_ACTUAL_RTL_COMMIT_IDENTITY`

The next semantic scope is the six-stage full chain. No further split-C
diagnostic package is justified.

## Shared runtime-layout hold

Mainline has paused fresh full-chain publication while the shared
install-subtree parent contract is corrected. The correct intended boundary
is that only `$server_root/install` must pre-exist; the package may safely
create its own `install/cfg_pkg` and `install/codex_runs` descendants.

`PACKAGE_RELEASE=HOLD_WAIT_SHARED_INSTALL_PARENT_CONTRACT`

No fresh ZIP was generated or published in this task record. The full-chain
numeric/workload/config/golden assets remain frozen for the successor.

## Machine evidence

- analyzer:
  `tools/analyze_qlinearadd_node0007_cout32_rootclean_v37_return.py`
- analyzer SHA256:
  `7e313b8b2bd3e77a5c81669bad72570f6ab97e85cb9aa871cc7db0941f1d9e3c`
- command:

```text
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/analyze_qlinearadd_node0007_cout32_rootclean_v37_return.py --return-zip C:\Users\15383\Downloads\r5_qadd_n7_cout32_rootclean_v37_return.zip --output artifacts/operator_config_validation/r5-qlinearadd-node0007-v37-return-analysis/report.json
```

- exit: `0`
- report:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-v37-return-analysis/report.json`
- report bytes/SHA256:
  `15778` /
  `5b2488cbb93dc70561fc3b7054daf24d0b2ca5b886c889240c99e3b887988266`

## Rule feedback

`RULE_CONFIRMATION`: current result-conjunction, user-attested external
transport, cloud-RTL nonblocking identity and QAdd D-buffer transaction
conservation rules correctly distinguish qualified structural completion
from unavailable numeric E4 evidence. No non-synonymous rule delta is
proposed.

`numeric_analysis_repeated=false`

`workload_analysis_repeated=false`

`configuration_numeric_analysis_repeated=false`

`golden_recomputed=false`

`functional_rtl_modified=false`
