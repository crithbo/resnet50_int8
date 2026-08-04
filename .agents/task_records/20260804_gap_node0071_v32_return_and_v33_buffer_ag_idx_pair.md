# GAP node0071 v32 RETURN and v33 information-gain successor

- Owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Scope: GAP-family return adjudication and package-local diagnostic successor only.
- No plan/public-rule/functional-RTL/other-family modification; no server upload/run/lease.

## v32 adjudication

The submitted no-sidecar return is accepted only at the external transport layer under `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`. ZIP CRC, safe single root, duplicate/symlink exclusion, internal identity, RETURN_MANIFEST exact-set/allowlist/per-file receipts, and source-package binding all pass.

Execution compiled successfully but ended through `INT` with simulation/runner status 125. It is not a natural terminal. Formal D is 0/48 present; `mismatch=0` is unevaluable; E3/E4/E5 and the conjunctive server result gate are false.

- LAST_PROVEN_GOOD: COL-LC0 accepted values 1/3, and all eight writes reaching the MSE write boundary were also accepted by Buffer0 MRM with matching byte-lane strobes.
- FIRST_DIVERGENCE: `COL_LC0_ACCEPTED_BYTE_LANE1_VALUE_PRESENT_ONLY_BEFORE_MSE0_BUFFER_AG_ACTIVITY_AND_NO_BUFFER0_MRM_BYTE_LANE1_WRITE`.
- HANG_ROOT_CAUSE: `LONG_RUNNING_HANG_AT_MSE0_BUFFER_AG_INDEX_PAIRING_BEFORE_BYTE_LANE1_ENQUEUE_PENDING_INPUT_OR_MATCH_MASK_LEAF`.

Machine return report: `artifacts/operator_config_validation/r5-gap-node0071-v32-return-analysis/report.json`, SHA256 `fc7e784c461f2c871cd58ddbc4f73c8e1626b1fd90d6bf4e86484aafe2f7a9d2`.

## v33 successor

Fresh identity: `r5_n71_gap_v33_buffer_ag_idx_pair_diag`.

Classification is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`; candidate release is false and evidence cannot exceed `E2_LOCAL_ONLY`.

The observer uses a time-to-root-cause/information-gain slice rather than a one-leaf probe. In one bounded feature it retains the COL-LC0 evidence and observes both direct MSE0 queue inputs, tag/index, decoded valid/same/gotten/keep masks, all-matched, MSE enable, accepted enqueue versus full rejection, FIFO count, accepted dequeue, and the direct tag/index output consumer. Only qualified accepts are monotonic events. Event emission is capped at 256; stable state is only summarized.

No legal typed checkpoint exists before the internal first-stage queue. Therefore the exact keep set remains all 73 workload/numeric files and the complete ordered-stage/return contract; the drop set is empty. The stall occurs in first-stage `sum_s1`, so later stages never start and deleting them would not reduce this run's observed dynamic duration.

Frozen receipts:

- 73 numeric/workload files byte-equal.
- 119 other non-allowlisted files byte-equal.
- No numeric/sum/tail/workload/config/golden recomputation.
- No timeout, ready/backpressure, lifetime, functional RTL, or pre-FD DUT input change.

Final package:

- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v33_buffer_ag_idx_pair_diag.zip`
- bytes: `1824172`
- SHA256: `5bd5f3a4cc555f618d535aba375363cf0c041abe506d7b3589cc4265b4459c03`
- sidecar SHA256: `9bdb2cdb465d225d5dcd37746ba0e8e782cf3d2076a9b53625fe00b46cb46f1b`
- command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return: `r5_n71_gap_v33_buffer_ag_idx_pair_diag_return.zip`

Validation:

- deterministic double build: equal;
- feature validator: PASS, 67 negatives fail closed;
- full runner safe compile positive: exit 86; wrong identity: exit 5; all runner negatives fail closed;
- real frozen runner TERM path: exit 125, one shared finalizer, stderr empty, partial return exact-set/identity/allowlist valid, nonnatural not misreported;
- focused package-local HDL XMR/sampler syntax and name resolution: compile exit 0; four declaration/use/update/XMR negatives fail closed; no full-design elaboration claim;
- final ZIP current-rule self-audit: PASS, errors 0.

Closure machine report: `artifacts/operator_config_validation/r5-gap-node0071-v32-return-v33-successor/report.json`, SHA256 `0c37f937316dfc09215f632a2d700b8607de665028d9b75d2057b88dc43d7676`.

RULE_CONFIRMATION applies; `RULE_DELTA_PROPOSAL=NONE`.
