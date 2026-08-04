# 2026-07-29 hardware-available assumption replan

## User direction

The mainline shall assume the server-side RTL is compilable and that the hardware
semantics required by the first Conv are available. Cloud-repository cleanup and
the hardware team's later RTL maintenance are no longer local prerequisites.
Local work shall continue toward the whole ResNet50 and may generate the first
complete Conv server test package.

## Mainline adjudication

- `HARDWARE_SEMANTICS_ASSUMED_AVAILABLE=true`.
- Cloud conflict markers, a final cloud RTL SHA, and server-side RTL identity
  inspection are deferred; they do not block local config generation.
- This is an execution assumption, not E4/E5 evidence. Formal counters change
  only after a real complete return is accepted.
- All historical node0004 materialized assets remain untrusted negative history.
  Fresh generation may consume only the typed request/lowering, formal ONNX/W3,
  active rules, and current native tools/templates authorized by those rules.
- The node0004 logical W3 domain audit covers 3,211,264 outputs and 51,380,224
  dot4 groups with zero mismatch under the corrected carry semantics. The default
  accumulate path is therefore fresh normal four-lane SA.
- One-product-lane plus DataC psum is retained only as a configuration fallback
  when a final physical packing/domain audit fails. The SA-product-to-GA-tree
  composite design is demoted to a later diagnostic fallback.
- Signed INT32-to-FP32 is assumed fixed. The node0004 output tail shall use an
  explicit two-stage route with a separately rounded FP32 multiply, scratch and
  barrier before RNE/saturation. The historical raw `max(acc,0)` route is not a
  current prerequisite.
- MaxPool continues to reuse the Git original JSON unchanged. Historical issues
  5/6/7/8 are deferred until a real operator or whole-network first divergence
  selects them.
- Work may proceed through `PACKAGE_READY_NOT_RUN`. No server file/name/RTL
  inspection, upload or run is authorized by this record.

## Execution order

1. Re-read all generation rules required by the index.
2. Fresh-materialize node0004 normal four-lane INT32 accumulate.
3. Fresh-materialize and validate the two-stage exact UINT8 tail.
4. Close complete-node JSON, mapping, bitstream, execplan/SCA,
   address/lifetime, config-bound inverse and full W3 comparison.
5. Read package rules and generate the node0004 server test package.
6. After node0004 succeeds, expand Conv by schedule signature while reusing
   accepted non-Conv operators without retesting.

## Plan receipt

- `.agents/plan.md`
- SHA-256:
  `43e7fcf2224f9bf88fb6ddf99a69360e3a5a60f181304d050c3078d1600b3c58`

## Published rule deltas

The historical local-RTL contradictions remain recorded, but they no longer
block this node0004-only execution profile:

- `.agents/rules/INT8_SA点积专项规则.md`
  - rule: `CDA-SA-NODE0004-ASSUMED-FIXED-HARDWARE-001`
  - SHA-256:
    `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/精确UINT8量化尾专项规则.md`
  - rule: `CDA-QUANT-TAIL-NODE0004-ASSUMED-SIGNED-INGRESS-001`
  - SHA-256:
    `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- `.agents/rules/RequantizeUint8算子配置规则.md`
  - rule: `CDA-REQUANT-NODE0004-DIRECT-SIGNED-TWO-STAGE-001`
  - SHA-256:
    `5fcd1c9d2f6fa6dd193e369412c46c16b7bd087b570cc607aa0d0f06ba4c7555`

These deltas authorize fresh local materialization and package generation only.
They do not assert a verified server RTL identity and do not change E4/E5 counts.
