# 2026-08-11｜exact-instance / payload-known-width / semantic-fingerprint 主线同步

## 结果

- status：`MAINLINE_EXACT_SYNC_PASS`
- source owner：`019fd276-14c5-7800-94db-87ebfb9ce632`
- target mainline：`019fbec2-fe93-7e03-9314-cff6f222f33d`
- target root：`C:/Users/15383/Desktop/Codex/project/resnet50_int8`
- 三支 next-fresh successor 的共享阻断门已经落到主工作区；current/pending/tested package、plan、RTL/config/numeric/workload 与服务器状态均未修改。

## 同步方式与并行增量保护

三份规则在主工作区 current bytes 上做窄幅语义合并，没有用专项旧快照覆盖主线后续规则。工具、v2 schema、dispatch 和 first-fresh validator 按精确文件同步；registry 与 source-bound tests 显式合并并保留主线后发的：

- `CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001`；
- `PARTIAL_EXIT_LIVE_CAUSAL_RECORD` mechanism；
- native Conv p33b historical negative；
- `first_payload_samples=0`、live-only INT、required plugin disposition 三组回归。

`fixtures/server_source_bound_observer_v1/rtl/demo_pipeline.sv` 已与专项 byte-equal，采用 receipt reuse，未改写。

`.agents/plan.md` 同步前后均为 SHA256 `4f04b3e207a5fd200b6bbc6e66b6c0a312d1e4f24317cd9266d31d2018aecc13`。

## 已发布规则

1. `CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001`
2. `CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001`
3. `CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001`

三门只作用于 next fresh：精确绑定 canonical target/near-miss，以 `boundary_id/canonical_instance/seq` 分组；X/Z、missing、known=false、wrong-width payload 必须 `EVIDENCE_INCOMPLETE`；诊断语义 fingerprint 变化后必须重新执行 typed exact-final-ZIP first-use audit。

## 主工作区回归发现与修复

首次合并回归运行 82 项时，保留下来的
`test_generated_parser_adjudicates_from_live_events_without_final_block` 发现 1 项兼容失败：v2 的内部
`boundary@instance` key 被暴露到 v1 `live_event_count` 外部 JSON。

已在共享 generator 增加 v1 output adapter：

- v2 继续输出 `enabled_boundary_instances`、`boundary@instance` live count 与三元 grouping key；
- v1 恢复历史 `enabled_boundaries` 和 boundary-only `live_event_count`；
- 内部判别仍使用实例键，不放宽 v2 防跨实例聚合语义。

最终同一组回归 `82/82 PASS`，failures=0，errors=0。

## Current exact receipts

- server rule：bytes=`140636`，SHA256=`74ae37513d6bcb763543a7a4583ec1acea3d4b2919f07ab8fab266272bf3cc0b`
- generation index：bytes=`29906`，SHA256=`991740fe543243c1697174fe9c9621af0201469c8bab37c95ea4db12d8276f2c`
- convergence specialized rule：bytes=`18282`，SHA256=`426876da2a299e4e2003f52cd254ff5f8f3fd5b3510a81b1e15fb0d47567ef23`
- source-bound generator：bytes=`97493`，SHA256=`121fa10c6e455667bb9b46ffda59067bd198b0b1840b3f185e283d9178fd7072`
- first-fresh validator：bytes=`23577`，SHA256=`644ba6f360e313dfe527296aca6fbe127cae18661d4bd3854a8b7ae6a5508680`
- plan v2 schema：SHA256=`16989a65cf2c2a8ff3058aa499f947b53731fb5a2094cb8061209520cb581343`
- decision v2 schema：SHA256=`87e3821722bf8ea29d73748dab7074f37aa4d293e0f8f7f90d59d5aed091b694`
- generation report v2 schema：SHA256=`dceacf50bae9e432f30c3c24da7099ba8e810fbc9f477a977b3d2816aaaf1906`
- final-ZIP validation v2 schema：SHA256=`6eff97aadc1f5c3529b1161fad916b5d43a193b94c705382d0da11466fdc8a8a`
- merged mechanism registry：bytes=`7901`，SHA256=`8f28928a332b79c79311ffa346737f0a054b13bc262d9c6c2ce5f2b8a5e1cf9c`
- merged source-bound tests：bytes=`28818`，SHA256=`1e48ae3253f8a6888aa46ef0de42d6b90499c5e5ab8ff75a5f61197cb93ce918`

完整 18 项 path/bytes/SHA 收据见 machine report：

- `artifacts/operator_config_validation/r5-whole-network-test-convergence-optimizer-v1/diagnostic_exact_instance_payload_semantics_v2/mainline_sync_report.json`
- bytes=`6889`
- SHA256=`bab66d941995d2bbb2f872936ba5934c781677cde5884f2e9bcb92f765270662`

## 验证

执行：

`python -m unittest tests.test_server_source_bound_observer tests.test_server_first_fresh_extra_audit tests.test_server_package_pipeline tests.test_server_triggered_causal_observability`

结果：`82/82 PASS`。18 项 report receipt recheck PASS，JSON parse PASS，scoped `git diff --check` PASS。

## Claim boundary

本记录只证明主工作区本地规则、生成器、schema、contract、tests 的同步与共享回归。没有生成或重建 package，没有服务器动作，也不声称 DUT compile/simulation、natural terminal、正式 D、runtime-D absent、E4/E5 或性能结果。
