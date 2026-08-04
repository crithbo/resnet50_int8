# ADR-017：133-stage typed lowering 与显式服务器协议交接

- 日期：2026-07-23
- 状态：accepted

## 决策

R5 的逻辑参数审计不再只停留在一份大合同中。`contracts/resnet50_r5_lowering_bundle.json` 将冻结模型的 133 个 hardware stage 转成顺序稳定、可独立校验的 typed lowering request。每个 request 必须携带：

- node/stage/hw-op 身份和拓扑序号；
- 前驱 stage、逻辑 geometry、输入输出 tensor identity；
- 参数 dtype、shape、axis、精确值或值哈希及 provenance；
- 6144-row 目标 profile 与 `resnet50-ndp-toolchain-6144-v1` 补丁身份；
- 每个 field requirement、未解决 blocker、正式输出许可和 request SHA-256。

完整 request 不等于正式 target config。当前全部 133 项的 typed payload 完整，但没有一项通过所有硬件语义门，所以正式 emission 仍为 0/133；生成器必须 fail closed。

真实服务器入口采用 `resnet50-server-execution-protocol-v1`。协议必须由用户提供并批准，精确包含 load、start、wait、readback 四阶段 argv、cwd、timeout，以及服务器 RTL repository/commit/filelist SHA-256 和全部必返路径。项目不从历史日志、README 或旧 runner 猜命令。

`tools/run_e4e5_server_protocol.py` 只按协议中的 argv 以 `shell=False` 执行，保存：

- 四阶段 stdout/stderr 和退出码；
- 协议与 RTL 身份；
- 包执行前后逐文件哈希；
- 原始返回文件树和 run1/run2 身份。

未批准的 `contracts/server_execution_protocol.template.json` 故意不可执行。模板占位符、错误阶段顺序、路径逃逸、缺返回项或不完整 RTL 身份均必须拒绝。

## E4/E5 边界

`contracts/resnet50_e4e5_handoff_readiness.json` 为 10 种 hardware stage 各选择一个代表。只有正式 target package 已生成时才允许进入 E4。E4 run1 必须自然完成并用独立 W3/subop golden 比较原始回读；E5 run2 必须复用相同包、RTL 和协议，再证明结果与环境回执稳定并覆盖该族边界语义。

当前 ready package 为 0/10、E4=0、E5=0。这是可执行交接链已经准备好但上游正式配置和用户服务器协议仍缺失的状态，不能写成服务器已通过。
