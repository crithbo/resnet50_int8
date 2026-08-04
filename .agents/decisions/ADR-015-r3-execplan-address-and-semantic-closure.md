# ADR-015：R3 execplan、请求地址与语义合同闭环

日期：2026-07-23

状态：accepted；R3 本地退出门已达到，服务器 E4/E5 与正式 lowering 仍未完成。

依赖：ADR-010～ADR-014。

## 1. 决策

R3 外围 fail-closed 验证器已经把以下对象闭合到同一条可复查证据链：source JSON、零 penalty mapping、逐 bit 配置镜像、原生 execplan、每条 Load_Config/Write_Reg/Start_Comp、SCA 地址、逐请求物理地址、layout/qparam/tail/stage/provenance 合同及双跑确定性。验证器不 import `ndp-sim`，不改写活动原生仓和既有候选。

新增实现与入口：

- `resnet50_pipeline/operator_config_execplan_validator.py` 与 `tools/validate_operator_config_execplan.py`：独立解析 128-bit execplan，绑定真实 Load_Config、bitstream、source JSON、SCA payload 和 CONFIG stage 状态；
- `resnet50_pipeline/operator_config_package_validator.py` 与 `tools/validate_operator_config_package.py`：绑定 SCA region、6144-row profile、B′、alias/overlap、layout、qparam、tail、stage DAG 和 provenance；
- `resnet50_pipeline/operator_config_request_address_validator.py` 与 `tools/validate_operator_config_request_addresses.py`：回放真实 Write_Reg，逐 slice 恢复 stream image，枚举 loop/LC-PE 索引与全部 Memory_AG 请求；
- `resnet50_pipeline/operator_config_execplan_evidence.py` 与 `tools/generate_operator_config_execplan_evidence.py`：在两个隔离工具副本中运行未修改的原生 planner，只有两次确定性输出一致且所有验证层通过时才发布 bundle。

## 2. 地址语义裁决

活动 RTL 的请求地址按以下顺序解释：

```text
byte_offset = sum(idx[i] * dim_stride[i])
每笔逻辑事务按 16-byte 边界拆分
word_offset = (byte_offset + transfer_bias) >> 4
mapped = permute26(word_offset, address_remapping)
request_word_addr = (mapped + (base_addr >> 4)) mod 2^26
```

`address_remapping[out_bit]` 指定该输出位读取哪个输入位；base 在 remap 后相加。transaction size 由编码后的 `total_size` 决定，`idx_size` 不是索引枚举范围。索引值来自 DRAM/ROW/COL loop 与 LC-PE 表达式；验证器使用共享环境枚举，保留相关性，不把各表达式结果错误地做独立笛卡尔积。

padding/tailing 位于后续读写数据通路，不抑制 Memory_AG 请求，因此命中 padding 或 tailing 的请求仍必须计入地址合法性。read padding 数据优先于 tailing zero；write tailing 是 old-DDR merge。row 等于 6144、30-bit transaction wrap、26-bit base-add wrap、请求落不到目标 SCA region 均 fail closed。

原生配置只携带 slice0 base；execplan 对 slice1～27 发出真实 Write_Reg 覆写高位。因此不能只读 source JSON 判断所有 slice 地址，也不能把每 slice 基址差异误判为 planner 错误。

## 3. 单 stage 正例

持久证据：`artifacts/operator_config_validation/r3-execplan-evidence/decode_summac-seed42-v3/`。

- 原生 execplan 双跑一致，57 条 64-bit 指令；
- 54 条 base Write_Reg（A、D 各 27 条）被按机器位与 explanation 双重绑定；
- 28 slice 共 924 次请求、252 个唯一物理地址，全部落在对应 A/D SCA region；
- 绑定 layout、`qparams.policy=not-applicable`、显式 A/D 尾块和 provenance；
- 原生 `ndp-sim` 提交保持 `ec12424516ae0304228dd2321d4e604fe225e04e`。

## 4. 两 stage 正例

为了验证真实 stage 顺序和地址更新，增加两个独立外部输入的 Decode summac 诊断图。原生 planner 证明 stage1 相对 stage0 只有 stream0/stream1 base 从 `0x0/0x80` 变为 `0x90/0x110`；stage1 配置另行生成零 penalty mapping bundle，不复用 stage0 source-config 哈希。

最终持久证据：`artifacts/operator_config_validation/r3-execplan-evidence/decode_summac-two-stage-seed42-v4/`。

| 项目 | 结果 |
|---|---|
| graph SHA-256 | `20876371887504db28cd5efca2bcfb31fb3a783c9a5bb99cbff73e0462c9ed0b` |
| execplan SHA-256 | `5885868d008ef3de16e65aef11df2e47f5ce386a68f096af370ea37bf9c84344` |
| 64-bit 指令 | 113；2 Load_Config、2 Start_Comp |
| 确定性双跑 | 25 个文件全部一致 |
| Write_Reg | 每 stage 54 条 |
| 请求 | 1848 次；504 个唯一物理地址 |
| 唯一地址表 SHA-256 | `a9b1ab67fcffce77fe3b5ca522c702001be32577e144acb5b51f0f8f90de18f3` |
| SCA/语义合同 | 112 个预期 tensor entry、115 个 region、0 issue；matrix 文件本诊断不要求存在 |
| bundle manifest SHA-256 | `c5c7b3a50abe54c4ba67aff05704999a52d0a0d101577a453d4bc357e35bcf0e` |

这份证据证明真实 execplan 中连续两个 `update` stage 的状态、base 写入和请求地址闭合。它不证明 `reuse/disable` 的服务器行为：update→reuse→disable→非法 reuse 已由外围状态机正负测试覆盖，但真实 RTL/服务器回读仍属于 R6 的 E4/E5 门。

## 5. 负例与回归

R3 故障注入已覆盖未知字段、错误 arity、非法 enum、silent default、位宽 wrap、非零 placement penalty、fallback/cache provenance、RTL 不可达 mapping、bit 篡改、Load_Config 地址错配、source/mapping/SCA 偷换、缺独立 B′、row=6144、尾块越界、未绑定 qparam、remap 后越界和 explanation 重复索引。

2026-07-23 定向回归 63 项通过。55 份活动 JSON 的身份保持 46 strict-valid、9 intentional-reject；9 份只在内存中规范化的副本不授权覆盖源文件，其中 4 份 mapper-blocked 仍不升级为完整 mapping 证据。

## 6. R3 退出与剩余边界

R3 的退出条件是验证器、报告和选定正负样例可稳定定位第一处字段/连接/stage 错误，并非 ResNet50 已可生成或服务器数值已通过。当前满足该本地退出门，因此允许进入 R4 活动规则切换。

仍未完成且不得混报：

1. 真实服务器 CONFIG reuse/disable、非对称 SA、padding/tailing、6144-row 边界和数值回读（R6，E4/E5）；
2. 4 份 legacy 规范化配置的零 penalty mapping；它们不是 R3 验证器退出阻塞，但继续限制对应 legacy 身份；
3. 修改或扩展活动 `ndp-sim`、正式 typed lowering 和 ResNet50 78 节点覆盖（R5/R7）；
4. 当前 `ndp-sim` 本地派生文件的可克隆来源问题；bootstrap 只能保证锁定 clean commit。
