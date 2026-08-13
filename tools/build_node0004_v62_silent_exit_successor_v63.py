from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v61_pekeep_fix_successor_v62 as base


SOURCE = "r5_n4_hw_v62_pekeep_fix"
INSTALL = "r5_n4_hw_v63_runnerdiag"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE}.zip"
)
SOURCE_SHA = "613eb2a6e4dc14f65065c1a4cd880f0f42828b25a6ebde8383ae78f6d2bdec40"
DEFAULT_OUTPUT = ROOT / "outputs/conv_node0004_v62_silent_exit_v63_successor/build"


class BuildError(RuntimeError):
    pass


def configure_base() -> None:
    base.SOURCE = SOURCE
    base.INSTALL = INSTALL
    base.SOURCE_SHA = SOURCE_SHA
    base.SOURCE_ZIP = SOURCE_ZIP
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT


def replace_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise BuildError(f"runner replacement count {count} for {old!r}")
    return text.replace(old, new)


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "attempt=\"a$$\"\n",
        """attempt="a$$"
runner_fail() {
  rc="$1"
  shift
  printf 'RUNNER_ERROR code=%s package=%s message=%s\\n' \
    "$rc" "$package_id" "$*" >&2
  exit "$rc"
}
""",
    )
    replacements = {
        """if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root" >&2
  exit 2
fi
""": """if [ "$#" -ne 1 ]; then
  runner_fail 2 "expected exactly one server_root argument; usage: bash PREPARE_AND_RUN.sh /absolute/path/to/server_root"
fi
""",
        """case "$1" in /*) ;; *) echo "server_root must be absolute" >&2; exit 2;; esac
""": """case "$1" in /*) ;; *) runner_fail 2 "server_root must be absolute: $1";; esac
""",
        """for tool in python3 timeout make; do command -v "$tool" >/dev/null 2>&1 || exit 3; done
""": """for tool in python3 timeout make; do
  command -v "$tool" >/dev/null 2>&1 || runner_fail 3 "required tool not found: $tool"
done
""",
        """package_root="$(cd "$package_root" && pwd -P)" || exit 2
""": """package_root="$(cd "$package_root" && pwd -P)" || runner_fail 2 "cannot resolve package_root: $package_root"
""",
        """server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2
""": """server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 "server_root missing or unreadable: $1"
""",
        """mkdir -p -- "$result_root" || exit 9
""": """mkdir -p -- "$result_root" || runner_fail 9 "cannot create fixed result_root: $result_root"
""",
        """[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9
""": """[ -d "$result_root" ] && [ -w "$result_root" ] || runner_fail 9 "fixed result_root is not a writable directory: $result_root"
""",
        """resolved_result_root="$(cd "$result_root" && pwd -P)" || exit 9
""": """resolved_result_root="$(cd "$result_root" && pwd -P)" || runner_fail 9 "cannot resolve fixed result_root: $result_root"
""",
        """[ "$resolved_result_root" = "$result_root" ] || exit 9
""": """[ "$resolved_result_root" = "$result_root" ] || runner_fail 9 "fixed result_root resolves elsewhere: $resolved_result_root"
""",
        """[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || exit 10
""": """[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || runner_fail 10 "return target collision; preserve and move the existing files before retry: $return_zip $return_sha"
""",
        """ndp_pre_snapshot="$(python3 "$runtime" root-snapshot --server-root "$server_root")" || exit 12
""": """ndp_pre_snapshot="$(python3 "$runtime" root-snapshot --server-root "$server_root")" || runner_fail 12 "NDP root pre-snapshot failed: $server_root"
""",
        """  --format shell)" || exit 13
""": """  --format shell)" || runner_fail 13 "install-only V2 layout prepare failed under: $server_root/install"
""",
        """python3 "$runtime" path-budget --package-root "$package_root"   --target-root "$server_root" || exit 8
""": """python3 "$runtime" path-budget --package-root "$package_root"   --target-root "$server_root" || runner_fail 8 "path-budget preflight failed"
""",
        """python3 "$runtime" preflight --package-root "$package_root"   > "$evidence_root/package_preflight.json" || exit 5
""": """python3 "$runtime" preflight --package-root "$package_root"   > "$evidence_root/package_preflight.json" || runner_fail 5 "package preflight failed; see $evidence_root/package_preflight.json"
""",
        """python3 "$runtime" verify-install --package-root "$package_root"   --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" || exit 6
""": """python3 "$runtime" verify-install --package-root "$package_root"   --cfg-root "$cfg_root" > "$evidence_root/install_preflight.json" || runner_fail 6 "installed workload/SCA open preflight failed; see $evidence_root/install_preflight.json"
""",
        """  > "$evidence_root/observer_precompile.json" || exit 7
""": """  > "$evidence_root/observer_precompile.json" || runner_fail 7 "observer precompile guard failed; see $evidence_root/observer_precompile.json"
""",
        """[ "$compile_status" -eq 0 ] || exit "$compile_status"
""": """[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed; see $compile_root/sim_results/compile_driver.log"
""",
    }
    for old, new in replacements.items():
        text = replace_once(text, old, new)
    text = replace_once(
        text,
        """  exit "$final"
}
on_signal() {
""",
        """  printf 'RUNNER_FINAL_STATUS package=%s compile=%s run=%s signal=%s exit=%s return=%s\\n' \
    "$package_id" "$compile_status" "$run_status" "$signal_status" "$final" "$return_zip" >&2
  exit "$final"
}
on_signal() {
""",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def update_metadata(package: Path) -> None:
    readme = package / "README.md"
    readme.write_text(
        "# node0004 v63 runner-visible early-failure successor\n\n"
        "v63 preserves the v62 PE keep-terminal configuration fix and all "
        "numeric/workload/golden/observer/DUT semantics. It uses a fresh "
        "identity and makes every package-owned early runner failure visible "
        "on stderr as `RUNNER_ERROR code=<n> ...`; finalization prints one "
        "`RUNNER_FINAL_STATUS` line. This prevents an existing fixed-result "
        "target or another preflight failure from appearing as a silent exit.\n\n"
        f"Run: `bash {INSTALL}/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{INSTALL}_return.zip`.\n",
        encoding="utf-8",
        newline="\n",
    )
    base.write_json(
        package / "provenance/v62_to_v63_runner_visibility_fix.json",
        {
            "schema": "node0004-v62-to-v63-runner-visibility-fix-v1",
            "source_v62_sha256": SOURCE_SHA,
            "server_attempt": {
                "status": "UNAVAILABLE_AUTHENTICATION_FAILED",
                "ssh_host": "NDP",
                "error": "Permission denied (publickey,password)",
            },
            "most_likely_silent_branch": {
                "exit_code": 10,
                "predicate": "return ZIP or sidecar already exists",
                "why": "v62 used a bare `|| exit 10`; an earlier failed invocation may already have published a partial return",
            },
            "changed_surface": [
                "fresh package/install/return identity",
                "runner stderr diagnostics for every early package-owned failure",
                "single final status line",
                "manifest/runtime SCA identity projection",
            ],
            "frozen": [
                "PE1 keep_last_index=3 configuration",
                "bitstream",
                "mapping",
                "execplan semantics",
                "matrix payloads",
                "numeric/W3/qparams/tail/workload/golden",
                "observer semantics",
                "timeout/backpressure",
                "functional RTL/ISA/hardware/active ndp-sim",
            ],
        },
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "install_name": INSTALL,
            "source_package_sha256": SOURCE_SHA,
            "classification": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "configuration_rebuilt": False,
            "configuration_rebuilt_in_this_successor": False,
            "mapping_rebuilt": False,
            "bitstream_rebuilt": False,
            "execplan_rebuilt": False,
            "sca_semantics_rebuilt": False,
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
    )
    manifest["v62_silent_exit_adjudication"] = {
        "server_fix_attempt": "SSH_AUTHENTICATION_UNAVAILABLE",
        "probable_exit": 10,
        "root_cause_boundary": "RUNNER_EARLY_FAILURE_NOT_PRINTED",
        "fresh_identity_avoids_v62_fixed-return_collision": True,
        "all_early_package_owned_failures_now_print_code_and_reason": True,
    }
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    base.update_path_budget(package)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)


def build_directory(output: Path) -> Path:
    configure_base()
    package = base.build_directory(output)
    patch_runner(package)
    update_metadata(package)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    targets = [
        output / INSTALL,
        output / f"{INSTALL}.zip",
        output / f"{INSTALL}.zip.sha256",
        output / f"{INSTALL}.validation.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite existing v63 target")
    package = build_directory(output)
    zip_path = output / f"{INSTALL}.zip"
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v63-repeat-") as temp:
        repeat = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{INSTALL}.zip"
        base.deterministic_zip(repeat, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v63 deterministic rebuild differs")
    sidecar = output / f"{INSTALL}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v62-to-v63-runner-visibility-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": deterministic,
        "source_v62_sha256": SOURCE_SHA,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "observer_semantics_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action_attempted": True,
        "server_action_succeeded": False,
        "server_action_error": "Permission denied (publickey,password)",
    }
    base.write_json(output / f"{INSTALL}.validation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
