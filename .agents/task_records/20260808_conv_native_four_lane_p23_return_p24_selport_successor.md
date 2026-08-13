# Conv native four-lane p23 formal return and p24 successor

Date: 2026-08-08  
Owner: native four-lane Conv performance branch  
Mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## p23 exact identities

- Source package: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p23_epochflow.zip`
- Source bytes: `5878970`
- Source SHA256: `f70f9a7643012a013736df3026057ca981f19d543c572064d3cd69edaa46a788`
- Formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p23_epochflow_r1786189179254670581_4095589_return.zip`
- Return bytes: `2161834`
- Return SHA256: `2287d88e98c3affbf155e010a364cec7ca9985a9dc6deba534f2591ff756d6be`
- Execution identity: `r1786189179254670581_4095589`

## Formal p23 adjudication

Machine report: `outputs/conv_native_four_lane_0ccae916_p23_return_analysis/report.json`.

The transport, internal exact-set/source, repeatable execution, install/root, compile and signal
receipts pass. Production compile exited zero; simulation was later interrupted with `INT` and did
not reach a natural terminal. This c0 diagnostic intentionally carries no formal 320-D payload, so
zero D records do not constitute a numeric failure or pass and do not establish E3/E4/E5.

The last proven good boundary is a real Memory_AG queue write/read and descriptor progress through
18. The first divergence is after the qualified physical PE7 output carrying index 8: the p23
selected input1 snapshot remains index 7, there is no next Memory_AG queue write and descriptor 19
is not produced. p23 therefore closes the epoch-owner and actual queue-handshake alternatives but
cannot distinguish the Stream_Engine_Connect configured source, selected public output, and the
Memory_WR_Stream_Engine public input boundary. Its private derived-mask fields are not used as a
functional correctness oracle.

Classification:

```text
P23_EPOCH_FLOW_PASS_CONNECT_SELECTION_SUCCESSOR_REQUIRED
LPG = Memory_AG queue write/read + descriptor18 + qualified PE7 index8
FD  = selected input1 remains index7; no next queue write/descriptor19
natural/27-run/320D/E3/E4/E5 = NOT_CLAIMED
```

## Continuous closure

One fresh p24 successor is authorized in the same owner task. It freezes p23 numeric/W3/workload/
config/mapping/bitstream/execplan/SCA/golden/timeout and functional RTL, and changes only package
identity plus a bounded same-clock observer on public `Stream_Engine_Connect` and
`Memory_WR_Stream_Engine` ports. The observer must distinguish configured source ID, physical PE7
word acceptance, selected Connect output and exact Memory input without relying on a new private
leaf XMR.

## p24 release

Disposition: `PACKAGE_READY_NOT_RUN / PERFORMANCE_DIAGNOSTIC_CANDIDATE`;
`candidate_release=false`.

- Pickup ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p24_selport.zip`
- ZIP bytes: `5880634`
- ZIP SHA256: `4690da16077c60c91d7de7c5fd1042f17bdb8db844d59ae4169528a6ba318c28`
- Unique command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p24_selport_r<epoch-ns>_<pid>_return.zip`
- Final audit: `outputs/conv_native_four_lane_0ccae916_p24_selport/r5_n4_0cc_p24_selport.final_zip_audit.json`, SHA256 `26140ea7d9e5e8216e27e493f750f3328af61ec91d004803256f574ecb51ba04`
- Family audit: `outputs/conv_native_four_lane_0ccae916_p24_selport/p24_family_audit_v2.json`, SHA256 `ef1b6ed8f4637d6b807456358ef1546a5f8fe70aa26eca4c65eb956f951de2db`, PASS/errors=0
- Runner harness: `outputs/conv_native_four_lane_0ccae916_p24_selport/p24_runtime_layout_harness_v2.json`, SHA256 `6356f46981762ead03ee6aa8a92edbb05d7eae83688d4c4ea2e2587b18f1466c`, normal/preflight-fail/compile-fail/HUP/INT/TERM PASS
- Shared runtime layout: `outputs/conv_native_four_lane_0ccae916_p24_selport/p24_shared_runtime_layout_v2.json`, SHA256 `4ae552c94b046fc83527ab4b324a724581edaf1820bd413b361af8ee31f1044c`, PASS/errors=0, exact-final-ZIP invocation count=1
- Shadow profile: `outputs/conv_native_four_lane_0ccae916_p24_selport/server_package_build_profile.json`, SHA256 `d1e5efca92eb45ce5d787931741977fd6a645ac86f4446e5a5309d8c1fedb1c0`, contract valid/errors=0
- Deterministic double build: PASS
- Frozen installed payload: 87/87 byte-equal; SCA identity-normalized equal; no numeric/W3/config/mapping/bitstream/execplan/golden/timeout or functional-RTL change
- Storage rotation: p23 moved to `tested`; p24 is the only `conv_native_four_lane` pending ZIP; storage audit PASS

p24 adds only public module-port observation and post-compile identity collection for
`Stream_Engine_Connect.sv` and `Memory_WR_Stream_Engine.sv`. The changed observer passes compatible
frontend syntax/scope, leaf-delete/rename/wrong-sibling negatives, exact logger/parser formatting,
same-clock predicate microtrace, and independent state/qualified budget controls. It contains no new
private-leaf XMR.

Expected p24 adjudication is a single-run split:

```text
src_id != 7
  -> configured source-selection/config leaf is first divergence
src_id == 7 && select_eq == 0
  -> Stream_Engine_Connect selection/equation boundary is first divergence
select_eq == 1 && port_eq == 0
  -> Connect output to Memory-WR public input binding is first divergence
select_eq == 1 && port_eq == 1 but no qualified Memory input/next queue write
  -> actual Memory_AG consumer semantics/actual-leaf causal difference remains
```

The package remains c0 diagnostic-only and does not claim a natural terminal, 27-run completion,
formal 320 D, E3, E4, E5, numeric correctness, or performance.

## Rule feedback

`RULE_CONFIRMATION`:

- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`: p24 uses public ports and adds no private
  XMR; exact module identities and path/scope negatives pass.
- `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001` and
  `CDA-SERVER-DIAGNOSTIC-LOGGER-PARSER-EXACT-FORMAT-TRACE-001`: changed predicate and exact rendered
  row grammar pass positive and whitespace/token mutation negatives.
- `CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001`: qualified and state budgets
  are separate and stable state cannot exhaust the progress budget.
- `CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`,
  `CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`, and
  `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`: all six local runner outcomes close in the
  install-only layout with root exact-set preservation and repeatable fixed-result publication.
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`: p23 formal-return source is retained as tested and p24
  is the single pending package for this family.

No non-synonymous public-rule gap was found. Claim boundary is only the p23 return and p24 local
release surfaces above.
