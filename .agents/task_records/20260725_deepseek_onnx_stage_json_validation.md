# DeepSeek ONNX→crop→stage→JSON→bitstream 首批验证记录

日期：2026-07-25

## 结论

本轮完成了 SiLU、RMSNorm、RoPE、Softmax、GEMM、GEMV 六个代表族的本地验证、
双隔离重建和全部已知本地 blocker 的闭合。证据上限仍为 E2；未修改任何 `rtl/`
文件，未生成服务器测试包，所有资产均保持 `candidate_release=false`。

身份边界固定为：

- ONNX Community FP16 GQA 只分类为 `SEMANTIC_MODEL_MATCH`；
- 不声明其为 ndp-sim 原始权重的 `ORIGINAL_SOURCE_IDENTITY`；
- 896/1792、7Q/1KV、1-layer 实例均由显式 crop contract 派生；
- 不把源 ONNX shape 直接写成硬件 stage shape。

## 六族状态

| family | 当前本地状态 | 已闭合 | 仍打开 |
|---|---|---|---|
| SiLU | `LOCAL_E2_REFERENCE_CONFORMANT` | ONNX 融合公式、crop shape、JSON、bitstream、execplan、SCA_D、双隔离重建 | 硬件数值精度与 E4/E5 |
| GEMV | `LOCAL_E2_REFERENCE_CONFORMANT` | crop 数值 golden、B/B′ 独立分配、28-slice N2N、D 覆盖、config length | E4/E5 |
| RMSNorm | `LOCAL_E2_ACTIVE_STAGE_PRODUCER_CONFORMANT` | 7×4-slice 分组归约、active Stage、五 stage 双隔离、首四 stage 地址图、最终常量/SCA_D、全部 config length | 无本地 blocker |
| RoPE | `LOCAL_E2_REFERENCE_CONFORMANT` | canonical XOR2、单一 sign owner、三 stage 生命周期、28-slice route、301 个非空 logical/physical payload | 无本地 blocker；E4/E5 未做 |
| Softmax | `LOCAL_E2_REFERENCE_CONFORMANT` | active layout hints、五 stage 双隔离、5/5 最终 JSON 命中、245 个非空 payload 与独立公式 | 无本地 blocker；E4/E5 未做 |
| GEMM | `LOCAL_E2_REFERENCE_CONFORMANT` | active layout hints、地址/ring/D、59-word config、111/111 命令、88 个非空 payload 与全部 ring partial | 无本地 blocker；E4/E5 未做 |

## 续验证最终闭环

首轮记录中的 RMSNorm raw producer、Softmax/GEMM 数值 payload 和 RoPE
pairing/sign/payload 均已在后续本地验证中关闭：

1. 新增规则所有的 active Stage producer，只对上游 raw prefill graph 做 12 个注册叶
   变更；RMSNorm、Softmax、GEMM 均从该 active graph 正向物化，raw graph 保持只读。
2. Softmax 生成 49 个 logical 与 196 个 physical 非空文件，覆盖 7 个 head、每 head
   四份 slice replica 和全部五 stage；因果 mask、概率和、FP16 输出与原生 relayout
   均闭合。
3. GEMM 生成 4 个 logical 与 84 个 physical 非空文件；每个输出 slice 都逐项覆盖
   28 个 K-chunk partial，FP32 累加、FP16 D、physical mapping 和 ring order 均闭合。
4. RoPE 选择 `CANONICAL_CROSS_SLICE_XOR2`：激活不预交换，sin 前半正/后半负，
   op1 输出按 `slice_id xor 0b10` 路由，payload relayout 不再拥有全局负号。隔离
   overlay 的两次运行逐文件一致，最终 execplan 的 28 个逻辑路由零失配。
5. RoPE 数值资产包含 49 个 logical 与 252 个 physical 非空文件，覆盖 7 head、
   28 slice、三 stage 的全部 A/B/D，并证明 op0.A 与 op1.A 逐字节相同。

原生 `slice_routing.py` 的 XOR3 和原生 `relayout_rope.py` 的全局负号仍作为反例
原样保留；本轮只在隔离工具副本应用项目侧 route overlay，没有修改活动原生
checkout，更没有修改 `rtl/`。

## Load_Config 通用缺陷与修复

发现旧 `model_execplan` 在重新生成 bitstream 后用 `128-bit 行数 × 2` 写
`Load_Config.config_length`。这会在真实 64-bit 字数为奇数时多下发一个 transport
padding half，但又会把 SiLU/GEMV 末尾真实的全零 64-bit 字误判成 padding。

最终规则为：

1. 有效配置长度等于同轮 `*_bitstream_64b.bin` 非空行数；
2. 128-bit 文件必须等于 64-bit 字按 `second + first` 的逐对重打包；
3. 奇数个 64-bit 字时，最后一个 128-bit high half 才是 transport padding；
4. 即使 high half 全零，只要它来自偶数位置的真实 64-bit 源字，就必须计入长度。

非 RTL 修复文件：

- `ndp-sim/model_execplan/src/execution_plan_generator/pipeline.py`

规则/validator：

- `CDA-DEEPSEEK-CONFIG-LENGTH-PADDING-001`
- `resnet50_pipeline/ndp_config_length.py`
- `resnet50_pipeline/deepseek_config_length_audit.py`
- `contracts/operator_config/deepseek_config_length_audit_v1.json`

六族重新物化后，16/16 个 stage 均满足：

```text
programmed Load_Config length
== 64-bit source word count
== RTL meaningful delivery count
```

其中 GEMM 从旧的 60 修正为 59，生成的 111 条命令现与可信
`jsons/gemm_ring_fnn` package 逐条一致；GEMV 保持 78，证明其末尾全零高半字是
第 78 个真实配置字而非 padding。

## 首轮 RMSNorm 分组归约定位（续验证已关闭 producer gap）

可信 `jsons/rmsnorm/rmsnorm_withbaseaddr.json` 证明 crop RMSNorm 采用 7 个 head、
每 head 4 slice 的分组归约：

- op1、op2 都启用 28 slice；
- op1 A 为 `[1,4,32]` 且 `type=slice0`，含义是四片组内相对 source；
- op2 从 op1 普通取数，不再使用全局 `slice0`。

按该拓扑重新物化后，两次空 cache 隔离运行自然完成；首四 stage 的 address-bound graph
与可信 package 完全一致；op2 最终 64-bit 配置码流中 `1/896` 与 `1e-6` 的 FP32
payload 各出现 8 次；五 stage 的 SCA_D 分别覆盖每片 `8/8/8/256/128` 行。由此关闭
旧 leader、gather、control 三项。首轮保留的
`B_DS_RMSNORM_STAGE_TOPOLOGY_GAP` 后续由带逐叶 provenance 的 active Stage
producer 关闭；上游 raw Stage 仍不被改写或声明为原生正确。

专项规则：

- `CDA-DEEPSEEK-RMSNORM-GROUPED-REMOTE-SUM-001`
- `CDA-DEEPSEEK-RMSNORM-STAGE-TOPOLOGY-OWNER-001`
- `.agents/rules/DeepSeek_RMSNorm增量规则.md`

## 首轮 RoPE 配对与符号裁决（续验证已选 canonical XOR2）

对 128 元素 half-split 向量建立了精确整数 ONNX 方程，并同时解码当前生成配置、
可信 route 和原生 relayout 的符号所有权：

- 当前 prefill `xor3` route 再叠加全局 relayout 负号时为 128/128 不匹配；
- canonical 跨 64 元素半区的 `xor2` route 且不再全局取负时为 0/128 不匹配；
- 文档化 decode 备选方案（激活预交换、`[-sin,+sin]`、同 slice 加法）同样为
  0/128 不匹配。

因此首轮不能只凭“算子名/三 stage 生命周期正确”放行 RoPE。续验证已在 route 与
relayout 之间选择唯一符号 owner，并以 301 个非空合成 payload 关闭本地 E2；可信
package 的 252 个 tensor 文件中仍仅一份 4096-byte matrix D 非空，所以它继续只作
配置/拓扑 oracle，不作完整数值 oracle。新增规则：

- `CDA-DEEPSEEK-ROPE-HALF-PAIRING-001`
- `CDA-DEEPSEEK-ROPE-SIGN-SINGLE-OWNER-001`
- `CDA-DEEPSEEK-ROPE-PAYLOAD-COVERAGE-001`
- `CDA-DEEPSEEK-ROPE-IMPLEMENTATION-CHOICE-001`

## 首轮 Softmax 规则归一化定位（续验证已关闭数值 gap）

本地差异最终被定位为两个不能由 shape 推导的 layout owner：

- op0 C/mask 需要 `write_reg_hint=softmax_mask_reuse_rows`，生成
  `dim_stride=[32,512,null]`；
- op2 A/exp 需要 `write_reg_hint=softmax_exp_m8_n_interleave`，生成
  `[0,1,8,9,2,3,10,11,4,5,12,13,6,7,14,15]` 的 buffer bank 顺序。

加入显式 hint 后，从 address-bound graph 到 mapping、bitstream、execplan、
SCA/SCA_D 完整重建；两次空 cache 隔离运行的 57 个确定性文件逐字节一致，5/5
materialized JSON 均与 `jsons/softmax/jsons/` 的可信硬件样本逐字段相等。由此关闭
旧 mask stride 与 exp bank divergence；首轮保留的 producer 与 numeric blocker
后续分别由 active Stage producer 和 245 个非空合成 payload 关闭。可信
install/output 的零长度边界仍被保留，不被误写成数值证据。

新增规则：

- `CDA-DEEPSEEK-SOFTMAX-MASK-STRIDE-OWNER-001`
- `CDA-DEEPSEEK-SOFTMAX-EXP-BUFFER-LAYOUT-001`
- `CDA-DEEPSEEK-SOFTMAX-NORMALIZED-ROUNDTRIP-001`
- `CDA-DEEPSEEK-SOFTMAX-PAYLOAD-COVERAGE-001`

共享 `control_registers.py` 变化后，六个代表族全部从空 artifact root 重新物化，
刷新 base/family 读取收据和下游合同；SiLU、RMSNorm、RoPE、Softmax、GEMM、
GEMV 的两次隔离运行均保持确定性一致。

## 最终身份

- 码流生命周期规则 SHA-256：
  `247f4469572359055af077b631d59f4193cb1735c8932c857f5de94e1a83518a`
- config-length 总账文件 SHA-256：
  `407718d55e59af2556e2afb9027219d75f7f7342ffc190df59de4ec62008049f`
- active Stage producer 合同文件 SHA-256：
  `b59312280d0e11cdae398b4ab7c3cd467061e2b8db48bfb7c37d0373c0a334c1`
- SiLU 合同文件 SHA-256：
  `948174748df076b3be252da2cc2db0ac7040e6e50e2c3efa20291e21299cb791`
- GEMV 合同文件 SHA-256：
  `061a82190762c59cc5d6365442e5a319edd75e9b611e12e1506e4fdcedfea1cc`
- RMSNorm 合同文件 SHA-256：
  `8ed6ad5a806e14d0cddca6bf13a7dc374815bc37c03d29f62135a66a809d509d`
- RMSNorm 专项规则 SHA-256：
  `c40b5ecb09290946490881473b5f23bcc483238153bdfb7151743b25ad9a0a2c`
- RoPE 合同文件 SHA-256：
  `4c15ab1d9ee9b8a91558cd5f264966c3e0b8d3e109a375efd9eceba259af7c43`
- RoPE 数值合同文件 SHA-256：
  `41fdcb5d2222f392f1101bf7154a61dd3134aa61fc3905545845972b40602e6d`
- RoPE 专项规则 SHA-256：
  `f4ae02f66fd00f98f4597af254e6f8c28f902af56de3b940b8e9be33fba4b2d4`
- Softmax 合同文件 SHA-256：
  `1440dfa1ead88c39e9a80c45ce68f54d04173744d255b30e9dff93fdaafd24ad`
- Softmax 数值合同文件 SHA-256：
  `71aca8cc907b49b1338631e60ab5f58d7144a84e471df391a9e9a1adec63ad3a`
- Softmax 专项规则 SHA-256：
  `2bb2dfb0f37db68848f7a8ff1c018169d3d4a2ee13359c672c502f1031f00cc8`
- GEMM 合同文件 SHA-256：
  `9e94c382f8c370eb71af0b9c6da7f1e9545299464b833c14748d19f1b6479a58`
- GEMM 数值合同文件 SHA-256：
  `b0063a6ad58d02382266a7ee6fc9cb7034c70043ed10832555c504bd40fdb8f3`
- GEMM 专项规则 SHA-256：
  `9745e0517efa26315fc9682cbceb4abd579bac6d9b40a52ab627feef8ee49b97`
- 公共读取收据 SHA-256：
  `bab13378476bd715f416d7cdb9b9d9b753a5729132590322d44954f5ce8c1ce4`

以上为文件 SHA；合同 JSON 内部另有 canonical payload hash。

## 验证

最终当前 DeepSeek 专项回归共 100 项，全部通过，覆盖：

- ONNX identity/crop/stage mapping；
- primitive/reduction 规则；
- 六族主合同、三份新增非空数值合同与篡改 fail-closed；
- 双隔离空 cache 重建；
- active Stage producer 的 12 个注册叶变更；
- 64b→128b packing 与 16/16 Load_Config 长度总账；
- RoPE 隔离 route overlay 的 preimage/postimage provenance 和逐 slice 路由。

## 下一步

本次六族验证已结束。下一项最有价值的工作是选择尚未参与规则构造的真实 operator
family 作为 holdout，重复 ONNX→crop→active Stage→可信 JSON→bitstream/execplan
回环，以检验规则的可推广性，而不是继续调同一批样本。

仅当某一项无法再由可信 JSON、原生 consumer、生成码流和 RTL 方程裁决时，才形成最小
原子 JSON 测试需求并交给“测试修复”会话；本任务不生成服务器包。
