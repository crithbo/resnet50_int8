# GAP/QAdd package-build failure shared-rule audit v1

Date: 2026-08-14  
Role: `optimizer.whole-network`  
Status: `CURRENT_DISK_SHARED_RULE_AUDIT_READY`

## Mandatory-read receipts

- `.agents/agent.md`: SHA-256 `7a6fe116109b2c7953f3e1ff223160801e1d4df4ac6bfffc394c5ce4598294e4`
- `.agents/rules/生成前必读索引.md`: SHA-256 `c78675c39387df924807feed5022ba6c3f50716b9e041b91504974d61fd79c8e`
- `.agents/rules/服务器测试包生成规则.md`: SHA-256 `beccd3fed2d9892a51ad928fa80443d58f6e4b619bf03bfcb5da3db428b2ea97`
- `.agents/rules/整网测试收敛优化专项规则.md`: SHA-256 `b2b81017865162a161f2b1610588d36032d2b4aa60a5f659f964f2fa2ea9af37`
- `.agents/plan.md` mutable provenance: SHA-256 `fdf61ede9b62219efd389d1df0242dfbebb0cdd37dc1ccee5318cb07e833306a`

No public rule, plan or owner-registry file was modified in this worktree.

## Inputs

- GAP audit: canonical `outputs/gap_node0071_v63_sum_s2_tbvcd_preflightfix/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json`, bytes 3031, SHA-256 `9272142175c3fd9feabca0b27c3efd400b519a28151c41aed418b754d5150c9e`.
- QAdd audit: canonical `outputs/qlinearadd_node0007_v63_return_r1786698111383862725_2250595/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json`, bytes 3626, SHA-256 `bbb5dd16c6e1ad3633ac5de568786cfa05be0bbdbeb997172378136736b8a9c4`.

## Adjudication

### GAP

The GAP failure is an existing-rule implementation escape, not a new semantic rule gap. Existing final-ZIP self-audit, runner-preflight positive-control and compilefail-core rules already require the necessary causal protections. The shared implementation now:

1. runs the package-specific preflight after manifest promotion on final staging;
2. repeats it on a clean exact-ZIP extraction;
3. requires the real pending-status negative to fail with `package claim boundary differs`;
4. types positive assertions separately from negative observations;
5. retains preflight stdout/stderr/exit in a compile-not-started core.

The current GAP v63 scoped control report proves both staging and exact-ZIP preflight PASS and the real pending negative fail-closed. It remains valid `PACKAGE_READY_NOT_RUN` before shared activation; no rebuild or hold is requested. Its earlier stale build receipt is record-only and superseded by the final conjunction/release identity.

### QAdd

The QAdd findings are split precisely:

- Non-synonymous narrowing under the existing optional-VCD rule ID: authoritative appended-VCD timestamp supervision; unsigned width >=64 heartbeat at 16384 owner cycles; exact source-bound catalog `$dumpvars` targeting with module/aggregate over-dump forbidden.
- Existing-rule implementation escapes: target claim without target entry; legal multiline `$timescale` rejection; partial/unflushed/unreaped runtime passing finalization; absent exact-set/no-hard-limit conjunction; stale downstream/first-error evidence; missing realistic negative controls.

No synonymous public rule ID is proposed. Exact-signal targeting is accepted as shared schema/gate semantics only for `TB_VCD_BOUNDED_CAUSAL_CONE`; observer-only remains the default and unchanged. QAdd v64 remains frozen and is not rebuilt or mutated by this audit.

## Shared implementation

Machine-readable asset identities and the item-by-item classification are in:

- `contracts/server_package_release_admission_dispatch_v1.json`
- `contracts/server_tb_vcd_qadd_v63_rule_audit_dispatch_v2.json`
- `outputs/gap_qadd_package_build_failure_shared_rule_audit_v1/report.json`

Permanent controls cover the real GAP pending-manifest contradiction, typed polarity, precompile evidence retention, exact dump targeting, display-versus-appended timestamp divergence, timestamp regression, invalid heartbeat width/cadence, legal multiline timescale, exact-set/no-limit failure, missing target entry, stale live-state evidence, unflushed VCD and unreaped descendants.

## Validation

- Focused shared regression: 41/41 PASS.
- Broader related release/preflight/pipeline/return/VCD regression: 132/132 PASS.
- `py_compile`: PASS.
- JSON parse: PASS.
- Synthetic exact-catalog VCD contract: PASS.
- Synthetic natural runtime receipt: `DIAGNOSTIC_EVIDENCE_COMPLETE`.

## Activation and boundary

Proposed activation: `package-release-admission-and-tbvcd-runtime-v2`, next-fresh only after mainline narrow sync. Do not retrospectively hold or rebuild GAP v63 or QAdd v64. No family package, server action, functional RTL, config, numeric payload, workload, plan or registry was changed. No production compile/simulation, target execution, natural terminal, formal D, E3, E4 or E5 is claimed.
