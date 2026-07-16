#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Validate repository license metadata consistency.

This script is intentionally repo-local so the framework can enforce basic
license metadata expectations in CI without depending on proprietary tooling.

Exit codes:
- 0: License metadata is internally consistent.
- 1: One or more consistency checks failed.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

EXPECTED_LICENSE = "AGPL-3.0-only"
EXPECTED_CLASSIFIER = "License :: OSI Approved :: GNU Affero General Public License v3"
LICENSE_SENTINEL = "GNU AFFERO GENERAL PUBLIC LICENSE"
README_REQUIRED_HEADINGS = (
    "## License",
    "## Production Use",
)
README_REQUIRED_SNIPPETS = (
    "AGPL-3.0-only",
    "GNU Affero General Public License v3.0 only",
)


def read_text(path: Path) -> str:
    """Read a UTF-8 text file."""
    return path.read_text(encoding="utf-8")


def extract_license_value(project_table: dict) -> str | None:
    """Return the normalized project license value from pyproject metadata."""
    license_value = project_table.get("license")
    if isinstance(license_value, str):
        return license_value
    if isinstance(license_value, dict):
        text_value = license_value.get("text")
        if isinstance(text_value, str):
            return text_value
    return None


def main() -> int:
    """Run the consistency checks."""
    repo_root = Path(__file__).resolve().parents[1]
    license_path = repo_root / "LICENSE"
    pyproject_path = repo_root / "pyproject.toml"
    readme_path = repo_root / "README.md"
    violations: list[str] = []

    if not license_path.exists():
        violations.append("Missing root LICENSE file.")
    else:
        license_text = read_text(license_path)
        if LICENSE_SENTINEL not in license_text:
            violations.append(
                "LICENSE does not appear to contain the GNU Affero General Public License text."
            )

    if not pyproject_path.exists():
        violations.append("Missing pyproject.toml.")
    else:
        pyproject_data = tomllib.loads(read_text(pyproject_path))
        project_table = pyproject_data.get("project", {})
        manifest_license = extract_license_value(project_table)
        if manifest_license != EXPECTED_LICENSE:
            violations.append(
                f"pyproject.toml project.license must be {EXPECTED_LICENSE!r}, got {manifest_license!r}."
            )

        classifiers = project_table.get("classifiers", [])
        if EXPECTED_CLASSIFIER not in classifiers:
            violations.append(
                f"pyproject.toml classifiers must include {EXPECTED_CLASSIFIER!r}."
            )

    if not readme_path.exists():
        violations.append("Missing README.md.")
    else:
        readme_text = read_text(readme_path)
        for heading in README_REQUIRED_HEADINGS:
            if heading not in readme_text:
                violations.append(f"README.md is missing the heading {heading!r}.")

        for snippet in README_REQUIRED_SNIPPETS:
            if snippet not in readme_text:
                violations.append(f"README.md is missing the text {snippet!r}.")

    if violations:
        print("❌ License metadata validation failed:")
        for violation in violations:
            print(f"- {violation}")
        return 1

    print("✅ License metadata is internally consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())