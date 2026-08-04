from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_stem_serialized_local_e2 import (  # noqa: E402
    ARTIFACT_ROOT_REL,
    CONFIG_ROOT_REL,
    FINAL_EXECPLAN_REL,
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


def _run(command: list[str], cwd: Path) -> None:
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument(
        "--execplan-only",
        action="store_true",
        help="reuse complete mapping bundles and publish a fresh execplan bundle",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    native = root / "ndp-sim"
    python = root / ".venv/Scripts/python.exe"
    artifact = root / ARTIFACT_ROOT_REL
    mapping_root = artifact / "mapping"
    execplan_root = root / FINAL_EXECPLAN_REL
    if args.execplan_only:
        if (
            execplan_root.exists()
            or not mapping_root.is_dir()
            or any(
                not (mapping_root / op_id(wave) / "bundle_manifest.json").is_file()
                for wave in range(3)
            )
        ):
            print(
                "error: execplan-only requires complete mappings and a fresh execplan path",
                file=sys.stderr,
            )
            return 1
    elif mapping_root.exists() or execplan_root.exists():
        print("error: native evidence outputs must be fresh", file=sys.stderr)
        return 1
    try:
        with tempfile.TemporaryDirectory(prefix="r5-stem-native-") as temp_text:
            clean = Path(temp_text) / "ndp-sim"
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
                root,
            )
            _run(["git", "checkout", "--force", "HEAD"], clean)
            mappings: dict[str, Path] = {}
            for wave in range(3):
                current = op_id(wave)
                output = mapping_root / current
                mappings[current] = output
                if not args.execplan_only:
                    create_mapping_evidence_bundle(
                        ndp_sim_root=clean,
                        config_path=root / CONFIG_ROOT_REL / f"wave-{wave}.json",
                        output_dir=output,
                        python_executable=python,
                        seed=42,
                        heuristic_iterations=20_000,
                        heuristic_restarts=20,
                        timeout_seconds=600,
                        patchset_manifest_path=root / PATCHSET_REL,
                    )
            result = create_execplan_evidence_bundle(
                ndp_sim_root=clean,
                graph_path=root / GRAPH_REL,
                mapping_bundles=mappings,
                output_dir=execplan_root,
                python_executable=python,
                timeout_seconds=600,
                patchset_manifest_path=root / PATCHSET_REL,
            )
        print(
            json.dumps(
                {
                    "valid": result.valid,
                    "execplan": str(result.output_dir),
                    "execplan_sha256": result.execplan_sha256,
                    "deterministic_file_count": result.deterministic_file_count,
                },
                indent=2,
            )
        )
    except Exception as error:
        if mapping_root.exists() and not args.execplan_only:
            shutil.rmtree(mapping_root, ignore_errors=True)
        if execplan_root.exists():
            shutil.rmtree(execplan_root, ignore_errors=True)
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
