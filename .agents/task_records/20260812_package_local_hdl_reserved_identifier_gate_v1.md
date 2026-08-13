# 2026-08-12 package-local HDL 保留字声明名共享硬门

状态：`LOCAL_SHARED_HARD_GATE_READY_AWAIT_MAINLINE_SYNC_AND_THREE_FAMILY_DISPATCH`

## 结论

serialized Conv FSDB smoke s1 的首次真实失败不是 FSDB、DUT、配置、数值、workload 或
功能 RTL 问题，而是 package-local probe 使用了 `integer sequence;`。`sequence` 是
SystemVerilog 保留字，production compile 在 simulation 前退出。

现有 `CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001` 已要求 fresh
exact final ZIP 的 HDL frontend syntax/scope/state 正控，因此裁决为
`IMPLEMENTATION_ESCAPE_EXISTING_RULE_SEMANTICS`，不新增同义 CDA 规则。缺失的是低成本、
可复用且能在昂贵压缩前阻断的共享实现。

## 实现

- 新增 `tools/validate_server_package_local_hdl_lexical.py`：
  - `--tree` 在 staging package root 扫描全部 `.sv/.svh/.v/.vh`，一次聚合全部错误；
  - `--zip` 从 exact final ZIP bytes 独立重算；
  - 排除注释、字符串、合法 escaped identifier；
  - 拒绝保留字被用作普通 data/port/named-construct declaration identifier；
  - ZIP 入口同时 fail closed 于 duplicate/unsafe/symlink/multiple-root；
  - 输出 exact member bytes/SHA、输入 identity 和完整 violation 列表。
- 新增 schema、dispatch contract 和 9 个 focused tests。
- 在服务器包规则、生成前索引和共享 build-gate registry 中把 staging 廉价聚合与 final-ZIP
  重算明确映射到 `server_start`；完整 frontend/scope/state/负控仍为强制合取，lexical scan
  不替代编译前端。

## 真实正负控

- s1 exact ZIP SHA `33f8ec3d0216213684612e129c7a56f49f1bb6a735b08d474bc158025a69c0ed`：
  exit 1，精确命中 1 个 `sequence`；report
  `outputs/package_local_hdl_lexical_gate_v1/s1_negative.json` SHA
  `bee3fe2fa70d8ae0ac56870f3770f5181e87b16323f9c965b6b1093e29eda110`。
- s2 exact ZIP SHA `f9bd28497597af0f395872c9a34bce597bb18b744eeace98476f1de70fe0ccde`：
  exit 0，violations=0；report SHA
  `bbeda1d01356350dc9b95eb7559a9d0afa67a48af85e288b265009d96d63d2fa`。
- 当前 s3 exact ZIP SHA `bdcc9b52ec850211a496936870edd85f4aa965082623b5e11bf9a390669743be`：
  只读 exit 0，violations=0；report SHA
  `b5e6e019bbe774c6840ca7ea7eff4acbf961baa2caccf467105717c8f118d2ad`；未修改或轮转该包。

## 验证

- `py_compile`：PASS。
- `python -m unittest tests.test_server_package_local_hdl_lexical`：9/9 PASS。
- schema/dispatch/registry JSON load：PASS。
- scoped `git diff --check`：PASS。
- 当前 bundled Python 缺少 `jsonschema`，因此 `tests.test_server_package_pipeline` 在 import
  依赖处未执行；这不是门失败。mainline 同步时必须在其 current configured environment 跑完整
  shared regression 后才能激活和派发。

## 派发合同

主线完成窄幅语义同步、current regression、registry/plan 更新后，按用户最新指令显式取代
旧的“等待 serialized smoke 两次服务器 return 才允许构包”的 **build-only hold**，同时派发：

1. `family.gap` / `019ff02d-8225-7d21-9779-e46ce4130572`；
2. `family.conv.native` / `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`；
3. `family.qlinearadd` / `019ff02d-9e93-7d61-8c98-c928fdea157c`。

三族只允许本地生成 next-fresh FSDB successor。每个 exact final ZIP 必须通过本门和 current
FSDB-v3、first-fresh、完整 HDL frontend、final-ZIP、runtime/return、storage gates 后才可标记
`PACKAGE_READY_NOT_RUN`。上传、运行和 lease 仍由用户完成；不授权修改 functional RTL、ISA、
active ndp-sim、配置、数值或 workload。QAdd 还必须关闭已知 manifest `install_name` 与 SCA
namespace identity 差异。

## Machine report

`outputs/whole_network_package_local_hdl_lexical_gate_v1/report.json`，bytes=6137，SHA256=
`69213226270ecd44dbc3a1f979d7e46fad99bcfe1e74db8357b42734c319d0a7`。

`RULE_CONFIRMATION`：现有 package-local HDL syntax/scope 规则语义正确；本轮补齐的是共享执行门。
`RULE_DELTA_PROPOSAL=NONE`。

