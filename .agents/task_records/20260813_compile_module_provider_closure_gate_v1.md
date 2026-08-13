# Compile module-provider closure gate v1

Date: 2026-08-13

Owner: optimizer.whole-network / task `019fd276-14c5-7800-94db-87ebfb9ce632`

Return target: current mainline role `mainline.resnet50`

## Objective

Prevent repeated full server compiles when a required external module provider is unavailable, without restoring broad
server-source preflight and without falsely treating one missing `-y/+incdir` path as the root cause.

## Correction to the earlier draft

The earlier unactivated draft `CDA-SERVER-COMPILE-ARGV-EXTERNAL-DEPENDENCY-ATTESTATION-001` treated an absent named
DesignWare `sim_ver` directory as sufficient to block. It is invalidated before activation.

The paired production evidence is decisive:

- serialized Conv v88 used the same named `/tools/Synopsys/dc2023/syn/V-2023.12-SP3/dw/sim_ver` tokens, the same
  Makefile SHA, top-filelist SHA and 874-source recursive closure as v89, then compiled successfully and recompiled the
  required DW modules;
- v89 reported the named path unreadable and then emitted `Error-[URMI]` for `DW_ecc`, `DW_sync`, `DW_lod` and
  `DW_fifo_s1_sf`;
- GAP v60 and native Conv p45 repeated the v89 failure mechanism.

Therefore the three failures prove current module-provider closure failure, not a unique server-environment change or a
unique-path root. v88 historical success is useful comparison evidence but cannot prove current availability.

## Implemented current method

Rule proposal: `CDA-SERVER-COMPILE-MODULE-PROVIDER-CLOSURE-001`.

Shared implementation:

- `tools/server_compile_environment_gate.py`
- `schemas/server_compile_environment_gate_v1.schema.json`
- `contracts/server_compile_environment_gate_dispatch_v1.json`
- `fixtures/server_compile_environment_gate_v1/misleading_platform_then_urmi.log`
- `tests/test_server_compile_environment_gate.py`
- `outputs/compile_module_provider_closure_gate_v1/report.json`
- `outputs/compile_module_provider_closure_gate_v1/rule_delta_proposal.json`

The gate now:

1. derives provider candidates from the exact compiler argv, resolving make/gmake through an exact `--just-print/-n`
   request with identical Makefile, target and variables;
2. aggregates source-declaration coverage across all bound provider candidates;
3. records missing/wrong-type named paths without blocking by that fact alone;
4. if the static provider closure remains incomplete, runs a small package-owned same-compiler/same-provider-flags
   lookup top with one empty instance per required module; it does not compile the DUT or run simulation;
5. binds the result to execution epoch, boot, host, compiler, Makefile, recursive source closure, top filelist,
   make-affecting environment, provider flags, provider path state and required-module exact set;
6. allows cross-family reuse only for the exact same projection;
7. preserves the separate first-true-error extractor and aggregate compile-failure return-core audit.

## Real-return classification

- v89/GAP v60/native p45 primary class: `COMPILE_ONLY_PRODUCTION_MODULE_PROVIDER_CLOSURE_FAILURE`.
- Not config/numeric/DUT-runtime evidence; simulation never started.
- p45 independently exposed stale actual-argv evidence plus an incomplete compile-failure return core.
- GAP v60 independently exposed a first-error extractor that selected platform prose before URMI.

## Validation

- focused provider-closure suite: 15/15 PASS;
- combined provider-closure + runner-return-resilience + package-pipeline suite: 36/36 PASS;
- `py_compile`: PASS;
- Draft 2020-12 schema meta-validation: PASS.
- active-rule audit: 14/14 registered rules, 155 unique definitions, zero duplicates/errors/warnings.

Required controls include source-provider success, named-path-absent/probe-success, v88 historical receipt not promoting
current readiness, stale semantic fingerprint, unbound provider, exact make resolver, provider probe success and URMI
failure, runtime-context reuse drift, platform-prose first-error regression, and p45 stale/missing return-core aggregation.

## Next-fresh handoff

After exactly-once finalizer arm and layout preflight, the runner must resolve the actual compiler argv, bind the complete
semantic/provider projection, and run the provider lookup probe only when source closure is incomplete. A failed probe
returns immediately as `SIM_NOT_STARTED_RETURN`; a successful probe only authorizes the full production compile. No
alternate toolchain is selected automatically.

## Boundary

No current/pending/tested package was rebuilt or modified. No mapping, bitstream, execplan, SCA, config, numeric,
workload, functional RTL, active ndp-sim, upload, lease or server execution occurred. `.agents/plan.md` was not edited.
The proposed public rule remains subject to mainline narrow merge and activation.
