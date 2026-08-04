# GAP INT32 sum-stage config-only local E2 主线裁决

日期：2026-07-27

## 裁决

接受 `r5:hwop-0071-00` INT32 sum 子阶段为
`CONFIG_ONLY_CORRECTNESS_BASELINE` / local E2：

- 六级非 transout `int32_mac(A,1,C)`：
  `49→25→13→7→4→2→1`；
- 每级显式 INT32 scratch、reload 与 same-mask barrier；
- occurrences/slice：
  `[8192,4096,2048,1024,512,256]`；
- 最终 D coverage：
  `[262144,131072,65536,32768,16384,8192]` bytes，全部 exact contiguous；
- config-bound simulator 对真实 W3 输入逐 bit 等于独立 sum golden，输出 SHA
  `f838df652cadb27110ed79084f49fd7e80445277d497e0d6e019c49132b73117`，
  range `[0,2477]`；
- 六份 final JSON 只有 planner-owned base 变化，non-base diff=0；
- 两个隔离 mapping 的核心语义产物逐 SHA 相同；
- replay 只复制正式 node0070 uint8 output，不包含 host-precomputed internal/final
  tensor。

该 baseline 只覆盖 GAP 的 INT32 sum hardware stage，不是完整
QLinearGlobalAveragePool 或完整 ONNX 节点。shared exact UINT8 tail 未物化，因此完整
GAP local E2 和 target 计数不增加。

## stage1 地址规则

发布 `CDA-GAP-INT32MAC-STAGE1-ALIGNED-EVEN-ODD-001`：

- 8B C8 pair 不得使用 `C_base=A_base+8`，因为 RTL 丢弃 base 低 4 位；
- A/C 使用同一 16B-aligned base 和独立 LC branch；
- A 取偶数 index、C 取奇数 index，byte stride 8；
- 必须证明 equal cardinality、ordered pairing、padding、独立 branch roots、
  `[0,4,...,28]` buffer columns 和最终 D coverage。

同时发布 `CDA-GAP-INT32MAC-SUM-STAGE-LOCAL-E2-001`，只批准当前冻结 sum-stage
identity。

## 仍开 blocker

- `B_GAP_INT32MAC_DYNAMIC_DUAL_STREAM`
- `B_GAP_INT32MAC_STAGE_BARRIER` 动态 drain/visibility
- `B_GAP_INT32MAC_FORMAL_READBACK`
- native composite handler/pipeline integration
- shared exact UINT8 tail 的 full-domain、ordered-rounding、transport、terminal、
  typed binding 与 mapper 门
- `B_GAP_NODE0071_TO_NODE0072_INTEGRATED_BINDING`：完整 GAP 最终 uint8 output 尚未
  materialize，node0072 当前只重放冻结 producer tensor；未来必须绑定同一最终
  storage/address/coverage/lifetime，才能计连续子图 E2

旧 16-slice/512-line 动态 readback 合同不得外推到当前 28-slice local baseline。

## 计数与身份

- 新增 config-only hardware-stage baseline：1；
- 新增完整 ONNX 节点 local E2：0；
- 正式 ResNet 三方节点：仍为 1/78；
- contract file SHA：
  `15318caf31dc13e702b66c9b0e7849a844210a5a887ef52cf3d84610e04be697`
- contract semantic SHA：
  `6756d6aeae24418847ad9fc32beaedb9826dd64699379e12ad5f18892a4ba32d`
- validation report：
  `b19157bc875d6d28b0ac8014e55abe94d0e6044227346019a64541b3d09bc019`

`PACKAGE_RELEASE=NONE`；server action/lease=0；RTL 修改=0。
