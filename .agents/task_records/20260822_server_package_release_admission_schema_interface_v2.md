# Server package release-admission contract/result schema interface v2

## 裁决

- role: `optimizer.whole-network`, owner epoch 5；消费 current registry epoch 48。
- p57 正式 return 只证明 VCS license 连接失败后 external INT；compile=125，simulation/target 未开始，不能裁决 DUT/config/RTL。
- p58 保持 config、RTL、workload、causal cone，只改 runner/return；本专项未修改 p58。
- shared blocker 分类为 `IMPLEMENTATION_ESCAPE`：`tools/validate_server_package_release_admission.py` 把 companion contract 交给了 pipeline admission-result schema，jsonschema 正确地报出 10 个 shape errors。现有 `CDA-SERVER-CAUSAL-RELEASE-ADMISSION-001`、`CDA-SERVER-PACKAGE-LOCAL-HDL-001` 与 `CDA-SERVER-RUNNER-REPEAT-SAFE-001` 已语义覆盖，不新增或修改 public rule。

## 实现

- 新增独立 contract schema：`schemas/server_package_release_admission_contract_v1.schema.json`。
- 保留 `schemas/server_package_release_admission_v1.schema.json` 为 pipeline result schema，字节不变。
- companion validator 改为只用 contract schema 校验输入；`jsonschema` 缺失/skip/schema failure 仍 fail closed。
- dispatch 明确绑定 `contract_schema` 与 `result_schema`，并登记 p58 历史反例。
- 新增正负控，永久拒绝 contract/result schema 再混用；无 family exemption。

## 验证

- focused release-admission/result-entry：23/23 PASS。
- admission + result-entry + pipeline + first-fresh + incident：63/63 PASS。
- exact p58 contract/staging/final-ZIP 只读 replay：PASS，errors=0。
- incident adjudication schema：PASS，分类 `IMPLEMENTATION_ESCAPE`。

权威机器报告：`outputs/server_package_release_admission_schema_interface_v2/report.json`。

## 同步与边界

主线应机械同步 report 中 `changed_assets`、machine receipts 和本记录，不覆盖并行增量；无需 public rule delta 或 family-specific exemption。canonical 复验后通知 persistent native owner 只重跑 p58 shared admission 并按 standing auto-pending policy 继续；不得重建 p58 或重跑 p57。

未修改 family package、storage、plan、owner registry、functional RTL、config/numeric/workload 或 model setting；未执行服务器、上传、lease；不声称 natural terminal、Formal-D、E3/E4/E5。
