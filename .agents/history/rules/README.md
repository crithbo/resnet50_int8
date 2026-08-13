# 停用规则统一入口

最后更新：2026-08-11

本目录保存已停用、被取代、异项目或正交化前的规则原文，仅用于 provenance、审计和解释
旧 task record。它不是活动规则入口：默认会话不得读取这里来生成 JSON、测试包、RTL
repair 或放行结果；任何历史文件都不能因被旧记录引用而重新获得授权。

当前有效规则只允许出现在 `.agents/rules/`，exact-set、职责和 SHA 由
`contracts/active_rule_registry_v1.json` 登记。需要恢复历史语义时，必须先证明其仍适配
current source/contract，由唯一活动 owner 提交非同义 rule delta，经过裁决后写回对应活动
规则；禁止直接移动历史文件回 `.agents/rules/`。

## 归档清单

| 原活动文件 | 历史路径 | 分类 | 当前替代入口 |
|---|---|---|---|
| `DeepSeek_GEMM增量规则.md` | `deepseek/DeepSeek_GEMM增量规则.md` | 异项目 | 无；ResNet50 会话不读 |
| `DeepSeek_ONNX到Stage验证规则.md` | `deepseek/DeepSeek_ONNX到Stage验证规则.md` | 异项目 | 无；ResNet50 会话不读 |
| `DeepSeek_RMSNorm增量规则.md` | `deepseek/DeepSeek_RMSNorm增量规则.md` | 异项目 | 无；ResNet50 会话不读 |
| `DeepSeek_RoPE增量规则.md` | `deepseek/DeepSeek_RoPE增量规则.md` | 异项目 | 无；ResNet50 会话不读 |
| `DeepSeek_Softmax增量规则.md` | `deepseek/DeepSeek_Softmax增量规则.md` | 异项目 | 无；ResNet50 会话不读 |
| `DeepSeek_码流生命周期增量规则.md` | `deepseek/DeepSeek_码流生命周期增量规则.md` | 异项目 | 无；ResNet50 会话不读 |
| `DequantizeLinear原子动态合同规则.md` | `resnet50/DequantizeLinear原子动态合同规则.md` | 版本化动态合同，被族规则/服务器规则取代 | `DequantizeLinear算子配置规则.md` + `服务器测试包生成规则.md` |
| `GAP_probe_v7_validator_rules.md` | `resnet50/GAP_probe_v7_validator_rules.md` | 版本绑定、重复定义 | `GAP_int32_mac_bypass_rules.md` + `服务器测试包生成规则.md` |
| `GAP_repair_candidate_rules.md` | `resnet50/GAP_repair_candidate_rules.md` | 一次性 repair 授权历史 | current plan + 本轮用户 RTL 授权 + 公共服务器规则 |

## 正交化前快照

`resnet50/*_pre_orthogonalization_20260811.md` 保存 2026-08-11 清理前的活动族/原语规则
文本。快照只用于核对被剥离的版本状态是否仍可追溯；其稳定语义已由同名活动规则继承，
其 package SHA、return 结论、当前 blocker 和一次性授权已回归 plan/task record 所有权。

## 使用纪律

1. 新会话 handoff capsule 不得把历史规则列为 mandatory read。
2. validator、builder 和 dispatch contract 不得依赖历史路径；旧版本工具可保留只读引用，
   但不能作为 next-fresh 发布入口。
3. 历史文件中出现的 `CDA-*` ID 不参加活动唯一性统计，也不覆盖 current 定义。
4. 归档不删除证据、不改变 plan 状态、不修改 package、RTL、config 或服务器状态。

