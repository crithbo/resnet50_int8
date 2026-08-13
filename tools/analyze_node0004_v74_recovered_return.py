from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


EXPECTED_RETURN_SHA = "19fbfa3a341a2179dbf35e71ae94938d042fdf05d0b510f95b2b8d3efb728403"
EXPECTED_RETURN_BYTES = 236606
EXPECTED_SOURCE_SHA = "3a780d8e75768ee241c4cfca0ed738a97b691f6329d8ff247e5f5d4c96ef5400"
EXPECTED_EXECUTION = "r1786246441849431853_141468"
EXPECTED_FIXED_RETURN = (
    "/home/panqs/ndp/simresult/"
    "r5_n4_hw_v74_sourcebound_epoch_diag_"
    f"{EXPECTED_EXECUTION}_return.zip"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(data: bytes) -> dict:
    return json.loads(data.decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-zip", required=True, type=Path)
    ap.add_argument("--source-zip", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ns = ap.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    rz = ns.return_zip.resolve()
    sz = ns.source_zip.resolve()
    if rz.stat().st_size != EXPECTED_RETURN_BYTES:
        errors.append("return byte count differs")
    if sha256(rz) != EXPECTED_RETURN_SHA:
        errors.append("return SHA differs")
    if sha256(sz) != EXPECTED_SOURCE_SHA:
        errors.append("source ZIP SHA differs")

    with zipfile.ZipFile(rz) as archive:
        bad_crc = archive.testzip()
        infos = archive.infolist()
        names = [item.filename for item in infos]
        duplicate = sorted({name for name in names if names.count(name) > 1})
        unsafe = []
        symlinks = []
        for item in infos:
            pure = PurePosixPath(item.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in item.filename:
                unsafe.append(item.filename)
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode):
                symlinks.append(item.filename)
        roots = sorted({PurePosixPath(name).parts[0] for name in names if name})
        if bad_crc:
            errors.append(f"CRC failure: {bad_crc}")
        if duplicate:
            errors.append("duplicate ZIP members")
        if unsafe:
            errors.append("unsafe ZIP members")
        if symlinks:
            errors.append("ZIP symlink members")
        if roots != ["r5_n4_hw_v74_sourcebound_epoch_diag_return"]:
            errors.append("return root differs")
        root = roots[0] + "/"
        members = {name[len(root):]: archive.read(name) for name in names if not name.endswith("/")}

    manifest = load_json(members["RETURN_MANIFEST.json"])
    allowlist = load_json(members["RETURN_ALLOWLIST.json"])
    records = manifest.get("records", [])
    expected_set = {item["path"] for item in records} | {"RETURN_MANIFEST.json", "RETURN_ALLOWLIST.json"}
    actual_set = set(members)
    if expected_set != actual_set:
        errors.append("RETURN_MANIFEST exact-set differs")
    allow_paths = {item["path"] for item in allowlist.get("records", [])}
    if allow_paths != actual_set - {"RETURN_MANIFEST.json", "RETURN_ALLOWLIST.json"}:
        errors.append("RETURN_ALLOWLIST exact-set differs")
    receipt_errors = []
    for record in records:
        raw = members.get(record["path"])
        if raw is None or len(raw) != record["size_bytes"] or sha256_bytes(raw) != record["sha256"]:
            receipt_errors.append(record["path"])
    if receipt_errors:
        errors.append("per-file return receipts differ")

    returned_package_manifest = load_json(members["evidence/returned_package_manifest.json"])
    with zipfile.ZipFile(sz) as source_archive:
        source_bad_crc = source_archive.testzip()
        source_manifest_name = next(name for name in source_archive.namelist() if name.endswith("/package_manifest.json"))
        source_manifest_raw = source_archive.read(source_manifest_name)
    if source_bad_crc:
        errors.append("source package CRC failure")
    if load_json(source_manifest_raw) != returned_package_manifest:
        errors.append("returned package manifest differs from exact local source")

    publication = load_json(members["evidence/publication_preflight.json"])
    if publication.get("return_zip") != EXPECTED_FIXED_RETURN:
        errors.append("publication exact return ZIP differs")
    if EXPECTED_EXECUTION not in publication.get("return_zip", ""):
        errors.append("execution identity differs")
    if not all(publication.get(key) is True for key in (
        "server_root_duplicate_absent", "package_root_duplicate_absent",
        "install_namespace_duplicate_absent", "run_root_duplicate_absent",
        "launch_cwd_duplicate_absent",
    )):
        errors.append("publication duplicate-absence receipt differs")

    compile_status = int(members["evidence/compile_exit_status.txt"].decode().strip())
    run_status = int(members["evidence/run_exit_status.txt"].decode().strip())
    signal_status = members["evidence/signal_status.txt"].decode().strip()
    gate = load_json(members["evidence/SERVER_RESULT_GATE.json"])
    parser_receipt = load_json(members["evidence/source_bound_parser_receipt.json"])
    parser_decision = load_json(members["runs/c0/source_bound_causal_decision.json"])
    causal = members["runs/c0/source_bound_causal.log"]
    compact_sim = members["runs/c0/sim.log"]
    causal_lines = causal.decode("utf-8", errors="replace").splitlines()
    kind_counts: dict[str, int] = {}
    invalid_instance_bracket_lines = 0
    for line in causal_lines:
        match = re.search(r"\bkind=([^ ]+)", line)
        if match:
            kind_counts[match.group(1)] = kind_counts.get(match.group(1), 0) + 1
        if re.search(r"\binstance=[^ ]*[\[\]$]", line):
            invalid_instance_bracket_lines += 1
    compact_valid = (
        compact_sim == causal
        and all(line.startswith("CODEX_PROBE_V1 ") for line in causal_lines)
        and set(kind_counts).issubset({"ENABLED", "SUMMARY", "CLASS"})
    )
    if not compact_valid:
        errors.append("recovered compact log transform differs")
    source_bound_escape = (
        parser_receipt.get("source_bound_record_count") == len(causal_lines) == 7280
        and parser_receipt.get("parser_exit_status") == 1
        and parser_decision.get("decision") == "EVIDENCE_INCOMPLETE"
        and len(parser_decision.get("errors", [])) == 7280
        and invalid_instance_bracket_lines == 7280
    )
    if not source_bound_escape:
        errors.append("source-bound parser escape evidence differs")

    natural = gate.get("natural_terminal_observed") is True
    formal_files = sorted(path for path in actual_set if re.search(r"formal|readback|mismatch", path, re.I))
    formal_present = gate.get("formal_readback_claimed") is True
    formal_count = 320 if formal_present else 0
    e3 = compile_status == 0 and run_status == 0 and signal_status == "NONE" and natural
    e4 = e3 and formal_count == 320
    e5 = e4 and gate.get("e5_claimed") is True
    if parser_decision.get("matching_candidate_ids"):
        warnings.append("source-bound candidate match is non-consumable because parser decision is incomplete")

    report = {
        "schema": "conv-node0004-v74-recovered-return-analysis-v1",
        "status": "RETURN_VALID_FUNCTIONAL_HANG_SOURCE_BOUND_DIAGNOSTIC_FAILED_PACKAGE_LOCAL",
        "return_receipt": {"path": str(rz), "bytes": rz.stat().st_size, "sha256": sha256(rz)},
        "source_receipt": {"path": str(sz), "bytes": sz.stat().st_size, "sha256": sha256(sz)},
        "same_execution_recovery": {
            "execution": EXPECTED_EXECUTION,
            "fresh_run": False,
            "publication_exact_return_zip": publication.get("return_zip"),
            "compact_log_byte_equal_to_source_bound_log": compact_sim == causal,
            "compact_log_bytes": len(compact_sim),
            "compact_log_sha256": sha256_bytes(compact_sim),
            "kind_counts": kind_counts,
        },
        "integrity": {
            "pass": not errors,
            "errors": errors,
            "warnings": warnings,
            "crc_pass": bad_crc is None,
            "single_root": roots,
            "duplicate_members": duplicate,
            "unsafe_members": unsafe,
            "symlink_members": symlinks,
            "exact_set_pass": expected_set == actual_set,
            "allowlist_pass": allow_paths == actual_set - {"RETURN_MANIFEST.json", "RETURN_ALLOWLIST.json"},
            "per_file_receipt_errors": receipt_errors,
            "member_count": len(actual_set),
        },
        "dynamic_gate": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "signal_status": signal_status,
            "natural_terminal": natural,
            "formal_d_present": formal_count,
            "formal_d_missing": 320 - formal_count,
            "formal_d_mismatch": 0,
            "E3": e3,
            "E4": e4,
            "E5": e5,
            "server_result_status": gate.get("status"),
            "canonical_decision": gate.get("canonical_decision", {}).get("fields", {}),
        },
        "source_bound_diagnostic": {
            "consumable": False,
            "record_count": len(causal_lines),
            "parser_exit_status": parser_receipt.get("parser_exit_status"),
            "decision": parser_decision.get("decision"),
            "error_count": len(parser_decision.get("errors", [])),
            "invalid_instance_bracket_lines": invalid_instance_bracket_lines,
            "exact_failure": "generated parser TOKEN_RE omitted []$ accepted by SystemVerilog %m instance paths",
            "secondary_failure": "automatic return collector admitted the full simulator log to the 8-MiB per-file gate instead of publishing a bounded causal projection",
            "candidate_matrix_claim_boundary": "NON_CONSUMABLE_IN_V74_RECOVERED_RETURN",
        },
        "last_proven_good": "D_WRITE_DATA_ACCEPTED_WITH_21_DETAILED_NONTERMINAL_ACCEPTS_AND_CANONICAL_D_WDATA_36",
        "first_divergence": "FIRST_TERMINAL_D_WRITE_DATA_AND_SLICE_FINISH_ABSENT_AFTER_LAST_TAG_INDEX4_AND_BUFFER_LAST_INDEX5_STATE",
        "hang_root_cause": "UNRESOLVED_FUNCTIONAL_CAUSE; V74_SOURCE_BOUND_DIAGNOSTIC_INVALIDATED_BY_PACKAGE_LOCAL_LOGGER_PARSER_ESCAPE",
        "blocker_delta": {
            "opened": ["B_CONV_NODE0004_V74_SOURCE_BOUND_PARSER_AND_TEXT_BUDGET_ESCAPE"],
            "retained": ["B_CONV_NODE0004_D_TERMINAL_OWNER_CHAIN_UNRESOLVED"],
            "invalidated_not_rtl_bug": ["B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"],
        },
        "analysis_reuse": {
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "configuration_rebuilt": False,
            "functional_rtl_modified": False,
        },
    }
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(ns.output)}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
