# GAP node0071 v30 return and v32 COL/AG/MRM byte-lane successor

- Owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Scope: GAP-family return adjudication and package-local diagnostic successor only.
- Functional RTL, public rules, `.agents/plan.md`, numeric/sum/tail/workload/config/golden, timeout and backpressure were not modified.

## RETURN_ANALYSIS

The formal v30 return is internally valid and source-bound despite the absent adjacent sidecar, which is accepted only under `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`.

- Return SHA256: `b72a3baa7468aa6a09254c90a7d488aa949b37045b1dad83670cc8a9dc2239f6`
- Frozen source SHA256: `f0606ebeab52391856a7fb939b6f8c6d02984ae8384117d53d906ba1a9c4a931`
- Compile: `0`
- Simulation/runner: `125/125`, signal `INT`, nonnatural terminal.
- Formal D: expected `48`, present `0`, missing `48`, mismatch bytes `0` but unevaluable.
- `SERVER_RESULT_GATE=false`; E3/E4/E5 are all false.

`LAST_PROVEN_GOOD`: two Buffer0 ARM full-row reads are accepted with all selected banks ready and NRM read barrier low.

`FIRST_DIVERGENCE`: `THIRD_BUFFER0_ARM_ROW_READ_HELD_WITH_ALL_SELECTED_BANK_READINESS_ZERO_AND_NRM_READ_BARRIER_ZERO`.

`HANG_ROOT_CAUSE`: `LONG_RUNNING_HANG_AT_BUFFER0_SELECTED_BANK_READINESS_AFTER_PARTIAL_ROW_FILL_BYTE_LANE0_ONLY`.

The final v30 factor snapshot is request/mask `0xff`, bank-ready `0x00`, barrier `0`, and valid-byte state `0x11111111`. Thus each bank contains lane0 only; the barrier branch is excluded and the remaining boundary is COL-LC/Buffer-AG/MRM byte-lane materialization.

Blocker closed:
`B_GAP_NODE0071_BUFFER0_ARM_READ_READY_CONJUNCTION_PENDING_BANK_READY_OR_NRM_BARRIER_LEAF`.

Blocker opened:
`B_GAP_NODE0071_BUFFER0_SELECTED_BANK_READINESS_PARTIAL_ROW_FILL_PENDING_COL_AG_OR_MRM_STROBE_LEAF`.

## Successor

The first local candidate v31 was not released because its final manifest omitted directly applicable rule ID `CDA-GAP-8B-RD-BUFFER-BYTE-LANE-COVERAGE-001`. It remains preserved and quarantined; SHA256 `d37405bf47e2a572f52de47580faec3375ba387fffeb0168bad1cf42b7671650`.

The unique released successor is:

- Identity: `r5_n71_gap_v32_col_ag_mrm_lane_rulebind`
- Class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Status: `PACKAGE_READY_NOT_RUN`
- ZIP bytes/SHA256: `1822477` / `c974125f0b3e913f733ad4c2341b922ea3551a62144b1062c6dd433d82e369a1`
- Sidecar bytes/SHA256: `110` / `b03af7b7269dab340f7b3d54bc6c1aed40768da5e69abd4e1ba551c96d67aa8e`
- Command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- Expected return: `r5_n71_gap_v32_col_ag_mrm_lane_rulebind_return.zip`

The observer records accepted events only across IGA COL-LC0, MSE0 WR_Buffer_AG, the MSE0 address/data paired write, and Buffer0 MRM request/data/strobe acceptance. Stable levels are state only.

## Validation

- Deterministic double build: identical.
- Frozen numeric/workload: 73 files, byte-equal.
- Frozen other tree: 119 files, byte-equal.
- Fresh runner reaches safe compile stub: exit `86`.
- Wrong identity and all package validator negatives: fail closed.
- TERM shared-finalizer safe stub: runner `125`, complete partial return, empty stderr, nonnatural not misreported.
- Focused exact observer HDL compile/name-resolution: exit `0`.
- HDL negatives (delete declaration, typo use, delete critical update, typo XMR): all fail closed.
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors `0`.

Final audit SHA256:
`2ccd9a92c4a1088d74b60326908b85b401216698044f47ed111a670bbb8fc0e5`.

Machine report:
`artifacts/operator_config_validation/r5-gap-node0071-v30-return-v32-successor/report.json`,
bytes `8080`, SHA256 `27c2728f2912a170762a6d6817561b25cf4b87ee908a0c237993ca5510a895fc`.

## Rule disposition

`RULE_CONFIRMATION`: existing handshake-conjunction, 8B read-buffer byte-lane coverage, focused package-local HDL, and return-to-successor closure rules are confirmed.

`RULE_DELTA_PROPOSAL=NONE`.
