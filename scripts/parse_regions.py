#!/usr/bin/env python3
"""Parse regions.yaml into JSON outputs for CI matrices and validation.

Usage:
  parse_regions.py --file path/to/regions.yaml [--region NAME] [--github-output PATH]

Exit codes:
  0  success
  1  usage / I/O / parse error
  2  validation failure (empty list, duplicate names, invalid requested region)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REGION_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")


def _fail(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def load_yaml(path: Path) -> Any:
    try:
        import yaml  # type: ignore
    except ImportError:
        _fail(
            "PyYAML is required (pip install pyyaml). "
            "The fetch-regions action installs it automatically."
        )

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _fail(f"could not read {path}: {exc}")

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # type: ignore[name-defined]
        _fail(f"invalid YAML in {path}: {exc}")

    if data is None:
        _fail(f"{path} is empty")
    if not isinstance(data, dict):
        _fail(f"{path} must parse to a mapping at the root")
    return data


def parse_active_regions(data: dict[str, Any]) -> list[dict[str, Any]]:
    if "active_regions" not in data:
        _fail("missing required key: active_regions", code=2)

    raw = data["active_regions"]
    if not isinstance(raw, list) or not raw:
        _fail("active_regions must be a non-empty list", code=2)

    regions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            _fail(f"active_regions[{index}] must be a mapping", code=2)
        if "name" not in item or not isinstance(item["name"], str) or not item["name"].strip():
            _fail(f"active_regions[{index}].name is required", code=2)

        name = item["name"].strip()
        if not REGION_NAME_RE.match(name):
            _fail(
                f"active_regions[{index}].name {name!r} is not a valid region id",
                code=2,
            )
        if name in seen:
            _fail(f"duplicate region name: {name}", code=2)
        seen.add(name)

        entry: dict[str, Any] = {"name": name}
        for optional in ("tier", "endpoint_suffix"):
            if optional in item and item[optional] is not None:
                entry[optional] = item[optional]
        regions.append(entry)

    return regions


def write_github_output(path: Path, outputs: dict[str, str]) -> None:
    # GitHub Actions supports multiline values via heredoc delimiters.
    chunks: list[str] = []
    for key, value in outputs.items():
        if "\n" in value:
            delimiter = f"ghadelim_{key}"
            chunks.append(f"{key}<<{delimiter}\n{value}\n{delimiter}")
        else:
            chunks.append(f"{key}={value}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(chunks) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--file",
        required=True,
        type=Path,
        help="Path to regions.yaml",
    )
    parser.add_argument(
        "--region",
        default="",
        help="If set, require this region name to exist in active_regions",
    )
    parser.add_argument(
        "--github-output",
        type=Path,
        default=None,
        help="Append outputs in GitHub Actions format (usually $GITHUB_OUTPUT)",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print human-readable summary to stdout",
    )
    args = parser.parse_args(argv)

    regions = parse_active_regions(load_yaml(args.file))
    names = [r["name"] for r in regions]

    requested = (args.region or "").strip()
    if requested:
        if requested not in names:
            _fail(
                f"region {requested!r} is not enabled in active_regions "
                f"(enabled: {', '.join(names)})",
                code=2,
            )
        selected_names = [requested]
        selected_full = [r for r in regions if r["name"] == requested]
    else:
        selected_names = names
        selected_full = regions

    regions_json = json.dumps(selected_names, separators=(",", ":"))
    regions_matrix = json.dumps({"region": selected_names}, separators=(",", ":"))
    regions_full_json = json.dumps(selected_full, separators=(",", ":"))
    region_count = str(len(selected_names))

    outputs = {
        "regions-json": regions_json,
        "regions-matrix": regions_matrix,
        "regions-full-json": regions_full_json,
        "region-count": region_count,
    }

    if args.github_output is not None:
        write_github_output(args.github_output, outputs)

    if args.print or args.github_output is None:
        print(f"region_count={region_count}")
        print(f"regions-json={regions_json}")
        print(f"regions-matrix={regions_matrix}")
        print(f"regions-full-json={regions_full_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
