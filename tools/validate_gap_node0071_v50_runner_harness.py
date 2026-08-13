from __future__ import annotations

import importlib.util
import os
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "validate_gap_node0071_v49_runner_harness.py"


def main() -> int:
    spec = importlib.util.spec_from_file_location("gap_v49_runner_harness", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.INSTALL = "r5_n71_gap_v50_ga_ob_conjunction_diag"
    # The inherited harness provides an MSYS-style PATH.  Keep MSYS from
    # converting that already-normalized value back into a malformed Windows
    # search path when launching the exact runner.
    os.environ["MSYS2_ENV_CONV_EXCL"] = "PATH"
    inherited_write_stubs = module.write_stubs

    def write_stubs(stub: Path, python: Path) -> None:
        inherited_write_stubs(stub, python)
        mkdir = stub / "mkdir"
        mkdir.write_text(
            """#!/usr/bin/bash
set -u
parents=0
paths=()
for arg in "$@"; do
  case "$arg" in
    -p|--parents) parents=1 ;;
    --) ;;
    -*) exit 64 ;;
    *) paths+=("$arg") ;;
  esac
done
[ "${#paths[@]}" -gt 0 ] || exit 64
python3 - "$parents" "${paths[@]}" <<'PY'
import pathlib,sys
parents=sys.argv[1]=="1"
for raw in sys.argv[2:]:
    pathlib.Path(raw).mkdir(parents=parents,exist_ok=parents)
PY
""",
            encoding="utf-8",
            newline="\n",
        )
        mkdir.chmod(0o755)

    module.write_stubs = write_stubs
    inherited_map_harness = module.map_harness

    def map_harness(package: Path, result_root: Path) -> None:
        inherited_map_harness(package, result_root)
        runner = package / "PREPARE_AND_RUN.sh"
        text = runner.read_text(encoding="utf-8")
        prefix = "#!/usr/bin/env bash\n"
        if not text.startswith(prefix):
            raise ValueError("runner shebang differs")
        harness_path = module.msys(package.parent / "stub") + ":/usr/bin:/bin"
        text = text.replace(
            prefix,
            prefix + f"export PATH={harness_path!r}\n",
            1,
        )
        runner.write_text(text, encoding="utf-8", newline="\n")
        module.refresh_manifest(package)

    module.map_harness = map_harness
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
