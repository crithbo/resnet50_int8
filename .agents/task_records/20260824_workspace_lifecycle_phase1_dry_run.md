# Workspace lifecycle phase-1 dry-run

Date: 2026-08-24
Role: `optimizer.whole-network` owner epoch 5
Canonical registry epoch: 50

## Previous progress

The server rule limited registered heavy raw evidence to three groups, but no active retention index or invocation existed. Ordinary build, extraction, cache, failed-attempt and managed archive lifecycle was not covered.

## Current result

Implemented a strictly non-destructive `scan-plan` surface:

- `tools/manage_workspace_lifecycle.py`
- `schemas/workspace_lifecycle_v1.schema.json`
- `contracts/workspace_lifecycle_policy_v1.json`
- `tests/test_workspace_lifecycle.py`

The CLI has no apply, move or delete action. It reads the canonical owner registry, plan, task-record references, managed storage index and Git tracked set; it never follows symlinks and treats access failures as protected.

Canonical dry-run observed 94,709 visible files and 21,897,615,229 visible bytes. This is a lower bound because 69 paths were inaccessible. It derived 8,532 protected entries, 129 candidates and 310 unknown legacy output roots. Only 8 tiny ephemeral candidates are immediately eligible for quarantine review; 2 repeat ZIPs require one apply-time identity confirmation; 32 derived trees require canonical-anchor review. No file was changed.

## Validation

- `py_compile`: PASS
- focused lifecycle tests: 8/8 PASS
- four generated reports against `workspace_lifecycle_v1.schema.json`: 4/4 PASS
- canonical takeover readiness: PASS

## Classification

Primary `RULE_SEMANTIC_OMISSION`, secondary `IMPLEMENTATION_ESCAPE`. A validated incident adjudication is stored at `outputs/workspace_lifecycle_v1/incident_adjudication.json`.

## Boundary

No canonical file was moved, deleted, overwritten or modified. No package, storage, plan, owner registry, RTL, config, numeric, workload or server action occurred. Destructive work remains stopped at the explicit quarantine-plan checkpoint.
