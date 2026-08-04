# Package-local HDL syntax/scope positive gate merge

## Scope

- mainline owner: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- action: public server-package rule and routing-index update
- functional RTL modified: false
- server uploaded/run/lease: false/false/false
- package bytes modified: false

## Triggering evidence

Conv node0004 v23 reached the real server VCS compile and failed before
simulation because the exact package-local observer used
`return_obs_buf45_wr_edge_count` once but declared, reset and updated it zero
times. Generation and post-generation rule reads were complete and
current-match. The audit escape was therefore classified as
`VALIDATOR_NONCOMPLIANCE_WITH_STRICT_LOCAL_AUDIT_INTENT`, not a rule-read
omission.

The old release checks proved token presence, XMR constant-index safety,
source/include/macro/runtime binding, runner reachability and EXIT/TERM
collection. They invoked no HDL parser/compiler/linter and did not prove local
identifier scope/name resolution.

Evidence:

- task record:
  `.agents/task_records/20260803_conv_node0004_v23_return_v24_compilefix_successor.md`
- task record SHA256:
  `7dc571fa57b372f17713b416ec89787ade8fba6c128711149cf4ff51150a308c`
- audit-escape report:
  `outputs/conv_node0004_v23_return_analysis/package_audit_escape_root_cause.json`
- audit-escape report SHA256:
  `9ccd411e32ba74ee086fb327adb6f9b1c4c1a73aa6996673a6e50154381fc636`

## Rule adjudication

The existing
`CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001` intent was
correct but not mechanically sufficient. Mainline merged the new non-synonymous
release gate:

`CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001`

For every final ZIP that compiles package-local HDL/TB/observer/support source,
the gate now requires:

1. fresh-extract exact final member identity and actual include/concatenation
   order;
2. a compatible SystemVerilog frontend syntax/elaboration/name-resolution
   positive over the package-local changed/required-evidence scope;
3. when full vendor/DUT dependencies are unavailable, a focused compatible
   frontend plus exact-final-HDL scoped identifier/state ownership closure;
4. declaration, initialization/reset applicability, qualified update and
   consumer-use closure only for identifiers newly changed or used by the
   required canonical/result decision;
5. tool/version/command/cwd/exit/member SHA/harness SHA/specialization/claim
   boundary receipts;
6. deletion-of-declaration, misspelled-use and deletion-of-reset/update
   negatives, all fail closed.
7. a mandatory `package_local_hdl_gate` machine record containing exact
   members, frontend coverage, closure counts, negative-control results, claim
   boundary and one `pass` bit. The equivalent record may be an external
   final-audit/revalidation report bound to exact ZIP/member SHAs and is not a
   server runtime dependency.

Safe compile stubs, `make` reachability, token/regex presence, XMR
constant-index scans and source/include/macro/runtime binding remain useful
separate gates but cannot satisfy this rule.

Failure before release is
`PACKAGE_LOCAL_HDL_SYNTAX_SCOPE_UNPROVEN`. Existing unrun packages enter
`PACKAGE_HELD_HDL_SCOPE_REVALIDATION_REQUIRED`. A frozen package may recover
through a package-external content-neutral rule-drift receipt only when the
exact unchanged ZIP passes the full new gate; otherwise it must be quarantined
and rebuilt with fresh identity.

The user then clarified the minimal-runtime boundary. The gate must not require
exhaustive historical observer-state inventory, complete local vendor/DUT
dependencies, full-design elaboration or new server-source preflight. Those
checks are unnecessary for the stated objective: enter real server compile/run
and recover the target error. Missing non-runtime audit inventory alone cannot
force package repacking.

## Final public rule identities

- `.agents/rules/生成前必读索引.md`
  - bytes: `8219`
  - SHA256:
    `d9e66e5a1dc4ba1658aac7f851227bb162b76601cd497eeea558a88a2e900422`
- `.agents/rules/服务器测试包生成规则.md`
  - bytes: `52840`
  - SHA256:
    `559ce2660cfe34d567ab45f6c2573f7d0ad2ad3f3d751337432616ce9a9690b2`

## Existing-package disposition

QLinearAdd v20 completed package-external read-only revalidation:

- frozen ZIP SHA256:
  `13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51`
- exact `return_obs` used/declared/unresolved: `121/121/0`
- compatible focused frontend: Icarus Verilog 12.0, exit `0`
- required negative controls: all fail closed
- revalidation report SHA256:
  `114893b15ebb90f6c4440ef82f38b60815fbe319f5a44f024c10fc0ed902e402`
- current-rule machine-record equivalence:
  the report's `members`, `frontend`, `full_observer_machine_closure`,
  `negative_controls`, frontend `claim_boundary`, `valid=true` and
  `status=HDL_SCOPE_REVALIDATION_PASS` jointly provide every required
  `package_local_hdl_gate` evidence field; mainline independently parsed the
  exact disk report and rebound it to the current public rule SHA above
- final disposition:
  `HDL_SCOPE_REVALIDATION_PASS / PACKAGE_READY_NOT_RUN`
- the temporary manifest-only successor request was withdrawn before
  materialization; no new package/ZIP/sidecar/identity was created

GAP v24 and Conv v24 preserve their successful scoped HDL positive and negative
evidence. Their subsequently received formal server returns remain
authoritative inputs and were dispatched to the original family owners. The
temporary manifest-only quarantine does not invalidate either return.

## Validation

- full current rule/index/common/hardware/README reread: complete
- current Conv task record and machine reports reread: complete
- targeted rule-ID/current-state search: pass
- `git diff --check` on scoped rule/plan/history files: pass
- public rule duplicate/synonym adjudication:
  `NON_SYNONYMOUS_EXECUTABLE_ACCEPTANCE_GATE`
