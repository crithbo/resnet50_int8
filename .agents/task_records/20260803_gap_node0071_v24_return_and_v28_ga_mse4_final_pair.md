# GAP node0071 v24 return → v28 narrow diagnostic closure

- Analysis owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Final state: `PACKAGE_READY_NOT_RUN`

## v24 RETURN_ANALYSIS

The formal v24 return is internally authoritative under the user-attested
no-sidecar transport rule. CRC, root/path safety, duplicate/symlink rejection,
RETURN_MANIFEST exact-set, allowlist, per-file size/SHA and frozen source
identity all pass.

Compilation exited 0. Simulation and runner exited 125 under `INT`; there is no
natural terminal. Only `sum_s1` started, no stage completed, and formal D is
0/48 present (48 missing), so mismatch=0 is not evaluable. E3/E4/E5 are all
false and the conjunction gate is false.

Qualified `PREP_COUNT_CAUSE` evidence closes the prior MSE3 prepared-count
blocker: MSE0 and MSE3 each record 7 writes, 3 reads, two count changes and
the same `0 -> 8 -> 0` sequence with no reset edge. The next narrow interval
is downstream: GA input/output are 40/32; MSE4 request/write-data accepts are
9/8 per channel, with one outstanding request per channel stable for more
than 1,048,576 cycles.

- LAST_PROVEN_GOOD: symmetric MSE0/MSE3 prepared paths, 32 GA outputs, and 8
  accepted MSE4 write-data beats on each channel.
- FIRST_DIVERGENCE:
  `FINAL_GA_INPUT_BATCH_TO_GA_OUTPUT_AND_MSE4_WRITE_DATA_ABSENT_WITH_MSE4_REQUEST_OUTSTANDING_1_PER_CHANNEL`
- HANG_ROOT_CAUSE:
  `LONG_RUNNING_HANG_AT_GA_FINAL_PIPELINE_TO_MSE4_REQUEST_WRITE_DATA_PAIRING_PENDING_LEAF`

Formal v24 report:
`artifacts/operator_config_validation/r5-gap-node0071-v24-return-analysis/report.json`,
bytes 11930, SHA256
`713641032c1bb5d020176694f2d3369257aeee0f8a41b4b8196f1c2247b35710`.

## v28 successor

Only runnable identity:
`r5_n71_gap_v28_ga_mse4_final_pair_diag`.

The package adds bounded, rate-limited, qualified evidence around GA pipeline
retire/outbuffer flow and MSE4 request metadata, prepared-data and output-buffer
handshakes. It does not count stable levels as progress. It does not change
numeric, sum/tail, workload, config, golden or functional RTL content.

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v28_ga_mse4_final_pair_diag.zip`
- ZIP bytes: 1815690
- ZIP SHA256:
  `7b34ef0b592ebfd86d3e75a0983a91c8d87271454139e609174cdce8afc7d422`
- Sidecar SHA256:
  `027016ecb4c93f5d17ebc8cfaf3994571a018cf737c227cffd7710a7983ddf4c`
- Command from the extracted package directory:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- Expected return:
  `r5_n71_gap_v28_ga_mse4_final_pair_diag_return.zip`

## Final verification

- Deterministic double build: byte-identical.
- Frozen numeric/workload files: 73/73 byte-identical.
- All unchanged inherited files: 119/119 byte-identical, including the 73
  numeric/workload files above.
- Static validator: exit 0, PASS, errors=0; report SHA
  `6c931083f3ff2f25ea28009f6392c0c12da80dace3b9b0abc3de81339e422408`.
- Fresh-extract real runner → safe compile stub: exit 0; compile reached and
  terminated only at expected stub exit 86; wrong identity exits 5; all
  negatives fail closed. Report SHA
  `eefc1beb21b801d72096458eaa0ed7b6d97aa8281c0f7b469eca64d7f3297907`.
- TERM finalizer positive control: exit 0, PASS; one shared finalizer,
  stderr empty, partial return complete, non-natural termination not
  misreported. Report SHA
  `4cbb0dff9eca4586c9c31ed4300167fc71cd137724640b73dbfc969689669ac5`.
- Focused package-local HDL gate: exit 0, PASS with Icarus 12.0; exact observer
  projection and focused XMR compile exit 0. Delete-declaration, typo-use and
  delete-update negatives all fail closed. This claims only v28-added and
  result-critical identifiers, not full-design elaboration. Report SHA
  `b633adb99cc68a34b24ba5cd8e206c067b5b4caf4ae6e4422b64ad386f5cc4af`.
- Final ZIP rule self-audit: exit 0,
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors=0, all negatives fail closed.
  Report SHA
  `1b8471a5f910b6e9f96df6d19ffcd5863dca16ed2aca7d8d398acb61582b25ed`.

Intermediate v25/v26/v27 assets remain preserved and non-published. They are
not runnable identities. No server upload/run or lease occurred.

## Blocker and rule delta

- Closed:
  `B_GAP_NODE0071_MSE3_PREPARED_COUNT_UPDATE_PENDING_LOCAL_RESET_OR_UPDATE_CAUSE`
- Opened:
  `B_GAP_NODE0071_GA_FINAL_PIPELINE_TO_MSE4_REQUEST_WDATA_PAIRING_PENDING_LEAF`
- RULE_DELTA_PROPOSAL: `NONE`

Canonical machine closure report:
`artifacts/operator_config_validation/r5-gap-node0071-v24-return-to-v28-closure/report.json`,
bytes 10115, SHA256
`6fff0ecd97d75d9ab1f56671b0d3162e2b70e4e990f824564cad0d1d8bf82a5d`.
