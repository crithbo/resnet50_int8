# 服务器测试包内层路径长度预算公共规则发布记录

日期：`2026-08-04`

主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 用户要求

- 当前已冻结、已生成的服务器测试包不修改、不改名、不重建；
- 后续 fresh 服务器包应尽可能缩短路径，避免服务器解压、安装、compile、run 或工具
  中间文件超过字符限制；
- 最外层 package/install identity 可以较长以保留可读性和可追溯性，内层目录和成员名
  应适当缩短。

## 主线裁决

发布公共规则：

`CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001`

规则适用于后续新生成、因其他原因重建或使用 fresh identity 发布的服务器包。它不要求
仅因路径风格重新验证或重建 current 冻结包。

规则要求：

1. single-root 外层 identity 可以较长，但完整长 identity 只出现一次；
2. 内层采用确定性短命名空间和短 ID，长语义、来源和 SHA 写入 manifest/report；
3. 默认设计目标为：outer root 之后内部相对路径不超过 128 字符、内部深度不超过
   8 层、单个内层 component 不超过 48 字符；工具 ABI 强制 leaf 可有记录化例外；
4. manifest 新增 `path_length_budget`，本地默认按 target root 最长 96 字符、
   package-controlled projected absolute path 最长 240 字符做保守验证；
5. final-ZIP validator 在 fresh extract 后计算最长 install/workload/run/observer/
   readback/return-staging 路径并验证所有改名后的直接消费者引用；
6. runner 只在 compile 前按用户实际根长度做廉价保护，不扫描服务器 RTL/source tree；
7. 超预算深层成员、重复完整长 identity、改名后漏改直接消费者三类负控均须 fail closed。

该门只证明 package-controlled 路径具有执行余量，不替代 compile、自然终态、正式 D 或
E3/E4/E5；不得通过删除必需 payload、破坏 ABI 或缩短唯一外层身份到不可追溯来满足预算。

## 修改文件与 current SHA256

- `.agents/rules/服务器测试包生成规则.md`
  SHA256=`14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1`
- `.agents/rules/生成前必读索引.md`
  SHA256=`93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`

`.agents/plan.md`、现有 package/ZIP/sidecar、functional RTL 和算子专项规则均未修改。

## 验证

- 两个规则文件完整 UTF-8 读取；
- `git diff --check` 对规则文件退出 `0`；
- 索引的“生成服务器测试包”路由与生成前停止门均显式引用新 rule ID；
- 服务器规则的 final-ZIP self-audit 清单已纳入路径长度预算。

