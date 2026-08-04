from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT_NAME = "r5_n71_gap_v14_accum_enable"
RUNNER = "PREPARE_AND_RUN.sh"


class ValidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def read_zip(target: Path) -> tuple[str, dict[str, Any]]:
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None:
            raise ValidationError("ZIP CRC differs")
        names: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or info.filename in names
            ):
                raise ValidationError(f"unsafe ZIP member: {info.filename}")
            names.add(info.filename)
        runner = archive.read(f"{ROOT_NAME}/{RUNNER}")
        manifest_payload = archive.read(
            f"{ROOT_NAME}/TEST_PACKAGE_MANIFEST.json"
        )
    manifest = json.loads(manifest_payload.decode("utf-8"))
    receipt = manifest["files"][RUNNER]
    if (
        receipt["sha256"] != sha256_bytes(runner)
        or receipt["size_bytes"] != len(runner)
    ):
        raise ValidationError("runner manifest receipt differs")
    return runner.decode("utf-8"), manifest


def validate_text(text: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    sim_block = text.split("sim_args=(", 1)[-1].split("\n)", 1)[0]
    if sim_block.count("+RETURN_OBS_ACCUM_STATE") != 1:
        errors.append("real sim_args accumulator enable differs")
    if sim_block.count("+RETURN_OBS_ACCUM_LIMIT=512") != 1:
        errors.append("real sim_args accumulator limit differs")
    if (
        "grep -Fq 'accum_state=1' \"$observer_log\"" not in text
        or "buffer_to_ga_accum_state_enabled=true" not in text
    ):
        errors.append("runtime returned-enable binding differs")
    if (
        "+RETURN_OBS_ACCUM_STATE +RETURN_OBS_ACCUM_LIMIT=512 "
        "+RETURN_OBS_FILE=<run>" not in text
    ):
        errors.append("server command receipt accumulator binding differs")
    if "+RETURN_OBS_ACCUM_STATE=0" in text:
        errors.append("explicit disabled accumulator probe")
    return not errors, errors


def validate(target: Path) -> dict[str, Any]:
    text, manifest = read_zip(target)
    valid, errors = validate_text(text)
    if not valid:
        raise ValidationError("; ".join(errors))
    controls: dict[str, Any] = {}
    mutations = {
        "sim_enable_removed": text.replace(
            "  +RETURN_OBS_ACCUM_STATE\n", "", 1
        ),
        "sim_limit_removed": text.replace(
            "  +RETURN_OBS_ACCUM_LIMIT=512\n", "", 1
        ),
        "runtime_marker_guard_removed": text.replace(
            " && grep -Fq 'accum_state=1' \"$observer_log\"", "", 1
        ),
        "runtime_receipt_removed": text.replace(
            "buffer_to_ga_accum_state_enabled=true\\n", "", 1
        ),
    }
    for name, mutated in mutations.items():
        control_valid, control_errors = validate_text(mutated)
        controls[name] = {
            "failed_closed": not control_valid,
            "errors": control_errors,
        }
        if control_valid:
            raise ValidationError(f"negative control did not fail: {name}")
    repair = manifest.get("accum_state_enable_repair", {})
    if (
        repair.get("first_divergence")
        != "BUFFER_TO_GA_DIAGNOSTIC_RUNTIME_ENABLE_ABSENT"
        or repair.get("observer_algorithm_changed") is not False
        or repair.get("numeric_workload_changed") is not False
        or repair.get("config_changed") is not False
        or repair.get("golden_changed") is not False
    ):
        raise ValidationError("manifest repair boundary differs")
    return {
        "schema": "gap-node0071-accum-enable-validation-v14",
        "status": "PASS",
        "target_zip": str(target),
        "target_zip_sha256": sha256_bytes(target.read_bytes()),
        "runtime_enable_plusarg": "+RETURN_OBS_ACCUM_STATE",
        "runtime_limit_plusarg": "+RETURN_OBS_ACCUM_LIMIT=512",
        "runtime_marker": "buffer_to_ga_accum_state_enabled=true",
        "observer_algorithm_changed": False,
        "numeric_workload_changed": False,
        "config_changed": False,
        "golden_changed": False,
        "negative_controls": controls,
        "all_negative_controls_fail_closed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target_zip", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.target_zip.resolve())
    except Exception as error:
        print(f"v14 accumulator-enable validation failed: {error}")
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
