# 服务器包严格本地自检与最小运行前检查规则发布

日期：2026-07-31

## 用户原则

服务器测试应尽快进入真实 compile/run，并优先暴露配置语义或 RTL 问题。测试包不得把
本地可发现的生成错误带到服务器；服务器端也不得因无必要地检查既有特定文件而在
compile 前失败。

## 已证明的触发事实

1. GAP node0071 v9 的 package/installed preflight 均通过，但 runner 内第二份硬编码
   observer expected SHA 与最终 ZIP 实际 observer SHA 不一致；guard 输出被重定向后
   `exit 7`，导致终端只打印 preflight JSON，compile 未触发。
2. 本地真实 runner + 安全 compile stub 正控能够在不访问服务器 RTL 的情况下发现该类
   提前退出；wrong identity 负控可证明 fail-closed。
3. 多轮服务器失败表明，枚举/哈希/要求服务器既有 RTL、TB、Makefile、filelist、Git、
   README 或 observer 并不能提高算子语义验证质量，反而增加与真实 compile 无关的
   基础设施首分歧。

## 规则裁决

公共规则新增：

- `CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001`
- `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`

并把 `CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001` 调整为普通测试包的默认
profile。

本地最终 ZIP 自检保持严格，覆盖 ZIP/sidecar、CRC/exact-set、manifest-bound payload、
runner 正负启动链、SCA/SCA_D、runtime-D absent、observer 四向绑定、canonical
decision、联合结果门和 return allowlist。

服务器运行前只允许检查用户参数、fresh namespace、本包自身安装完整性、正式 D 未预置
和通用命令；默认禁止读取、枚举、哈希、比较或要求服务器既有具体 RTL/TB/Makefile/
filelist/support/Git/README/observer/历史 SHA。真实环境问题由 compile/run 自然失败并
通过 allowlist return 回传。

package-local payload identity 必须以最终 manifest 为单一事实源；runner 不得维护第二份
硬编码 expected SHA。只有用户明确要求源码身份审计或授权事务式修改唯一服务器文件时，
才允许检查该精确目标，而且不得成为普通包进入 compile 的前置门。

## 收据

- `.agents/rules/服务器测试包生成规则.md`
  SHA-256=`0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a`
- `.agents/plan.md`
  mutable provenance SHA-256=`532d176ed70fb630dbc797263409887a2d32bafecd5f9af3a21077d56a157bfe`
- `git diff --check`：exit 0

## 边界

本轮只修改主线计划和公共服务器测试包规则；未修改功能 RTL、算子配置、workload、
golden 或服务器文件，未上传或运行服务器。
