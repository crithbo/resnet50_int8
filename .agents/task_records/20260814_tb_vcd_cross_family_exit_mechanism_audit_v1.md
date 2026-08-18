# TB-VCD cross-family exit mechanism audit v1

Date: 2026-08-14  
Role: `optimizer.whole-network`  
Status: `CURRENT_DISK_TB_VCD_EXIT_MECHANISM_DELTA_READY`

## Mandatory-read receipts

- `.agents/agent.md`: `7a6fe116109b2c7953f3e1ff223160801e1d4df4ac6bfffc394c5ce4598294e4`
- `.agents/rules/生成前必读索引.md`: `c78675c39387df924807feed5022ba6c3f50716b9e041b91504974d61fd79c8e`
- `.agents/rules/服务器测试包生成规则.md`: `beccd3fed2d9892a51ad928fa80443d58f6e4b619bf03bfcb5da3db428b2ea97`
- `.agents/rules/整网测试收敛优化专项规则.md`: `b2b81017865162a161f2b1610588d36032d2b4aa60a5f659f964f2fa2ea9af37`
- `.agents/plan.md` mutable provenance: `fdf61ede9b62219efd389d1df0242dfbebb0cdd37dc1ccee5318cb07e833306a`

No public rule, plan, owner registry, family package, RTL, config, numeric or workload file was changed.

## Exact returns

- serialized v93d: bytes 182946578, SHA-256 `1ff059a6f23ca2dc2460956b04c81d636bfa3d2df14ca8be46fba591ac46421d`.
- native p48: bytes 6504753, SHA-256 `a9bf1c85c827985b30461727c4f0371fea1f1d9fff71dcf43eca599054e4e0e3`.
- GAP v63: bytes 1347117, SHA-256 `448185224f4806f251b19a09847328586fefc73e5819570acb40674d8acd842c`.

All were current packages left unchanged when `package-release-admission-and-tbvcd-runtime-v2` activated next-fresh only; the audit does not treat them as executions of v2.

## Cross-family result

The suspicion that two packages shared QAdd v63's failure class is correct:

- native p48 = `A_QADD_V63_CLASS_FALSE_FREEZE`. Its supervisor/runtime timestamp remained 0 while the archived VCD reached 303783125. The returned VCD had 871 declarations versus the 66-signal catalog, so module-scope over-dump also amplified runtime cost. Final status remained partial, but the process tree was not fully reaped.
- GAP v63 = `A_QADD_V63_CLASS_FALSE_FREEZE`. Its supervisor stopped at 102000 while the archived VCD reached 465335625. Its 1910 VCD declarations equal its 1910-signal catalog; this is a very broad catalog, not an undeclared extra-scope mismatch. Finalization incorrectly said pass while runtime was incomplete and the process tree remained unreaped.
- serialized v93d = `B_DIFFERENT_SHARED_SUPERVISOR_DEFECT`. It did not freeze. The outer runner declared `CAUSAL_PLATEAU` after only 1409024 no-progress cycles, below the required 4194304 dump-off plus 262144 grace total of 4456448. The shared evaluator therefore reported `NONZERO_EXIT`, no dump-off cycle and partial evidence. Its VCD catalog and declarations were exact 54/54. The process tree remained unreaped.

Counts: A=2, B=1, C=0, D=0, E=0. No signal-level or functional family root is claimed.

## Shared gap and delta

There is a real shared implementation gap under the existing optional-VCD public rule ID, but no reason for a new synonymous rule ID:

1. the field named appended timestamp was trusted without independently binding it to the quiescent archived VCD;
2. an outer runner could duplicate and drift from shared plateau/freeze thresholds;
3. first-fresh controls did not execute the four decisive decisions through the exact packaged helper/runner handoff.

The shared v3 delta makes the shared evaluator receipt the sole decision authority, requires exact packaged replay of advancing timestamp / suspected-only plateau / full plateau / true freeze, and binds the quiescent VCD SHA, bytes and last timestamp to the final runtime timestamp. Incomplete or unreaped runtime cannot pass finalization.

The cheapest implementation is to fuse last-timestamp extraction with the existing VCD SHA pass. It adds no extra full-file pass. The exact four-case replay costs only local build seconds and adds no DUT simulation overhead. Consolidating the outer runner onto the shared evaluator is a low-to-medium code change with negligible runtime cost and the largest cross-family benefit.

## Validation and activation

- Focused tests: 39/39 PASS.
- Broader related tests: 140/140 PASS.
- `py_compile`: PASS.
- JSON parse: PASS.
- Three exact ZIP/VCD streaming scans: PASS.
- Synthetic v3 contract and natural runtime: PASS / `DIAGNOSTIC_EVIDENCE_COMPLETE`.

Proposed activation is `tb-vcd-exit-mechanism-consistency-v3`, next-fresh optional-VCD packages only after canonical sync. Current packages/returns are not held or rebuilt; observer-only remains unchanged; no server action is authorized.

Machine identities and exact changed set are recorded in `outputs/tb_vcd_cross_family_exit_audit_v1/report.json`.

