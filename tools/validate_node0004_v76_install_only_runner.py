from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v75_install_only_runner as wrapper

wrapper.wrapper.validator.INSTALL = "r5_n4_hw_v76_sourcebound_boundfix"
_base_map_harness = wrapper.wrapper.validator.map_harness
_original_temporary_directory = wrapper.wrapper.validator.tempfile.TemporaryDirectory


def _short_temporary_directory(*args, **kwargs):
    kwargs["prefix"] = "n4_"
    return _original_temporary_directory(*args, **kwargs)


wrapper.wrapper.validator.tempfile.TemporaryDirectory = _short_temporary_directory


def map_post_sim_core_harness(package: Path, result_root: Path) -> None:
    """Map the fixed production publication root only in the isolated harness.

    The production ZIP remains byte-exact and hard-coded to
    ``/home/panqs/ndp/simresult``.  The older family harness rewrites the
    runner/runtime publication receipts but predates the shared post-sim core
    helper, whose own request and constant need the same temporary mapping.
    """

    _base_map_harness(package, result_root)
    native_root = result_root.resolve().as_posix()
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = __import__("json").loads(request_path.read_text(encoding="utf-8"))
    if request.get("result_root") != "/home/panqs/ndp/simresult":
        raise ValueError("post-sim request fixed result root differs")
    request["result_root"] = native_root
    request_path.write_text(
        __import__("json").dumps(request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    helper_path = package / "package_tools/server_post_sim_return.py"
    helper = helper_path.read_text(encoding="utf-8")
    old = 'FIXED_RESULT_ROOT = "/home/panqs/ndp/simresult"'
    new = f'FIXED_RESULT_ROOT = {native_root!r}'
    if helper.count(old) != 1:
        raise ValueError("post-sim helper fixed result root token differs")
    helper = helper.replace(old, new, 1)
    long_atomic = 'temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")'
    short_atomic = 'temporary = path.with_name(f".t{os.getpid()}")'
    if helper.count(long_atomic) != 1:
        raise ValueError("post-sim helper atomic JSON token differs")
    helper = helper.replace(long_atomic, short_atomic, 1)
    long_staging = 'tempfile.TemporaryDirectory(prefix=".return_core_", dir=attempt_root)'
    short_staging = 'tempfile.TemporaryDirectory(prefix=".r_", dir=attempt_root)'
    if helper.count(long_staging) != 1:
        raise ValueError("post-sim helper staging token differs")
    helper_path.write_text(
        helper.replace(long_staging, short_staging, 1),
        encoding="utf-8",
        newline="\n",
    )
    wrapper.wrapper._refresh_manifest(package)


wrapper.wrapper.validator.map_harness = map_post_sim_core_harness


if __name__ == "__main__":
    raise SystemExit(wrapper.wrapper.validator.main())
