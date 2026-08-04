from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_gap_node0071_runner_guard_chain as common


ROOT_NAME = "r5_n71_gap_v11_runner_rule"
OBSERVER_SHA256 = (
    "0a1621d2f09c0c8a074cf992f61deed7b0a3433608b5e0ae9cb53396619eccc8"
)
WRONG_SHA256 = "f" * 64


class ValidationError(ValueError):
    pass


def validate(target_zip: Path, bash: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(
        prefix=".g71-v11-",
        dir=Path.cwd(),
        ignore_cleanup_errors=True,
    ) as temporary:
        root = Path(temporary)
        package = common.extract(target_zip, ROOT_NAME, root / "fresh")
        observer_sha = common.sha256(
            package / common.OBSERVER_RELATIVE
        )
        runner_text = (package / common.RUNNER_RELATIVE).read_text(
            encoding="utf-8"
        )
        if (
            observer_sha != OBSERVER_SHA256
            or runner_text.count(OBSERVER_SHA256) != 1
            or f'install_name="{ROOT_NAME}"' not in runner_text
        ):
            raise ValidationError("v11 static observer/identity binding differs")

        positive_guard = common.run_guard(package, OBSERVER_SHA256)
        if (
            positive_guard["exit_code"] != 0
            or positive_guard["parsed"].get("valid") is not True
            or positive_guard["parsed"].get("identity_match") is not True
        ):
            raise ValidationError("v11 positive observer guard failed")

        controls: dict[str, Any] = {}
        control_specs = {
            "source_missing": None,
            "incdir_missing": (
                "+incdir+$package_root/tb_probe",
                "+incdir+$package_root/absent_probe",
            ),
            "macro_missing": (
                "+define+NATIVE_RETURN_OBSERVER_ENABLE",
                "+define+NATIVE_RETURN_OBSERVER_DISABLED",
            ),
            "runtime_missing": (
                "+RETURN_OBSERVER",
                "+NO_RETURN_OBSERVER",
            ),
        }
        for name, mutation in control_specs.items():
            control_root = root / f"control_{name}"
            shutil.copytree(package, control_root)
            if name == "source_missing":
                (control_root / common.OBSERVER_RELATIVE).unlink()
            else:
                assert mutation is not None
                common.mutate_runner_term(
                    control_root, mutation[0], mutation[1]
                )
            receipt = common.run_guard(control_root, OBSERVER_SHA256)
            controls[name] = receipt
            if receipt["exit_code"] != 1:
                raise ValidationError(
                    f"negative control did not fail: {name}"
                )

        wrong_guard = common.run_guard(package, WRONG_SHA256)
        controls["wrong_expected_sha"] = wrong_guard
        if wrong_guard["exit_code"] != 1:
            raise ValidationError("wrong expected SHA guard did not fail")

        positive_runner = common.run_runner_mock(
            package, root / "positive_runner", bash
        )
        if (
            positive_runner["exit_code"] != 86
            or not positive_runner["make_reached"]
            or positive_runner["installed_preflight"].get("valid") is not True
            or positive_runner["observer_precompile"].get("valid") is not True
            or not positive_runner["actual_compile_argv_exists"]
        ):
            raise ValidationError(
                "fresh-extract real runner did not reach compile stub"
            )

        wrong_package = root / "wrong_identity_package"
        shutil.copytree(package, wrong_package)
        common.mutate_runner_term(
            wrong_package, OBSERVER_SHA256, WRONG_SHA256
        )
        common.refresh_manifest_file_receipt(
            wrong_package, common.RUNNER_RELATIVE.as_posix()
        )
        wrong_runner = common.run_runner_mock(
            wrong_package, root / "wrong_runner", bash
        )
        if (
            wrong_runner["exit_code"] != 7
            or wrong_runner["make_reached"]
            or wrong_runner["observer_precompile"] is None
            or wrong_runner["observer_precompile"].get("valid") is not False
            or wrong_runner["actual_compile_argv_exists"]
        ):
            raise ValidationError(
                "wrong identity/SHA runner did not fail before compile"
            )

        return {
            "schema":
                "gap-node0071-runner-preflight-to-compile-validation-v11",
            "valid": True,
            "rule_id":
                "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
            "target_zip": str(target_zip),
            "target_zip_sha256": common.sha256(target_zip),
            "fresh_extract_root": ROOT_NAME,
            "positive_guard": positive_guard,
            "positive_full_runner": positive_runner,
            "negative_controls": controls,
            "wrong_identity_full_runner": wrong_runner,
            "compile_stub_unique_expected_exit_code": 86,
            "positive_compile_reached": True,
            "actual_compile_argv_captured": True,
            "wrong_identity_failed_before_compile": True,
            "all_negative_controls_fail_closed": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(
            args.target_zip.resolve(), args.bash.resolve()
        )
        if args.output:
            args.output.write_text(
                json.dumps(
                    result, indent=2, ensure_ascii=False, sort_keys=True
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
    except Exception as error:
        print(f"runner-rule validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
