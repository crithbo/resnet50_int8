# Native reference / handler / composition 规则语义主线裁决

日期：2026-08-06  
提案 task：`019fd276-14c5-7800-94db-87ebfb9ce632`  
主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 只读审计事实

- pinned upstream `ndp-sim@ec124245`共有53个JSON；47个属于transformer
  decode/prefill/GEMM/GEMV，ResNet-adjacent仅6个：
  add_dequant、avgpool、两份maxpool、int32→uint8 quant和sum。
- active `ndp-sim/jsons`另有5个project-added untracked文件；它们不属于upstream Git
  tree，不能冒充native authority。
- ResNet50 lowering bundle共有78 nodes / 133 hardware stages；其中
  ConvInt32Accumulate 53、RequantizeUint8 54，二者共107/133。native JSON不能单独覆盖
  整网，但可作为部分primitive/control field参考。
- `model_execplan`注册31/53 templates；22个未注册。handler map覆盖48/53；
  avgpool、两份maxpool、gemv_local、sum没有handler。现有量化/add_dequant handler及
  handler文档含placeholder/example/conservative语义。
- `output_writer`主要读取source JSON、修改base和应用局部update。存在JSON、registry或
  handler不能证明支持新shape/dtype/qparam/layout/address/cross-stage schedule。

## 主线裁决

三项提案均为现有规则无法机器表达的独立语义门，正式接受：

1. `CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001`
2. `CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001`
3. `CDA-NATIVE-COMPOSITION-BOUNDARY-001`

它们分别关闭：

- source实例字段正确被错误外推到target leaf；
- registry/handler存在被错误解释成新shape/参数泛化能力；
- primitive正确被错误提升为跨模板composite正确。

同时正式纳入：

- native authority必须绑定Git tree中的repo/commit/path/blob SHA、source typed
  signature和source direct consumer；
- target required leaf必须区分absent/not-applicable/unknown/null/zero/derived，
  禁止nearest-template和implicit-zero；
- generation receipt绑定实际相关generator tree与patch manifest，不能只信repos.lock；
- existing frozen package不因规则发布追溯重建；fresh/changed target JSON、handler路径或
  composition boundary触发本门。

## 更新收据

- `.agents/rules/生成前必读索引.md`
  - bytes=`11916`
  - SHA256=`bc319a157ec3d55ae0fce998e5f44365085ebfebed1e252aabcfe72d0144dc09`
- `.agents/rules/算子配置规则.md`
  - bytes=`31837`
  - SHA256=`90c6fe4b12f1026480daa55682405288ae2f74f46931c1a7848353ec37e8a2f5`

## Claim boundary

本裁决只发布以后fresh/changed配置的字段适用性、handler能力和组合边界门。它不宣称
任一现有算子E2/E4/E5通过，不授权RTL修改，不把project-added JSON提升为upstream native，
也不改变当前已发布服务器包的运行资格。
