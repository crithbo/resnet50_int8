# MaxPool INT8 max 活动 RTL 主线裁决（2026-07-28）

## 裁决

- `INT8_MAX_NUMERIC_POLARITY=CURRENT_ACTIVE_SOURCE_SELECTS_UNSIGNED_MAX`
- `INT8_MAX_PIPELINE0_READY=CONTRADICTED_NO_INT8_BP_POST_BRANCH`
- `FUNCTIONAL_RTL_MODIFIED=false`
- `SERVER_SOURCE_INSPECTED=false`
- `OLD_MAXPOOL_MATERIALIZED_ASSET_USED_AS_POSITIVE_PROOF=false`

旧公共规则把 `int8_max` 数值极性写成 min。针对当前活动源码的独立
`GA_PE_Float_CSA` 测试和完整
`GA_PE_ALU→GA_ALU→GA_PE_Float_CSA→GA_PE_Float_Last` 测试均证明逐 byte
结果为 unsigned max，故旧数值极性结论作废。该翻案只关闭当前源码身份的局部数值
不确定项，不构成整 GA、整 Slice、正式 MaxPool 地址/terminal 或服务器动态通过。

pipeline0 ready 缺陷继续成立。`GA_PE_Inbuffer.sv` 的
`alu_pipeline0_bp_post` 只有 INT32 和 FP32 分支，没有 INT8 分支。首个 INT8 token
进入 pipeline0 后，`bp_post=0`、`enable=0`、`clear=0`；第二个 token 可以进入空
inbuffer，但不能进入 pipeline0，随后 `bp_pre=0`，持续流停止前进。

## 源码落点

- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv:22-24`
  绑定外部 INT8_MAX opcode。
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/GA_ALU.v:183-185`
  把 INT8 比较输入绑定到 DataA/DataC。
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/GA_PE_Float_CSA.v:41-50,68-72`
  逐 byte 形成 A-C 并据标志选择输入。
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_ALU/GA_PE_Float_Last.v:277-284`
  直接保留 INT8 结果。
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv:527-529,554-557`
  dtype 分类与缺少 INT8 的 pipeline0 ready 方程。

## 聚焦测试

完整 ALU 的四组非相等输入均选择 unsigned max：

| A | C | RTL |
|---|---|---|
| `0ac800ff` | `146401fe` | `14c801ff` |
| `146401fe` | `0ac800ff` | `14c801ff` |
| `8001fe11` | `7f02ff10` | `8002ff11` |
| `01020304` | `05060708` | `05060708` |

pipeline0 测试在 downstream ready=1 时观测到：

```text
INT8 first token:  P0_VALID=1 P0_BP_POST=0 P0_ENABLE=0 P0_CLEAR=0
INT8 second token: IB_MATCHED=1 BP_PRE0=0
INT32 control:     P0_BP_POST=1 P0_ENABLE=1
FP32 control:      P0_BP_POST=1 P0_ENABLE=1 P1_ENABLE=1
```

## 身份

```text
GA_PE_ALU.sv        8a73c66755df0897034d7bdbc7183f663aeba630d16ccae07e8e879d689eb9aa
GA_PE_Inbuffer.sv   25fa4dd2c6fe8301bc3651d660df72059ea2787c0c26a2841a1d4e439586b518
GA_ALU.v            9ccbe59e35f55fca07ba159fb87185c5274de86b15618d781e3c0fec712d94f6
GA_PE_Float_CSA.v   5bcc09111624f403cc2aab291f79fd32a6dd40ce7d9624db6306f8cde94906dc
GA_PE_Float_Last.v  2e90094fd01155c0028ab1a414e7e10e9eaaf8ee46bc8f02af4d6ce9a841efa0
tb_int8_max_csa.sv             3564e7c129941fe10bd9830af22585d770d919bb9d9f8272977411a67db4c122
tb_ga_alu_int8_max.sv          5565c20f859e27c7231eae02c60551edf01d4dfe500c46a9d3224bf4978560b4
tb_ga_pe_inbuffer_pipeline0.sv c63bdf4293debfb2cbc1cca0d5c682e12183b1898fc3a613f288d264412a6395
```

## MaxPool 与封包边界

新 MaxPool 包只能把 numeric polarity 标记为当前源码局部 PASS；动态 flow blocker 保持
开放。包必须只从 GitHub tracked 原 JSON 和可信模型输入 fresh 生成，不得读取此前任何
MaxPool mapping、bitstream、execplan、SCA/SCA_D、测试包或 local-E2 物化资产。
本记录不授权修改 RTL、检查服务器身份、上传或运行。
