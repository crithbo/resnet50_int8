# 隔离编译 observer include 公共规则同步

日期：2026-07-25

Requant node0001 E4 v1 的 VCS 编译失败证明：仅把
`native_return_observer.svh` 安装到 NDP 根目录并确认该目录存在，不足以保证从隔离
`RUN_DIR` 启动的 VCS 能解析相对 `` `include ``。

公共 `.agents/rules/服务器测试包生成规则.md` 第 6 节已增加最小通用约束：

- 从隔离 `RUN_DIR` 编译相对 `` `include `` 时，必须显式传入 include 目录；
- compile 前必须核验目标文件可读；
- 目标文件 SHA-256 必须与安装收据一致；
- 只确认项目根目录存在不能通过此门。

更新后规则身份：

```text
path = .agents/rules/服务器测试包生成规则.md
size_bytes = 10787
sha256 = cb101e1aedf8f1d7516bb7f120badb120d2efbf8316223d39990c383c10e95ea
```

Requant E4 v2 在该规则更新前已经以全新身份生成，其实现已包含显式 `+incdir`、
precompile observer 可读/字节身份门和独立 compile driver 日志。v2 的原始生成收据
保持其真实生成时点所读旧规则 SHA，不得事后改写成新 SHA；用户明确要求后续生成读取
收据采用新 SHA。冻结 v2 ZIP/sidecar 不修改，E4 仍未运行，E5 仍禁止。

本次只更新公共规则与记录，不修改任何 `rtl/` 文件。
