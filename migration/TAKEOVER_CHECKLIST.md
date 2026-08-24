# ResNet50 INT8 clean-clone takeover checklist

1. Clone the repository or restore the verified Git bundle. Do not copy an old
   developer directory, virtual environment, cache, output tree or Codex
   worktree.
2. Read `AGENTS.md`, then `.agents/agent.md`, `.agents/plan.md`, the mandatory
   router and the current owner registry.
3. Restore only the external objects listed in `PROTECTED_DATA_INDEX.json`.
   Never restore retired caches, build/extract trees or unknown legacy content.
4. Recreate Python dependencies from the repository lock files. Do not migrate
   `.venv`, `node_modules`, compiler caches or temporary worktrees.
5. Run active-rule audit, project takeover readiness and managed package
   storage audit. Their current role/pending sets must match the migration
   manifest before any package or server action.
6. Verify each current pending ZIP is present in managed storage. Transport
   digests are provenance; missing current bytes or an inconsistent consumer is
   blocking.
7. Resume only the persistent owner registered for the intended role. Handoff
   never expands server, RTL, config, numeric or workload authority.
8. Keep uploads, server runs and leases disabled until the user explicitly
   authorizes them in the restored project.
