# Complete-JSON 九族后续规则反馈裁决

日期：2026-08-06

## Flatten / View

裁决：接受真实非同义族规则漂移并窄幅合入。

current route：

```text
node0071 D: uint8[16,2048,1,1]
  -> node0073 Flatten/View
node0075 A: uint8[16,2048]
```

- element count=`32768`，byte span=`32768`；
- offset=`0`；
- byte strides：
  `[2048,1,1,1] -> [2048,1]`；
- metadata-only、storage identity与静态address已闭合；
- accepted producer-before-consumer lifetime、actual reads、natural terminal与formal D
  继续为动态门。

旧FP32 `node0072D→node0074A`、131072B route保留为off-path历史证据，不作为current
storage/lifetime权威。旧静态allocation/offset blocker已由动态门取代。

族规则：

- `.agents/rules/Flatten_View算子配置规则.md`
- SHA256:
  `f5c5ffbefb1e2515f0676fc5134bfeaf8ee1455562638f615a94e0fa598bc005`

## QLinearAdd

裁决：不新增
`CDA-QADD-COMPLETE-STRICT-COMPOSITE-TYPED-HANDLER-001`。

原因：现有QAdd six-qparam、stage0、broadcast、readiness及exact-tail规则已经覆盖目标
语义；本轮`BLOCKED`反映typed composite handler实现能力缺口，不是新的规则语义缺口。

## MaxPool

裁决：不改变数值规则，派owner修工具/收据一致性。

1. `OperatorConfigValidator`必须把GA INT8 MAX分层为：
   - numeric=`CDA-GA-INT8-MAX-NUMERIC-001 / LOCAL_SOURCE_PASS`；
   - pipeline=`CDA-GA-INT8-MAX-PIPE-001 / CONTRADICTED`。
   不得继续以旧unsigned-min事实把pipeline失败冒充numeric失败。
2. 只读绑定current/cloud权威`RD_Data_Channel` padding substitution equation并刷新
   legacy padding contract的RTL SHA receipt；不改functional RTL或padding数值语义。
3. MaxPool candidate、current diff与用户deferred状态保持；禁止构包/server动作。

## 公共边界

- 本轮未生成mapping、bitstream、execplan、SCA或服务器测试包。
- 未上传、运行或获取lease。
- View静态规则更新、QAdd不新增规则与MaxPool工具修复均不提升E3/E4/E5。
