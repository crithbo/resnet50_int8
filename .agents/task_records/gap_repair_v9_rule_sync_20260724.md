# GAP repair_v9 规则同步记录

状态：已同步 repair candidate 可复用规则；未修改本地功能 RTL preimage。

新增规则资产：

- `.agents/rules/GAP_repair_candidate_rules.md`

新增规则 ID：

- `CDA-CONFIG-FULL-REBUILD-PROVENANCE-001`
- `CDA-RTL-REPAIR-TRANSACTIONAL-RESTORE-001`
- `CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001`
- `CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001`
- `CDA-GAP-REPAIR-RETURN-RECEIPTS-001`

继续强制引用的既有规则：

- `CDA-GAP-ORTHOGONAL-DEFECTS-001`
- `CDA-GAP-D-READBACK-COVERAGE-001`
- `CDA-GA-OUTBUFFER-OCCUPANCY-001`
- `CDA-GA-INVALID-SLOT-ISOLATION-001`
- `CDA-GA-CROSS-BLOCK-INIT-001`
- `CDA-MSE4-MONITOR-EVIDENCE-001`
- `CDA-SERVER-FOCUSED-IDENTITY-001`

候选身份：

- `artifacts/operator_config_validation/r5-server-test-packages/gap_hwop0071_sum_repair_v9.zip`
- ZIP SHA-256：
  `4344b4166540482d12256b1a5893b8e3dbb512a74a7d735237de0ae2bf873864`
- `artifacts/operator_config_validation/r5-gap-repair-release-v9/GAP_REPAIR_RELEASE_GATE.json`
- 当前声明严格保持 `candidate_release=false`、`E2_LOCAL_ONLY`。

核验结果：

- ZIP 重新计算 SHA-256 与 sidecar 完全一致。
- 两个本地 `NDP_copy01` RTL preimage 的逐文件 SHA-256 与包 manifest 一致，
  本次规则同步未修改它们。
- `tools/validate_gap_repair_test_package.py` 通过：124 个 payload file、125 个
  ZIP entry、exact file set、RTL allowlist 为 2 个文件。
- `tests.test_gap_repair_release`、`tests.test_gap_repair_workload`、
  `tests.test_build_gap_repair_test_package` 共 8 项测试通过。
