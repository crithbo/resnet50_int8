# GAP node0071 v9 startup diagnosis and v10 runner-guard repair

Date: 2026-07-31  
Owner thread: `019fa366-cb1f-7ae2-880c-f527be0680cd`  
Return target: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

- Screenshot:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\temp\RWTemp\2026-07\20f30dfa7bcf5df119fa6e67acbfb5c6\1dacbf3b35ffb2261e3b0dadc1d6042b.png`
- Screenshot bytes/SHA-256:
  `18684 / 5f9c5e5cfa615aaea87b903e5f1d8481e49b274673ab4adffe822c62422b0c96`
- The screenshot is sufficient to prove that the foreground command returned
  to the prompt after printing only the package preflight JSON. It does not
  show install, compile, simulator, or return generation.
- Frozen v9 source ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v9_ingress_rule.zip`
  SHA-256
  `d37f40e768001d3588cd22f25040ba4e229ffc138221a42b13d7e446436e644c`.
- v9 `PREPARE_AND_RUN.sh` passes package preflight, installs and passes the
  installed workload preflight, then invokes the package-local observer guard
  with expected SHA
  `47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`.
- The actual package-local
  `tb_probe/native_return_observer.svh` SHA is
  `0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8`.
- Guard stdout is redirected to
  `evidence_r5_n71_gap_v9_ingress_rule/observer_precompile.json`; the explicit
  `|| exit 7` returns control to the shell. `set -u` and `set -o pipefail`
  are enabled; absence of `set -e` does not affect this explicit branch.

## FIRST_DIVERGENCE

`OBSERVER_GUARD_EXPECTED_SHA_MISMATCH_BEFORE_COMPILE`

Local full-run mock result:

- v9: package preflight valid, installed preflight valid with 75 installed
  workload files and formal D targets absent, observer guard invalid with
  `identity_match=false`, runner exit `7`, compile mock not reached.
- v10: same preflights valid, observer guard valid with
  `identity_match=true`, actual compile argv written, compile mock reached and
  deliberately returned `86`.

Therefore the failure is package-side and occurs before compile, simulation,
GAP arithmetic, terminal, and formal readback.

## BLOCKER_DELTA

- Closed:
  `B_GAP_NODE0071_V9_RUNNER_OBSERVER_EXPECTED_SHA_STALE`.
- v9 is quarantined and must not be rerun.
- No GAP sum/tail numeric analysis or workload execution was repeated.
- The 73-file numeric workload tree is byte-identical between v9 and v10.
- The 120-file immutable non-receipt tree and observer algorithm are
  byte-identical.
- Open dynamic blockers remain unchanged: server compile/simulation, natural
  terminal, 48 formal D exact-set and exact equality, qualified dual-ingress
  behavior, and E3/E4/E5 adjudication.

## RULE_DELTA_PROPOSAL

Propose `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`:
after final ZIP generation, a safe package-bound mock must execute the real
runner through package preflight, installed preflight, and every package-local
precompile guard until the compile invocation is positively reached. A
deliberate compile stub exit may stop the test. The audit must also prove that
a wrong guard identity stops before compile. Static four-way source/include/
macro/runtime checks alone do not detect a stale hard-coded expected observer
SHA inside the runner.

## PACKAGE_RELEASE

- Fresh identity: `r5_n71_gap_v10_runner_guard`
- Claim:
  `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / PACKAGE_READY_NOT_RUN`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v10_runner_guard.zip`
- ZIP bytes/SHA-256:
  `1792702 / 1293d2f3868974edefad562bc28d9128a23bf3ff609df096bd68c11fd6a3a2b8`
- Sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v10_runner_guard.zip.sha256`
- Sidecar file SHA-256:
  `1438b7fb0027fa39b1bc802063620c33d49e8b1d0f5465677ee574464e38ecae`
- Server command:
  `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`
- Expected return:
  `r5_n71_gap_v10_runner_guard_return.zip` and
  `r5_n71_gap_v10_runner_guard_return.zip.sha256`
- Changed relative files are exactly:
  `PREPARE_AND_RUN.sh`, `README.md`, `TEST_PACKAGE_MANIFEST.json`,
  `workload/sca_cfg.json`, `workload/sca_cfg_D.json`.

## Final ZIP self-audit

- Report:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v10_runner_guard.final_zip_rule_self_audit.json`
- Report SHA-256:
  `416923e80e9e52d7c902d361b5795bdf8c55c2fff0bd699251252a8f613f068c`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=[]`, `error_count=0`
- ZIP CRC, sidecar, manifest exact-set, manifest receipts, current-rule
  receipts, runtime-D absence, bootstrap immutability, return allowlist,
  canonical decision, observer four-way binding, dual-ingress observer and
  runner-chain checks all pass.
- Command harness exit codes:
  canonical `0`, observer four-way `0`, dual-ingress `0`, runner-chain `0`,
  fresh preflight `0`, canonical self-test `0`, bash syntax `0`.
- Runner-chain report:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v10_runner_guard.runner_chain_validation.json`
  SHA-256
  `db55ad199c0d57bbc3b8f8a5732e4c219be84f143a2600b52056264960375ce7`.
- All required negative controls fail closed.

## Current rule receipts after package generation

- generation index:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- common operator:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- NDP field semantics:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- server package:
  `7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa`
- GAP int32:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- GAP dynamic:
  `4191f12fb19fc301cb323993b9aee0b28057c339adba1af780e9d27ff3068baf`
- exact UINT8 tail:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- plan mutable provenance:
  `558dce2c256f91bcf537750262b717db00c97ea415849d544cc13d365049a47e`

No server file inspection, upload, run, public-rule edit, plan edit, or
functional RTL edit was performed.
