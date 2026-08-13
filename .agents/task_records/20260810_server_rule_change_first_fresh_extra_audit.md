# Rule-change first-fresh package extra audit

Date: 2026-08-10  
Owner: `019fd276-14c5-7800-94db-87ebfb9ce632`  
Mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Outcome

Published `CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001` and the
matching generation-index/specialist routing.  After a server-package rule or
shared implementation epoch changes, the first fresh package for every affected
family is now explicitly marked `ACTION_REQUIRED_BEFORE_UPLOAD` and must remain
held until `EXTRA_AUDIT_PASS`.

The package owner first runs the normal cheap aggregate once, builds one final
ZIP, then independently re-audits a clean extraction of that exact ZIP.  The
second audit cannot reuse family build reports.  It covers exact ZIP structure,
actual runner/input opens, exact generated logger-to-collector-to-parser
roundtrip with real formatting/multi-instance/over-budget records, post-sim
return-core four scenarios, and the full candidate discrimination matrix.

Only findings mapped to `server_start`, `actual_input`, `state_safety` or
`return` may block.  All other findings are `record_only`.  Every failure is
collected in one report before a rebuild.  After the first package passes, later
packages in the same family/epoch bind that PASS receipt and return to normal
changed-surface gates.  A new epoch triggers one new first-package audit.

## Shared implementation

- contract schema: `schemas/server_first_fresh_extra_audit_v1.schema.json`
- dispatch schema: `schemas/server_first_fresh_extra_audit_dispatch_v1.schema.json`
- dispatch: `contracts/server_first_fresh_extra_audit_dispatch_v1.json`
- validator: `tools/validate_server_first_fresh_extra_audit.py`
- tests: `tests/test_server_first_fresh_extra_audit.py`
- build gate: `first_fresh_extra_audit=blocking_applicable/required_next_fresh`
- rule-change epoch: `20260810-first-fresh-extra-audit-v1`

Worktree focused/shared regression is 84/84 PASS.  Current main-workspace
regression is 85/85 PASS; profile-schema validation and external-pycache
`py_compile` pass.  Ten mechanically synchronized shared files are byte/SHA
identical between owner and main workspaces; `git diff --check` passes.

Machine report:
`artifacts/operator_config_validation/r5-server-first-fresh-extra-audit-v1/report.json`,
bytes `5085`, SHA256
`bb9dd54263eb6b661b5048fb1f4b5fca2f15844fe5eb093be966ad2f59390bae`.

No current/pending/tested package was rebuilt, modified, held or invalidated.
No mapping, bitstream, execplan, SCA or ZIP was generated; no server upload/run,
lease, RTL, config, numeric, workload, timeout or `.agents/plan.md` action occurred.
