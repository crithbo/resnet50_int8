from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import stat
import zipfile
from collections import Counter, defaultdict, deque
from pathlib import Path, PurePosixPath


EXPECTED_RETURN_BYTES = 683874
EXPECTED_RETURN_SHA = "1797f0f684a3e8c69b141167139aa22829b94a8dcc3be01119da1085dba91710"
EXPECTED_SOURCE_SHA = "322214d94af5bdfe75e509612da190a205e7cf4324f9e31dcc6e052bb9b3126c"
PACKAGE_ID = "r5_n4_hw_v75_sourcebound_collectfix"
EXECUTION_ID = "r1786262789619295530_203645"
ROOT_NAME = PACKAGE_ID + "_return"
RETURN_BASENAME = f"{PACKAGE_ID}_{EXECUTION_ID}_return.zip"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_json(value: bytes):
    return json.loads(value.decode("utf-8"))


def fields(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in line.split()[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    return_zip = args.return_zip.resolve()
    source_zip = args.source_zip.resolve()
    errors: list[str] = []

    if return_zip.stat().st_size != EXPECTED_RETURN_BYTES:
        errors.append("return byte count mismatch")
    if sha256(return_zip) != EXPECTED_RETURN_SHA:
        errors.append("return SHA mismatch")
    if sha256(source_zip) != EXPECTED_SOURCE_SHA:
        errors.append("source SHA mismatch")

    with zipfile.ZipFile(source_zip) as source:
        source_crc = source.testzip()
        source_names = source.namelist()
        source_manifest_name = next(
            name for name in source_names if name.endswith("/package_manifest.json")
        )
        request_name = next(
            name
            for name in source_names
            if name.endswith("/contracts/server_post_sim_return_request.json")
        )
        plan_name = next(
            name
            for name in source_names
            if name.endswith("/diagnostics/source_bound_probe_plan.json")
        )
        source_manifest_raw = source.read(source_manifest_name)
        request = load_json(source.read(request_name))
        plan = load_json(source.read(plan_name))
    if source_crc:
        errors.append(f"source CRC failure: {source_crc}")

    with zipfile.ZipFile(return_zip) as archive:
        bad_crc = archive.testzip()
        infos = archive.infolist()
        names = [item.filename for item in infos]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        unsafe: list[str] = []
        symlinks: list[str] = []
        for item in infos:
            pure = PurePosixPath(item.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in item.filename:
                unsafe.append(item.filename)
            if stat.S_ISLNK(item.external_attr >> 16):
                symlinks.append(item.filename)
        roots = sorted({PurePosixPath(name).parts[0] for name in names if name})
        if bad_crc:
            errors.append(f"return CRC failure: {bad_crc}")
        if duplicates:
            errors.append("duplicate return members")
        if unsafe:
            errors.append("unsafe return paths")
        if symlinks:
            errors.append("symlink return members")
        if roots != [ROOT_NAME]:
            errors.append(f"return root mismatch: {roots}")
        prefix = ROOT_NAME + "/"
        members = {
            name[len(prefix) :]: archive.read(name)
            for name in names
            if name.startswith(prefix) and not name.endswith("/")
        }

        manifest = load_json(members["RETURN_CORE_MANIFEST.json"])
        core_status = load_json(members["return_core/RETURN_CORE_STATUS.json"])
        plugin_status = load_json(members["return_core/RETURN_PLUGIN_STATUS.json"])
        sim_exit = load_json(members["return_core/SIM_EXIT_RECEIPT.json"])
        gate = load_json(members["evidence/SERVER_RESULT_GATE.json"])
        returned_manifest_raw = members["evidence/returned_package_manifest.json"]

        plugin_ids = [item["plugin_id"] for item in request["plugins"]]
        generated = {
            "RETURN_CORE_MANIFEST.json",
            "return_core/RETURN_CORE_STATUS.json",
            "return_core/RETURN_PLUGIN_STATUS.json",
            "return_core/SIM_EXIT_RECEIPT.json",
        }
        for plugin_id in plugin_ids:
            generated.update(
                {
                    f"return_core/plugins/{plugin_id}.status.json",
                    f"return_core/plugins/{plugin_id}.stdout.log",
                    f"return_core/plugins/{plugin_id}.stderr.log",
                }
            )
        receipted = {item["path"] for item in manifest["core_entry_receipts"]}
        expected_set = generated | receipted
        actual_set = set(members)
        if expected_set != actual_set:
            errors.append(
                "request/core-manifest derived exact-set mismatch: "
                f"missing={sorted(expected_set-actual_set)} extra={sorted(actual_set-expected_set)}"
            )
        request_allowlist = {item["archive"] for item in request["core_entries"]}
        if not receipted.issubset(request_allowlist):
            errors.append("core manifest contains a path outside request allowlist")
        required_request = {
            item["archive"] for item in request["core_entries"] if item["required"]
        }
        if not required_request.issubset(receipted):
            errors.append("required request core path missing")
        receipt_errors: list[str] = []
        for item in manifest["core_entry_receipts"]:
            data = members.get(item["path"])
            if (
                data is None
                or len(data) != item["bytes"]
                or sha256_bytes(data) != item["sha256"]
            ):
                receipt_errors.append(item["path"])
        if receipt_errors:
            errors.append(f"per-file core receipts mismatch: {receipt_errors}")

        sim_entry = archive.getinfo(prefix + "runs/c0/sim.log")
        kind_counts: Counter[str] = Counter()
        boundary_counts: dict[str, Counter[str]] = defaultdict(Counter)
        enabled: set[str] = set()
        sticky: dict[str, int] = defaultdict(int)
        summaries: dict[str, dict[str, str]] = {}
        ring_tail: dict[str, deque[dict[str, str]]] = defaultdict(lambda: deque(maxlen=8))
        projection_bytes = 0
        record_count = 0
        permitted = {
            "ENABLED",
            "SUMMARY",
            "CLASS",
            "TRIGGER",
            "STALL",
            "RING_PROGRESS",
            "RING_STATE",
            "RING_POST",
        }
        with archive.open(sim_entry) as raw_stream:
            with io.TextIOWrapper(raw_stream, encoding="utf-8", errors="replace") as stream:
                for raw in stream:
                    offset = raw.find("CODEX_PROBE_V1 ")
                    if offset < 0:
                        continue
                    line = raw[offset:].rstrip("\r\n")
                    item = fields(line)
                    kind = item.get("kind", "")
                    if kind not in permitted:
                        continue
                    boundary = item.get("boundary", "<none>")
                    kind_counts[kind] += 1
                    boundary_counts[boundary][kind] += 1
                    record_count += 1
                    projection_bytes += len((line + "\n").encode("utf-8"))
                    if kind == "ENABLED":
                        enabled.add(boundary)
                    if kind == "CLASS" and "mask" in item:
                        try:
                            sticky[boundary] |= int(item["mask"], 16)
                        except ValueError:
                            errors.append(f"invalid class mask at {boundary}")
                    if kind == "SUMMARY":
                        summaries[boundary] = item
                        try:
                            sticky[boundary] |= int(item.get("sticky", "0"), 16)
                        except ValueError:
                            errors.append(f"invalid summary sticky at {boundary}")
                    if kind.startswith("RING_") or kind in {"TRIGGER", "STALL"}:
                        ring_tail[boundary].append(item)

    if returned_manifest_raw != source_manifest_raw:
        errors.append("returned package manifest differs from exact source package")

    if manifest.get("package_id") != PACKAGE_ID or core_status.get("package_id") != PACKAGE_ID:
        errors.append("package identity mismatch")
    if manifest.get("execution_id") != EXECUTION_ID or core_status.get("execution_id") != EXECUTION_ID:
        errors.append("execution identity mismatch")
    if manifest.get("return_basename") != RETURN_BASENAME:
        errors.append("return basename mismatch")

    observations: dict[str, bool] = {}
    boundary_map = {item["boundary_id"]: item for item in plan["boundaries"]}
    for observation in plan["decision_observations"]:
        boundary = observation["boundary_id"]
        if observation["metric"] == "class_seen":
            bit = next(
                item["bit"]
                for item in boundary_map[boundary]["classes"]
                if item["class_id"] == observation["class_id"]
            )
            observations[observation["observation_id"]] = bool(
                sticky.get(boundary, 0) & (1 << bit)
            )
        else:
            observations[observation["observation_id"]] = boundary in summaries
    matches = [item for item in plan["candidates"] if item["signature"] == observations]
    source_bound_decision = (
        matches[0]["root_cause_class"] if len(matches) == 1 else "EVIDENCE_INCOMPLETE"
    )

    plugin = plugin_status[0]
    plugin_stderr = members[
        "return_core/plugins/node0004_source_bound_collect.stderr.log"
    ].decode("utf-8", errors="replace")
    required_core_missing = core_status.get("missing_required_entries", [])
    required_plugin_failures = core_status.get("required_plugin_failures", [])
    plugin_projection_failure = (
        required_core_missing == []
        and required_plugin_failures == ["node0004_source_bound_collect"]
        and plugin.get("exit_code") == 1
        and "bounded source-bound causal projection exceeds 7 MiB" in plugin_stderr
    )
    if not plugin_projection_failure:
        errors.append("required plugin projection failure identity differs")

    compile_status = int(members["evidence/compile_exit_status.txt"].decode().strip())
    run_status = int(members["evidence/run_exit_status.txt"].decode().strip())
    signal_status = members["evidence/signal_status.txt"].decode().strip()
    natural = sim_exit.get("natural_terminal_observed") is True
    formal_d = 320 if gate.get("formal_readback_claimed") is True else 0
    e3 = compile_status == 0 and run_status == 0 and signal_status == "NONE" and natural
    e4 = e3 and formal_d == 320 and gate.get("e4_claimed") is True
    e5 = e4 and gate.get("e5_claimed") is True

    report = {
        "schema": "conv-node0004-v75-formal-return-analysis-v1",
        "status": "FORMAL_RETURN_VALID_REQUIRED_POST_SIM_PLUGIN_FAILED",
        "return_receipt": {
            "path": str(return_zip),
            "bytes": return_zip.stat().st_size,
            "sha256": sha256(return_zip),
        },
        "source_receipt": {
            "path": str(source_zip),
            "bytes": source_zip.stat().st_size,
            "sha256": sha256(source_zip),
        },
        "integrity": {
            "pass": not errors,
            "errors": errors,
            "crc_pass": bad_crc is None,
            "single_root": roots,
            "duplicate_members": duplicates,
            "unsafe_members": unsafe,
            "symlink_members": symlinks,
            "exact_set_pass": expected_set == actual_set,
            "request_derived_allowlist_pass": receipted.issubset(request_allowlist),
            "per_file_receipt_errors": receipt_errors,
            "member_count": len(actual_set),
            "source_manifest_exact": returned_manifest_raw == source_manifest_raw,
        },
        "post_sim_core": {
            "disposition": core_status.get("disposition"),
            "missing_required_entries": required_core_missing,
            "required_plugin_failures": required_plugin_failures,
            "plugin": plugin,
            "plugin_failure_unique": plugin_projection_failure,
            "failure": "bounded source-bound causal projection exceeds 7 MiB",
            "return_publication_independent_of_plugin_success": core_status.get(
                "return_publication_independent_of_plugin_success"
            ),
            "optional_missing": core_status.get("optional_entry_errors", []),
        },
        "dynamic_gate": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "sim_started": sim_exit.get("sim_started"),
            "sim_exit_code": sim_exit.get("sim_exit_code"),
            "natural_terminal": natural,
            "formal_d_present": formal_d,
            "formal_d_missing": 320 - formal_d,
            "formal_d_mismatch": 0,
            "E3": e3,
            "E4": e4,
            "E5": e5,
            "canonical_status": gate.get("status"),
            "canonical_fields": gate.get("canonical_decision", {}).get("fields", {}),
            "install_root_publication_receipts_returned": False,
            "install_root_publication_claim_boundary": "Not allowlisted in the v75 core-return request; source package identity is bound but these dynamic receipts cannot be promoted from this return.",
        },
        "source_bound_offline_recovery": {
            "record_count": record_count,
            "projection_bytes": projection_bytes,
            "projection_limit_bytes": 7 * 1024 * 1024,
            "excess_bytes": projection_bytes - 7 * 1024 * 1024,
            "kind_counts": dict(sorted(kind_counts.items())),
            "boundary_kind_counts": {
                key: dict(sorted(value.items()))
                for key, value in sorted(boundary_counts.items())
            },
            "enabled_boundary_count": len(enabled),
            "summary_boundary_count": len(summaries),
            "observations": observations,
            "matching_candidate_ids": [item["candidate_id"] for item in matches],
            "decision": source_bound_decision,
            "ring_tail": {key: list(value) for key, value in sorted(ring_tail.items())},
            "claim_boundary": "Offline recovery from receipted full sim.log; it does not repair the failed server plugin or satisfy the formal return joint gate.",
        },
        "last_proven_good": "SOURCE_BOUND_LOGGER_EMITTED_RECEIPTED_FULL_LOG_AND_POST_SIM_CORE_RETURN_PUBLISHED",
        "first_divergence": "POST_SIM_SOURCE_BOUND_BOUNDED_PROJECTION_SIZE_GATE_BEFORE_PARSER_PRODUCTS",
        "hang_root_cause": {
            "package_local": "V75_COLLECTOR_RETAINS_TOO_MANY_SOURCE_BOUND_RING_RECORDS_AND_EXCEEDS_7_MIB",
            "functional": source_bound_decision,
        },
        "blocker_delta": {
            "opened": ["B_CONV_NODE0004_V75_POST_SIM_BOUNDED_PROJECTION_OVERFLOW"],
            "retained": ["B_CONV_NODE0004_D_TERMINAL_OWNER_CHAIN_UNRESOLVED"],
            "invalidated_not_rtl_bug": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"],
        },
        "reuse": {
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(args.output)}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
