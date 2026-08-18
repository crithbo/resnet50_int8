# Observer guard process-identity v3 canonical activation

The canonical observer operational guard now enumerates processes directly from procfs without spawning a child enumerator and binds ownership to `(PID, start_time_ticks)`. PID reuse cannot hide or invent descendants. Failed finalization preserves an earlier atomic return, and cleanup requires both a valid fully-reaped finalization receipt and a durable-return receipt.

This is an implementation correction under the existing public semantics; no new public rule ID or public rule text was added. `observer_only_wide_causal_final_zip` advances to semantic version 5. Canonical validation passed 80 focused tests, 181 related tests, 123 registry/package-pipeline tests, and a final 201-test guard/boundary suite. The latter permanently updates the operational-attempt fixture so every started child carries the canonical procfs PID plus start-time identity model.

The existing serialized v101 ZIP embeds the pre-activation `ps`-enumerator exclusion helper rather than the canonical procfs helper, so it is not publishable and must be rebuilt with a fresh identity. The separate QAdd measured-runtime proposal remains unactivated because extending the default 3600-second server wall boundary requires explicit user authorization.

No managed-storage or server action occurred. Machine receipt: `outputs/observer_operational_guard_process_identity_runtime_budget_v3/CANONICAL_GUARD_PROCESS_IDENTITY_ACTIVATION_RECEIPT.json`.
