from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PATCHSET_ID = "resnet50-ndp-toolchain-6144-v1"
GAP_PATCHSET_ID = "resnet50-ndp-toolchain-6144-gap-v1"
REQUANT_PATCHSET_ID = "resnet50-ndp-toolchain-6144-requant-v1"
CONV_PATCHSET_ID = "resnet50-ndp-toolchain-6144-conv-v1"
CONV_SERIALIZED_PATCHSET_ID = (
    "resnet50-ndp-toolchain-6144-conv-serialized-one-product-v1"
)
CONV_STEM_SERIALIZED_PATCHSET_ID = (
    "resnet50-ndp-toolchain-6144-conv-stem-serialized-one-product-v1"
)
NODE0004_ASSUMED_HW_PATCHSET_ID = (
    "resnet50-ndp-toolchain-6144-node0004-assumed-hw-v1"
)
BASE_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
PATCHSET_SCHEMA = "resnet50-ndp-patchset-v1"


@dataclass(frozen=True)
class Replacement:
    replacement_id: str
    before: str
    after: str


@dataclass(frozen=True)
class PatchedFile:
    relative_path: str
    base_sha256_lf: str
    replacements: tuple[Replacement, ...]


PATCHED_FILES = (
    PatchedFile(
        relative_path="model_execplan/src/execution_plan_generator/address_planner.py",
        base_sha256_lf="0c122a03b2c1b4b75ca2d04006c41d11d081dbf3b1977e90809a728e6fea7f59",
        replacements=(
            Replacement(
                replacement_id="target-profile-row-count-6144",
                before="    MAX_ROWS = 8192\n",
                after="    MAX_ROWS = 6144\n",
            ),
        ),
    ),
    PatchedFile(
        relative_path="bitstream/config/mapper.py",
        base_sha256_lf="9889c1433849ac1a536d9fe4aa85b46b808da472f58bc5f1137cdc3fe00a0a39",
        replacements=(
            Replacement(
                replacement_id="direct-dram-lc-unmatched-name",
                before=(
                    "        if \"DRAM_LC\" in node and \".LC\" in node:\n"
                    "            match = re.search(r'LC(\\d+)(\\d)$', node)  # LCrc where r=row, c=col\n"
                    "            if match:\n"
                    "                row = int(match.group(1)[0]) if len(match.group(1)) > 0 else 0\n"
                    "                col = int(match.group(2)) if match.group(2) else 0\n"
                    "            return row * 10 + col  # Linearize: first row 0-9, second row 10-19\n"
                ),
                after=(
                    "        if \"DRAM_LC\" in node and \".LC\" in node:\n"
                    "            match = re.search(r'\\.LC(\\d+)$', node)\n"
                    "            if match:\n"
                    "                return int(match.group(1))\n"
                    "            return None\n"
                ),
            ),
            Replacement(
                replacement_id="zero-penalty-search-return",
                before=(
                    "            except Exception as exc:\n"
                    "                print(f\"[Simulated Annealing] Failed to cache mapping: {exc}\")\n"
                    "        else:\n"
                    "            # Gather per-connection violation details for diagnosis.\n"
                ),
                after=(
                    "            except Exception as exc:\n"
                    "                print(f\"[Simulated Annealing] Failed to cache mapping: {exc}\")\n"
                    "            return self.node_to_resource\n"
                    "        else:\n"
                    "            # Gather per-connection violation details for diagnosis.\n"
                ),
            ),
            Replacement(
                replacement_id="preserve-explicit-nonconnected-bindings",
                before=(
                    "        self.node_to_resource = best_mapping\n"
                    "        self.last_mapping_cost = best_cost\n"
                ),
                after=(
                    "        # Preserve explicit bindings (for example GROUP targets) that are\n"
                    "        # intentionally absent from the connection-only annealing set.\n"
                    "        self.node_to_resource.update(best_mapping)\n"
                    "        self.last_mapping_cost = best_cost\n"
                ),
            ),
        ),
    ),
)

GAP_PATCHED_FILES = PATCHED_FILES + (
    PatchedFile(
        relative_path=(
            "model_execplan/src/execution_plan_generator/control_registers.py"
        ),
        base_sha256_lf=(
            "c7844a510bb72c16417c79da002b85c0a421f08dd2c88ef6eaa1a86d5f2b6e1c"
        ),
        replacements=(
            Replacement(
                replacement_id="register-exact-resnet50-gap-sum-handler",
                before="OP_CONTROL_REGISTER_FN = {\n",
                after=(
                    "def _compute_resnet50_gap_sum_uint8_int32_control_register_updates(\n"
                    "    operator: OperatorSpec,\n"
                    "    template: OperatorTemplate,\n"
                    ") -> dict[str, int]:\n"
                    "    \"\"\"Validate the exact ResNet-50 GAP sum specialization.\n"
                    "\n"
                    "    The authorized avgpool_config_2048_7_7 template already contains\n"
                    "    the complete loop/stream/GA program.  The common native pipeline\n"
                    "    still binds addresses and remapping; this handler deliberately\n"
                    "    changes no semantic register and fails closed on any other ABI.\n"
                    "    \"\"\"\n"
                    "    input_a = operator.inputs.get(\"A\")\n"
                    "    if set(operator.inputs) != {\"A\"} or input_a is None:\n"
                    "        raise ValueError(\"ResNet-50 GAP sum requires exactly input A\")\n"
                    "    if input_a.shape != (1, 1, 100416) or input_a.dtype != \"uint8\":\n"
                    "        raise ValueError(\n"
                    "            \"ResNet-50 GAP sum A must be the guarded uint8 100416-byte allocation\"\n"
                    "        )\n"
                    "    if operator.output.shape != (2048, 1, 1):\n"
                    "        raise ValueError(\n"
                    "            \"ResNet-50 GAP sum D must have shape [2048,1,1]\"\n"
                    "        )\n"
                    "    if operator.output.dtype != \"int32\":\n"
                    "        raise ValueError(\"ResNet-50 GAP sum D must be int32\")\n"
                    "    if operator.used_slice_count() != 16:\n"
                    "        raise ValueError(\"ResNet-50 GAP sum requires exactly 16 slices\")\n"
                    "    return {}\n"
                    "\n"
                    "\n"
                    "OP_CONTROL_REGISTER_FN = {\n"
                    "    \"resnet50_gap_sum_uint8_int32\": "
                    "_compute_resnet50_gap_sum_uint8_int32_control_register_updates,\n"
                ),
            ),
        ),
    ),
)

_REQUANT_OPERATOR_TYPES = tuple(
    f"resnet50_requant_node0004_w{wave}_s{shard:02d}"
    for wave in range(3)
    for shard in range(8)
)

REQUANT_PATCHED_FILES = PATCHED_FILES + (
    PatchedFile(
        relative_path=(
            "model_execplan/src/execution_plan_generator/control_registers.py"
        ),
        base_sha256_lf=(
            "c7844a510bb72c16417c79da002b85c0a421f08dd2c88ef6eaa1a86d5f2b6e1c"
        ),
        replacements=(
            Replacement(
                replacement_id="register-exact-resnet50-node0004-requant-handlers",
                before="OP_CONTROL_REGISTER_FN = {\n",
                after=(
                    "def _compute_resnet50_node0004_requant_control_register_updates(\n"
                    "    operator: OperatorSpec,\n"
                    "    template: OperatorTemplate,\n"
                    ") -> dict[str, int]:\n"
                    "    \"\"\"Validate one exact 8-channel node-0004 requant shard.\n"
                    "\n"
                    "    Per-channel constants and loop bounds are already specialized in\n"
                    "    the mapping-bound JSON.  Native model_execplan continues to bind\n"
                    "    addresses/remapping and emit config/execplan/SCA artifacts.\n"
                    "    \"\"\"\n"
                    "    input_a = operator.inputs.get(\"A\")\n"
                    "    if set(operator.inputs) != {\"A\"} or input_a is None:\n"
                    "        raise ValueError(\"node-0004 requant requires exactly input A\")\n"
                    "    if input_a.shape != (1, 3136, 8) or input_a.dtype != \"int32\":\n"
                    "        raise ValueError(\n"
                    "            \"node-0004 requant A must be int32 [1,3136,8]\"\n"
                    "        )\n"
                    "    if operator.output.shape != (1, 3136, 8):\n"
                    "        raise ValueError(\n"
                    "            \"node-0004 requant D must have shape [1,3136,8]\"\n"
                    "        )\n"
                    "    if operator.output.dtype != \"uint8\":\n"
                    "        raise ValueError(\"node-0004 requant D must be uint8\")\n"
                    "    if operator.used_slice_count() not in (2, 7):\n"
                    "        raise ValueError(\n"
                    "            \"node-0004 requant wave must use exactly 7 or 2 slices\"\n"
                    "        )\n"
                    "    return {}\n"
                    "\n"
                    "\n"
                    "OP_CONTROL_REGISTER_FN = {\n"
                    + "".join(
                        f'    "{op_type}": '
                        "_compute_resnet50_node0004_requant_control_register_updates,\n"
                        for op_type in _REQUANT_OPERATOR_TYPES
                    )
                ),
            ),
        ),
    ),
)

_CONV_OPERATOR_TYPES = tuple(
    f"resnet50_conv_node0004_wave{wave}" for wave in range(3)
)

CONV_PATCHED_FILES = PATCHED_FILES + (
    PatchedFile(
        relative_path=(
            "model_execplan/src/execution_plan_generator/control_registers.py"
        ),
        base_sha256_lf=(
            "c7844a510bb72c16417c79da002b85c0a421f08dd2c88ef6eaa1a86d5f2b6e1c"
        ),
        replacements=(
            Replacement(
                replacement_id="register-exact-resnet50-node0004-conv-wave-handlers",
                before="OP_CONTROL_REGISTER_FN = {\n",
                after=(
                    "def _compute_resnet50_node0004_conv_control_register_updates(\n"
                    "    operator: OperatorSpec,\n"
                    "    template: OperatorTemplate,\n"
                    ") -> dict[str, int]:\n"
                    "    \"\"\"Validate one exact node-0004 Conv accumulate wave.\n"
                    "\n"
                    "    The mapping-bound zero-ping-pong JSON contains the complete\n"
                    "    stream/loop/SA program.  Native model_execplan binds addresses\n"
                    "    and remapping; this handler changes no semantic register.\n"
                    "    \"\"\"\n"
                    "    if set(operator.inputs) != {\"A\", \"B\", \"C\"}:\n"
                    "        raise ValueError(\"node-0004 Conv requires exactly A/B/C\")\n"
                    "    expected = {\n"
                    "        \"A\": ((1, 1, 1024), \"int8\"),\n"
                    "        \"B\": ((1, 1, 200704), \"uint8\"),\n"
                    "        \"C\": ((1, 1, 16), \"int32\"),\n"
                    "    }\n"
                    "    for name, (shape, dtype) in expected.items():\n"
                    "        tensor = operator.inputs[name]\n"
                    "        if tensor.shape != shape or tensor.dtype != dtype:\n"
                    "            raise ValueError(\n"
                    "                f\"node-0004 Conv {name} must be {dtype} {list(shape)}\"\n"
                    "            )\n"
                    "    if operator.output.shape != (1, 1, 50176):\n"
                    "        raise ValueError(\n"
                    "            \"node-0004 Conv D must be int32 [1,1,50176]\"\n"
                    "        )\n"
                    "    if operator.output.dtype != \"int32\":\n"
                    "        raise ValueError(\"node-0004 Conv D must be int32\")\n"
                    "    if operator.used_slice_count() not in (8, 28):\n"
                    "        raise ValueError(\n"
                    "            \"node-0004 Conv wave must use exactly 28 or 8 slices\"\n"
                    "        )\n"
                    "    return {}\n"
                    "\n"
                    "\n"
                    "OP_CONTROL_REGISTER_FN = {\n"
                    + "".join(
                        f'    "{op_type}": '
                        "_compute_resnet50_node0004_conv_control_register_updates,\n"
                        for op_type in _CONV_OPERATOR_TYPES
                    )
                ),
            ),
        ),
    ),
)

_CONV_SERIALIZED_OPERATOR_TYPES = tuple(
    f"resnet50_conv_node0004_serialized_wave{wave}" for wave in range(3)
)

CONV_SERIALIZED_PATCHED_FILES = PATCHED_FILES + (
    PatchedFile(
        relative_path=(
            "model_execplan/src/execution_plan_generator/control_registers.py"
        ),
        base_sha256_lf=(
            "c7844a510bb72c16417c79da002b85c0a421f08dd2c88ef6eaa1a86d5f2b6e1c"
        ),
        replacements=(
            Replacement(
                replacement_id=(
                    "register-exact-resnet50-node0004-serialized-conv-handlers"
                ),
                before="OP_CONTROL_REGISTER_FN = {\n",
                after=(
                    "def _compute_resnet50_node0004_serialized_conv_control_register_updates(\n"
                    "    operator: OperatorSpec,\n"
                    "    template: OperatorTemplate,\n"
                    ") -> dict[str, int]:\n"
                    "    \"\"\"Validate one stock-SA serialized-product Conv wave.\"\"\"\n"
                    "    if set(operator.inputs) != {\"A\", \"B\", \"C\"}:\n"
                    "        raise ValueError(\"serialized node-0004 Conv requires exactly A/B/C\")\n"
                    "    expected = {\n"
                    "        \"A\": ((1, 1, 4096), \"int8\"),\n"
                    "        \"B\": ((1, 1, 802816), \"uint8\"),\n"
                    "        \"C\": ((1, 1, 16), \"int32\"),\n"
                    "    }\n"
                    "    for name, (shape, dtype) in expected.items():\n"
                    "        tensor = operator.inputs[name]\n"
                    "        if tensor.shape != shape or tensor.dtype != dtype:\n"
                    "            raise ValueError(\n"
                    "                f\"serialized node-0004 Conv {name} must be {dtype} {list(shape)}\"\n"
                    "            )\n"
                    "    if operator.output.shape != (1, 1, 50176):\n"
                    "        raise ValueError(\n"
                    "            \"serialized node-0004 Conv D must be int32 [1,1,50176]\"\n"
                    "        )\n"
                    "    if operator.output.dtype != \"int32\":\n"
                    "        raise ValueError(\"serialized node-0004 Conv D must be int32\")\n"
                    "    if operator.used_slice_count() not in (8, 28):\n"
                    "        raise ValueError(\n"
                    "            \"serialized node-0004 Conv wave must use exactly 28 or 8 slices\"\n"
                    "        )\n"
                    "    return {}\n"
                    "\n"
                    "\n"
                    "OP_CONTROL_REGISTER_FN = {\n"
                    + "".join(
                        f'    "{op_type}": '
                        "_compute_resnet50_node0004_serialized_conv_control_register_updates,\n"
                        for op_type in _CONV_SERIALIZED_OPERATOR_TYPES
                    )
                ),
            ),
        ),
    ),
)

_CONV_STEM_SERIALIZED_OPERATOR_TYPES = tuple(
    f"resnet50_conv_stem_hwop0001_serialized_wave{wave}" for wave in range(3)
)

CONV_STEM_SERIALIZED_PATCHED_FILES = PATCHED_FILES + (
    PatchedFile(
        relative_path=(
            "model_execplan/src/execution_plan_generator/control_registers.py"
        ),
        base_sha256_lf=(
            "c7844a510bb72c16417c79da002b85c0a421f08dd2c88ef6eaa1a86d5f2b6e1c"
        ),
        replacements=(
            Replacement(
                replacement_id=(
                    "register-exact-resnet50-stem-serialized-conv-handlers"
                ),
                before="OP_CONTROL_REGISTER_FN = {\n",
                after=(
                    "def _compute_resnet50_stem_serialized_conv_control_register_updates(\n"
                    "    operator: OperatorSpec,\n"
                    "    template: OperatorTemplate,\n"
                    ") -> dict[str, int]:\n"
                    "    \"\"\"Validate one exact stem 7x7 serialized-product wave.\"\"\"\n"
                    "    if set(operator.inputs) != {\"A\", \"B\", \"C\"}:\n"
                    "        raise ValueError(\"serialized stem Conv requires exactly A/B/C\")\n"
                    "    expected = {\n"
                    "        \"A\": ((1, 1, 9472), \"int8\"),\n"
                    "        \"B\": ((1, 1, 7426048), \"uint8\"),\n"
                    "        \"C\": ((1, 1, 16), \"int32\"),\n"
                    "    }\n"
                    "    for name, (shape, dtype) in expected.items():\n"
                    "        tensor = operator.inputs[name]\n"
                    "        if tensor.shape != shape or tensor.dtype != dtype:\n"
                    "            raise ValueError(\n"
                    "                f\"serialized stem Conv {name} must be {dtype} {list(shape)}\"\n"
                    "            )\n"
                    "    if operator.output.shape != (1, 1, 200704):\n"
                    "        raise ValueError(\n"
                    "            \"serialized stem Conv D must be int32 [1,1,200704]\"\n"
                    "        )\n"
                    "    if operator.output.dtype != \"int32\":\n"
                    "        raise ValueError(\"serialized stem Conv D must be int32\")\n"
                    "    if operator.used_slice_count() not in (8, 28):\n"
                    "        raise ValueError(\n"
                    "            \"serialized stem Conv wave must use exactly 28 or 8 slices\"\n"
                    "        )\n"
                    "    return {}\n"
                    "\n"
                    "\n"
                    "OP_CONTROL_REGISTER_FN = {\n"
                    + "".join(
                        f'    "{op_type}": '
                        "_compute_resnet50_stem_serialized_conv_control_register_updates,\n"
                        for op_type in _CONV_STEM_SERIALIZED_OPERATOR_TYPES
                    )
                ),
            ),
        ),
    ),
)

_NODE0004_TAIL_MUL_OPERATOR_TYPES = tuple(
    f"resnet50_requant_node0004_mul_w{wave}_s{shard:02d}"
    for wave in range(3)
    for shard in range(8)
)
_NODE0004_TAIL_ROUND_OPERATOR_TYPES = tuple(
    f"resnet50_requant_node0004_round_w{wave}_s{shard:02d}"
    for wave in range(3)
    for shard in range(8)
)

NODE0004_ASSUMED_HW_PATCHED_FILES = PATCHED_FILES + (
    PatchedFile(
        relative_path=(
            "model_execplan/src/execution_plan_generator/control_registers.py"
        ),
        base_sha256_lf=(
            "c7844a510bb72c16417c79da002b85c0a421f08dd2c88ef6eaa1a86d5f2b6e1c"
        ),
        replacements=(
            Replacement(
                replacement_id=(
                    "register-node0004-assumed-hw-conv-and-two-stage-tail-handlers"
                ),
                before="OP_CONTROL_REGISTER_FN = {\n",
                after=(
                    "def _compute_resnet50_node0004_assumed_conv_control_register_updates(\n"
                    "    operator: OperatorSpec,\n"
                    "    template: OperatorTemplate,\n"
                    ") -> dict[str, int]:\n"
                    "    if set(operator.inputs) != {\"A\", \"B\", \"B'\", \"C\"}:\n"
                    "        raise ValueError(\"node0004 Conv requires A/B/B-prime/C\")\n"
                    "    expected = {\n"
                    "        \"A\": ((1, 1, 1024), \"int8\"),\n"
                    "        \"B\": ((1, 1, 200704), \"uint8\"),\n"
                    "        \"B'\": ((1, 1, 200704), \"uint8\"),\n"
                    "        \"C\": ((1, 1, 16), \"int32\"),\n"
                    "    }\n"
                    "    for name, (shape, dtype) in expected.items():\n"
                    "        tensor = operator.inputs[name]\n"
                    "        if tensor.shape != shape or tensor.dtype != dtype:\n"
                    "            raise ValueError(f\"node0004 Conv {name} ABI differs\")\n"
                    "    if operator.output.shape != (1, 1, 50176) or operator.output.dtype != \"int32\":\n"
                    "        raise ValueError(\"node0004 Conv D ABI differs\")\n"
                    "    if operator.used_slice_count() not in (8, 28):\n"
                    "        raise ValueError(\"node0004 Conv wave requires 28 or 8 slices\")\n"
                    "    return {}\n"
                    "\n"
                    "\n"
                    "def _compute_resnet50_node0004_tail_mul_control_register_updates(\n"
                    "    operator: OperatorSpec,\n"
                    "    template: OperatorTemplate,\n"
                    ") -> dict[str, int]:\n"
                    "    input_a = operator.inputs.get(\"A\")\n"
                    "    if set(operator.inputs) != {\"A\"} or input_a is None:\n"
                    "        raise ValueError(\"node0004 tail MUL requires A\")\n"
                    "    if input_a.shape != (1, 3136, 8) or input_a.dtype != \"int32\":\n"
                    "        raise ValueError(\"node0004 tail MUL A ABI differs\")\n"
                    "    if operator.output.shape != (1, 3136, 8) or operator.output.dtype != \"fp32\":\n"
                    "        raise ValueError(\"node0004 tail MUL D ABI differs\")\n"
                    "    if operator.used_slice_count() not in (2, 7):\n"
                    "        raise ValueError(\"node0004 tail MUL requires 7 or 2 slices\")\n"
                    "    return {}\n"
                    "\n"
                    "\n"
                    "def _compute_resnet50_node0004_tail_round_control_register_updates(\n"
                    "    operator: OperatorSpec,\n"
                    "    template: OperatorTemplate,\n"
                    ") -> dict[str, int]:\n"
                    "    input_a = operator.inputs.get(\"A\")\n"
                    "    if set(operator.inputs) != {\"A\"} or input_a is None:\n"
                    "        raise ValueError(\"node0004 tail round requires A\")\n"
                    "    if input_a.shape != (1, 3136, 8) or input_a.dtype != \"fp32\":\n"
                    "        raise ValueError(\"node0004 tail round A ABI differs\")\n"
                    "    if operator.output.shape != (1, 3136, 8) or operator.output.dtype != \"uint8\":\n"
                    "        raise ValueError(\"node0004 tail round D ABI differs\")\n"
                    "    if operator.used_slice_count() not in (2, 7):\n"
                    "        raise ValueError(\"node0004 tail round requires 7 or 2 slices\")\n"
                    "    return {}\n"
                    "\n"
                    "\n"
                    "OP_CONTROL_REGISTER_FN = {\n"
                    + "".join(
                        f'    "{op_type}": '
                        "_compute_resnet50_node0004_assumed_conv_control_register_updates,\n"
                        for op_type in _CONV_OPERATOR_TYPES
                    )
                    + "".join(
                        f'    "{op_type}": '
                        "_compute_resnet50_node0004_tail_mul_control_register_updates,\n"
                        for op_type in _NODE0004_TAIL_MUL_OPERATOR_TYPES
                    )
                    + "".join(
                        f'    "{op_type}": '
                        "_compute_resnet50_node0004_tail_round_control_register_updates,\n"
                        for op_type in _NODE0004_TAIL_ROUND_OPERATOR_TYPES
                    )
                ),
            ),
        ),
    ),
)


class PatchsetError(ValueError):
    pass


def _patched_files_for(patchset_id: str) -> tuple[PatchedFile, ...]:
    if patchset_id == PATCHSET_ID:
        return PATCHED_FILES
    if patchset_id == GAP_PATCHSET_ID:
        return GAP_PATCHED_FILES
    if patchset_id == REQUANT_PATCHSET_ID:
        return REQUANT_PATCHED_FILES
    if patchset_id == CONV_PATCHSET_ID:
        return CONV_PATCHED_FILES
    if patchset_id == CONV_SERIALIZED_PATCHSET_ID:
        return CONV_SERIALIZED_PATCHED_FILES
    if patchset_id == CONV_STEM_SERIALIZED_PATCHSET_ID:
        return CONV_STEM_SERIALIZED_PATCHED_FILES
    if patchset_id == NODE0004_ASSUMED_HW_PATCHSET_ID:
        return NODE0004_ASSUMED_HW_PATCHED_FILES
    raise PatchsetError(f"unknown patchset id: {patchset_id}")


def _lf_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _git_head(root: Path) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.resolve().as_posix()}",
            "-C",
            str(root),
            "rev-parse",
            "HEAD",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise PatchsetError(completed.stderr.decode("utf-8", errors="replace").strip())
    return completed.stdout.decode("ascii").strip()


def _git_blob_lf_bytes(root: Path, commit: str, relative_path: str) -> bytes:
    """Read a patch base from the declared Git commit, not the mutable worktree."""

    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.resolve().as_posix()}",
            "-C",
            str(root),
            "show",
            f"{commit}:{relative_path}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise PatchsetError(
            completed.stderr.decode("utf-8", errors="replace").strip()
        )
    return completed.stdout.replace(b"\r\n", b"\n")


def _patched_lf_bytes(source: bytes, spec: PatchedFile) -> tuple[bytes, list[str]]:
    text = source.decode("utf-8")
    applied: list[str] = []
    for replacement in spec.replacements:
        count = text.count(replacement.before)
        if count != 1:
            raise PatchsetError(
                f"{spec.relative_path}:{replacement.replacement_id} expected one source match, got {count}"
            )
        text = text.replace(replacement.before, replacement.after, 1)
        applied.append(replacement.replacement_id)
    compile(text, spec.relative_path, "exec")
    return text.encode("utf-8"), applied


def build_patchset_manifest(
    source_root: Path,
    *,
    patchset_id: str = PATCHSET_ID,
) -> dict[str, Any]:
    source_root = source_root.resolve()
    commit = _git_head(source_root)
    if commit != BASE_COMMIT:
        raise PatchsetError(f"base commit differs: expected {BASE_COMMIT}, got {commit}")
    records: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for spec in _patched_files_for(patchset_id):
        # The manifest names BASE_COMMIT as its base identity.  Reading the
        # corresponding Git blob keeps validation stable when an active,
        # read-only ndp-sim checkout has unrelated local experiments.  Actual
        # patch application remains work-copy hash gated below.
        source = _git_blob_lf_bytes(source_root, BASE_COMMIT, spec.relative_path)
        source_sha = _sha256(source)
        if source_sha != spec.base_sha256_lf:
            raise PatchsetError(
                f"base source hash differs for {spec.relative_path}: {source_sha}"
            )
        patched, applied = _patched_lf_bytes(source, spec)
        patched_sha = _sha256(patched)
        record = {
            "path": spec.relative_path,
            "base_sha256_lf": source_sha,
            "patched_sha256_lf": patched_sha,
            "replacement_ids": applied,
        }
        records.append(record)
        digest.update(
            f"{spec.relative_path}\0{source_sha}\0{patched_sha}\0{','.join(applied)}\n".encode(
                "utf-8"
            )
        )
    return {
        "schema": PATCHSET_SCHEMA,
        "patchset_id": patchset_id,
        "base_repository": "https://github.com/uSFrances/ndp-sim.git",
        "base_commit": BASE_COMMIT,
        "target_profile": {
            "slices": 28,
            "banks_per_slice": 4,
            "rows_per_bank": 6144,
            "columns_per_row": 64,
            "bytes_per_column": 16,
        },
        "policy": {
            "active_source_read_only": True,
            "fail_closed_mapping": True,
            "zero_penalty_required": True,
            "direct_mapping_is_not_evidence": True,
        },
        "files": records,
        "patchset_sha256": digest.hexdigest(),
    }


def apply_patchset_in_place(
    tool_root: Path,
    *,
    patchset_id: str = PATCHSET_ID,
    relative_paths: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Apply the hash-bound patchset to a disposable ndp-sim tool copy."""

    tool_root = tool_root.resolve()
    selected = set(relative_paths) if relative_paths is not None else None
    patched_files = _patched_files_for(patchset_id)
    known = {spec.relative_path for spec in patched_files}
    if selected is not None and not selected <= known:
        raise PatchsetError(f"unknown patch target(s): {sorted(selected - known)}")
    records: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for spec in patched_files:
        if selected is not None and spec.relative_path not in selected:
            continue
        path = tool_root / spec.relative_path
        if not path.is_file():
            raise PatchsetError(f"tool copy is missing: {path}")
        raw = path.read_bytes()
        newline = b"\r\n" if b"\r\n" in raw else b"\n"
        source = raw.replace(b"\r\n", b"\n")
        source_sha = _sha256(source)
        if source_sha != spec.base_sha256_lf:
            raise PatchsetError(
                f"tool-copy source hash differs for {spec.relative_path}: {source_sha}"
            )
        patched, applied = _patched_lf_bytes(source, spec)
        path.write_bytes(patched.replace(b"\n", newline))
        patched_sha = _sha256(patched)
        record = {
            "path": spec.relative_path,
            "base_sha256_lf": source_sha,
            "patched_sha256_lf": patched_sha,
            "replacement_ids": applied,
        }
        records.append(record)
        digest.update(
            f"{spec.relative_path}\0{source_sha}\0{patched_sha}\0{','.join(applied)}\n".encode(
                "utf-8"
            )
        )
    return {
        "schema": PATCHSET_SCHEMA,
        "patchset_id": patchset_id,
        "base_commit": BASE_COMMIT,
        "files": records,
        "patchset_sha256": digest.hexdigest(),
    }


def materialize_patched_toolchain(
    source_root: Path,
    output_root: Path,
    *,
    patchset_id: str = PATCHSET_ID,
) -> dict[str, Any]:
    """Create a clearly identified patched copy without mutating the base checkout."""

    source_root = source_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite patched toolchain: {output_root}")
    manifest = build_patchset_manifest(source_root, patchset_id=patchset_id)
    output_root.mkdir(parents=True)
    shutil.copytree(
        source_root / "bitstream",
        output_root / "bitstream",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "mapping_cache", "placement_failed.png"),
    )
    shutil.copytree(
        source_root / "jsons",
        output_root / "jsons",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    model = output_root / "model_execplan"
    model.mkdir()
    shutil.copy2(source_root / "model_execplan" / "main.py", model / "main.py")
    shutil.copytree(source_root / "model_execplan" / "src", model / "src")
    shutil.copytree(source_root / "model_execplan" / "config", model / "config")
    for spec in _patched_files_for(patchset_id):
        target = output_root / spec.relative_path
        target.write_bytes(
            _git_blob_lf_bytes(source_root, BASE_COMMIT, spec.relative_path)
        )
    applied = apply_patchset_in_place(output_root, patchset_id=patchset_id)
    if applied["patchset_sha256"] != manifest["patchset_sha256"]:
        raise PatchsetError("applied patchset identity differs from the source manifest")
    (output_root / "PATCHSET_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


def validate_patchset_manifest(value: Any, source_root: Path) -> None:
    if not isinstance(value, dict) or not isinstance(value.get("patchset_id"), str):
        raise PatchsetError("patchset manifest identity is missing")
    expected = build_patchset_manifest(
        source_root,
        patchset_id=value["patchset_id"],
    )
    if value != expected:
        raise PatchsetError("patchset manifest differs from the locked source and transforms")


__all__ = [
    "BASE_COMMIT",
    "CONV_PATCHED_FILES",
    "CONV_PATCHSET_ID",
    "CONV_STEM_SERIALIZED_PATCHED_FILES",
    "CONV_STEM_SERIALIZED_PATCHSET_ID",
    "NODE0004_ASSUMED_HW_PATCHED_FILES",
    "NODE0004_ASSUMED_HW_PATCHSET_ID",
    "GAP_PATCHED_FILES",
    "GAP_PATCHSET_ID",
    "PATCHED_FILES",
    "PATCHSET_ID",
    "PATCHSET_SCHEMA",
    "REQUANT_PATCHED_FILES",
    "REQUANT_PATCHSET_ID",
    "PatchsetError",
    "apply_patchset_in_place",
    "build_patchset_manifest",
    "materialize_patched_toolchain",
    "validate_patchset_manifest",
]
