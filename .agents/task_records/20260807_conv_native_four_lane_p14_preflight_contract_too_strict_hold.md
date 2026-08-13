# Conv native-four-lane p14 preflight contract-too-strict HOLD

## Scope

- Family: performance/native-four-lane Conv, frozen `node0004`.
- Package: `r5_n4_0cc_p14_install`.
- Mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- This record consumes the formally dispatched server preflight receipt only. It does not authorize a p14 rerun or a p15 build.

## Exact identities

- Source ZIP before storage rotation:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p14_install.zip`
  - bytes: `45911951`
  - SHA256: `e920803ffddbb90dc93470c0b711bfc8bf046ae819012ad89461f36ab9be5427`
- Formal partial return on the server:
  `/home/panqs/ndp/simresult/r5_n4_0cc_p14_install_return.zip`
  - bytes: `2264`
  - SHA256: `c08005d0a3daa9a8417488738ae3b67c77ab7b7a055d9f207ac722987060fd6d`
  - `duplicate_absent=true`
  - The server path, byte count, SHA256, duplicate receipt, and stderr are user/mainline-attested. No local copy of the partial return ZIP was supplied, so this record does not claim local CRC/member inspection.
- Current public server-package rule:
  - bytes: `102441`
  - SHA256: `570ffedd04d5f41bc3093e5aa498544325281a4d81f2f4ddc889b754e968424c`
- Current shared runtime-layout helper:
  `tools/server_package_runtime_layout.py`
  - SHA256: `82723ecc427c3e42cfc327eff87cae7d5d935b9f6dccb220e78bfa573d11a9ae`

## RETURN_ANALYSIS

- Formal classification:
  `PACKAGE_LOCAL_PREFLIGHT_CONTRACT_TOO_STRICT`.
- Execution classification:
  `simulation_not_started`.
- Observed first divergence:
  `required pre-existing parent is absent: install/codex_runs`.
- Last proven good:
  the early shared finalizer was armed before the fallible layout preflight and atomically published the partial return under `/home/panqs/ndp/simresult`; no duplicate remained.
- Root cause:
  the current public contract and its exact helper require all of
  `install`, `install/cfg_pkg`, and `install/codex_runs` to pre-exist.
  The user requirement only requires the NDP root direct-child set to remain unchanged and `install` itself to pre-exist. Creating package-owned real directories below the existing real `install` directory does not add an NDP-root direct child.
- This is not a server environment, DUT, RTL, config, mapping, bitstream, execplan, SCA, numeric, W3, observer, terminal, or D failure.

Compile did not start, simulation did not start, natural terminal was not
exercised, and formal D was not evaluated. E3/E4/E5 and performance therefore
remain unclaimed.

## Local audit escape

The p14 local harness pre-created `install/cfg_pkg` and
`install/codex_runs`. It therefore proved the then-current over-strict
contract but omitted the legitimate boundary where only `install` pre-exists.
The next shared fixture must positively cover package creation of both missing
children and must fail closed for:

- missing/symlink/non-directory `install`;
- symlink/non-directory `install/cfg_pkg` or `install/codex_runs`;
- package-specific destination collision;
- path escape;
- any new NDP-root direct child;
- late finalizer coverage that misses this same preflight failure.

## Storage and successor disposition

- p14 was actually invoked and produced a formal partial return, so its exact
  ZIP and side receipts were moved byte-exact into the read-only `tested`
  disposition, not `superseded`:
  `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p14_install/`.
- p14 must not be rerun.
- There is no native-four-lane pending package after the rotation.
- `PACKAGE_RELEASE=NONE`.
- `STOP_WAIT_SHARED_GATE_FIX`: no p15 may be built until shared owner
  `019fd276` returns fresh exact rule/helper/schema/validator/test receipts and
  mainline explicitly redispatches this owner.
- DUT/config/mapping/bitstream/execplan/SCA/numeric/W3/golden/observer/timeout/
  functional RTL remain frozen and were not retested or modified.

## Rule feedback

`RULE_DELTA_PROPOSAL` for
`CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`:

Require only `$server_root/install` to pre-exist as a real non-symlink
directory. Permit the package to create missing real
`install/cfg_pkg` and `install/codex_runs` directories below it, while still
failing closed on symlinks, non-directories, path escapes, collisions, or any
change to the NDP-root direct-child name/type exact-set.

Machine analysis:
`outputs/conv_native_four_lane_0ccae916_p14_preflight_return_analysis/report.json`.
