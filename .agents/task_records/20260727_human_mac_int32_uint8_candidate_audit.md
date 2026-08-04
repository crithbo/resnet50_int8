# 人工 mac_int32_uint8 JSON 字段审核

时间：2026-07-27（Asia/Shanghai）

## 输入身份

- 容器绝对路径：
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\mac.zip`
- ZIP bytes：1620
- ZIP SHA-256：`7b6770dfe038d5e92b810c20fb4a8a620472afd1dc1e3d6837d4e3af54755a55`
- 人工候选 entry：`mac_int32_uint8.json`
- 候选 bytes：12123
- 候选 SHA-256：`d98929d1c31b6c55d12ea8b232cf76400024d60ebc29d8d4e39c6e3abc8e4db9`
- `human_authored_input=true`

ZIP 只有 `mac_int32_uint8.json` 和 `readme.txt`，没有重复 entry、绝对路径、`..` 或路径
穿越。原 ZIP 与候选未修改。

## 功能合同

README 声明：

- 输入：`int32[32,32]`
- 输出：`uint8[32,32]`
- 方程：`out = inp * 1 + 1`
- 不考虑溢出
- 不要求 simulator

测试输入计划使用固定随机种子，并限制 `inp` 在 `[0,254]`，使 `inp+1` 精确落入
`uint8`，从而不引入 README 未定义的溢出裁决。

## 首个字段分歧

人工候选的以下 8 个 PE 都配置：

```text
$.general_array.PE_array.PE{00,02,10,12,20,22,30,32}.alu_opcode = "mac"
```

直接消费者证明：

- `ndp-sim/bitstream/config/general.py` 将 `"mac"` 编码为 6；
- 同一 encoder 将 `"int32_mac"` 编码为 14；
- `NDP_copy01/rtl/includes/NDP_Parameters.svh` 定义 opcode 6 为
  `GA_PE_ALU_OPCODE_FP32_MAC`；
- 同一 RTL 定义 opcode 14 为 `GA_PE_ALU_OPCODE_INT32_MAC`。

候选同时配置
`$.general_array.inport.inport0.int32tofp32 = "false"`，所以不能把该路径解释为“先把
int32 转 FP32，再做 FP32 MAC”。当前 JSON 不实现 README 的整数 `x*1+1`。

## 裁决

- `CONFIRMED_REFERENCE`：encoder/RTL opcode 映射；
- `LOCAL_E2`：未开始；
- `STRUCTURAL_RISK`：`CONFIG_SEMANTICS_CONFIRMED_FAILURE`；
- `DYNAMIC_REQUIRED`：修正并完成静态/物化回环后仍需 stock-RTL 正式 readback；
- `candidate_release=false`；
- `formal_target_instance_allowed=false`；
- `generated_package=false`。

按 `CDA-CONFIG-SEMANTIC-OWNERSHIP-001`、
`CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001` 和生成前停止门，不对已知错误配置生成服务器包。

## 唯一最小后继

等待用户明确授权后：

1. 保留原 ZIP/entry；
2. 另存 corrected candidate；
3. 仅把上述 8 处 `"mac"` 改为 `"int32_mac"`；
4. 保存逐字段 diff、bytes 和 SHA-256；
5. 重新做 transaction/bank/buffer/tag/lifetime 审核；
6. 生成固定随机输入与独立 golden；
7. 从 corrected candidate 原生完整重建 mapping、parsed/64b/128b bitstream、
   execplan、SCA/SCA_D 和 candidate-release-false stock-RTL 包。

