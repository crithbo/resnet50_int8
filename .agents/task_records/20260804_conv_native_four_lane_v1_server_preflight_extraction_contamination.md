# Conv native-four-lane v1 server preflight extraction contamination

Date: 2026-08-04  
Owner: independent Conv native-four-lane performance owner  
Target mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Submitted observation

The user invoked:

`bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`

from:

`/home/panqs/ndp/r5_conv_native_four_lane_df23e4d_perf_v1`

The package-local runtime stopped in its first package exact-set preflight:

```text
package exact-set differs:
missing=[]
extra=[
  'r5_conv_native_four_lane_df23e4d_perf_v1/PREPARE_AND_RUN.sh',
  'r5_conv_native_four_lane_df23e4d_perf_v1/README.md',
  'r5_conv_native_four_lane_df23e4d_perf_v1/TEST_PACKAGE_MANIFEST.json'
]
changed=[]
```

The traceback ends before install verification, observer guard, production
compile or simulation.

## Receipt-only adjudication

`missing=[]` and `changed=[]` prove that every manifest-bound top-level
package file was present with the expected size/SHA. The only divergence is an
additional directory named exactly like the package root underneath the
package root. The three printed paths are the first three sorted extra members;
the exact-set check intentionally reports a bounded prefix.

This is an extraction-tree contamination, not a workload, mapping, arithmetic,
functional RTL or production compile failure.

Classification:

- `SERVER_TEST_INFRASTRUCTURE_PACKAGE_PREFLIGHT_FAILURE`;
- `EXTRACTION_TREE_CONTAMINATION_FAIL_CLOSED`;
- `compile_started=false`;
- `simulation_started=false`;
- `dynamic_attempt_count=0`;
- no E3/E4/E5 evidence and no Conv numeric/RTL adjudication.

The runner creates the candidate's install/run/evidence namespaces immediately
before package preflight. Therefore the failed invocation leaves these exact
task-owned paths in `NDP_copy02`:

- `install/cfg_pkg/r5_conv_native_four_lane_df23e4d_perf_v1`;
- `run_r5_conv_native_four_lane_df23e4d_perf_v1`;
- `evidence_r5_conv_native_four_lane_df23e4d_perf_v1`.

No return ZIP is expected because the EXIT/signal finalizer is installed only
after package preflight.

## Independent reproduction

Source ZIP:

`artifacts/operator_config_validation/r5-server-test-packages/r5_conv_native_four_lane_df23e4d_perf_v1.zip`

- bytes: 46,027,937;
- SHA256:
  `5cbf05cac96f887c6753d378c7f3f44daf04f60caa6016f1f41eab274cebd62f`.

The canonical ZIP was freshly extracted into a new temporary directory. With
the real shell-entry bytecode environment
`PYTHONDONTWRITEBYTECODE=1`, the package-local runtime preflight returned:

```text
exit=0
valid=true
file_count=832
readback_target_count=320
preloaded_readback_target_count=0
```

An otherwise identical extract was then contaminated only by adding:

```text
r5_conv_native_four_lane_df23e4d_perf_v1/PREPARE_AND_RUN.sh
r5_conv_native_four_lane_df23e4d_perf_v1/README.md
r5_conv_native_four_lane_df23e4d_perf_v1/TEST_PACKAGE_MANIFEST.json
```

The same preflight returned exit `1` with the same three `extra` paths as the
server traceback. The temporary trees were removed after their resolved paths
were verified to be under the system temporary directory.

## Successor adjudication

`PACKAGE_SUCCESSOR=NONE_REQUIRED_FOR_THIS_OBSERVATION`.

The immutable source ZIP passes a fresh-extract preflight and the observed
failure is caused entirely by mutable extraction state outside the source ZIP.
Changing package bytes or assigning a new package identity would not correct
that state. The canonical v1 ZIP remains read-only and valid for a retry from:

1. a newly created empty extraction parent;
2. the single archive root directly below it;
3. a server root with fresh candidate install/run/evidence namespaces.

If `NDP_copy02` is reused, only the three exact task-owned namespaces listed
above may be removed after the operator verifies their resolved absolute
paths. Unrelated server content must not be touched. A fresh equivalent server
root is preferable when available.

## Blocker and claim boundary

Preserved:

- `B_CONV_NATIVE_FOUR_LANE_SERVER_NATURAL_TERMINAL`;
- `B_CONV_NATIVE_FOUR_LANE_SERVER_FORMAL_D_320`;
- `B_CONV_NATIVE_FOUR_LANE_SERVER_PRODUCTION_RTL_IDENTITY`.

The previous local E2 and package SHA remain unchanged. This record does not
claim any production compile, natural terminal, formal D, performance, E3, E4
or E5 evidence.

## Rule feedback

RULE_CONFIRMATION:
`CONFIRMED_SUFFICIENT_NO_RULE_DELTA`.

The failure directly confirms:

- `CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001`;
- `CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001`;
- package exact-set fail-closed behavior;
- fresh extraction and fresh namespace requirements.

The exact-set gate rejected external extraction contamination before compile,
so no configuration/RTL conclusion was fabricated. Current rules already
require a fresh extract and an immutable package tree; no non-synonymous rule
gap is established by this observation.

Current read receipts:

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`;
- `.agents/plan.md` mutable provenance:
  `16bfcb9f27590e572acd46ccc55dc90c7acfde05f667655cb8555d6c61e811c2`;
- generated-before-read index:
  `b3dbba8b272866c3109b7d7d3339166a333794ab114adcee9bcbda3c9ce88fbe`;
- server-package rule:
  `14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1`.
