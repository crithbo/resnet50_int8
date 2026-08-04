"""Current-source reuse audit for node0074 exact binary32 division.

The audit is deliberately structural.  It does not rerun accepted W3/golden,
Flatten, Dequant, or counterexample tests and creates no hardware target.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "resnet50-quantize-node0074-exact-division-reuse-audit-v2"
REPORT_SCHEMA = "resnet50-quantize-node0074-exact-division-reuse-audit-report-v2"


class QuantizeReuseAuditError(ValueError):
    """Raised when current sources no longer support the fail-closed audit."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QuantizeReuseAuditError(f"JSON root must be an object: {path}")
    return value


def _section_hash(section: dict[str, Any]) -> str:
    payload = dict(section)
    payload.pop("owner_section_content_sha256", None)
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _locked_sources(contract: dict[str, Any], root: Path) -> list[dict[str, str]]:
    validated = []
    for item in contract["current_match_sources"]:
        path = root / item["path"]
        if not path.is_file():
            raise QuantizeReuseAuditError(f"missing current source: {item['path']}")
        actual = _sha256(path)
        if actual != item["sha256"]:
            raise QuantizeReuseAuditError(
                f"current source changed: {item['path']} "
                f"expected={item['sha256']} actual={actual}"
            )
        validated.append(
            {
                "path": item["path"],
                "sha256": actual,
                "gate": "current_match_fail_closed",
            }
        )
    return validated


def _collect_alu_opcodes(value: Any, result: set[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "alu_opcode":
                result.add(str(child))
            _collect_alu_opcodes(child, result)
    elif isinstance(value, list):
        for child in value:
            _collect_alu_opcodes(child, result)


def _validate_corpus(contract: dict[str, Any], root: Path) -> dict[str, Any]:
    corpus = _load_json(root / "contracts/operator_config/ndpsim_json_corpus_v1.json")
    json_paths = sorted((root / "ndp-sim/jsons").glob("*.json"))
    if len(corpus["templates"]) != 55 or len(json_paths) != 55:
        raise QuantizeReuseAuditError("current native JSON corpus size changed")
    quant = [
        item for item in corpus["templates"] if item["family"] == "quantize"
    ]
    if len(quant) != 1 or quant[0]["template_id"] != "quant_from_buffer_int32MN_uint8MN":
        raise QuantizeReuseAuditError("current quantize template inventory changed")
    opcodes: set[str] = set()
    for path in json_paths:
        _collect_alu_opcodes(_load_json(path), opcodes)
    expected = set(contract["current_corpus_audit"]["observed_alu_opcodes"])
    if opcodes != expected:
        raise QuantizeReuseAuditError(
            f"current native opcode set changed: expected={sorted(expected)} "
            f"actual={sorted(opcodes)}"
        )
    if any("div" in opcode.lower() for opcode in opcodes):
        raise QuantizeReuseAuditError("a division opcode requires a new capability audit")
    return {
        "template_count": len(json_paths),
        "quantize_template_count": len(quant),
        "quantize_template_id": quant[0]["template_id"],
        "alu_opcodes": sorted(opcodes),
        "direct_division_template_present": False,
        "direct_division_opcode_present": False,
        "passed": True,
    }


def _extract_opcode_map(path: Path) -> dict[str, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "opcode_map":
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and isinstance(child.value, ast.Dict):
                value = ast.literal_eval(child.value)
                if isinstance(value, dict):
                    return value
    raise QuantizeReuseAuditError("could not parse GA opcode map")


def _validate_encoder_and_transport(root: Path) -> dict[str, Any]:
    opcode_map = _extract_opcode_map(root / "ndp-sim/bitstream/config/general.py")
    if opcode_map.get("rec") != 17:
        raise QuantizeReuseAuditError("REC encoder identity changed")
    if any("div" in str(name).lower() for name in opcode_map):
        raise QuantizeReuseAuditError("encoder now exposes a division opcode")

    registry = _load_json(root / "ndp-sim/model_execplan/config/operator_base_info.json")[
        "operators"
    ]
    if "quant_from_buffer_int32MN_uint8MN" not in registry:
        raise QuantizeReuseAuditError("quant structure template disappeared")
    if registry["quant_from_buffer_int32MN_uint8MN"]["config_sfu"] is not None:
        raise QuantizeReuseAuditError("quant template unexpectedly gained an SFU")
    for name in ("prefill_sum_rec_fp32MN_fp32MN", "decode_sum_rec_fp32N_fp32N"):
        if registry[name]["config_sfu"] != "REC":
            raise QuantizeReuseAuditError(f"REC registry identity changed: {name}")

    handlers = (
        root
        / "ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py"
    ).read_text(encoding="utf-8")
    if not re.search(
        r"def _compute_quant_from_buffer_int32MN_uint8MN.*?"
        r"Placeholder for quant_from_buffer_int32MN_uint8MN",
        handlers,
        re.DOTALL,
    ):
        raise QuantizeReuseAuditError("quant handler is no longer the audited placeholder")
    mapper_test = (
        root / "ndp-sim/address_remapping/tests/test_solver.py"
    ).read_text(encoding="utf-8")
    if 'assertNotIn("quant_from_buffer_int32MN_uint8MN", registry)' not in mapper_test:
        raise QuantizeReuseAuditError("quant mapper registry boundary changed")
    return {
        "encoder_opcode_count": len(opcode_map),
        "rec_opcode": opcode_map["rec"],
        "division_opcode": None,
        "sum_rec_registry_sfu": "REC",
        "quant_handler": "PLACEHOLDER_BLOCKED",
        "quant_mapper": "REGISTRY_MISSING",
        "passed": True,
    }


def _validate_rtl(root: Path) -> dict[str, Any]:
    base = root / "Trassic2.0_RTL/code/NDP_rtl"
    params = (base / "includes/NDP_Parameters.svh").read_text(encoding="utf-8")
    if "`define GA_PE_SFU_REC                     5'b10001" not in params:
        raise QuantizeReuseAuditError("RTL REC opcode identity changed")
    if re.search(r"`define\\s+\\S*(?:DIV|FDIV)\\S*", params, re.IGNORECASE):
        raise QuantizeReuseAuditError("RTL now declares a division opcode")
    preprocess = (
        base
        / "Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Preprocess.sv"
    ).read_text(encoding="utf-8")
    pe = (
        base / "Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE.sv"
    ).read_text(encoding="utf-8")
    postprocess = (
        base
        / "Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Postprocess.sv"
    ).read_text(encoding="utf-8")
    lut = (
        base / "Slice/General_Array/GA_PE_Group/GA_SFU_LUT.sv"
    ).read_text(encoding="utf-8")
    alu = (
        base / "Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv"
    ).read_text(encoding="utf-8")
    required = (
        ("breakpoint", preprocess),
        ("ga_pe_sfu_slope_data_i", pe),
        ("ga_pe_sfu_intercept_data_i", pe),
        ("rec_result", postprocess),
        ("pe_slope_addr", lut),
        ("pe_intercept_addr", lut),
        ("ga_pe_alu_opcode[4] ? 3'b110", alu),
    )
    if any(token not in text for token, text in required):
        raise QuantizeReuseAuditError("RTL affine REC evidence changed")
    return {
        "rec_opcode": 17,
        "division_opcode": None,
        "rec_datapath": "breakpoint_LUT_slope_intercept_MAC_then_exponent_reconstruction",
        "direct_binary32_divider_present": False,
        "passed": True,
    }


def _validate_counterexample_binding(
    contract: dict[str, Any], root: Path
) -> dict[str, Any]:
    binding = contract["accepted_counterexample_binding"]
    source = _load_json(root / binding["source_contract"]["path"])
    if _sha256(root / binding["source_contract"]["path"]) != binding[
        "source_contract"
    ]["sha256"]:
        raise QuantizeReuseAuditError("accepted counterexample source changed")
    previous = source["same_scale_sequential_reciprocal_counterexample"]
    checks = {
        "x_bits": previous["x_bits"],
        "scale_bits": previous["scale_bits"],
        "divide_then_rne_uint8": previous["divide_then_rne_uint8"],
        "reciprocal_mul_then_rne_uint8": previous[
            "reciprocal_mul_then_rne_uint8"
        ],
    }
    for key, value in checks.items():
        if binding[key] != value:
            raise QuantizeReuseAuditError(
                f"accepted counterexample binding changed at {key}"
            )
    if binding["retested"] is not False:
        raise QuantizeReuseAuditError("accepted counterexample must not be rerun")
    return {**checks, "retested": False, "still_contradicts_rec_mul": True}


def _validate_endpoint(contract: dict[str, Any], root: Path) -> dict[str, Any]:
    endpoint = contract["endpoint_binding"]
    if (
        endpoint["blocked_by"] != "B_QUANT_NODE0074_EXACT_DIVISION"
        or endpoint["provisional_address_allowed"] is not False
        or endpoint["integrated_endpoint_closed"] is not False
        or any(endpoint["consumer_owned_fields"].values())
    ):
        raise QuantizeReuseAuditError("consumer endpoint fail-closed boundary changed")
    canonical = _load_json(root / endpoint["canonical"])
    quant = canonical["owner_sections"]["QuantizeLinear"]
    if any(quant["consumer_owned_endpoint_fields"].values()):
        raise QuantizeReuseAuditError("canonical consumer endpoint is no longer null")
    contract_rel = (
        "contracts/operator_config/"
        "quantize_node0074_exact_division_reuse_audit_v2.json"
    )
    if quant["audit_contract"] != {
        "path": contract_rel,
        "sha256": _sha256(root / contract_rel),
    }:
        raise QuantizeReuseAuditError(
            "canonical QuantizeLinear owner is not bound to the current reuse audit"
        )
    if (
        quant.get("reuse_class") != "STRUCTURE_OR_PRIMITIVE_ONLY"
        or quant.get("reuse_status")
        != "REUSE_ACCEPTED_FOR_INTEGRATION_WITH_OPEN_CAPABILITY_GAP"
        or quant["status"] != contract["status"]
        or quant["numeric_capability"].get("minimum_missing_capability")
        != "EXACT_BINARY32_DIVIDE_RNE"
        or quant["numeric_capability"].get("blocker_id")
        != contract["first_divergence"]["id"]
        or quant["numeric_capability"].get("shared_blocker_id")
        != contract["first_divergence"]["shared_id"]
    ):
        raise QuantizeReuseAuditError(
            "canonical QuantizeLinear capability boundary diverged from the audit"
        )
    if _section_hash(quant) != quant["owner_section_content_sha256"]:
        raise QuantizeReuseAuditError(
            "canonical QuantizeLinear owner section hash is stale"
        )
    for name in ("DequantizeLinear", "Flatten_View"):
        section = canonical["owner_sections"][name]
        if _section_hash(section) != section["owner_section_content_sha256"]:
            raise QuantizeReuseAuditError(f"non-Quantize owner section changed: {name}")
    return {
        "canonical": endpoint["canonical"],
        "canonical_sha256": _sha256(root / endpoint["canonical"]),
        "quantize_owner_section_sha256": quant["owner_section_content_sha256"],
        "quantize_audit_contract": quant["audit_contract"],
        "reuse_class": quant["reuse_class"],
        "consumer_owned_fields_all_null": True,
        "provisional_address_allowed": False,
        "integrated_endpoint_closed": False,
        "passed": True,
    }


def validate_contract(contract_path: Path, root: Path) -> dict[str, Any]:
    contract = _load_json(contract_path)
    if contract.get("schema") != SCHEMA:
        raise QuantizeReuseAuditError(f"unexpected schema: {contract.get('schema')}")
    if contract["reuse_class_and_boundary"]["class"] != "STRUCTURE_OR_PRIMITIVE_ONLY":
        raise QuantizeReuseAuditError("reuse class widened")
    if any(contract["outputs"].values()):
        raise QuantizeReuseAuditError("target or package output must remain absent")
    accounting = contract["analysis_accounting"]
    if any(
        accounting[key] is not False
        for key in (
            "accepted_w3_or_golden_retested",
            "accepted_flatten_or_dequant_primitive_retested",
            "accepted_counterexample_retested",
        )
    ):
        raise QuantizeReuseAuditError("accepted evidence was marked as retested")
    sources = _locked_sources(contract, root)
    corpus = _validate_corpus(contract, root)
    transport = _validate_encoder_and_transport(root)
    rtl = _validate_rtl(root)
    counterexample = _validate_counterexample_binding(contract, root)
    endpoint = _validate_endpoint(contract, root)
    return {
        "schema": REPORT_SCHEMA,
        "status": contract["status"],
        "claim_boundary": contract["claim_boundary"],
        "contract": {
            "path": contract_path.relative_to(root).as_posix(),
            "sha256": _sha256(contract_path),
        },
        "current_match_sources": sources,
        "reuse_class_and_boundary": contract["reuse_class_and_boundary"],
        "current_corpus_audit": corpus,
        "encoder_handler_mapper_audit": transport,
        "rtl_consumer_audit": rtl,
        "accepted_counterexample_binding": counterexample,
        "first_divergence": contract["first_divergence"],
        "minimum_missing_capability_contract": contract[
            "minimum_missing_capability_contract"
        ],
        "endpoint_binding": endpoint,
        "downstream_deferred": contract["downstream_deferred"],
        "analysis_accounting": accounting,
        "generated_outputs": contract["outputs"],
        "rule_delta_proposal": contract["rule_delta_proposal"],
        "package_release": contract["package_release"],
        "passed": True,
    }


def write_report(contract_path: Path, root: Path, report_path: Path) -> dict[str, Any]:
    report = validate_contract(contract_path, root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
