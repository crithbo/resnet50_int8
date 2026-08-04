# QLinearAdd node0007 真拆分 workload 启动记录

- owner：`019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target：`019fbec2-fe93-7e03-9314-cff6f222f33d`
- 状态：`AUTHORIZED_MATERIALIZATION_IN_PROGRESS`
- 服务器动作：无；未上传、未运行、未取得 lease

## 更正

最终 v24 `sca_cfg.json` 的合同回读为：

- `Repeat_Num=1`
- `Exec_Length=29`
- `ExecutionPlan=execplan_op_b_dequant.txt`

因此 v24 的真实服务器执行是 B-dequant 单 stage；ZIP 内仍携带其他五个 stage
资产不等于运行六阶段全链。v24 ZIP 保持原字节、原身份和
`PACKAGE_READY_NOT_RUN`，不作为新拆分身份原地改写。

## current 收据

- agent：
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- plan（mutable provenance）：
  `e37ee58cf9a4ac98423b066516ee610054f940505c00a8e3fb2bc921a412c583`
- index：
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- common：
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- hardware：
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- server：
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- QAdd：
  `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f`
- exact tail：
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- README：
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

## 边界裁决

1. A 独立运行 `op_a_dequant + op_b_dequant`，只消费冻结的原始 typed A/B。
2. B 独立运行 `op_relocation_pad`。其输入在冻结 graph 中是 external，payload
   是非计算性 FP32 零 spacer；不是 host 计算的内部 scratch。
3. C 未发现逐字节回收的硬件 A-scaled/B-scaled payload，也不以 host 重算冒充；
   自动退化为 `A+B+relocation+fp32_add` 累计前缀。
4. D 未发现逐字节回收的硬件 FP32 SUM payload，也不以 host 重算冒充；
   自动退化为六阶段 full chain，并保留 28 formal D。

完整机器合同：
`contracts/operator_config/qlinearadd_node0007_split_workload_v25.json`。

## 原生 materialization 进度

- A：两阶段原生 execplan 已通过双生成、最终链与 request-address 验证；
  `Repeat_Num=2`，`Exec_Length=57`。
- B：单阶段从空 mapping/execplan state 重建；只有 stream0/stream2 的两个
  planner-owned base address 随 fresh 单段 allocation 改变；其余配置不变；
  `Repeat_Num=1`，`Exec_Length=29`。
- C：四阶段累计前缀已通过双生成、最终链与 request-address 验证；
  `Repeat_Num=4`，`Exec_Length=126`。
- D：继续绑定冻结六阶段 execplan 与 28 D，不重复 C 前缀的大域地址枚举。

本阶段 machine report：
`artifacts/operator_config_validation/qn7v25-split-progress/report.json`。
当前 `PACKAGE_RELEASE=NONE_IN_PROGRESS`；runner/observer/manifest/ZIP 尚未组装，
不得把原生 execplan 证据误称服务器包。

## 冻结边界

本轮不重复 numeric/W3/qparam/tail/workload 数值分析，不修改功能 RTL，不改变
golden 值。分段结果只用于定位；不得关闭未执行 producer、跨段 barrier/lifetime
或 E3/E4/E5。最终仍需一次六阶段 + 28 D 端到端运行。
