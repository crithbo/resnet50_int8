# Conv/SA b7acbe5 最新源码独立审计

日期：2026-07-29

## SOURCE_IDENTITY

- GitHub 私有仓库：`xlsjdjdk/Trassic2.0_RTL`
- `master`：`b7acbe55340ca7e98ead70335156f555929c0777`
- source-current-match：
  `Trassic2.0_RTL_master_b7acbe5_sync/Trassic2.0_RTL-master/code/NDP_rtl`
- 活动根：`NDP_copy01/rtl`
- 活动 filelist：`NDP_copy01/rtl/filelists/NDP_Top_phy_filelist.f`
- source 与活动根均为 2242 文件，逐路径 SHA 差异为 0，tree SHA-256 为
  `62cc16b630046e7a1ed09351de8065e37764e2afb4c881f44d2f84e57c55bdc7`。
- 当前同步合同 SHA-256：
  `15aca6e8747d6cf5c24ab498a958cd23c3552963c8641dd85c7bd33303d7a75c`。
- 同步记录 SHA-256：
  `8b1292de0082e587a51183c897688fac249fe25f3605056f19ac5e96aa923def`。
- plan 仅作 mutable provenance，读取时 SHA-256：
  `fba33da2dc53e88e75a177266014991dca84f5536045b6ad4ae1b92a61f9b906`。

## 相对 1c49bd1 是否真的改了活动 RTL

没有。

将 `b7acbe5` 的 `code/NDP_rtl` 与上一审计
`1c49bd1155a89ff187e29016dc4415e59a55f991` 的同一目录逐相对路径计算
SHA-256：

- 共同路径内容差异：0
- 新增文件：0
- 旧快照独有：16

16 项只包括 15 个 AXI 仿真归档 `.so` 和一份上一轮审计日志，不属于活动 RTL
或 filelist 源。因此，commit 说明“修复语法问题”不能替代源码叶子收据；
当前活动 RTL 内容与 `1c49bd1` 相同。

## CONFIRMED_BLOCKERS

### 1. 原样首个确定 VCS/source compile blocker

文件：
`Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_Control.v`

文件 SHA-256：
`c6018e762411e14346bfec672b273b826f893b11c5de0cfb38fca674f9d33c4b`

第 50-51 行：

```verilog
output[1:0] o_Config,
);
```

`o_Config` 已是 ANSI port list 最后一项，尾逗号会要求后续还有 port；解析器遇到
下一行 `)` 时失败。既有服务器 VCS 报在第 51 行的 `)`，本轮直接对最新源码做
focused Icarus 编译，原样 `exit=1`，明确报：

```text
SA_PE_Float_Control.v:50:
Superfluous comma in port declaration list.
```

最小修复只应删除 `o_Config` 后面的逗号，不改端口名、位宽、顺序或功能语句。
这是公共 NDP top 的 compile stop：Conv 直接使用 SA；GAP/QAdd 即使走 GA，也会
被公共 filelist 编译阻塞。

### 2. SA INT32 negative-psum 边界错误仍在

文件：
`Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Float_CSA.v:49-50`

SHA-256：
`04cc5d95754a05a7580c1e6a4649c19c067f41af6f0d12184d736bfef2164cf5`

本轮在只删除语法逗号的诊断副本上重新编译并执行 11 项定向用例，
compile=0、run=1、失败 2 项：

```text
psum=-5, dot4=+5:
RTL=0x80000000, expected=0x00000000

psum=INT32_MIN, dot4=0:
RTL=0x00000000, expected=0x80000000
```

所以该缺陷在 `b7acbe5` 仍是确定的 RTL 算术错误，不是“架构没有 INT32
accumulate”。它只在边界编码命中时破坏 Conv modulo-INT32 结果；本记录不声称
当前 ResNet50 W3 已命中这两个值，也不把它冒充本次无法启动的首因。

### 3. GA INT8 pipeline0 ready 缺口仍在

文件：
`Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv:527-557`

SHA-256：
`25fa4dd2c6fe8301bc3651d660df72059ea2787c0c26a2841a1d4e439586b518`

源码解码了 `alu_is_int8`，但 `alu_pipeline0_bp_post` 只含 INT32 与 FP32：

```verilog
assign alu_pipeline0_bp_post = (alu_is_int32 && ga_pe_inbuffer_bp_post)
                             || (alu_is_fp32  && ga_pe_alu_pipeline1_enable);
```

INT8 没有任何 ready 分支，因此有效 INT8 token 进入 pipeline0 后不能继续前进。
这是 GA INT8/MaxPool 等路径的确定 flow 缺陷；它不是 SA Conv 的数据路阻塞，
也不是 GA opcode14 INT32 GAP 或 FP32 QAdd 的当前阻塞。

## POST_UPDATE_CLOSURE

只在
`outputs/conv_sa_rtl_compile_audit_b7acbe5/diagnostic_rtl_copy/NDP_rtl`
删除上述一个尾逗号。源快照、活动 RTL 和功能 RTL均未修改。诊断副本相对源只有
这一个文件差异。

修复后 focused SystemVerilog-2012 编译/展开：

| top | source 数 | 结果 |
|---|---:|---:|
| `SA_ALU` | 32 | PASS |
| `SA_PE_ALU` | 32 | PASS |
| `SA_PE` | 32 | PASS |
| `SA_PE_Group` | 33 | PASS |

因此：

- `SA_ALU.v:125-128` 的 `.slice_rst(slice_rst)` 与
  `SA_PE_Mul_Array.v:1-5` 的 `input slice_rst` 当前一致；
- `slice_rst` caller/callee mismatch 已关闭；
- 只删尾逗号后，没有发现第二个确定的 SA module/port/width compile blocker。

活动 full filelist 可递归展开为 30 份 filelist、846 个且 846 个唯一 source entry；
静态扫描得到 900 个唯一 module 名，重复 module 名 0，冲突标记文件 0。

本地没有 VCS。Icarus 对完整 `NDP_Top_phy` 的首个工具边界是受保护的 DDR
vendor model `dram_model.vp:55`；排除该 `.vp` 后，又在合法的 SystemVerilog
localparam array、`signed'(...)` cast 和动态 packed-array index 上停止。这些均
单列为 Icarus/tool boundary，不能声称是 VCS/source blocker，也不能声称完整
VCS 已通过。硬件组删除逗号后仍须执行真实的 full-filelist VCS
compile/elaboration。

## QAdd observer 边界

`native_return_observer.svh` 在该 RTL 树中的匹配数为 0，活动 RTL filelist
引用数也为 0。QAdd return 的首分歧来自服务器
`tb_NDP_Top_new_phy.sv:5854` 无条件 include 该文件，而服务器 TB/include 环境
未提供它。

因此它属于服务器 TB/include 环境，不属于 `b7acbe5 code/NDP_rtl`，不能通过
修改本 RTL 树或 QAdd 数值配置来解决。

## BLOCKER_DELTA

- KEEP OPEN：`SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA`
- KEEP OPEN：`SA_INT32_NEGATIVE_PSUM_BOUNDARY`
- KEEP OPEN：`GA_INT8_PIPELINE0_READY`
- CLOSED：`SA_MUL_ARRAY_SLICE_RST_CALLER_CALLEE_MISMATCH`
- SEPARATE NON-RTL：`SERVER_TB_NATIVE_RETURN_OBSERVER_INCLUDE_MISSING`

## RULE_DELTA_PROPOSAL

`NONE`。现有 source-current-match 与叶子 SHA 证据门已足以拒绝“commit 说明等于
修复落地”的推断。

## 边界

- 未访问服务器。
- 未修改 `.agents/plan.md`、公共规则、活动 RTL 或 GitHub 快照。
- 未生成算子包。
- 未重复 QAdd 数值分析。
- `PACKAGE_RELEASE=NONE`。

