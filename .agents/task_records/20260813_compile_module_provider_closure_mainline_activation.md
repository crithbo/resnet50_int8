# Compile module-provider closure canonical activation

Date: 2026-08-13

Role: `mainline.control`

Activation epoch: `compile-module-provider-closure-v1-e455bf5dd7dc`

## Previous progress

Serialized Conv v88 completed a fresh production compile and resolved `DW_ecc/DW_sync/DW_lod/DW_fifo_s1_sf` while naming the same `sim_ver` argv path that v89 later reported unreadable. GAP v60 and native Conv p45 repeated the v89 unresolved-module failure. This paired evidence invalidated the earlier unactivated rule draft that treated one absent named path as a sufficient blocking root.

## Current purpose and decision

Canonical current disk now activates `CDA-SERVER-COMPILE-MODULE-PROVIDER-CLOSURE-001` for later next-fresh packages. A named `-y/+incdir` path being absent or wrong-type is record-only. Blocking requires either an incomplete aggregate closure across every provider bound by the exact actual compiler argv, or failure of a package-owned tiny lookup probe using the same compiler identity, provider flags and runtime context without compiling/elaborating the DUT or running simulation.

Known-good compile evidence is comparison-only. Cross-family receipt reuse requires the exact execution epoch, boot, host, compiler, Makefile/source/filelist/environment, provider-state and required-module projection. Probe failure publishes a complete `SIM_NOT_STARTED_RETURN`; first-true-error selection and stale/missing compile-failure core aggregation remain mandatory.

## Canonical merge

- Mechanically synchronized the shared tool, schema, dispatch, fixture, focused tests, report, proposal and optimizer task record.
- Narrowly merged provider semantics into the current server-package rule, generation router and whole-network optimizer rule without replacing observer-only or one-shot VCD increments.
- Added `compile_environment_attestation` to the current build-gate registry as `required_next_fresh` with `server_start+return` impact.
- Refreshed the active-rule registry identities; no duplicate `CDA-*` definition was introduced.

## Validation

- focused provider closure: 15/15 PASS;
- provider closure + runner resilience + package pipeline: 36/36 PASS;
- Python compile, JSON parse, Draft 2020-12 schema meta-check and scoped diff check: PASS;
- active-rule audit: PASS, 14 active rules, 164 unique definitions, zero duplicates/errors/warnings.

Machine receipt: `outputs/compile_module_provider_closure_gate_v1/canonical_activation_receipt.json`.

## Boundary

Activation is required-next-fresh only. No current/pending/tested package was rebuilt, mutated, held or rotated; no alternate toolchain was selected; no server, config, numeric, workload or RTL action occurred. The exact historical v88 A/B package remains a separate user-run comparison option, not current provider proof.
