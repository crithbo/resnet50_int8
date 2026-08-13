# family.conv.native p41 mandatory-VPD package publication

- role_id: `family.conv.native`
- owner_thread: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- owner_epoch: `2`
- registry_epoch: `6`
- current_mainline: `019ff027-e7db-72a3-b282-cfad8708da05`
- shared_gate_epoch: `waveform-mandatory-v2-01ca6d7cd4a4a270`
- rule_id: `CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001`
- status: `PACKAGE_READY_NOT_RUN`

## Previous-version progress and current-version purpose

Previous-version progress: p39 closed production compile exit=2 to the two package-local observer `arb_req_ready` XMR sites. Old p40 preserved the Datahub public-surface and structured-first-error repair, but it was withdrawn for old `DUMP_VCD=0` semantics and remains superseded.

Current-version purpose: p41 preserves the p40-equivalent diagnostic, is intended to prove production compile beyond the public-surface repair, and returns mandatory full-hierarchy unbounded VPD so the retained MSE4 causal blocker can be localized in one run.

## Exact source and fresh package

- exact superseded p40 source:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_native_four_lane/r5_n4_0cc_p40_dhpubfix/r5_n4_0cc_p40_dhpubfix.zip`
  - bytes: `5973269`
  - SHA-256: `64c47086bcc1e9dade1b1c9e9fb912c186f49a0ab223c816996e08e9ad86b39f`
- exact fresh pending ZIP:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p41_vpdfull.zip`
  - bytes: `5986703`
  - SHA-256: `339d8f4e17cbf34132be9bc84f33dec637ea3fd6ecc8deeec5aa5620a012a95a`
- pending sidecar receipt:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p41_vpdfull/r5_n4_0cc_p41_vpdfull.zip.sha256`
  - bytes: `92`
  - SHA-256: `2f06d33b4b711a4e51b8c13301f1c20ac339e4d0e232af58dd098c0910621c07`

## Frozen surface and authorized delta

- Frozen: config, numeric, workload, functional RTL, p40 Datahub public-surface observer repair, structured-first-error repair, and retained MSE4 target diagnostic.
- Identity-normalized p40 comparison passed for all 89 workload members and all protected observer/parser/catalog/plan/contract fixtures.
- Functional RTL modified: `false`.
- Authorized changes only: fresh package identity plus waveform/runtime-return surfaces.
- Old p40 was not rebuilt, mutated, or restored to pending.

## Mandatory waveform closure

- Actual make/simulator controls: `DUMP_VCD=1`, `DUMP_FSDB=0`, `TB_DUMP_FSDB=0`.
- Format: VPD.
- Top/scope: `tb_NDP_Top_new_phy`, `FULL_HIERARCHY`, depth `0`.
- Exclusions: none.
- Runtime patterns: every `wave.vpd` and `wave.vpd.*` shard below `compile/sim_results`.
- Return policy: collect all matching files, `hard_limit_bytes=null`, no sampling, no truncation, no size-based deletion.
- Simulation-started without waveform: fail closed.
- Compile-not-started: waveform omission permitted only while the independent bootstrap-safe compile-core return remains mandatory.
- Runner invokes the waveform collector before the shared post-sim finalizer and maps NATURAL, TIMEOUT, HUP, INT, TERM and SIMULATION_NONZERO exit kinds.

## Exact gates

- deterministic double-build tree equality: PASS
- config/numeric/workload/functional-RTL/target-diagnostic freeze: PASS
- shared prebuild aggregate, one top-level invocation: PASS (only the registered record-only formatting fixture warned)
- runner definition-before-use: PASS, `unsafe_uses=[]`
- bootstrap-safe actual compile argv/source identity/bounded head-tail/first-error core return: PASS
- compile-not-started exact allowlist and waveform exemption: PASS
- source-bound typed-v2 final ZIP: PASS
- post-sim final ZIP and partial-exit live-causal integration: PASS
- mandatory waveform v2 final ZIP: PASS
- p40 observer public-surface preservation: PASS
- local six-state runtime harness: PASS for normal, preflight-fail, compile-fail, HUP, INT and TERM; local simulator stub emitted a nonempty VPD for every simulation-started scenario
- runtime-layout validator: PASS
- independent first-fresh clean-extract audit: PASS, errors `[]`, warnings `[]`
- final-ZIP self-audit: PASS, errors `[]`

Exact final receipts:

- final ZIP audit:
  - path: `outputs/conv_native_four_lane_0ccae916_p41_vpdfull/r5_n4_0cc_p41_vpdfull.final_zip_audit.json`
  - bytes: `5345`
  - SHA-256: `d77904afd1a888873bcd17273f04b17e0bda4693d29efc5b4131ed3717eed954`
- first-fresh contract:
  - path: `outputs/conv_native_four_lane_0ccae916_p41_vpdfull/first_fresh_audit/contract.json`
  - bytes: `3208`
  - SHA-256: `20d00c75e561dc8d9debef107ec29c50ea57d97312ea11a1d4c3950a1a178a95`
- first-fresh validation:
  - path: `outputs/conv_native_four_lane_0ccae916_p41_vpdfull/first_fresh_audit/first_fresh_validation.json`
  - bytes: `2416`
  - SHA-256: `6a806f40667596e205f8da6370db2a9d061e7253b0243023aaca3954b0d01666`

## Storage

- `manage_server_test_package_storage.py rotate` published only `r5_n4_0cc_p41_vpdfull` to the flat pending pickup directory.
- Post-rotation global storage audit: PASS.
- Pending count: `1`.
- `pending_by_family.conv_native_four_lane = ["r5_n4_0cc_p41_vpdfull"]`.
- Old p40 remains exactly under `superseded/conv_native_four_lane/r5_n4_0cc_p40_dhpubfix/` and is absent from pending.
- storage index:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`
  - bytes: `396745`
  - SHA-256: `5f6b85b1dc8557099a908d3e7745c9a5b0c73ce0060e8d23b126fdffec617881`

## Server command and expected return

The only authorized future server command is:

`bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`

Expected fixed return templates:

- `/home/panqs/ndp/simresult/r5_n4_0cc_p41_vpdfull_r<epoch-ns>_<pid>_return.zip`
- `/home/panqs/ndp/simresult/r5_n4_0cc_p41_vpdfull_r<epoch-ns>_<pid>_return.zip.sha256`

No upload, lease, server run, or other server action was performed by this owner.

## Claim boundary and mainline action

This record claims local construction, exact source/fresh identity, frozen-surface equality, exact final-ZIP gates, first-fresh gates, and clean local storage publication only. It does not claim production compile, DUT execution, natural terminal, waveform existence in a future production return, formal 320D, E4 or E5.

Mainline should consume this receipt and update the owner registry/plan from `PACKAGE_BUILDING` to `PACKAGE_READY_NOT_RUN`, pointing native Conv pending to `r5_n4_0cc_p41_vpdfull` without changing the package bytes.
