# QLinearAdd node0007 v35 cloud RTL causal-cone revalidation

Date: 2026-08-05

## Provenance and scope

- owner:
  `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target/mainline:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`
- cloud authority:
  `xlsjdjdk/Trassic2.0_RTL/master@0ccae916ef61904a64d6cf8ec1d1931b45e428d8`
- local expected checkout:
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`
- action:
  exact Git-object diff plus QAdd v35 affected-causal-cone static revalidation
- numeric/W3/qparam/tail/workload/config/golden repeated: `false`
- package rebuilt or modified: `false`
- plan/public rules/functional RTL modified: `false`
- server upload/run/lease: `false`

## Current receipts

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md` (mutable):
  `0d1c5577f71d565c7ee4fa6a43054db458de53b41f45813ed2bb3b98be30e126`
- `.agents/rules/生成前必读索引.md`:
  `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`
- `.agents/rules/算子配置规则.md`:
  `d4069167000ae5e0076401afbc6c8db20965965ef4f5da30914f40297f59cba0`
- `.agents/rules/服务器测试包生成规则.md`:
  `61753f6866f49aca142545394451cd73c4e634a5aa160b066e020b7c9067cedd`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/QLinearAdd算子配置规则.md`:
  `28bb859c5f9b8cb5ce5e7ac0dfd81bc06c8b24835d1d3fa4a6062c7c23c0800b`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

The dispatched server-rule SHA
`68fafe7c33e8ac037d94308a0902cdb52afec32f1325d6cee9bc14f70ca9d69d`
had a legal later disk-current update. The current
`61753f6866f49aca142545394451cd73c4e634a5aa160b066e020b7c9067cedd`
contains `CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001`
and was used for this revalidation.

Cloud identity report:

- path:
  `artifacts/rtl_sync/trassic_cloud_master_0ccae91_20260805/report.json`
- bytes: `2952`
- SHA-256:
  `c77e81c7d7ee5b7f557e52a8ec22cb8318cac06ff0ead2aeab80aaa236e25d93`

## Exact v35 identity

- package:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_crow32_v35.zip`
- bytes: `26180881`
- SHA-256 before/after:
  `45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829`
- sidecar file SHA-256:
  `03f3067b57c82be83b27cb402e4e2c7884fbc49d820621f22a66820e23cecedc`
- scope:
  split-C cumulative prefix, not the complete QLinearAdd chain

## Affected causal cone

The exact local Git object database contains both commits. Read-only
`git diff e1fb0f7..0ccae91` confirms the QAdd-relevant changes:

1. `IGA_ROW_LC_Inbuffer`: single-register buffering becomes a FIFO with
   depth 128; output valid is `!fifo_empty` and input ready is `!fifo_full`.
2. `Array_Request_Manager`: the active read request expression changes from
   `array2arm_bp_post && !buf2arm_valid_hold` to `array2arm_bp_post`.
3. `Buffer_AG_Idx_Queue`: capacity `24 -> 32`.
4. `RD_Data_Channel`: capacity `32 -> 128`.
5. global request OOO/queue/tag depths: `16 -> 128`.
6. `SA_Inport` ping-pong adds the valid qualifier, but v35 `op_fp32_add`
   maps only `GA_PE.*`; this SA edge is not active for the exact v35 stage.

The targeted ARM metadata trace covers all `(ready, hold)` combinations:
the cloud equation still issues no request while the consumer is not ready,
and issues the masked request immediately when ready, including held-data
resume. Capacity traces cover old-1/old/new-1/new thresholds and prove
monotonic expansion. These traces do not run DUT data or tensor arithmetic.

## Frozen configuration receipt reuse

The final v35 rowpair receipt remains byte-bound:

```text
[0,16) U [16,32) = [0,32)
```

for both `Buffer0/MSE0` and `Buffer2/MSE1`.

- final address-bound JSON SHA:
  `ee499127939131a11597d2657b17f078fcc193253037c7a4da94103722b496e1`
- package bitstream SHA:
  `aec903e223a448dc007d4dcd57dc4801eac67f9ab85c6c6a528bb460b8d1b798`

No config/mapping/bitstream/execplan/SCA byte changed. Therefore
`CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001` and
`CDA-CONFIG-BOUNDARY-MICROTRACE-001` are `receipt_reuse/not_applicable`
for a new config release gate. The cloud-RTL impact microtrace is recorded
separately and does not repeat the seven frozen rowpair negative controls.

## Dynamic-only boundaries

The following temporal effects remain `DYNAMIC_ONLY_BOUNDARY`:

- IGA FIFO enqueue/dequeue ordering under backpressure;
- ARM request/read-valid/GA acceptance timing after the hold-gate change;
- expanded MSE/RD/global request queue occupancy and request-tag timing.

The exact v35 observer already returns the relevant low-overhead boundaries:
ARM request, Buffer read valid, MSE queue input/ready, MSE AG valid/ready,
pair queue write and pair AG handshake. The package runner contains no
server-RTL expected-SHA mismatch gate, so an actual/local identity
difference does not stop simulation.

## Machine result

Command:

```text
C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe tools/revalidate_qlinearadd_node0007_v35_cloud_rtl_causal_cone.py --repo Trassic2.0_RTL --zip artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_crow32_v35.zip --audit artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-server-package/final_zip_self_audit.json --mapping artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v30/mapping/op_fp32_add/mapping_review.json --cloud-report artifacts/rtl_sync/trassic_cloud_master_0ccae91_20260805/report.json --output artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-cloud-rtl-impact/report.json
```

Two deterministic runs both exited `0`.

Machine report:

- path:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-cloud-rtl-impact/report.json`
- bytes: `13487`
- SHA-256:
  `762f3f1304a456304828c0890235f4754dbec1758195108745e1dc001ecc3abf`

Validator:

- path:
  `tools/revalidate_qlinearadd_node0007_v35_cloud_rtl_causal_cone.py`
- bytes: `17379`
- SHA-256:
  `824a7d7cf3e0dcbe6410af158ae2cef76ce790bdcd3933373a0a78ee7dd74de9`

## Adjudication

```text
CLOUD_RTL_CAUSAL_CONE_REVALIDATION_PASS_NO_REBUILD
PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN
ZIP_BYTES_UNCHANGED=true
```

No new static blocker is opened. A formal return must bind the actual/cloud
compiled identity and prove split-C natural terminal, ARM/GA progress and
stage-local outputs. Identity mismatch alone must not block simulation.

## Rule confirmation

`RULE_CONFIRMATION`: the cloud-authority rule correctly treats the local/cloud
identity difference as non-blocking provenance while forcing a directed
operator causal-cone review. The changed-slice config rules correctly permit
byte-equal rowpair ledger reuse and avoid repeating numeric/W3/golden.
Claim boundary is static Git-diff/config/observer impact only; it does not
claim production compile, natural terminal, formal D, E3, E4 or E5.
