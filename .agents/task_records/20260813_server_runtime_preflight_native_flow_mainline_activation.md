# Server runtime preflight native-flow mainline activation

日期：2026-08-13
activation epoch：`runtime-preflight-native-flow-v1`

## 上一版本进度

主线已经撤销 compile module provider closure/短探针的 current blocking 权限，但尚未把用户要求的
“真实 production 命令先行”落实为 exact final-ZIP gate，也未统一正式失败后的原生 ndp-sim 差分入口。

## 本版本目的与结果

在保留 current observer-only、post-sim、one-shot TB VCD 与其它并行规则的前提下，主线窄幅激活：

- `runtime_preflight_noninterference_final_zip`：扫描 exact runner 唯一 production launch 标记之前的
  文件/目录/tool/library/provider existence、Make dry-run、lookup probe 与独立 attestation 逃逸；
- runner arm partial-return finalizer 后直接执行真实 production cd/install/compile/sim；
- environment 只由 actual cwd/argv/log/exit 裁决；
- 正式失败后必须执行原生 ndp-sim differential，未知 server loader/start/wait/readback 保持 UNKNOWN；
- 历史 provider tool/schema/report 只允许失败后只读诊断，不进入 runner、final ZIP、first-fresh 或 family HOLD。

## 边界

本次只同步共享 tool/schema/dispatch/fixtures/tests/report/task record，并窄幅更新规则、README 与 build gate
registry。没有修改、重建、旋转或 HOLD current/pending/tested/superseded package；没有服务器、RTL、
config、numeric 或 workload 动作。
