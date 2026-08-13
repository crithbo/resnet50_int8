#!/usr/bin/env python3
"""Exact-final-ZIP HDL gate for the identity-only v62 native-flow successor."""

from __future__ import annotations

import validate_qlinearadd_node0007_v61_observerwide_hdl as prior


prior.PACKAGE = "r5_qadd_n7_tailround_lanephase_v62_nfobs"
prior.MEMBER = f"{prior.PACKAGE}/tb_probe/qadd_observer_wide_impl.svh"
prior.CONTRACT = f"{prior.PACKAGE}/contracts/server_observer_only_wide_causal_contract.json"
prior.MANIFEST = f"{prior.PACKAGE}/TEST_PACKAGE_MANIFEST.json"


if __name__ == "__main__":
    raise SystemExit(prior.main())
