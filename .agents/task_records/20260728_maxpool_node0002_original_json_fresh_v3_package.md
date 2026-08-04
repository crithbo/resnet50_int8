# MaxPool node0002 Git 原始 JSON fresh-v3 服务器包

日期：2026-07-28

## RETURN_ANALYSIS

- 状态：`PACKAGE_READY_NOT_RUN`。
- 目标：`node-0002 / r5:hwop-0002-00 / MaxPoolUint8`，覆盖两个真实
  ResNet channel tile，分别放在 slice0、slice1。
- 唯一配置源是 Git 跟踪文件
  `ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json`；
  文件 SHA256 为
  `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`。
- 原 JSON 被逐字节复制到包内 `.original` 文件，未重写；包内外 SHA 相同。
- 未读取、遍历、散列、复制或复用
  `artifacts/w5/native_json_maxpool/**`，也未读取任何先前 MaxPool
  mapping、bitstream、execplan、SCA/SCA_D、local-E2 或服务器包作为生成输入。
- 未检查服务器文件、名称、RTL 或身份；未上传、未运行、无 lease。
- 未修改功能 RTL、`.agents/plan.md` 或 `.agents/rules/**`。

## SOURCE_PROVENANCE

- Git remote：`https://github.com/uSFrances/ndp-sim.git`
- Git commit：`ec12424516ae0304228dd2321d4e604fe225e04e`
- Git blob：`4e8f7bb8906ab58f54f4c6507d2b94822f71bf04`
- JSON file SHA256：
  `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`
- 正式输入：
  `artifacts/w3/golden_batch16/tensors/tensor-f6c1a8fb6fd529e8.npy`
  ，SHA256
  `db55178510d91ed87faf9a3884c5e0b79685f6dd2c97561dc53f00a40a1b376f`。
- 输入只取 batch0 的 channel 0:16 与 16:32；slice 二进制 SHA256 分别为
  `1dad114e2230d10f5e4afbb3e2a88ad78feb7ca67215f093c6a1ba356335ab6e`
  和
  `11b683f4b4729a60a96adb42991befc14cf54044c047a241fac3a161ddbd7298`。
- golden 未读取正式输出 tensor，也未读取旧 MaxPool golden；由正式输入独立执行
  NumPy 九窗口 padded `maximum.reduce` 生成。两个 golden SHA256 分别为
  `70d5066e4b6687db7929bc5181a641c81c0754c9ea1f088dda52672fe12f32e6`
  和
  `4da95e977781d85557fabe70745112858851faa3ceb8f0b7a74fc6827ab7b033`。

## FRESH_MAPPING_AND_MATERIALIZATION

- 预声明 seed 顺序：`[42, 20260728, 314159]`。
- 每项预算：`10000` heuristic iterations、`2` internal restarts。
- 每次尝试均从锁定 commit 的独立 local clone 开始，初始
  `bitstream/config/mapping_cache` 文件数为 0；设置
  `PYTHONHASHSEED=0`。
- seed42 未找到 exact placement；seed20260728 首个达到
  `penalty=0 / fallback=false`。
- 选中 seed 后又在两个独立 clone/output root 中重跑；五项语义输出
  mapping review、parsed bitstream、64-bit bitstream、128-bit bitstream、
  detailed dump 逐 SHA 相同，mismatch path 为空。
- 关键身份：
  - mapping review：
    `995b28fdbf7f5f78c36cdaa69ed29a74063687de4b318a4eb3ec371ca87a1e39`
  - 128-bit bitstream logical：
    `e74bc621c3ac1bec45145d40eba86474eb4c95344adfeb8b90e643f80c7b1179`
  - 64-bit bitstream logical：
    `f16ea2395d9e4ba97f02736ae4e91fb59c3530bc6e8fcbb859df1fc308c688b8`
  - parsed bitstream：
    `9df9fe93a14324f9c2a9dfc4828d0508e8b7f92dbd96fff1aea256871e9293fd`
  - execplan：
    `7bcb656686d67cf8f751152de0dcf71869bb9e2bb50179de34160f0fbc3ed8d9`
  - package-adapted SCA：
    `092f1ccb2f4e75e6f4c57ceaff5e04a483923a4e5a0eb54b2ea2f7f03228c904`
  - package-adapted SCA_D：
    `e5117b05509fc01edd7c65cb389451def088655e9dc673c9d1503ec49ff057b8`
- config-bound GeneralPEA 与独立 NumPy golden 在两片共 100352 个 UINT8
  元素上 mismatch=0。该本地结果不计 E4/E5。

## ACTIVE_INT8_MAX_ADJUDICATION

- 绑定公共规则
  `.agents/rules/NDP硬件字段语义.md`
  SHA256
  `18d71520dd4ededc5edd9bb316acd0cc0421a9a261cf14b28ea6997ddd0e844a`。
- 绑定主线裁决
  `.agents/task_records/20260728_maxpool_int8_max_active_rtl_mainline_adjudication.md`
  SHA256
  `a283b0068b7b5a47b6711707e26c39946a2f89f65145207efdb0ca2315792c4f`。
- `INT8_MAX_NUMERIC_POLARITY=CURRENT_ACTIVE_SOURCE_SELECTS_UNSIGNED_MAX`。
- `CDA-GA-INT8-MAX-NUMERIC-001=LOCAL_SOURCE_PASS`。
- 旧 lane-min / numeric-polarity blocker 已从包 manifest 删除。
- 动态 pipeline0 ready 缺陷仍开：
  `CDA-GA-INT8-MAX-PIPE-001=CONTRADICTED`。
- 仅保留开放门：
  `B_GA_INT8_MAX_FLOW`、`B_MAXPOOL_SERVER_E4_E5`。

## FORBIDDEN_PATH_AUDIT

- generator、builder、runtime 三个实现文件在生成时执行静态 forbidden-token
  审计；match_count=0。
- manifest 明确记录
  `prior_materialized_asset_read_count=0` 和
  `forbidden_prior_materialized_asset_read_count=0`。
- fresh workload 从 generator 直接写入本轮临时 build root；没有 copytree
  或输入路径指向旧 MaxPool 物化目录。
- 旧的 fresh-v3 自构建结果在规则翻案后被移出输出目录，未被新构建读取；
  当前 ZIP 由新的两个空缓存构建根重新生成。

## RETURN_COLLECTION_FIX

- 包内 runtime SHA256：
  `c996b8250b3277646e38c28319ab7c0d24a1ba439ea84cc5465eff0a748c6b3a`。
- 已包含 staging tail source=destination 时不重复 copy 的回传修复。
- compile failure 定向测试确认仍会生成 return ZIP 与 sidecar，并保留
  `SERVER_TEST_INFRASTRUCTURE_COMPILE_FAILURE` 分类。

## PACKAGE_RELEASE

- ZIP：
  `artifacts/operator_config_validation/r5-server-test-packages/maxpool_node0002_original_json_fresh_v3.zip`
- ZIP SHA256：
  `17164af2758d22be1585e920a89eb2ae095fbc33a123867eb40bb96fb09a0eed`
- ZIP size：`1491637` bytes；entry count：`51`。
- payload tree SHA256：
  `8f018402326f57faabb3a068b3cea37e94485013781bd8cc7d843067de2d5340`
- validation receipt SHA256：
  `3705110b7e1a3b23cf6a74c94cc73fc6601acbe2e2d2fa0a19b38dc8494b5d53`
- 包内功能 RTL 数：0；TB/observer 数：0。
- `server_source_preflight_performed=false`；
  `server_source_identity_bound=false`。
- 唯一命令：
  `bash PREPARE_AND_RUN.sh /absolute/path/to/server_root`
- 预期回传：
  `maxpool_node0002_original_json_fresh_v3_return.zip` 与同名
  `.zip.sha256`。
- 状态仅 `PACKAGE_READY_NOT_RUN`；由于 `NO_DYNAMIC_BASELINE`，未来首次失败
  只能称 `FIRST_DYNAMIC_FAILURE`，成功也只按 version-unbound 诊断边界裁决，
  本包自身不计 E4/E5。

## VALIDATION

- 完整 fresh deterministic double build：PASS。
- ZIP exact-set、sidecar、原 JSON byte identity、SCA namespace-only adaptation、
  version-unbound/no-server-scan、bootstrap immutability：PASS。
- `python -m unittest tests.test_build_maxpool_node0002_original_json_retest -v`：
  7/7 PASS。
- `py_compile`：PASS。
- targeted `git diff --check`：PASS。

## IMPLEMENTATION_IDENTITIES

- `resnet50_pipeline/native_json_maxpool_package.py`
  `280c5121f855d9c401618f2a78e99c05cd5849f05722741eaeaa5853e43071d0`
- `tools/build_maxpool_node0002_original_json_retest.py`
  `1ab364974a95229036abfb28bb2bf72ce9e72f8ac3097d30559b51493714e3fd`
- `tools/maxpool_node0002_original_json_server_runtime.py`
  `c996b8250b3277646e38c28319ab7c0d24a1ba439ea84cc5465eff0a748c6b3a`
- `tests/test_build_maxpool_node0002_original_json_retest.py`
  `734f5ce5ab1c9e8d51c64f6a435123a39c29da46529d9ff821fd31e93f8aced5`

## READ_RECEIPTS

- `.agents/agent.md`
  `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0`
- `.agents/plan.md`
  `dc587e80c7ad94bf4ecb2f9942f97c585c278edd946658b426f08e295b85f69d`
  （mutable provenance）
- `.agents/rules/生成前必读索引.md`
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/算子配置规则.md`
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/服务器测试包生成规则.md`
  `72f22cc21e328eb06a841418a39640a924de0c533e6d0ac6d8822dfd0771d524`
- `.agents/rules/NDP硬件字段语义.md`
  `18d71520dd4ededc5edd9bb316acd0cc0421a9a261cf14b28ea6997ddd0e844a`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

## BOUNDARY

- `candidate_release=false`
- `counts_as_e4=false`
- `counts_as_e5=false`
- `functional_rtl_modified=false`
- `server_inspected=false`
- `uploaded=false`
- `run=false`
- `lease=none`
