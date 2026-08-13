# Conv node0004 v62 silent exit → v63 runner-visible successor

## Outcome

- Server-first recovery was attempted using the configured `NDP` SSH target, but authentication failed with `Permission denied (publickey,password)` (exit 255). No server write, upload, simulation, or lease occurred.
- The frozen v62 runner contains package-owned pre-compile branches that call bare `exit`, including return-target collision exit 10. This explains how `bash ...` can terminate without a diagnostic. Because server access and an exact server exit receipt were unavailable, the precise branch taken is not claimed.
- A fresh local successor `r5_n4_hw_v63_runnerdiag` was generated. It preserves the v62 functional configuration and payload and changes only identity/runner visibility/manifest projection.
- v63 emits `RUNNER_ERROR code=... package=... message=...` for every package-owned early failure and one `RUNNER_FINAL_STATUS` line from the finalizer.

## Frozen scope

Numeric data, W3, qparams, tail, workload, golden, PE1 `keep_last_index=3`, observer semantics, timeout, backpressure, functional RTL, ISA, hardware, and active ndp-sim are unchanged.

## Package

- Status: `PACKAGE_READY_NOT_RUN`
- Candidate release: `false`
- ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v63_runnerdiag.zip`
- Bytes: `5159479`
- SHA256: `99f50faeed69d89cff3211121661b5331a9e98d8135064b41b76203f7c277712`
- Command: `bash r5_n4_hw_v63_runnerdiag/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- Expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v63_runnerdiag_return.zip`

v62 was moved intact to `superseded/conv_serialized_node0004/r5_n4_hw_v62_pekeep_fix`; the serialized Conv family has exactly one pending ZIP.

## Validation

- Deterministic double build: PASS.
- Install-only V2 family validation: PASS, exit 0.
- Shared runtime-layout validation: PASS, exit 0.
- Focused observer validation: PASS, exit 0.
- Predicate trace: PASS, exit 0.
- Runner visibility positive/negative controls: PASS. Missing argument exits 2 with stderr; invalid server root exits 2 with stderr; return collision exits 10 with stderr and preserves the existing file; a bare collision branch fails closed.
- Final ZIP audit: `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`, SHA256 `9680a547429ba90f3fd4676da6ad66b6d40c98b67ce4a0d2a9aeb13c04fdbe94`.
- Storage audit: PASS; only `r5_n4_hw_v63_runnerdiag` is pending for `conv_serialized_node0004`.

## Rule receipts

- agent: `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- plan (mutable provenance): `83dc18e72d215bce54d664fabbf3d17684e480b4edb15ca49be8ac36a8115852`
- index: `3c2bd9017f351b6456eac49c966063cc9b76e96420d71162a1ca57d1b62b552c`
- server rule: `89d27141f1a151ef5e6cc98603238050c9b0442a3d1937b2ec23cf92e55a27a2`
- common config: `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- NDP fields: `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- INT8-SA: `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- hardware README: `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`

Relevant rules consumed include `CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001`, `CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001`, `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`, `CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`, `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`, `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`, `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`, `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`, and `CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`.

## Rule feedback

`RULE_DELTA_PROPOSAL`: require every package-owned nonzero exit before compile/finalizer handoff to print a concise stderr record with package identity, numeric exit code, failed gate, and recovery/evidence hint. Add negative controls for silent return collision, missing tool, and invalid server root. Safe compile-stub reachability alone does not prove this user-visible failure property.

## Claim boundary

This closes local package/runner visibility and release auditing only. It does not claim server compile/simulation, DUT natural terminal, formal 320D, E4, or E5.
