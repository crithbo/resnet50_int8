from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import node0004_hang_localization_runtime_v12 as runtime


REQUIRED = {
    "evidence/compile_exit_status.txt": b"0\n",
    "runs/c0/simulator_argv.txt": b"simv +RETURN_OBSERVER\n",
    "runs/c0/sim.log": b"simulation started\n",
    "runs/c0/return_observer.log": b"[RETURN_OBSERVER] enabled\n",
    "runs/c0/host_progress.log": b"host_monotonic=1.0\n",
}


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_return(
    root: Path,
    entries: dict[str, bytes],
    *,
    extra: dict[str, bytes] | None = None,
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=False)
    install = "synthetic_return"
    zip_path = root / f"{install}.zip"
    records = [
        {
            "path": name,
            "required": True,
            "size_bytes": len(payload),
            "sha256": _sha(payload),
        }
        for name, payload in sorted(entries.items())
    ]
    allowlist = (
        json.dumps(
            {
                "schema": "synthetic-v12",
                "install_name": "synthetic",
                "records": records,
            },
            sort_keys=True,
        )
        + "\n"
    ).encode()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(entries.items()):
            archive.writestr(f"{install}/{name}", payload)
        archive.writestr(f"{install}/RETURN_ALLOWLIST.json", allowlist)
        for name, payload in sorted((extra or {}).items()):
            archive.writestr(f"{install}/{name}", payload)
    sidecar = Path(str(zip_path) + ".sha256")
    sidecar.write_text(
        f"{runtime.sha256(zip_path)}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return zip_path, sidecar


def _fails(callable_: Any) -> bool:
    try:
        callable_()
    except runtime.base.DiagnosticRuntimeError:
        return True
    return False


def validate() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="node0004-return-gate-v12-") as tmp:
        root = Path(tmp)
        valid_zip, valid_sidecar = _write_return(root / "valid", REQUIRED)
        valid = runtime.validate_return_zip(valid_zip, valid_sidecar)

        missing_entries = dict(REQUIRED)
        missing_entries.pop("runs/c0/host_progress.log")
        missing_zip, missing_sidecar = _write_return(
            root / "missing", missing_entries
        )

        extra_zip, extra_sidecar = _write_return(
            root / "extra", REQUIRED, extra={"not_allowlisted.txt": b"x"}
        )

        per_file_zip, per_file_sidecar = _write_return(
            root / "per-file", REQUIRED
        )
        uncompressed_zip, uncompressed_sidecar = _write_return(
            root / "uncompressed", REQUIRED
        )
        compressed_zip, compressed_sidecar = _write_return(
            root / "compressed", REQUIRED
        )
        sidecar_zip, sidecar_path = _write_return(root / "sidecar", REQUIRED)
        sidecar_path.write_text(
            f"{'0' * 64}  {sidecar_zip.name}\n",
            encoding="ascii",
            newline="\n",
        )

        negatives = {
            "missing_required_progress_after_compile0": _fails(
                lambda: runtime.validate_return_zip(
                    missing_zip, missing_sidecar
                )
            ),
            "extra_member_exact_set": _fails(
                lambda: runtime.validate_return_zip(extra_zip, extra_sidecar)
            ),
            "per_file_budget": _fails(
                lambda: runtime.validate_return_zip(
                    per_file_zip, per_file_sidecar, text_max_bytes=8
                )
            ),
            "aggregate_uncompressed_budget": _fails(
                lambda: runtime.validate_return_zip(
                    uncompressed_zip,
                    uncompressed_sidecar,
                    uncompressed_max_bytes=64,
                )
            ),
            "compressed_budget": _fails(
                lambda: runtime.validate_return_zip(
                    compressed_zip, compressed_sidecar, zip_max_bytes=64
                )
            ),
            "sidecar_mismatch": _fails(
                lambda: runtime.validate_return_zip(
                    sidecar_zip, sidecar_path
                )
            ),
        }

    fallback = runtime._fallback_canonical(
        [
            (
                "1 | PROGRESS_WINDOW | sample=2 qualified_progress=9 delta=3 "
                "req0=1 req1=1 req3=1 rdata0=2 rdata1=2 rdata3=2 "
                "d_req=0 d_wdata=0"
            )
        ],
        "TERM",
    )
    fallback_fields = fallback["fields"]
    fallback_valid = (
        fallback_fields["decision"] == "EVIDENCE_INSUFFICIENT"
        and fallback_fields["reason"]
        == "EXTERNAL_SIGNAL_BEFORE_OBSERVER_CANONICAL"
        and fallback_fields["boundary"]
        == "READ_DATA_TO_D_WRITE_REQUEST_UNRESOLVED_INTERNAL"
        and fallback_fields["qualified_progress"] == 9
        and fallback_fields["content_digest"] == "QIOV1_9_3_2"
        and fallback_fields["signal_status"] == "TERM"
    )
    passed = valid["valid"] and all(negatives.values()) and fallback_valid
    return {
        "schema": "node0004-return-gate-validation-v12",
        "valid": passed,
        "positive": valid,
        "negative_controls": negatives,
        "all_negative_controls_fail_closed": all(negatives.values()),
        "external_signal_canonical_fallback_valid": fallback_valid,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = validate()
    payload = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
