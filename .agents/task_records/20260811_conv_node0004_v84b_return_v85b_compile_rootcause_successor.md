# 2026-08-11 serialized Conv v84b return -> v85b compile-rootcause successor

## Ownership / handoff closure

- role: `family.conv.serialized`
- active owner thread: `019ff02d-901b-7f70-a9da-f54e268b5bbe`
- owner epoch: `2`
- current registry epoch observed before publication: `6`
- current mainline thread: `019ff027-e7db-72a3-b282-cfad8708da05`
- handoff publication: `.agents/task_records/20260811_handoff_conv_serialized_publication.json`, bytes `1061`, SHA-256 `5d2dfe7b9d3d0cdd407db8215f0902be545f25f81432c29dcc8d23c72672ef0a`
- activation response: `HANDOFF_ACTIVATED`, `conflicts=[]`

## Bound predecessor and formal return

- source pending ZIP before rotation: `r5_n4_hw_v84b_ack_inline_realtime_diag.zip`
  - bytes: `5264811`
  - SHA-256: `0ccb7e46856b814df4e0849129a765df7026ea7f52b76c73502c369c15c14ac4`
- formal return:
  - execution: `r1786436071113419680_1052700`
  - SHA-256: `43f1a99877de60e40b273aa05f8d5a57e8159dd4a5229809e0f09a620b544a8d`
  - compile exit: `2`
  - run exit: `125`
  - simulation started: `false`
- inherited causal boundary: production compile failed, but the prior return omitted the actual compile argv, selected source identity, bounded compile log and first-error evidence; the RTL/numeric cause therefore remains unresolved.

## Fresh successor

- package: `r5_n4_hw_v85b_compile_rootcause`
- final build ZIP: `outputs/conv_node0004_v84b_return_v85b_successor/build/r5_n4_hw_v85b_compile_rootcause.zip`
  - bytes: `5272850`
  - SHA-256: `d8b5c3ecfbc44839863ff7db1e8f0ad4559a343bf92d640a2455e9d06de5aad7`
- pending publication: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v85b_compile_rootcause.zip`
  - bytes: `5272850`
  - SHA-256: `d8b5c3ecfbc44839863ff7db1e8f0ad4559a343bf92d640a2455e9d06de5aad7`
- predecessor rotation: `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_serialized_node0004/r5_n4_hw_v84b_ack_inline_realtime_diag/r5_n4_hw_v84b_ack_inline_realtime_diag.zip`
  - bytes: `5264811`
  - SHA-256: `0ccb7e46856b814df4e0849129a765df7026ea7f52b76c73502c369c15c14ac4`
- server upload/run/lease: `NONE`

The package is published through `manage_server_test_package_storage.py rotate`, not by a bare pending-directory copy. Its sidecar and release evidence live under `pending_receipts/conv_serialized_node0004/r5_n4_hw_v85b_compile_rootcause/`; the former v84b ZIP and its receipt set move together into the tested family tree. A global storage `audit` must be clean before handoff notification.

## Changed and frozen surfaces

Changed only:

1. fresh package identity and identity-only SCA/runtime paths;
2. runner definition-before-use/bootstrap finalizer handling;
3. pre-compile persistence of the exact argv and selected source identities;
4. bounded `compile_driver.log`, 64-KiB head/tail, bounded first-error and compile-exit receipts;
5. minimal-return and shared post-sim core allowlists/contracts for those seven compile-rootcause files.

Frozen:

- config/numeric/workload semantics;
- workload payload bytes and all matrices/golden/formal-D targets;
- functional RTL, hardware ISA and active ndp-sim;
- v84b diagnostic executable HDL semantics and timeout/backpressure/workload.

The current source-bound generator was run fresh before full materialization. Its only observer-text delta is the generated `plan_semantic_sha256` provenance comment caused by the fresh plan identity; after normalizing that line, executable diagnostic HDL is byte-equal to v84b. All other package-local HDL is exact or identity-normalized byte-equal.

## Runner / return resilience closure

- `set -u` definition-before-use:
  - unsafe package-owned expansions: `0`
  - bootstrap assignment line: `12`
  - finalizer arm line: `132`
  - first declared fallible execution line: `141`
- bootstrap root is independent of attempt-root creation:
  - `install/codex_runs/<package_id>/bootstrap-<return_tag>`
- required core evidence:
  - `compile_argv.json`
  - `compile_source_identity.json`
  - `compile_exit.txt`
  - `compile_driver.log`
  - `compile_first_error.txt`
  - `compile_log_head.txt`
  - `compile_log_tail.txt`
- the full compile driver log remains outside the return; only bounded evidence is allowlisted.
- the shared helper's `return_core/RETURN_FINALIZER_STATE.json` persistence is explicitly declared before plugin invocation.

## Aggregate and exact-ZIP gates

- builder: `tools/build_node0004_v84b_return_successor_v85.py`
  - bytes: `63145`
  - SHA-256: `ac3484fde8a13ffc5e5ab571113349c9cd0601f024b5aefa11dd29e56b281b53`
- shared build profile: `outputs/conv_node0004_v84b_return_v85b_successor/server_package_build_profile.json`
  - bytes: `20887`
  - SHA-256: `b63c1f8557e6252499e6e18ff2b7469f60cde1a7e290b8677b11de0bed192896`
  - cheap aggregate top-level invocations: `1`
  - all required cheap reports supplied, including `runner_return_resilience`
  - receipt reuse candidates: `[]`
- deterministic full-tree rebuild equality: `PASS`
- final ZIP count for the successful `v85b` identity: `1`
- exact final ZIP aggregate: `outputs/conv_node0004_v84b_return_v85b_successor/final_zip_audit_v85.json`
  - bytes: `2527`
  - SHA-256: `b91d83de62ce62f4f861d67adeca78ac509eee95bc15e7af12b8bb227153867e`
  - `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
  - errors: `[]`
- runner return resilience: bytes `2258`, SHA-256 `fe5adce462793474e3e7aabdd2fbdfed1fb95494362da3c6b8ab6591027c72a1`, `pass=true`
- source-bound exact-generation / semantic controls: bytes `171759`, SHA-256 `fbab9290d1b44b51ce6b34f52c34e2e730f4ef4aa268b8d104b1aaaebed1e750`, `pass=true`, typed v2
- post-sim return core: bytes `2977`, SHA-256 `515c3cd1b9fa0197ad5cd0f1a0c0855d5ef431b3769b4917925b92982a6dbe4d`, `pass=true`, all four local scenarios present
- waveform gate: bytes `442`, SHA-256 `28fdbe277fdede769826c05ef480bab98725caa66723d81f5b8eaf5908ecb4a2`, `pass=true`, applicability `not_applicable`; dumps remain disabled because the predecessor failed before simulation and bounded text is the required causal evidence
- first-fresh independent exact-ZIP audit: bytes `2459`, SHA-256 `ea187aebc4d296973eadeed7ab0104d03fad09c6009670d10922bb40c798694c`, `pass=true`, `upload_authorized=true`

## Validation notes

- exact ZIP CRC, single-root/safe-member, manifest exact-set, package Python AST and sidecar checks: `PASS`
- `python -m unittest -q tests.test_server_runner_return_resilience`: `6 tests`, `PASS`
- exact source-bound and post-sim validators were executed directly from the same final ZIP and passed.
- bundled Python lacks optional `pytest` and `jsonschema`; therefore the broader pytest invocation was not used as a release claim. This is nonblocking because the exact required validators and shared resilience unittest completed successfully.
- local bash is unavailable, so no separate `bash -n` claim is made; the exact runner static validator and post-sim integration validator both passed.

## Local failed candidates (not published)

- prebuild attempt 1 was stopped by the shared finalizer-order validator because its token set included a function-body `mkdir -p`; the contract was corrected to the execution-path fallible tokens and rerun from a clean output root.
- local `v85` exact ZIP was not published because shared post-sim validation required the runner literal `RETURN_FINALIZER_STATE.json`; changed bytes received the fresh `v85b` identity.
- the first `v85b` audit-contract rendering carried an extra `bytes` field and read the plan's wrong candidate key. The ZIP itself already passed runner/source-bound/post-sim; the audit schema was corrected and rerun from a second clean extraction of the same unchanged ZIP SHA.

## Claim boundary / next action

This record claims a local package and exact-ZIP gate closure only. It does not claim a production compile, simulation, natural terminal, 320 formal-D results, E4/E5, server upload, server run or lease.

Next action: current mainline may consume the exact pending ZIP receipt and task-record receipt. Any later server execution must return the seven bootstrap compile-rootcause files before serialized-Conv causal work resumes; no server action was taken in this task.
