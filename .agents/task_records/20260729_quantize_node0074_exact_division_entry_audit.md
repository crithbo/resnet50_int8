# Quantize node0074 exact-binary32-division entry audit

Date: 2026-07-29  
Owner: QuantizeLinear / shared exact UINT8 tail  
Mainline return target: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## Scope and control boundary

- Audited only the real `r5:hwop-0074-00` / `node-0074`
  `flatten_473_QuantizeLinear` exact-division entry and its owned side of
  `node0072-D -> node0073 alias -> node0074-A`.
- Did not repeat node0004, 26-vs-25 singleton, node0072 Dequant, or node0073
  Flatten primitive tests.
- Did not modify `.agents/plan.md`, `.agents/rules/**`, or `rtl/**`.
- Did not inspect a server installation, upload, run, obtain a lease, or create
  a server package.
- Did not generate a target JSON, mapping, bitstream, execplan, or SCA.
- The delegated plan SHA
  `f9a3ce73baa73346c144f14bf005262f0b0caaf66d981da157a5a11c0a703183`
  is retained as historical read provenance. A later plan drift is not a
  semantic current-match gate.

## Real instance identity

- Request: `r5:hwop-0074-00`
- Input: `tensor-9b1363d3baf474c8`, float32 `[16,2048]`,
  byte strides `[8192,4]`, 32,768 elements / 131,072 bytes
- Scale: float32 bits `0x3cbf57ec`
  (`0.02335735410451889`)
- Zero point: uint8 `0`
- Output: `tensor-6fbd5707d5f08110`, uint8 `[16,2048]`,
  32,768 bytes
- Semantics:
  `saturate_uint8(RNE(binary32_divide(x, scale)) + 0)`

Typed lowering, model graph, frozen W3 input/output, active common/NDP/exact-tail/
Flatten rules, native configs, registry/handler/opcode sources, and REC
coefficients are current-match identities in the machine contract.

## Reuse accounting

Consumed without retest:

- node0072 config-only correctness contract, only for producer D geometry and
  accepted 28-slice physical-write evidence;
- node0073 physical View contract, only for metadata-only zero-copy alias
  semantics;
- shared exact-tail capability matrix and rounding discriminator, only for
  accepted capability taxonomy and prior gates.

`accepted_numeric_analysis_repeated=false`,
`accepted_primitive_retested=false`, and `node0004_analysis_repeated=false`.
The only new numeric work was path-specific: a sequential REC/MUL audit for the
formal node0074 scale and one frozen-W3 comparison.

## Native entry audit

No direct exact binary32 division entry exists in the audited native
configuration, opcode, typed-handler, or mapper surfaces.

- `prefill_sum_rec_fp32MN_fp32MN` and
  `decode_sum_rec_fp32N_fp32N` are fixed reduction-then-REC entries. They do not
  have node0074's elementwise computation boundary or shape.
- SFU `REC` is coefficient/LUT based, not an audited exact division opcode.
- `prefill_mul_fp32MN_fp32M_fp32MN` can supply a multiply structure, but
  composing a rounded reciprocal with a rounded multiplication is not
  binary32 division.
- `quant_from_buffer_int32MN_uint8MN` remains structure/primitive-only: its
  ingress is INT32 and it has no node0074 exact division or complete typed
  transport.

## Minimal same-scale contradiction

For the formal scale:

- `x=0x406cefe0` (`3.7021408081054688`)
- exact binary32 division:
  `0x431e8001 = 158.50001525878906`, RNE -> uint8 `159`
- rounded reciprocal `0x422b4095`, then binary32 MUL:
  `0x431e8000 = 158.5`, RNE -> uint8 `158`

This is a finite positive value in the legal node0074 input domain. It refutes
the sequential reciprocal/MUL replacement without relying on fused FMA or the
previous singleton.

On the frozen 32,768-element W3 tensor, exact division reproduces the formal
output. Reciprocal/MUL differs at 720 scaled float32 elements but happens to
have zero final uint8 differences. That coincidence is recorded as
non-authorizing and cannot establish full-domain operator equivalence.

## Endpoint ownership

The accepted metadata dependency remains:

- producer tensor `tensor-50c285690f899b1b`,
  float32 `[16,2048,1,1]`, strides `[8192,4,4,4]`;
- alias/consumer tensor `tensor-9b1363d3baf474c8`,
  float32 `[16,2048]`, strides `[8192,4]`;
- required node0074 A read: 32,768 elements / 131,072 bytes;
- node0073 performs no compute, allocation, or copy.

Because the first node0074 numeric capability is still absent, the six
node0074-owned integrated endpoint fields remain `null`:

1. `final_storage_identity`
2. `final_producer_base`
3. `final_view_offset`
4. `final_consumer_base`
5. `final_read_coverage`
6. `final_accepted_lifetime`

No provisional address or endpoint claim is allowed.

The sole canonical endpoint manifest is
`contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json`.
Only `owner_sections.QuantizeLinear` was appended. Its canonical content SHA is
`08b2e7fdc5a7e1b642b8dab45bc157a465342aceffd8d5ff331e52d8749c36ac`.
The Dequant producer section remains byte-semantically unchanged with canonical
content SHA
`e372f7b0fa434845a8199830c3c46a9467fc71d5687fa103750a86408191b371`.
The Flatten endpoint manifest remains a requirement/View projection and was
not modified or copied into a second fact section.

## Structured return

### RETURN_ANALYSIS

`FAIL_CLOSED_NO_EXACT_BINARY32_DIVISION_ENTRY`. There is no complete
configuration-only node0074 route. Nearest REC/reduction and MUL assets are
structure/primitive-only and do not implement exact binary32 division.

### BLOCKER_DELTA

- `B_QUANT_TAIL_EXACT_FP32_DIVISION=OPEN`
- `B_QUANT_NODE0074_EXACT_DIVISION=OPEN_NO_DIRECT_OR_EQUIVALENT_ENTRY`
- First unavoidable break:
  `exact_binary32_division_opcode_and_config_entry`
- FP32 ingress, signed/finite domain execution, typed handler, mapper, terminal
  readback, and final endpoint binding remain downstream/deferred; they cannot
  be used to skip the first break.

### RULE_DELTA_PROPOSAL

`NONE`. The active exact-tail rule already forbids replacing `x/scale` with
rounded reciprocal multiplication without exact-equivalence proof. The new
counterexample is instance evidence, not a missing public rule.

### PACKAGE_RELEASE

`NONE`. `candidate_release=false`; target and server outputs are absent. The
existing node0004 package identity was neither consumed nor modified.

## Assets

- Contract:
  `contracts/operator_config/quantize_node0074_exact_division_entry_audit_v1.json`
- Validator library:
  `resnet50_pipeline/quantize_node0074_exact_division_entry_audit.py`
- CLI:
  `tools/validate_quantize_node0074_exact_division_entry_audit.py`
- Tests:
  `tests/test_quantize_node0074_exact_division_entry_audit.py`
- Report:
  `artifacts/operator_config_validation/r5-quantize-node0074-exact-division-entry-audit-v1/report.json`

Validation:

- CLI: pass
- Unit tests: 5/5 pass
