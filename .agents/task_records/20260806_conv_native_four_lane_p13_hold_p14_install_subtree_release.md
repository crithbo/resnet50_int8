# Conv native-four-lane p13 HOLD → p14 install-subtree package release

## Scope and disposition

- Owner scope: performance/native-four-lane Conv only.
- Mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- Source p13 remains `PACKAGE_HELD_PRE_SHARED_INSTALL_LAYOUT_GATE` and is preserved under `superseded`; it was not overwritten or released.
- Fresh successor: `r5_n4_0cc_p14_install`.
- Final status: `PACKAGE_READY_NOT_RUN`.
- No upload, server execution, lease, functional-RTL edit, public-rule edit, plan edit, serialized-Conv edit, or other-family edit occurred.

## Frozen and changed surfaces

The following p13 surfaces are byte-frozen or semantically frozen: workload, numeric inputs, W3/golden, materialized CONFIG/mapping/bitstream/execplan, observer/parser/predicate, timeout, package-local HDL/TB, functional RTL, ISA, hardware and active `ndp-sim`.

Fresh changes are restricted to package identity, runtime layout, runner/manifest/return contracts, and the mechanical SCA_D projected output-path prefix needed by the install-subtree layout. Deterministic double construction produced the same final ZIP.

## Current rule and shared-contract receipts

- generation index: `1101d76534c4898569dbfd0fd4ed1f99800d4a8ec0bdd8dbbef3ce030d147fc1`
- server package rule: `570ffedd04d5f41bc3093e5aa498544325281a4d81f2f4ddc889b754e968424c`
- whole-network convergence rule: `123e66c80048808e93b7151b1dca4af3faee823f458310d41856163790656020`
- shared layout helper: `82723ecc427c3e42cfc327eff87cae7d5d935b9f6dccb220e78bfa573d11a9ae`
- shared layout validator: `6176218d6d36d6ae0e57ead8832742144c11594f4383e1da282ab36608deb943`
- layout schema: `eda7b583551d409c4a45fa6e9fee8d2a1e94b922d36e3b3c56c76553ac07bf39`
- harness schema: `91d20878e242be132eeb48149e204bcb7af26ef29c93b13f3b39f6ce6100541f`
- build registry: `38ddda7091df3f6cba6ad5c55124f3af80fb9f68ee7d79e217cf8f3adda30001`
- two-Conv dispatch contract: `67330174cef70e1dd6085a4395d217df37704f9a333bd83c03a18bec171a4624`
- pipeline tool: `51fde61978a796d3346723f17dbbefc1deec876fd8eae1985f9a195bcd44888b`
- mutable plan provenance observed after completion: `43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70`

## Package identity

- p13 source ZIP: `a2c9e849bf57bc96d05ceb50c22351ae512470343bf1c96928d5b57962c8fe01`
- p14 ZIP bytes: `45911951`
- p14 ZIP SHA256: `e920803ffddbb90dc93470c0b711bfc8bf046ae819012ad89461f36ab9be5427`
- pickup path: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p14_install.zip`
- expected server return ZIP: `/home/panqs/ndp/simresult/r5_n4_0cc_p14_install_return.zip`
- expected server return sidecar: `/home/panqs/ndp/simresult/r5_n4_0cc_p14_install_return.zip.sha256`

## Install-subtree contract

- cfg: `$server_root/install/cfg_pkg/r5_n4_0cc_p11f_pubord`
- run: `$server_root/install/codex_runs/r5_n4_0cc_p14_install/a0`
- evidence: `$server_root/install/codex_runs/r5_n4_0cc_p14_install/a0/evidence`
- compile: `$server_root/install/codex_runs/r5_n4_0cc_p14_install/a0/compile`
- final result publication only: `/home/panqs/ndp/simresult`
- all required parents are verified as pre-existing real directories and non-symlinks before fresh children are created.
- NDP-root direct-child name+type exact-set is unchanged.
- all new server-root descendants stay under `install/`.
- final ZIP contains exact `SERVER_RUNTIME_LAYOUT_CONTRACT.json` and exact shared `package_tools/server_package_runtime_layout.py`.
- TB cwd is `$server_root`; all 86 SCA input paths open their exact projected installed bytes.

The p12 path-budget regression is closed:

- exact longest projected relative string length: `115`
- declared relative maximum: `115`
- computed relative maximum: `115`
- declared absolute maximum: `212`
- server limit: `240`
- a declared `112` mutation fails closed.

## Local gates

- family final-ZIP audit: PASS, errors `0`
- shared runtime-layout validator: PASS, errors `0`
- shared unit tests: `5/5` PASS
- Python syntax compile: PASS
- deterministic double build: PASS
- manifest exact-set and sidecar: PASS
- frozen-surface comparison: PASS (`91` frozen paths)
- exact runtime path-budget and package preflight: PASS
- normal runner: compile reached, simulation reached, finalizer reached, fixed result published
- preflight failure: compile not reached, partial return published
- compile failure: compile reached, simulation not reached, partial return published
- HUP/INT/TERM: compile and simulation reached, signal exit preserved, partial return published
- all six runner modes: root exact-set unchanged, no writes outside `install`, no root/package duplicate return
- negative controls: `8/8` fail closed (wrong SCA input prefix, missing payload, `112/115`, external work root, new root entry, late finalizer, fixed-result drift, wrong SCA_D prefix)

## Release-gate disposition

The shadow build profile is contract-valid and exactly matches the authoritative family validator:

- `blocking_applicable`: `7` — core identity/bootstrap, runner control flow, materialized config, return/result, final ZIP, runtime layout, storage rotation; all PASS.
- `not_applicable`: `2` — package-local HDL and diagnostic semantics are frozen.
- `record_only`: `1` — intermediate report formatting.
- `receipt_reuse`: `0`.

Evidence:

- family report SHA256: `9e4d40ac41425ee009ee3e904537544998741df573adbd79b30e770154e8a951`
- shared report SHA256: `352f035a0cf50a72d4e8020a500551144697aaee2fb11c05a1edf4294a42de19`
- runtime harness SHA256: `745f787f1f62efe004352644c1a7ca64f01d3f5d234ce378f986f35242fc2806`
- shadow profile SHA256: `9ae92936ed162b645c0362229c45cc4a8f91395e077a3f48577ab2adad080f33`
- release report SHA256: `438bd6d578253a2b50a16bc7726c07984ec9c25f9b17a5fc2b3401d77cea2c48`
- storage index SHA256 at rotation: `eb1b2de611c3bcf3c29c672861a1a6f5631d70643c19aa7d85165cb30615869e`
- post-rotation storage audit: PASS; the only pending package for `conv_native_four_lane` is p14, and pending pickup remains ZIP-only.

## Server instruction and claim boundary

After extracting the pickup ZIP, run:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

This record claims only `PACKAGE_READY_NOT_RUN`. No DUT was run locally or remotely, so natural terminal, formal 320D, E3/E4/E5 and performance closure remain unclaimed until a formal server return is consumed.

## Rule feedback

`RULE_CONFIRMATION`

`CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001` correctly blocks the p13 pre-shared layout and forces all package-owned runtime state under the pre-existing NDP `install/` subtree. The shared exact-layout validator plus the family runner harness closes normal and all required partial-return paths, while the exact `115=115=115` path-budget equality prevents the p12 audit escape. No non-synonymous rule delta was found.
