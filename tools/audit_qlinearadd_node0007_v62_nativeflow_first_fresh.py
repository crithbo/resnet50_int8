#!/usr/bin/env python3
"""Independent current-epoch first-fresh audit for the QAdd v62 successor."""

from __future__ import annotations

import audit_qlinearadd_node0007_v61_observerwide_first_fresh as prior


prior.PACKAGE = "r5_qadd_n7_tailround_lanephase_v62_nfobs"
prior.EPOCH = "runtime-preflight-native-flow-v1"
prior.CONJUNCTION_EPOCH = "observer-only-post-sim-conjunction-fix-v1"
prior.HDL_TOOL = "validate_qlinearadd_node0007_v62_nativeflow_hdl.py"
prior.RULES = [
    "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
    "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
    "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
    "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
    "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
]


if __name__ == "__main__":
    raise SystemExit(prior.main())
