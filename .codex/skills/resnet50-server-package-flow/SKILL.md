---
name: resnet50-server-package-flow
description: Orchestrate ResNet50 INT8 family routing, patch-first server-package generation, changed-surface gate reuse, formal-return analysis, and incident maintenance. Use whenever Codex dispatches a registered family, builds or patches a package/runner/observer/optional TB VCD/return, analyzes a return, or designs a successor. Do not use it to authorize server runs, functional RTL changes, or numeric/config changes.
---

# ResNet50 Server Package Flow

Use this Skill as a thin workflow over current project rules and machine gates. Never copy stable rule semantics into the Skill. When a registry, rule, and Skill disagree, stop and use the registry-bound rule and validator.

## Establish the current control plane

1. Read completely once per task and record path plus reason for:
   - `.agents/agent.md`
   - `.agents/plan.md`
   - `.agents/rules/生成前必读索引.md`
   - `contracts/active_rule_registry_v1.json`
   - `contracts/server_package_build_gate_registry_v1.json`
2. Resolve the current role and owner from `contracts/current_session_owner_registry_v1.json`; a missing current registry is a takeover blocker. A fresh session/model also runs `tools/validate_project_takeover_readiness.py` before writing.
3. Read only the role row and changed-surface rules selected by the index. For package work this always includes `.agents/rules/服务器测试包生成规则.md` and the actual server-entry README.
4. Do not read `.agents/history/rules/` unless the task explicitly needs provenance. Historical text never authorizes generation or release. File digests are optional provenance unless an actual input consumer explicitly requires them.

## Route registered family work

1. Resolve the target `role_id`, unique active `thread_id`, `owner_epoch`, and `registry_epoch` from `contracts/current_session_owner_registry_v1.json` immediately before dispatch.
2. Send the task to that exact persistent task with the Codex thread-message tool and record `dispatch_mechanism=PERSISTENT_REGISTERED_THREAD`. Never spawn a subagent or temporary child task to perform, resume, or replace a registered family role. A subagent may only perform a bounded read-only shared audit that owns no family artifact and cannot return a family completion receipt.
3. Bind the dispatch to one explicit diagnostic mode. User or current-plan selection overrides the selector's default. New dynamic successors default to `TB_VCD_BOUNDED_CAUSAL_CONE`; use observer-only only when explicitly dispatched.
4. Materialize a `server-family-dispatch-mode-binding-v1` receipt before family work begins. It must bind the registered owner, persistent-thread mechanism, package identity, diagnostic mode, authority receipt, selector-dispatch identity, and `NEXT_FRESH_AFTER_ACTIVATION` boundary.
5. Require the family to package that binding byte-for-byte with `contracts/server_diagnostic_mode_selector.json`. Reject a final ZIP when the binding, selector, manifest, owner registry, or expected mode disagree.

## Choose one workflow

### Build or modify a package

1. Freeze target family, package identity, input/config/workload/RTL identities, selected diagnostic mode, changed surface, authorization boundary, and exact family-dispatch binding. Missing dispatch binding or mode authority is blocking; do not fall back to a default.
2. Compile the active build profile once with `python tools/server_package_pipeline.py prepare --spec <spec.json> --output <profile.json>`. Every disposition must be exactly one of:
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
4. If the current package has not run, prefer a patched revision of its staging/package source. Preserve unchanged config/mapping/bitstream/execplan/SCA/workload; use a fresh successor after execution or return binding.
5. Run one aggregate cheap-check pass. Fix all findings together, then rerun only gates whose direct consumed surfaces changed; reuse unaffected PASS receipts.
6. Create or repack the final ZIP once after fixes. Run the registry-selected top-level final-ZIP gate once; do not rebuild once per finding.
7. If a first-use audit applies, test the new or changed gate against that same final ZIP; do not rerun unrelated historical gates.
8. Run `tools/validate_server_family_dispatch_mode_binding.py` against the exact final ZIP and current dispatch-time registry/authority receipts. This gate is required only for next-fresh packages after its activation and is not retroactive.
9. Aggregate the required gate results and run `python tools/server_package_pipeline.py admit --profile <profile.json> --gate-results <results.json> --zip <candidate.zip> --output <admission.json>`. Only `PACKAGE_READY_NOT_RUN` may enter pending; record-only failures remain warnings.
10. Rotate storage only after admission. Do not upload, lease, or run a server unless the user explicitly authorizes it. SHA/bytes are cache/provenance only unless an actual consumer explicitly requires them.
11. Enforce the single-ZIP return policy for every next-round package: the formal server return is exactly one ZIP; all SHA-256/digest/manifest attachments must be inside the ZIP (e.g. `RETURN_DIGESTS.json`, `RETURN_CORE_MANIFEST.json`); never publish an adjacent `.sha256` or other sidecar next to the return ZIP.
12. For a new dynamic successor, default to the most one-round-discriminative diagnostic form (`TB_VCD_BOUNDED_CAUSAL_CONE`); use `OBSERVER_ONLY_WIDE_CAUSAL` only when explicitly dispatched. The candidate×boundary matrix must pairwise distinguish every open candidate before release.
13. After admission plus storage rotation, register the local output root and run the active workspace-lifecycle
    post-admission plan. Delete nothing before the canonical package exists. Cleanup failure never revokes the
    admitted package; record `CLEANUP_PENDING` and do not start another same-kind local materialization when the
    cleanup set or projected free-space boundary remains unsafe.

### Analyze a formal return and design a successor

1. Bind the exact source package, execution identity, return ZIP, internal manifest, and selected diagnostic mode.
2. State the last proven stage and first divergence before interpreting a root cause.
3. Distinguish compile failure, simulation not started, target not reached, useful boundary progress, natural terminal, formal D, and E4/E5.
4. Use the source-bound actual consumer and actual compiled RTL driver cone. Do not treat an observer-recomputed equation as the DUT signal.
5. Build one candidate-by-boundary matrix and include all low-cost observations that can distinguish open candidates in one successor.
6. Stop scanning large evidence once a unique root cause is proven. Otherwise use streaming checkpoints and bounded summaries; never load a full large VCD/ZIP/JSONL into model context.
7. Preserve the claim boundary. A diagnostic partial return cannot claim natural terminal, formal D, or E4/E5.
8. After both family and mainline consume the return, run the active retention/lifecycle plan. Preserve
   MAX_PROGRESS, LATEST_1, LATEST_2, current blocker anchors and small core reports before retiring heavy raw or
   extracted copies.

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
6. For workspace growth incidents, require `scan -> exact plan -> writer quiescence -> quarantine -> canonical
   verify -> purge`. Unknown, inaccessible or reparse paths fail protected. Do not add cleanup to the final-ZIP
   blocking allowlist; lifecycle is a post-transition/control-plane workflow.

## Preserve non-negotiable boundaries

- Do not weaken legal workload provenance, runtime-D absent, DUT natural terminal, formal-D conjunction, E4/E5, actual-input identity, or functional RTL authorization.
- Do not preflight arbitrary server file/tool/provider existence. Locally validate package-owned bytes; on the server run the production command and return the compile/sim core on failure.
- Never change the mode of a current ready package. For a future new dynamic successor with no contrary user/plan binding, select package-local TB causal-cone VCD; use observer-only when explicitly dispatched. The default can never override a bound campaign/package decision. Do not restore VPD, FSDB, UCLI direct-VCD, or vendor query paths.
- Do not mutate tested packages or original returns. Unrun local/pending packages are patch-first; executed packages use a fresh successor. Keep repeat-safe exact-owned runtime reset.
- Never publish a formal return as anything other than a single ZIP. All SHA-256/digest/manifest attachments must live inside that ZIP; an adjacent sidecar is forbidden.
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
Before owner handoff or task closure, include the workspace-object manifest and cleanup receipt or an explicit
`CLEANUP_PENDING` reason. Do not hide cleanup debt by creating a new output root.
