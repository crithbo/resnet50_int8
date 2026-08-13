# Server test package storage rotation migration

Date: 2026-08-06

Mainline task: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## User decision

After every fresh server package release, the pending-package location must
retain at most one latest package for each operator family. Older packages
must leave the pickup location.

To avoid falsely calling an unrun intermediate package "tested", the store
uses three dispositions:

```text
pending/<family>/<package-id>/
tested/<family>/<package-id>/
superseded/<family>/<package-id>/
```

`tested` requires a consumed formal return. Unrun, intermediate, quarantined,
preflight-failed, or otherwise replaced packages use `superseded`.

## Migration result

All 67 ZIP packages and their package-derived artifact sets were moved inside
the same workspace package root without deletion or overwrite:

- pending: `4`
- tested: `40`
- superseded: `23`
- flat root ZIPs after migration: `0`
- total ZIPs after migration: `67`

The four pending families each have exactly one package:

1. `gap_node0071`:
   `r5_n71_gap_v40_lc_supply_conservation_diag`
2. `conv_serialized_node0004`:
   `r5_n4_hw_v49_lc9_actual_compilefix`
3. `qlinearadd_node0007`:
   `r5_qadd_n7_cout32_v36`
4. `conv_native_four_lane`:
   `r5_n4_0cc_p9b_tx5`

QLinearMatMul v9 has a consumed return and was moved to `tested`; it must not
be repeated while the family waits for GAP v40.

## Rule delta

Published rule:

`CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`

Rule behavior:

- `pending` is the only normal user pickup location;
- one current package maximum per family;
- the previous pending package must be classified with readable evidence as
  `tested` or `superseded` before the new package is installed;
- ZIPs, sidecars, validation/audit receipts, reports, and task records are
  never deleted or overwritten;
- storage rotation updates `PACKAGE_STORAGE_INDEX.json`;
- release notifications and current plan links point to `pending/...`.

## Exact receipts

Storage index:

`artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`

- bytes: `59439`
- SHA256:
  `50f0260fdd4304aa85abe5851d715c16061a110e2eab271de8e2158f84942d1a`

Migration manifest:

`contracts/server_test_package_storage_migration_v1.json`

- bytes: `13235`
- SHA256:
  `21eaf149714df8ae6912caf55db4cd0b3b30b7d85589c338dd6a266dc4b818ef`

Storage tool:

`tools/manage_server_test_package_storage.py`

- bytes: `16132`
- SHA256:
  `5fe86fe77ad2cf4f3e83f9258b523e392a35d40fecf10d8e9d090d52b76a7921`

Tests:

`tests/test_manage_server_test_package_storage.py`

- bytes: `7056`
- SHA256:
  `64cb526d16fbc0195c27d5438a4eb2af4448c069e19b1185b6f8158e52fd1925`

Server-package rule:

`.agents/rules/服务器测试包生成规则.md`

- bytes: `84873`
- SHA256:
  `dc9c3d3ef2a235fe3eb0d91fe0655377ebfc09629d86a551fa39915e162765c7`

Generation index:

`.agents/rules/生成前必读索引.md`

- bytes: `13789`
- SHA256:
  `be063b6e4281c89c3777e4373ca3d2972c364f90d1a66f45c96762c8a8c91097`

## Validation

- migration manifest package count/root ZIP count before move: `67/67`
- duplicate package bases: `0`
- `pending` one-per-family: `PASS`
- ZIP/sidecar verification for all 67 packages: `PASS`
- post-migration storage audit: `PASS`
- unit tests: `5/5 PASS`
- `py_compile`: `PASS`
- `git diff --check`: `PASS`

Negative controls cover:

- two pending packages for one family;
- sidecar mismatch;
- flat root package after migration;
- rotation without the required previous-package evidence;
- successful evidence-bound previous-package archive and new-package promotion.

## Claim boundary

This operation only changed local package storage paths and added a
non-destructive rotation rule/tool. Package bytes, sidecars, package-internal
identities, server commands, expected return names, functional RTL, ISA,
hardware, active ndp-sim, configuration, workload, golden, and E3/E4/E5
claims were not changed.

