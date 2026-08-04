# QuantizeLinear node0074 inventory and fail-closed selection

Status: `BLOCKED_BEFORE_GENERATION`

This task selected real ResNet50 instance `node-0074 / hwop-0074-00`
(`flatten_473_QuantizeLinear`) as the family representative. It consumes
`float32[16,2048]` from `node-0073 Flatten`, uses scalar float32 scale
`0.02335735410451889` (`0x3cbf57ec`) and scalar uint8 zero-point `0`, and
produces `uint8[16,2048]` for `node-0075 QLinearMatMul`.

The selection is higher-value than node0000 for a first closure because it has
only 32,768 elements, needs no nonzero-zero-point support, and directly closes
the classifier MatMul input boundary if a valid hardware implementation is
found.

## Stop-gate result

No QuantizeLinear-specific rule exists under `.agents/rules/`. The typed
request itself sets `formal_target_instance_allowed=false` and
`candidate_files_may_satisfy_request=false`. The family catalog is
`related_template_evidence_available_emitter_blocked`.

The trusted upstream
`ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json` is an
`int32 -> uint8` hardware oracle. Its GA inport enables `int32tofp32`; therefore
it cannot substitute for the selected ONNX `float32 -> uint8` instance. The
native control-register handler is explicitly a placeholder with rank-3
geometry assumptions, and the address-remapping test asserts this operator is
not registered.

Under the mandatory read index and common configuration rules, these facts
activate the generation stop gate. Consequently this task did not invent
occurrence/bank/address/lifetime values, did not emit a final JSON, did not
rebuild mapping/bitstream/execplan/SCA, and did not create a server package.

## BLOCKER_DELTA

- Add `B_QUANT_SPECIALIZED_RULE_MISSING`: mainline must adjudicate a
  QuantizeLinear-specific rule covering qdomain, exact rounding order,
  saturation, zero-point, fp32 ingress, layout, tail, terminal/readback and
  release gates.
- Keep `B_LAYOUT_APPROVAL`, `B_EXECPLAN_TYPED_TRANSPORT`,
  `B_QUANT_FP32_INPUT_PATH`, `B_QUANT_INPUT_DTYPE_PATH`, and
  `B_QUANT_ROUNDING_EXECUTION`.
- Add `B_QUANT_NATIVE_HANDLER_PLACEHOLDER`: the active native handler is not a
  complete shape/parameter consumer.
- Add `B_QUANT_MAPPER_REGISTRY_MISSING`: the active mapper registry does not
  include `quant_from_buffer`.

## RULE_DELTA_PROPOSAL

Mainline should create a QuantizeLinear专项 rule only after it has evidence for
an actual fp32-input hardware route. The rule should explicitly forbid treating
`quant_from_buffer_int32MN_uint8MN.json` as a direct ONNX QuantizeLinear
template; it may be used only as a field-semantics oracle until fp32 ingress and
rounding are independently proved. This proposal does not modify public rules.

Machine-readable evidence:
`contracts/operator_config/quantize_node0074_inventory_v1.json`.

Package state: `NOT_BUILT`, `candidate_release=false`, `rtl entries=0`.
