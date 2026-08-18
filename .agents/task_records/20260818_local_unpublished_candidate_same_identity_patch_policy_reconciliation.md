# 本地未发布候选原 identity 定点修补策略校正

## 裁决

- classification: `USER_SUPERSEDING_LOCAL_UNPUBLISHED_CANDIDATE_PATCH_POLICY`
- public rule delta: 无新增同义规则 ID；窄幅澄清现有服务器构包、聚合预检、规则漂移与收据复用语义。
- superseded statement: `release-cross-member-temporal-consistency-v1` 激活收据中“任何 preactivation frozen ZIP 失败都必须新 identity”的绝对表述。
- retained immutability: managed、published、tested、superseded、server-run、authoritative handoff 或 formal-return-bound 包继续 byte-immutable，仍必须 fresh successor。

## 严格准入

只有同时为 local-only、从未 managed/published、从未 server run、从未 authoritative release handoff、未绑定 formal return 的候选，才可按 `LOCAL_UNPUBLISHED_CANDIDATE_PATCH` 在原 package identity 下定点修补/re-ZIP。必须保留 prepatch tree/ZIP bytes+SHA、逐文件 added/removed/modified/unchanged exact delta，并证明 config、functional RTL、workload、numeric、golden、causal cone 冻结。

旧 final-ZIP、final conjunction 与 ready/release claim 收据全部失效。`receipt_reuse_allowed=false` 或任何 exact dependency 变化的门必须重跑；只有 `receipt_reuse_allowed=true` 且 inputs/validator/schema/authority/dependency receipts byte-equal 的门可复用。补丁完成后只运行一次 `final_zip_release_driver` 聚合门。

## 当前候选处置

- QAdd v80：主线已裁决为 local unpublished/in-progress，可按上述边界保留同一 identity 定点修补；本记录没有修改其 ZIP。
- serialized v106：尚无 ZIP，可在同一 identity 下继续构建；本记录没有创建或修改其包。

## 当前共享身份

- `.agents/rules/服务器测试包生成规则.md`: bytes 203949, SHA-256 `7d7dbe6e92f60893d461c615622598740ca09f9a3fca10b01e18d950d0f64ec7`
- `.agents/rules/生成前必读索引.md`: bytes 15503, SHA-256 `f17b6ef7e4762ee1bd7b209c4f3a4a0d7b285fafdf1fb2fa5bbca2c6c37bef04`
- `contracts/server_release_consistency_dispatch_v1.json`: bytes 3975, SHA-256 `9d034affc4804e03734077182dfdfd3e8159ca05659b6baf424e48394afe8793`
- `tests/test_server_release_consistency.py`: bytes 17596, SHA-256 `4b6215bad67e2eab24c3578fa02df93f7cff34e88a1034ae9818ef7a5ae29641`
- `contracts/active_rule_registry_v1.json`: bytes 9979, SHA-256 `b6b5985dd6088539c4ab1fa7183c563db2691c89401344ccd22e950e4a08eeac`
- `contracts/server_package_build_gate_registry_v1.json`: bytes 26628, SHA-256 `02fcdb57376bd0d75139639eb54448edd45e4a5bd7c66bda885ab7d53c427937`

## 验证

- focused release consistency: 12/12 PASS。
- related QAdd/TB-VCD/observer/family-binding/package pipeline suites: 180/180 PASS。
- additional runtime/return/layout/first-fresh suites: 142/142 PASS，2 个既有环境 skip，0 fail。
- active-rule audit: 14/14 active，164 definitions，0 duplicate/error/warning。
- py_compile、JSON parse、changed tracked-file diff-check: PASS。

## 边界

未修改任何 family package、managed storage、plan、owner registry、server、functional RTL、config、workload、numeric 或 golden；未授权上传、租约、连接或运行。
