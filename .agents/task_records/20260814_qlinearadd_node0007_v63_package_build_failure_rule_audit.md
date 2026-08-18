# QLinearAdd v63 package-build-failure rule audit

- role: `family.qlinearadd`, owner epoch 2
- trigger: two server attempts for the same tail-round target did not execute that target because of package-local defects
- disposition: `RULE_DELTA_PROPOSAL`
- authorization boundary: local build/validation/storage only; no upload, lease, connection, or server run

## Attempt audit

1. v59 stopped at package preflight because `manifest.install_name` still named v58 while the package and SCA namespace named v59.
2. v63 compiled successfully and started simulation, but its runtime supervisor stopped a still-progressing preload. The TB converted realtime through 32-bit `$rtoi`, assigned the wrapped value to an unsigned 64-bit heartbeat field, and emitted heartbeats only every 262,144 owner cycles. The three-interval guard therefore asserted `SIM_TIME_FREEZE` while VCD timestamps, owner cycles, and matrix loading still advanced. Buffer5 request decode never occurred.

This is the mandatory audit before a third server attempt. It does not authorize that attempt.

## Non-synonymous rule delta

The fresh family package must implement and negatively test all of these points:

- freeze supervision follows newly appended VCD `#timestamp` records, not the displayed TB integer;
- TB heartbeat time cannot overflow and heartbeat cadence is at most 16,384 owner cycles;
- `$dumpvars` targets are the exact 64 source-bound catalog signals; whole-module depth-0 dumping is rejected;
- legal multiline `$timescale` is locally decoded;
- partial runtime, missing close/flush, or unreaped descendants cannot produce `finalization.pass=true`;
- a required TB-VCD exact-set/no-limit receipt is returned;
- compile/simulation downstream state and the structured supervisor stop are live rather than stale/benign.

The active shared schema cannot express the exact-signal dump strategy and is outside this family owner's schema/rule write scope. The machine-readable audit therefore grants only a QAdd next-fresh family hard-gate delta, bound to `tools/validate_qlinearadd_node0007_v64_tbvcd_failure_delta.py` and its first-fresh negative controls. It expires after the first production return from that successor.

## RULE_GAP_AUDIT disposition

The separate one-round-localization `RULE_GAP_AUDIT` did not trigger: although production compile and simulation started, the diagnostic target itself never executed. The stricter package-build-failure audit above did trigger and is controlling.

The exact supplied return and v63 pending package remain preserved. No server action occurred.
