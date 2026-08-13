# 2026-08-12 — Portable local waveform decodability v1

## Scope

The whole-network optimizer implemented a shared read-only method for binding a formal-return VPD to a portable VCD/FST derivative and for extracting exact selected-signal transition rows. Signal-level interpretation and root-cause classification remain owned by `family.conv.serialized`.

No current package, RTL, config, numeric asset, `.agents/plan.md`, public rule, active ndp-sim tree, or server state was changed.

## Exact input receipt

- Return ZIP: `C:/Users/15383/Downloads/r5_n4_hw_v87b_mandatory_vpd_r1786458170706574446_1205339_return.zip`
- bytes: `11249796`
- SHA256: `793163afeea31675192429f0f4c39021299b594d487ed4fa4b4e0ca62b718148`
- VPD member: `r5_n4_hw_v87b_mandatory_vpd_return/waveforms/compile/sim_results/wave.vpd`
- VPD bytes: `10871483`
- VPD SHA256: `bd75bcb588345bc1819049e247b512a67e9b5b3885e2cb0e6e52065c8c90b3b7`
- VPD completeness: `PARTIAL`

## Shared method

- `tools/server_waveform_local_analysis.py` — bytes `24472`, SHA256 `088e8d797f98f247f030e9331ca3c83e7b767b5958a8bf74d2732974850510af`
- `schemas/server_waveform_local_analysis_v1.schema.json` — bytes `687`, SHA256 `88ee61884e42f574958bb810b6f82427e374afa315c1a31086e5d5043e916044`
- `contracts/server_waveform_local_analysis_dispatch_v1.json` — bytes `1568`, SHA256 `e9a9078cb27dc202b62a75a9d23ce15a394430b4e1c58bbd18bf3c03a50f1931`
- `tests/test_server_waveform_local_analysis.py` — bytes `6173`, SHA256 `d796576f0d527b33e567aa0eef0e15a7f34d46c466fb3b172810b08cf6005a1a`
- `fixtures/server_waveform_local_analysis_v1/small.vcd` — bytes `319`, SHA256 `bca910f02fb8ab8519a3bc12213394d2042e6d0242ff49bafbdf6dfdd8cf7fb6`

The method provides `toolchain`, `prepare-request`, `convert`, `catalog-vcd`, `extract-vcd`, and `convert-fst` commands. The raw VPD is never rewritten. Conversion receipts contain executable identity, best-effort version probe, exact argv, input/output SHA256, logs and exit status. VCD catalog/extraction is streaming and has no hidden byte/event cap.

## Current blocker and usable local surface

Current discovery is exact: `vpd2vcd`, Verdi and DVE are absent. GTKWave and `vcd2fst` are available, but neither can semantically decode a Synopsys VPD without `vpd2vcd`.

- toolchain receipt: `outputs/whole_network_waveform_portable_local_analysis_v1/toolchain.json`, bytes `1074`, SHA256 `64f1429f6ff19aa1cb2ed4d61cea6a36515a7d5b336f95fdcb19f502bb388332`
- v87b conversion request: `outputs/whole_network_waveform_portable_local_analysis_v1/v87b_conversion_request.json`, bytes `1025`, SHA256 `1dd683359ee481c1ea780a639e90b38437053d60f91a2a0bd534ca62686effb7`
- request result: PASS; the VPD member is byte-bound and no simulation rerun is required
- exact blocker: `VPD_SEMANTIC_DECODER_EXECUTABLE_NOT_AVAILABLE`

## Validation

- focused unit tests: `8/8 PASS`
- `py_compile`: PASS
- JSON parse: PASS
- scoped `git diff --check`: PASS

## Rule adjudication

`RULE_DELTA_PROPOSAL=CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001`.

This is non-synonymous with the existing raw-waveform return rule: transport completeness does not guarantee local semantic decodability. For next fresh packages, retain authoritative raw VPD and additionally require either an unbounded VCD derivative produced by identity-bound `vpd2vcd`, or an identity-bound signal-query receipt. Conversion failure must retain the raw/core return but classify diagnostic evidence as incomplete. Mainline owns public-rule merge.

## Claim boundary

Shared read-only conversion/query method only. No signal interpretation, family diagnosis, package/RTL/config/numeric change, server action, natural-terminal, formal-D, E4 or E5 claim.
