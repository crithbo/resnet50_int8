---
name: resnet50-server-package-flow
description: Orchestrate ResNet50 INT8 family-task routing, server-package generation, final-ZIP auditing, formal-return analysis, and incident maintenance using current owner/build registries and fail-closed hard gates. Use whenever Codex dispatches work to a registered family owner, creates or changes a package/runner/observer/optional TB VCD/return/successor, analyzes a formal return, or reviews a package incident. Do not use it to authorize server runs, functional RTL changes, or numeric/config changes.
---

# ResNet50 Server Package Flow

Use this Skill as a thin workflow over current project rules and machine gates. Never copy stable rule semantics into the Skill. When a registry, rule, and Skill disagree, stop and use the registry-bound rule and validator.

## Establish the current control plane

1. Read completely and record path, bytes, SHA-256, reason, and read time for:
   - `.agents/agent.md`
   - `.agents/plan.md`
   - `.agents/rules/生成前必读索引.md`
   - `contracts/active_rule_registry_v1.json`
   - `contracts/server_package_build_gate_registry_v1.json`
2. Resolve the current role and owner from `contracts/current_session_owner_registry_v1.json` when present.
3. Read only the role row and changed-surface rules selected by the index. For package work this always includes `.agents/rules/服务器测试包生成规则.md` and the actual server-entry README.
4. Do not read `.agents/history/rules/` unless the task explicitly needs provenance. Historical text never authorizes generation or release.

## Route registered family work

1. Resolve the target `role_id`, unique active `thread_id`, `owner_epoch`, and `registry_epoch` from `contracts/current_session_owner_registry_v1.json` immediately before dispatch.
2. Send the task to that exact persistent task with the Codex thread-message tool and record `dispatch_mechanism=PERSISTENT_REGISTERED_THREAD`. Never spawn a subagent or temporary child task to perform, resume, or replace a registered family role. A subagent may only perform a bounded read-only shared audit that owns no family artifact and cannot return a family completion receipt.
3. Bind the dispatch to one explicit diagnostic mode. User or current-plan selection overrides the selector's default. Never infer observer-only merely because it is the default when the current dispatch selects TB VCD.
4. Materialize a `server-family-dispatch-mode-binding-v1` receipt before family work begins. It must bind the registered owner, persistent-thread mechanism, package identity, diagnostic mode, authority receipt, selector-dispatch identity, and `NEXT_FRESH_AFTER_ACTIVATION` boundary.
5. Require the family to package that binding byte-for-byte with `contracts/server_diagnostic_mode_selector.json`. Reject a final ZIP when the binding, selector, manifest, owner registry, or expected mode disagree.

## Choose one workflow

### Build or modify a package

1. Freeze target family, package identity, input/config/workload/RTL identities, selected diagnostic mode, changed surface, authorization boundary, and exact family-dispatch binding. Missing dispatch binding or mode authority is blocking; do not fall back to a default.
2. Compile a build profile from the current gate registry. Every disposition must be exactly one of:
   - `blocking_applicable`
   - `receipt_reuse`
   - `record_only`
   - `not_applicable`
3. A blocking item must map to at least one causal class:
   - `server_start`
   - `actual_input`
   - `state_safety`
   - `return`
   If it cannot, downgrade it to `record_only`.
4. Run one aggregate cheap-check pass before expensive materialization. Report all findings together; do not rebuild after each error.
5. Materialize once, freeze the staging tree, then run the staging aggregate gate once.
6. Create the final ZIP once. Run the registry-selected top-level final-ZIP gate once against a clean exact extraction.
7. If the rule epoch requires first-fresh audit, run it against that same exact ZIP. Do not substitute builder or staging receipts.
8. Run `tools/validate_server_family_dispatch_mode_binding.py` against the exact final ZIP and current dispatch-time registry/authority receipts. This gate is required only for next-fresh packages after its activation and is not retroactive.
9. Rotate storage only after all required gates pass. Do not upload, lease, or run a server unless the user explicitly authorizes it.

### Analyze a formal return and design a successor

1. Bind the exact source package, execution identity, return ZIP, internal manifest, and selected diagnostic mode.
2. State the last proven stage and first divergence before interpreting a root cause.
3. Distinguish compile failure, simulation not started, target not reached, useful boundary progress, natural terminal, formal D, and E4/E5.
4. Use the source-bound actual consumer and actual compiled RTL driver cone. Do not treat an observer-recomputed equation as the DUT signal.
5. Build one candidate-by-boundary matrix and include all low-cost observations that can distinguish open candidates in one successor.
6. Stop scanning large evidence once a unique root cause is proven. Otherwise use streaming checkpoints and bounded summaries; never load a full large VCD/ZIP/JSONL into model context.
7. Preserve the claim boundary. A diagnostic partial return cannot claim natural terminal, formal D, or E4/E5.

### Review an incident that may affect rules

1. Read the current unique semantic owner and its exact machine implementation before proposing text.
2. Produce a `rule-maintenance-incident-adjudication-v1` document using `schemas/rule_maintenance_incident_adjudication_v1.schema.json`.
3. Select exactly one primary class:
   - `RULE_SEMANTIC_ERROR`: replace, narrow, delete, or archive wrong semantics.
   - `RULE_SEMANTIC_OMISSION`: merge the missing non-synonymous semantic into the unique owner.
   - `IMPLEMENTATION_ESCAPE`: keep public semantics and repair generator/validator/schema/tests.
   - `SESSION_EXECUTION_NONCOMPLIANCE`: repair this Skill, handoff, or invocation; add a hard gate only with a causal blocking class and actual consumer.
   - `ONE_OFF_OR_DOMAIN_FAILURE`: keep the shared rule and gate unchanged; route the fix to the owning family or environment.
4. Run `tools/validate_rule_maintenance_incident_adjudication.py`.
5. Never choose append-only maintenance. List preserved, replaced, merged, deleted, and archived sections. Add no synonymous public rule ID.

## Preserve non-negotiable boundaries

- Do not weaken legal workload provenance, runtime-D absent, DUT natural terminal, formal-D conjunction, E4/E5, actual-input identity, or functional RTL authorization.
- Do not preflight arbitrary server file/tool/provider existence. Locally validate package-owned bytes; on the server run the production command and return the compile/sim core on failure.
- Keep observer-only as the fallback only when the current dispatch is silent and current plan/user authority does not select another mode. Use package-local TB causal-cone VCD whenever the current dispatch selects it; the default can never override a bound campaign/package decision. Do not restore VPD, FSDB, UCLI direct-VCD, or vendor query paths.
- Do not mutate current/tested packages or original returns. Use fresh successor identity and repeat-safe exact-owned runtime reset.
- Do not modify `.agents/plan.md`, public rules, another family, functional RTL, or server state without explicit scope and authorization.

## Return a machine-verifiable handoff

Report:

- previous proven progress and current purpose;
- exact package/return identity and selected gate epoch;
- changed, frozen, and reused surfaces;
- aggregate gate results and any `record_only` warnings;
- `LAST_PROVEN_GOOD`, `FIRST_DIVERGENCE`, candidate matrix, and blocker delta when analyzing a return;
- `RULE_CONFIRMATION` or a validated incident adjudication when rule maintenance is considered;
- claim boundary and explicit absence of unauthorized server/RTL/config/numeric actions.

Notify the current mainline resolved from the owner registry; historical thread IDs are provenance only.
