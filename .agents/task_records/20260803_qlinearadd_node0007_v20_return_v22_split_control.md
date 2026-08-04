# QLinearAdd node0007 v20 return → v22 split control

## Provenance

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target/mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- machine report:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-b-dequant-control-v22/release_report.json`
- machine report bytes/SHA256:
  `7150` /
  `55baaa8746100f43ce00232a6e619f1bfe7e8e4157d4c372589290159b3510f4`
- numeric/W3/qparams/tail/workload/config/golden repeated: `false`
- functional RTL modified: `false`
- server uploaded/run/inspected: `false`

## RETURN_ANALYSIS

The v20 return passed CRC, single-root/path, manifest exact-set, allowlist,
returned-source-manifest byte binding, package preflight and installed
preflight.

- source v20 ZIP:
  `13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51`
- return ZIP:
  `fd874e7d0f2ded42a31288bfa273c9fe32323c15455d256fb2cb01e66d0563d7`
- external sidecar: absent, accepted only under the user-attested transport
  rule; all internal gates remained strict
- compile/simulation/signal: `0 / 125 / INT`
- natural terminal: `false`
- formal D expected/present/missing: `28 / 0 / 28`
- mismatch bytes: `0`, unevaluable because all D are missing
- `SERVER_RESULT_GATE=false`; `E3=false`; `E4=false`; `E5=false`

`op_a_dequant` completed after `559628` active cycles. The next physical
stage was `op_b_dequant`, not FP32 add. It advanced qualified traffic and
then VCS reported `INFL_DELTA` / possible zero-delay loop at
`17020861875 ps`, about `154000` active cycles after the B-stage start.
The later `INT` is not a natural terminal.

The returned canonical record claiming
`FP32_ADD_FIRST_OUTPUT_OBSERVED_CONTINUE_STANDARD_PROGRESS` is rejected:
its stage sequence remained `1`, while the actual execution plan was in
stage 2 (`op_b_dequant`), and its snapshot was one-sided MSE0/Buffer0/GA
activity. It cannot close the frozen dual-ingress FP32-add boundary.

## Regression-first adjudication

The user's old-good/new-bad hypothesis is supported and was evaluated
before attributing the failure to the B configuration:

- v18 completed `op_b_dequant` after `540857` active cycles and then
  completed relocation;
- normalized v18→v20 package comparison found no changed input,
  bitstream, stage execplan, configuration or golden payload;
- v20 added the FP32-ingress observer tail and GA-capture shim and enabled
  them throughout A/B, without physical-stage gating.

Therefore the leading cause is a package-local observer event storm, not a
proven functional-RTL or B-config fault. This remains an A/B hypothesis
until the control package returns.

`LAST_PROVEN_GOOD=OP_A_DEQUANT_COMP_FINISH_AND_OP_B_DEQUANT_QUALIFIED_PROGRESS`

`FIRST_DIVERGENCE=V20_OP_B_DEQUANT_VCS_INFL_DELTA_AT_17020861875PS_ABOUT_154000_ACTIVE_CYCLES`

`HANG_ROOT_CAUSE=PACKAGE_LOCAL_OBSERVER_REGRESSION_IS_LEADING_CAUSE_NOT_YET_DYNAMICALLY_CONFIRMED`

## Split execution

The accepted diagnostic split is:

1. A dequant;
2. B dequant;
3. relocation/pad;
4. FP32 add;
5. exact UINT8 tail.

Final acceptance still requires a full end-to-end run. No host-precomputed
internal tensor may substitute a hardware-produced scratch.

The next run is only B dequant. It consumes the frozen original B edge
payload and produces the B scratch in hardware. The v20 FP32 tail and
GA-capture shim are absent; the v18 base observer remains, with a
`16384`-cycle cadence. This directly distinguishes an observer regression
from a B-stage/config/RTL problem and avoids re-running A.

## Quarantined intermediate

`r5_qadd_n7_b_dequant_isolated_v21.zip`
SHA256
`a62c6281072281a9dd9903ec62e99db1fed1fc3859732e1c89234ed5c5dfd126`
is `QUARANTINED_NOT_RUN`: it inherited the suspected v20 observer and its
final audit did not pass. It must not be uploaded or run.

## PACKAGE_RELEASE

`PACKAGE_READY_NOT_RUN`, `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`,
`candidate_release=false`, `E2_LOCAL_ONLY`.

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_b_dequant_control_v22.zip`
- bytes/SHA256:
  `38034925` /
  `4a51be0ab59b0ff8c0754de68f11d7f3d1328b6fe012b3945468b787d2b11fd5`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_b_dequant_control_v22.zip.sha256`
- sidecar bytes/SHA256:
  `103` /
  `80d31fee787b7149bbf58b9202df7689babe588b940cf33f5fb87967c74ddf4f`
- server command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return:
  `r5_qadd_n7_b_dequant_control_v22_return.zip`

Two deterministic builds produced the same ZIP SHA. Final-ZIP current-rule
self-audit passed with `errors=0`. Safe compile-stub positive control,
wrong-identity precompile negative, EXIT and TERM finalizer positives,
feature/stage/marker/receipt negatives all passed or failed closed as
required.

Final audit:

- path:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-b-dequant-control-v22/final_zip_self_audit.json`
- bytes/SHA256:
  `7581` /
  `a747d41b18ed51cc3120ab97c04bb966814e2b7d81e023a23aa127e36412451f`

Build validation:

- path:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_b_dequant_control_v22.validation.json`
- bytes/SHA256:
  `1213` /
  `e95b3385c0cd5b7cc62ab89ccb3c9910e0286c42f5cb4ad6906721dc829a5776`

## BLOCKER_DELTA

- opened:
  `B_QADD_V20_PACKAGE_LOCAL_FP32_OBSERVER_EVENT_STORM_SUSPECT`
- kept open:
  `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`
- closed:
  `B_QADD_V19_OBSERVER_GA_OPERAND_CAPTURE_MON_UNDECLARED`

## RULE_CONFIRMATION

`CURRENT_RULES_SUFFICIENT`.

The current ordered-stage, qualified-event, default-diagnostics and
continuous-return-closure rules already reject the v20 one-sided stage-2
sample as FP32-add success and require the observer-regression control.
No public-rule change is proposed from this evidence.
