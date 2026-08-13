#!/usr/bin/env python3
"""Run the independent p46 first-fresh audit using the current shared epoch."""

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import audit_conv_native_p45_observerwide_first_fresh as base


base.PACKAGE_ID = "r5_n4_0cc_p46_nativeflow"
base.EPOCH = "runtime-preflight-native-flow-v1"
base.RULE_IDS = [
    "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
    "CDA-SERVER-SOURCE-BOUND-GENERATED-OBSERVER-001",
    "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
    "CDA-SERVER-POST-SIM-CORE-RETURN-INDEPENDENT-PUBLISH-001",
    "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
]


if __name__ == "__main__":
    raise SystemExit(base.main())
