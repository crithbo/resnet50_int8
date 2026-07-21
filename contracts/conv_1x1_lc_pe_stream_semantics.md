# 首个真实 1×1 Conv：LC / PE / stream 语义说明

适用实例：`node-0004 / hwop-0004-00`，`[16,64,56,56] × [64,64,1,1] -> [16,64,56,56]`。本文是对当前实现和机器合同的可读说明，不单独定义配置真值；身份与可执行字段应以`conv_1x1_real.json`、机器合同中被consumer实际使用的字段、正式native candidate及其parsed evidence为准。若说明性文字与这些实文件的可复现行为冲突，应修正说明，不得为迁就文字修改已验证实现。

静态JSON表达单样本SA累加微程序；batch-16、七个HIGH-4组、三个accumulate wave和后续requant stage由typed request与项目级package调度。操作者已确认原DeepSeek算子JSON具备目标硬件执行能力，但这不替代本Conv实例的字段、数值和服务器验证。

## 当前端口与physical轴序

当前target与项目逻辑端口一致，不再沿用旧说明中的A/B交换：

| target/stream | 逻辑角色 | dtype | physical轴序 |
|---|---|---|---|
| A / stream0 | activation | UINT8 | `[storage_sample,H,Qblock,Cquartet,Q8,C4]` |
| B / stream1 | HIGH-4 PREV顺序weight | INT8 | `[R,S,ring_PREV_step,Cquartet,Kblock,K8,C4]` |
| C / stream3 | bias | INT32 | `[Kblock,K8]` |
| D / stream2 | accumulator P | INT32 | `[storage_sample,H,Qblock,Q8,Kblock,K8]` |

逻辑UINT8输出D由8份绑定的requant JSON产生，不在SA-only accumulate JSON中编码。execplan ABI固定为项目A→`READ_STREAM0`、B→`READ_STREAM1`、bias→`READ_STREAM3`、P→`WRITE_STREAM0`；旧A/B互换只能作为负向回归。

## LC 对照

范围使用JSON的`[start,end,step)`语义。

| LC | 当前语义 | 范围 | source/说明 |
|---|---|---:|---|
| LC0 | compute Kblock | `[0,2,1)` | 独立根 |
| LC1 | compute H | `[0,56,1)` | `LC0` |
| LC2 | compute Qblock | `[0,7,1)` | `LC1` |
| LC3 | activation Cquartet | `[0,4,1)` | `LC2` |
| LC4～LC5 | unused | `[0,0,0)` | 禁止赋予旧模板语义 |
| LC6 | HIGH-4 ring step | `[0,4,1)` | `LC2` |
| LC7 | local weight Cquartet | `[0,4,1)` | `LC6` |
| LC8 | unused | `[0,0,0)` | 禁止赋予旧模板语义 |
| LC9 | P write Q8 lane | `[0,8,1)` | `LC15` |
| LC10 | bias Kblock | `[0,2,1)` | 独立根 |
| LC11 | bias H | `[0,56,1)` | `LC10` |
| LC12 | bias Qblock | `[0,7,1)` | `LC11` |
| LC13 | P write Kblock replica | `[0,2,1)` | 独立根；为placement保留 |
| LC14 | P write H replica | `[0,56,1)` | `LC13` |
| LC15 | P write Qblock replica | `[0,7,1)` | `LC14` |

LC10→LC11→LC12是v19新增的bias tile触发分支。它不能退化为只按Kblock运行，否则同一bias行不会为每个`H×Qblock`输出tile重新进入buffer4。

## LC-PE 对照

正式consumer把`mac`编码为opcode 2；当前只使用两个地址PE：

| PE | 输出公式 | 用途 |
|---|---|---|
| PE0 | `LC6 × 4 + LC7` | HIGH-4 ring step与local Cquartet线性化 |
| PE1 | `LC15 × 8 + LC9` | Qblock与Q8 lane线性化 |

公式由semantic contract和正式mapper共同绑定；mapper的zero-cost placement证明连接可放置，不单独证明逐周期RTL数值行为。

## stream 对照

`idx_size`是minus-one编码；31表示单次32 B事务。

| stream | target/角色 | `idx=[port2,port1,port0]` | `idx_size` | byte stride | full last |
|---|---|---|---|---|---:|
| stream0 | A / activation read | `[LC3,LC2,LC1]` | `[31,0,0]` | `[32,128,896]` | 3 |
| stream1 | B / weight read | `[PE0,LC0,null]` | `[31,0,0]` | `[64,32,null]` | 4 |
| stream2 | D / INT32 P write | `[LC13,PE1,LC14]` | `[31,0,0]` | `[32,64,3584]` | 无 |
| stream3 | C / INT32 bias read | `[LC10,LC11,LC12]` | `[31,0,0]` | `[32,0,0]` | 2 |

stream3每个`Kblock×H×Qblock` tile发起一次32 B事务；只有Kblock改变地址，H/Qblock只重复触发。两个Kblock地址覆盖恰好64 B bias physical region。buffer4的JSON `buffer_life_time=4`编码为3，并由RTL包含端点地形成每tile四次SA bias握手；这四次握手用于初始化一组16项outbuffer psum。旧`idx_size=127`、128 B事务、Kblock-only触发和lifetime=1均已由v18真实停滞证据否定。

## SA、buffer与HIGH-4合同

- SA为INT8 GEMM，`bias_enable=1`，outport为column mode。
- GROUP0消费activation row；GROUP1消费local weight column；GROUP2消费本tile的K8 bias column broadcast，并与LC12 terminal事件一致。
- buffer0/1是允许neighbor的activation pair；buffer2/3承载local weight；buffer4承载bias且`buf_full_last_index=2, buffer_life_time=4`；buffer5从SA接收P，`dst_port=0`。
- N2N固定`mem_loop=4, src_slice_sel=1, dst_slice_sel=1`，表示HIGH-4 jump route；`ping_pong`未接入当前目标NSE RTL，只作provenance，不作为正确性字段。
- 例示group0 owners为`[0,2,3,1]`；destination 0的PREV遍历为`[0,1,3,2]`。weight按destination-relative PREV顺序预排布。

## v19身份与证据边界

- config SHA-256：`f26a3346859601055abc9cb88dd0b7c3650e5fcc4fae6d1f85d2562aba0ad8ed`。
- mapper connection count：33；mapping key：`2702bd9d31f9efc0`；constraint cost：0。
- 正式128-bit码流：29行，LF规范化逻辑SHA-256=`7d85938215a1d5a5622c38938b5adb64b982c631170604a4ba8285fb5397b255`。
- 正式A/B candidate、parsed/mapping/placement evidence、config-bound Golden/NDP P/D、新freeze、package和两轮本地ZIP审计均已通过。
- 历史28行`rebuild-v9`身份解决了旧35行码流混装，但仍包含v18暴露的bias节拍错误，不能作为current身份；行数必须随revision的semantic/encoder/freeze身份验证，不能写成永久规则。
- typed qparam transport和首例G5已经闭合。尚未证明的是v19在服务器上的自然完成、原始RTL P/D、run1/run2稳定性和Golden/NDP/RTL三方bit-exact，因此G6/G8仍为false。

v19哈希绑定的`contracts/conv_1x1_lc_pe_stream_semantics.json`在`evidence_boundaries`中仍保留旧候选“16 of 20 LC and 7 of 10 LC-PE”以及“execplan typed qparam transport未证明”的自由文本。它们不参与配置生成、placement或runner判定；当前`conv_1x1_real.json`与正式candidate的实际事实是16个DRAM LC、2个LC-PE和33条连接，typed qparam transport也已由当前项目链闭合。因为原地改写该JSON会破坏v19的typed request、preflight和freeze身份，v19保持不可变；下一次因数值/配置变化建立新revision时，语义合同刷新步骤必须从当前candidate和项目门状态同步更新这些说明字段。
