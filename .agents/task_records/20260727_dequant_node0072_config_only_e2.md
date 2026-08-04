# DequantizeLinear node0072 config-only local E2

日期：2026-07-27  
算子族：DequantizeLinear  
实例：`node-0072 / hwop-0072-00 / r5:hwop-0072-00`  
状态：`CONFIG_ONLY_CORRECTNESS_BASELINE`

## 1. 边界与读取收据

- 只新增 Dequant node0072 generator、validator/test、静态配置、机器合同和本 task record。
- 未修改 `.agents/plan.md`、`.agents/rules/**`、`rtl/**`、node0077 冻结资产或其他算子族资产。
- 未生成服务器授权包，未上传、未运行服务器，未消费服务器回传或服务器身份。
- node0077 正式三方闭环保持冻结；本记录不重做、也不扩大其声明。

最终物化读取收据：

| 文件 | SHA-256 |
|---|---|
| `.agents/agent.md` | `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0` |
| `.agents/plan.md` | `a1e19c6e84360641205836f6fa0b172fc0405472b8b2dfdc4c580cc2e0875516`（mutable provenance） |
| `.agents/rules/生成前必读索引.md` | `3940dc4d6f6d0b5d52347acd6fe5655281562dc09d4082c298cf70c7dbfb4f19` |
| `.agents/rules/算子配置规则.md` | `407fc0320d0587c362730c74e9b1d87cbd8e2ab686051173ceacadb6ac31c2cc` |
| `.agents/rules/NDP硬件字段语义.md` | `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59` |
| `.agents/rules/DequantizeLinear算子配置规则.md` | `76c66fb19268061caaeafca5ba2899017f6f0c95326a6350c5fb12f18e710dd2` |
| `.agents/rules/DequantizeLinear原子动态合同规则.md` | `cc9e5215d92e55b7440a07954503586c9a6d50f56fe505595341c0ba71358d85` |

`Flatten_View算子配置规则.md` 未读取：本任务只交付 node0072 storage handoff，不拥有
node0073 Flatten/View 解释、物化或放行。

## 2. 实例差异与数值域

| 项目 | node0072 | node0077/v6 参考 |
|---|---|---|
| logical shape | `[16,2048,1,1]` | `[16,1000]` |
| scale bits | `0x3cbf57ec` | `0x3e01622d` |
| zero point | `0` | `60` |
| hardware CWH | `[16,74,1]` | `[16,47,1]` |
| occurrence/slice | `74` | `47` |
| D lines/slice | `296` | `188` |
| GA topology | 4 ADD → 4 MUL | 4 ADD → 4 MUL |

node0077 专项规则只作结构参考，未把 node0077 的 qparam、shape 或正式动态批准跨实例复用。

真实 node0072 输入为 `uint8[16,2048,1,1]`，32768 元素；W3 域内：

- two-stage GA ↔ W3 golden：0 bit mismatch；
- single multiply ↔ W3 golden：0 bit mismatch；
- two-stage ↔ single multiply：0 bit mismatch；
- logical output SHA-256：
  `9430e90815858319eb2e08f610a54779bb12a78b7313ece27a92c5042d08018e`；
- NaN count：0；padding D 全为 `0x00000000`。

## 3. BYPASS_ANNOTATION

`bypass_reason`：
复用 node0077 已闭合的两级普通 GA 拓扑，因为 node0072 typed target 明确拒绝 standalone
native/handler、typed transport 和正式 layout 路径。

`contradicted_or_missing_native_path`：

- `r5:hwop-0072-00.field.ga_standalone_uint8_to_fp32_dequant`
- `r5:hwop-0072-00.field.execplan_typed_parameter_transport`
- `r5:hwop-0072-00.field.rtl28_physical_port_layout`

`exact_equivalence_scope`：
仅限 node0072 `uint8[16,2048,1,1]`、scale bits `0x3cbf57ec`、zero point 0、冻结 W3
输入域和 `28×1184` padded physical layout。

`materialized_configuration_mechanism`：
四个普通 GA ADD PE 加 `-0.0f`，再由四个普通 GA MUL PE 乘 `x_scale`；官方 typed
parser/planner/mapper/encoder/execplan/SCA 在 28 片上完整物化。

`performance_and_resource_cost`：
使用 8 个 GA PE 和两个依赖层，而数值上单层 4 个 MUL PE 已足够；每片 74 occurrence，
全局 384 个 padded element，增加一个 GA stage 的依赖/延迟并降低 PE/吞吐效率。

`unresolved_production_blocker`：

- `B_DEQUANT_NODE0072_NATIVE_STANDALONE_PATH`
- `B_DEQUANT_NODE0072_FORMAL_LAYOUT_APPROVAL`
- `B_DEQUANT_NODE0072_HARDWARE_E4_E5`
- `B_DEQUANT_NODE0072_TO_NODE0073_INTEGRATED_BINDING`

`claim_boundary`：
仅为本地 materialized E2；不是正式 target config、production/performance release、
服务器/硬件证据，也不可转移到 node0077 或其他 Dequant 实例。

## 4. 输入重放与最终物化字段

输入重放只复制 node0071 `QLinearGlobalAveragePool` 产生的原始 typed tensor
`tensor-ab32f279540568c3`：

- NPY SHA-256：
  `70e76086c96394b1cc0a50cf316663b4ea1def7f0d0b73568dd83662d6556b55`
- payload SHA-256：
  `b0b78ce73942e90566b05edfe6bd5ca5e924d3865e0232b31a58d9ffabb41067`
- 未改变 dtype/value；未在 host 预计算 subtract、scale、round、saturate、内部 tensor
  或最终 output；两级 Dequant 算术均由最终 GA 配置执行。

静态配置→最终 address-bound JSON 逐 leaf diff：

- 总变化：10；
- planner-owned base：2；
- typed constant 非 base 规范化：8，均逐字段声明 owner/input/formula/old/new/authorization；
- 未声明变化：0。

最终 occurrence/address 覆盖方程：
`union_{i=0..73} [D_base+i*64, D_base+i*64+64)`；每片唯一覆盖 4736 bytes，
与 SCA_D `296×16=4736` bytes 完全一致。将 `stream2.dim_stride[1]` 污染为 256 的负例
由 validator fail closed。

## 5. node0073 integrated-binding handoff

- storage owner：node0072 官方 addressed execplan 的 standalone D allocation；
- logical dtype/shape：`float32[16,2048,1,1]`；
- logical byte strides：`[8192,4,4,4]`；
- logical span：131072 bytes；
- physical storage：28 片，每片 4736 bytes，共写 132608 bytes；
- valid logical bytes：131072；padding：1536 bytes；
- 每片最终 D base 和相对 A offset 已完整列入机器合同与报告；
- static final-write/completion path、57-command execplan、28 片 D address write 和
  config-bound physical D 均已接受；
- dynamic hardware final-write、共享多算子 execplan、跨 node lifetime/visibility 和
  node0073 实际消费未物化，因此 integrated binding 状态为 `UNRESOLVED`。

addressed graph SHA-256：
`2c9cf00cd6ac03ac2f09236a4868d7b2fb6bd61f3e48a18de13d3f4630a3d7d1`。  
layout evidence SHA-256：
`4a8d3ac9ef7f965b944ef8d116b324f2229dabdd86b9b39a7699fd984f55b61a`。

## 6. 运行入口、产物与验证

运行入口：

```powershell
$env:PYTHONPATH='.'
$py='C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py tools/build_dequant_node0072_config_only_e2.py
& $py -m unittest tests.test_dequant_node0072_config_only -v
```

两份空 cache、隔离只读工具副本独立物化；normalized request、final JSON、mapping、
bitstream、execplan、SCA/SCA_D、cfg_pkg 等语义产物逐文件 SHA 完全一致。

主要输出：

| 产物 | SHA-256 |
|---|---|
| generator `resnet50_pipeline/dequant_node0072_config_only.py` | `56f6a4e58f25b3c9e93f03d86de563aabf90c91afd257046bded54e37f84d13e` |
| entry `tools/build_dequant_node0072_config_only_e2.py` | `5c5aa8e1b69b403590b32f6b8ea931605cc9a82f177572d2a9529ffd1e06f4ed` |
| test `tests/test_dequant_node0072_config_only.py` | `9d262b0f1fb9b6d2d1d567b697efb84c950ccfdd26308f69d1b314286246795d` |
| static config | `42c2ec4e7b0b4034ccad2f4822a19e5d7e26fe85a9427dd66febaa46a2e3211b` |
| final address-bound JSON | `de212d8d49bc963bc08a5691879433c165ef2aa938aa2581b56c25e75a92da50` |
| mapping review | `cc4d2e0cf9353a7962688c2874f691b93aebee4f78599965f15894bfe960a2b6` |
| bitstream | `edf7949e4b308a6105f30f1accd1cc247a0121a43cc2c104bc17c4e3cc8e398b` |
| execplan | `fdcdd46b878cdf7582b072ec1438a0211a01f34bf7245a280ea6dd1e7e322687` |
| SCA | `a1131970cc29df9baf7e0186f8fdc5e00785681dd6c05d2592ae75cf7a61fc2a` |
| SCA_D | `68e6cf00f09bc16ebdfddab72b63b9f3cb4fd0d3a4d8e3a80bb06162a09ff1ae` |
| ordered physical D | `18db1821f01336dfa641cf35ac08736e3ab7609dda31105bb8bd028dd4b41672` |
| local E2 report | `50e30f52bcc95fb3f3e89b2690bc163c77b4de3d77474dd9fecb569ed5176a43` |
| machine contract | `cf5172db59a0a7c294e49445f63cd7c61919c3aa4640af180799d2dcef42c60f` |

验证结果：

- family test：11/11 PASS；
- generic strict validator：static/final JSON 2/2 valid；
- mapping exact penalty=0，`fallback_used=false`；
- bitstream 26×128-bit lines；
- execplan 57×64-bit commands / 29×128-bit lines；
- physical D：28×4736 bytes；
- inverse logical D ↔ W3 golden：0 bit mismatch。

## 7. 结构化回传

### RETURN_ANALYSIS

node0072 真实实例已完成 typed target→static JSON→final address-bound JSON→mapping→
bitstream→execplan/SCA→address/lifetime→config-bound physical D→logical inverse 的
本地 E2。唯一允许声明为 `CONFIG_ONLY_CORRECTNESS_BASELINE`。node0077 正式 ResNet
三方计数保持 1/78；node0072 不增加正式计数。

### RULE_DELTA_PROPOSAL

提议主线评估 `DQ-NODE0072-MATERIALIZED-CONSTANT-NORMALIZATION-001`：当 typed handler
把 fp32 bit-string 常量规范化为十进制时，必须逐 leaf 声明并证明十进制 round-trip bits；
若 `-0.0` 规范化为 `+0.0`，还必须限定非负 typed 输入域并给出最终输出逐 bit 等价证据。
本任务未修改专项规则。

### BLOCKER_DELTA

新增/保持：

- `B_DEQUANT_NODE0072_NATIVE_STANDALONE_PATH`
- `B_DEQUANT_NODE0072_FORMAL_LAYOUT_APPROVAL`
- `B_DEQUANT_NODE0072_HARDWARE_E4_E5`
- `B_DEQUANT_NODE0072_TO_NODE0073_INTEGRATED_BINDING`

本地配置链无未声明 leaf drift、coverage 或 simulator blocker。

### PACKAGE_RELEASE

`NONE`。无服务器 lease；未生成、未上传、未运行任何 Dequant 服务器包。
