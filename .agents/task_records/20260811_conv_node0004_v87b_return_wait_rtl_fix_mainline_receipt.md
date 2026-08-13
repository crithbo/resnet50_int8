# Serialized Conv node0004 v87b formal return / WAIT_RTL_FIX mainline receipt

- role: `family.conv.serialized`
- owner thread: `019ff02d-901b-7f70-a9da-f54e268b5bbe`
- owner epoch / registry epoch consumed: `2 / 6`
- termination: `WAIT_RTL_FIX`
- successor / package release / server action: none

## Previous progress and current result

v85b closed production compile exit `2` to two package-local observer XMREs. v86b repaired the observer and
structured-first-error surfaces but was withdrawn for old no-wave semantics. v87b preserved that repair and
added mandatory full-hierarchy unbounded VPD.

The v87b formal return proves production compile exit `0`, simulation started and process exit `0`; the XMRE
blocker is closed. No natural terminal was observed and formal D remained `0/320`.

- `LAST_PROVEN_GOOD=PRODUCTION_COMPILE_PASSED_SIM_STARTED_AND_C0_DESCRIPTOR_DATA_PATH_ADVANCED`
- `FIRST_DIVERGENCE=SLICE13_GROUP1_MSE4_BUFFER_ACK_OUTPUT_BIT1_PERSISTENTLY_DIFFERS_FROM_SAME_INSTANCE_INLINE_RHS`
- `HANG_ROOT_CAUSE=FUNCTIONAL_RTL_BUFFER_ACK_PUBLIC_OUTPUT_DOES_NOT_CONFORM_TO_INLINE_RHS`

Thirteen complete sequences and 65 binary-known exact-instance events remain mismatched at the stable late
sample; each sequence retains XOR bit1. The temporal ledger then records memory residual `0`, buffer residual
`4`, eight buffer enqueues and seven dequeues after memory terminal. The canonical hang boundary is
`D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH`, with no qualified delta or slice finish.

## Formal receipts

- return: `C:/Users/15383/Downloads/r5_n4_hw_v87b_mandatory_vpd_r1786458170706574446_1205339_return.zip`
- bytes: `11249796`
- SHA-256: `793163afeea31675192429f0f4c39021299b594d487ed4fa4b4e0ca62b718148`
- report: `outputs/conv_node0004_v87b_formal_return_r1786458170706574446_1205339/report.json`
- report bytes/SHA-256: `9114 / 07916cc49e3e95fda724d3296ebcec9a4e9129f9d45957fdd64323145b2ef7ce`
- family mainline receipt: `outputs/conv_node0004_v87b_formal_return_r1786458170706574446_1205339/mainline_receipt.json`
- waveform extract: `outputs/conv_node0004_v87b_formal_return_r1786458170706574446_1205339/waveform_extract/waveforms/compile/sim_results/wave.vpd`

Return exact-set, package/return identity, compile-core and mandatory VPD collection/return checks pass. The
VPD is `PARTIAL` because the execution ended at the diagnostic stall; no local semantic VPD decoder is
installed, so signal-value claims are bound to exact runtime observer decisions rather than an invented VPD
decode.

## Independent completeness defect and identity boundary

The frozen legacy `buffer_input_ack_equation` parser still targets slice0/group0 while the exact realtime target
is slice13/group1. It produced zero events, omitted its parser receipt and failed the required plugin closed.
This package-local return-completeness defect is independent of the 65-event receipt-bound phase decision and
does not change the functional root classification.

The formal return binds the production Makefile, package identity and package-local observer sources, but its
compile-source receipt does not hash the actual server DUT `Buffer_AG_Idx_Queue.sv`. The runtime public-net/RHS
contradiction is proven; relating it byte-for-byte to the current authorized local equation remains an explicit
source-identity boundary for any later RTL repair.

## Storage and disposition

v87b was moved atomically from pending to
`artifacts/operator_config_validation/r5-server-test-packages/tested/conv_serialized_node0004/r5_n4_hw_v87b_mandatory_vpd/`.
The serialized pending set is empty and the global storage audit passes.

A package/runner-only successor cannot repair the closed public-net functional leaf. Functional RTL was frozen
for this round, so the correct terminal state is `WAIT_RTL_FIX`. Any repair requires explicit functional RTL
authorization and must first preserve or independently establish the actual compiled DUT source identity.

Config, numeric, workload, golden, functional RTL and target diagnostic remain unchanged. E3/E4/E5 remain
false; no new package, upload, lease or server action is authorized by this receipt.
