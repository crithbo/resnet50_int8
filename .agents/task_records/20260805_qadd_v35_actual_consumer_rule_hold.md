# 2026-08-05 QLinearAdd v35 actual-consumer rule hold

## 主线裁决

- owner：`019fa2c0-b647-7a91-93bf-d21a173487e3`
- mainline：`019fbec2-fe93-7e03-9314-cff6f222f33d`
- exact package：
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_crow32_v35.zip`
- bytes：`26180881`
- SHA256：`45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829`
- status：
  `PACKAGE_HELD_ACTUAL_CONSUMER_REVALIDATION_REQUIRED`
- package bytes modified：`false`
- server action：`false`

## 已接受的功能配置裁决

v29 已把 FP32-add 首个动态停点唯一化为 Buffer0/2 输入事务供应不守恒：
每个 operand 只有一笔16B accepted write，而 ARM mask要求完整32B row。v35已在同一行
物化 `[0,16)+[16,32)=[0,32)`，transaction=32、inner LC=9408，且保持
每slice `8×9408×32=2,408,448 B`。该配置修正与既有 rowpair、runner、TERM、
path-budget、deterministic build 门不因本 hold 撤销。

## Hold 原因

current server rule SHA256：
`5f1369c4af431baaf74044a004a3383860a9d279561712616fb19e745465c7f9`
已包含：
`CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`。

v35 final audit：

- path：
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-server-package/final_zip_self_audit.json`
- bytes：`76192`
- SHA256：
  `b4d6f11b204c613cb12a04ace2da1dcc17a430eb15b19d4ee78cee2941a3a110`

现有 HDL receipt：

- path：
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-fp32-rowpair-v35-server-package/hdl_scope_revalidation.json`
- bytes：`2474`
- SHA256：
  `cea2f15dd2a8f9f2619259608b5fd21c2917efd10f11c7cc54bece99b59428ee`

该 receipt 有 declaration/use/update closure与三类负控，但未发布新增规则要求的：

- exact final compiled HDL actual-consumer expression 枚举；
- consumer expression总数；
- 逐表达式或机器等价类 coverage；
- uncovered=`0`；
- misspell负控的真实member/source-span/expression SHA与变异token来源。

仅在 `current_rule_receipts` 记录新server-rule SHA，不能替代执行新增门。因此主线不能直接
把v35排入服务器运行队列。

## 解锁条件

owner 对同一exact ZIP做包外只读复验：

1. 从fresh extract后实际include/concatenation顺序推导范围内actual consumers；
2. 发布完整coverage与uncovered=`0`；
3. 拼写负控源于真实compiled source span并重跑同一frontend/semantic closure；
4. 若package bytes无需变化，保存
   `RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS`并恢复`PACKAGE_READY_NOT_RUN`；
5. 若必须修改package-local HDL、runner或运行依赖，隔离v35并生成fresh identity。

本hold不要求full-design production elaboration，不新增服务器侧检查，不撤销v35的
32B transaction修正；它只阻止缺少current本地放行收据的包占用服务器。

