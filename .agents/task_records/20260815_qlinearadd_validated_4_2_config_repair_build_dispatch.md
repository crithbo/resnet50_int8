# QLinearAdd validated 4/2 config repair build dispatch

- role: `family.qlinearadd`
- user authorization: explicit local fresh-package rebuild using the validated configuration repair
- root: `QADD_TAIL_ROUND_STALE_CONFIG_LINEAGE_REINTRODUCES_INTERLEAVED_COLUMN_ALIAS`
- predecessor: `r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3`（保留只读，禁止运行）
- state: `BUILD_IN_PROGRESS`

Authorized functional delta is limited to `GROUP2.COL_LC end/stride: 32/16 -> 4/2`, with exact JSON→encoder→bitstream→SCA/SCA_D→manifest regeneration and identity binding. The old `a3094e...` lineage must be rejected; the historical validated correction is `a7d42a...`, subject to fresh deterministic identity proof.

All other config fields, numeric, workload, golden and functional RTL remain frozen. The fresh diagnostic surface must require ordered `0x33333333` then `0xcccccccc` requests, both accept/clear, no repeated first-half alias, and downstream output/terminal/formal-D evidence. The `32/16` restoration remains a fail-closed negative control.

Authorization is local build only. No storage rotation until a separate mainline single-writer release; no upload, lease, connection or server run.
