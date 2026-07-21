# `.agents` 文档归档索引

最后更新：2026-07-18

本目录保存已经完成、被后续证据替代或仅在追溯时需要的 Markdown 文档。归档文档记录的是形成当时的事实，不是当前执行命令；当前状态始终以 `.agents/plan.md` 为准，稳定入口与长期边界以 `.agents/agent.md` 为准。

## 分类

| 目录 | 内容 | 使用方式 |
|---|---|---|
| `server-simulation/v1-v4/` | 首个 Conv 的 v1～v4 服务器错误报告、深度诊断、重跑说明和交付记录 | 仅在追溯旧运输、scratch、route 或早期 testbench 问题时读取 |
| `milestones/w4/` | W4 方案切换、裁决、事故和闭环索引 | 仅在追溯 W4/ADR 背景时读取 |
| `engineering-lessons/` | 可复用但不承担当前项目状态的工程经验 | 按问题需要读取，不能覆盖当前规则 |

## 仍在归档目录之外的文档

- `.agents/plan.md`：唯一动态接手入口。
- `.agents/agent.md`：项目总览、稳定地图与长期协作约束。
- `.agents/history.md`：全项目历史台账。
- `.agents/rules/`：当前仍生效的执行规则。
- `.agents/decisions/`：ADR 与已批准裁决。

## 归档约束

1. 归档文档默认只读，不因措辞整理改写其中的旧事实、版本号或 SHA。
2. 新证据只更新当前 `plan.md`、相应规则和 `history.md`；历史文档如需更正，应增加明确勘误而不是覆盖原结论。
3. 当前文档引用归档资料时必须写完整归档路径，禁止重新在 `.agents` 根目录建立历史交接文件。
4. 新的阶段性报告先进入对应产物目录；阶段关闭后，确有长期追溯价值的 Markdown 才移入本目录并登记分类。

## 2026-07-18 整理记录

- `HARDWARE_SERVER_RERUN.md`及 I2 v1～v4 六份报告/交接文档移入`server-simulation/v1-v4/`。
- `W4_ARCHIVE.md`移入`milestones/w4/`。
- `经验.md`改名为`engineering-lessons/managed-worktree.md`。
- `.agents`根目录只保留三个现行入口文档。
