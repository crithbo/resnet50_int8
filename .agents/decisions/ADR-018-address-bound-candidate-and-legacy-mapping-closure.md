# ADR-018：地址绑定候选链与 legacy mapping 闭合

日期：2026-07-23  
状态：接受

## 背景

R5 在 typed lowering 完成后仍有两类本地欠账：`node-0004 accumulate-wave-0 nopp-r1` 的 mapping 与 planner 最终地址未绑定；9 份 legacy 规范化配置只有 5 份具备 zero-penalty 完整证据。直接复用地址绑定前 bitstream、把 qparam 向量压成标量，或把历史 cache 当作成功结果都会产生不可审计的假闭环。

## 决策

1. mapping 必须在 planner 写入最终 A/B/C/D base 后重新运行；execplan evidence 在每个隔离 planner 副本中按 op type 安装已验证 mapping bundle 的 source config。
2. `node-0004` 的 semantic contract 允许 scalar qparam 或哈希绑定的 per-channel descriptor；后者必须保留 dtype、shape、axis、element_count、min/max 和 value SHA。
3. 请求地址验证仍完整枚举所有请求；发布报告允许省略逐地址 rows，但必须保留每 stream 的计数、有序哈希和首尾边界样本。
4. 固定参考 cache 只在来源提交、文件哈希、16-hex key 和内容均绑定时进入隔离工具副本；原生 mapper 必须实际加载并重新计算 exact penalty=0、fallback=false。
5. MaxPool `padding_reg_value:null→0` 只由 `contracts/maxpool_uint8_zero_padding_contract.json` 对单一 source SHA 授权。合同绑定 W3 uint8 dtype、隔离 RTL 的 65536 输入对/262144 lane 无符号 max 证明，以及读流 padding-byte 替换 RTL。它不授权 AvgPool、其他 dtype 或服务器声明。

## 结果

- `node-0004` 地址绑定配置 SHA-256：`12daf4c1a81d1634439374ea79dbb7972a28bd415da74e999ee9cfa87e7905ae`。
- 最终 mapping penalty=0、fallback=false；双跑 execplan SHA-256：`a5d9edf2fbd51f2107b9fe7845f4716786a61797be7c9e38aca3ede9009a0711`。
- node-0004 请求按 multiplicity 为 748160 次，704368 个唯一地址；紧凑报告为 229259 字节。
- 3 份 GEMM 由固定 `fab05601add9259e` cache 闭合；16×16 MaxPool 由固定 `dc65063f38e8722f` cache 闭合。9/9 legacy 规范化配置现均有 zero-penalty mapping。
- 原始 legacy JSON 仍是 intentional-reject；`node-0004` 与 MaxPool 仍是 candidate-only。正式 ResNet50 配置仍为 0/133，E4=0、E5=0。

## 非决策

本 ADR 不批准完整 MaxPool completion、不批准任一服务器命令、不把本地功能模型或隔离 RTL kernel proof 当作第三方硬件回读，也不允许从固定参考仓复制最终配置、bitstream、execplan 或数据产物。
