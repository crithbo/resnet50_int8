# 复用优先、算子免复测、整网失败再回查主线策略

日期：2026-07-28

## 用户要求与主线裁决

用户明确要求：能够复用的算子不再单独复测，直接进入 ResNet50 整网；如果最终整合出现
问题，再按首分歧返回对应算子族查验。

主线接受并发布 `CDA-REUSE-FIRST-DEFERRED-RETEST-001`。该规则把复用资产状态定义为
`REUSE_ACCEPTED_FOR_INTEGRATION`：

- 不重跑 operator golden、定向 unittest、operator-only config-bound simulator、
  单算子动态运行或未改变的 native template reconstruction；
- 只建立不可变 source SHA、reuse class、目标节点/stage、参数替换、deferred blocker
  和 fallback owner；
- 首次整网比较失败后，只重开首分歧 owner，其他 reuse binding 保持冻结；
- 免复测不等于 E2/E4/E5、正式 target 或 blocker close。

## 当前整体进度

| 口径 | 当前值 | 边界 |
|---|---:|---|
| ONNX 节点 | 78 | 全部已有 typed request |
| hardware stages | 133 | 全部已有 stage lowering |
| 非 Conv 节点复用路径 | 25/25 | exact、approved-equivalent 或 primitive/structure reuse 均已指定 |
| 完整节点直接复用候选 | 4/78 | Dequant×2、MaxPool×1、Flatten×1 |
| 已复用前半段的复合节点 | 18 | QLinearAdd stage0×17、GAP sum×1 |
| exact UINT8 tail consumer | 74 | 只实现一次公共能力，不逐节点复测 |
| INT8 SA consumer | 54 | Conv×53、MatMul×1，共用 serialized 参数化路线 |
| 133-stage 整网 assembly | 0/1 | 尚未生成，是下一主线交付 |
| 完整 ONNX 节点本地 E2 | 2/78 | 历史证据计数，不因免测增加 |
| 正式三方节点 | 1/78 | Dequant node0077，保持不变 |

“25/25 非 Conv 节点有复用路径”不表示 25 个完整 backend 已正式通过：

- `EXACT_FULL_OPERATOR`：完整资产直接进入整网；
- `APPROVED_EQUIVALENT`：复用已批准的计算边界；
- `STRUCTURE_OR_PRIMITIVE_ONLY`：只复用相同字段、拓扑、transport，缺失计算继续归入
  shared capability gap。

因此真正仍需开发的独立能力只保留两项：

1. `R5_GAP_EXACT_UINT8_QUANT_TAIL`：覆盖 74 个 consumer；
2. `R5_GAP_INT8_SA_DOT_PRODUCT`：把已证明的 serialized route 参数化覆盖
   53 Conv + 1 MatMul。

QLinearAdd、GAP、MaxPool、Flatten 后续只做整网 graph/allocator/address/lifetime/
execplan binding，不再派发已完成部分的算子复测。

## 新执行顺序

1. 冻结 reuse binding manifest；
2. 完成 exact UINT8 tail 与 serialized SA 两个共享能力；
3. 一次性生成 133-stage integrated graph、全局地址/lifetime、execplan/SCA；
4. 运行首次整网 config-bound 比较；
5. 只有出现首分歧时，才回查命中的算子族。

## 活动身份

- machine policy：
  `contracts/operator_config/resnet50_reuse_first_integration_policy_v1.json`
  @ `c8886c946a15e281e2b9fc40c3e37523cc00d3aab330131572887f3d64de6960`；
- common operator rule：
  `.agents/rules/算子配置规则.md`
  @ `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`；
- routing index：
  `.agents/rules/生成前必读索引.md`
  @ `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`；
- source reuse audit：
  `contracts/operator_config/resnet50_ndpsim_reuse_gap_audit_v1.json`
  @ `ca3daf485f4098793e1c4544139c22e62119dbe5743e0db02e4e07d7c301c7c5`。

## 授权边界

本轮未修改功能 RTL，未检查服务器文件或名称，未生成服务器包，未上传、未运行，
未授予 `SERVER_RUNNING` lease。
