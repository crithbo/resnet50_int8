# QLinearAdd node0007 nested-LC v4 local E2 and package record

Date: 2026-07-30  
Owner: QLinearAdd family  
Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## Control receipts

- plan mutable read receipt:
  `5d5f6ac5cf91dbf8e8306e1d8788557f9ae2d61e737790b4b8d5183f4ecb92b4`
- generation index:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- common operator rule:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- hardware-field rule:
  `4db23b6019a43a7cc7b30488c549fb9426fe374349e8224ad989cf107c9bd7a1`
- QLinearAdd rule:
  `dd4a8122d771ed5f4dbb9995fd6463ba14b179a72a515d2af5e91d30f2c71269`
- exact UINT8 tail rule:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- server package rule:
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- hardware simulator entry:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

No plan, rule, functional RTL, server file, or non-QLinearAdd family asset was
modified. No server was inspected, uploaded to, or run.

## RETURN_ANALYSIS

The prior v2/v3 server behavior is a configuration-induced nontermination, not
a workload-size delay. The flat positive-stride DRAM loop domains with
`end=37632` exceed the active signed-feedback bound `end<=32768`. The v3 package
is therefore still `QUARANTINED_NOT_RUN_NO_FUNCTIONAL_FIX`.

The mainline-proposed dequant split `2 x 18816` was not copied blindly. Its
write-stream outer stride would be `18816 x 64 = 1204224`, which does not fit
the unsigned 20-bit `dim_stride` field. This was the first fresh static
divergence and was resolved before mapping by choosing:

```text
dequant: 4 x 9408
  read outer stride  = 9408 x 16 = 150528
  write outer stride = 9408 x 64 = 602112

FP32 add: 8 x 18816
  all stream outer stride = 18816 x 16 = 301056
```

All positive-stride final DRAM loops now have `end<=18816`. The ordered logical
offset hashes for dequant read, dequant write, and FP32 add are identical
between the frozen flat logical domain and the nested domain. Six-qparam
transport, W3 per-operation FP32 order, input replay, relocation, exact UINT8
tail, saturation, and golden are unchanged.

`numeric_analysis_repeated=false`. The frozen 17-instance/stage0/tail assets
were consumed; only the new schedule, final materialization, and config-bound
integration comparison were replayed.

## Local E2 result

- six strict configs: valid
- final positive-stride LC maximum end: `18816`
- mapping: `6/6`, empty initial cache, exact penalty `0`, fallback `false`
- final JSON leaf diff: `13` base-address formatting/binding leaves only;
  non-base diff `0`
- requests with multiplicity: `37352448`
- unique request addresses: `20493312`
- unique address SHA-256:
  `e933bb1cd4f9f163174c8375fcbed841b7258f11dae542bb9beb97b6c7830034`
- maximum formal DDR row: `6143`
- padding-masked request bytes: `0`
- config-bound physical/logical/padding mismatches: `0/0/0`
- execplan bundle manifest:
  `1025d284423192d28c82a2f809b74561847be5b054878be4b3c53dffa81a889d`
- closure report:
  `b8b7991c2027440937870dc31a859ab675c729e40e831ee823968a29296152b2`
- contract:
  `743fef2dfe8cd38d120483ef2dcab3cfdd94b96bf594013d6fb6b7d8187e6bfb`

Targeted tests: `6/6 PASS`.

## BYPASS_ANNOTATION

- `bypass_reason`: native add_dequant terminates at FP32 and the prior flat
  positive-stride LC domains wrap signed feedback.
- `contradicted_or_missing_native_path`: native fused QLinearAdd with exact
  UINT8 tail is absent; the flat dequant/add `end=37632` schedule is dynamically
  contradicted.
- `exact_equivalence_scope`: frozen node0007 six-qparam W3 order, all 28 slices,
  complete UINT8 Y, and zero padding.
- `materialized_configuration_mechanism`: six serialized native stages,
  dequant `4x9408`, add `8x18816`, explicit FP32 scratches, and the frozen exact
  UINT8 tail.
- `performance_and_resource_cost`: two complete FP32 activation scratches, one
  FP32 relocation spacer, six stages, and sequential completion barriers.
- `unresolved_production_blocker`: performance is not qualified and no final
  server RTL identity or E4/E5 dynamic result is bound.
- `claim_boundary`: `CONFIG_ONLY_CORRECTNESS_BASELINE`;
  `candidate_release=false`; local E2 only.

## BLOCKER_DELTA

- CLOSED locally:
  `B_QADD_NODE0007_DRAM_LC_SIGNED_FEEDBACK_WRAP`
- OPEN production/dynamic boundary:
  final server RTL identity, E4 exact readback, and independent E5 rerun
- No new local E2 blocker remains.

## RULE_DELTA_PROPOSAL

Proposed ID: `CDA-QADD-NESTED-LC-FACTOR-WIDTH-COUPLING-001`

When replacing a large flat LC domain with `outer x inner`, the validator must
jointly prove:

1. every positive-stride LC `end<=32768`;
2. every derived outer `dim_stride` fits the encoded field width;
3. `outer*inner` equals the frozen logical occurrence count;
4. ordered request-offset hashes, byte coverage, and final address signatures
   match the frozen logical domain.

The node0007 counterexample is dequant `2x18816`: its write outer stride
`1204224` exceeds 20 bits. `4x9408` is the first selected power-of-two split
that keeps the same ordered domain while fitting the field.

## PACKAGE_RELEASE

Status: `PACKAGE_READY_NOT_RUN`

- install/package identity: `r5_qadd_n7_nested_lc_v4`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_nested_lc_v4.zip`
- ZIP bytes: `38008754`
- ZIP SHA-256:
  `dfe6ab0e11482d9af7954ba3e87911b770f8d80efa4148352b63d27bf7df2361`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_nested_lc_v4.zip.sha256`
- package files: `131`
- repeated build: package tree equal and ZIP byte-equal
- ZIP CRC/path/exact-set: clean
- functional RTL entries: `0`
- TB/observer entries: `0`
- packaged runtime D targets: `0`
- formal D targets: `28`, absent in ZIP/package preflight
- preload entries: `85`
- return allowlist entries: `38`
- gate:
  `compile0 AND simulation0 AND natural_terminal AND loader_exact AND
  readback_exact_set AND missing0 AND mismatch0`
- candidate release: `false`
- evidence level: `E2_LOCAL_ONLY`

One server command, if and only if mainline later grants the group-B lease:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02
```

Expected return:

```text
r5_qadd_n7_nested_lc_v4_return.zip
r5_qadd_n7_nested_lc_v4_return.zip.sha256
```

This record does not authorize upload or execution.
