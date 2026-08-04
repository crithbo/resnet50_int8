# GAP v28 / Conv v26 return dispatch and whole-network gap overview

## Mainline and input receipts

- mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- GAP owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- Conv/SA/MatMul owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- plan before dispatch SHA256:
  `e37ee58cf9a4ac98423b066516ee610054f940505c00a8e3fb2bc921a412c583`

GAP return:

- path:
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n71_gap_v28_ga_mse4_final_pair_diag_return.zip`
- bytes: `129696`
- SHA256:
  `875a9ec0ade4f1957025e0b7cefb0e843830f6dca57db8c078d462c5df40b0ff`

Conv return:

- path:
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_hw_v26_transout_threshold_fix_return.zip`
- bytes: `96874`
- SHA256:
  `2a3e041737376a8afdfcb70d85e30c9f4c7fbc12d5bdad94c9ec2c9b7fa78d68`

Both exact source packages leave the runnable queue and become
`RETURN_CONSUMED_ANALYSIS_IN_PROGRESS_DO_NOT_RERUN`. Missing adjacent
sidecars may only be replaced by the user's external transport attestation;
all internal return gates remain mandatory.

## Dispatch

The GAP owner was instructed to close
`B_GAP_NODE0071_GA_FINAL_PIPELINE_TO_MSE4_REQUEST_WDATA_PAIRING_PENDING_LEAF`
from the v28 return and generate a fresh fix if unique, otherwise a narrower
low-cost diagnostic successor.

The Conv owner was instructed to validate the v26 threshold fix, old
terminal-ignore boundary, DUT natural completion and 320 formal-D outputs.
The invalidated occupancy claim must not be revived. A fresh fix or narrower
diagnostic successor is mandatory unless a formal terminal disposition is
reached.

Both owners must proactively report RETURN analysis, successor identity,
blocker delta and evidence-backed rule feedback to the current mainline.

## Whole-network operator-family gaps

The frozen model has 78 ONNX nodes and 133 typed hardware stages.

### QLinearConv / shared INT8 SA

- 53 Conv nodes share the SA arithmetic route.
- node0004 is the only fully materialized representative currently in server
  return analysis.
- the other 52 Conv instances still require fresh multiplier,
  allocation/address/lifetime, schedule, tail and final artifact
  materialization.
- serialized one-nonzero-product-lane fallback is proven only for the frozen
  node0004 accumulate identity. It costs about four times the occurrences
  and is not a family-wide E2/E4/E5 release.
- node0004's signed-ingress/tail authorization does not automatically release
  the 20 nonzero-zero-point Conv tails.

### QLinearAdd

- 17 nodes have reusable stage0 structure/semantics.
- node0007 remains the representative dynamic closure.
- current v24 executes B-dequant only; A/B/C/D true workload split generation
  is in progress under a separate mainline authorization.
- the remaining instances still need integrated allocator/address/lifetime,
  tail and final 133-stage binding; representative diagnostics do not create
  17 formal node passes.

### GAP

- the INT32-MAC sum bypass has local E2 and has already produced multiple
  server diagnostic identities.
- v28 has now returned and is being analyzed. It is therefore not waiting for
  initial package generation.
- complete GAP, natural terminal and formal D remain open.

### MaxPool

- the single node is governed by the user's native ndp-sim reuse exception.
- v5 has been consumed and deliberately deferred; no generic successor should
  be generated and no new E4/E5 claim is made.

### Dequantize / View / Quantize

- Dequantize node0077 is the only frozen E4/E5 node.
- the node0072 → node0073 View → node0074 chain has an approved equivalent
  rewrite that removes node0072/node0074 arithmetic and aliases the original
  UINT8 storage to node0075 A.
- the rewrite is valid only for the frozen instance; the generic exact-divider
  capability remains open.
- a standalone Quantize test package would be semantically meaningless
  because the approved result is a cross-node alias, not a new Quantize
  computation.

### QLinearMatMul node0075

- this is the first active integration gap for the approved Quantize bypass.
- the active toolchain lacks registered
  `MatMulInt32Accumulate`/`QLinearMatMul` op-json handlers and a final consumer
  materializer.
- node0075 A occurrence/read coverage, visibility barrier, accepted lifetime,
  mapping, bitstream, execplan and SCA remain unmaterialized.
- this task has been queued to the Conv/SA/MatMul owner after the v26 return
  closure. A server package is allowed only after a real local materializer/E2
  loop closes.

### Requant / exact UINT8 tails

- the tail is a shared hardware capability consumed by Conv, Add, GAP,
  Quantize and MatMul, not an independently completed whole-network family.
- node0004 has an instance-specific authorized two-stage tail.
- the remaining Conv tails and the MatMul nonzero-zero-point rank-2 tail need
  fresh binding; generic division, rounding-domain, topology, handler and
  mapper blockers remain where applicable.

### Whole-network integration

- final global allocator/address/alias/lifetime, complete artifact references,
  133-stage execplan/SCA assembly and first whole-network config-bound
  comparison remain open.
- two plan references to `33-stage` were corrected to `133-stage`, matching
  typed lowering and the frozen reuse/lifetime contracts.

## Bypass package readiness

- GAP INT32-MAC bypass: already testable; v28 return is under analysis.
- Conv serialized fallback: testable only for node0004; v26 return is under
  analysis. Family-wide expansion remains a high-cost materialization gap.
- Quantize node0074 identity fusion: equivalence is approved, but no standalone
  package should be generated. The first legal test package must include the
  materialized node0075 consumer path.
- Dequant/View alias components: no independent compute package is needed.
- Requant/general exact-tail bypass: not ready for a generic package; only
  explicitly authorized instance paths may be packaged.

No functional RTL, server upload/run or lease action was authorized by this
dispatch.
