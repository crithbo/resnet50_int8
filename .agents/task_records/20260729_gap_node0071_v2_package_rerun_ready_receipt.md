# GAP node0071 v2 receipt-only package-boundary rerun audit

- date: `2026-07-29`
- unique mainline:
  `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- status: `PACKAGE_RERUN_READY`
- scope: existing v2 ZIP receipt and package boundary only
- package rebuilt or modified: `false`
- GAP numeric analysis repeated: `false`
- sum/tail retested: `false`
- server files inspected: `false`
- uploaded/run: `false / false`
- local claim retained: `CONFIG_ONLY_CORRECTNESS_BASELINE`

## Rule and control receipts

- server package rule SHA256:
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- operator-config rule SHA256:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- generation index SHA256:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- GAP rule SHA256:
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- mainline-dispatched mutable plan SHA256:
  `f614a1e307e916932a9e778d8f902abb009744a2e32493f7f428cb3ba79c2958`
- locally observed mutable plan SHA256 at audit start:
  `aa8d4bbfe92d0fdc8e7c95c088d43d4cb6adac97ce22561f75e199014e2eb73c`
- locally observed mutable plan SHA256 at report materialization:
  `8ebc5025f8e464071e67392863a9a32de56d8b6273bcf8d197e29dff2d22e887`
- plan role: mutable provenance only, not a semantic gate

## RETURN_ANALYSIS

No new dynamic return was analyzed. This is a receipt-only audit of the
existing package after the user confirmed that the external server RTL compile
issue was resolved.

Package identity:

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v2_obs.zip`
- bytes: `1777110`
- ZIP SHA256:
  `c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f`
- sidecar SHA256:
  `d4008551f3e19c1e5960cc3a44a1986b7363deec08246004e6e4391fa152d84f`
- manifest SHA256:
  `5404e51e2c5c2cef3fb87b4d21192020cfdffbccdbd3f11a14db3daba7cbecdd`
- ZIP CRC/path/file-count receipt: pass, `123` files
- runtime readback targets in ZIP: `0`

## PACKAGE_BOUNDARY

Full-ZIP byte scanning found no occurrence of:

- `slice_rst`
- `SA_PE_Mul_Array`
- `SA_ALU`

The only RTL-like entry is the package-local read-only observer:

- path: `tb_probe/native_return_observer.svh`
- SHA256:
  `47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`
- server install: `false`
- compile binding:
  `VCS_EXTRA_OPTS=+incdir+<package_root>/tb_probe`

Manifest boundary:

- functional RTL modified: `false`
- server RTL entries: `0`
- server TB/observer install entries: `0`
- package-local observer entries: `1`
- server source identity bound: `false`
- server source preflight performed: `false`

The package therefore neither carries nor binds the old `slice_rst` interface
and has no package content that must be updated after the external server RTL
fix. The earlier returned log already proved that this observer was parsed
before the now-resolved server RTL interface failure.

## BLOCKER_DELTA

Closed by receipt:

- whether v2 embeds the old `slice_rst` interface;
- whether a functional RTL, server TB or observer-install payload requires
  rebasing;
- whether the observer include binding needs regeneration.

Still open:

- actual fresh-namespace rerun;
- compile/simulation/natural terminal;
- exact 48-file formal readback set with missing=0 and mismatch=0;
- final server/Trassic2.0_RTL source identity and E4/E5.

The server RTL repair is user-confirmed external state and was not independently
inspected by this audit.

## RULE_DELTA_PROPOSAL

No public rule delta is proposed. Existing package-boundary and conjunctive
dynamic-result gates are sufficient.

## PACKAGE_RELEASE

- status: `PACKAGE_RERUN_READY`
- original ZIP preserved byte-identical: `true`
- original ZIP SHA256:
  `c3fe06f6e0110b41936b69ae264a24b2dc2d76779efc589c4fe34378b6891b8f`
- package update required: `false`
- new package generated: `false`
- server command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- command precondition: fresh install/run/return namespace under the supplied
  absolute server root
- expected return ZIP: `r5_n71_gap_v2_obs_return.zip`
- expected return sidecar: `r5_n71_gap_v2_obs_return.zip.sha256`

## Machine receipt

- validator:
  `resnet50_pipeline/gap_node0071_v2_rerun_receipt.py`
- validator SHA256:
  `38d216d324bd1e5e4df49ca333a4b5a581f9521d09c0ff8b03bccfd34b3d346d`
- CLI:
  `tools/audit_gap_node0071_v2_rerun_receipt.py`
- CLI SHA256:
  `270357c813cab80a8bb84fb929b13a0852ea14e7ab837f181c18f4f7f21dd4cc`
- test:
  `tests/test_gap_node0071_v2_rerun_receipt.py`
- test SHA256:
  `b962f439638fcbb4bff1c1f237befd281376139982ae8d13d120160dae6bcfd5`
- report:
  `artifacts/operator_config_validation/r5-gap-node0071-v2-rerun-receipt/report.json`
- report SHA256:
  `5120a72b26b472b28c6e17d2c120005411256b3f5ed449af3033e9f45fb4788a`
- tests: `5`, all passed

Accepted local-E2/package assets were consumed only as immutable reuse.
No GAP numerical work, package materialization, server inspection, upload or
execution was performed.
