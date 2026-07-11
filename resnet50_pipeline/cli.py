from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .backends import MockBackend
from .contracts import load_contracts
from .errors import PipelineError
from .manifest import RunManifest
from .pipeline import STAGES, execute_mock_run, manifest_exit_code


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resnet50-pipeline",
        description="ResNet50 INT8 auditable integration pipeline",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("probe", help="show W0 backend capabilities")
    subparsers.add_parser("validate-contracts", help="validate required W0 contracts")

    mock = subparsers.add_parser("mock-run", help="run the complete W0 stage DAG")
    mock.add_argument("--output", type=Path, default=project_root() / "artifacts" / "w0")
    mock.add_argument("--input", type=Path)
    mock.add_argument("--fail-stage", choices=STAGES)
    mock.add_argument("--op", default="MockIdentity")
    mock.add_argument("--dtype", default="uint8")
    mock.add_argument("--slice-count", type=int, default=16)
    mock.add_argument("--config-version", default="mock-0.1")
    mock.add_argument("--resume", action="store_true")

    show = subparsers.add_parser("show-manifest", help="validate and summarize a manifest")
    show.add_argument("path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = project_root()
    try:
        if args.command == "probe":
            capabilities = MockBackend().capabilities
            print(json.dumps({
                "name": capabilities.name,
                "version": capabilities.version,
                "ops": sorted(capabilities.ops),
                "dtypes": sorted(capabilities.dtypes),
                "slice_counts": sorted(capabilities.slice_counts),
                "config_versions": sorted(capabilities.config_versions),
                "can_dump_physical_output": capabilities.can_dump_physical_output,
            }, indent=2))
            return 0
        if args.command == "validate-contracts":
            contracts = load_contracts(root / "contracts")
            print(json.dumps({"status": "valid", "digest": contracts.digest}, indent=2))
            return 0
        if args.command == "show-manifest":
            manifest = RunManifest.load(args.path)
            print(json.dumps({
                "run_id": manifest.run_id,
                "status": manifest.status,
                "cache_key": manifest.cache_key,
                "stages": {stage.name: stage.status for stage in manifest.stages},
            }, indent=2))
            return manifest_exit_code(manifest)
        if args.command == "mock-run":
            manifest = execute_mock_run(
                root,
                args.output,
                MockBackend(fail_stage=args.fail_stage),
                input_path=args.input,
                op=args.op,
                dtype=args.dtype,
                slice_count=args.slice_count,
                config_version=args.config_version,
                resume=args.resume,
            )
            print(json.dumps({
                "run_id": manifest.run_id,
                "status": manifest.status,
                "cache_key": manifest.cache_key,
                "output": str((args.output / manifest.run_id).resolve()),
            }, indent=2))
            return manifest_exit_code(manifest)
    except (PipelineError, ValueError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
