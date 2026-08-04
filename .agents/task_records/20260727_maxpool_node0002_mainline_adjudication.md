# MaxPool node0002 config-only local E2 主线裁决

日期：2026-07-27

## 裁决

主线接受唯一 ResNet50 MaxPool
`node-0002 / r5:hwop-0002-00` 为完整节点
`CONFIG_ONLY_CORRECTNESS_BASELINE`，证据等级为本地 `E2`。该结论覆盖冻结
`uint8[16,64,112,112]→uint8[16,64,56,56]`、3×3、stride2、pads1、输入输出
同 qdomain 的完整 ONNX MaxPool 节点；不计 target simulator、正式 D、production、
性能、E4/E5 或三方动态通过。

因此更新全网计数：

- 精确物化 hwop JSON：增加 1；
- `CONFIG_ONLY_CORRECTNESS_BASELINE`：增加 1；
- 完整 ONNX 节点本地 config-only E2：增加 1；
- 正式 target、E4、E5、正式三方节点：均不增加。

## 接受证据

- family task record：
  `.agents/task_records/20260727_maxpool_node0002_config_only_e2.md`
  @ `85ff606787a923cb3d35fdfbf5126dc7c66065bba642c3a40a5b9ade0ebe221d`；
- machine contract：
  `contracts/operator_config/maxpool_node0002_config_only_e2_v1.json`
  @ `c9833c15844e17b17fbe492175c071d2cc3b19fbf749c6459f360b3ee67a02ce`；
- validation report：
  `artifacts/operator_config_validation/maxpool-node0002-config-only-e2-v1/validation_report.json`
  @ `5fb484e9c1bf40b86d68c21c8837e6a61978e63cac40e9e2f5b3b42ea3dd9a61`；
- 三份最终 address-bound JSON 的 native mapper 均为 `penalty=0`、
  `fallback_used=false`，完成 28+28+8=64 occurrences；
- final leaf diff 只有四个 planner-owned `base_addr`，non-base diff=0；
- 64 个 occurrence 各精确覆盖 50,176 D bytes，总覆盖 3,211,264 bytes；
- config-bound GeneralPEA 对 3,211,264 个逻辑值的 logical/physical mismatch 均为 0；
- 两个隔离 native tool copy 的 35 个受管产物逐 byte 一致，14/14 定向测试通过。

## `CDA-GA-INT8-MAX-PIPE-001` 范围裁决

不存在规则翻案：

- 当前本地 E2 证明的是最终配置绑定软件模型、地址、布局和冻结 unsigned-max
  golden 的一致性；
- `.agents/rules/NDP硬件字段语义.md`
  @ `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59`
  中 `CDA-GA-INT8-MAX-PIPE-001=CONTRADICTED` 证明的是 stock RTL
  `int8_max` lane 极性和 pipeline0 ready/flow 的动态缺陷；
- 本地 config-bound E2 不能覆盖或否定 RTL 动态反例，故该公共规则、对应
  `B_GA_INT8_MAX_NUMERIC` 与 `B_GA_INT8_MAX_FLOW` 全部保持开放。

无需修改公共硬件字段规则。MaxPool 可以计完整节点本地 E2，但不能据此生成服务器
release 或声称实际 stock RTL 已能跑通。

## 绕行与 blocker

本轮没有 host 预计算或算术替代；机制是把可信 MaxPool 模板精确绑定到真实 target，
用三次 native occurrence、独立 A/D allocation、planner base binding、bitstream、
execplan/SCA 和 config-bound simulator 完成闭环。成本是三次 config load/start、
六个物理 allocation 与 64 个 tile occurrence；无吞吐声明。

仍开：

- authoritative target simulator/hardware execution；
- stock RTL GA INT8 max numeric 与 ready/flow；
- E4/E5 与三方比较；
- production throughput/resource；
- common validator 对重复 planner-owned base leaves 的通用支持。

`PACKAGE_RELEASE=NONE`。未检查服务器文件、名称或 identity，未上传、未运行，
未修改功能 RTL或公共硬件字段规则。
