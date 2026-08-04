# QLinearAdd node0007 v24 return and true split v26 release

## Provenance

- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- unique mainline/return target:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`
- machine report:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-v26-release/report.json`
- machine report bytes/SHA256:
  `11274` /
  `04b8e736aae54e0c7372d8d39b4e94aa03ba283babfb75c25b533273a7f47c44`
- numeric/W3/qparams/tail/workload/golden repeated: `false`
- functional RTL modified: `false`
- server uploaded/run by owner: `false`

## v24 return adjudication

The v24 B-control return passed CRC/root/path/manifest/source binding,
package/install preflight and observer/canonical binding.

- compile/simulation: `0/0`
- signal: `NONE`
- natural terminal: `true`
- host wall time: `6137.602946413 s`
- ordered stage: `op_b_dequant`
- completion: `543212` active cycles
- qualified advancing windows: `32`
- hang root cause: `NOT_A_HANG`

The same frozen B-dequant configuration completed with the v18 base
observer. This closes the possibility that the v20 B-stage failure came
from the frozen B configuration or functional RTL; its package-local
observer change introduced the failure.

The 28 returned full-chain D files are all X-valued because the tail was
not executed. They are not valid 128-bit payloads, mismatch is
unevaluable, `SERVER_RESULT_GATE=false`, and E3/E4/E5 remain false.

## True split construction

The split packages are real execution scopes, not merely observer views:

- A: `op_a_dequant + op_b_dequant`
- B: independent `op_relocation_pad`
- C: cumulative prefix through `op_fp32_add`
- D: complete six-stage plus 28-D chain

A consumes only the original typed A/B edges. B consumes the frozen
external noncomputational zero spacer. C has no byte-recovered hardware
A/B scaled replay, so it legally falls back to the prefix. D has no
byte-recovered SUM replay, so it remains the full chain.

The first v25 package attempt was isolated before delivery. Its C/D SCA
still contained intermediate `op_fp32_add` preloads, and its safe
compile-stub return did not have a compile-log placeholder. V26 removes
all 56 C internal FP32-add preloads, binds D to the accepted final v18
package SCA, and adds only the package-runner placeholder needed for a
complete compile-failure return.

## Final package identities

All four v26 packages were built twice deterministically. Each final ZIP
passed:

- CRC/root/path/exact manifest and sidecar checks;
- current-rule receipts;
- package-local HDL compatible frontend and declaration/use/update
  negatives;
- exact ordered stage and final-output SCA checks;
- runtime-D initially absent;
- real runner to safe compile-stub;
- wrong-identity precompile failure;
- EXIT and TERM trap-safe finalizers;
- feature, time0, stage, event and output negative controls.

### A

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_a_dequants_v26.zip`
- bytes/SHA256:
  `26024463` /
  `d9fa3eb8d94ec83382c5be79150a9ea0d9a04903227405d243edb82dcb5e3978`
- expected return:
  `r5_qadd_n7_split_a_dequants_v26_return.zip`
- final audit SHA256:
  `7e5f53df87ae12a7e244608fe34ff71af63a9b5268fb3dc7ba6b99576897c53a`

### B

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_b_reloc_v26.zip`
- bytes/SHA256:
  `158248` /
  `fb3f248bf4031db9f9d7d8168149ece1a80dbeda50843c8bb20834ab3fc58f05`
- expected return:
  `r5_qadd_n7_split_b_reloc_v26_return.zip`
- final audit SHA256:
  `d1a499f21a465574b8ed5a297541812635095b63651cb99e0fa467e0771d9137`

### C

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_c_fp32_prefix_v26.zip`
- bytes/SHA256:
  `26156775` /
  `e4c16585707b37170d04311f91c038c37b3c95330ffceed17a23687d913f5d50`
- expected return:
  `r5_qadd_n7_split_c_fp32_prefix_v26_return.zip`
- final audit SHA256:
  `c919bb55f2821db7fc77537e2f52bf04c63dd0d38a78ad8b09a91813b048e26a`

### D

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_d_full_v26.zip`
- bytes/SHA256:
  `38027184` /
  `b73b13b95f01ea95919cd2eae29415dd04e8a1fff7bc67307099b4c67871d49c`
- expected return:
  `r5_qadd_n7_split_d_full_v26_return.zip`
- final audit SHA256:
  `94da9cc429d786f07e81b3727e222c80338eeb864209be1717aee699097fa5f2`

All use:

`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`

Recommended server order is B, A, C, D. B is the shortest independent
control; D is run last because it retains the complete numeric
conjunction.

## BLOCKER_DELTA

Closed:

- `B_QADD_V20_PACKAGE_LOCAL_FP32_OBSERVER_EVENT_STORM_SUSPECT`
- `B_QADD_NODE0007_OP_B_DEQUANT_DYNAMIC_COMPLETION_UNPROVEN`
- `B_QADD_TRUE_SPLIT_PACKAGE_IDENTITIES_NOT_MATERIALIZED`

Opened:

- `B_QADD_V24_B_ONLY_FULL_CHAIN_RESULT_GATE_SCOPE_MISMATCH`

Kept open:

- `B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED`
- `B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN`

## RULE_CONFIRMATION

`CURRENT_RULES_CONFIRMED_EFFECTIVE`.

The current ordered-stage, minimal-runtime, package-local HDL, result
conjunction and continuous-closure rules rejected both the v24 full-D
overclaim and the v25 internal-preload escape before release. No public
rule delta is proposed.

## PACKAGE_RELEASE

`A_B_C_D_PACKAGE_READY_NOT_RUN`.
