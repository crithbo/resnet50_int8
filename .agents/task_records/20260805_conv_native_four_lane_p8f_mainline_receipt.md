# Conv native four-lane p7 RETURN → p8f 主线收据

日期：2026-08-05  
owner：`019fc783-1146-7901-9e40-64d0ed8e052d`  
主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## p7 裁决

- return SHA256:
  `71e7feda390934afec933ddfbfded6d6bebfdb633a66fe3ab00dd1817293f05c`
- source SHA256:
  `4ff473247a7356af3e6b960430b559e90113b774e27478dbcd41151d8507f8a4`
- production compile=`0`；8/8 actual leaves匹配云端权威`0ccae916`。
- run=`124`来自包内1h预算；末样本cycle=`31,946,266`，
  qualified total=`44,827,079`，连续28个完整窗口有增量，zero-delta hang=`0`。
- 裁决：
  `LONG_RUNNING_PROGRESSING_RUNNER_TIMEOUT_SUCCESSOR_REQUIRED`，
  不是功能hang；p7本身无正式320D，不能作formal-D通过或失败裁决。

## p8f 唯一后继

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_0cc_p8f.zip`
- bytes: `66231520`
- SHA256:
  `1e214ba277992d4ab08795dd35f4db3082ccad4e17bebc2aaf6e473b1bc7c224`
- sidecar SHA256:
  `2e6ce2939087f637db4dd0e9da46c8e1c8a28fc0bcf19ca8e75adeaf686d03c2`
- command:
  `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- expected return:
  `/home/panqs/ndp/NDP_copy02/r5_n4_0cc_p8f_return.zip`
- final audit SHA256:
  `a50c72f28d1bb1f66d891756fa35b59bee824b791e4e82f911933b9581bb7b43`
- owner task record SHA256:
  `e6b59f81f486ff66b4179817ad73969e80f8853ccde739d35626b16cb7220544`

p8f恢复27-run、每run 12h、27个natural-terminal门和320个formal-D consumer。
`PACKAGE_RELEASE=PACKAGE_READY_NOT_RUN`；未上传、未运行、未取lease。
