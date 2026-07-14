# RTL28 硬件批准请求包（可直接转发）

状态：`approval_request`，不是批准文件。请三类责任方分别答复下述 `APR_*` 项，并由最终硬件权威合并签署；未明确答复、`TBD`、口头确认或仅引用本项目 candidate 均不视为批准。

## 1. 固定审查对象与回复规则

本请求只适用于以下唯一目标，不接受从其他分支或旧 16-slice 文件混选结论：

- repository：`https://github.com/xlsjdjdk/Trassic2.0_RTL`
- commit：`e3bdebba95dec36ee8eba43caa92a326a88392cd`
- top source：`code/NDP_rtl/NDP_Top.sv`
- top module：`NDP_Top_new`
- authoritative filelist：`code/NDP_rtl/filelists/NDP_Top_filelist.f`
- architecture ID：`trassic2_rtl28_candidate_v1`
- topology ID：`rtl28_high7x4_low28_e3bdebba`

请每类责任方返回：

1. 一份有姓名、组织、日期、适用 commit 的书面决定，逐项写明 `approved` 或 `rejected`，保留原 `APR_*` ID；若拒绝，请给出替代真值及其版本。
2. 表中要求的原始文件，不要只返回截图、聊天摘录或二次摘要。每个原始文件都要给出稳定 URI/路径和小写 64 位 SHA-256；另附 `SHA256SUMS`，摘要覆盖文件内容而不只覆盖压缩包。
3. 生成文件所用的完整命令、工作目录、工具版本、目标 commit 和非敏感环境信息。许可证密钥可以删除，但 simulator、vendor library/IP 版本及 `protected128` 支持不得隐去。
4. 若实际权威对象与上述任一固定项不同，请停止批准并返回 `rejected`；不要把其他 commit 的成功日志套用到本合同。

本请求基于以下本地 candidate 材料；它们可用于定位问题，不能作为责任方批准的替代品：

| 文件 | SHA-256 |
| --- | --- |
| `contracts/rtl28_candidate_audit.json` | `69505a527a53c25b0bb828b192aba991fba78e838a2429f9cb99d251b8a815aa` |
| `contracts/rtl28_candidate_audit.md` | `ab8e703c379e1598db39b1cc4820bf5eea680d475f374a88bc04188348b5a977` |
| `schemas/hardware_approval.schema.json` | `c591e95e46e649e6e8bcea95017f5e49a0efa2bcd0dd9418681b725f5c2dea96` |
| `resnet50_pipeline/hardware_approval.py` | `95807e042f009771f704d728906c4c7751a3e8b1a8202a0f7986c85e86f349a0` |

## 2. 发给 RTL / 集成人员

### `APR_ELAB_001`：构建权威与 clean elaboration

- 需决定：批准或拒绝上述 top/filelist；给出正式 ISA version、register-map version、权威 simulator/toolchain、`MC_DIR`、`DIR_HOME`、vendor library/IP 与许可证环境。
- 现有证据：`EV_FILELIST`、`EV_TOP_PORTS` 固定了 active top；`EV_DDR_FILELIST`、`EV_MC_FILELIST`、`EV_PROTECTED_MODEL`、`EV_NIC_FILELIST` 证明 closure 依赖 `MC_DIR`、`${DIR_HOME}/Hardware/IP/bus/nic_cgra_0310` 和 `protected128`。`EV_LINT_SCRIPT` 指向旧 top/路径，`EV_LINT_SUMMARY` 是 7 errors/436 warnings 的失败记录，均不能证明 clean elaboration。
- 建议从 `code/NDP_rtl/filelists` 执行：

```bash
export MC_DIR="<absolute checkout>/code/NDP_rtl/DDR_Model/MC_IP/rtl"
export DIR_HOME="<approved root resolving Hardware/IP/bus/nic_cgra_0310>"
vcs -full64 -sverilog -top NDP_Top_new -f NDP_Top_filelist.f -l vcs_elab.log
```

  可以使用等价权威工具，但必须支持 active `.vp` 的 `protected128` 解密/编译及所需 vendor libraries；不得以 Icarus 展平尝试、旧 lint summary 或黑盒跳过替代完整 elaboration。
- 必须返回的原始文件及各自 SHA-256：完整 `vcs_elab.log`（或等价日志）、tool/version 输出、实际 argv/cwd/exit-code 记录、解析后的完整 source/include/library 清单、`MC_DIR`/`DIR_HOME` 解析记录、`git rev-parse HEAD`/dirty 状态、warning waiver/triage（若有），以及逐项签署的 `APR_ELAB_001` 决定。
- 接受条件：exit code 0；commit/top/filelist 完全一致；没有 unresolved module/include/library、加密体/许可证错误、blackbox 或 error；所有 warning 均保留并完成书面分级。否则该项拒绝。

### 需共同签署：`APR_WAIT_008`

请与板级/固件共同确认 BARR：`EV_SEM_DECODE`/`EV_SEM_FSM` 显示 opcode `110` 只声明常量但未进入 slice FSM。请返回“不可使用”或给出实际同步实现及原始 RTL/test 日志；沉默不能解释为 barrier 已实现。

## 3. 发给 RTL + 量化 / 编译人员

### `APR_INT8_004`：INT8 端口、bias 与 psum

- 需决定：activation/weight 分别绑定 PEA DataA/DataB 的哪一端，byte/lane/endian 顺序，activation/weight zero-point 的处理位置，bias dtype/signedness/layout，accumulator 位宽/符号/overflow，以及首、中、末 K tile 的 psum 生命周期。
- 现有证据：`EV_SA_INT8_SIGN` 只证明原语表现为 signed-A × unsigned-B；`EV_SA_BIAS`、`EV_SA_PSUM` 只证明 input group 2 可初始化 outbuffer psum。模型数学类型已经固定为 UINT8 activation × INT8 weight + INT32 bias，但这不自动决定物理 A/B 绑定。
- 必须返回：获批的最小 INT8 Conv 配置/指令源文件，A/B/bias/psum/D layout manifest，输入向量、逐步 INT32 accumulator 与最终 D 的原始 dump，复现脚本/命令和 bit-exact 比较日志，以及上述每个文件的 SHA-256 和签署决定。

### `APR_QPARAM_005`：完整 requant 与 qparams 传递

- 需决定：scale/multiplier 编码、zero-point 加入阶段、`nearest_even` rounding、UINT8 saturation、per-channel qparam 顺序/对齐/owner、qparams 是 constant patch、tensor stream、control write 还是逐层静态配置，以及精确 SA/GA 指令序列。
- 现有证据：`EV_GA_CLAMP` 只提供 INT32→UINT8 clamp，没有 scale/zero-point/rounding；`EV_GA_PE_CONFIG` 暴露 constant WREG 的 `INPORT_ID+1`/`INPORT_ID+2` 地址错位迹象，静态阅读不能裁决。
- 必须返回：qparam 编码规范、获批配置/指令、至少覆盖 rounding tie、负值、0/255 饱和、非零输入/输出 zero point 和 per-channel scale 的原始向量及输出，GA constant 地址裁决及 RTL/test 证据，复现日志、签署决定和全部 SHA-256。
- 接受条件：完整链可重放并与项目所需 `nearest_even` + UINT8 saturation bit-exact；只批准 clamp 或只给浮点公式视为拒绝。

### `APR_CONV_006`：Conv lowering 与可执行 profile

- 需决定：Conv tile、padding/stride、DRAM placement、buffer lifetime、HIGH/LOW route、28-bit mask、同步与实测性能配置；同时审核 activation/weight/bias/qparams/psum/output 的 owner、axis order、alignment、tail、address unit。
- 现有证据：`EV_ARRAY_PARAMS`、`EV_SA_CONFIG`、`EV_GA_PE_CONFIG`/`EV_GA_OUT_CONFIG` 固定了原语，权威 closure 内没有命名 Conv/requant 模块。项目的 RTL28 layouts 仍是 software candidate，不是硬件 schedule 真值。
- 必须返回：批准的 source config/JSON/指令流、每个物理对象的 layout 表、地址/生命周期图、对应 input/output dump、cycle/performance 原始日志及测量环境、复现命令、签署决定和全部 SHA-256。估算值必须标为 estimate，不能作为 measured cycle。

## 4. 发给板级 / 固件人员

### `APR_BOARD_002`：板级地址、端口与初始化

- 需决定：host 看到的 `m_axi_reserved` 物理 base，`0x8...` register window 的板级映射，转发 DRAM map，byte/beat/endian/alignment，APB 初始化，clock/reset/`ras_clr` 时序，以及 logical 128-bit 与 physical 144-bit/ECC、bank/row/column 和实际容量的对应。
- 现有证据：`EV_TOP_PORTS`、`EV_TOP_EXTERNAL_BRIDGE`、`EV_REG_DECODE` 固定了 RTL 结构；`EV_DDR_PARAMS` 固定的是每 slice 4×6144×64×16-byte 的逻辑几何，不能证明板卡容量或 ECC 映射。
- 必须返回：权威 board/SoC memory map、接口/端序/对齐规范、clock/reset/APB sequence、ECC/bank 映射，最小初始化/读写 test 日志或波形，板卡/bitstream/driver 版本，签署决定和各文件 SHA-256。

### `APR_FW_003`：命令 ABI 与 load/start

- 需决定：64-bit command ABI、每个 128-bit execution beat 内两条 command 的顺序、`init_exec_inst_length` 单位、CFG base/length 单位、地址对齐、reset/load/start 顺序和目标 slice mask。
- 现有证据：`EV_SEM_DECODE`、`EV_SEM_WREG_FIELDS`、`EV_GLOBAL_REGS`、`EV_EXEC_FETCH`、`EV_CFG_FETCH`。尤其 `init_exec_inst_length` 控制 128-bit response beats，随后才拆成两个 64-bit commands，不能未经批准按 64-bit command 数解释。
- 必须返回：固件 ABI/packing 规范、可重放的最小 execution list、loader/runner 源码或原始 testbench、总线 trace/log、签署决定和全部 SHA-256。

### `APR_DUMP_007`：输出与 readback

- 需决定：output placement、有效时刻/completion fence、readback/dump API、传输尺寸、cache/coherency、物理到比较格式的转换和错误返回。
- 现有证据：`EV_TOP_EXTERNAL_BRIDGE` 与 `EV_REG_DECODE` 只证明非寄存器 AXI read 可结构性转发；不存在已批准 top-level dump 合同，VCD/FSDB 也不是硬件 dump API。
- 必须返回：runner/driver/testbench 源码、输出地址/layout 规范、一次完整 load→start→wait→dump 的原始命令/log/status/raw dump、期望值比较报告、签署决定和全部 SHA-256。

### `APR_WAIT_008`：完成、超时与错误

- 需决定：`fetch_finish`、overflow、28 个 slice-finish bits 的成功 mask，timeout、错误恢复、reset 和 completion fence；与 RTL 方共同裁决 BARR opcode `110`。
- 现有证据：`EV_GLOBAL_REGS`、`EV_EXEC_FINISH` 固定了可见状态；`EV_SEM_FSM` 显示 BARR 没有执行状态。RTL 没有给出 host timeout/error policy。
- 必须返回：wait/status/error 状态机规范、timeout 数值及单位、失败注入和恢复日志、barrier 裁决、签署决定及全部 SHA-256。

## 5. 如何回填现有 `hardware_approval` 合同

三方答复验收后，由有权承担最终批准责任的人合并为 `contracts/hardware_approval.json`。不要让项目开发者代写“示例批准”。该 JSON 必须严格符合 schema 0.2，且不允许额外字段：

| schema 字段 | 回填来源 |
| --- | --- |
| `schema_version`, `contract_type`, `status` | 固定为 `0.2`, `hardware_approval`, `approved` |
| `approval_id`, `authority.{name,organization,approved_at}` | 最终可识别批准人；日期为 ISO `YYYY-MM-DD` |
| `target_version` | 固定 repository/commit/top/filelist/architecture ID/schema version；RTL 方补 `isa_version`、`register_map_version` |
| `clean_elaboration` | `APR_ELAB_001` 的 `approved`、tool、tool_version、原始 log URI 与 log SHA-256 |
| `architecture` | 三方批准：`rtl28`、28 slices、上述 topology；SA 8×8、GA 4×4、mask 28；DRAM 4 banks、6144 rows、64 cols、16-byte subword、byte address、顺序 `slice_owner, local_bank, row, column, byte_offset` |
| `network_profile`, `operator_layouts` | 从下表选择一整套 exact ID；不能混搭，且仍须由 current architecture 登记为 gate-eligible |
| `physical_objects` | `APR_INT8_004`/`APR_QPARAM_005`/`APR_CONV_006`/`APR_BOARD_002`：activation、weight、bias、qparams、psum、output 各填 owner、axis_order、alignment_bytes、tail_rule、address_unit |
| `numeric_semantics` | `APR_INT8_004`/`APR_QPARAM_005`：accumulator_bits、overflow、requant multiplier encoding/`nearest_even`/`uint8`/zero-point stage、qparams transport、psum lifecycle |
| `isa` | `APR_FW_003` + RTL 签署：整数 opcode map、所有 field widths（`slice_mask=28`）和 mask semantics；BARR 必须与 `APR_WAIT_008` 裁决一致 |
| `runtime_protocol` | `APR_BOARD_002`/`APR_FW_003`/`APR_DUMP_007`/`APR_WAIT_008`：非空的 load_config、load_data、start、wait、status、error、dump |
| `evidence[]` | 上述原始文件逐项填写 kind、稳定 URI、内容 SHA-256；至少一项，但应覆盖全部批准结论 |

可选 profile/layout 必须整套选择：

| family | 主 profile `w4_group4x7_batch_channel28_candidate_v1` | 比较 profile `w4_global_ring28_candidate_v1` |
| --- | --- | --- |
| simple | `w4_simple_group4x7_28_candidate_v1` | `w4_simple_global_ring28_candidate_v1` |
| view | `w4_zero_copy_view_group4x7_28_candidate_v1` | `w4_zero_copy_view_global_ring28_candidate_v1` |
| conv | `w4_conv_group4x7_28_candidate_v1` | `w4_conv_global_ring28_candidate_v1` |
| maxpool | `w4_maxpool_group4x7_28_candidate_v1` | `w4_maxpool_global_ring28_candidate_v1` |
| add | `w4_qlinearadd_group4x7_28_candidate_v1` | `w4_qlinearadd_global_ring28_candidate_v1` |
| global_average_pool | `w4_globalavgpool_group4x7_28_candidate_v1` | `w4_globalavgpool_global_ring28_candidate_v1` |
| matmul | `w4_qlinearmatmul_group4x7_28_candidate_v1` | `w4_qlinearmatmul_global_ring28_candidate_v1` |

## 6. 总体验收、拒绝与边界

只有八个 `APR_*` 全部有可重放原始证据、匹配 SHA-256 和具名批准，合并合同才能标记 `approved`。以下任一情况必须拒绝或保持未决：目标 commit/top/filelist 不一致；elaboration 跳过 encrypted/vendor closure；日志截断或非零退出；存在 unresolved/blackbox；ISA/register-map 没有版本；物理对象、A/B、overflow、requant、qparams、运行协议或 BARR 仍含歧义；只给截图/摘要；证据 hash 缺失或不匹配。

`rtl28_candidate_audit.*`、本请求包、软件 layout、功能模型结果和测试 fixture 始终只是 candidate/evidence。即使 `hardware_approval.json` 结构有效，也仍需 current architecture 的布局 gate eligibility、RTL28 七算子布局、93-edge/91-qparam/16-Add 整网审计与成本/逻辑回归共同通过，才能令 G4 通过并授权 W5；在此之前不得生成正式 W5 JSON/bitstream，也不得宣称 G1/G4 或硬件性能通过。
