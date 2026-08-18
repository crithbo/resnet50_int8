# family.qlinearadd PACKAGE_READY_NOT_RUN: v63 bounded causal-cone TB VCD

Date: 2026-08-14 (Asia/Shanghai)

## Ownership and activation

- role_id: `family.qlinearadd`
- owner thread: `019ff02d-9e93-7d61-8c98-c928fdea157c`
- owner_epoch: `2`
- registry_epoch: `6`
- family storage key: `qlinearadd_node0007`
- activation_epoch: `tb-vcd-bounded-causal-cone-optional-v1-0820e1733437`
- selected_mode: `TB_VCD_BOUNDED_CAUSAL_CONE`
- exact package base: `r5_qadd_n7_tailround_lanephase_v63_tbvcd`
- status: `PACKAGE_READY_NOT_RUN`

## Previous progress and current purpose

Previous-version progress: v57h localized the DUT boundary after Buffer5
request decode and before selected ping-pong-port required-lane read accept;
v59 exposed the manifest `install_name`/SCA namespace mismatch; v60 repaired
that identity defect; v62 preserved the repaired identity and native-flow
non-interference contract under an unrun observer-only package.

Current-version purpose: preserve v62's manifest/install/SCA identity repair,
tail-round target and both ping-pong branches while returning one bounded,
source-bound package-local standard-TB VCD causal cone over Buffer5 request
decode, producer/clear, both-port valid/ready, per-bank/lane valid/missing/owner/
full state, read barrier/accept, address/tag/mask/outstanding, data/output,
completion/terminal/formal-D and the global progress witness.

## Exact package and gates

- release ZIP: `outputs/qlinearadd_node0007_v63_tb_vcd_release/build/r5_qadd_n7_tailround_lanephase_v63_tbvcd.zip`
  - bytes: `108620573`
  - SHA-256: `c506b97891bf8e8d78c26bc9cf959bc2bfc4eacc54345e68cf69b22a3ccc12fa`
- final aggregate audit: `outputs/qlinearadd_node0007_v63_tb_vcd_release/gates/final_zip_release_audit.json`
- first-fresh contract/validation: `outputs/qlinearadd_node0007_v63_tb_vcd_release/gates/first_fresh/contract.json`, `validation.json`
- staging aggregate/profile: `outputs/qlinearadd_node0007_v63_tb_vcd_release/gates/staging_aggregate.json`, `server_package_build_profile.json`
- exact-ZIP mode/VCD/lexical/runner/post-sim receipts: `outputs/qlinearadd_node0007_v63_tb_vcd_release/gates/precheck/`
- full-HDL/source-bound/runtime-layout receipts: `outputs/qlinearadd_node0007_v63_tb_vcd_release/gates/precheck/hdl.json`, `source_bound.json`, `runtime_layout.json`

The staging tree aggregate, exact-final-ZIP recomputation, mode selector,
41-role/64-actual-signal causal-cone and 7-candidate/4-boundary matrix,
package-local HDL lexical/full frontend/scope/state negative controls,
source-bound, native-flow non-interference, post-sim, runner/compile-core,
six-exit/process-tree, streaming/retention, current-epoch first-fresh,
deterministic ZIP and prepublication storage gates all passed. Current shared
regressions passed 75 tests. The previous v62 pending ZIP remained byte-frozen
until this conjunction passed.

## Frozen surface and runtime contract

- config, numeric, workload, golden, functional RTL, ping-pong behavior and the selected tail-round diagnostic target are frozen;
- no DUT-driving HDL was introduced;
- actual Make dump argv remain `DUMP_VCD=0`, `DUMP_FSDB=0`, `TB_DUMP_FSDB=0`;
- the only waveform producer is package-local standard `$dumpfile/$dumpvars/$dumpon/$dumpoff/$dumpflush`;
- VPD, FSDB, FST, UCLI direct-VCD, vendor query and full-top unbounded dump are absent;
- decimal 100,000,000 bytes is warning-only, with no cap, truncation, sampling or size deletion;
- 8GB VCD and 10GB return projections are operational fail-closed stops, never truncation;
- 1,048,576-cycle suspect, 4,194,304-cycle dumpoff and 262,144-cycle grace require the strict owner-clock/sim-time/counters/digest/global-witness/catalog/XZ intersection;
- every non-natural exit remains `PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE` and cannot claim natural terminal/formal-D/E4/E5;
- analysis is streaming/resumable through `analysis_state.json`, append-only `checkpoints.jsonl` and incremental `report.md`;
- protected raw-result retention is `MAX_PROGRESS + LATEST_1 + LATEST_2` and deletion requires analysis completion, family+mainline consumption, deterministic core-only evidence and protected-set audit.

## Sole future command and claim boundary

Only after separate user authorization for server execution:

`bash r5_qadd_n7_tailround_lanephase_v63_tbvcd/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

No upload, lease, connection, server run, production compile or simulation
occurred during construction. Local gates do not claim root cause, natural
terminal, formal D, E3, E4 or E5.
