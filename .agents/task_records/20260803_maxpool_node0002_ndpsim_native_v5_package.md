# MaxPool node0002 ndp-sim native v5 package

## Ownership

- analysis_owner_thread: `019fbe9f-3f2d-7071-806c-1ae72ae96391`
- return_target_thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- date: `2026-08-03`

## USER_OVERRIDE_APPLIED

The generic MaxPool return-to-successor/observer route was stopped. No
capture-to-outbuffer root-cause audit, generic observer, canonical diagnostic,
v4 workaround, numeric retest, or RTL retest was included. Existing assets were
left untouched.

## NATIVE_STRUCTURE_AUTHORITY

- authoritative JSON:
  `ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json`
- authoritative JSON SHA256:
  `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1`
- native generated tree:
  `ndp-sim/model_execplan/output/node0002_maxpool_wave0_graph`
- direct consumer: `ndp-sim/model_execplan/main.py`
- isomorphic repository sample: `jsons/gemv_local`
- resolved native style:
  `jsons/`, `config/`, `install/`, `sca_cfg.json`, `sca_cfg_D.json`,
  `instructions_explained.txt`, `*_withbaseaddr.json`

The source JSON is byte-identical. The native materialized operator JSON
differs only at the planner-owned `stream0.base_addr` and `stream1.base_addr`
leaves. SCA/SCA_D have exactly 58 mechanical fresh-install namespace prefixes;
their remaining bytes, including original line endings, are unchanged.

## Packaging boundary

The original native tree has 186 files and 81,407,600 bytes. Packaging retains
all native content, relocates two native generation receipts and 84 D-golden
files without changing their bytes, and adds six files:

- source JSON authority copy: 19,762 bytes
- runner: 5,576 bytes
- minimal runtime/result collector: 23,346 bytes
- final manifest: 58,427 bytes
- native-structure receipt: 32,451 bytes
- README: 509 bytes

The six additions total 140,071 uncompressed bytes. Excluding the already
counted source JSON copy, package wrapper/contracts are five files and 120,309
bytes. Runtime D targets are absent at startup.

## Validation

- deterministic double build: PASS; ZIPs byte-identical
- final ZIP CRC/root/exact-set/sidecar: PASS
- source JSON byte identity: PASS
- native structure and two-base-leaf materialization: PASS
- generic observer/canonical/v4 route absence: PASS
- safe compile+sim stub with exit finalizer: PASS, runner exit `74`
- safe TERM finalizer: PASS, runner exit `143`, signal receipt `TERM`
- wrong source identity: fail closed before compile
- missing native operator JSON: fail closed before compile
- focused unittest: `4/4 PASS`
- final audit:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n2_maxpool_ndpsim_native_v5.final_zip_rule_self_audit.json`
- final audit SHA256:
  `f75706a14b58f794037d073f193501b656b3378e72dd7c30e34094071fed58d0`

## PACKAGE_RELEASE

- status: `PACKAGE_READY_NOT_RUN`
- claim: `NATIVE_NDPSIM_REUSE_SERVER_TEST_NOT_E4_E5`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n2_maxpool_ndpsim_native_v5.zip`
- bytes: `14718654`
- ZIP SHA256:
  `9a193d8f97d7b43d7e43886a2bc42dffee74e585832f5360a13a8ead2fa7269e`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n2_maxpool_ndpsim_native_v5.zip.sha256`
- sidecar file SHA256:
  `e360177c0996cbfbe200868d9ec0766a61b589be37e1e4ed21a7323db0d8b4db`
- command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- expected return:
  `r5_n2_maxpool_ndpsim_native_v5_return.zip`

No server upload/run/lease, functional RTL edit, public rule edit, plan edit, or
other-family edit was performed. This package does not claim E4/E5.
