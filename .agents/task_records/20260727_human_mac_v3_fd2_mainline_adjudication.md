# Human MAC corrected-v3 fd2 主线裁决

日期：2026-07-27

## 接受的事实

- compile/sim 均 exit 0，slice 在 891 cycles 后 completed，随后自然 `$finish`；
- 28/28 正式 D 均存在，但每片只有前 16 行/256 bytes 逐 bit 等于 golden，后
  48 行/768 bytes 全为 X；
- 总计 448 行相等、0 行已知值错误、1,344 行 X；
- 静态 human JSON 的 `stream2.dim_stride[1]=256`；
- native `quant_from_buffer_int32MN_uint8MN` handler 以 `d_n*32` 把该字段物化为
  1024，`output_writer.py` 在编码前写回；
- 最终 occurrence 地址为 `0..255`、`1024..1279`、`2048..2303`、
  `3072..3327`，正式 D `0..1023` 只与第一段相交，和返回逐 byte 一致。

因此本次是
`FIRST_DYNAMIC_FAILURE/NO_DYNAMIC_BASELINE/NATURAL_COMPLETION/FORMAL_D_PARTIAL_COVERAGE`，
不是 regression，也不是正式节点通过。相邻 return `.sha256` sidecar 缺失，正式回传
身份继续 fail closed。

## 主线 blocker 裁决

退出候选：

- GA output source selection 已允许算术和自然完成；
- `LC2.last_index=1` 与本次首分歧无关。

保持/新增：

- `B_HUMAN_NATIVE_MATERIALIZATION_STRIDE_OVERWRITE`：handler 把 256 覆盖为 1024；
- `B_HUMAN_FORMAL_D_PARTIAL_COVERAGE`：每片只有 256/1024 bytes 被写入正式 region；
- `B_HUMAN_RETURN_IDENTITY_SIDECAR_MISSING`：相邻 return SHA sidecar 缺失。

## 规则裁决

接受提案的工程事实，规范化发布为
`CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001`：

- 编码前逐 leaf diff 静态/逻辑配置与最终 materialized JSON；
- 非 base 字段变化必须有逐字段 owner、公式和值域 allowlist；
- 由最终 occurrence/address 方程重新证明正式输出 byte coverage；
- 未声明覆盖、超出 allowlist 或 owner 冲突均 fail closed。

该门适用于所有当前纯配置物化任务，不只适用于 human JSON。

## PACKAGE_RELEASE

`NONE`。不修 RTL，不生成新服务器包，不检查服务器环境；corrected-v3 与 variable-root
包继续冻结。
