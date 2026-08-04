# Conv node0004 v9 canonical-decision rule receipt

## RESULT

The final v9 ZIP identity matches
`bce6e7e852885cc3c396a860f8aeb687b245a1137a7943db1b9bdc6cf9bd14ce`,
but it does not satisfy
`CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`.

v9 correctly excludes persistent Buffer4/5 levels from monotonic progress. A
32-cycle continuously-high level produces zero qualified transactions and one
rising-edge witness, not 32 transactions.

v9 fails the canonical record gate:

- it appends a summary-only record using the same `DIAG_DECISION` prefix;
- its decision record lacks schema/version, explicit decision, window range,
  and a recomputable content digest;
- summary-only append does not fail closed;
- conflicting records use last-line-wins;
- missing reason/boundary does not produce
  `PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS`.

Therefore v9 is
`QUARANTINED_CANONICAL_DECISION_CONTRACT_DEFECT` and must be withdrawn from
the server queue. It must not be uploaded or run.

## SUCCESSOR

The minimum successor is
`r5_n4_hw_v10_hangloc_canonical.zip`, classified
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN`.

It changes only the package-local observer decision record and parser:

- exactly one `CANONICAL_DIAG_DECISION_V1` record;
- complete schema/version/decision/reason/boundary/window/counter/digest;
- summary uses `DIAG_SUMMARY`;
- duplicate, conflicting, summary-only canonical, missing reason, and missing
  boundary all fail closed as
  `PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS`;
- qualified-only monotonic progress is preserved;
- low-overhead progress diagnostics are enabled by default under
  `CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`.

Receipts:

- ZIP SHA256:
  `9dad438724489b56d4a2546631f4de8a8ee6fc76f2133072a3868a33ba10f0c4`
- ZIP bytes: `5,808,564`
- validation SHA256:
  `be7463c495babb425a73fc8659ca1b5cb2e02d11c6b6e06fa9fbccee405f2579`
- four-way receipt SHA256:
  `7e3d6c8f059aafa346cce67dad4ffde4f14d40e4f1e666904326152129576dba`
- canonical receipt SHA256:
  `96a1138b3a26dfb750e70fe1ec2871707d4214529fc2a15e175e4142e02165f2`
- observer SHA256:
  `ec7241e77c548b8f793cbb45e8d8500ea65c402563ec27c0ac72f9f9eb2655a9`
- deterministic repeated build: pass
- four-way binding and four negative controls: pass
- canonical record and five negative controls: pass
- directed tests: 17/17 pass
- numeric analysis repeated: false
- node0004 workload rebuilt: false
- functional RTL modified: false
- server action: false

Current receipts:

- plan mutable provenance:
  `21dec7853cf9dc1610e51ede1366550b390bfc301d8dc8d5bf6c560d5ecae545`
- server package rule:
  `ed3990f13c62ce67e5081458b0dfdcf6ca257908fe138fcc05a7000482afd2f8`
