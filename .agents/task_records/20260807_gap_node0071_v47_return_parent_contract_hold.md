# GAP node0071 v47 formal return and shared parent-contract hold

- Analysis owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Return:
  `C:\Users\15383\Downloads\r5_n71_gap_v47_stage_transition_rootfix_return.zip`
- Return bytes: `179683`
- Return SHA256:
  `a219978583f67d89974b9ffb584f50658c6acfe6e33fc475423a0d88a1d0ca5a`
- Frozen source:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v47_stage_transition_rootfix.zip`
- Source bytes: `1944021`
- Source SHA256:
  `e5e1e010970230fb9f9706bc2dd2381dbfecd2c304fd48e212587827110567ab`
- Machine report:
  `artifacts/operator_config_validation/r5-gap-node0071-v47-return-analysis/report.json`
- Machine report SHA256:
  `8b8bbcf9b8f332d90aad3fc39ecf47db90b65e028365fe8a83387bd92151bb6d`
- Successor design:
  `artifacts/operator_config_validation/r5-gap-node0071-v47-return-analysis/successor_design.json`

## RETURN_ANALYSIS

ZIP CRC, single root, path safety, duplicate and symlink checks,
`RETURN_MANIFEST` exact-set, source allowlist, per-file size/SHA receipts,
returned package manifest identity, installed SCA/SCA-D, package preflight,
runtime-D-initially-absent, actual compile/simulator argv, package-local
observer binding, and NDP-root direct-child exact-set all pass.

The compile exits `0`. The runner and simulator exit `124` with
`signal=NONE` after `43200.06988434` seconds of simulator wall time, so the
termination is the package's 12-hour timeout, not HUP/INT/TERM and not a
natural terminal. The generic canonical record describes only early completed
windows and is not accepted as progress at timeout.

All 16 selected input payloads are logged as loaded at their expected
slice-address bases. The global-owner-clock stage observer reports:

- selected and EXEC-start-seen masks: `0x000ffff`;
- finish-seen mask: `0x0000001`;
- selected ready mask: slice0 only;
- blocked and compute-active masks: `0x000fffe`;
- noncompute-blocked mask: zero;
- local-empty selected mask: all ones;
- `config_match=1` and `gconfig_ready=1`.

The final stage-transition heartbeat is at `148111459000 ps`,
global edge `118489088`. No newer qualified stage heartbeat is returned for
`31078.922199139` wall seconds before finalization. Stable repeated state is
not counted as progress.

## LPG / FD / root cause

`LAST_PROVEN_GOOD`: all 16 selected slices load input and observe the shared
sum_s1 EXEC_START. Slice0 completes the already-proven
MSE0/MSE3 -> GA -> MSE4 path and reaches `slice_cmpt_finish`.

`FIRST_DIVERGENCE`: selected slices 1..15 remain compute-active in sum_s1
after shared EXEC_START while slice0 completes.

`HANG_ROOT_CAUSE`:
`LONG_RUNNING_HANG_WITHIN_NONZERO_SELECTED_SLICE_SUM_S1_LOCAL_COMPUTE_PIPELINE_PENDING_CONFIG_DELIVERY_OR_FIRST_MISSING_ACCEPTED_CHECKPOINT`.
The global dispatch conjunction is closed, but the first local leaf is not:
the return does not distinguish per-slice config completion from the first
missing accepted MSE0/MSE3, GA, or MSE4 checkpoint. No unique functional RTL
leaf is claimed.

The current cloud authority is
`0ccae916ef61904a64d6cf8ec1d1931b45e428d8`. The return binds the actual
compile root and argv but carries no immutable compiled-commit receipt, so the
actual compiled commit remains `UNBOUND_BY_RETURN`.

## Formal D and evidence level

Formal D is `0/48`: missing `48`, mismatch bytes `0`, exact-set false and
result conjunction false. Mismatch zero is unevaluable under all-missing
readback. There is no numeric failure or pass claim. E3, E4, and E5 are all
false.

## Blocker delta

Closed:
`B_GAP_NODE0071_POST_SUM_S1_MASK_WIDE_STAGE_TRANSITION_CONJUNCTION_PENDING_LEAF`.

Opened:
`B_GAP_NODE0071_SELECTED_SLICES_1_TO_15_SUM_S1_LOCAL_PIPELINE_PENDING_CONFIG_OR_FIRST_ACCEPTED_CHECKPOINT`.

Natural terminal, formal 48D, and actual compiled commit binding remain open.

## Successor and release

The reserved design-only identity is
`r5_n71_gap_v48_multislice_pipeline_diag`. It will use one information-gain
surface covering mask-wide per-slice config start/finish, MSE0/MSE3 accepted
ingress, GA accepted input/output, MSE4 accepted request/write-data, and local
finish. It preserves workload, numeric, golden, functional config semantics,
timeout, backpressure, and functional RTL.

`PACKAGE_RELEASE=NONE`. Mainline ordered a hard pause because the then-current
shared install-subtree helper wrongly required `install/cfg_pkg` and
`install/codex_runs` to pre-exist and caused a real p14 preflight failure.
Correct semantics require only `$server_root/install` to pre-exist; the
package may safely create both second-level directories. No v48 ZIP, sidecar,
server package tree, or pending pickup was generated. Final materialization
must wait for fresh exact rule/tool/schema receipts and a mainline
re-dispatch.

The consumed v47 pending package is intentionally left in place until the
storage manager can atomically rotate it to `tested` together with the future
validated successor; no manual partial storage move was performed.

No numeric/sum/tail/workload/config/golden analysis was repeated. No plan,
public rule, functional RTL, other-family asset, server state, upload, run, or
lease was modified.

## Rule feedback

`RULE_CONFIRMATION`: existing timeout/signal, qualified-progress, canonical,
formal-D conjunction, return allowlist, and continuous-closure rules correctly
classify this evidence.

`RULE_DELTA_PROPOSAL=NONE`. The install-subtree parent-contract correction is
already being handled by mainline; no synonymous GAP-local proposal is added.
