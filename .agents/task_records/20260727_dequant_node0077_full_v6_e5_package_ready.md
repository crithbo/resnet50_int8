# Dequant node0077/v6 stock-RTL E5 package ready

Date: 2026-07-27

## Status

- Package identity: `dequant_node0077_stockrtl_e5_onecmd_v1`
- Status: `E5_PACKAGE_READY_NOT_RUN`
- `candidate_release=false`
- Remaining blocker: `B_DEQUANT_SERVER_E5`
- No upload or server run was performed.
- No `rtl/**`, TB, public rule, or `.agents/plan.md` file was modified.

## Frozen source and derivation

- Frozen E4 ZIP SHA-256:
  `2ac27a4856b36bb660c0293ff53f84794464283712f20fe0d84dabfa16b699e0`
- Frozen E4 manifest SHA-256:
  `5916ccd3c4999daa49368d61dd80a19ab09d3a501bbbcd43c92b0a3a77e61f10`
- Authoritative E4 analysis SHA-256:
  `c7d1380f6dd365b6349e050390a5e112125906eb04a73fcd54a3dec412bfe35f`
- E4 pass record SHA-256:
  `e7fe4ceaf9a9581b68b5ddf16d57f7bc19a9f5ee6a34aa4b4b9235f16c81cc28`
- Workload comparison: 61 paths identical; 60 byte-exact and one
  `sca_cfg.json` path-only install-namespace rewrite that becomes byte-exact
  after E5-to-E4 normalization. `sca_cfg_D.json` is byte-exact.
- Frozen semantics include strict JSON, mapping, bitstream, execplan, 28 input
  shards, 28 golden shards, full-output golden, addresses, lengths and inverse.

## Package identity

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/dequant_node0077_stockrtl_e5_onecmd_v1.zip`
- ZIP size: 153,596 bytes
- ZIP SHA-256:
  `83cd2db78f99d27f02c2b65a46f9f5c43e94b9ff9a5c50ef0273a0409f1cab68`
- Sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/dequant_node0077_stockrtl_e5_onecmd_v1.zip.sha256`
- Manifest SHA-256:
  `dd945f768755d8e937d44d6e258f06e6e9a03d10932a1ec4531543f3bc4fda46`
- Payload: 85 files plus manifest; payload tree SHA-256:
  `74cf018513e664a5c4b8e378b7bcbac6449c67ded08d59f80fc079da9b6494a8`
- ZIP exact set: 86 entries; `rtl/` entries: 0.

## One-command server operation

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

Expected return:

- `dequant_node0077_stockrtl_e5_onecmd_v1_return.zip`
- `dequant_node0077_stockrtl_e5_onecmd_v1_return.zip.sha256`

The success allowlist contains 106 paths: 28 formal D readbacks, 28 lifecycle
logs, 28 observer logs, focused identities/gates, SCA/SCA_D, bounded log tails,
package manifest and return receipt.

## Gates and verification

- Two independent deterministic builds were byte-identical.
- Exactly one final fresh-extract complete self-check passed.
- Bootstrap package tree remained 86 files / 1,209,439 bytes with identical
  path/size/SHA tree before and after runtime preflight plus observer
  install/verify/restore.
- Complete bootstrap tree SHA-256 before and after:
  `19cd2feb92cac39642ef6f3d99395955f60ca3d62f2d24592ffc0203591c0df2`.
- Packaged Python bytecode count: 0.
- Functional RTL/TB replacement count: 0.
- Formal D geometry: 28 slices × 188 lines = 5,264 128-bit lines.
- Expected raw observer counts: 5,264 requests and 5,264 write-data events.
- Layout inverse SHA-256:
  `d5aa938813ec8ef7fe51cc2288df5f0e1782c19729a184cef248718ce83a311d`.
- E5 preflight reports `dynamic_run_gate=E5` and
  `evidence_level=E4_SERVER_FORMAL_PASS_E5_NOT_RUN`; the E4 preflight boundary
  remains `dynamic_run_gate=E4`, `evidence_level=E2_LOCAL_ONLY`.
- Three directed tests passed through direct invocation. The project `.venv`
  does not contain pytest, so no dependency was installed and the same test
  functions were executed directly with `PYTHONDONTWRITEBYTECODE=1`.

Independent read receipt:
`.agents/task_records/20260727_dequant_node0077_full_v6_e5_package_read_receipt.json`.
