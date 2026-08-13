# ResNet50 INT8

本仓库用于把 ResNet50 INT8 模型物化为 28-slice NDP 配置、执行计划、服务器测试包与
可复验的回传证据。根目录只保留这一份项目级说明；活动状态、生成规则和历史记录分别由
`.agents` 下的唯一入口维护。

## 稳定入口

- 项目边界与协作方式：`.agents/agent.md`
- 当前状态与短期计划：`.agents/plan.md`
- 生成前规则路由：`.agents/rules/生成前必读索引.md`
- 已完成任务收据：`.agents/task_records/`
- 被取代状态与旧说明：`.agents/history.md`、`.agents/history/`、`.agents/archive/`

不要从历史测试包、旧报告或归档说明推断当前可运行身份；以 `plan.md` 和磁盘 current
收据为准。

## 恢复环境

需要 Python 3、Git，以及相关外部仓库的读取权限。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-resnet50.lock.txt
.\.venv\Scripts\python.exe bootstrap.py
```

`bootstrap.py` 按 `repos.lock.json` 的完整提交恢复并验证 `CGRA_SIM`、`ndp-sim-ref`、
`NDPFuncModel`、`ndp-sim` 和独立 Git checkout `Trassic2.0_RTL`。只验证已有 checkout：

```powershell
.\.venv\Scripts\python.exe tools\sync_repositories.py verify
```

大型 W3 tensor/golden 不进入 Git。只有新机器确实缺失时，才按 `.agents/agent.md`
当前要求生成；已有产物不得与新结果混写。

## 目录

- `configs/`：已物化配置和冻结实例
- `contracts/`：机器合同、typed request 与身份收据
- `resnet50_pipeline/`：项目 lowering、materializer 与验证逻辑
- `tools/`：构建、审计、回传分析和仓库恢复入口
- `tests/`：本地回归与定向 RTL/合同测试
- `artifacts/`、`outputs/`、`server_returns/`：生成物与回传证据
- `Trassic2.0_RTL/`：直接跟踪 GitHub `master` 的独立 Git checkout
- `NDP_copy01/`：本地硬件仿真入口；其中 `rtl/` 由 current Trassic checkout 精确同步，
  不保留 `rtl_pre_*` 副本
- `ndp-sim/`：活动原生工具链；`ndp-sim-ref/` 仅作规则授权下的冻结参考

根目录的 `conv_full.json`、`conv_1x1_real.json` 和 `conv_full.txt` 是被代码、合同与测试
直接引用的配置/伪代码输入，不是重复的项目说明文件。

## 基本纪律

- 工作树长期 dirty；禁止用 reset、checkout 或 clean 清除既有成果。
- 默认不得修改功能 RTL；必须取得用户本轮明确授权。
- 本地 E0/E1/E2、结构 valid 或自然完成不能替代正式 E4/E5。
- 服务器上传、运行、lease、提交或推送只在用户明确要求后执行。
- 新实验使用 fresh identity；冻结包和原始回传不覆盖。

完整本地测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

具体任务应先读取生成前索引，再只运行目标 family 对应的定向验证；不要以整库回归替代
专项数值门、服务器正式回读或 production RTL 身份核验。
