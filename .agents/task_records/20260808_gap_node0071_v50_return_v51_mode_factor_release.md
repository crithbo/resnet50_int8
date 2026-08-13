# GAP node0071 v50 return → v51 mode-factor diagnostic release

Owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`  
Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## RETURN_ANALYSIS

The v50 repeatable-runtime return is internally authoritative:

- return SHA256
  `af493115127b0040d8bec83815d0e00d2fc90a7a9c559b11758ddb42982adfc2`;
- source SHA256
  `96c23c3762b9fca323ff3d76250f8ca9482c74d536a93b843321c8be3f37252d`;
- CRC/root/path/duplicate/symlink, RETURN_MANIFEST exact-set/allowlist,
  per-file receipts, stable source manifest, and per-execution
  `r1786110415338387175_3719505`→`a3719505` binding all pass;
- adjacent sidecar is absent and accepted only at the user-attested transport
  layer; no internal gate was relaxed;
- compile `0`, simulation `125`, runner `130`, signal `INT`, no natural
  terminal;
- formal D `0/48`, missing `48`, mismatch `0` is unevaluable;
- E3/E4/E5 are all false.

The returned finalizer parser statuses are all `2`: parser variables captured
the pre-canonical relative `package_root=.` and later resolve under
`NDP_copy03/./package_tools`. Exact source parser replay over the returned raw
observer log exits `0`; this is a package-local finalizer path bug.

## LPG / FD / HANG_ROOT_CAUSE

LAST_PROVEN_GOOD is sum_s1 all-slice MSE0/MSE3/GA input/selected-outbuffer
write plus MSE4 idx/request/q_wr, all `0xffff`.

FIRST_DIVERGENCE is diagnostic coverage:

- v50 GA conjunction record `n=256` at `704646000 ps`;
- first later-slice GA output occurs at `739638000 ps`, mask `0x0003`;
- state-only slice0 oscillations consumed the entire v50 emit budget before
  slices1–15 reached the observed boundary.

Therefore v50 zero masks for slices1–15 are not functional evidence. The
functional blocker remains
`B_GAP_NODE0071_GA_OUTBUFFER_TO_MSE4_POST_QUEUE_PENDING_LEAF`, with mode
selection, selected write, nonempty/read, and MSE4 q_rd/buffer/prepared
acceptance still candidates.

Return report:

`artifacts/operator_config_validation/r5-gap-node0071-v50-return-analysis/report.json`

SHA256:
`241ea0f4d823011433ca949a22c64093b99004eeb810122ca6a902d7297125b3`

## SUCCESSOR / PACKAGE_RELEASE

Fresh successor:
`r5_n71_gap_v51_ga_ob_mode_factor_diag`.

It fixes finalizer parser rebinding after canonical `package_root` resolution
and adds one qualified-only, all-slice information-gain feature covering ALU
request, normal/transout selection, selected write handshake, selected write,
nonempty, selected read, and the inherited MSE4 direct-consumer chain.
Heartbeat/state records cannot consume the qualified limit.

Frozen:

- numeric/sum/tail/workload/config/golden byte-equal after identity
  normalization;
- timeout/backpressure unchanged;
- no functional RTL modification;
- repeat-safe exact-owned reset and unique return semantics retained.

Final build A/B:

- bytes `1966085`;
- ZIP SHA256
  `76336937dd52822e948dcc81c6f35054c73d0066dfad5f964b6753a04a78f7b4`;
- sidecar SHA256
  `30ff3b0181dde583184ee81826f50b5f6c2aa3593eeefd975bb147f1aae4cea7`.

Validation:

- family changed-surface validation: exit `0`, SHA256
  `0989f148b9b7dcd21ec52162b9c368021d7b39ecc90b4ca374e7845fb50f54a8`;
- runner normal/preflight-fail/compile-fail/HUP/INT/TERM:
  `0/5/73/129/130/143`;
- all six controls publish a unique return and valid sidecar, preserve the NDP
  root direct-set, and enter the shared finalizer;
- normal parser statuses all `0`, parser stderr empty;
- shared runtime validation: exit `0`, SHA256
  `f4581523b26ca99ec9991fa7a88b85c9672f2a908f22aed7609d4a2742d342f3`;
- final ZIP rule self-audit: PASS, errors `0`, SHA256
  `1910e2b60ff24641fa5fe501de3c7acb413c5585d5de61aefdd7f264f0112baf`.

Status: `PACKAGE_READY_NOT_RUN / DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

Command:

`bash r5_n71_gap_v51_ga_ob_mode_factor_diag/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

Expected unique return:

`/home/panqs/ndp/simresult/r5_n71_gap_v51_ga_ob_mode_factor_diag_r<epoch-ns>_<pid>_return.zip`

Closure machine report:

`artifacts/operator_config_validation/r5-gap-node0071-v50-return-v51-release/report.json`

SHA256:
`b817967bd736c4de98d9a7989c88e95d4cd621205e0c07b31c03b1d36f3ea78b`

## RULE FEEDBACK

RULE_CONFIRMATION: repeatable-return source/per-execution binding, all-missing
formal-D conjunction, current final-ZIP/runner/install/fixed-simresult/root and
storage gates behaved correctly.

RULE_DELTA_PROPOSAL:
`CDA-SERVER-DIAGNOSTIC-QUALIFIED-BUDGET-NOT-CONSUMED-BY-STATE-001`.
A multi-slice/lane qualified observer must keep state/heartbeat on a separate
non-progress budget and prove that early-slice state oscillation cannot exhaust
later target coverage.

No server action, upload, run, lease, plan/rule/functional-RTL modification, or
numeric replay was performed.
