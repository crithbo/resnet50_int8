# QLinearAdd node0007 split-B relocation v26 return analysis

## Provenance

- analysis owner thread: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- scope: read-only adjudication of split segment B (`op_relocation_pad`) and selection of the already-built next split identity
- repeated analysis: `numeric=false`, `W3=false`, `qparam=false`, `tail=false`, `workload=false`, `config=false`, `golden=false`
- functional RTL modified: `false`
- server uploaded or run by this analysis: `false`

## Frozen input receipts

- return: `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_qadd_n7_split_b_reloc_v26_return.zip`
  - bytes: `214518`
  - SHA256: `7571a4d58f65406525537fdae29dd3443114bfb7cbe1c3d4168ad9b984c58aa7`
  - adjacent sidecar: absent; accepted only as external transport under `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`
- source: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_b_reloc_v26.zip`
  - bytes: `158248`
  - SHA256: `fb3f248bf4031db9f9d7d8168149ece1a80dbeda50843c8bb20834ab3fc58f05`
- source final audit: `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-b-v26/final_zip_self_audit.json`
  - SHA256: `d1a499f21a465574b8ed5a297541812635095b63651cb99e0fa467e0771d9137`

## Current-rule receipts

All immutable receipts matched the dispatch values:

- agent: `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- generation index: `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- server rule: `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- QLinearAdd rule: `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f`
- exact-tail rule: `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- common operator rule: `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- NDP field rule: `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- server README: `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

The dispatch-time plan receipt `c7c9d120...e3aec3d` drifted to `9cc2770f0b09acdd03a123ab4f2fcb335fab648b0b717a69556ddf615b2549cb` while analysis was in progress. This is recorded as mutable provenance only and did not alter any semantic gate.

## RETURN_ANALYSIS

- ZIP CRC passed; one exact root `r5_qadd_n7_split_b_reloc_v26_return`; 49 entries; no duplicate, unsafe path, or symlink.
- `RETURN_MANIFEST.json` exactly covered every other ZIP file, and every declared size/SHA matched.
- the manifest target set exactly equaled the source package return allowlist; all size ceilings held.
- returned `PACKAGE_MANIFEST.json` was byte-equal to the frozen source `TEST_PACKAGE_MANIFEST.json`; all 40 source payload member size/SHA receipts matched.
- package/install/run/return identities all bound `r5_qadd_n7_split_b_reloc_v26`, segment `B`, final stage `op_relocation_pad`.
- package and installed preflight were valid; runtime readback targets were absent before execution; no server source inventory was inspected.
- observer compile `+incdir`, enable macro, simulator plusargs, time-0 marker, feature receipt, returned observer log, and canonical digest all closed.
- compile exit `0`; simulation exit `0`; canonical parser exit `0`; signal `NONE`; natural `$finish` at `2498760625 ps`.
- host wall time `595.629068595 s`; simulator wall time `513.589514534 s`.
- `EXEC_START=1635794000 ps`; `COMP_FINISH=1689504000 ps`; active cycles `42969`.
- qualified terminal snapshot: `req=33529`, `rdata=13096`, `wdata=16764`, `buf5_wr=16630`, `buf5_rd=33189`; `ga_input=64`, `ga_output=64`; MSE4 read/write-data `4224/4224` on both channels with outstanding `0/0`.
- all 28 stage-local relocation readbacks were present, decodable, `8448` lines / `135168` bytes each, with missing `0`, invalid `0`; the split-B conjunction passed.

## Scope adjudication

- `LAST_PROVEN_GOOD=OP_RELOCATION_PAD_COMP_FINISH_WITH_28_STRUCTURAL_READBACKS`
- `FIRST_DIVERGENCE=NONE_WITHIN_SPLIT_B_SCOPE`
- `HANG_ROOT_CAUSE=NOT_A_HANG_NATURAL_TERMINAL`
- `SERVER_RESULT_GATE=true` only for the split-B stage-local structural gate.
- full-chain formal-D expected count in this package is `0`. The 28 returned files are relocation outputs, not final quant-tail D. Numeric mismatch is deliberately unevaluable.
- `E3=false`, `E4=false`, `E5=false`; no A/C/D, upstream producer, cross-segment barrier/lifetime, numeric, or full-chain claim is made.

## BLOCKER_DELTA

Closed:

- `B_QADD_SPLIT_B_RELOCATION_DYNAMIC_COMPLETION_UNPROVEN`
- `B_QADD_SPLIT_B_STAGE_LOCAL_28_READBACK_GATE_UNPROVEN`

Kept open:

- `B_QADD_SPLIT_A_DUAL_DEQUANT_DYNAMIC_PASS_UNPROVEN`
- `B_QADD_SPLIT_C_FP32_PREFIX_DYNAMIC_PASS_UNPROVEN`
- `B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN`

No new blocker was opened.

## PACKAGE_RELEASE

No new package was generated. Per the frozen B→A→C→D run order, the unique next runnable identity is the existing:

- status: `PACKAGE_RUN_READY`
- package: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_a_dequants_v26.zip`
- bytes: `26024463`
- SHA256: `d9fa3eb8d94ec83382c5be79150a9ea0d9a04903227405d243edb82dcb5e3978`
- sidecar: `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_split_a_dequants_v26.zip.sha256`
- sidecar bytes/SHA256: `102` / `2575b5d56c12f278cef7ad914176fd41451725f21104b58a344f5cde3d6c3d31`
- final audit SHA256: `7e5f53df87ae12a7e244608fe34ff71af63a9b5268fb3dc7ba6b99576897c53a`
- command: `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return: `r5_qadd_n7_split_a_dequants_v26_return.zip`

## Machine receipts

- analyzer: `tools/analyze_qlinearadd_node0007_split_b_reloc_v26_return.py`
  - bytes: `21272`
  - SHA256: `d9ffc79021aa8a41b25d4e96f8e18c09ecdc2b0af914440618527dba71223025`
- report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-b-v26-return-analysis/report.json`
  - bytes: `8907`
  - SHA256: `d65685987a2613b0b4fb41046b6f37e6a2c45cd88aba667503d6525b3376e41d`
- analyzer command exit: `0`
- JSON parse and report `valid=true`, `errors=[]`: passed

## RULE_CONFIRMATION

`CURRENT_RULES_CONFIRMED_EFFECTIVE`: the no-sidecar policy waived only the external transport sidecar. Internal CRC/root/manifest/allowlist/source binding remained exact, and the stage-local result conjunction closed segment B without overclaiming full-chain 28-D or E3/E4/E5.
