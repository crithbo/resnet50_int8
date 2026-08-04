# Conv 配置绕行前本地 RTL 与替代入口审计主线授权

日期：2026-07-28

## 用户授权

用户要求 Conv 优先，但禁止在以下前置条件完成前直接推进 serialized 配置绕行：

1. 详细分析本地活动 RTL 与完整代码消费链；
2. 确认 RTL 的普通 INT8 dot4 路径确实存在功能问题；
3. 穷尽并否决其他可配置、精确、保持目标 INT32 语义的入口；
4. 只有确认 serialized config fallback 是当前唯一可用精确路线后，才开始生成绕行配置；
5. 首个完整 Conv 必须逐节点单独测试，之后才能按参数类别选择代表并批量复用。

用户随后明确追加：

- node0004 的全部既有本地资料均不可信，历史测试按失败处理；
- 旧 JSON、mapping、bitstream、execplan/SCA、package、local simulator output、
  local E2 与测试收据不得作为新配置输入或通过证据；
- C0 若确认 RTL 缺陷且没有其他入口，采用全新 config bypass；
- C0 若发现其他精确入口，或确认 RTL 不存在该错误，则采用正常/替代入口继续；
- 两条路径都必须从活动规则和锁定原生工具链全新生成 node0004 算子 JSON，再完成
  第一个完整 Conv 单节点测试；
- 本地执行止于生成测试包，不上传、不运行。

## C0 派发门

主审与独立复核均为只读任务。允许：

- 读取本地活动 filelist、RTL、mapper、encoder、handler、registry、typed lowering、
  既有 immutable report 与 source-level replay；
- 生成只读分析报告、SHA manifest、capability matrix；
- 若本地工具存在，在非 RTL 目录创建最小 testbench/临时编译产物。

禁止：

- 修改任何 `rtl/**`；
- 生成新的 Conv target/bypass JSON、mapping、bitstream、execplan/SCA 或服务器包；
- 检查服务器文件、服务器名称或服务器 RTL identity；
- 上传、运行服务器或授予 lease；
- 把既有 task record 当作替代本轮活动代码复读的结论。

## 主线通过条件

两份独立报告必须同时证明：

```text
RTL_DEFECT_CONFIRMED = true
NO_EXACT_ALTERNATIVE_ENTRY = true
SERIALIZED_CONFIG_FALLBACK_IS_ONLY_AVAILABLE_EXACT_ROUTE = true
```

并提供：

- 活动本地 filelist、module hierarchy 与 source SHA；
- typed request→JSON→mapper→bitstream→control→packing→RTL→psum 路径；
- carry shift、reduction width、`cout` 消费和 signed domain 的逐式证明；
- four-ones、完整正负范围、mixed-sign、psum wrap、tail/bias/x-zp 反例；
- SA opcode/mode、lane/packing、GA、FP 路径、handler/mapper registry 的替代入口矩阵；
- static proof 与 dynamic proof 的明确区分。

裁决分支：

- 三项全为 true：允许 `PATH_CONFIG_BYPASS`；
- `RTL_DEFECT_CONFIRMED=false` 或找到精确替代入口：使用
  `PATH_NORMAL_OR_ALTERNATIVE`，不允许 serialized bypass；
- evidence incomplete 或两份报告冲突：停止，任何配置生成均不允许。

## C1 及后续

C0 主线通过后，首个目标固定为完整 `node0004`：

```text
hwop-0004-00 accumulate
→ hwop-0004-01 requant
→ complete UINT8 node output
```

node0004 全部历史本地资料只作负面历史，禁止复用。C0 选定路径后，必须从 typed
request、正式 W3/model tensor、活动规则、C0 直接代码证据和获授权的原生静态模板/工具
源码开始，以全新目录和 identity 重建：

```text
operator JSON
→ mapping / bitstream
→ execplan / SCA
→ address / lifetime
→ config-bound complete UINT8 node
→ local server test package
```

配置生成前完整读取生成前索引、公共规则、NDP硬件字段、INT8 SA、精确UINT8量化尾和
Requant 专项规则；测试包生成前再读取服务器测试包规则与本地活动 package 入口 README，
保存 current SHA receipt。node0004 完整本地 E2 与 `PACKAGE_READY_NOT_RUN` 形成后，才按
lowering schedule signature 选择每类一个代表并批量复用同类节点。

本授权不包含功能 RTL 修改、服务器现有文件/名称/identity 检查、上传或运行。
