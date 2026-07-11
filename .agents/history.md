# ResNet50 INT8 工作日志

最后更新：2026-07-11

本文件只保留已经发生的关键决策、验证和状态变化。当前任务看 `.agents/plan.md`，代码和仓库细节看 `.agents/agent.md`，单算子推导看 `.agents/rules/算子配置规则.md`。

## 2026-07-05～2026-07-09：确认原始ResNet参考链

- 克隆 `CGRA_SIM`，基线commit为 `53c41e0`；确认其中已有ONNXRuntime golden、QNN软件算子、DDR辅助、旧手写execution plan和Python functional simulator。
- 确认旧 `.cu` 功能模拟链不等于目标JSON/bitstream链；golden dump不完整、路径硬编码、checkpoint数量不足。
- 将项目协作文档统一迁到根目录 `.agents/`：`agent.md`负责接手入口，`plan.md`是唯一执行计划，`history.md`只记事实。

## 2026-07-10：引入NDP工具链并完成两仓审计

- 拉取 `ndp-sim-ref`，基线commit为 `e299b2804448242d1589b3e58ed7c5a9a5eca09f`；完整工作树413个跟踪文件。
- 定位目标主线：42个单算子JSON、JSON→bitstream、`model_execplan`、DeepSeek golden/relayout和address-remapping；将计算到配置的规则整理为 `.agents/rules/算子配置规则.md`。
- 固定seed批量测试42个JSON：38个模板曾成功生成完整bitstream，4个仍受placement约束失败；bitstream成功只证明编码/placement，不证明数值正确。
- 确认现有JSON只局部覆盖ResNet：核心INT8 Conv/MatMul、完整Add/AvgPool requant和逐层qparams传递仍缺失；`model_execplan`仍含28-slice假设和unresolved constant风险。
- 从旧ResNet计划还原77个模型级原语：2 Quantize、53 Conv、1 MaxPool、17 Add、1 AvgPool、1 MatMul、2 Dequantize；确认Conv首/中/末K tile分别执行bias初始化、int32 psum累加和requant。
- 操作者确认目标硬件为16个PE/slice阵列；仓库中的28-slice DeepSeek约定改为待适配参考。不同版本的资源数、字段位宽、opcode和DDR row存在冲突，不能混用。
- 全量审计 `CGRA_SIM` 275个、`ndp-sim-ref` 413个跟踪文件；唯一Python语法错误为 `CGRA_SIM/cgra_python/layout/layout_buffer.py:201`。

## 2026-07-11：引入Conv模型、建立环境和端到端计划

- 克隆 `NDPFuncModel/conv_func`，commit为 `89d1655ce6450477cdcc04965d8b4866f12066e5`；完整历史47个提交，1232个跟踪文件。
- 确认其提供硬编码Conv DRAM→AG→Buffer→8×8 PEA→ring通路和旧固定配置，但不读取目标JSON/bitstream；`config_nse.py`的NSE count=15是16个PE间15次邻居传递的候选证据。
- 确认关键缺陷：`hex_data`缺失；slice跨度漏bank；逻辑slice0～3实际都读物理slice0；RDAG/WRAG遗漏multi-transaction偏移；A/B符号与ResNet参考相反；int32 psum经过浮点；最后reduction判定错误；requant和真实DRAM writeback未完成。
- 当前 `extracted_*.npy` 和 `verify_pe` psum由错误链路生成，不得作为golden。
- 创建根目录持久化 `.venv`（CPython 3.12.13），安装并锁定NumPy、ONNX、ONNX Runtime、PyTorch CPU、OpenCV等依赖；`pip check`通过。`model_execplan --help`可启动；Conv入口运行到缺 `hex_data`；golden入口运行到既有语法错误。
- 将最终目标确定为：正式ONNX→全节点/硬件子步骤golden→16-slice relayout→全算子JSON/bitstream→目标simulator→execplan/Bank_data→RTL/硬件→三方逐算子和整网一致。
- 将执行计划统一为W0～W9工作包和G0～G9验收门；W0先建立根集成层、manifest、contract、adapter、artifact和mock状态机，W1外部规格并行，W2以小Conv建立第一条真实纵向闭环。
- 审核计划并补齐根repo/`repos.lock.json`、architecture/quantization/backend contract、不可变attempt、resume失效、adapter能力探测、memory地址安全、分层CI和operator coverage matrix。
- 删除临时独立阻塞报告，其有效结论已合并进 `plan.md`，避免重复文档漂移。

## 2026-07-11：W1暂定模型基线

- 操作者暂定接受官方ONNX Model Zoo `resnet50-v1-12-int8.onnx`作为正式模型；已下载并通过checker，SHA-256为 `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0`。
- 预处理暂定复现旧 `golden.py`：RGB输入直接缩放到256×256、中心裁剪224×224、除以255后使用ImageNet mean/std归一化、HWC→CHW。复核后确认ONNX本身不规定resize；旧脚本明确加载同名模型且检查节点与当前图匹配，是旧功能模拟链的实验性golden基线。此前“官方必然保持宽高比、与旧脚本冲突”的表述证据不足，撤回为待官方评测源码核验。
- 旧ONNX、DDR、golden和原 `hex_data`降级为兼容性回归资料，不再作为软件工作开工前置。
- 模型IR 4、opset 12、78节点、366 initializer；算子数量与旧77原语计划完全一致。53层Conv全部为UINT8 activation、INT8 weight、INT32 bias、per-output-channel weight scale，weight zero point全为0，但input/output zero point并非全部为0。
- 使用仓库 `cat.jpg` 生成 `[16,3,224,224]` 输入并以ONNX Runtime 1.27 CPU得到 `[16,1000]` 输出；第二次执行与保存输出bit-exact。模型、图片、输入和输出hash已写入 `contracts/model_baseline.json`，同时建立quantization/architecture candidate contract和ADR-001。
- 按操作者要求统一根集成层说明文档：将 `算子配置规则.md` 迁入 `.agents/rules/`，将ADR-001迁入 `.agents/decisions/`；requirements和contracts因分别属于环境清单和机器契约留在根目录。未发现可明确删除的过时说明文档。
- 迁移校验发现大型规则文档读取时曾受工具输出长度限制；已重建受影响的6.5～15.1中段并复核1～16章标题、UTF-8和截断标记，最终规则文档完整且较原版更紧凑。

## 2026-07-11：W0骨架完成并开始W2

- 操作者提供本地正式模型文件；大小和SHA-256与项目缓存的Model Zoo模型一致。出于后续GitHub发布隐私考虑，历史不记录含个人账号标识的本机绝对路径。
- 完成根集成层W0：建立 `resnet50_pipeline`、CLI、稳定Node/Tensor/HwOp/Layout/Config/Execution/Result记录、run manifest、contract/backend能力探测、artifact原子写入、阶段DAG、失败阻断、cache key、resume和旧schema拒绝/跳过规则。
- 建立 `pyproject.toml`、`repos.lock.json`、backend candidate contract、run manifest schema、mock fixture和operator coverage矩阵；根 `.gitignore` 排除虚拟环境、运行产物、生成目录及三个独立参考仓库，避免首版误生成gitlink或提交大文件。
- W0共11项单元测试通过；可安装CLI的probe、contract验证、完整mock run、resume复用、缺输入、能力不支持和backend失败路径均验证通过，G0判定通过。三个参考仓库未因W0发生新修改。
- 开始W2并完成独立QLinearConv软件golden：标量循环和im2col/einsum两条实现均覆盖UINT8 activation×INT8 weight、INT32 bias/psum、per-channel weight scale、非零zero-point、group/stride/padding/dilation、nearest-even和UINT8饱和，并输出bias初值、reduction tile psum、最终accumulator和requant结果。
- QLinearConv两条实现与ONNX Runtime在小型确定样例上逐元素bit-exact；连同W0当前共15项测试通过。下一步是小Conv物理partition/layout、地址provenance和正逆round-trip，再接入修复后的NDP功能模型。
- 操作者规定版本策略：现在建立根本地Git仓库并做首个提交；此后每个验证有效的小步骤做原子提交，W1/W2等大步骤完成后推送GitHub。任何删除、压缩或改写历史必须先询问确认。
- 根本地Git仓库已建立，首个提交为 `5bf423f`；首版排除了模型、虚拟环境、运行产物和三个参考仓库，提交后根工作树干净。
- W2小Conv候选物理布局已实现：严格复现NDP DRAM的slice/bank/row以及反向col/subword字节坐标，修正 `bytes_per_slice` 必须包含bank数；提供16-byte边界拆分、显式byte-stride transaction和稀疏physical image。
- 布局合同 `w2_ndp_ring_candidate_v1` 按NDP ring意图将activation沿C连续分片并存为NHWC，将weight/bias/qparams/output沿K连续分片，weight存为RSKC、output存为NHWK；C/K tail分别用zero-point填充，所有region对齐到16字节。
- 每个physical byte均记录tensor、逻辑坐标、element byte、data/tensor-padding/alignment语义和DRAM五维坐标；实现统一 `forward/inverse/explain_coordinate/validate`，1-slice与4-slice含C/K tail样例均bit-exact round-trip。
- 当前共20项测试通过。此步骤只完成raw↔physical和provenance，仍是candidate；NDP functional model尚未消费该image，G2尚未通过，16-slice扩展仍按计划留到G2之后。
- 在 `NDPFuncModel` 子仓库完成并提交 `789d121`：修复 `per_slice` 漏bank、`run_dram_to_ag` 未应用slice基址，以及RDAG/WRAG跨transaction物理地址丢失；逻辑counter与物理transaction offset现已分离。
- NDP侧新增4项寻址回归，覆盖4-slice独立DRAM写读、slice AG读取、跨16-byte边界的strided RDAG和WRAG对称顺序；全部通过。测试运行禁止写 `.pyc`，避免污染该仓错误跟踪的缓存文件。
- 根集成层新增显式 `NdpFunctionalAdapter`，通过独立子进程把同一W2 physical bundle载入NDP DRAM，并逐region读回校验SHA-256和slice坐标；根侧当前21项测试全部通过。
- 当前闭环边界推进为“raw↔physical↔NDP DRAM bit-exact”；尚未经过Buffer/PEA/reduction/requant/writeback，G2仍未通过。
- 在 `NDPFuncModel` 子仓库完成并提交 `deee41f`：INT8 PEA按uint8 activation A×int8 weight B执行，psum保持int32、乘加使用int64检查中间值；branch屏蔽lane先清零，越界暂显式报错，等待硬件溢出规则确认。
- NDP侧新增4项INT8 PEA回归，连同寻址测试共8项通过。根adapter新增physical-address dot probe：从4个activation slice和所属K slice读取字节，以折叠输入zero-point后的有效bias启动累加，单输出坐标accumulator与独立QLinearConv golden逐值相同；根侧21项测试通过。
- 当前闭环边界推进为“raw↔physical↔NDP DRAM↔单坐标整数PEA accumulator bit-exact”。尚未覆盖全部输出坐标、跨slice reduction结束、requant、INT8 packing和真实writeback，故G2仍未通过。
- 在 `NDPFuncModel` 子仓库完成并提交 `86cd3e3`：删除错误的 `r*s*cc_shared` reduction末态判定，统一使用LC `last/last_index`；同时把PEA psum清零从每个R迭代后移到完整C/S/R及ring reduction结束后，避免3×3/C累加被中途丢弃。
- NDP侧新增3项reduction调度回归，覆盖词典序末态、非零start/非单位step及非法状态，连同既有测试共11项通过。该提交修复控制与生命周期，但完整输出坐标尚未实际跑通，不能据此宣布G2通过。
