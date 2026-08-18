# Server package Python exact-set / schema-runtime gate v1

GAP v67 and v68 prove two shared final-ZIP implementation escapes. A late generated
package-local Python source was not compiled by the shared clean-ZIP audit, and a
schema-enabled validator could be reported as skipped when `jsonschema` was absent.
GAP v69 is the positive historical control: 19/19 package Python members compile and
its schema-enabled gates pass.

No new public rule ID is required. The fix is a narrow implementation hardening under
`CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001` and
`CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001`:

- final staging and clean exact-ZIP `.py` path/bytes/SHA sets must be identical;
- every discovered member is compiled, with all errors aggregated and bytecode kept
  outside both package trees;
- the gate runtime must import `jsonschema` and execute the admission contract schema;
  missing/incompatible dependency, skipped validation or schema failure is blocking.

The existing `package_release_admission_runtime_preflight` gate is advanced to semantic
version 2. Focused release-admission plus first-fresh/pipeline regression is 44/44 PASS;
Python compile, JSON parse and scoped diff-check pass. Permanent controls include the
real GAP v67/v68 pair, malformed unlisted Python, missing `jsonschema`, forbidden skip,
staging/ZIP drift and the earlier pending-manifest/polarity failures.

Machine report: `outputs/server_package_python_schema_runtime_gate_v1/report.json`.
Canonical narrow rule merge is still required before activation. Activation is
required-next-fresh only; GAP v69 and all current packages remain unchanged.

No family package, storage, RTL, config, numeric, workload or server action occurred.
