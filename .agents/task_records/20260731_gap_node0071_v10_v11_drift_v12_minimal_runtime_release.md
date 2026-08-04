# GAP node0071 v12 minimal-runtime package release

Date: 2026-07-31

Source/mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

- v10 behavior already had a fresh-extract runner positive control, but its
  final manifest/README bound the superseded server rule SHA
  `7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa`.
- v11 refreshed the receipt to
  `bcf62cc301f721a48641ecd9a7a1c6ad38a16cc831fb7a695da9229782f35f38`,
  but was never released because the next rule required minimal server-side
  preflight and prohibited a second hard-coded observer SHA in the runner.
- v10 and v11 remain byte-preserved and quarantined. The only runnable
  successor is v12.
- No GAP sum/tail numeric analysis, config generation, golden generation, or
  workload execution was repeated.

## FIRST_DIVERGENCE

`POST_GENERATION_CURRENT_RULE_DRIFT_AT_RUNNER_EXPECTED_IDENTITY_OWNERSHIP`

The v11 runner embedded observer SHA
`0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8`
as a second expected-identity source. Current rule requires the final manifest
to be the single source of truth.

## BLOCKER_DELTA

- Closed:
  `PACKAGE_RUNNER_PREFLIGHT_TO_COMPILE_CHAIN_UNPROVEN`.
- Closed:
  `PACKAGE_RUNTIME_PREFLIGHT_OVERREACH` for this package. The runner performs
  no pre-compile enumeration/hash/requirement of existing server RTL, TB,
  Makefile, filelist, Git, README, observer, or specific server source file.
- Closed:
  duplicate runner observer SHA. Canonical identity is JSON Pointer
  `/files/tb_probe~1native_return_observer.svh/sha256`.
- Still open: real server compile/elaboration/run, natural terminal, all 48
  formal D readbacks, `missing_count=0`, `mismatch_count=0`, and result-gate
  conjunction. E3/E4/E5 remain zero.
- Server-source identity is intentionally unbound under
  `CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001`; this limits version
  attribution and production claims.

## RULE_DELTA_PROPOSAL

No new public rule proposal. The published rules were sufficient:

- `CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001`
- `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`
- `CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001`

Current server rule SHA:
`0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a`.

## PACKAGE_RELEASE

Status: `PACKAGE_READY_NOT_RUN`

Claim: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`

Package:
`artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v12_minruntime.zip`

- bytes: `1793432`
- SHA-256:
  `a1e149e7e4a20cd254e84a8fd7199607beeafb11fd71cfe4d548226825b06d06`
- sidecar SHA-256:
  `47a8dce27c7d7f01cdef48c88c80c592cd48f7f0c54e70fcafdbb4898c65f61d`

Single server command:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected return:

- `r5_n71_gap_v12_minruntime_return.zip`
- `r5_n71_gap_v12_minruntime_return.zip.sha256`

Final ZIP self-audit:

- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- report SHA-256:
  `670f708c5ca743ed2323efa6589477f3f2b44d7a096675edb401bc28e7e7b98e`
- runner-chain report SHA-256:
  `fd5903a8dd9d83a8246a60d9bfb6bfa078fd5c05b63cd385f650864cd3110512`
- observer four-way report SHA-256:
  `679406a4b473cc7c9983aab264360ec9357b52dc56f1a582388d8a19dd8aa830`

All independent validator commands exited `0`. The real-runner safe compile
stub positive exited the unique expected `86` after reaching compile and
capturing actual argv. Wrong manifest identity exited `5` before compile.
Source/incdir/macro/runtime-return and canonical decision negatives all failed
closed.

Frozen-reuse boundary:

- v11→v12 exact changed paths:
  `PREPARE_AND_RUN.sh`, `README.md`, `TEST_PACKAGE_MANIFEST.json`,
  `package_tools/gap_node0071_package_observer_guard.py`,
  `workload/sca_cfg.json`, `workload/sca_cfg_D.json`.
- 73 numeric workload files: byte-identical.
- 119 remaining immutable files: byte-identical.
- observer source/algorithm: byte-identical.
- two deterministic builds: identical ZIP SHA.
- functional RTL modified: false.
- server inspected/uploaded/run: false.

