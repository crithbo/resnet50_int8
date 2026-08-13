# Package-local HDL lexical gate activation and three-family build dispatch

Date: 2026-08-12  
Owner: `mainline.control` / `019ff027-e7db-72a3-b282-cfad8708da05` / owner epoch 2  
Registry epoch: 6  
Activation epoch: `package-local-hdl-lexical-v1-01211147e247`

## Previous-version progress

The first real serialized FSDB smoke reached production VCS parsing and failed
before simulation because the shipped package-local probe declared
`integer sequence;`.  The existing
`CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001` rule already
required exact-final-ZIP HDL frontend/scope proof, so this was an implementation
escape under an existing semantic rule rather than a new rule gap.  Smoke s1 is
tested, unrun s2 is superseded for an imprecise operator-root self-description,
and corrected smoke s3 remains `PACKAGE_READY_NOT_RUN` for two sequential user
runs.

## Current-version purpose

Harden the existing package-local HDL rule with a cheap staging lexical scan and
an independent exact-final-ZIP recomputation.  Both scans aggregate every
reserved declaration-name violation; neither replaces the full
frontend/scope/state/negative-control conjunction.  Once this hard gate is
current, supersede the obsolete build-only `HOLD_FSDB_SMOKE_GATE` for GAP,
native Conv and QAdd and dispatch local fresh FSDB-v3 package generation.  This
activation does not authorize upload, lease, server execution, or a formal
serialized Conv successor.

## Current exact assets

- `tools/validate_server_package_local_hdl_lexical.py`
- `schemas/server_package_local_hdl_lexical_validation_v1.schema.json`
- `contracts/server_package_local_hdl_lexical_gate_dispatch_v1.json`
- `tests/test_server_package_local_hdl_lexical.py`
- `contracts/server_package_build_gate_registry_v1.json`
- `.agents/rules/服务器测试包生成规则.md`
- `.agents/rules/生成前必读索引.md`
- `outputs/whole_network_package_local_hdl_lexical_gate_v1/report.json`

The build-gate registry publishes `package_local_hdl_lexical_final_zip` as an
always-active, non-reusable, required-next-fresh, final-ZIP/server-start gate.
The existing `package_local_hdl` aggregate is cheap-prebuild eligible at semantic
version 2.  The router references the existing source-bound, triggered-causal,
qualified-budget, logger/parser and multiclass no-loss rules without duplicating
their definitions.

## Validation

- Shared regression: 170 tests passed, 1 skipped.
- New lexical focused suite: included in the shared regression and passed.
- Python compilation of the lexical validator, active-rule auditor and package
  pipeline passed.
- JSON parsing of the schema, dispatch, build-gate registry, active-rule
  registry, owner registry and machine report passed.
- Active-rule audit passed with 14 active/registered rules, 160 unique
  definitions, no duplicate definitions, no errors and no warnings.
- Scoped diff check passed before dispatch.

## Dispatch disposition

- `family.gap`: `PACKAGE_BUILDING`; preserve the v56-proven slice-local bypass
  and the v57/v58 sum-s2 input-supply/read target, changing only the fresh FSDB
  runtime/return and diagnostic surfaces required by current gates.
- `family.conv.native`: `PACKAGE_BUILDING`; preserve the p42 vector-handshake
  correction and MSE4 target, changing only the fresh FSDB runtime/return and
  diagnostic surfaces required by current gates.
- `family.qlinearadd`: `PACKAGE_BUILDING`; preserve the v57h selected-port
  lane-readiness target and additionally correct the known manifest
  `install_name` versus SCA namespace identity mismatch.
- `family.conv.serialized`: unchanged at smoke s3
  `PACKAGE_READY_NOT_RUN`; no formal serialized successor is authorized.

Each dispatched family must pass staging and exact-final-ZIP lexical checks,
the full package-local HDL frontend/scope/state/negative controls, current FSDB
v3, first-fresh, final-ZIP, runtime/return and storage gates before returning
`PACKAGE_READY_NOT_RUN`.  Config, numeric, workload, golden and functional RTL
remain frozen.  No family may upload, acquire a lease, connect to or run a
server under this dispatch.  Formal package server execution remains blocked
until the user-run serialized smoke proves production time advance, fresh FSDB
collection, registered events, exact repeat reset and distinct returns.

## Claim boundary

This record proves current-disk shared-gate activation, regression coherence and
build-only dispatch.  It does not prove production compile, DUT simulation,
FSDB runtime behavior, natural terminal, formal D, E3, E4 or E5 for any fresh
family package.
