# Family dispatch/mode binding and Skill activation ready

Date: 2026-08-18

## Decision

Current packages are frozen. This change is `REQUIRED_NEXT_FRESH_AFTER_ACTIVATION_ONLY`; it must not hold, rebuild, mutate or rotate serialized v102, QAdd v73, or any other package already current/in progress.

The audit found no deleted VCD rule. The existing semantic owner still preserves observer-only and optional TB VCD, while current plan selects `TB_VCD_BOUNDED_CAUSAL_CONE` for the four families' next fresh packages. Two implementation gaps caused the apparent forgetting:

1. `resnet50-server-package-flow` existed only in the optimizer worktree, not in canonical project or personal Skill discovery paths.
2. No exact-final-ZIP gate bound the registered persistent owner and dispatch-time diagnostic mode to the selector and manifest. Temporary child/subagent family routing was therefore not machine-rejected.

Classification: primary `IMPLEMENTATION_ESCAPE`, secondary `SESSION_EXECUTION_NONCOMPLIANCE`; `public_rule_change=NONE`.

## Implemented next-fresh surface

- Updated the Skill to resolve the current owner registry, require `PERSISTENT_REGISTERED_THREAD`, forbid temporary subagent replacement of registered family roles, and bind the user/plan/task-selected mode before work begins.
- Added `server-family-dispatch-mode-binding-v1` schema, dispatch contract and fail-closed validator.
- The validator binds the upstream user/plan/task record through a machine-readable authority receipt, checks registry/mainline/family epochs and threads, and requires byte-equal binding plus selector/manifest agreement in both staging tree and exact final ZIP.
- Refreshed three stale observer frozen-asset receipts in the existing diagnostic selector dispatch; no observer/VCD semantic changed.
- Added positive/negative tests for VCD/observer authority, owner/issuer drift, subagent substitution, missing/renamed/drifted bindings, registry/source drift and non-retroactive scope.

## Validation

- New focused tests: 10/10 PASS.
- Combined binding/selector/handoff/first-fresh/pipeline suite: 56/56 PASS.
- Python compile: PASS.
- Skill Creator quick validation: `Skill is valid!`.
- Incident adjudication validation: PASS, errors 0.

Machine report: `outputs/family_dispatch_mode_binding_v1/report.json`.

## Canonical handoff

Mainline must mechanically sync the exact asset set, install the project-local Skill, add `family_dispatch_mode_binding_final_zip` to the current build-gate registry, and narrowly require Skill invocation/persistent-owner messaging in the existing handoff workflow. Do not introduce a synonymous public rule. Activation is future-only.

No current package, plan, public rule, functional RTL, config, numeric/workload asset, storage or server state was modified by this implementation.
