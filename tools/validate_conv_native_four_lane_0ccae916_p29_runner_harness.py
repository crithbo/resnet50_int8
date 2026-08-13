#!/usr/bin/env python3
"""Run p29 exact runner through the inherited isolated six-scenario harness."""

import json
import tempfile
from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p19_runner_harness as base


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p29_row2own"
SOURCE_ID = "r5_n4_0cc_p28_b5release"
SOURCE_SHA256 = "3b15bf1cebf18b95d07e4c290ccf246d7cd6f89e6b2bd6c9665b05186b2e0066"
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
    base.ROOT = Path(tempfile.gettempdir())

    def mapped_prepare(original_prepare, package, scenario_root, mode):
        value = original(original_prepare, package, scenario_root, mode)
        local_package, _server_root, result_root, _marker, _env = value
        helper = local_package / "package_tools/server_post_sim_return.py"
        request_path = local_package / "contracts/server_post_sim_return_request.json"
        helper_text = helper.read_text(encoding="utf-8")
        old = 'FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"'
        new = f'FIXED_RESULT_ROOT = {str(result_root)!r}'
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
    try:
        return base.main()
    finally:
        base.mapped_prepare = original
        base.ROOT = original_root


if __name__ == "__main__":
    raise SystemExit(main())
