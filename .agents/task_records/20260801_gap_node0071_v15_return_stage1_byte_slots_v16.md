# GAP node0071 v15 return → stage1 byte-slot v16

- v15 return integrity, source binding, package/install preflight and diagnostic feature
  binding passed. Compile passed; the run was interrupted without a natural terminal and
  all 48 formal D files were missing, so E3/E4/E5 remain false.
- Qualified evidence proved one MSE0→Buffer0 and one MSE3→Buffer4 acceptance, followed by
  no Buffer ARM or GA ingress acceptance.
- The deterministic configuration root cause is
  `STAGE1_8B_READ_REPEATS_BUFFER_BYTE_LANE_ZERO`: the old stage1 GROUP0/GROUP1 COL
  sequence `0,4,8,...` keeps `low2=0`, repeatedly writes byte lane 0 in every bank, and
  can never satisfy the Buffer all-four-byte-valid ready condition.
- The typed materializer now emits COL `0,1,2,3`. The exact configuration diff is four
  leaves: GROUP0/GROUP1 COL `end 32→4` and `stride 4→1`.
- Full config→mapping→bitstream→complete local-E2 integration was replayed. Only the
  stage1 bitstream changed; stages2-6, tail, execplan, SCA semantics, frozen W3/golden and
  functional RTL remain unchanged.
- The public GAP rule now contains
  `CDA-GAP-8B-READ-BUFFER-BYTE-LANE-COVERAGE-001`.
- The only runnable successor is
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v16_stage1_byte_slots.zip`,
  SHA256 `85ee11406a8f7b67d67d7fd3e82705c3c48c12b01e2a155496cbf7b05679cee5`.
  Final-ZIP self-audit passed with errors=0 and all required negative controls fail-closed.
- The complete focused GAP regression (`tests.test_gap_sum_config_only` plus
  `tests.test_gap_int32_mac_stage_memory`) passed 17/17 after refreshing the local-only
  bypass contract receipt.

Machine report:
`artifacts/operator_config_validation/r5-gap-node0071-v15-return-analysis/report.json`.
