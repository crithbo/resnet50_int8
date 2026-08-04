# Conv stem typed materializer/registry 窄授权

日期：2026-07-29

## 用户授权来源

用户要求本地主线按硬件可用假设继续推进整网、由主线直接下发必要的算子包生成与返回
分析工作，并允许本地执行到测试包生成。该持续授权覆盖为真实 ResNet Conv 补齐缺失的
项目工具 handler，但不授权修改功能 RTL、活动上游 checkout 或服务器文件。

## 已验收前置证据

- target：`r5:hwop-0001-00`，ResNet stem 7×7/stride2/pad3；
- one-product-lane + DataC psum symbolic schedule、容量和 D coverage 方程已闭合；
- 64 个 slice-region，每区 8,238,400B，小于 25,165,824B；
- 当前首阻塞为 `B_CONV_STEM_TYPED_MATERIALIZER_AND_HANDLER`，不是算术、容量或
  Requant tail；
- 活动 generator/layout/registry 只批准1×1/3×3或node0004固定尺寸，不能借用
  node0004 identity 生成 stem。

## 授权范围

允许 Conv/SA owner：

1. 在 `resnet50_pipeline/ndp_patch_toolchain.py` 中增加唯一
   `r5:hwop-0001-00` stem patchset/handler registry identity；
2. 只在 hash-bound 隔离 ndp-sim 副本安装 patchset，活动 `ndp-sim` checkout 保持只读；
3. 新增本族 `conv_stem_*` generator、packer、validator、config、contract、artifact、
   tests 与 task record；
4. 生成 stem target JSON、mapping、bitstream、execplan/SCA、address/lifetime 和
   config-bound local E2；
5. 只读消费已接受 `r5:hwop-0001-01` Requant tail；禁止重复其数值分类或复制
   node0004 multiplier/常量。

当前授权 preimage：

- `resnet50_pipeline/ndp_patch_toolchain.py`
  SHA-256=`05af9d7cf6efc9aef22f134c858a09a6cca498d62573766fe97a4f0cecf069f0`
- `tools/generate_conv_instance.py`
  SHA-256=`fc6524b430a204cd7659a0d6a51b21f24582dd6765cdf9ff1dacbfaeb56df43a`
- `resnet50_pipeline/conv28_layout.py`
  SHA-256=`28ebc5eda3ec07e7b1e2dcf59d249f0ae97cd6e0058a8862de05fc96f76f1924`

任一 preimage 漂移时必须重新读取、报告差异并 fail closed，不得机械套用 patch。

## 禁止项

- 不得修改 `rtl/**`；
- 不得修改 `.agents/plan.md` 或公共规则；
- 不得借用 node0004 op identity、固定 A/B/D size、常量、地址或 package；
- 不得实现第二套 graph parser/address planner/execplan generator；
- node0004 v2 未取得有效动态结果前不得生成 stem 服务器包；
- 不得检查、上传或运行服务器。

## 控制面

- `.agents/plan.md` SHA-256：
  `c19363826061ac6842f1946a1fd860d87917902f3fad199d589a739ab0003b03`
- PACKAGE_RELEASE：`NONE`

