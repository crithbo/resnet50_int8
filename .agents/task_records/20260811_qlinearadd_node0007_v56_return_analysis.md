# QLinearAdd node0007 v56 formal return analysis

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- raw return: `C:/Users/15383/Downloads/r5_qadd_n7_tailround_lanephase_v56_r1786417542514431046_867213_return.zip`
- raw return bytes/SHA256: `247070` / `c8a59e24a0acef95210d4ae42872350e5e174a78b9ad7bb39911652b69ea18e4`
- frozen source bytes/SHA256: `70701485` / `78e98876977060c3ea5c29ec93e130dbd48dc13c0d8386e8c5e42c075e2055fc`
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-v56-return-analysis/report.json`
- machine report bytes/SHA256: `23742` / `2e40f4830107e87c6db76d0052f2366242e5dbce8ebfe22955008a0259940e0f`

## Formal result

- transport/internal/source/package/install/execution binding: PASS
- compile: `0`
- simulation: `124`
- signal: `NONE`
- host wall time: `7305.315688324 s`
- natural terminal: false
- ordered target-stage starts/finishes: `0/0`
- formal D: expected/present/missing/invalid=`28/0/28/0`; mismatch bytes=`0`, but mismatch is not evaluable
- E3/E4/E5: false/false/false

The simulator timed out while loading `op_tail_round/slice26/matrix_A_linearized_128bit.txt` at preload matrix index 21. It never emitted `INFO: slice start`; therefore this return did not reach the isolated tail_round stage.

The generated observer materialized six probe modules in each of 168 Buffer instances (`1008` probes). The returned parser accepted 35 records from the canonical Buffer5 instance and ignored 4725 non-target records, but all accepted records occurred without an `EXEC_START` and before the final observed preload. They are pre-stage state and cannot adjudicate the requested `0x33333333` versus valid `0xcccccccc` temporal lane phase.

## Adjudication

- `LAST_PROVEN_GOOD=PACKAGE_INSTALL_COMPILE_AND_INPUT_PRELOAD_THROUGH_PART_OF_SLICE26`
- `FIRST_DIVERGENCE=SIMULATION_TIMEOUT_DURING_MATRIX_A_PRELOAD_BEFORE_OP_TAIL_ROUND_EXEC_START`
- functional progress relative to v54: `ZERO`
- config leaf authorization: false
- functional/RTL root cause: unresolved because the target stage was never observed
- package diagnostic defect: excessive all-instance observer fanout plus pre-stage predicate contamination

The next package must remain `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, keep workload/config/numeric/W3/qparams/tail/golden/2h timeout/functional RTL frozen, collapse redundant Buffer probes into one generated multiclass boundary, and ensure only records after ordered `EXEC_START` can enter the candidate decision.

## Rule feedback

`RULE_CONFIRMATION`: current exact-instance/grouping, time-to-root-cause, qualified-budget, and result-conjunction rules correctly reject v56. No synonymous rule delta is proposed.
