# ADR-003：W4 profile/transition综合审计与G4门结论

状态：G4未通过，等待正式硬件布局与拓扑裁决
日期：2026-07-12

## 决定

W4计划内全部算子族的软件candidate readiness通过，但G4保持未通过，W5不获授权。项目停在W4/G4边界，等待硬件侧给出带版本的正式profile与物理layout批准；不得把任一candidate改写为approved，也不得用candidate直接生成目标INT8 JSON/bitstream。

机器审计报告：`artifacts/w4/g4_gate_audit.json`，100,609 bytes，SHA-256 `f4bd5d3e84ad6c022729179fe2ce01643792c9fedb792bf61c58b83684e32a5a`。

## 软件审计通过项

- 正式图78/78节点均有W4 candidate：2 Quantize、53 QLinearConv、1 MaxPool、17 QLinearAdd、1 QLinearGlobalAveragePool、1 Flatten、1 QLinearMatMul、2 Dequantize。
- 12个W4 layout candidate对应的实现均提供`forward/inverse/explain_coordinate/validate`。
- 已登记的5份算子族正式报告及2份Conv0报告共7份证据，其文件大小和SHA-256全部匹配合同。
- 正式图93条runtime tensor边均分别给出batch和ring/channel责任；91条量化边的producer输出与consumer输入scale/zero-point稳定tensor ID全部一致。
- batch候选边分类：4条已证明exact alias、1条显式relayout、87条layout-compatible并留W7统一base、1条zero-copy View。
- ring/channel候选边分类：3条已证明exact alias、4条显式relayout、85条layout-compatible并留W7统一base、1条zero-copy View。
- 最小shape、正式shape、tail/inactive slice、qparam副本、容量、坐标与raw→physical→raw回归均通过；当前根仓共68项测试。

## 重要审计解释

1. GAP报告中的D→Flatten是singleton H/W的存储视图证明，不是正式图直接边。正式图为`GAP node-0071 → Dequantize node-0072 → Flatten node-0073`；batch GAP D与Dequantize A布局兼容并需W7统一base，channel GAP D需显式转batch，然后Dequantize D→Flatten才是zero-copy View。
2. standalone bundle上的exact alias不等于网络级地址已经分配。双残差输入、连续算子和head重用的同时生存/覆盖关系由W7负责；本审计只批准布局兼容性与转换责任。
3. ring/channel候选在当前batch simple-op边界存在显式转换：输入Quantize→Conv、Quantize→MatMul，以及GAP/dense Add输出→Dequantize。
4. W4保存的是Conv/MatMul完整K reduction后的INT32 accumulator；首/中/末K tile或逐ring-step psum的正式物理位置依赖目标tile/JSON合同，不能由W4 candidate自行批准。

## G4阻塞项

以下三项均为false，因此G4不能通过：

1. `approved_target_profile_exists`：当前12个W4布局全部仍为candidate，没有批准的整网profile。
2. `target_rtl_isa_register_map_version_frozen`：没有给出适用的RTL/ISA/register-map完整commit或版本。
3. `approved_physical_layout_contract_exists`：activation、weight、bias、qparams、psum、D的正式物理布局尚未批准。

资源数/字段位宽、opcode、DDR row与地址单位、instruction mask、加载/启动/等待/错误/dump协议仍在`contracts/architecture.json`的unresolved账本中，后续W5～W8也依赖这些事实。

## 等待硬件侧裁决

除ADR-002的Conv问题外，需要硬件侧一次性回答并注明适用版本：

1. 批准整网采用batch profile、ring/channel profile，还是逐算子混合profile；若混合，批准每类D→A转换由remapping、stream还是显式relayout承担。
2. 批准每个端口的slice owner、物理轴序、tile/padding/tail、复制规则、byte/word地址单位和128-bit lane字节序。
3. 批准Conv/MatMul的K tile、INT32 psum保存位置与生命周期、ring方向/起点/结束条件、requant与writeback阶段。
4. 提供答案对应的RTL/ISA/register-map commit，以及最小可执行的load/start/wait/status/dump协议或runner/testbench。

## 裁决后动作

- 将获批profile写成新的版本化`approved`合同，不原地篡改candidate证据。
- 使未获批candidate及其下游JSON/地址产物显式失效。
- 重新运行本G4审计；只有三个阻塞条件全部转为true且回归保持通过，才允许将G4标记通过并进入W5。

## 批准记录

- 批准整网profile：待填写
- 适用RTL/ISA/register-map版本：待填写
- 物理layout合同版本：待填写
- 批准人和日期：待填写
- 原始回复/证据链接：待填写
