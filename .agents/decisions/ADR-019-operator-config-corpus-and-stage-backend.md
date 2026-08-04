# ADR-019：建立算子配置语料合同并启动 hardware stage→JSON 后端

日期：2026-07-23

状态：accepted；首个 MaxPool candidate emitter 与 View 零拷贝 emitter 已实现，其余算子族继续 fail closed。

## 1. 背景

活动 `ndp-sim/jsons` 当前包含 55 份顶层静态配置，根仓 `jsons` 保存若干用户确认可运行的 DeepSeek 服务器包，用户另提供了
`register_map_with_groups1_20260527.xlsx`。此前 R0～R4 已证明这些 JSON 可以接受严格 schema、mapping、bitstream、execplan、地址和语义验证，但没有把这些配置整理成可供 R5 lowering 消费的模板语料和 stage backend。

本决策将三类证据分开：

1. 静态模板和服务器专用实例用于提炼结构、参数和调度关系；
2. Excel 用于字段名、硬件端口和备注语义，不作为未经仲裁的位偏移真值；
3. 真实服务器日志只按 E0～E5 证据等级登记，不因文件夹存在而提升。

## 2. 硬件测试证据裁决

机器审计入口：

```text
tools/build_operator_config_corpus.py
contracts/operator_config/ndpsim_json_hardware_evidence_v1.json
```

55 份当前模板中：

- 42 份出现在历史权威库存，35 份被分类为 DeepSeek Transformer 模板；
- 用户确认的 DeepSeek 整网基线支持公共硬件方法继承，但仓库没有 35/55 份逐文件原始执行回执；
- `decode_summac_fp32N_fp32N.json` 有用户报告的自然完成 E3；
- `decode_max_fp32N_fp32N.json` 已找到原始 `sim.log`，日志包含真实 preload、slice start、66-cycle completed、每片 MSE4 写数据和自然完成；28 个有效最低 32-bit 写数据与本地 D Golden 全部一致，故为 E3。实际命令遗漏 `+SCA_CFG_D`，testbench 默认寻找 `sca_cfg_D_softmax.json` 并跳过正式 DDR readback，不能升级 E4；后续必须显式绑定本包 `sca_cfg_D.json`；
- `maxpool_config_16_112_112_stride2_padding1.json` 与原 `node0004_accumulate_wave0.json` 保存硬件非完成负证据；
- `node0004_accumulate_wave0_nopp_r1.json` 的服务器尝试缺失 A/B/C 与 bitstream 文件，随后跑到仿真上限；该尝试无效，不能算 E3 或配置失败。

因此“55 份全部经过硬件测试并通过”不能由当前仓库证明，并且与已有负证据冲突。后续允许继续把 DeepSeek 基线作为公共结构/物理先例，但不得把它升级成逐模板 E4/E5。

## 3. 寄存器语义合同

`tools/build_register_semantics_contract.py` 支持直接读取 xlsx，也可用仓内 CSV 回退。生成的
`contracts/operator_config/register_semantics_v1.json` 保存：

- 配置名、硬件端口、备注、默认值；
- JSON 字段匹配；
- 当前 encoder `FIELD_MAP`；
- Excel 中 13 项 declared-width/bit-range span 冲突。

Excel 只负责字段语义。位宽和打包以当前 encoder 为实现事实、以活动 RTL 为最终事实；冲突未裁决前不得把表中 `[hi:lo]` 直接写入 codegen。

## 4. 模板与调度规则证据

`contracts/operator_config/ndpsim_json_corpus_v1.json` 规范化 55 份配置的结构、字段路径、模块特征、graph 引用和服务器实例。

`contracts/operator_config/config_rule_evidence_v1.json` 对同族 shape 和模板→服务器实例做逐叶差分。16×16 与 16×112×112 MaxPool 不仅改变地址和数值，还改变 LC end/last-index、ROW_LC source、stream stride、padding 上界和 buffer keep/full 边界。由此规定：

- 地址可后绑定；
- shape 变化必须经过 schedule rule；
- topology 变化不得作为普通参数插值；
- 数值字段变化必须绑定 typed qparam；
- 每条规则必须反向复现已知 JSON。

## 5. Stage backend

新增 `resnet50_pipeline/stage_config_backend.py`：

```text
typed lowering request
  -> request/hash/effective-resolution validation
  -> ScheduleIR
  -> strict address-unbound candidate JSON
  -> manifest
```

当前已实现：

- `MaxPoolUint8`：仅接受 ResNet50 `hwop-0002-00` 的精确签名，产生 64 tile、`[28,28,8]` 三波调度和严格 JSON；
- `View`：产生零拷贝 alias binding，不生成硬件 JSON。

Conv accumulate、requant、Add、Quant/Dequant、GAP、MatMul 已登记模板证据和精确 blocker，但在 shape、qparam、tail 或 E5 未闭合时拒绝生成。首个物化候选为
`configs/stage_codegen/hwop-0002-00-v1`，身份是 `candidate_address_unbound_not_formal`；它不改变正式 target config 仍为 0/133，也不提升 E4/E5。

## 6. 下一顺序

1. 以 node-0004 strict 配置为 Conv accumulate 的结构种子，先闭合 signed A/unsigned B、非对称 SA layout、K tile/psum 与 shape schedule；
2. 以 quant 模板闭合 per-channel multiplier 放置、舍入、饱和和 zero-point；
3. 依次闭合 Add、Quant/Dequant、GAP、MatMul；
4. 每类先复现已有 JSON，再生成非对称微测候选并取得服务器 E4/E5；
5. 最后推广到 133 stage 和整图地址/生命周期。

## 7. 后续实施进展（2026-07-23）

硬件证据审计已补充原始服务器回执绑定。当前 55 份活动模板中：

- 精确正向 E3 为 2 份：`decode_summac_fp32N_fp32N.json`（用户报告）和
  `decode_max_fp32N_fp32N.json`（原始 `sim.log`）；
- 精确硬件负证据为 2 份：MaxPool 112×112 与旧 node-0004；
- node-0004 nopp-r1 的服务器尝试为无效尝试：预载数据和 bitstream 缺失，不能计作
  配置通过或配置失败；
- 精确数值 E4 仍为 0。

因此新增两个只读机器合同，继续把“本地静态/数值闭合”和“硬件放行”分开：

1. `contracts/operator_config/node0004_conv_schedule_evidence_v1.json`
   - 绑定 `r5:hwop-0004-00`、strict config、语义合同、零罚分 mapping、确定性
     execplan、逐请求地址报告、W3 输入清单及硬件审计；
   - 闭合 wave-0 的 28 个 tile、signed-A/unsigned-B、C=bias、D=INT32 psum、
     SA 非对称端口和 28 slice 请求事实；
   - 明确完整算子为 64 个 `(sample,K16)` tile，当前还有 36 个 tile 未被该配置覆盖，
     不得把单 wave 冒烟配置推广为完整三波次 Conv emitter。
2. `contracts/operator_config/node0004_requant_semantics_evidence_v1.json`
   - 只使用活动 `ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json`，不读取
     `ndp-sim-ref` 或旧 requant 输出；
   - 闭合 64 个 per-channel multiplier、8 lane × 8 组的 GA 参数放置、magic-add /
     int32-sub 舍入路径和 uint8 饱和；
   - 对 W3 的 3,211,264 个元素独立重放为 `mismatch=0`，但该结果仍是本地数值证据，
     不能代替目标硬件 E4/E5。

`artifacts/operator_config_validation/r5-server-candidates/node0004-nopp-r1-v2`
已经包含 378 个 payload 文件、28 slice 的 336 个 A/B/C/D 伴随文件和真实
`install/cfg_pkg` bitstream，本地完整性测试通过。已有服务器“缺文件”日志不能绑定到
这棵完整候选树；下一次必须从该目录内容作为服务器工作目录执行，并保存新的原始回执。
在取得有效 E4 前，Conv accumulate 和 requant emitter 均继续 fail closed。

## 8. ADR-021 来源范围覆盖说明（2026-07-23）

ADR-021 后续确认根仓 `jsons` 12 份，以及 `ndp-sim/jsons` 中与固定云端提交逐文件
一致的 53 份配置，可视为正确、高强度参考基线。因此，本 ADR 中“必须先找到逐文件
原始服务器回执才能采信配置语义”的限制对这 65 份参考配置被覆盖；上述 E3、负回执、
无效尝试及 E4 计数继续保留，只用于描述本项目具体包和具体运行的证据状态。

两份 `node0004*` 配置是固定提交之外的项目新增文件，未通过测试，不得由目录位置自动
获得正确性授权。规则提炼、已知配置反向复现和同族 ScheduleIR 开发可直接使用上述
65 份参考配置；项目新增配置、新 shape、地址、常量、拓扑及 ResNet50 派生候选仍须
通过严格本地链和服务器 E4/E5，不得由源目录或相邻模板正确性自动晋升。
