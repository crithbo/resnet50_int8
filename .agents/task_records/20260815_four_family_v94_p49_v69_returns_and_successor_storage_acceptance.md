# 四族 TB-VCD return 与 successor 存储验收（2026-08-15）

## 主线裁决

- `family.conv.native`：p49 production compile/simulation/target entry 已成立；动态边界收敛到 RD-buffer dequeue 与 prepared-data/metadata/output join，仍为 `OPEN_UNVALIDATED_MECHANISM`。p49 已归 `tested`，fresh `r5_n4_0cc_p50_rdbufdrain` 为唯一 native pending。
- `family.gap`：v69 production compile/simulation/sum_s2 entry 已成立；动态边界为 selected Buffer0 MRM ready 持续低、alternate branch ready 高，仍缺地址/数据 FIFO 与 MRM direct leaves，故不作配置绕行。v69 已归 `tested`，fresh `r5_n71_gap_v70_sum_s2_tbvcd_mrmcone` 为唯一 GAP pending。
- `family.conv.serialized`：v94b production compile/simulation/target entry 已成立；直接证明五组 prepared-data 仅对应三组 WR metadata，排除 output/memory downstream backpressure，剩余 metadata lifetime 少两组或 data lifetime 多两组。v94b 已归 `tested`，fresh `r5_n4_hw_v95b_tbvcd_metapair` 为唯一 serialized pending。
- `family.qlinearadd`：v64 已归 `tested`，v65 为物理/索引唯一 QAdd pending，但后续 config/RTL/dynamic 复审已形成 `VALIDATED_ROOT_CAUSE=QADD_TAIL_ROUND_STALE_CONFIG_LINEAGE_REINTRODUCES_INTERLEAVED_COLUMN_ALIAS`。v65 仍绑定已证错误的 `GROUP2.COL_LC end/stride=32/16`，不得运行；等待用户明确授权后按已验证 `4/2` lineage 构建 fresh 修复包。

## 当前唯一 pending exact set

- native: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p50_rdbufdrain.zip`, bytes `5906571`, SHA-256 `ad0e75a3c9202344272f6fdd9d22aafadeeca8a9e36a73e0fdcee0b53cd5af32`.
- GAP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v70_sum_s2_tbvcd_mrmcone.zip`, bytes `2121343`, SHA-256 `80cbcd6ad938cccfb1d039a86d11b09cbc32ff0e9b7c919cca0d2d1e4572cb1a`.
- serialized: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v95b_tbvcd_metapair.zip`, bytes `5201145`, SHA-256 `120e7a019ac7b524437c11a67a6076e6c1816f919e1a7e5151719ce9dc462b84`.
- QAdd: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3.zip`, bytes `108641052`, SHA-256 `ed204d677bd379f30aba96c2a3d4c228a646dd8c885a9b07ebe545278948c800`; `HOLD_VALIDATED_CONFIG_LINEAGE_ROOT_REPAIR_REQUIRES_EXPLICIT_BUILD_OR_CONFIG_AUTHORIZATION`.

## 存储与权限边界

- `PACKAGE_STORAGE_INDEX.json` corrected audit `pass=true`; pending/tested/superseded=`4/43/23`; bytes `335964`; SHA-256 `251103294bd7ea11b56e0e775b0c98483fbab583224552ac663807a52ee9dba4`.
- 四次 family storage lifecycle 已串行完成，所有 storage writes 已停止，没有跨族覆盖。
- 当前没有 upload/run/lease/server authorization；p50/v70/v95 只为 `PACKAGE_READY_NOT_RUN`。QAdd v65 明确禁止运行。
- 未修改 functional RTL/config/numeric/workload/golden；QAdd `4/2` 修复包尚未获得用户授权，未构建。
