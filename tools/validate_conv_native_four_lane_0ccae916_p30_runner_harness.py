#!/usr/bin/env python3
"""Run p30 exact runner through the isolated six-scenario harness."""

import json
import faulthandler
import sys
import tempfile
import traceback
from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p19_runner_harness as base


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p30_bankvalid"
SOURCE_ID = "r5_n4_0cc_p29_row2own"
SOURCE_SHA256 = "43cfd63753ee964a92efec955f1dcba05c772c659406bd0142da8e37d2bd0f49"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"


def main() -> int:
    base.PACKAGE_ID = PACKAGE_ID
    base.SOURCE_ID = SOURCE_ID
    base.SOURCE_SHA256 = SOURCE_SHA256
    base.SOURCE_ZIP = SOURCE_ZIP
    base.INPUT_PREFIX = f"install/cfg_pkg/{PACKAGE_ID}/"
    base.OLD_INPUT_PREFIX = f"install/cfg_pkg/{SOURCE_ID}/"
    base.OLD_OUTPUT_PREFIX = f"install/codex_runs/{SOURCE_ID}/a0/c0/d/"
    base.OUTPUT_PREFIX = f"install/codex_runs/{PACKAGE_ID}/a0/c0/d/"

    original = base.mapped_prepare
    original_root = base.ROOT
    original_tempfile_module = base.tempfile
    original_temporary_directory = tempfile.TemporaryDirectory

    class ShortHarnessTempfile:
        @staticmethod
        def TemporaryDirectory(*_args, **_kwargs):
            return original_temporary_directory(prefix=".r", dir=tempfile.gettempdir())

    # Keep the Windows-only harness below MAX_PATH by shortening only its outer
    # temporary prefix. Production runner paths and exact ZIP bytes are unchanged.
    base.tempfile = ShortHarnessTempfile
    base.ROOT = Path(tempfile.gettempdir())

    def mapped_prepare(original_prepare, package, scenario_root, mode):
        value = original(original_prepare, package, scenario_root, mode)
        local_package, _server_root, result_root, _marker, _env = value
        helper = local_package / "package_tools/server_post_sim_return.py"
        request_path = local_package / "contracts/server_post_sim_return_request.json"
        helper_text = helper.read_text(encoding="utf-8")
        old = 'FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"'
        new = f"FIXED_RESULT_ROOT = {str(result_root)!r}"
        if helper_text.count(old) != 1:
            raise base.HarnessError("shared post-sim fixed result anchor differs")
        helper.write_text(helper_text.replace(old, new, 1), encoding="utf-8", newline="\n")
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["result_root"] = str(result_root)
        request_path.write_text(
            json.dumps(request, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return value

    base.mapped_prepare = mapped_prepare
    harness_arg = Path(sys.argv[sys.argv.index("--harness-output") + 1])
    progress = harness_arg.with_name(harness_arg.stem + ".progress.json")
    original_scenario = base.unique_runner_scenario
    original_layout = base.validate_layout

    def mark(stage, **extra):
        progress.parent.mkdir(parents=True, exist_ok=True)
        progress.write_text(
            json.dumps({"stage": stage, **extra}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def traced_scenario(package, harness_root, mode):
        mark("scenario_started", mode=mode)
        value = original_scenario(package, harness_root, mode)
        mark("scenario_completed", mode=mode, valid=value.get("valid"))
        return value

    def traced_layout(*args, **kwargs):
        mark("shared_layout_started")
        value = original_layout(*args, **kwargs)
        mark("shared_layout_completed", passed=value.get("pass"), errors=value.get("errors"))
        return value

    base.unique_runner_scenario = traced_scenario
    base.validate_layout = traced_layout
    trace_path = harness_arg.with_name(harness_arg.stem + ".stack.txt")
    trace_stream = trace_path.open("w", encoding="utf-8")
    faulthandler.dump_traceback_later(15, repeat=True, file=trace_stream)
    mark("base_main_started")
    try:
        try:
            return base.main()
        except Exception as error:
            output = None
            if "--harness-output" in sys.argv:
                output = Path(sys.argv[sys.argv.index("--harness-output") + 1])
            if output is not None:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    json.dumps({
                        "schema": "conv-native-four-lane-p30-runner-harness-error-v1",
                        "valid": False,
                        "error_type": type(error).__name__,
                        "error": str(error),
                        "traceback": traceback.format_exc(),
                    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
            raise
    finally:
        faulthandler.cancel_dump_traceback_later()
        trace_stream.close()
        base.mapped_prepare = original
        base.ROOT = original_root
        base.tempfile = original_tempfile_module
        base.unique_runner_scenario = original_scenario
        base.validate_layout = original_layout


if __name__ == "__main__":
    raise SystemExit(main())
