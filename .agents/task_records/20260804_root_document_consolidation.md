# 2026-08-04 根目录说明文件收敛

## 目标

根目录只保留一个项目级说明 `README.md`；非活动教程、旧交接和旧缺陷说明迁入
`.agents/archive/`，不改代码、配置、模型、RTL 或当前测试包。

## 裁决

- 保留根目录唯一项目说明：`README.md`。
- `conv_full.txt` 虽为文本，但被 `contracts/conv_full_encoder_evidence.json`、
  `tools/audit_senior_conv_operator.py` 等直接消费，因此保留原路径。
- `conv_full.json` 与 `conv_1x1_real.json` 被 pipeline、tests、contracts 和 builders
  直接按根路径消费，因此保留原路径。
- `.gitattributes`、`.gitignore`、`.worktreeinclude`、`pyproject.toml`、
  `repos.lock.json`、requirements 和 `bootstrap.py` 都是仓库/环境入口，不归档。

## 归档

- 原 `docs/` 整体迁入：
  `.agents/archive/project_docs_20260804/docs/`
- 原长版 `README.md` 迁入：
  `.agents/archive/project_docs_20260804/README.pre_consolidation.md`
- 归档前 `docs/`：16 files，320,788 bytes。
- 原 README：7,969 bytes，
  SHA256=`db6a0cc90577062f64c9d100f4b7105d7feb211f433fb8f7321f2530c455b139`。

本轮没有永久删除说明材料；归档可恢复。新根 README 去除旧进度数字、重复段落和过时
候选命令，只保留稳定入口、恢复方式、目录职责和安全边界。
