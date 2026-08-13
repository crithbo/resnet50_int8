# GAP node0071 v46 hold → v47 root-top-level runner fix

- Analysis owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Machine report: `artifacts/operator_config_validation/r5-gap-node0071-v47-stage-transition-rootfix/report.json`
- Machine report SHA256: `71ab233e58c4dd7f004f654b3b568e34486f36d4469065cc217fa54ce1e7383e`

## Adjudication

`r5_n71_gap_v46_stage_transition_mask_diag.zip` was not run after the new
`CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001` gate became current. Its
runner created root-level `run_*` and `evidence_*` entries, so it was held as
`PACKAGE_HELD_NDP_ROOT_TOPLEVEL_GATE_REQUIRED` and rotated to
`superseded/gap_node0071/r5_n71_gap_v46_stage_transition_mask_diag/`.

The fresh runner-only replacement is
`r5_n71_gap_v47_stage_transition_rootfix`. Numeric files, workload, config
semantics, golden, observer, timeout, backpressure, and functional RTL are
frozen. The runner requires the direct child `install` to exist before any
write, then uses only `install/codex_pkg_runs/<identity>` and
`install/cfg_pkg/<identity>`. The shared finalizer returns sorted direct-child
name/type pre/post sets, their SHA256 values, the declared parent, and
`ndp_root_toplevel_unchanged`.

## Local gates

- Deterministic double build: PASS.
- Focused package-local HDL syntax/scope/name-resolution: PASS.
- Predicate trace: unchanged observer receipt reused, PASS.
- Exact runner safe harness: normal, compile-fail, HUP, INT, TERM PASS.
- Root negative controls: new root file, new root directory, root return
  directory, missing declared parent, and removed drift propagation all fail
  closed.
- Fixed server publication target remains
  `/home/panqs/ndp/simresult`; no local production path was created.
- Final ZIP current-rule self-audit:
  `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`.

## Release

- Status: `PACKAGE_READY_NOT_RUN`
- Pickup:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v47_stage_transition_rootfix.zip`
- ZIP bytes: `1944021`
- ZIP SHA256:
  `e5e1e010970230fb9f9706bc2dd2381dbfecd2c304fd48e212587827110567ab`
- Sidecar is internal under `pending_receipts`; users need only pick up the ZIP.
- Run from the extracted package directory:
  `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`
- Expected return:
  `/home/panqs/ndp/simresult/r5_n71_gap_v47_stage_transition_rootfix_return.zip`

This is a local runner/package correctness release only. Production compile,
DUT progress, natural terminal, 48 formal-D values, E3, E4, and E5 remain open.
No server upload/run or lease occurred. No plan, public rule, functional RTL,
numeric, config, workload, golden, timeout, or backpressure content was
modified.
