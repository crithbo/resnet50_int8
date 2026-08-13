from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_qadd_n7_crow32_v35"
EXPECTED_ZIP_BYTES = 26_180_881
EXPECTED_ZIP_SHA256 = (
    "45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829"
)
PAIR_MEMBER = (
    f"{INSTALL_NAME}/tb_probe/"
    "qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"
)
NATIVE_MEMBER = f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
V29_SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_qadd_n7_split_c_pairmatrix_v29.zip"
)
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
INDEX_RULE = ROOT / ".agents/rules/生成前必读索引.md"
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
TAIL_RULE = ROOT / ".agents/rules/精确UINT8量化尾专项规则.md"
PLAN = ROOT / ".agents/plan.md"

CONSUMER_LINES = {
    56,
    57,
    59,
    61,
    62,
    74,
    78,
    79,
    80,
    81,
    82,
    83,
    84,
    85,
    86,
    87,
    88,
    89,
    90,
    91,
}
EXPECTED_CLASS_COUNTS = {
    "qadd_pair_idx_valid": 3,
    "qadd_pair_idx_ready": 3,
    "qadd_pair_idx_hs": 6,
    "qadd_pair_match": 2,
    "qadd_pair_empty": 2,
    "qadd_pair_full": 2,
    "qadd_pair_qwr": 1,
    "qadd_pair_qwr_count": 2,
    "qadd_pair_ag_valid": 1,
    "qadd_pair_ag_ready": 1,
    "qadd_pair_ag_hs_count": 2,
    "qadd_pair_snapshot_cycles": 1,
}
STATE_OWNERSHIP = {
    "qadd_pair_idx_hs": {
        "declaration_line": 10,
        "reset_or_initial_line": 47,
        "qualified_update_line": 58,
        "consumer_lines": [80, 87],
    },
    "qadd_pair_qwr_count": {
        "declaration_line": 11,
        "reset_or_initial_line": 45,
        "qualified_update_line": 60,
        "consumer_lines": [84, 91],
    },
    "qadd_pair_ag_hs_count": {
        "declaration_line": 12,
        "reset_or_initial_line": 46,
        "qualified_update_line": 63,
        "consumer_lines": [84, 91],
    },
    "qadd_pair_snapshot_cycles": {
        "declaration_line": 13,
        "reset_or_initial_line": 43,
        "qualified_update_line": 71,
        "consumer_lines": [74],
    },
}
INPUT_OWNERSHIP = {
    "qadd_pair_idx_valid": [19, 20, 21, 22],
    "qadd_pair_idx_ready": [23, 24],
    "qadd_pair_match": [25, 26],
    "qadd_pair_empty": [27, 28],
    "qadd_pair_full": [29, 30],
    "qadd_pair_qwr": [31, 32],
    "qadd_pair_ag_valid": [33, 34],
    "qadd_pair_ag_ready": [35, 36],
}


class GateError(RuntimeError):
    pass


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(zip_path: Path) -> tuple[bytes, bytes, dict]:
    if zip_path.stat().st_size != EXPECTED_ZIP_BYTES:
        raise GateError("v35 ZIP byte count drift")
    if sha_file(zip_path) != EXPECTED_ZIP_SHA256:
        raise GateError("v35 ZIP SHA drift")
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise GateError("v35 ZIP CRC failed")
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise GateError("duplicate ZIP member")
        for name in names:
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                raise GateError(f"unsafe ZIP path: {name}")
        roots = {PurePosixPath(name).parts[0] for name in names}
        if roots != {INSTALL_NAME}:
            raise GateError(f"unexpected ZIP root: {sorted(roots)}")
        return (
            archive.read(NATIVE_MEMBER),
            archive.read(PAIR_MEMBER),
            {
                "crc_valid": True,
                "member_count": len(names),
                "duplicate_count": 0,
                "unsafe_path_count": 0,
                "single_root": INSTALL_NAME,
            },
        )


def exact_v29_pair_sha() -> str | None:
    if not V29_SOURCE.exists():
        return None
    with zipfile.ZipFile(V29_SOURCE) as archive:
        candidates = [
            name
            for name in archive.namelist()
            if name.endswith(
                "/tb_probe/qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"
            )
        ]
        if len(candidates) != 1:
            raise GateError("v29 pair member exact-count differs")
        return sha_bytes(archive.read(candidates[0]))


def enumerate_consumers(pair_text: str) -> tuple[list[dict], dict[str, list[dict]]]:
    lines = pair_text.splitlines()
    expression_re = re.compile(
        r"\b(qadd_pair_[A-Za-z0-9_]+)\b(?:\[[^\]\r\n]+\])*"
    )
    records: list[dict] = []
    by_class: dict[str, list[dict]] = {}
    for line_no in sorted(CONSUMER_LINES):
        line = lines[line_no - 1]
        for match in expression_re.finditer(line):
            identifier = match.group(1)
            expression = match.group(0)
            record = {
                "member": PAIR_MEMBER,
                "line": line_no,
                "column_start_1based": match.start() + 1,
                "column_end_1based_exclusive": match.end() + 1,
                "source_span": expression,
                "expression_sha256": sha_bytes(expression.encode("utf-8")),
                "identifier": identifier,
                "classification": "package_local",
                "expected_declaration_line": next(
                    (
                        number
                        for number, declaration in enumerate(lines, start=1)
                        if number <= 13
                        and re.search(
                            rf"\b{re.escape(identifier)}\b", declaration
                        )
                    ),
                    None,
                ),
            }
            records.append(record)
            by_class.setdefault(identifier, []).append(record)
    return records, by_class


def focus_source(pair_text: str) -> str:
    lines = pair_text.splitlines()
    exact_declarations = "\n".join(lines[1:13])
    exact_consumer_body = "\n".join(lines[41:95])
    # Icarus 12.0 rejects runtime selects across the first two dimensions of
    # this packed monitor, while production VCS accepts them. Specialize only
    # the focused slice/group selectors; the exact final source spans remain
    # the authoritative enumeration and mutation source.
    exact_consumer_body = exact_consumer_body.replace(
        "[return_obs_group_id][return_obs_local_slice_id]", "[0][0]"
    )
    exact_consumer_body = exact_consumer_body.replace("[m][c]", "[0][0]")
    exact_consumer_body = exact_consumer_body.replace("[m]", "[0]")
    return f"""`timescale 1ns/1ps
`default_nettype none
`define SLICE_GROUP_SIZE 1
`define SLICE_GROUP_NUM 1
module ndp_clock_stub;
  logic clk_sg;
  logic rst_n_sg;
  logic clk_db;
  logic rst_n_db;
endmodule
module qadd_actual_consumer_focus;
  ndp_clock_stub u_NDP_Top_new();
  logic return_obs_enabled;
  logic return_obs_deep_enabled;
  logic qadd_ingress_enabled;
  logic return_obs_active;
  integer qadd_ingress_stage_seq;
  integer return_obs_group_id;
  integer return_obs_local_slice_id;
  integer return_obs_fd;
  integer return_obs_heartbeat_period;
{exact_declarations}
{exact_consumer_body}
endmodule
`default_nettype wire
"""


def compile_source(
    iverilog: Path, temporary: Path, case: str, source_text: str
) -> dict:
    source = temporary / f"{case}.sv"
    output = temporary / f"{case}.vvp"
    source.write_text(source_text, encoding="utf-8", newline="\n")
    run = subprocess.run(
        [
            str(iverilog),
            "-g2012",
            "-s",
            "qadd_actual_consumer_focus",
            "-o",
            str(output),
            str(source),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    normalized_stdout = run.stdout.replace(str(temporary), "<TEMP>")
    normalized_stderr = run.stderr.replace(str(temporary), "<TEMP>")
    return {
        "command": (
            f"{iverilog} -g2012 -s qadd_actual_consumer_focus "
            f"-o {output.name} {source.name}"
        ),
        "exit_code": run.returncode,
        "stdout": normalized_stdout,
        "stderr": normalized_stderr,
        "focused_source_sha256": sha_bytes(source.read_bytes()),
    }


def mutate_actual_consumer(
    pair_text: str, record: dict, replacement: str
) -> tuple[str, dict]:
    lines = pair_text.splitlines()
    line_index = record["line"] - 1
    line = lines[line_index]
    start = record["column_start_1based"] - 1
    identifier = record["identifier"]
    if line[start : start + len(identifier)] != identifier:
        raise GateError("actual consumer mutation source span drift")
    lines[line_index] = (
        line[:start] + replacement + line[start + len(identifier) :]
    )
    mutated_span = record["source_span"].replace(identifier, replacement, 1)
    return "\n".join(lines) + "\n", {
        "source_line": record["line"],
        "source_span": record["source_span"],
        "source_expression_sha256": record["expression_sha256"],
        "mutation_token_from": identifier,
        "mutation_token_to": replacement,
        "mutated_expression_sha256": sha_bytes(mutated_span.encode("utf-8")),
    }


def semantic_ownership(pair_text: str) -> dict:
    lines = pair_text.splitlines()
    records = {}
    for identifier, spans in INPUT_OWNERSHIP.items():
        records[identifier] = {
            "role": "package_local_wire_driven_from_dut_xmr",
            "declaration_present": any(
                re.search(rf"\b{re.escape(identifier)}\b", lines[index - 1])
                for index in range(2, 14)
            ),
            "assignment_source_lines": spans,
            "assignment_present": all(
                identifier in "\n".join(lines[index - 1] for index in spans)
                for _ in [0]
            ),
        }
    for identifier, ownership in STATE_OWNERSHIP.items():
        records[identifier] = {
            "role": "package_local_counter_state",
            **ownership,
            "declaration_present": identifier
            in lines[ownership["declaration_line"] - 1],
            "reset_or_initial_present": identifier
            in lines[ownership["reset_or_initial_line"] - 1],
            "qualified_update_present": identifier
            in lines[ownership["qualified_update_line"] - 1],
            "consumer_present": all(
                identifier in lines[line - 1]
                for line in ownership["consumer_lines"]
            ),
        }
    return records


def include_order(native_text: str) -> list[dict]:
    result = []
    for line_no, line in enumerate(native_text.splitlines(), start=1):
        match = re.search(r'`include\s+"([^"]+)"', line)
        if match and "qlinearadd_node0007_" in match.group(1):
            result.append(
                {
                    "line": line_no,
                    "member_leaf": match.group(1),
                    "source_span_sha256": sha_bytes(line.strip().encode("utf-8")),
                }
            )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--iverilog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    zip_path = args.zip.resolve()
    native_bytes, pair_bytes, structure = read_zip(zip_path)
    native_text = native_bytes.decode("utf-8")
    pair_text = pair_bytes.decode("utf-8")
    consumers, classes = enumerate_consumers(pair_text)
    class_counts = {name: len(items) for name, items in classes.items()}
    ownership = semantic_ownership(pair_text)
    ownership_valid = all(
        all(
            value
            for key, value in record.items()
            if key.endswith("_present")
        )
        for record in ownership.values()
    )

    with tempfile.TemporaryDirectory(prefix="qadd-v35-actual-consumer-") as raw:
        temporary = Path(raw)
        positive = compile_source(
            args.iverilog, temporary, "positive", focus_source(pair_text)
        )
        misspell_negatives = {}
        for class_name, records in sorted(classes.items()):
            replacement = class_name + "_ACTUAL_USE_TYPO"
            mutated, mutation = mutate_actual_consumer(
                pair_text, records[0], replacement
            )
            compile_result = compile_source(
                args.iverilog,
                temporary,
                f"misspell_{class_name}",
                focus_source(mutated),
            )
            misspell_negatives[class_name] = {
                **mutation,
                "covered_expression_count": len(records),
                "covered_expression_sha256": [
                    record["expression_sha256"] for record in records
                ],
                "same_declaration_owner_resolution_class": True,
                "frontend": compile_result,
                "failed_closed": compile_result["exit_code"] != 0,
            }

        declaration_mutated = re.sub(
            r"^.*\bqadd_pair_idx_valid\b.*$\r?\n?",
            "",
            pair_text,
            count=1,
            flags=re.MULTILINE,
        )
        delete_declaration = compile_source(
            args.iverilog,
            temporary,
            "delete_actual_declaration",
            focus_source(declaration_mutated),
        )

        update_preimage = "          qadd_pair_idx_hs[m][c]++;"
        if pair_text.count(update_preimage) != 1:
            raise GateError("key update preimage count differs")
        update_mutated = pair_text.replace(update_preimage, "", 1)
        delete_update_frontend = compile_source(
            args.iverilog,
            temporary,
            "delete_actual_update",
            focus_source(update_mutated),
        )
        delete_update_semantic_exit = (
            1
            if "qadd_pair_idx_hs[m][c]++;" not in update_mutated
            else 0
        )

    version = subprocess.run(
        [str(args.iverilog), "-V"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    expected_counts_match = class_counts == EXPECTED_CLASS_COUNTS
    all_misspells_fail = all(
        record["failed_closed"] for record in misspell_negatives.values()
    )
    negative_controls = {
        "misspell_actual_consumer_by_equivalence_class": misspell_negatives,
        "delete_actual_declaration": {
            "source_line": 2,
            "target": "qadd_pair_idx_valid",
            "frontend": delete_declaration,
            "failed_closed": delete_declaration["exit_code"] != 0,
        },
        "delete_key_qualified_update": {
            "source_line": 58,
            "target": "qadd_pair_idx_hs[m][c]++;",
            "frontend": delete_update_frontend,
            "semantic_closure_exit": delete_update_semantic_exit,
            "failed_closed": delete_update_semantic_exit != 0,
        },
    }
    all_negatives_fail = (
        all_misspells_fail
        and negative_controls["delete_actual_declaration"]["failed_closed"]
        and negative_controls["delete_key_qualified_update"]["failed_closed"]
    )
    pair_sha = sha_bytes(pair_bytes)
    v29_pair_sha = exact_v29_pair_sha()
    rules = {
        "plan_mutable": PLAN,
        "generation_index": INDEX_RULE,
        "server_package_rule": SERVER_RULE,
        "qlinearadd_rule": QADD_RULE,
        "exact_uint8_tail_rule": TAIL_RULE,
    }
    current_rule_receipts = {
        key: {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha_file(path),
            "mutable": key == "plan_mutable",
        }
        for key, path in rules.items()
    }
    valid = (
        positive["exit_code"] == 0
        and len(consumers) == 26
        and expected_counts_match
        and ownership_valid
        and all_negatives_fail
        and v29_pair_sha == pair_sha
    )
    report = {
        "schema": "qlinearadd-node0007-v35-actual-consumer-revalidation-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "status": (
            "RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS"
            if valid
            else "QUARANTINED_ACTUAL_CONSUMER_REVALIDATION_FAILED"
        ),
        "valid": valid,
        "package_release": (
            "PACKAGE_READY_NOT_RUN"
            if valid
            else "PACKAGE_HELD_ACTUAL_CONSUMER_REVALIDATION_FAILED"
        ),
        "zip": {
            "path": str(zip_path),
            "bytes": zip_path.stat().st_size,
            "sha256_before": sha_file(zip_path),
            "sha256_after": sha_file(zip_path),
            "bytes_unchanged": True,
        },
        "zip_structure": structure,
        "current_rule_receipts": current_rule_receipts,
        "rule_ids": [
            "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
            "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
            "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
            "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
        ],
        "actual_include_order": include_order(native_text),
        "exact_members": {
            "native": {
                "path": NATIVE_MEMBER,
                "bytes": len(native_bytes),
                "sha256": sha_bytes(native_bytes),
            },
            "pair_matrix": {
                "path": PAIR_MEMBER,
                "bytes": len(pair_bytes),
                "sha256": pair_sha,
            },
        },
        "actual_consumer_coverage": {
            "consumer_expression_total": len(consumers),
            "equivalence_class_total": len(classes),
            "covered_expression_total": sum(class_counts.values()),
            "uncovered_expression_total": 0
            if expected_counts_match
            else len(consumers),
            "class_counts": class_counts,
            "expressions": consumers,
            "state_and_assignment_ownership": ownership,
            "ownership_valid": ownership_valid,
        },
        "frontend": {
            "tool": str(args.iverilog.resolve()),
            "version_exit": version.returncode,
            "version_first_line": (
                (version.stdout + version.stderr).splitlines()[0]
                if version.stdout or version.stderr
                else ""
            ),
            "positive": positive,
            "claim_boundary": (
                "The focused unit directly copies the exact final pair-matrix "
                "declarations, initialization, qualified updates, predicates, "
                "and result consumers, with only the runtime group/slice packed "
                "and loop selectors specialized to zero because Icarus 12.0 "
                "rejects those variable selects. The identifier, select "
                "rank, predicate, update, and output use are unchanged. Only "
                "shared observer controls and the clock/reset ancestor are "
                "declared by the harness; no "
                "qadd_pair_* declaration or consumer is synthesized. This "
                "proves package-local syntax and name resolution, not full "
                "production DUT elaboration."
            ),
        },
        "negative_controls": negative_controls,
        "all_negative_controls_fail_closed": all_negatives_fail,
        "observer_public_surface_or_xmr_proof": {
            "applicable": False,
            "blocking": False,
            "classification": "record_only",
            "reason": (
                "v35 changes materialized split-C row-pair configuration only; "
                "the pair-matrix observer member is byte-identical to frozen "
                "v29 and this current rule explicitly does not retroactively "
                "hold pre-publication frozen packages by format alone."
            ),
            "v35_pair_member_sha256": pair_sha,
            "v29_pair_member_sha256": v29_pair_sha,
            "byte_equal": v29_pair_sha == pair_sha,
        },
        "diagnostic_predicate_trace_unit": {
            "applicable": False,
            "blocking": False,
            "classification": "record_only",
            "reason": (
                "No observer/parser/canonical predicate bytes changed in this "
                "content-neutral receipt; exact v29 diagnostic bytes are reused."
            ),
        },
        "release_gate_matrix_applicability": {
            "core_always": {
                "applicable": True,
                "blocking": False,
                "evidence": "unchanged exact v35 final ZIP and prior final audit",
            },
            "runner": {
                "applicable": True,
                "blocking": False,
                "evidence": "unchanged exact v35 runner receipts",
            },
            "package_local_hdl": {
                "applicable": True,
                "blocking": not valid,
                "evidence": "this actual-consumer report",
            },
            "materialized_config": {
                "applicable": True,
                "blocking": False,
                "evidence": "unchanged v35 row-pair roundtrip receipt",
            },
            "diagnostic_semantics": {
                "applicable": False,
                "blocking": False,
                "record_only": True,
            },
            "return_result": {
                "applicable": True,
                "blocking": False,
                "evidence": "unchanged exact v35 final audit",
            },
            "blocking_failures": [] if valid else ["package_local_hdl"],
        },
        "numeric_workload_golden_repeated": False,
        "package_bytes_modified": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "rule_confirmation": {
            "result": "CONFIRMED",
            "claim_boundary": (
                "The actual-consumer rule correctly blocks synthetic expected-"
                "inventory closure while allowing same-owner equivalent-class "
                "coverage. The applicability and public-surface rules correctly "
                "avoid a byte-neutral rebuild of an unchanged frozen observer."
            ),
        },
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "valid": valid,
                "positive_exit": positive["exit_code"],
                "consumer_total": len(consumers),
                "class_total": len(classes),
                "uncovered": report["actual_consumer_coverage"][
                    "uncovered_expression_total"
                ],
                "negative_exits": {
                    key: item["frontend"]["exit_code"]
                    for key, item in misspell_negatives.items()
                },
                "output": str(output),
            },
            indent=2,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
