# Server runtime preflight non-interference / native-flow reassertion v1

日期：2026-08-13  
owner：`optimizer.whole-network`  
状态：`READY_FOR_MAINLINE_NARROW_MERGE`

## 用户裁决

服务器端不要检查文件、目录、module provider、library 或工具是否存在；能运行即可。runner 在
arm partial-return finalizer 后直接执行 production command，以真实 cwd/argv/log/exit 裁决环境。
如果真实运行失败，先回看这些包所衍生的学长学姐原生 `ndp-sim` 路径，不得通过猜测服务器
目录或新增短探针代替真实运行。

## 审计结论

现有 `CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001` 本来已经禁止无关服务器
源码树检查，但随后激活的 `CDA-SERVER-COMPILE-MODULE-PROVIDER-CLOSURE-001` 又要求 provider
聚合、Make dry-run 和 module lookup probe，形成语义回退。该规则与
`compile_environment_attestation` 必须退出 current blocking；其 tool/schema/report 仅作为正式
compile 失败后的历史/只读诊断资产保留。

原生路径核对确认：仓库明确没有保存完整 server loader/start/wait/readback 命令，禁止猜测；已验证
链路是 native graph → `model_execplan/main.py` → bitstream/address/execplan/SCA → package，再由活动
Make/TB 运行。最有价值的失败差分包括 cwd、`../model_execplan/main.py`、明确的 regenerated-op 日志、
真实 bitstream、同包 `SCA_CFG/SCA_CFG_D`、TB path echo、`Repeat_Num` 和 actual consumer path。

## 实现

- 窄幅更新服务器包规则、生成前索引、整网优化规则和硬件仿真入口 README；
- 新增 `runtime_preflight_noninterference_final_zip`，只扫描 exact runner 的唯一
  `# CODEX_PRODUCTION_LAUNCH` 之前部分；
- 一次聚合 `test/stat/find/hash/git/command -v`、Make dry-run、provider probe 和独立 preflight
  subcommand；production launch 后的 return collection 文件判断不受影响；
- 新增 machine-readable native failure differential：`SAME/PACKAGE_DERIVATION/`
  `NATIVE_DOCUMENT_IMPLEMENTATION_DRIFT/SERVER_RUNTIME_UNKNOWN`；UNKNOWN 禁止猜测和转化为 preflight。

## 验证

使用 canonical `.venv`：

```text
python -m unittest tests.test_server_runtime_preflight_native_flow tests.test_server_package_pipeline -v
22 tests PASS
python -m py_compile tools/validate_server_runtime_preflight_native_flow.py
PASS
git diff --check -- <changed exact set>
PASS
```

机器报告：`outputs/server_runtime_preflight_native_flow_v1/report.json`。

## 边界

仅 local rule/tool。未修改 current/pending/tested/superseded package，未生成包，未上传、运行或取
lease，未修改 RTL/config/numeric/workload/plan。规则文件来自较旧专项 worktree，主线必须按报告中的
canonical baseline 做窄幅语义合并，禁止整文件覆盖并行增量。
