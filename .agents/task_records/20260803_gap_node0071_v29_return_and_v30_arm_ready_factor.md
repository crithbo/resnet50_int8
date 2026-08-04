# GAP node0071 v29 RETURN to v30 ARM-ready-factor closure

- Owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Scope: GAP-family formal return adjudication and one package-local, read-only
  diagnostic successor.
- No plan, public-rule, functional-RTL, other-family, server, upload, run, or
  lease mutation was performed.

## RETURN_ANALYSIS

The v29 return ZIP is internally valid and exactly bound to source package
`r5_n71_gap_v29_mse0_buffer_prep_group0_diag.zip`, SHA256
`15833d826872e118a9be834b082351ae2b31862da0b138a2a4f271269108e164`.
The `(1)` download suffix does not create a new identity. The absent adjacent
sidecar is accepted only at the external transport layer under
`CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`.

Compile exited 0. Simulation and runner exited 125 after INT, so this is not a
natural terminal. Formal D is 48 expected, 0 present, 48 missing; mismatch zero
is unevaluable and the conjunction result gate is false. E3/E4/E5 are false.

Qualified v29 evidence shows that, within active `sum_s1`, all eight observed
MSE0 producer-to-Buffer0 accepts reach prepared writes. Two ARM reads accept
and clear, and five prepared reads produce five `data_vld` events. The final
state still has nonzero Buffer0 validity, ARM read request `0xff`, and composite
request-ready 0. Inherited evidence continues to show 48/48 GA input/output
transactions and consumption of all 12 available MSE4 pairs.

The v29 raw group0 counter (`15597566`) is excluded: it counted a stable,
nonzero whole tag level with backpressure rather than a qualified capture.
v30 corrects this package-local observer defect by requiring the GA valid tag
bit. No formal v29 first-divergence conclusion depends on the defective count.

`LAST_PROVEN_GOOD`:
all eight active-window MSE0 Buffer0 accepts reach prepared writes; accepted
ARM reads clear; prepared reads produce `data_vld`; available downstream GA and
MSE4 transactions are lossless.

`FIRST_DIVERGENCE`:
`BUFFER0_ARM_READ_REQUEST_0xFF_HELD_WITH_BUF2ARM_REQ_READY_0_AFTER_TWO_ACCEPTS`.

`HANG_ROOT_CAUSE`:
`LONG_RUNNING_HANG_AT_BUFFER0_ARM_READ_READY_CONJUNCTION_PENDING_BANK_READY_OR_NRM_READ_BARRIER_LEAF`.

The RTL equation is:
`buf2arm_rreq_ready = &(~buffer_mask | buf2arm_rreq_bank_ready) & (~nrm2buf_rd_barrier)`.
Existing evidence cannot yet distinguish selected-bank readiness from the NRM
read-barrier leaf, so a functional fix is not authorized.

## BLOCKER_DELTA

- Closed:
  `B_GAP_NODE0071_MSE0_BUFFER_TO_RD_PREPARED_TO_GA_GROUP0_CAPTURE_PENDING_LEAF`
- Opened:
  `B_GAP_NODE0071_BUFFER0_ARM_READ_READY_CONJUNCTION_PENDING_BANK_READY_OR_NRM_BARRIER_LEAF`

## SUCCESSOR / PACKAGE_RELEASE

Fresh identity: `r5_n71_gap_v30_arm_ready_factor_diag`

Test ID:
`r5-gap-node0071-v30-buffer0-arm-read-ready-factor-diagnostic`

Class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`

The package adds bounded, read-only evidence for Buffer0 `buffer_mask`,
per-bank `buf2arm_rreq_bank_ready`, `arm_clear_reg`,
`nrm2buf_rd_barrier`, and the existing ARM request/rw/address/composite-ready
boundary. Only qualified accepts and factor/blocking edges advance counters;
stable levels are state only. The record limit is 256 and timeout is unchanged.

Frozen reuse:

- 73 numeric/workload files are byte-equal.
- 119 other frozen files are byte-equal.
- Two deterministic builds produce the same ZIP.
- Numeric/sum/tail/workload/config/golden analysis was not repeated.
- Functional RTL was not modified.

Final ZIP:
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v30_arm_ready_factor_diag.zip`

- bytes: `1819468`
- SHA256: `f0606ebeab52391856a7fb939b6f8c6d02984ae8384117d53d906ba1a9c4a931`

Sidecar:
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v30_arm_ready_factor_diag.zip.sha256`

- bytes: `107`
- SHA256: `b5e9cfde7be51995ed67ae5e7538f63a6ddb8c8f02928d4fab7b68cbf69b94a1`

Command:
`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`

Expected return:
`r5_n71_gap_v30_arm_ready_factor_diag_return.zip`

Release: `PACKAGE_READY_NOT_RUN`

## FINAL_ZIP_RULE_SELF_AUDIT

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- Package validator and all inherited/v30 negative controls: exit 0.
- Fresh-extract real runner to safe compile stub: exit 0; compile stub reached
  unique exit 86; wrong identity failed before compile.
- TERM shared-finalizer stub: PASS; one finalizer epoch, empty stderr, complete
  partial return, and no false natural-completion claim.
- Focused exact-final-observer HDL gate: PASS with Icarus Verilog 12.0.
- Declaration deletion, use typo, critical-update deletion, barrier-XMR
  deletion, and group0-valid-bit deletion all fail closed.
- Full-design elaboration is not claimed and server sources were not inspected.

Final audit SHA256:
`d105f919eb670f7b374f9687cd09fa742e1a908513f26387c3ab97752784ed94`

## RULE_CONFIRMATION

Evidence confirms the existing rules:

- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-OBSERVER-EVIDENCE-DOMINANCE-001`
- `CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001`
- `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`
- `CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001`

`RULE_DELTA_PROPOSAL=NONE`.

## RTL identity

Active RTL commit:
`d0aa87f682880a260fb792aaac88f70a23aba414`

Sync report SHA256:
`fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771`

The two synchronized SA-file changes are not assumed to fix GAP.

## Machine report

`artifacts/operator_config_validation/r5-gap-node0071-v29-return-to-v30-closure/report.json`

JSON parse exit: `0`

Machine-report bytes: `10836`

Machine-report SHA256:
`9891750ea46fdef880eb687e00cd7bc7720fe74171c31f60a50f66ea129e4d77`
