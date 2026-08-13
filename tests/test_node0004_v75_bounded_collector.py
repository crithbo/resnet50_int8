from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "outputs/conv_node0004_v74_recovered_return_v75_successor/build/r5_n4_hw_v75_sourcebound_collectfix"
RECOVERED = ROOT / "outputs/conv_node0004_v74_recovered_return_analysis/extract/r5_n4_hw_v74_sourcebound_epoch_diag_return/runs/c0/source_bound_causal.log"


def main() -> int:
    tools = PKG / "package_tools"
    sys.path.insert(0, str(tools))
    spec = importlib.util.spec_from_file_location("v75_runtime", tools / "node0004_hang_localization_runtime_v7.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="v75-collector-") as td:
        root = Path(td)
        c0 = root / "c0"
        c0.mkdir()
        with (c0 / "sim.log").open("wb") as stream:
            stream.write((b"UNBOUNDED_SIMULATOR_CHATTER\n" * 400000))
            stream.write(RECOVERED.read_bytes())
        original = (c0 / "sim.log").stat().st_size
        receipt = module._prepare_source_bound_products(root)
        decision = json.loads((c0 / "source_bound_causal_decision.json").read_text(encoding="utf-8"))
        assert original > 8 * 1024 * 1024
        assert receipt["bounded_log_bytes"] < 7 * 1024 * 1024
        assert receipt["sim_log_equals_causal_log"] is True
        assert receipt["parser_exit_status"] == 0
        assert decision["decision"] == "POST_TERMINAL_TEMPORAL_OWNERSHIP_REQUIRES_RING"
        assert not decision["errors"]
        print(json.dumps({"pass": True, "original_bytes": original, "receipt": receipt, "decision": decision["decision"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
