# Post-simulation shared return-core rule and gate

Date: 2026-08-09  
Owner: `019fd276-14c5-7800-94db-87ebfb9ce632`  
Mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Outcome

Implemented `CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001` for the next fresh package that may enter simulation. The change addresses the recurring class where simulation has already exited but a family parser, collector wrapper, generated fallback or path binding prevents the normal return ZIP from being published.

The shared helper persists the simulator exit receipt and finalizer state before running any parser/analyzer plugin. Plugins execute independently with bounded stdout/stderr and timeout. A required plugin failure or missing evidence changes the return disposition to `EVIDENCE_INCOMPLETE`, but the minimal core return is still atomically published. Family positional `collect()` wrappers are forbidden.

If ZIP publication itself fails, the attempt tree retains `FAILED_RECOVERABLE_FROM_ATTEMPT_ROOT` and a uniform recovery instruction. The same JSON finalizer request can be rerun after correcting external space or permission problems without rerunning compile or simulation. Re-entering a successfully published package/execution is idempotent and byte-preserving.

## Enforcement

- gate: `post_sim_return_core`
- disposition: `blocking_applicable`
- enforcement: `required_next_fresh`
- causal class: `return`
- pipeline enclosing mode: `SHADOW_ONLY_NEXT_FRESH`
- current/pending/tested package impact: none

Exact final-ZIP validation runs four short, isolated scenarios using the final helper and request: natural success, natural success with required plugin failure, simulation nonzero exit, and idempotent re-entry. These scenarios share the one final-ZIP aggregate and do not cause per-error package rebuilds.

## Validation

- post-sim return unit tests: 12/12 PASS
- combined shared regression: 73/73 PASS
- compiled package pipeline: contract valid
- required gates include `post_sim_return_core=blocking_applicable/required_next_fresh`
- exact mechanical sync: 12/12 files match, mismatch 0
- `git diff --check`: PASS

Machine report: `artifacts/operator_config_validation/r5-server-post-sim-return-core-v1/report.json`, bytes `4652`, SHA256 `4658b69def97625496a1c9c652e5332f34ac509b286cfc2eca2c326f3c816f9a`.

No package, upload, server run, lease, RTL, config, numeric, workload, timeout or `.agents/plan.md` action occurred.
