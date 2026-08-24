# Workspace lifecycle batch-1 purge and rule delta

Date: 2026-08-24
Role: `optimizer.whole-network`, owner epoch 5
Canonical registry epoch: 50

## Previous progress

Phase 1 produced a current-control-plane protected set and dry-run plan. It exposed a rule semantic omission for ordinary workspace lifecycle and an implementation escape because the earlier raw-evidence retention path had no active invocation/index.

## Exact cleanup

Mainline and persistent GAP owner independently confirmed local writer quiescence for eight exact legacy bytecode directories. They bound current GAP owner epoch 7, `gv80`, the managed pending ZIP, 156/156 exclusive opens, zero process references and zero reparse points.

The lifecycle tool moved the exact paths to an out-of-canonical quarantine and verified identical file/directory/byte counts. Canonical active-rule, takeover and storage audits then passed. The verified quarantine was permanently purged:

- directories: 8
- files: 156
- bytes: 2,966,762
- recovery: raw bytecode is no longer recoverable; all source/generators remain

No current pointer, pending package, plan, registry or managed storage changed.

## Rule/tool result

Implemented a narrow merge under existing rule owners, with no new synonymous public rule ID and no final-ZIP gate:

- automatic root `AGENTS.md` points only to `.agents/agent.md`;
- `.tmp/<role>/<task>` and `work/<role-or-family>/<objective>` own new temporary/intermediate output;
- every new generated root requires `WORKSPACE_OBJECT_MANIFEST.json`;
- destructive order is `scan -> exact plan -> writer quiescence -> quarantine -> canonical verify -> purge`;
- cleanup failure cannot revoke an admitted package; it becomes `CLEANUP_PENDING` and only blocks another same-kind materialization or an insufficient-space build;
- post-admission/storage, post-return double-consumption and owner handoff are explicit triggers.

Shared implementation includes the lifecycle tool, three schemas, policy, dispatch and focused tests. The tool supports dry-run, exact quarantine, verification and token-bound permanent purge with rollback on quarantine failure.

## Validation

- focused lifecycle/rule/active-rule/mandatory-read/Skill/takeover/handoff: 50/50 PASS
- active-rule audit: 14/14 active and registered, 103 definitions, duplicate/error/warning 0
- canonical post-quarantine takeover: PASS
- canonical storage: PASS 4/81/25

## Boundary

No family package, storage identity, plan, owner registry, RTL, config, numeric, workload or server action occurred. Canonical narrow sync and final migration handoff remain next.
