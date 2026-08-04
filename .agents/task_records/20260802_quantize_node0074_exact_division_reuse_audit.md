# QuantizeLinear node0074 exact-division reuse audit

Date: 2026-08-02  
Owner: QuantizeLinear / shared exact UINT8 tail  
Mainline return target: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

- Real target remains `r5:hwop-0074-00`: FP32 `[16,2048]` to UINT8
  `[16,2048]`, scale bits `0x3cbf57ec`, zero point `0`.
- The current 55-template native `ndp-sim/jsons` corpus exposes no division
  template or division opcode. Its only quantize template is
  `quant_from_buffer_int32MN_uint8MN` and has INT32 ingress.
- The encoder exposes `rec=17` but no division opcode. The native
  Quantize handler remains a placeholder and the mapper registry explicitly
  excludes the quantize template.
- The local RTL consumer implements REC as breakpoint/LUT
  slope/intercept/MAC followed by exponent reconstruction. It is not a
  correctly rounded binary32 divider.
- No accepted W3/golden, Flatten, Dequant, or counterexample primitive was
  rerun. The accepted same-scale counterexample was identity-bound only:
  `x_bits=0x406cefe0`, divide path UINT8 `159`, reciprocal-multiply path
  UINT8 `158`.
- Therefore no complete node0074 target, mapping, bitstream, execplan, SCA,
  local E2, or server package was generated.

## REUSE_CLASS_AND_BOUNDARY

Reuse class is fixed to `STRUCTURE_OR_PRIMITIVE_ONLY`.

Allowed reuse from
`ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json` is limited to matching
LC/MSE/Buffer/GA field structure, two-PE transport topology, raw constant
transport, nearest-even integer decode structure, and UINT8 saturation
structure.

Forbidden reuse includes treating INT32 ingress as FP32 ingress, treating the
rank-3 source schedule as the rank-2 target schedule, treating the placeholder
handler or absent mapper as complete, or replacing `x/scale` with
`x*reciprocal`/reciprocal-FMA.

## FIRST_DIVERGENCE

- Local blocker: `B_QUANT_NODE0074_EXACT_DIVISION`
- Shared blocker: `B_QUANT_TAIL_EXACT_FP32_DIVISION`
- First missing capability: `EXACT_BINARY32_DIVIDE_RNE`
- Missing interface: one FP32 input lane plus the exact scalar scale bits must
  produce the RN-even binary32 quotient `x/scale` with one rounding point for
  all finite signed producer-domain inputs.
- First acceptance gate: a config-bound implementation must return exact
  quotient bits before the already separated RNE/decode/saturation tail.
- Acceptable proof is either a direct opcode/RTL implementation or a complete
  composed algorithm with full legal-domain bit proof and the accepted
  counterexample. Host-precomputed scaled, rounded, saturated, or final tensors
  remain forbidden.

Typed handler, mapper, shape/tail, materialized roundtrip, and terminal/readback
remain deferred behind this first numeric capability.

## ENDPOINT OWNERSHIP

The canonical endpoint is
`contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json`.
Only `owner_sections.QuantizeLinear` was refreshed to bind the v2 reuse audit.
The DequantizeLinear and Flatten/View owner sections were not changed. All six
QuantizeLinear consumer-owned endpoint fields remain null; provisional
addresses, coverage, and lifetimes remain forbidden.

## BLOCKER_DELTA

No blocker is closed. The earlier generic exact-division blocker is sharpened
to the minimum hardware/config interface `EXACT_BINARY32_DIVIDE_RNE`, with
REC/MUL and iterative-correction candidates explicitly rejected or absent in
the current native transport.

## RULE_DELTA_PROPOSAL

None. Current rules already require the fail-closed behavior and prohibit
reciprocal substitution.

## PACKAGE_RELEASE

`NONE`. No target or server package was generated, inspected, uploaded, or run.
No server lease was acquired.

## Read receipts and machine evidence

Current-match rule receipts:

- `.agents/rules/生成前必读索引.md`:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/算子配置规则.md`:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

Primary artifacts:

- Capability contract:
  `contracts/operator_config/quantize_node0074_exact_division_reuse_audit_v2.json`
  SHA256
  `7892b1dc2b54161ee2d5cab3c033d2a72bec19bbabaf269a38099674e2e45bdf`
- Canonical endpoint SHA256
  `e80d098511ac3689abcf6901a633c895f105ee8f2e6aaca2b2185d1440673df4`
- QuantizeLinear owner-section content SHA256
  `4e6844d214f4d1cccde8807a38130ace3f14df691a5abd3f1bec1e2b5e758d92`
- Validator module SHA256
  `825d8e2b11791dae274368433a4b4e667c2d1ba2fc10060ad04eb4593d5e985f`
- Validator CLI SHA256
  `c6f6acccd547d017f3b44270a860fc66ecf654949292855dd127ba0ba0c418eb`
- Test SHA256
  `5462b7f4e8fa6439902cb084d6702e2f67fa541e0b0785b4f24ab686821d5a8a`
- Machine report:
  `artifacts/operator_config_validation/r5-quantize-node0074-exact-division-reuse-audit-v2/report.json`
  SHA256
  `9b9cc0229f7d07f801298767fb2b1f683960fa5134366526b3f534c835d10650`

Validation commands:

```text
python tools/validate_quantize_node0074_exact_division_reuse_audit.py
exit_code=0, passed=true

python -m unittest tests.test_quantize_node0074_exact_division_reuse_audit -v
exit_code=0, tests=5, failures=0, errors=0

git diff --check -- <QuantizeLinear scoped files>
exit_code=0
```
