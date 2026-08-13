# GAP node0071 v48 return and v49 MSE4 mask-wide release

- Analysis owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Scope: GAP family only; no plan/public-rule/functional-RTL/server mutation.

## RETURN_ANALYSIS

The formal v48 return passed CRC, root/path, duplicate/symlink, internal identity, RETURN_MANIFEST exact-set/allowlist, per-file receipt, and frozen source binding. Compile completed with exit 0. Simulation exited 125 and the runner exited 130 on `INT`; there was no natural terminal. Formal D was 0/48 present, 48 missing, and mismatch 0 was unevaluable, so E3/E4/E5 all remain false.

Qualified evidence proves all 16 slices reached config start/finish, MSE0/MSE3 acceptance, and GA input/output acceptance. Only slice0 reached MSE4 request/write-data and finish. Stable heartbeat levels were not counted as progress.

- LAST_PROVEN_GOOD: all 16 slices through GA output; slice0 through finish.
- FIRST_DIVERGENCE: slices1–15 GA output accepted without MSE4 request/write-data/finish.
- HANG_ROOT_CAUSE: `LONG_RUNNING_HANG_AT_NONZERO_SLICE_GA_OUTPUT_TO_MSE4_REQUEST_WDATA_FINISH_PENDING_LEAF`; the exact leaf was not unique in v48.

The reported Python `SyntaxError` is package-local: the shared EXIT/HUP/INT/TERM finalizer's embedded fallback JSON writer contained an outer-generator escaping defect. It ran after parser calls and before runtime analyze/collect. It removed three required decision artifacts, so it damaged formal return completeness, but it did not affect the already-running functional simulation. Raw observer/log evidence and an incomplete atomic return survived.

Formal machine analysis:

- `artifacts/operator_config_validation/r5-gap-node0071-v48-return-analysis/report.json`
- SHA256 `03dc7c568ac5bfcad61967880e07e52ae8aaca31e46cfe0c071f4fc18654a0eb`

## SUCCESSOR

Fresh diagnostic-only successor: `r5_n71_gap_v49_mse4_maskwide_diag`.

It fixes only the finalizer fallback quoting and adds low-overhead all-slice qualified MSE4 factor evidence from GA outbuffer read through index/request/queue/buffer/prepared/output-buffer/local request/write-data/finish. It preserves the prior qualified checkpoints. Numeric files (73), sum/tail/workload/config/golden, timeout, backpressure, and functional RTL are frozen.

Final ZIP:

- Pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v49_mse4_maskwide_diag.zip`
- Bytes: `1953473`
- SHA256: `eb2f5f02b3dce69aad51a3319972622b7cff8d594ef9cbf5909efb7c4114d85a`
- Server command: `bash r5_n71_gap_v49_mse4_maskwide_diag/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`
- Fixed return: `/home/panqs/ndp/simresult/r5_n71_gap_v49_mse4_maskwide_diag_return.zip`

## LOCAL RELEASE GATES

- Two deterministic builds: byte/SHA identical.
- Family validation: PASS, errors=0; focused HDL positive and declaration-delete/use-typo/critical-update negatives closed.
- Predicate trace: PASS; stable state is not progress.
- Exact runner safe harness: normal=0, preflight-fail=5, compile-fail=73, HUP=129, INT=130, TERM=143; common finalizer and fixed simresult publication passed; stderr empty.
- Shared install-only V2/runtime layout: PASS.
- Final ZIP current-rule self-audit: PASS=true, errors=0.
- Storage rotation: v48 moved to tested; v49 is the only pending GAP package; parallel families were untouched.

Final continuous-closure machine report:

- `artifacts/operator_config_validation/r5-gap-node0071-v48-return-v49-release/report.json`
- Its SHA256 is recorded in the mainline handoff after JSON parse/hash verification.

## RULE FEEDBACK AND CLAIM BOUNDARY

RULE_CONFIRMATION: current fixed-simresult, install-only V2, NDP-root direct-set, time-to-root-cause, predicate-trace, and result-conjunction rules were satisfied.

RULE_DELTA_PROPOSAL: require executable local syntax coverage for every package-local heredoc emitted by an outer generator, including signal-finalizer fallback branches; token and safe-stub checks can miss escaping loss.

PACKAGE_RELEASE=`PACKAGE_READY_NOT_RUN`. v49 is diagnostic-only, unrun, and capped at local E2 evidence. No production compile/simulation, natural-terminal, formal-D, E3, E4, or E5 claim is made.
