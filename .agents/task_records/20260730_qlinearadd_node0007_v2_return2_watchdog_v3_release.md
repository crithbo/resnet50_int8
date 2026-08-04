# QLinearAdd node0007 v2 return(2) analysis and v3 timeout-only release

Date: 2026-07-30

Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`

## Read receipts

- mutable plan:
  `e3e44d47121b6c567b6e4c103b60c8012bbf09e8d904aabf9f1e4a03c016d97f`
- pre-generation index:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- server-package rule:
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`
- QLinearAdd rule:
  `dd4a8122d771ed5f4dbb9995fd6463ba14b179a72a515d2af5e91d30f2c71269`
- exact UINT8-tail rule:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

All four active-rule receipts current-match. The plan receipt is provenance only.

## RETURN_ANALYSIS

Input:

- local file:
  `r5_qadd_n7_relocated_v2_return(2).zip`
- `(2)` is only a local collision suffix.
- bytes: `137291`
- SHA-256:
  `7a7b1c68dbf582c070cbdb4daa310facdcfb46a6a3b796294300979f80551afb`
- directly adjacent sidecar:
  `r5_qadd_n7_relocated_v2_return(2).zip.sha256`
- sidecar status: absent; formal receipt therefore fails closed.

Internal identity:

- `install_name=r5_qadd_n7_relocated_v2`
- source ZIP observed and expected SHA-256:
  `60534faad0894a8b6507687159d43c824dd968f6c6a3386fa7877fc2007bf0bc`
- embedded/source/local package manifest three-way SHA-256:
  `617dff140f9553bad601fce368dd3981fab5d56662a7a66f49d0831a46b410de`
- source and return ZIP CRC: clean
- return exact-set, per-record size/hash, and package allowlist: pass
- package/install preflight: pass
- package and installed formal D targets before simulation: absent

Dynamic gate:

- compile exit: `0`
- simulation exit: `124`
- SCA/SCA_D echo: exact
- preload: `85/85`
- last ordered public events:
  `85 matrices loaded` -> `Exec_Base=0x00d2c800 Exec_Length=182` ->
  `Reg Started.` -> `INFO: slice start`
- natural terminal: false
- formal D: expected `28`, observed `0`, missing `28`
- mismatch byte count: `0`, but is non-evaluable because all formal D is
  missing; it is not a numeric pass.

## FIRST_DIVERGENCE

Formal receipt first divergence:
`FORMAL_RECEIPT.ADJACENT_SIDECAR_MISSING`.

Execution first divergence:
`SIMULATION_TIMEOUT_AFTER_SLICE_START_NO_PROGRESS`.

The package-owned `timeout ... 12h "$simv"` returned 124 after every preload
and the first slice-start marker, before natural completion or any formal D
dump. After `slice start`, the returned log contains only monitor creation at
the same simulator timestamp and no accepted transaction or completion event.

The log has no wall-clock timestamp at `slice start`. Therefore this return
cannot distinguish:

1. the 85 large preload/write-read-verification transfers consuming almost all
   of the shared 12-hour budget; or
2. computation starting earlier and immediately stalling until timeout.

This is not accepted as either “normal slow completion” or a proven deadlock.
The first dynamic root cause remains unresolved.

The full-node workload is unusually large: 12,845,056 logical output elements,
16,859,136 padded formal output bytes, six physical operators, 37,352,448
requests with multiplicity, 20,493,312 unique request addresses, and 85
preloads carrying 37,505,888 logical bytes represented by 302,391,404 text
bytes. This scale makes preload domination plausible, but does not remove the
post-start stall possibility.

## E3 / E4 / E5

- E3: false; no natural completion.
- E4: false; `28/28` formal D targets are missing. The compatibility profile
  also does not bind a final server RTL commit.
- E5: false; no E4 and no fresh-identity repeated dynamic pass.

## BLOCKER_DELTA

- closed: prior missing-observer compile blocker is not present in this
  return; compile succeeds and simulation starts.
- opened:
  `B_QADD_NODE0007_POST_SLICE_START_NO_PROGRESS_ROOT_CAUSE_UNRESOLVED`.
- preserved: formal-return adjacent sidecar is absent.
- no QLinearAdd arithmetic, qparam, W3-order, address, lifetime, mapping,
  bitstream, execplan, SCA, or golden blocker was reopened.

## RULE_DELTA_PROPOSAL

None. Current shared rules already require independent compile/simulation
timeouts, natural-terminal qualification, exact-set readback, and fail-closed
partial-return handling.

## PACKAGE_RELEASE

Generated one fresh identity:

- install/package identity: `r5_qadd_n7_relocated_v3`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_relocated_v3.zip`
- bytes: `38009015`
- SHA-256:
  `265188700bca6c45d6d0894326f71b4e9c991cbaf3847f384785504ed7b2fc5c`
- sidecar:
  `r5_qadd_n7_relocated_v3.zip.sha256`
- status: `PACKAGE_READY_NOT_RUN`
- candidate release: false
- evidence level: `E2_LOCAL_ONLY`
- single command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02`
- expected return:
  `r5_qadd_n7_relocated_v3_return.zip` and adjacent
  `r5_qadd_n7_relocated_v3_return.zip.sha256`

The only runtime-control change is the simulation watchdog `12h -> 48h`,
plus the required fresh install namespace. This is a diagnostic observation
window extension, not proof that v2 was merely slow and not proof that a
deadlock is absent. The install payload, independent
golden set, runtime gate, and SCA semantics after namespace normalization are
identical to v2. The package contains zero RTL/TB entries and zero preseeded
formal D targets. Deterministic package-tree and ZIP rebuilds both match.

`numeric_analysis_repeated=false`; frozen 17-instance/stage0, six-stage
mapping/bitstream/execplan/SCA, and independent golden assets were consumed.
No server file inspection, upload, run, or lease action occurred.
