# 2026-07-29 算子族任务进度同步与重新规划

## 主线事实

- 用户指定本对话为唯一主线控制面；后续算子包生成和 return 分析继续派发到既有算子族或人工 JSON 任务。
- 硬件组报告历史问题 1/3/4 已修补，2/5/6/7/8 判断为非当前必需缺陷。主线按硬件语义可用、服务器可编译继续本地工作，但未绑定最终 `Trassic2.0_RTL` commit，也未把该假设计为 E4/E5。
- node0004 fresh 完整 QLinearConv 包已经生成：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v1.zip`，
  SHA-256=`335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989`，
  状态=`PACKAGE_READY_NOT_RUN`。
- node0004 完整 W3 本地闭合：3,211,264 outputs、51,380,224 dot4 groups，
  accumulate mismatch=0、tail mismatch=0；包内 320/320 readback dry-run 通过。
- 当前没有经主线验收的服务器 compile/return 日志；`.git/FETCH_HEAD: Permission denied`
  只分类为 Git 仓库写权限问题。

## 分发计划

- Conv/SA：唯一负责 node0004 return 分析；并行准备其余 52 Conv 的 schedule signature 扩展清单。
- Requant：复用其他 52 Conv 的分类，建立 tail signature binding；不重复 node0004 包。
- QLinearAdd：从 17/17 SUM_F32 接共享 tail，先闭合一个完整代表节点。
- GAP：复用六级 sum tree，完成 node0071 UINT8 tail 和完整本地 E2。
- Dequant/Flatten/Quantize：共同闭合 node0072-D→node0073 alias→node0074-A endpoint；不复测 node0072/View。
- MaxPool：只保留 Git 原始 JSON 复用，不修改、不复测、不消费历史物化资产。
- 人工 JSON：冻结，等待用户提供新 JSON 或新 return。

所有新包只允许生成到 `PACKAGE_READY_NOT_RUN`；不得上传、运行、检查服务器身份或自行取得 lease。

## 控制面身份

- `.agents/plan.md` SHA-256：
  `f9a3ce73baa73346c144f14bf005262f0b0caaf66d981da157a5a11c0a703183`
- `.agents/rules/生成前必读索引.md` SHA-256：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/算子配置规则.md` SHA-256：
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/INT8_SA点积专项规则.md` SHA-256：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/精确UINT8量化尾专项规则.md` SHA-256：
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- `.agents/rules/服务器测试包生成规则.md` SHA-256：
  `72f22cc21e328eb06a841418a39640a924de0c533e6d0ac6d8822dfd0771d524`

