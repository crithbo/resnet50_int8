# Conv node0004 native four-lane performance owner start

## Provenance

- date: `2026-08-03`
- mainline thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- independent performance owner:
  `019fc783-1146-7901-9e40-64d0ed8e052d`
- serialized correctness owner:
  `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- pre-dispatch plan SHA256:
  `5f5715b1cb3d7649b36dc79736eb2da1038ef8ea94acd1884bf17092033f8654`

## User decision

Keep the current serialized single-nonzero-product implementation as the
independent correctness baseline and start a separate native four-lane
performance candidate.

The performance target is:

- reduce compute occurrence from about 4x toward 1x;
- reduce weight and activation traffic from about 4x toward 1x;
- raise maximum useful product-lane utilization from 25% toward 100%;
- preserve bit-exact node0004 semantics and the final natural-terminal plus
  320/320 formal-D gate.

## Ownership boundary

The existing Conv owner retains:

- serialized correctness assets;
- node0004 v28 D-write diagnostic;
- v28 return-to-successor closure;
- the remaining Conv expansion only after the representative node closes.

The new performance owner may create only fresh-prefixed native-four-lane
contracts, builders, validators, tests, configurations, artifacts and server
packages. It must not modify, overwrite or rebuild serialized/v28 assets, the
mainline plan/rules, functional RTL or other operator families.

## Mandatory arithmetic and RTL gates

Before target materialization, the performance owner must bind an immutable
compatible RTL identity and independently exercise:

- the 18-bit first INT8 compressor;
- the absence of duplicate carry shifting;
- the historical stock behavior as a negative control;
- the serialized implementation as an independent correctness oracle;
- four-lane signed18 extrema `[-130560, 129540]`;
- K tails with one, two and three live lanes;
- nonzero input zero-point, bias and modulo-s32 wrap.

The current audit also identifies a separate negative-psum boundary in
`SA_PE_Float_CSA`: `(-5)+5` and `INT32_MIN+0`. The performance owner must prove
whether any frozen node0004 or intended ResNet Conv occurrence reaches that
boundary.

- If reachable, stop at the exact RTL capability blocker and set
  `PACKAGE_RELEASE=NONE`; no RTL modification is authorized.
- If unreachable, the candidate remains model/instance scoped and may not
  claim full INT32-domain correctness.

## Local and server sequence

The required order is:

1. immutable RTL identity and arithmetic/negative controls;
2. fresh native-dot4 target JSON, mapping, bitstream, execplan and SCA;
3. deterministic builds and config-bound E2;
4. native-vs-serialized-vs-ONNX/W3 bit-exact comparison;
5. only after E2, a fresh
   `PERFORMANCE_DIAGNOSTIC_CANDIDATE / candidate_release=false /
   PACKAGE_READY_NOT_RUN` server package with current final-ZIP audit;
6. user-controlled server execution and a formal return proving DUT natural
   terminal, 320/320 D, mismatch zero and production RTL identity.

The new task is not authorized to upload, run, lease or modify functional RTL.
It must proactively notify the mainline at package-ready or the first precise
blocking leaf, including actual occurrence/traffic/lane utilization and
evidence-backed rule feedback.
