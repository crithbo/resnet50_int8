# 全网三方主线 plan 重写记录

日期：2026-07-25

## 结论

`.agents/plan.md` 已改为面向真实 ResNet50 节点与整网的三方闭环主线：

```text
ONNX/W3 golden ↔ config-bound simulator ↔ stock-RTL hardware
```

`CGRA_SIM` 保留为旧 ResNet/QNN 算式参考；只有消费当前最终 JSON、布局与码流的
`NDPFuncModel` 或等价执行器，才能承担配置绑定 simulator 一侧。DeepSeek 已验证 JSON
继续作为生成 ResNet 规则的硬件 oracle，不作为独立交付目标。

## 保留的整体进度

- ONNX 独立软件公式：78/78；
- typed hardware request：133/133；
- hardware stage family：10；
- 精确局部 JSON candidate：2/133；
- 正式 target config：0/133；
- 正式服务器 E4/E5：0/0；
- 正式 ResNet 节点三方闭环：0/78；
- Requant：54/54 W3 数值分类，33 项当前 guard 数值兼容、21 项被反证，
  仅 node0001 完成物理 E2；
- Dequant、Requant 首次动态失败分类、GAP/repair 冻结和全部既有 blocker 均保留。

## 新执行顺序

1. 补 node0001 的 config-bound simulator 中间腿与三方报告模板；
2. 从合同重建 guard-only、round-only、single-occurrence-two-stage、
   alias-lifetime 四个诊断性原子动态合同；
3. 完成 node0001 全量三方 E4/E5；
4. 参数化生成器并完成四类 zero-point-zero shape holdout 物理 E2；
5. 用 DeepSeek 可信 `quant_from_buffer`/`add` 关闭真实 ResNet
   QuantizeLinear/QLinearAdd 代表；
6. 关闭 Conv/MatMul 的 SA、bias/psum、tail 及其余 family；
7. 按 residual block、ResNet stage、head、整网逐级组合，完成 78 节点、
   93 runtime edge、133 hardware stage 的逐层三方比较。

原子动态合同只负责定位硬件子路径，shape holdout 只负责证明规则可推广；
两者都不得冒充真实节点 E4/E5 或整网三方通过。服务器包生成和回传分析继续交由
“测试修复”会话；本任务未生成服务器包。

## 物化与验证

- `plan.md`：178 行；
- 重写前 SHA-256：
  `552eba8b19dfc5ada39283f79c4ee105c24241938b83de8182ed0061b9db2bcb`；
- 重写后 SHA-256：
  `856f5b825990503690e10ef901461fab1da872e17114c248f3fcfac19215386c`；
- Requant family、stage backend/system、GAP D-index、derivation matrix、
  lifecycle、local closure、project closure 已按依赖顺序重建；
- project closure 保持 78 nodes、133 hardware ops、93 runtime edges、
  2 candidates、0 formal target、0 E4、0 E5、18 blockers；
- 74 项相关回归通过；此前 15 项 plan/必读压缩定向测试也通过；
- `NDP_copy01/rtl/` 无改动；未生成或修改服务器测试包。
