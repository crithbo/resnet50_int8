# Serialized Conv node0004 v87b mandatory-VPD package ready, not run

- Role: `family.conv.serialized`
- Owner epoch: `2`
- Registry epoch: `6`
- Shared gate epoch: `waveform-mandatory-v2-01ca6d7cd4a4a270`
- Rule: `CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001`
- Status: `PACKAGE_READY_NOT_RUN`
- Server action: none (no upload, lease, or server run)

## Previous progress and current purpose

v85b closed the production compile exit `2` to the two package-local observer
`arb_req_ready` XMRE sites and recovered all seven bootstrap compile-rootcause
files. The withdrawn v86b preserved that observer repair and the structured
first-error repair, but used the superseded dump-disabled waveform semantics.

v87b preserves the v86b-equivalent target diagnostic and is intended to prove
production compile beyond the XMRE repair while returning mandatory
full-hierarchy VPD. A single future run can therefore localize ACK output versus
inline RHS, natural-terminal, and formal-D blockers.

## Frozen and changed surfaces

- Frozen: config, numeric, workload semantics, functional RTL, timeout, and the
  target diagnostic.
- Changed: fresh package identity plus waveform/runtime-return surfaces only.
- Actual controls: `DUMP_VCD=1`, `DUMP_FSDB=0`, `TB_DUMP_FSDB=0`.
- Wave scope: `tb_NDP_Top_new_phy`, hierarchy depth `0`, no exclusions.
- Return: every `wave.vpd`/shard, unbounded streaming; simulation-started with
  no wave fails closed; compile-not-started preserves the seven compile-core
  members.

## Gate closure

- Exact clean ZIP, runner definition-before-use/bootstrap compile core,
  source-bound final ZIP, post-sim return, mandatory waveform v2, candidate
  matrix, frozen-surface, and first-fresh gates: pass.
- Runtime-layout exact runner harness: normal, compile-fail, HUP, INT, TERM, and
  preflight-fail publication scenarios pass; all 86 SCA input paths opened in
  the safe local fixture.
- Shared runtime-layout validator with runner error visibility: pass.
- Waveform and post-sim unit tests: 31 passed.
- Current-disk rule/registry identity comparison: 12 of 12 match.
- Package-storage manager audit after rotation: pass.

The runtime-layout harness exposed and caused correction of two metadata-only
fresh-identity defects before publication: the observer precompile binding still
referenced the held package identity, and the path-budget receipt was one
character stale. No observer/RTL/config/numeric/workload diagnostic bytes were
changed by either correction.

## Published local paths

- Pickup ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v87b_mandatory_vpd.zip`
- Receipt directory:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v87b_mandatory_vpd`
- Release receipt:
  `outputs/conv_node0004_v87b_mandatory_vpd_release6/r5_n4_hw_v87b_mandatory_vpd.release_receipt.json`
- Storage audit receipt:
  `outputs/conv_node0004_v87b_mandatory_vpd_release6/r5_n4_hw_v87b_mandatory_vpd.storage_audit_receipt.json`
- Final ZIP audit:
  `outputs/conv_node0004_v87b_mandatory_vpd_release6/r5_n4_hw_v87b_mandatory_vpd.final_zip_audit.json`
- Shared runtime-layout validation:
  `outputs/conv_node0004_v87b_mandatory_vpd_release6/runtime_layout_shared_validation.json`

The held `r5_n4_hw_v86b_observer_xmre_fix` remains absent from pending and
preserved under `superseded/conv_serialized_node0004`.
