from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..conv_layout import ConvPhysicalBundle
from ..errors import PipelineError


@dataclass(frozen=True)
class NdpPhysicalProbeResult:
    per_slice: int
    total_bytes: int
    regions: tuple[dict[str, Any], ...]


class NdpFunctionalAdapter:
    def __init__(
        self,
        repository: Path,
        *,
        python_executable: Path | None = None,
        timeout_seconds: int = 30,
    ):
        self.repository = repository.resolve()
        self.python_executable = Path(python_executable or sys.executable).resolve()
        self.timeout_seconds = timeout_seconds
        bridge = self.repository / "tools" / "physical_image_probe.py"
        if not bridge.is_file():
            raise PipelineError(f"NDP physical-image bridge is missing: {bridge}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def probe_physical_bundle(self, bundle: ConvPhysicalBundle) -> NdpPhysicalProbeResult:
        geometry = bundle.geometry
        request = {
            "schema_version": "0.1",
            "geometry": {
                "slice_count": geometry.slice_count,
                "bank_count": geometry.bank_count,
                "row_count": geometry.row_count,
                "col_count": geometry.col_count,
                "subword_bytes": geometry.subword_bytes,
            },
            "regions": [],
        }
        expected: dict[tuple[str, int], str] = {}
        for region in bundle.regions:
            payload = bundle.image.read(region.base_address, region.size_bytes)
            digest = hashlib.sha256(payload).hexdigest()
            request["regions"].append(
                {
                    "name": region.name,
                    "slice_id": region.slice_id,
                    "base_address": region.base_address,
                    "data_hex": payload.hex(),
                    "sha256": digest,
                }
            )
            expected[(region.name, region.slice_id)] = digest

        with tempfile.TemporaryDirectory(prefix="ndp-physical-probe-") as directory:
            request_path = Path(directory) / "request.json"
            request_path.write_text(
                json.dumps(request, sort_keys=True), encoding="utf-8"
            )
            try:
                completed = subprocess.run(
                    [
                        str(self.python_executable),
                        "-m",
                        "tools.physical_image_probe",
                        str(request_path),
                    ],
                    cwd=self.repository,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_seconds,
                )
            except subprocess.TimeoutExpired as error:
                raise PipelineError(
                    f"NDP physical-image probe timed out after {self.timeout_seconds}s"
                ) from error
        if completed.returncode != 0:
            raise PipelineError(
                "NDP physical-image probe failed: "
                + (completed.stderr.strip() or completed.stdout.strip())
            )
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise PipelineError("NDP physical-image probe returned invalid JSON") from error
        if response.get("schema_version") != "0.1":
            raise PipelineError("NDP physical-image probe returned an unsupported schema")
        if int(response.get("total_bytes", -1)) != geometry.total_bytes:
            raise PipelineError("NDP physical-image probe returned the wrong DRAM capacity")
        if len(response.get("regions", [])) != len(expected):
            raise PipelineError("NDP physical-image probe returned the wrong region count")
        seen: set[tuple[str, int]] = set()
        for region in response["regions"]:
            key = (region["name"], int(region["slice_id"]))
            if key not in expected:
                raise PipelineError(f"NDP probe returned an unexpected region: {key}")
            if not region["hash_matches"] or region["sha256"] != expected[key]:
                raise PipelineError(f"NDP probe corrupted physical bytes for region: {key}")
            if (
                int(region["start_coordinate"][0]) != key[1]
                or int(region["end_coordinate"][0]) != key[1]
            ):
                raise PipelineError(f"NDP probe mapped region to the wrong slice: {key}")
            seen.add(key)
        if seen != set(expected):
            raise PipelineError("NDP probe did not return every physical region")
        if int(response["per_slice"]) != geometry.bytes_per_slice:
            raise PipelineError("NDP DRAM per_slice disagrees with the W2 geometry")
        return NdpPhysicalProbeResult(
            per_slice=int(response["per_slice"]),
            total_bytes=int(response["total_bytes"]),
            regions=tuple(response["regions"]),
        )
