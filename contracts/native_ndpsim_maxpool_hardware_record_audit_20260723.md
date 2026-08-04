# 原生 ndp-sim MaxPool 硬件测试记录审计

日期：2026-07-23  
仓库：`https://github.com/uSFrances/ndp-sim.git`  
审计提交：`ec12424516ae0304228dd2321d4e604fe225e04e`

## 结论

在该提交的 Git 跟踪内容和 Git 历史中，**没有找到两份原生 MaxPool 配置已经通过真实硬件、RTL/VCS
仿真或服务器测试的明确记录**。

能够确认的只有：

- 两份 MaxPool JSON 是原生 Git 跟踪文件；
- 它们能被原生配置/bitstream/execplan 工具消费；
- JSON 和编码器包含 `int8_max` 配置。

不能从原生仓库确认：

- 是否曾在 RTL/VCS 上自然完成；
- 是否产生过写数据和正式 D 回读；
- 是否与 Golden 数值一致；
- 测试使用的 RTL/filelist 身份；
- 是否曾在仓库外部做过未归档的硬件测试。

## 被审计的算子

```text
jsons/maxpool_config_16_16_16_stride2_padding1.json
jsons/maxpool_config_16_112_112_stride2_padding1.json
```

## Git 历史

两份文件都只追溯到同一个引入提交：

```text
d2b821c9f4353713b240d8a839d4f44949a44471
2026-04-23T21:17:27+08:00
Add new JSON configuration files and update control register logic
```

该提交一次加入 35 个文件，包括多份 Decode/Prefill、GEMM、Pool、Quant 和其他配置。提交说明只描述新增
JSON、修正 control-register 引用和保持 execution-plan 兼容，没有 MaxPool 硬件测试、通过状态、周期数、
RTL 身份或回读结果。

## README 证据

原生 Git 跟踪文档只有：

```text
address_remapping/README.md
generate_python_golden/README.md
generate_python_golden/README_gen_data.md
model_execplan/README.md
model_execplan/README_op_json.md
```

这些文档没有提到 MaxPool 的硬件通过记录。相反，
`generate_python_golden/README.md` 明确限定当前验证范围：

```text
第 609 行：硬件输出对比暂不执行，其余任务通过软件验证
第 632 行：硬件仿真输出对比暂缓
第 679 行：硬件输出对比按当前要求跳过，软件范围完成
```

因此 README 中的“完成”不能解释为 MaxPool 已完成硬件测试。

## 随附结果检查

Git 跟踪树中没有与这两份 MaxPool 配置绑定的：

- `sim.log`；
- VCS/RTL 测试报告；
- FSDB/VCD；
- MSE4 写数据记录；
- `matrix_D` 硬件回读；
- Golden↔RTL 比较报告；
- CI 硬件测试任务或通过徽标。

仓库中存在 ring-GEMM 的硬件 trace 分析文档，说明上游在有硬件数据时会保存明确的 cycle/trace
分析；但没有等价的 MaxPool 文档。

## 与本项目服务器结果的关系

本项目 2026-07-23 的 `sim4(2).zip` 是当前工作区新增的真实服务器运行证据：

- 正确装载 `native_int8_maxpool16_r1_graph`；
- 30 个矩阵和 29 行 execplan 装载；
- 138 次 GEXEC→slice 握手；
- 28 slice 有读返回和写地址，但 MSE4 写数据为 0；
- 无自然完成，最终 SIGHUP。

该结果使用原生 JSON 和原生控制工具链，但它是**本项目新取得的外部服务器证据**，不是 GitHub
原生仓库随附的既有通过记录。

## 证据边界

本审计只能得出“原生 Git 仓库没有明确归档硬件通过记录”，不能推导“作者从未在仓库外测试过”。
在作者提供外部日志、实验记录或对应 RTL 身份前，两份 MaxPool JSON 应标记为：

```text
upstream_native_configuration_present
hardware_pass_record_not_found
```

