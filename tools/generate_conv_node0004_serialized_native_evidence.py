from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_serialized_one_product_local_e2 import (  # noqa: E402
    ARTIFACT_ROOT_REL,
    CONFIG_ROOT_REL,
    GRAPH_REL,
    PATCHSET_REL,
    op_id,
)
from resnet50_pipeline.operator_config_evidence_bundle import (  # noqa: E402
    create_mapping_evidence_bundle,
)
from resnet50_pipeline.operator_config_execplan_evidence import (  # noqa: E402
    create_execplan_evidence_bundle,
)


def _run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            completed.stderr.decode("utf-8", errors="replace").strip()
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate mapping/bitstream/execplan/SCA evidence from a clean "
            "disposable clone of the pinned native ndp-sim commit."
        )
    )
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument(
        "--execplan-only",
        action="store_true",
        help="reuse the already published mapping bundles and emit execplan_final",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    native = root / "ndp-sim"
    python = root / ".venv/Scripts/python.exe"
    patchset = root / PATCHSET_REL
    artifact = root / ARTIFACT_ROOT_REL
    frozen_cache = (
        root
        / "artifacts/operator_config_validation/"
        "r5-patched-execplan-evidence/node0004-conv-three-wave-v1/"
        "mapping_evidence/op_w0/mapping_cache/df2e5c93d0c7120d.json"
    )
    mappings_root = artifact / "mapping"
    execplan_root = artifact / (
        "execplan_final" if args.execplan_only else "execplan"
    )
    if args.execplan_only:
        if (
            not mappings_root.is_dir()
            or any(
                not (mappings_root / op_id(wave) / "bundle_manifest.json").is_file()
                for wave in range(3)
            )
            or execplan_root.exists()
        ):
            print(
                "error: execplan-only requires complete mappings and a fresh final path",
                file=sys.stderr,
            )
            return 1
    elif mappings_root.exists() or execplan_root.exists():
        print("error: native evidence outputs must be fresh", file=sys.stderr)
        return 1

    try:
        with tempfile.TemporaryDirectory(prefix="r5-conv-serialized-native-") as tmp:
            clean = Path(tmp) / "ndp-sim"
            _run(
                [
                    "git",
                    "-c",
                    f"safe.directory={native.as_posix()}",
                    "-c",
                    f"safe.directory={(native / '.git').as_posix()}",
                    "clone",
                    "--no-hardlinks",
                    "--no-checkout",
                    str(native),
                    str(clean),
                ],
                cwd=root,
            )
            _run(["git", "checkout", "--force", "HEAD"], cwd=clean)
            mappings: dict[str, Path] = {
                op_id(wave): mappings_root / op_id(wave) for wave in range(3)
            }
            if not args.execplan_only:
                for wave in range(3):
                    current_id = op_id(wave)
                    output = mappings[current_id]
                    create_mapping_evidence_bundle(
                        ndp_sim_root=clean,
                        config_path=root / CONFIG_ROOT_REL / f"wave-{wave}.json",
                        output_dir=output,
                        python_executable=python,
                        seed=42,
                        heuristic_iterations=10_000,
                        heuristic_restarts=10,
                        timeout_seconds=300,
                        patchset_manifest_path=patchset,
                        frozen_cache_path=frozen_cache,
                    )
            result = create_execplan_evidence_bundle(
                ndp_sim_root=clean,
                graph_path=root / GRAPH_REL,
                mapping_bundles=mappings,
                output_dir=execplan_root,
                python_executable=python,
                timeout_seconds=300,
                patchset_manifest_path=patchset,
            )
        print(
            json.dumps(
                {
                    "valid": result.valid,
                    "mapping_bundles": {
                        key: str(value) for key, value in mappings.items()
                    },
                    "execplan_bundle": str(result.output_dir),
                    "execplan_sha256": result.execplan_sha256,
                    "deterministic_file_count": result.deterministic_file_count,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
