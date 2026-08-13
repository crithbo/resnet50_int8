# GAP node0071 v51 return and v52 direct-consumer diagnostic release

Owner task: `019fa366-cb1f-7ae2-880c-f527be0680cd`  
Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## RETURN_ANALYSIS

The v51 per-execution return is internally valid and bound to source ZIP
`76336937dd52822e948dcc81c6f35054c73d0066dfad5f964b6753a04a78f7b4`
and execution `r1786123595862873463_3802426`. The missing adjacent sidecar is
accepted only at the user-attested transport layer. ZIP safety, exact-set,
allowlist, per-file receipts, reset/install/parser/finalizer receipts and all
exact source parser replays pass.

Compile completed with exit 0. Simulation exited 125 and runner exited 130 on
INT, so there is no natural terminal. Formal D is 0 present / 48 missing / 0
mismatch and is unevaluable; E3/E4/E5 remain false.

All 16 slices reached config start/finish, MSE0/MSE3 acceptance, GA input and
output, selected GA write, nonempty, and selected GA read (`0xffff`). The old
MSE4 and GA-conjunction streams each exhausted their 256-record budget on
STATE_EDGE before this late progress. Therefore later zero MSE4 masks are not
functional evidence.

- LAST_PROVEN_GOOD: `ALL_16_SLICES_GA_SELECTED_WRITE_NONEMPTY_SELECTED_READ`
- FIRST_DIVERGENCE: `SELECTED_GA_READ_TO_ALL_SLICE_MSE4_DIRECT_CONSUMER_UNEVALUABLE_AFTER_LEGACY_STATE_BUDGET_SATURATION`
- HANG_ROOT_CAUSE: `LONG_RUNNING_HANG_AT_GA_SELECTED_READ_TO_MSE4_DIRECT_CONSUMER_PENDING_LEAF`
- remaining blocker: `B_GAP_NODE0071_GA_SELECTED_READ_TO_MSE4_DIRECT_CONSUMER_PENDING_LEAF`

Machine return report SHA256:
`3e6b063b4905b4cb118df547cc5931d32fb138f30712519d284bb7d67a92b231`.

## Successor

Fresh v52 is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It reuses package-local
surfaces without adding DUT XMR and records 17 separately qualified all-slice
masks from GA selected read through the full MSE4 direct-consumer chain.
`clk_sg` owns sticky qualification; `clk_db` reports. Only qualified mask
changes consume the 320-record budget; state/heartbeat does not.

An unpublished intermediate build exposed two undefined monitor aliases during
focused HDL validation. The builder was corrected to reuse the already bound
`local_req_hs[g][s][4]` and `local_wdata_hs[g][s][4]` surfaces, then rebuilt
twice from fresh directories. The authoritative builds are byte-identical:

- bytes: `1971409`
- ZIP SHA256: `1dfa3f28687f2725ea22579a05871b0353d2302914062225ecd13ac5784938ef`
- sidecar SHA256: `a67d8dd0264102d0d40148a4896cf8257e6f47778ccf06e4eb2394d89df5a777`

Frozen numeric/sum/tail/workload/config/golden bytes and timeout/backpressure
are unchanged. No functional RTL was included or changed.

## Validation

- family changed-surface validator: exit 0, SHA256
  `055eb5582750ebb205b1fd15443936428bf13bc1c2a6532522702d0b43b87f0a`
- safe runner/finalizer harness: exit 0, SHA256
  `25ee725fa3fc59f5835622959c6c6d736294952abcbdeda93526a68cdae9fea9`
- shared harness: exit 0, SHA256
  `18217eeb43b112bf7f6c083ac3321ecda63f83aa759c8cf6c808a6920dc8f094`
- shared exact-ZIP runtime validator: exit 0, SHA256
  `0795cef3932968cbd284386c5e5f62dac993d2c2f0d2ad8572344f3bee49bfe5`
- final-ZIP audit: exit 0, `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors 0,
  SHA256 `a23795eba88ba00d0189fa57180261c724c396172c4782ff37f8b054dd7ee2ee`
- normal/preflight-fail/compile-fail/HUP/INT/TERM exits:
  `0/5/73/129/130/143`; shared finalizer, fixed unique return, sidecar and root
  direct-set checks pass in all six flows.
- focused HDL positive compile passes; declaration deletion, typo use and key
  update deletion fail closed. Exact predicate self-test/trace passes.

## Package release

Status: `PACKAGE_READY_NOT_RUN`.

Pickup:
`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v52_ga_read_mse4_direct_diag.zip`

Command:
`bash r5_n71_gap_v52_ga_read_mse4_direct_diag/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

Expected return:
`/home/panqs/ndp/simresult/r5_n71_gap_v52_ga_read_mse4_direct_diag_r<epoch-ns>_<pid>_return.zip`

## Rule feedback

Confirmed `CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001`,
repeat-execution owned reset, and result conjunction. `RULE_DELTA_PROPOSAL=NONE`.

Claim boundary: no server/DUT run for v52, no natural terminal, no formal D,
and no E3/E4/E5 or production claim.
