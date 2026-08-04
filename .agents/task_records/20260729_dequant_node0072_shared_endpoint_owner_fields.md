# Dequant node0072-D shared endpoint owner fields

日期：2026-07-29  
owner：DequantizeLinear / `node-0072 / r5:hwop-0072-00 / D`  
状态：`REUSE_ACCEPTED_FOR_INTEGRATION`；shared endpoint 仍未闭合

## 边界与复用声明

- 未重复 node0072 数值分析、golden、operator-only E2、config-bound simulator、
  mapping、bitstream 或 execplan 生成。
- 消费并只读复用冻结 node0072 local E2：
  - `contracts/operator_config/node0072_dequant_config_only_correctness_baseline_v1.json`
    @ `cf5172db59a0a7c294e49445f63cd7c61919c3aa4640af180799d2dcef42c60f`
  - `artifacts/operator_config_validation/r5-dequant-node0072-config-only-e2-v1/local_e2_report.json`
    @ `50e30f52bcc95fb3f3e89b2690bc163c77b4de3d77474dd9fecb569ed5176a43`
- 未消费或修改 node0077、node0004 package、服务器文件、功能 RTL 或其他算子族资产。
- 未修改 `.agents/plan.md` 或 `.agents/rules/**`。

最终读取收据：

| 文件 | SHA-256 |
|---|---|
| `.agents/plan.md` | `f9a3ce73baa73346c144f14bf005262f0b0caaf66d981da157a5a11c0a703183`（第0/0.1节；mutable provenance） |
| `.agents/rules/生成前必读索引.md` | `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f` |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` |
| `.agents/rules/DequantizeLinear算子配置规则.md` | `f8cf7d2a041426f2b3348f3d02b570e3e559fe1a77c643a8393e77a2583e15a1` |
| `.agents/rules/Flatten_View算子配置规则.md` | `28ba3a92fecbb83149d494867429c34aa3124040a5c59fe99c4b9481feb3b7ee` |
| reuse policy manifest | `c8886c946a15e281e2b9fc40c3e37523cc00d3aab330131572887f3d64de6960` |

## RETURN_ANALYSIS

创建共享 owner-partition manifest：
`contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json`。
本轮只写 `owner_sections.DequantizeLinear`；Flatten/View 与 QuantizeLinear section
仍缺失，不替其他 family 填值。

Dequant-owned storage identity 已冻结为：

```text
r5:activation:node-0072:D:tensor-50c285690f899b1b:
slice-sharded-28x4736-v1
```

owner 是 `r5:hwop-0072-00:D`，byte offset 为 0，physical address space 为
`NDP_PER_SLICE_DDR`。最终 D base：

```text
D_base(slice) = 0x000004a0 + (slice_id << 25), slice_id=0..27
```

28 个 base 从 `0x000004a0` 到 `0x360004a0` 已在 manifest 完整枚举。每片 allocation/
final written coverage 为 4,736 bytes；总 physical write 为 132,608 bytes。

有效逻辑 tensor：

```text
tensor = tensor-50c285690f899b1b
dtype  = float32
shape  = [16,2048,1,1]
strides(bytes) = [8192,4,4,4]
valid span = 131072 bytes
```

slice0..26 各含 4,736 valid bytes；slice27 含 3,200 valid bytes 和 1,536 bytes
physical padding。padding 为 `0x00000000`。logical inverse complete/unique。

冻结 local-E2 write/completion evidence：

- static validator completion path accepted = true；
- execplan start 与 28 片 D address programming accepted = true；
- config-bound physical D writes complete = true；
- dynamic hardware final write accepted = false；
- integrated node0072→node0073 completion accepted = false。

visibility/lifetime owner contract：

- storage 只有在 node0072 final D write accepted 且 node0072 completion accepted 后
  对消费者可见；
- allocation owner 始终为 node0072 D，Flatten 不得 allocate/relocate；
- storage 必须保持到 node0074 final A input-data accepted 且无 pending/replayed read；
  无该事件时保守保持到 node0074 completion accepted；
- shared multi-operator barrier/allocator/execplan 尚未物化，状态为
  `DEFERRED_TO_INTEGRATION`。

Flatten/Quantize 共同消费时必须匹配同一 storage ID、28 片 base、offset=0、
131,072 valid bytes；Flatten 输入 strides `[8192,4,4,4]`，输出 strides `[8192,4]`。

addressed identities：

| 资产 | SHA-256 |
|---|---|
| addressed graph | `2c9cf00cd6ac03ac2f09236a4868d7b2fb6bd61f3e48a18de13d3f4630a3d7d1` |
| final address-bound JSON | `de212d8d49bc963bc08a5691879433c165ef2aa938aa2581b56c25e75a92da50` |
| execplan | `fdcdd46b878cdf7582b072ec1438a0211a01f34bf7245a280ea6dd1e7e322687` |
| SCA | `a1131970cc29df9baf7e0186f8fdc5e00785681dd6c05d2592ae75cf7a61fc2a` |
| SCA_D | `68e6cf00f09bc16ebdfddab72b63b9f3cb4fd0d3a4d8e3a80bb06162a09ff1ae` |
| layout evidence | `4a8d3ac9ef7f965b944ef8d116b324f2229dabdd86b9b39a7699fd984f55b61a` |

manifest SHA-256：
`f42d5829fd3cba55d915859b300f886b64025a5f966f4fe978b738b22cb611e9`。  
Dequant owner section SHA-256：
`e372f7b0fa434845a8199830c3c46a9467fc71d5687fa103750a86408191b371`。

静态 integration-binding validator 结果：

```text
valid=true
immutable_source_count=6
slice_count=28
logical_valid_bytes=131072
physical_written_bytes=132608
physical_padding_bytes=1536
numeric_analysis_repeated=false
operator_e2_retested=false
integrated_endpoint_closed=false
```

定向 manifest/identity 负向测试 6/6 PASS；仅检查 storage/base/coverage/claim drift，
不是算子数值复测。

## BLOCKER_DELTA

没有跨 family blocker 被本任务单方面关闭。

- `B_DEQUANT_NODE0072_TO_NODE0073_INTEGRATED_BINDING`：Dequant producer-owned
  storage/base/offset/coverage/identity 字段已补齐；其余 shared allocator/execplan、
  visibility/lifetime 与 consumer section 继续 `DEFERRED_TO_INTEGRATION`。
- `B_GAP_NODE0071_TO_NODE0072_INTEGRATED_BINDING`：保持，属于 upstream edge。
- node0072 四项 production/integrated blocker 保持。
- `B_VIEW_PRODUCER_ALLOCATION` 现在已有可消费的 Dequant section，但是否关闭由
  Flatten/View owner 与 cross-owner validator 裁决。
- node0074 exact division 与 accepted read endpoint 仍由 QuantizeLinear owner。

## RULE_DELTA_PROPOSAL

`NONE`。现有 reuse-first、Dequant node0072 local-E2 与 View physical identity/
coverage/lifetime 规则足以约束本轮 owner section。

## PACKAGE_RELEASE

```text
PACKAGE_RELEASE=NONE
server_package_generated=false
server_files_inspected=false
server_upload_or_run=false
server_lease=false
functional_rtl_modified=false
```

## 新增资产

| 资产 | SHA-256 |
|---|---|
| shared endpoint manifest | `f42d5829fd3cba55d915859b300f886b64025a5f966f4fe978b738b22cb611e9` |
| validator module | `4e2ed732a6db5ed65a6f955a092f4da8a23213ccf06ecb73f92f587fa93665ea` |
| validator CLI | `b698040668316980855b9dd9789039cbaa7fe82b0cc882b0b127c6c322775f40` |
| validator test | `51b41b54e38652ce5bc2d9a73c233f733a6e624d8acd5cdf0f4681929d197a06` |
