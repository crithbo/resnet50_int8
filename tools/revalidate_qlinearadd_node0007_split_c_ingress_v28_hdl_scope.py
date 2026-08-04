from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.revalidate_qlinearadd_node0007_v20_observer_hdl_scope as gate


NAME = "r5_qadd_n7_split_c_ingress_v28"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, default=ROOT / f"artifacts/operator_config_validation/r5-server-test-packages/{NAME}.zip")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, default=Path(r"C:\iverilog\bin\iverilog.exe"))
    args = parser.parse_args()
    gate.INSTALL_NAME = NAME
    gate.ZIP_SHA = gate.sha_file(args.zip)
    gate.ZIP_BYTES = args.zip.stat().st_size
    gate.MEMBERS = {
        "native": f"{NAME}/tb_probe/native_return_observer.svh",
        "shim": f"{NAME}/tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh",
        "tail": f"{NAME}/tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
    }
    sys.argv = [
        gate.__file__,
        "--zip",
        str(args.zip),
        "--output",
        str(args.output),
        "--iverilog",
        str(args.iverilog),
    ]
    return gate.main()


if __name__ == "__main__":
    raise SystemExit(main())
