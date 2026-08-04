# 归档：生成前必读资料精简前的算子配置规则

原标题：`NDP 原生算子配置、数据与复现规则`。本文件保留 2026-07-24 精简前的全部
字段真值表、阶段历史和重建命令，只用于审计；当前规则见原路径的新文件。

最后更新：2026-07-23（R4 严格规则切换）

本规则服务当前原版控制链和用户明确授权的最小 bridge。默认是**复现模式**：静态算子配置必须已经存在；graph/tensor 若活动仓库没有专用入口，可由可审计 bridge 描述或生成，但地址、bitstream、execplan 和 SCA 必须由活动原版 `ndp-sim` 产生。只有用户另行明确批准配置开发时才进入**开发模式**，并额外要求模型语义、dtype/qparam、layout、tail、stage DAG、地址生命周期和 provenance 合同。旧 server profile、freeze/v20 包、barrier 和三方比较规则不得执行。

原生工具退出码 0、生成了 bitstream 或服务器能够自然结束，都不单独证明配置正确。所有新配置身份必须经过本规则第 7 节的外围 fail-closed 验收；未满足的只能按实际证据等级声明。

## 1. 活动来源

唯一活动配置/生成仓库：

`C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim`

当前提交：

`ec12424516ae0304228dd2321d4e604fe225e04e`

暂停使用：

`C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim-ref`

服务器已运行参考目录：

`C:\Users\15383\Desktop\Codex\project\resnet50_int8\jsons`

参考目录只用于确认文件类别和服务器成功先例，不是 JSON、数据或配置来源，也不是最新版工具输出的逐字节基准。

## 2. JSON 层级不得混淆

原生流程中至少区分：

1. `ndp-sim/model_execplan/op_json/*.json`：模型/复合算子图，声明参数、operator 顺序、输入来源、输出 shape 和 slice mask；
2. `ndp-sim/jsons/*.json`：已经写好的硬件原子算子静态配置，包含 loop、stream、buffer、SA/GA/SFU 等字段；
3. `*_withbaseaddr.json` 或原生输出中的 patched JSON：`model_execplan` 按 tensor 地址和实例参数生成的消费配置；
4. `sca_cfg*.json`、`install/cfg_pkg`、`install/execplan.txt`、可选 `Bank_data`：原生 planner/writer 生成的服务器消费内容；
5. tensor/golden/relayout 文件：由原生数据与 layout 工具产生，不由 `model_execplan` 凭空生成。

不得把第 3～5 层文件当作第 1～2 层输入，也不得把参考目录中的最终文件倒灌为源 JSON。

## 3. 只使用已经存在的算子配置

- 首个参考阶段优先选择活动 `ndp-sim` 中已经写好 `op_json` 和全部被引用 `jsons/*.json` 的算子；后续用户授权的本地算子允许把工作库已有静态配置逐字节复制为活动 `type` 别名，但不得在本轮生成或修改配置语义。
- 不允许根仓工具即时发明静态算子 JSON，不允许从参考输出逆向生成源 JSON。
- 不允许手填缺失字段、地址、shape、slice、loop、stream、buffer、PE、dtype 或长度。
- 原生 `model_execplan` 根据 `op_json` 参数 patch 静态 JSON 属于允许的原生步骤；任何仓外 patch 都不允许。
- 目标算子引用的每一种 `type` 都必须在活动 `ndp-sim/jsons/` 中找到唯一、可追溯的文件；若为本地既有配置别名，manifest 必须记录原路径、原哈希和别名同哈希证明。
- 文件同名不等于语义相同；必须以当前 `op_json` 的 `type`、参数表达式和原生 loader 行为为准。

## 4. 当前单原子算子链

当前服务器冒烟图由原生生成器产生：

`ndp-sim/generate_python_golden/model_execplan/op_json/decode_summac_fp32N_fp32N_graph.json`

它只引用一个已经存在的原生原子算子类型：

| operator type | 活动静态 JSON |
|---|---|
| `decode_summac_fp32N_fp32N` | `ndp-sim/jsons/decode_summac_fp32N_fp32N.json` |

对应原生数据和 relayout 入口：

`ndp-sim/generate_python_golden/decode_ops.py`

`ndp-sim/generate_python_golden/run_single_op_decode.py --target-op decode_summac_fp32N_fp32N`

该链已生成 28-slice op0 数据、单图、bitstream、execplan 和自包含服务器目录并通过本地结构/哈希检查；用户已确认服务器完整跑通，但未做数值正确性证明。

## 5. 数据与 golden 来源

- tensor、权重、golden 或初始化数据必须由活动 `ndp-sim` 的原生脚本产生，或来自用户明确允许且独立于禁用参考仓/旧服务器包的正式输入；W3 与形式模型属于允许来源。
- 每份数据都记录来源脚本、命令、shape、dtype、layout、字节数和 SHA-256。
- 原生 relayout/packing 脚本只按其 README/源码约定使用，不能因参考文件大小不同而手改参数或补零。
- 参考目录中的输入、Bank、SCA 或空占位文件也属于禁止提取内容，不能因为其“不是结果”而复制。
- 若当前目标仅为服务器冒烟运行，允许使用活动 `ndp-sim` 明确提供、固定 seed 且可复现的合成输入/权重回退路径；不得另写随机生成器、使用空文件或用参考目录数据填充。需要数值验证时仍必须切回正式数据源。

## 6. 原生参数、地址与 bitstream

- 参数表达式由 `op_json` 和原生 parser 求值，不在外部复制一套解释器。
- 地址由原生 planner/remapping 生成；是否执行 address remapping 只依据当前 README 和目标算子源码路径。
- bitstream 只由活动 `ndp-sim` 的原生 placement/encoder 产生。
- 任何 placement 约束失败、bitstream 缺失、原生异常被吞掉或同输入重跑结果变化，都必须判失败。
- 不得用历史 `ndp-sim-ref` bitstream、根仓 freeze、旧 parsed evidence 或参考目录 bitstream 替换原生输出。
- 不得为服务器额外插入 completion barrier、改 opcode、拆 4 KiB、改地址或重排指令，除非这些就是当前原生 README/源码的默认步骤。

## 7. 配置验收

生成目录自洽检查至少包括：

- `op_json` 中每个 operator 都解析成功；
- 每个静态 JSON 来源唯一且哈希已记录；
- patched JSON 与原生 planner 的地址/shape 记录一致；
- 每个原生 bitstream 与其配置实例一一对应；
- `sca_cfg*.json`、`cfg_pkg`、`execplan.txt` 和可选 `Bank_data` 的引用路径均存在；
- 日志没有 placement、mapping、encoder、writer 或数据生成错误；
- 从全新目录重复执行时输出确定。

通过自洽检查后，可以只读比较参考目录以辅助理解服务器消费类别，但不得把差异当作失败条件。验收以 `.agents/rules/服务器测试包生成规则.md` 的最新版当前格式合同为准：manifest/SCA 引用全部存在、bitstream 真实生成成功、正式数据来源可追溯。

### 7.1 JSON 与 CONFIG

- 配置必须通过 `resnet50_pipeline/operator_config_validator.py` 的严格 schema；未知字段、缺字段、错误数组长度、非法 enum、错误 null、地址解析 fallback、位宽截断和非正向 loop 一律失败。
- `CONFIG` 必须按 IGA/LSU/SA/GA 的 enable 与 update 位解释为跨 stage 持久状态。首 stage reuse、disable 同时 update、reuse 时 body 漂移、disable 后无状态 reuse 均失败。
- 复现模式允许已经裁决的 legacy SA 名称：`col` 编码 bit0、物理不转置；`row` 编码 bit1、物理转置。开发模式必须由 layout contract 明确 `expected_sa_transpose`，不得按名称猜。
- D 的递归 terminal tag 链必须到达唯一 `last_index=0`；启用输入、ping-pong 半区、stream、buffer 和 array 端口必须存在可达的 producer/consumer。

### 7.2 mapping、bitstream 与 execplan

- placement 必须 exact penalty=0、`fallback_used=false`，并保存初始 cache 状态、同次生成/加载来源、seed、命令、活动 commit/source tree、stdout/stderr 和 cache 哈希。仅凭“Loaded cached mapping”或历史产物不能补齐 provenance。
- source JSON、`mapping_review.json`、`parsed_bitstream.txt`、64-bit/128-bit dump 必须由独立镜像逐字段、逐 bit 一致；原生 silent default 或 wrap 即使能生成文件也判失败。
- 每个 graph operator 必须唯一绑定原生 planner 生成的 patched JSON、mapping evidence、cfg_pkg 和 Load_Config。128-bit execplan 必须独立解析，机器位与 `instructions_explained.txt` 的序号、opcode、slice、register、value 和 operator 全部一致；重复 explanation 序号也失败。
- 必须按真实 Load_Config→Write_Reg→Start_Comp 顺序驱动 CONFIG 状态。不能只检查单份 JSON，也不能用 explanation 文本替代机器位。
- 相同输入至少在两个隔离的原生工具副本中重跑；除明确登记的非确定性可视化文件外，所有 planner 输出逐文件哈希一致后才可发布 evidence bundle。
- mapping 必须针对 planner 写入最终 A/B/C/D base 后的配置重新执行。地址绑定前的零 penalty 结果只能作为预检查，不能与地址绑定后的 execplan 拼接；evidence 生成器必须把已验证 mapping bundle 的 `source_config.json` 按 op type 安装到每个隔离 planner 副本。
- 默认 mapping cache 为空。唯一允许的历史 cache 例外是：文件来自 `repos.lock.json` 固定提交、文件名是原生 16-hex key、只复制进隔离工具副本、原生 mapper 明确报告已加载，且对当前连接图重新计算 exact penalty=0、无 fallback。只复制 cache 或只看到 load 日志均不构成证据。

### 7.3 地址、padding/tailing 与 SCA

活动 RTL 的请求地址按下式验收：

```text
byte_offset = sum(idx[i] * dim_stride[i])
事务按 16-byte 边界拆分
word_offset = (byte_offset + transfer_bias) >> 4
mapped = permute26(word_offset, address_remapping)
request_word_addr = (mapped + (base_addr >> 4)) mod 2^26
```

- `address_remapping[out_bit]` 选择输入 bit；base 在 remap 后相加。`idx_size` 参与 transaction-size 编码，不是索引范围；索引由硬件 loop 与 LC-PE 表达式产生。
- 原生 bitstream 中的 base 只是初始配置；每 slice 的真实 base 还必须回放 execplan Write_Reg。不得据 slice0 JSON 推断全部 slice。
- padding/tailing 不抑制 Memory_AG 请求，因此被替换或 merge 的数据请求也要计入地址枚举。read 数据优先级为 padding value > tailing zero > DDR；write tailing 为 old-DDR merge。
- 所有请求和 SCA region 都必须满足 16-byte 对齐、slice/bank/column 合法及 `row < 6144`；30-bit transaction wrap、26-bit base-add wrap、请求落不到声明 tensor region、未声明 overlap/alias 或生命周期冲突均失败。
- 大规模请求报告可以不保存每个地址行，但验证器仍必须完整枚举所有请求，并按 stream 保存 multiplicity、唯一地址数、有序地址哈希和首尾边界样本；省略 rows 只能缩小报告，不能抽样验证。

### 7.4 模型语义与证据等级

- 开发模式的每个 operator 必须哈希绑定 op type、输入/输出 dtype 与 layout、qparam 或明确 `not-applicable`、padding 值、尾块有效 lane、stage role/dependencies 和 source/mapping provenance。
- qparam 既可为标量，也可为哈希绑定的 per-channel tensor descriptor。后者必须携带 `value_kind`、dtype、shape、element_count、axis、min/max 和 `value_sha256`；缺 axis、元素数或值身份时失败，禁止退化为首元素标量。
- B′ 独立消费的算子必须有独立 SCA/producer；不能把 B 别名成 B′。qparam 缺失、tail block 越界、stage DAG 与 graph 不一致均失败。
- E0 只表示静态可解析/可编码；E1 表示本地结构、来源、地址及确定性闭合；E2 表示独立软件公式；E3 表示服务器自然完成；E4 表示服务器回读与独立 golden 一致；E5 表示边界和跨 stage 可推广。不同等级不得相互替代。
- 当前 Decode 两 stage evidence 只证明本地连续 `update`；真实 CONFIG `reuse/disable`、非对称 SA、padding/tailing、6144-row 边界及数值回读仍需服务器 E4/E5。

### 7.5 当前验收入口

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\validate_operator_configs.py ndp-sim\jsons --output <shadow-report.json>
& $py tools\validate_operator_config_artifacts.py <source.json> <artifact-dir> --mapping-evidence <mapping_evidence.json>
& $py tools\validate_operator_config_execplan.py <graph-output-dir> <graph-withbaseaddr.json> --source-config <op-id=source.json> --mapping-evidence <op-id=mapping_evidence.json> --artifact-dir <op-id=artifact-dir>
& $py tools\validate_operator_config_package.py <graph-output-dir> <graph-withbaseaddr.json> --semantic-contract <contract.json> --no-require-matrix-files
& $py tools\validate_operator_config_request_addresses.py <graph-output-dir> <graph-withbaseaddr.json> --source-config <op-id=source.json>
```

最终可移植证据优先由 `tools/generate_operator_config_mapping_evidence.py` 和 `tools/generate_operator_config_execplan_evidence.py` 生成；生成器任一验证层失败时不得发布目标目录。

## 8. 当前不启用的旧规则

当前阶段明确不启用：

- 未经用户明确批准，用根仓 `tools/generate_*` 或任何脚本生成/修改新的算子配置；已批准的外围验证报告和 evidence bundle 不属于配置语义修改；
- `ndp-sim-ref` 的 parser、placement、encoder 或 server profile；
- 用历史 typed request、freeze manifest、旧 28-slice execplan/address plan 直接构造控制内容；允许用户授权的数据 bridge 调用当前 tensor 描述和纯数据 layout，但原版 planner 必须重新规划服务器地址；
- config-bound NDPFuncModel preflight；
- hardware freeze、package、overlay、runner、ZIP 和 sidecar；
- 自定义 barrier、readback 合同和三方 P/D/A/D 比较；
- 历史 revision 的 G0～G8 门状态作为当前生成许可。

这些内容仍可在归档和历史中追溯，但只能在后续计划明确恢复时使用。

## 9. 后续 ResNet50 与 Conv

已测参考算子完成本地严格复现并由用户服务器测试通过后，才评估最简单 ResNet50 算子。

`node-0002` MaxPool 是优先候选，但必须重新确认：

- 活动 `ndp-sim` 中已有对应静态 JSON，而非根仓工具新生成；
- 有完整原生 `op_json` 或原生入口；
- 数据、relayout、地址、bitstream 和服务器消费目录均可由原生步骤生成；
- 不复用 `output/maxpool_node0002` 或任何参考目录占位文件。

用户已明确批准 `node-0004 accumulate-wave-0` 单阶段例外：根目录既有 `conv_1x1_real.json` 逐字节别名到活动 `ndp-sim/jsons`，正式 W3 数据经当前 signed-A Conv28 layout 生成单样本槽，graph 由最小 bridge 产生，控制内容由原版工具重建。该例外不授权其他 Conv、完整三波次、requant 或三方比较；缺口仍须向用户确认。

## 10. 停止条件

出现以下任一情况停止：

- 对应算子的静态 JSON 不存在；`op_json` 缺失时只有在用户授权且最小 graph bridge 能完整描述输入/输出时才可继续；
- 数据来源、原生命令、依赖版本或 remapping 条件无法从活动仓库复现；
- 需要从参考目录、`ndp-sim-ref` 或根仓旧产物提取内容；
- 需要修改原生源码或手工修正原生输出；
- 重复生成不确定；
- 当前 manifest/SCA 引用缺失、bitstream 未真实生成成功或当前格式目录不自洽。
- 严格 JSON、mapping、bitstream、execplan、SCA、逐请求地址或语义/provenance 任一验证层失败；
- 试图用 E0/E1、服务器自然完成或本地 mismatch=0 代替尚未取得的 E4/E5。

停止时只报告可复现证据、第一处差异和明确缺口；不能继续补文件或通过服务器试跑猜测配置。

## 11. R5 补丁来源授权修订

自 2026-07-23 起，用户已批准采用“哈希绑定的项目补丁版本”。第 8 节关于“未经批准不得由根仓脚本生成新配置”和第 10 节“需要修改原生源码时停止”继续约束未登记修改，但不再阻止以下已批准流程：

- 保持活动 `ndp-sim@ec12424516ae0304228dd2321d4e604fe225e04e` 只读；
- 按 `contracts/ndp_patch_toolchain_v1.json` 在隔离副本中应用逐源哈希锁定的四项修复；
- 用该补丁身份生成并严格验证新的 mapping/bitstream/execplan evidence；
- 从 W3/typed contract/已批准 layout 机械生成新的 lowering request、候选配置和验证报告。

任何补丁清单外源码差异、base commit 不同、源 SHA-256 不同、未绑定补丁身份或直接修改活动 checkout 仍必须停止。批准补丁只解决工具实现来源，不自动批准算子语义：每个 ResNet50 stage 仍需 E0～E5 逐级证据，尤其不得用 patched Decode 的通过结果替代 Conv、pool、add、quant/dequant、GAP 或 matmul 的 RTL 数值证明。

### 11.1 Typed lowering 与服务器交接

- 133-stage typed lowering 的机器入口固定为 `contracts/resnet50_r5_lowering_bundle.json`。消费方必须先校验 bundle 输入哈希、request-set SHA-256 和每项 request SHA-256；不得丢弃参数 dtype/shape/axis/value hash、前驱 DAG、target profile 或 patchset identity。
- `formal_target_instance_allowed=false` 或存在 unresolved blocker 时，不得输出正式 target config；已有候选文件不能满足 request。
- 服务器执行协议必须符合 `resnet50-server-execution-protocol-v1`，并按 load、start、wait、readback 顺序给出用户批准的 argv、cwd、timeout、RTL commit/filelist hash 和必返路径。模板状态、占位符或缺失字段不得执行。
- 统一 runner 只允许 `shell=False` 原样执行协议 argv，且 run1/run2 必须使用新输出目录。命令成功只形成原始回执；仍需独立 golden 比较才能成为 E4，两次环境与结果一致并覆盖边界后才能成为 E5。

### 11.2 受限 legacy 规范化与语义合同

- 原 legacy JSON 永不改写。严格副本只能由 `tools/materialize_strict_operator_config.py` 生成，并同时绑定源 SHA、变更集合、原生逐字段编码等价和裁决结果。
- write stream 的 read-only 字段删除、typed-null index mode 修正可以在原生字段等价后批准；启用 padding 的 `null→0` 还必须显式传入哈希绑定的 operator padding contract。
- 当前 padding 授权按算子合同分别调度：`contracts/maxpool_uint8_zero_padding_contract.json`
  只授权精确 16×16 MaxPool；`contracts/operator_config/gap_sum_zero_padding_contract_v1.json`
  只授权 `hwop-0071-00` 精确 GAP-sum 的零填充。二者都绑定单一源 SHA 和 JSON path，
  不得跨算子、dtype、shape、padding byte 推广，也不代表正式服务器结论。
- 当前 9 份 legacy 规范化配置均已取得 zero-penalty mapping；该事实只闭合 R3/R5 本地映射残留，不改变原始 JSON 的 intentional-reject 身份，也不替代 ResNet50 133-stage 正式配置。

## 12. 配置语料与 stage→JSON 开发后端

自 ADR-019 起，开发模式新增以下机器入口：

- `contracts/operator_config/ndpsim_json_corpus_v1.json`：55 份活动模板的结构、字段、模块特征、graph 引用及服务器专用实例；
- `contracts/operator_config/operator_config_authority_v1.json`：按 ADR-021 和固定上游 Git 身份分类 67 份库存；65 份授权正确参考，2 份后加 `node0004*` 未授权候选；
- `contracts/operator_config/ndpsim_json_hardware_evidence_v1.json`：逐模板硬件证据等级，明确区分继承基线、服务器包存在、原始回执、自然完成和数值回读；
- `contracts/operator_config/register_semantics_v1.json`：Excel/CSV 字段语义、当前 encoder `FIELD_MAP` 与冲突账本；
- `contracts/operator_config/config_rule_evidence_v1.json`：同族 shape 及模板→实例逐字段差分；
- `contracts/operator_config/deepseek_stage_ir_crosswalk_v1.json`：DeepSeek graph stage
  到授权静态模板的精确交叉索引；
- `contracts/operator_config/deepseek_reduction_rules_v1.json`：local/remote reduction、
  terminal 和精确 GAP schedule；
- `contracts/operator_config/deepseek_primitive_rules_v1.json`：GA add/mul/mac、SA
  GEMM/GEMV 及 local/ring N2N 结构证据；
- `contracts/operator_config/stage_backend_catalog_v1.json`：每种 typed hardware stage 的 emitter 状态、模板证据和 blocker。
- `contracts/operator_config/stage_operator_semantics_audit_v1.json`：JSON→register/
  RTL 方程、动态反证和稳定 issue ID 的机器总账；
- `contracts/resnet50_r5_lowering_bundle.json` 与
  `contracts/operator_config/stage_config_system_v1.json`：逐 request 的
  emitter/RTL/dynamic 三轴状态及其 blocker。
- `contracts/operator_config/stage_json_derivation_matrix_v1.json`：GAP、MaxPool、
  Requant、View 四个代表的逐 JSON leaf 值来源、owner、方程、合法域与 RTL consumer；
- `contracts/operator_config/gap_d_index_schedule_v1.json`：新 GAP D-index
  `0..255` 数值 root、256/256 事务、tag/terminal 和零代价 mapping 证明；
- `contracts/operator_config/ga_int32_input_domain_matrix_v1.json`：全部 54 个
  Requant 与 1 个 AverageRequant 的正式 W3 int32 输入域反例命中矩阵；
- `contracts/operator_config/stage_state_lifetime_contract_v1.json`：133-stage
  顺序、148 条 typed edge、View 逻辑 alias、20 个 Conv signature 和 N2N 非选择；
- `contracts/operator_config/operator_semantics_local_closure_v1.json`：0.3
  当前只读本地范围的单一哈希闭环与服务器交接门。

强制规则：

1. 依据 ADR-021，根仓 `jsons` 的 12 份用户参考配置，以及与固定上游提交逐文件一致的 53 份 `ndp-sim/jsons` 配置，是正确、高强度参考基线，可直接用于规则提炼。两份后加 `node0004*` 不在授权内，不得根据目录位置自动升级；原始日志/readback 仍单独决定具体运行的 E3/E4/E5，新 shape、地址、常量和拓扑也不自动获批。
2. Excel 只作为配置名、端口和备注语义来源；declared width、`[hi:lo]` 与当前 encoder/RTL 冲突时必须保留冲突并停止，不能选择一个方便值。
3. shape 差分中的地址字段允许在 `model_execplan` 阶段后绑定；LC、stream、buffer、terminal、padding/tailing 或拓扑字段必须由显式 ScheduleIR 规则产生。
4. Stage backend 必须先校验 lowering request SHA、patchset、effective resolution 和 typed 参数；未知算子族或 unresolved blocker 一律失败。
5. 当前 `MaxPoolUint8` 和 GAP 的结构 emitter 分别只识别 `hwop-0002-00` 与
   `hwop-0071-00` 的精确签名，`View` 只产生零拷贝 alias；但结构 emitter
   存在不等于 candidate emission 许可。MaxPool 被
   `B_GA_INT8_MAX_NUMERIC/B_GA_INT8_MAX_FLOW` 阻塞。旧 GAP 模板被
   `B_GAP_D_INDEX_CARRIER_SEMANTICS/B_GAP_GA_ACCUM_STATE` 阻塞；新的
   `hwop-0071-00-d-index-v1` 派生配置已独立解除前者，但仍被
   `B_GAP_GA_ACCUM_STATE` 阻塞。两类算子当前均不得 materialize 为新 candidate。
6. 生成物必须标为 address-unbound candidate，并继续经过地址绑定、mapping、bitstream、execplan、SCA、逐请求地址、独立 golden 和服务器 E4/E5。存在 `config.json` 不得改写为正式 target config。
7. 每个 stage 必须分别记录 `json_emitter_ready`、`rtl_semantics_compatible` 和
   `dynamic_release_ready`。candidate JSON 要求前两轴同时为真；正式 release 还要求
   第三轴为真。历史包完整性、授权模板正确性或 resolution overlay 本地放行不得替代
   任一轴。

重建入口：

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\build_operator_config_corpus.py
& $py tools\build_deepseek_stage_ir.py
& $py tools\build_deepseek_reduction_rules.py
& $py tools\build_deepseek_primitive_rules.py
& $py tools\build_register_semantics_contract.py --workbook <register-map.xlsx>
& $py tools\build_operator_config_rule_evidence.py
& $py tools\build_stage_config_backend_catalog.py
& $py tools\generate_stage_operator_config.py `
  r5:hwop-0002-00 configs\stage_codegen\hwop-0002-00-v1
```

### 12.1 Conv / requant 的当前证据边界

- `contracts/operator_config/node0004_conv_schedule_evidence_v1.json` 只把
  node-0004 wave-0 的 28/64 tile、A/B/C/D 端口、SA 布局、mapping、execplan 和
  逐请求地址登记为静态诊断事实。该配置是固定上游提交之外的项目新增文件，未通过测试，
  不得声明其语义正确，也不能把单 wave 推广为完整 Conv emitter。
- `contracts/operator_config/node0004_requant_semantics_evidence_v1.json` 证明活动
  quant 模板是授权正确配置，并闭合 node-0004 的 per-channel multiplier、
  8-lane GA 放置及 W3 本地数值重放；派生的 node-0004 requant 实例仍需物化、
  严格链验证和目标硬件 E4/E5。
- 旧 `conv_1x1_requant_real` 及其生成器保留为历史追溯对象。其 manifest/generator
  仍引用当前禁用的 `ndp-sim-ref`，不得作为新的 stage backend 输入或当前生成许可。
  当前 requant 证据只允许读取活动 `ndp-sim` 中哈希相同的量化模板。
- node-0004 nopp-r1 现有服务器尝试因缺预载文件和 bitstream 而无效。完整候选目录
  `artifacts/operator_config_validation/r5-server-candidates/node0004-nopp-r1-v2`
  的本地文件齐全不等于已在服务器运行；必须保存与该候选树哈希绑定的新回执。
- ADR-021 只为上游原生 quant 模板的 `B_REQUANT_TARGET_NUMERICS` 提供正确性证据。
  `node0004*` 不受授权，不能据此消解 `B_CONV_BIAS_PSUM` 或 `B_CONV_INT8_SA`。
  Conv 必须从上游原生已测模板、RTL 和 register map 独立提炼规则并反向审查 node0004；
  完整三波覆盖、requant 派生实例及其他新变化仍须保留独立 blocker。

新增重建入口：

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\build_conv_stage_schedule_evidence.py
& $py tools\build_requant_stage_semantics_evidence.py
& $py tools\build_stage_config_backend_catalog.py
```

### 12.2 完整 stage→JSON 系统

`contracts/operator_config/stage_config_system_v1.json` 是全部 133 stage 的统一规则和
状态入口。消费方必须同时验证 lowering bundle、backend catalog 和 configuration
authority 的哈希，且必须满足：

1. 133 个 request 各有且仅有一个 stage plan，family 计数与 typed lowering 一致；
2. 每个 shape 变体保存完整 logical geometry、request 集及 typed parameter schema hash；
3. `CONFIG`、LC/PE、stream、buffer、SA、GA、n2n 各有唯一语义所有者；
4. 参考模板必须按 ADR-021 做 Git 来源裁决；项目后加 `node0004*` 不能闭合参考正确性；
5. exact authorized template 只能闭合其精确参考语义；strict materialization、
   candidate emission、地址/mapping/execplan、formal release、E4/E5 分别判定；
6. 未闭合字段必须转成具体 blocker 和 next action，不能用通用“待验证”隐藏；
7. address-unbound candidate 只能在本地配置 blocker与 RTL semantic blocker
   同时清零后生成，地址永远由后续 remapping/execplan 阶段绑定。

当前 GAP-sum 的精确例外由
`contracts/operator_config/gap_sum_zero_padding_contract_v1.json` 与
`configs/native_ndp_sim/avgpool_config_2048_7_7_strict_v1` 及
`deepseek_reduction_rules_v1.json` 共同证明：`x_zero_point=0`、49 元素、8-lane
`int32_sum`、padding identity=0、每 slice 完整 sample 和 terminal `last_index=0`。
它只对 `hwop-0071-00` 解除 typed transport、centered sum、跨 slice 与 completion
的历史本地 blocker；不能解除 D-index 与 GA 累加状态反证，也不能据此生成当前
candidate。地址/mapping/execplan/SCA 和 E4/E5 继续阻塞。

系统的四条实现分支及优先级是：

1. 已实现的 control/alias（MaxPool、View）；
2. GA reduction（GAP）；
3. GA affine/requant（Requant、Add、Quant、Dequant、AverageRequant）；
4. SA INT8 accumulation（Conv、MatMul）。

新增重建入口：

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\build_gap_sum_padding_contract.py
& $py tools\build_r5_resolution_overlay.py
& $py tools\build_r5_lowering_bundle.py
& $py tools\build_stage_config_backend_catalog.py
& $py tools\build_stage_config_system.py
```

### 12.3 DeepSeek 模板的迁移等级

活动 `ndp-sim/model_execplan` 是已支持算子的唯一 graph→实例配置→execplan 实现。
必须直接复用：

- `json_loader.py`：graph、shape 表达式、source、dtype、remapping、used-slice 解析；
- `control_registers.py`：按原生 op type 的 shape-driven control-register handler；
- `output_writer.py`：把控制更新和 base address patch 回静态 JSON；
- `pipeline.py`：地址规划、bitstream 再生成、Load_Config/Write_Reg/Start_Comp、
  execplan、manifest 与 SCA。

原生 registry 当前有 48 个 handler，并覆盖全部 40 种 graph-referenced DeepSeek
stage type。本项目的 crosswalk/reduction/primitive 合同只允许做哈希索引、provenance、
审计和 ResNet 放行判断；禁止再实现平行 graph parser、控制字段 patcher、地址规划器、
bitstream 或 execplan generator。

DeepSeek 配置只能按以下三级使用：

1. **精确复放**：stage type、graph 参数、shape/dtype/source、used-slice mask 和模板 SHA
   全部一致时，允许把固定上游模板作为正确参考；地址实例与服务器结果仍分别判定。
2. **结构迁移**：允许提炼 GA opcode/lane/broadcast/terminal、SA local-versus-ring
   选择、N2N 与 `nbr_enable` 联动、跨 stage dependency；所有新 loop、shape、dtype、
   常量和地址仍须重新生成和验证。
3. **禁止外推**：不得把 FP16/FP32 GEMM/GEMV 的 SA 配置直接当作 INT8 Conv，
   不得把 neighbor transport 自动解释为已证明的 psum 数值语义，也不得据此猜
   zero-point、multiplier、rounding、saturation、bias 或 tail tile。

local/ring 不是单字段开关。已绑定的 GEMV 与 GEMM 对显示 ring 同时改变 K 分块、
LC/stream schedule、SA neighbor port 和 `n2n`；只在 local JSON 上增加 `n2n` 必须失败。

授权正确不等于 strict target schema 兼容。当前一份 vector-add 在 write stream 保留
read-only 字段，三份 prefill GEMM 使用 `mem_idx_mode[2]=0` legacy sentinel。精确模板
仍可作为规则证据，但派生 target 不得静默删除或改写；必须通过原生 encoder/RTL
逐字段等价合同后，由 strict materialization 生成新副本，且原 JSON 永不修改。

native 没有提供的部分仍由本项目负责：ONNX→ResNet typed stage lowering、把 ResNet
stage 精确选择为某个 native op type、qparam/数值合同、strict schema、来源哈希、
candidate/formal/E4/E5 放行。若 native registry 缺目标 op type，只能在哈希锁定的隔离
`ndp-sim` 补丁副本中新增 handler 并复用原生 pipeline，不得在根项目复制其功能。

### 12.4 LC trigger/tag 语义、GAP D 索引门与 MSE0 动态边界

机器入口为
`contracts/operator_config/stage_operator_semantics_audit_v1.json`。该合同绑定 typed
GAP request、encoder、物理 mapping、LC/MSE/Datahub RTL、sim6 数值报告和 probe_v1
身份，并只使用 `RTL_PROVEN`、`SAMPLE_SUPPORTED`、`TEST_REQUIRED`、
`CONTRADICTED` 四级结论。checked contract 与当前源码/证据不能重建为完全相同对象时
必须失败。

DRAM LC 的固定规则如下：

1. `dram_loop_configs.LC*.src_id` 是逻辑连接。mapper 将它转换为目标 LC 的 4-bit
   相对输入端口选择码；它选择上游的 trigger/tag/backpressure 路径，不传递上游
   numeric data。
2. 目标 RTL 的 LC 配置实际为 60 bit：`src_id[59:56]`、
   `outmost_loop[55]`、`start[54:38]`、`stride[37:21]`、`end[20:4]`、
   `last_index[3:0]`。register spreadsheet 中把三个 17-bit 值画成 13-bit range
   的 `[47:0]` 偏移与 encoder/RTL 冲突，不能作为 target packing 依据。
3. `outmost_loop=1` 时 LC 由 `slice_start_run` 触发，`src_id` 不参与触发；非 outmost
   LC 从所选源取得 `valid/last/same/last_index`。`start/end/stride` 始终定义本 LC
   的本地计数域，不因 `src_id` 改变。
4. RTL 以 signed 17-bit 做 `previous+stride` 及 `next >= end-stride`；对外 LC data
   截断为 16 bit。当前批准的生成子集仍要求正 stride、`start<end`，不得因 encoder
   能打包二补码就外推负 stride。
5. 本地 `last_index` 在上游未宣告 last 时输出；上游 last 时继承上游
   `last_index`。上游 `same` 用于抑制同一触发重复摄取，输出 `same` 由本 LC 在下游
   停顿时重新产生。因此 terminal validator 可以沿 trigger/tag 图追踪 last-index，
   但不能沿该图推断数值相等。

LC_PE 的固定规则如下：

1. 每个 LC_PE 配置是 96 bit、两个 48-bit configure beat。第一拍包含 16-bit
   reserved padding 和 32-bit `opcode/src_id/keep_last_index/mode` 控制；第二拍是
   `constant2/1/0` 三个 16-bit lane。register spreadsheet 的 constant 行虽声明
   16 bit，却只画出 12-bit range，不能作为 packing 依据。
2. `src_id` 是 4-bit 物理输入选择：LC 邻居编码为 0～5，LC_PE 邻居编码为
   6～9；mapping 中不可达的逻辑边必须失败，禁止让 encoder 的 fallback 0 静默
   选择另一个源。
3. mode 为 `null=00`、`buffer=01`、`keep=10`、`constant=11`。所有 enabled
   port 均 valid 才产生一次 matched 运算。严格 target 必须恰有一个 `buffer`
   作为 terminal-tag carrier；输出 `last/last_index` 只来自该 buffer port。
4. keep port 在 `buffer_last && buffer_last_index <= keep_last_index` 时释放并接入
   新值，比较是 inclusive；keep port 自身的 last/tag 不成为输出 terminal tag。
   `keep_last_index` 出现在非 keep 端口、constant 端口携带 `src_id` 均必须失败。
5. `add` 实际为 `low16(s16(p0)*1+s16(p1))`，`mul` 为
   `low16(s16(p0)*s16(p1))`，`mac` 为
   `low16(s16(p0)*s16(p1)+s16(p2))`。DW02 multiplier 使用 `TC=1`，只把
   32-bit 乘积低 16 bit 送入 16-bit CLA，carry 丢弃。
6. add/mul 必须启用 port0/1 并将 port2 置 null；mac 必须启用全部三端。置空被
   使用端会留下未定义 operand；启用被 opcode 忽略的端仍会参与 matched/
   backpressure，不能当作无影响字段。
7. LC_PE constant 的批准域是 signed int16 十进制，或精确
   `0x0000..0xffff` 原始 bit pattern。浮点/分数字面量会被通用 encoder 取 FP32
   编码低 16 bit，不是 LC_PE 浮点运算，严格 validator 必须拒绝。
8. 65 份授权正确配置中共有 193 个 LC_PE：151 个
   `mul(buffer,constant,null)`，42 个 `mac(keep,constant,buffer)`，没有 add
   实例。这证明两种已见组合可用；add 只有 RTL 方程证据，不得据此自动批准新
   stage 迁移。

MSE Memory/Buffer AG 的固定规则如下：

1. read stream 配置为 580 bit（10×58），write stream 为 496 bit（8×62，最高
   3 bit reserved）。向量字段按 JSON 列表从高位到低位打包，因此
   `mem_idx_* / idx / idx_size / dim_stride` 的 JSON
   `[dim0,dim1,dim2]` 分别落到 RTL `[port2,port1,port0]`；dim0 是事务内最内层
   维。`buf_idx_*` 的 JSON `[row,col]` 分别落到 RTL `[port1,port0]`。
2. memory index mode 为 `null=00`、`buffer=01`、`keep=10`、
   `constant=11`。null 输出 0 且作为 always-valid；buffer 每次消费；keep 按
   `buffer_last && buffer_last_index <= keep_last_index`（含等号）释放；
   constant 把 8-bit 原始 pattern 符号扩展到 16 bit。后续地址乘法端口未声明
   signed，因此扩展后的 16-bit pattern 按 `u16` 乘 `u20 stride`，不能把
   `0xff` 直接解释成地址 `-1`。
3. memory index 三端必须恰有一个 buffer terminal carrier；buffer/keep 必须有
   source，null/constant 不得依赖 source，constant 必须有显式 8-bit pattern。
   Buffer AG 只有 `buffer=0` 与 `keep=1`，row/col 两端都要求 valid，必须恰有
   一个 buffer 和一个 keep；null/constant 会被原生 mapper 静默编码成 buffer，
   strict target 必须拒绝。
4. Memory AG 的 buffer tag owner 按 RTL port0→1→2 优先，Buffer AG 按
   col(port0)→row(port1) 优先；strict target 的“恰一个 buffer”消除优先歧义。
   keep threshold 在非 keep mode 下是 RTL don't-care。授权语料确有非空
   don't-care threshold，不得把参考配置追溯改判为错误。
5. 地址方程为
   `B=low30(Σ u16(idx[i])×u20(dim_stride[i]))`，
   `T=low30(B+transfer_bias)`，`U=T[29:4]`，
   `R[o]=U[address_remapping[o]]`，
   `request=low26(R+base_addr[29:4])`。remap 只作用于事务 bias，不作用于
   base；base 低 4 bit 被丢弃，strict target 必须 16-byte 对齐。null remap
   编码为 identity；显式 remap 必须是 0～25 的置换。
6. `idx_size[j]` 编码 `S[j]-1`，null 表示 `S[j]=1`；encoder 派生
   `total_size=S0×S1×S2` 与
   `idx_size_log=[log2(S0),log2(S0×S1),0]`。Data Channel 以 shift+mask
   还原事务内 lane 坐标，因此每个 `S[j]` 必须是 2 的幂，total_size 必须落在
   非零 8-bit 域。
7. 事务按 16-byte DDR line 切分：首片
   `position=B[3:0]`、`try_size=16-position`，后续 `try_size=16`，
   `final_size=min(remaining,try_size)`，
   `valid_mask=low16(((1<<final_size)-1)<<position)`。每片 bias 增加
   `final_size`；小于 16 byte 的片标为 partial。
8. WR 对 full 且无 tail mask 的 line 直接写。partial 或任一 tail lane 越界时，
   `transfer_mask_flag=1`，同一双通道槽先以 `rw=0` 读旧 line，再以 `rw=1`
   写同址；新值只覆盖 `valid_mask & ~tail_mask`，其余 lane 合并旧 DDR 数据。
9. RD/WR 两套 request outbuffer 都每拍执行 `vld_d<=vld`，对外
   `valid=vld_d||vld`，且 `vld_d` 无显式 reset。因此静态地址/RMW 方程已闭合，
   但 first/stall/resume 下 delayed-only valid 是否被再次接受仍须周期 trace；
   不得用 JSON 地址补偿这一独立 RTL 控制风险。
10. 65 份授权配置共有 177 个 stream（112 read、65 write）。全部 Buffer AG
    mode 都是 `[keep,buffer]`（row keep、col buffer）；memory constant mode
    没有样例。四个精确 GEMM 参考使用整数 `0`，原生 mapper 将其编码成 null；
    strict target 继续要求 typed null，只能经逐字段编码等价的 materialization
    转换，不能泛化为接受任意整数 mode。

padding/tailing/valid-mask 的固定规则如下：

1. read padding 编码为 `padding_reg_value:8`、`padding_enable:3`、三组
   `low_bound/up_bound:12`；read/write tailing 编码为 `tailing_enable:3`、三组
   `low/up:12`。向量同样按 JSON dim0→RTL element2、dim1→1、dim2→0 对齐。
   write stream 没有 padding 寄存器位。
2. 对事务内 conceptual lane `l`，`q=transfer_bias+l`，JSON 顺序坐标为
   `idx0=low16(base0+(q&(S0-1)))`、
   `idx1=low16(base1+((q>>log2(S0))&(S1-1)))`、
   `idx2=low16(base2+((q>>log2(S0*S1))&(S2-1)))`。
   enabled 维只有 `idx<low || idx>up` 才越界，所以 low/up 均 inclusive；三维越界
   结果 OR 合并。bound 为 zero-extended 12-bit，strict target 限制在 0～4095。
3. padding/tail 先按 conceptual lane 生成 mask，再
   `physical_mask=low16(conceptual_mask<<transfer_start_position)`；
   line split 产生的 physical valid mask 与此独立。
4. RD byte 的选择优先级固定为
   `padding ? padding_reg_value : tail ? 8'h00 : DDR byte`。随后
   `rank[i]=popcount(valid_mask[0:i])`，有效 physical lane `i` 被压紧到
   `rank[i]-1`；padding/tail 是替换值，不会从输出序列删除，也不会抑制 DDR read。
5. WR 新值 mask 为 `valid_mask & ~tail_mask`；mask 为 0 的 lane 从 RMW read
   返回的旧 DDR line 合并。完全 tail 的 line 仍读旧 line 并原样写回，不做 request
   elision。write 没有 padding 语义。
6. 授权语料只有 3 个启用 padding 的 read stream（5 个 enabled dimension），没有
   任一启用 tailing 的 stream；tail 组合因此只有 RTL 方程证据。三份 padding 参考的
   `padding_reg_value=null` 经 BaseConfig 编为 0，精确参考仍正确；派生 strict target
   必须在哈希绑定的 operator padding contract 下显式写 0/目标 byte。另有一份 write
   legacy 参考保留 read-only padding keys，只能通过编码等价 materialization 清理。
7. 静态 lane/bounds/mask/reorder/merge 已闭合；RD request/data 与 WR request/write-data
   都存在 delayed-valid 时序边界，first/stall/resume 仍须周期 trace，禁止把静态数据
   方程写成动态无重复保证。

Buffer AG / Buffer Manager 的固定规则如下：

1. `buf_spatial_size=N` 产生低 N 位有效的 lane bitmap；原生 encoder 对 JSON stride
   列表先反转再在高位补零，所以落入 RTL 后仍满足 `stride_rtl[i]=stride_json[i]`。
   每个有效 lane 的地址为
   `row_i=row`、`col_i=low5(col+stride[i])`；col 溢出按模 32 回绕，不向 2-bit row
   进位。
2. Memory Request Manager 再将 `col_i` 分解为
   `bank_i=col_i[4:2]`、`byte_i=col_i[1:0]`、`strobe_i=1<<byte_i`。同 bank 的 lane
   以 OR 合并 strobe；strict target 要求有效 stride 不重复。若精确 col 冲突，RTL
   写数据循环由高编号 lane 覆盖同一 byte，该 alias 不属于批准的生成语义。
3. 物理 buffer 拓扑固定：A/READ_STREAM0 使用 buffer0，并且只有它能 ping-pong 到
   buffer1；B/READ_STREAM1→buffer2，B′/READ_STREAM2→buffer3，
   C/READ_STREAM3→buffer4，WRITE_STREAM0←buffer5。write stream 的第二个
   ping-pong 选择只接常量 ready/zero data，故不得启用；read B/B′/C 也不得启用
   ping-pong。
4. ping-pong 初值为 bank0；已接受的 `last=1 &&
   last_index<=pingpong_last_index` 在时钟沿后切换下一请求。read stream 写 Buffer
   时 request/data 共用当前选择；write stream 读 Buffer 时 data 选择是 request
   选择的一拍延迟，与同步 Buffer 返回对齐。阈值比较均 inclusive。
5. read stream 的 `buf_full_last_index` 与其映射 buffer 的同名字段是两条独立通知：
   前者在 WR_Buffer_AG 向 NSE 发 full/barrier 请求，后者在 Memory Request Manager
   向本 buffer 的 Neighbor manager 报告写满。strict target 要求二者相等；112 个
   授权 read stream 全部满足。
6. Buffer 配置寄存器为 26 bit：
   `buf_src_id[25]`、`buf_full_last_index[24:21]`、
   `buffer_nbr_cnt[20:16]`、`nbr_enable[15]`、
   `buffer_life_time_minus_1[14:11]`、`mode[10]`、`mask[9:2]`、
   `buf_end_row_addr[1:0]`。`enable` 不在寄存器内；存在的对象默认 enable=1。
   `buffer_nbr_cnt=null/缺省` 编为 27；JSON lifetime L 编为 L-1，合法域 1～16。
7. buffer0～4 的 MSE 方向是写 Buffer、Array 方向是读；buffer5 相反，由 Array
   写、WRITE_STREAM0 读。MSE 写必须等待所有命中 byte 无效；MSE 读必须等待所有
   命中 byte 有效，接受后只清除请求 strobe 对应的 valid byte。`mask` 是 Array/N2N
   的 active bank 集，不是 MSE spatial lane mask。
8. JSON `dst_port` 实际接 RTL `buf_src_id`。它只在 buffer5 选择写入源：
   0=Specialized Array，1=General Array。对 buffer0～4 它不选择消费端；数据同时连到
   SA/GA，backpressure 取二者 AND。禁止把字段名解释成通用“目标端口”。
9. Array Request Manager 有两个嵌套计数器。`mode=0` 为 row 内层：
   `for life in 0..L-1: for row in 0..end_row`；`mode=1` 为 lifetime 内层：
   `for row in 0..end_row: for life in 0..L-1`。buffer0～4 在
   `life=L-1` 的已接受 Array read 后到期；非 neighbor 模式直接清 row，neighbor
   模式还要经过本地/partner 完成协同。
10. 65 份授权配置共有 193 个 buffer 对象；48 个省略 enable 但按原生规则启用，
    没有 disabled 实例。5 个启用 stream ping-pong 的实例全是 A/READ_STREAM0 且
    buffer0/1 配置相同。neighbor-enabled 只有 6 个 buffer 实例；其多 slice barrier、
    finish counter 与 N2N 读写切换仍归 `C0-N2N` 审核，不由本节外推。

Specialized Array 的固定规则如下：

1. SA configure register 为 32 bit，不得使用 encoder 旧 docstring 的“24 bit /
   每 inport 5 bit”说明。布局为
   `mode[31]`、`inport2[30:24]`、`inport1[23:17]`、
   `inport0[16:10]`、`data_type[9:8]`、`transout[7:4]`、
   `bias[3]`、`major[2]`、`fp32tofp16[1]`、`fp32tobf16[0]`；
   每个 inport 是
   `{enable,pingpong_en,pingpong_last_index[3:0],nbr_enable}`。
   dtype 只允许 int8=`00`、fp16=`10`、bf16=`11`；`01` 没有 PE pipeline/tag
   分支，必须拒绝。
2. `mode=gemm` 编 0，启用全部 8×8 PE；`mode=gemv` 编 1，只启用 PE row0
   的 1×8。inport0 物理源为 buffer0/1 并按 PE row 广播；inport1 为
   buffer2/3 并按 PE col 广播；inport2 为 buffer4/硬零并按 col 广播。
   buffer5 是写方向，故 inport2 source1 不存在，严禁 inport2 ping-pong。
3. inport ping-pong 初始 source0，在
   `sa_enable && last && last_index<=pingpong_last_index && all_PE_ready`
   后切换。启用时 source0 的 last 固定被隐藏，仅 source1 的 last 能传播；
   `nbr_enable` 会继续清除传播 last，必须由 N2N completion 补回边界。
   strict target 的 inport0/1 阈值必须同时等于各自 buffer0/1 或 buffer2/3
   的 `buf_full_last_index`，且物理 pair 和 producer 必须同时存在。
4. SA 只以 inport0.valid 与 inport1.valid 配对启动 FMA。`bias_enable=0`
   时 initial port 强制 valid、data=0，将 psum bank 初始化为零；
   `bias_enable=1` 时必须启用 inport2/buffer4，每个 bias 握手写
   `p,p+4,p+8,p+12`，四拍填满 16 个 accumulator slot。bias 关闭却启用
   inport2，或 bias 开启却关闭 inport2，均 fail closed。
5. transout 是 loop-depth 比较，不是元素计数。设上游有效 last index 为 `i`、
   配置为 `T`：`i>T` 为 ignore/继续累加；`i=T` 为 matched，关闭并切换
   accumulator bank 但不传播 output last；`i<T` 为 out，关闭 bank 并令
   `result_last=1`。同时到达的 inport0/inport1 last 由 inport0 的 index 优先。
6. INT8 的端口角色固定为 DataA 的四个 signed int8、DataB 的四个 unsigned
   uint8 和 32-bit psum；但当前 `NDP_copy01` 的精确算术不是普通点积。
   17-bit `CSA_4to2` 输出的 carry 已经包含一次左移，`SA_PE_Mul_Array` 又把它
   左移后送入后级，实际方程为
   `psum + signext32(sum17) + (signext32(carry17)<<1) mod 2^32`。
   固定反例：四个 `1×1` 得 6（普通点积为 4），四个 `(-1)×1` 得 -6
   （普通点积为 -4）。这是 `CDA-SA-INT8-CSA-001=CONTRADICTED`；
   signed-A/unsigned-B 角色正确不等于 ResNet Conv/MatMul 数值正确。活动 RTL
   修正或服务器实现身份/bit-accurate 反证之前，不得批准任何普通 INT8 dot 合同。
7. outport legacy JSON `mode=col` 编 major=0，保持
   `out[out][source]=PE[out][source]`；`mode=row` 编 1，转置为
   `PE[source][out]`。不得按标签字面猜“row/col”。gemm 每个 outport 串行
   source0..7，last 只在 source7 传播；gemv 每拍都结束 counter，只消费 source0。
8. 未转换时一个 PE FP32/INT32 结果形成一个 32-bit word；启用 FP16/BF16 narrowing
   时，首个 16-bit 结果放低半字、第二个放高半字。两个 conversion flag 同时为 1
   时 RTL 优先 FP16，但 strict JSON 必须以 `SA.CONVERSION_CONFLICT` 拒绝。
9. FP32→FP16 对 exponent>=`0x8f` 输出 infinity，对 exponent<=`0x70`
   输出 signed zero，subnormal 实现已被注释。FP16/BF16 常规 fraction 使用
   guard/sticky 的 nearest-even，但 exponent carry 条件错误地要求 sticky=1；
   exact-half、保留 fraction 全 1 时 fraction 归零却不进 exponent。
   固定反例：`0x3ffff000→FP16 0x3c00`、`0x3fff8000→BF16 0x3f80`，
   IEEE RNE 均应为 `0x4000`。这是
   `CDA-SA-FP-CONVERT-001=CONTRADICTED`，不得声明完整 IEEE narrowing。
10. 65 份授权配置只有 8 份 SA，全部 FP16、bias=0；其中 4 份启用 FP16
    narrowing，没有 INT8、BF16、enabled-bias 样例。精确参考配置仍是正确来源，
    但不能外推到缺失数值域或上述已反证 corner。

General Array 的固定规则如下：

1. GA inport 配置实际为 20 bit：
   `mask[19:12]、src_id[11]、pingpong[10]、threshold[9:6]、nbr[5]、
   fp16[4]、bf16[3]、int32fp[2]、uint8fp[1]、uint8int32[0]`；outport 为
   12 bit。每个 PE 配置为 144 bit、分四个 36-bit beat，下发顺序是
   `{opcode,transout,三个端口控制}` 后跟三个 32-bit constant。
2. PE 是 4×4、三输入。`src_id=0` 的外部 GA inport 编号为
   `row+4*floor(col/2)`；其余 selector 1..5 固定为西北、北、东北、西、东
   邻接 PE。outport0..3 从 col0/1 二选一，outport4..7 从 col2/3 二选一。
   SFU 只存在于奇数列 col1/3；在 col0/2 配置 `rec/sqrt/rec_sqrt/
   sfu_activation` 必须以 `GA.SFU_PLACEMENT` 拒绝。
3. 算术方程固定为：`add=A+B`、`sub=A-B`、`mul=A*B`、
   `max=max_fp32(A,C)`、`sum=A+C`、`summac=A*B+C`、`mac=A*B+C`、
   `int32_sum=A+C`、`int32_sub=A-B`、`int32_mac=A*B+C`。SFU 先归一化
   A、按 breakpoint 选择 slope/intercept，算 `x_norm*slope+intercept`，再执行
   对应 exponent 后处理。算术必需端口为 add/sub/mul/int32_sub 的 A/B，
   max/sum/int32_sum 的 A/C，summac/mac/int32_mac 的 A/B/C，SFU 的 A。
4. `max/sum/summac/int8_max/int32_sum` 会进入 transout 自归约。INT8 首项
   C 被强制为 0，后续 C 来自 outbuffer，所以 JSON 只需 A。数值上未被 opcode
   使用的已启用端口仍参加 input matching/backpressure；原生四片 remote-sum
   确有这种控制依赖，不得仅按算术方程将其删除。
5. transout 的普通输出 last 条件是
   `buffer_last && buffer_last_index<T`；归约 flush 触发为
   `reduction && buffer_last && buffer_last_index<=T`。相等边界不产生
   pre-flush last，而是在 flush 完成后强制一拍 valid/last。flush 调度为
   FP32/SFU 8 拍、INT32 4 拍、INT8 1 拍。
6. PE port mode 为 `null=0、buffer=1、keep=2、constant=3`。
   buffer 正常消费；keep 等某个 buffer carrier 满足
   `last && last_index<=keep_last_index` 后释放；constant 不请求上游；
   null 关闭该端口 valid gate。开启 ping-pong 必须有 inclusive threshold；
   GA inport `src_id=1` 是单一 SA result source，没有第二路可切换，禁止同时
   开 ping-pong。
7. FP16/BF16 输入一字拆两项，低 16 bit 先出、仅高半项带 last；UINT8 输入按
   byte0→byte3 拆四项、仅 byte3 带 last。转换 flag 的 RTL 优先级是
   fp16→bf16→int32fp→uint8fp→uint8int32，但 strict JSON 必须互斥。
8. INT32→FP32 不能批准为一般有符号转换：负数幅值只取低 31 bit，而“最小负数”
   检测写成 `&input`。固定反例为 `-1(0xffffffff)→0xcf000000`（错误变成
   `-2^31`），`INT_MIN(0x80000000)→0xce800000`（错误变成 `-2^30`）。
   这是 `CDA-GA-INPORT-CONVERT-001=CONTRADICTED`。
9. 当前 `int8_max` 的四个 unsigned byte lane 选择极性反向，实际为
   `result_lane=min(A_lane,C_lane)`；反例
   `A=0x04030201,C=0x01020304→0x01020201`，而 max 应为 `0x04030304`。
   同时 pipeline0 ready 方程没有 INT8 分支，第一项后不能接受第二项。两项缺陷
   独立存在，均由 `CDA-GA-INT8-MAX-PIPE-001=CONTRADICTED` 阻断 MaxPool。
10. `CDA-GA-INT8-MAX-PIPE-001` 与
    `CDA-GAP-GA-ACCUM-STATE-001` 是两个正交 RTL blocker。前者只由 GA INT8
    opcode（当前正式配置为 `int8_max=0x0b`）触发；后者由
    `int32_sum=0x0c` 的 transout 归并在 occupancy=1 时固定减 2、清 tag 不清 data，
    再由无 valid guard 的 C feedback 触发。输入 tensor 是 UINT8 不能把两者归为
    同一个“INT8 问题”；修复任一项不得解除另一项。选择规避候选时必须检查实际
    GA opcode、conversion 和 transout，而不是只检查 tensor dtype。
11. outport 无转换时一项一 word；FP16/BF16 两项按 low16/high16 打包，并继承 SA
    converter 的 subnormal/exact-half 缺陷；INT32→UINT8 是 signed saturate 到
    `[0,255]`，四项按低 byte 到高 byte 打包。60 份 GA 授权配置共 511 个 PE，
    没有 GA input ping-pong、BF16、sqrt、int32_mac 样例；样例正确性不得外推到
    这些空白域或上述反例。

N2N 的固定规则如下：

1. 每个 neighbor stream 配置为 8 bit：
   `src_slice_sel[7]、dst_slice_sel[6]、ping_pong[5]、
   nse_cnt_size[4:0]=mem_loop-1`。硬件有两个 NSE；stream0 固定使用
   buffer0/1，stream1 固定使用 buffer2/3。
2. selector0 选择一条 28-slice low ring，selector1 选择七条 4-slice high
   ring。src selector 决定接收的 previous，dst selector 决定发送侧采用哪个
   next-ready；全环端点必须兼容。slice0 在 low ring 为 `prev=1,next=12`，
   在 high ring 为 `prev=1,next=2`；完整映射固化在
   `CDA-N2N-ROUTE-TRANSFER-001` 合同和 `n2n_neighbor()` 微模型中。
3. `mem_loop=L` 的 controller count 编为 `L-1`，实际执行恰好 `L-1` 次完整
   buffer 传输；`L=1` 不传输。每次固定遍历 row0,1,2,3，每行传
   256-bit data、32-bit valid、tag/same，并分别做 ready/valid 握手；不是
   pointer alias 或 zero-copy。
4. 发送 selector reset 为 buffer1，MSE trigger 后先切到 buffer0；接收 selector
   reset 为 buffer0，trigger 后先切到 buffer1。之后每次四行完成都无条件交替，
   所以传输序列为 `buffer0→buffer1、buffer1→buffer0、…`。
5. JSON `ping_pong` 虽被 decode 为 `nse_pingpong_enable`，但其模块连接被注释，
   没有任何消费者；硬件总是交替。为使 JSON 如实描述行为，启用 N2N 时 strict
   target 只接受 `ping_pong=1`，值 0 以 `N2N.PINGPONG_HARDWIRED` 拒绝。
6. N2N pair 的两只物理 buffer 必须都存在、enable/nbr_enable=1、
   `buf_end_row_addr=3`，并具有一致的 active 配置；否则分别以
   `N2N.BUFFER_PAIR_REQUIRED`、`N2N.BUFFER_NEIGHBOR_DISABLED`、
   `N2N.FULL_ROW_REQUIRED` 或 `N2N.BUFFER_PAIR_MISMATCH` 拒绝。
   缺省 `buffer_nbr_cnt` 按 encoder 的 27 比较，不强制它等于 `mem_loop-1`。
7. incoming-write 和 outgoing-read controller 独立计数，只要任一非零就保持
   MSE barrier。`nse_enable` 在传输结束后不会自动清除；disabled configure beat
   虽清配置寄存器，却没有对称的 `nse_enable<=0` 分支。跨 stage 复用必须证明
   reset、slice_rst、`se_nse_configure_clear` 或明确 reconfigure 边界。
8. 65 份授权语料中只有 3 份 N2N，全部为 neighbor_stream0、ping_pong=1：
   一份 `mem_loop=28,selector 0→0`，两份 `mem_loop=4,selector 1→1`。
   没有 stream1 或 mixed-selector 样例；这两域仍需单独 stage/dynamic 证明。

stage-aware 必要覆盖门：

- 对 typed 输出，先从 output shape/dtype 求每 active slice 的输出字节数，再以 write
  stream 的 `product(idx_size+1)` 求单事务字节数；可证明的 index 数值域所形成的不同
  transaction base 数不得少于所需事务数。
- 当前 `r5:hwop-0071-00` 每 slice 输出 `2048×int32=8192B`，D 事务为 32B，至少需要
  256 个不同事务基址。原始授权 strict 投影的 LC2 本地域为 `{0}`、PE1 为 `LC2*1`、D
  `dim_stride[0]=32`，只能产生 1 个事务基址，必须以
  `B_GAP_D_INDEX_CARRIER_SEMANTICS` 拒绝。
- 把 LC2 的 `src_id` 改指向另一个 LC 不会扩大其本地数值域，属于固定反例。把最小
  测试副本的 LC2 `end` 改为 256 只能通过“256 个基址”的必要门，不证明该修改是完整
  正确 schedule；mapping、tag/keep、完成、数据和 E4/E5 仍须独立闭合。
- 已裁决的新 schedule 不是上述单字段试改：LC2 改为独立 outmost 数值 root，
  `start=0,end=256,stride=1,last_index=0`，PE1 保持恒等乘 1，GROUP1 buffer loop
  与 D stream 共同受 LC2 backpressure/tag 驱动。其 256 个 bias 为
  `0,32,...,8160`，strict issue=0、原生 mapping penalty=0；只在
  `hwop-0071-00-d-index-v1` 身份内解除 `B_GAP_D_INDEX_CARRIER_SEMANTICS`。
- 上游模板的授权正确性继续作为其精确来源证据，但不能覆盖已被当前 RTL＋typed stage
  反证的 ResNet 等价关系。现有 GAP strict/stage/address-bound 配置及其
  mapping、bitstream、execplan、workload/package 均为 invalidated derived outputs；
  修正后必须使用新配置和新产物身份重建，禁止原地覆盖历史证据。
- probe_v5 已把独立数值分歧收窄到 GA block1 最终累加操作数：
  `700313000` 的 block0 正确，`700388000` 的 block1 已错；MSE4 512/512 握手、
  packing 和 GA 对给定 A+C 操作数的整数加法均正确。该问题固定登记为
  `CDA-GAP-GA-ACCUM-STATE-001=CONTRADICTED`，以
  `B_GAP_GA_ACCUM_STATE` 阻断 GAP。静态 RTL 已进一步证明 inbuffer match 在
  `transout_initial>=2` 时不要求
  inport2 valid，非 calculate 分支又无条件读取未清零的 outbuffer data，且没有
  valid guard；因此 invalid slot stale-data 是 RTL 反例和可达机制。修正 D carrier
  不能消除此 blocker。
- 服务器与本地关键路径 14/14 文件规范化文本一致，当前非 SFU GAP 不受四处
  GitHub 差异影响。v7 已动态记录全部 8 个普通 PE 在
  `700313000→700316000 ps` 从 `count=1` 下溢回绕为非法 `count=3`，并在
  `700318000 ps` 于两个 tag 无效、`ob_valid=0` 时复用旧槽 C；共记录 16 次非法
  occupancy 和 217 次 invalid-slot reuse。v10 又在修正 LC2、保持服务器原始 RTL
  的单变量运行中重复相同根因，因此精确分类固定为
  `ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse`，不再是
  `TEST_REQUIRED`。v10 未完成正式 D 回读和 E5，故动态根因闭合不等于候选发布。
- GA INT32→FP32 输入域不得按 node-0004 单例推广。全 55 个使用该转换的 stage
  已扫描 169,442,944 个正式 W3 int32：45 个 stage 命中已知反例，共 6640 个
  `-1`；其余 10 个 stage 只证明本次输入未命中。所有 55 个继续保留
  `B_GA_INT32TOFP32_INPUT_DOMAIN`，最终 UINT8 saturation 偶然掩盖差异也不解除。
- 当前 Conv 1×1/3×3 生成器的 LC 链按 trigger 嵌套构造，需要相同 numeric schedule
  的远端端点使用独立 root；未发现 `src_id` 数值继承代码。该检查不解除 Conv 的
  SA、bias/psum、tail、CONFIG lifetime 或 E4/E5 blocker。

RD Memory AG 的静态与动态边界：

- 两通道 outbuffer 在 `vld && ready` 时清除当前 `vld`，同时每拍执行
  `vld_d <= vld`，对外 valid 为 `vld_d || vld`。因此 ready 清除后的下一拍可能出现
  `vld=0,vld_d=1` 的旧地址 valid；若该通道 ready 同拍为 1，Datahub 可再次接受旧地址。
  这是 `CDA-MSE-RD-VALID-001=RTL_PROVEN`，且没有 JSON 位可关闭该方程。`vld_d`
  本身没有显式 reset 分支，首拍收敛还依赖当前 `vld` 复位后的继续时钟，也必须保留为
  first-beat 审核边界。
- probe_v4/v5 已推翻 sim6 的 GAP-specific replay 归因：按两个物理通道各自 FIFO
  关联，8960/8960 request occurrence、DDR payload 和深层 256 个
  metadata/consume 均匹配；跨通道全局顺序和 TB 推导 `IssueCh/IssueTime`
  不是 carrier identity。故 `CDA-MSE0-RD-REPLAY-001=CONTRADICTED`，旧 probe_v1
  实验不再派发。
- 上述结论只否定当前 GAP 的旧归因，不否定 `CDA-MSE-RD-VALID-001` 的通用 RTL
  方程。其他新 schedule 仍需独立覆盖 first/stall/resume；不得因 v4/v5 当前路径匹配
  就全局声明 Memory AG 动态安全。

重建与回归入口：

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\build_stage_operator_semantics_audit.py
& $py tools\build_stage_config_backend_catalog.py
& $py tools\build_stage_config_system.py
& $py -m unittest tests.test_stage_operator_semantics_audit `
  tests.test_stage_config_backend tests.test_stage_config_system
```
