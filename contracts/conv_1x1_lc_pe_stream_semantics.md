# 首个真实 1×1 Conv：LC / PE / stream 语义裁决

适用实例：`node-0004`，`[16,64,56,56] × [64,64,1,1] -> [16,64,56,56]`。静态 JSON 表达单样本 SA 累加微程序；batch-16、七个 HIGH-4 组和每组 3/2 个样本由 target request adapter 调度。

操作者已确认先前DeepSeek算子JSON可以被目标硬件执行，因此平台JSON执行能力不再是阻塞。具体字段裁决的证据优先级仍为正式编码消费代码/寄存器表、已知可执行DeepSeek JSON、可重复编码的新JSON、NDPFuncModel request执行、学长伪代码、旧规则文档。

## LC 对照

| LC | 唯一语义 | `[start,end,step)` | 裁决 |
|---|---|---:|---|
| LC0 / LC13 | `k_block` / placement replica | `[0,2,1)` | 原 TXT 首层误写成 q；K/32=2 |
| LC1 / LC14 | `q` / placement replica | `[0,56,1)` | 原 JSON end=1 错 |
| LC2 / LC15 | `p_block` / placement replica | `[0,2,1)` | `ceil(56/32)=2` |
| LC3 / LC6 | activation/weight C quartet | `[0,4,1)` | C/16=4；不再另占一个 c-global PE |
| LC4 / LC7 | S 两条支路 | `[0,1,1)` | 真实 1×1 |
| LC5 / LC8 | R 两条支路 | `[0,1,1)` | 真实 1×1 |
| LC9 | `k_reg` | `[0,4,1)` | 32/(4×2) |
| LC10 | `p_reg` | `[0,4,1)` | 32/8 |
| LC11 | `p_pe` | `[0,8,4)` | 实际值 0、4；原 JSON `[0,4,1)` 错 |
| LC12 | `k_pe` | `[0,2,1)` | 实际值 0、1 |

## LC-PE 对照

本适配合同将 `mac` 定义为 `inport0 × inport1 + inport2`。正式 consumer 已确认 `mac` 编码为 opcode 2，但算术公式仍属于适配语义，尚不是逐周期 RTL 证明。

| PE | 输出公式 | 主要冲突裁决 |
|---|---|---|
| PE0 | `rs=s×1+r` | 3 改为 1 |
| PE1 | `h=p_block×32+r` | 保留 32 行块 |
| PE2 | `w=s×1+q` | 原 JSON 实际会近似 `s×q` |
| PE3 | `p_inner=p_reg×8+p_pe` | 原常数 4 错 |
| PE4 | `p=p_block_replica×32+p_inner` | `mul` 改 `mac` |
| PE5 | `k_inner=k_reg×2+k_pe` | `mul` 改 `mac` |
| PE6 | `k=k_block_replica×32+k_inner` | `mul` 改 `mac`，且 LC15(p) 改 LC13(k) |

TXT 中的 `c_shared×4+c_weight` 不分配第八个 PE：C 的两级展开已由 stream transaction 和 buffer spatial 轴表达。

## stream 对照

target 字母沿用伪代码而不是项目逻辑端口：target A=weight，target B=activation，target C=bias，target D=INT32 P。适配器必须显式交换项目 A/B，禁止按名字直连。

| stream | target / 数据角色 | `idx=[port2,port1,port0]` | `idx_size` | byte stride | tail |
|---|---|---|---|---|---|
| stream0 | A / INT8 weight read | `[c_shared,k_block,rs]` | `[3,31,0]` | `[128,2048,128]` | 无 |
| stream1 | B / UINT8 activation read | `[c_weight,w,h]` | `[3,0,0]` | `[12544,4,224]` | h 有效 `[0,55]` |
| stream2 | D / INT32 P write | `[k,q,p]` | `[3,0,0]` | `[12544,4,224]` | p 有效 `[0,55]` |
| stream3 | C / INT32 bias read | `[k_block_replica,null,null]` | `[127,null,null]` | `[128,null,null]` | 无 |

N2N `mem_loop` 从16改为4；四步含本地步和三次传输。group0物理环为`[0,2,3,1]`，destination 0的PREV遍历为`[0,1,3,2]`。但当前候选编码`src/dst_slice_sel=0`，已知可执行的`prefill_gemm_ring_4slice.json`在`mem_loop=4`时使用selector 1，`decode_gemv_ring.json`只在`mem_loop=28`时使用selector 0；register map与execplan也把1绑定到jump-4/HIGH路径。因此当前`mem_loop=4 + selector=0`不是已批准规则，而是待修正/裁决的明确配置冲突。`ping_pong`仍需按Conv数据流单独判断，不能随selector机械复制。

## 结论边界

`conv_1x1_real.json`已由正式encoder两次解析、placement、生成bitstream，46条连接、constraint cost 0，两个输出目录逐文件SHA-256一致。目标平台执行DeepSeek JSON的通用能力已经确认；本候选仍有HIGH-4 selector冲突、真实per-channel requant/唯一flush和execplan typed qparam transport三项配置阻塞。该候选的硬件实跑与P/D dump按操作者决定延期，不再作为当前配置工作的前置阻塞。
