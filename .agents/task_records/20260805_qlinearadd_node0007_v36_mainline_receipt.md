# QLinearAdd node0007 v35 RETURN → v36 主线收据

日期：2026-08-05  
owner：`019fa2c0-b647-7a91-93bf-d21a173487e3`  
主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## v35 裁决

- return SHA256:
  `30c5bdc1d1bb3cd47f28300e7557e8316ad770d38e50cebaeda1fce81e067972`
- compile=`0`，simulation=`124`，natural terminal=false，formal D=`0/28`。
- LPG: `FP32_ADD_GA_OUTPUT_9114_OF_9408_ROWS`
- FD: `FP32_ADD_GA_16B_OUTPUT_CANNOT_FORM_BUFFER5_32B_ACCEPTED_ROW`
- root:
  `UNIQUE_CONFIG_GA_OUTPUT_FOUR_PE_16B_SUPPLY_VS_BUFFER5_EIGHT_BANK_32B_REQUIREMENT`
- v35仅4个GA PE，输出`4×4B=16B`；Buffer5要求八bank、`8×4B=32B`。
  GA有活动，但Buffer5 accepted write=`0`，MSE4有request而无write data。

## v36 唯一后继

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_cout32_v36.zip`
- bytes: `26181302`
- SHA256:
  `b10712a584ad69cfeacfeb70d4faa913d0a82e59f66a1466e3b59b444a90a382`
- sidecar SHA256:
  `6c432813261067470a7e12587ddb72f0fc051d44fc0538126cc16c22eb624b59`
- command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return:
  `r5_qadd_n7_cout32_v36_return.zip`
- final audit SHA256:
  `948041a8b453e4da46d0f5be7dee77cc5cc653062e6f0a727f061394aa9ea535`
- return analysis report SHA256:
  `387d4267aa29cafa5b8f34559d2efb289578998fe3e2ea643d2c8f07ae622c25`
- release report SHA256:
  `6fd52c0bb1a6a9db36f4b29daf8e88e505540010a2c2f0aaee9e3bbadfcf08fd`
- owner release task SHA256:
  `065c2badf0b1d8343aa559981a7db14d0a03e3bbf571a3d86e6da8f324a19598`

v36只补齐op_fp32_add缺失的4个native PE，使GA输出成为8 lane/32B。
`PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN`；仍是split-C累计前缀，正式return闭合后
下一fresh successor提升到full-chain natural terminal + 正式28D。
