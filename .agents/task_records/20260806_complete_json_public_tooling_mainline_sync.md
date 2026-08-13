# Complete-JSON 公共规则与工具主线同步

日期：2026-08-06  
来源 task：`019fd276-14c5-7800-94db-87ebfb9ce632`  
来源 worktree：`C:/Users/15383/.codex/worktrees/532a/resnet50_int8`

## 同步边界

- 用户已正式授权同步公共 complete-JSON 规则与工具。
- 11个公共合同/schema/tool/test文件在主工作区原先均不存在，按来源字节机械同步。
- 两份规则文件已有主线并行增量，未整文件覆盖；只合并complete-JSON逐叶适用性、
  handler能力、组合边界、current-config逐叶对比及共享validator路由。
- 未修改任何current ZIP、算子config/golden、functional RTL或server state。
- 未生成服务器测试包，未执行上传、服务器运行或lease。

## 主工作区精确身份

- `.agents/rules/算子配置规则.md`
  - bytes=`35038`
  - SHA256=`52939b59f079721a9a8438e3d5297f42118eadb1f2c2a238e20bcca73a30a820`
- `.agents/rules/生成前必读索引.md`
  - bytes=`12042`
  - SHA256=`d3a82e82199eb005d0d477b7cc740d11c42cf5fa3bef4ac2b2573cc5bad26bb6`
- `contracts/operator_config/complete_json_generation_contract_v1.json`
  - SHA256=`de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746`
- `schemas/operator_config_complete_json_candidate_v1.schema.json`
  - SHA256=`e97d7639e02efc6912937962c076b7a26d13c9ef73c17bac51044c7c93f96ac9`
- `schemas/operator_config_field_provenance_ledger_v1.schema.json`
  - SHA256=`4c0ba2042801ffedf26ccaf269d4e164b1f60e9bba5df29236ca425c7cd4ffb9`
- `schemas/operator_config_handler_capability_v1.schema.json`
  - SHA256=`8aacb2365d6c82c8bd21c40af942e11df898a43db4cfd24cb01d00976e564e5f`
- `schemas/operator_config_current_test_diff_v1.schema.json`
  - SHA256=`bd79f9cb6a3dd74d5f4b6fef8beda3caf176e620f773edc47dafbee86b98fe19`
- `schemas/operator_config_composition_boundary_v1.schema.json`
  - SHA256=`a2a9545301538c2c1c18a119fccfe16b394448509cf324dfba22b8dfd6dc8371`
- `schemas/operator_config_complete_json_family_set_v1.schema.json`
  - SHA256=`1d337c8dc948d4fb0fe3e8a9d247e4069413cb86843f82b150645e1b73b91ce7`
- `tools/validate_complete_operator_json_candidate.py`
  - SHA256=`c24a6fe103ebba3ece557bfd76417907f41847dd5550013f7fd45b047f49be0a`
- `tools/audit_complete_operator_json_family_set.py`
  - SHA256=`f7efd5cc471bf13d77a1224444f5b49a92bf82c446a99b757dc2fc7fe635f184`
- `tests/test_complete_operator_json_candidate.py`
  - SHA256=`4cdba0b531bb8dc73632d2993989f451fc3091e7f8a8aa78deb98d4f47d92a73`
- `tests/test_complete_operator_json_family_set.py`
  - SHA256=`ce041ae94f7172f017d92f366c8fa338f9b4237eb53555304537e6bfe5133aca`

## 验证

- `py_compile`：PASS。
- `tests.test_complete_operator_json_candidate`：
  `8/8 PASS`。
- `tests.test_complete_operator_json_family_set`：
  `2/2 PASS`。
- 合计：`10/10 PASS`。
- `git diff --check`：PASS。

覆盖：exact native正控、ledger漏叶、project-added冒充native、placeholder shape越权、
source absent unknown、composition缺失、错误`SAME`、禁止ZIP、完整family stage与漏项。

## Claim boundary

同步只提供本地complete-JSON候选、field provenance、handler capability、composition
boundary、current-test diff及family-set覆盖验收。它不生成mapping、bitstream、execplan、
SCA或服务器包，不执行服务器，不证明natural terminal、formal D、E3、E4或E5。
