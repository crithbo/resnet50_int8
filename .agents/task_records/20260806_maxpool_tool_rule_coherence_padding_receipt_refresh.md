# MaxPool tool-rule coherence and padding RTL receipt refresh

Date: 2026-08-06

## Provenance

- analysis_owner_thread: `019fbe9f-3f2d-7071-806c-1ae72ae96391`
- return_target_thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- agent receipt: `.agents/agent.md` SHA256 `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- plan receipt at finish: `.agents/plan.md` SHA256 `964772f65851522ee1f31db840ef1d609faa181042c189a0293f04171ffef3a8` (mutable provenance only)
- generation index: `.agents/rules/生成前必读索引.md` SHA256 `e3c7ed8a651d9b1d8b4d67e4ec29fe50c6441f8410cb60c9bd7f95359ccd4bf6`
- operator rule: `.agents/rules/算子配置规则.md` SHA256 `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- NDP field semantics: `.agents/rules/NDP硬件字段语义.md` SHA256 `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`

## Tool-rule coherence

`resnet50_pipeline/operator_config_validator.py` no longer gives
`ga_int8_max` one ambiguous overall `CONTRADICTED` classification.  It now
reports the two current rule results independently:

- `CDA-GA-INT8-MAX-NUMERIC-001=LOCAL_SOURCE_PASS`
- numeric equation: `unsigned bytewise max(A,C)`
- `CDA-GA-INT8-MAX-PIPE-001=CONTRADICTED`
- `pipeline0_accepts_second_item=false`

The MaxPool complete-JSON direct consumer
`tools/validate_maxpool_complete_json_local_v2.py` now requires this exact
split result and reports `metadata_coherence`, not a waived metadata conflict.
`tools/validate_maxpool_complete_json_regeneration_v1.py` was also changed to
consume the current padding receipt rather than carry a stale-padding status.
It was not executed in this task because downstream replay was outside the
authorized boundary.

## Current padding RTL receipt

The historical MaxPool padding contracts remain byte-identical.  Their old
tracked evidence remains historical, while validation now additionally
requires the fresh current receipt:

- receipt: `contracts/operator_config/maxpool_padding_rtl_current_receipt_v1.json`
- receipt SHA256: `3228e677cb1c7767e0ee68256db524e6ee9d25ff648916f1b05a6d4a46650e75`
- pinned cloud-authority checkout: `Trassic2.0_RTL`, remote
  `https://github.com/xlsjdjdk/Trassic2.0_RTL.git`, commit
  `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`
- authority `RD_Data_Channel.sv`: 28128 bytes, SHA256
  `08b35e80c234c6567099c4da5e18ff0a18955e259b7c12bedff72325f744038c`
- `NDP_copy01/rtl` mirror: byte-identical, same size and SHA256
- source lines 288-290: `padding_mask ? padding_value :
  branch_or_tail_mask ? zero : ddr_data`

The receipt is read-only evidence.  It does not alter the padding value,
MaxPool numerical rule, or functional RTL.

## Validation

- machine audit command:
  `.venv\Scripts\python.exe -B tools/validate_maxpool_tool_rule_coherence_padding_receipt_v1.py`
- audit exit: `0`
- machine report:
  `artifacts/operator_config_validation/r5-maxpool-tool-rule-coherence-padding-receipt-v1/report.json`
- machine report bytes: `11436`
- machine report SHA256:
  `28fcaeefed00a8320a2c48da71dd9f10efa2cc450a8155709cd30c5a292efb9e`
- targeted tests:
  `.venv\Scripts\python.exe -m unittest tests.test_operator_config_validator tests.test_maxpool_padding_contract -v`
- targeted test result: `46/46 PASS`, exit `0`
- negative controls: `8/8` fail closed
  - promote pipeline failure to numeric failure
  - hide pipeline contradiction
  - restore ambiguous overall classification
  - restore stale unsigned-min equation
  - tamper authority RTL hash
  - tamper mirror RTL hash
  - tamper padding priority equation
  - tamper authority commit
- syntax-only compile of all changed Python validator modules: PASS

## Complete-JSON/current-v5 invariance

No complete JSON, current v5 consumed configuration, or current-test diff was
rewritten:

- strict candidate SHA256:
  `0348ead26469b8ebda0df03979d38f8436bc9f1f6903bafed078b0547d682335`
- current v5 consumed config SHA256:
  `b1d0bb4e8f0aeb59253dfc2b3e73c3731f7b4bb1712998ccb845fa34c34f6c77`
- current-test diff SHA256:
  `eff77c32fa844b94d51a0ca5963bcf41430bde25d40f3d06ea06bb54fd983e09`
- candidate contract SHA256:
  `0096f0f507a3ad7281c07d443c548e1786a47cbf6820f0a1b194972d298518d6`
- diff remains exactly one leaf:
  `/stream_engine/stream0/padding_reg_value`, current v5 `null`, strict
  candidate `0`.
- MaxPool complete-JSON adjudication remains `COMPLETE`.

## Boundary

- numeric rule modified: false
- public rule modified: false
- plan modified: false
- functional RTL modified: false
- mapping/bitstream/execplan/SCA generated or modified: false
- server ZIP generated or modified: false
- server upload/run/lease: false
- other family assets modified: false

`RULE_DELTA_PROPOSAL=NONE`.
