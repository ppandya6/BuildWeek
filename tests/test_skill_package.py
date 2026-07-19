"""Focused, network-free validation for the packaged Agent Skill."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills" / "slide-of-life"


def test_skill_package_contract() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_skill.py")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_examples_are_synthetic_and_platform_specific() -> None:
    examples = SKILL / "examples"
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(examples.glob("*.md"))
    )
    assert "generated_train.csv" in combined
    assert "## Bash" in combined
    assert "## PowerShell" in combined
    assert "clinical data" not in combined.lower()


def test_skill_does_not_modify_runtime_engine() -> None:
    runtime = ROOT / "src" / "slidelineage"
    assert all(path.is_file() for path in runtime.glob("*.py"))
    assert not (SKILL / "src").exists()


def test_required_report_and_action_safeguards() -> None:
    report = (SKILL / "references/report-interpretation.md").read_text(encoding="utf-8")
    repair = (SKILL / "examples/repair-audit.md").read_text(encoding="utf-8")
    action = (SKILL / "examples/github-action.md").read_text(encoding="utf-8")
    assert "check existence" in report.lower()
    assert "never replace or commit source manifests automatically" in repair.lower()
    assert "@<pinned-ref>" in action
    assert "api-key:" not in action.lower()
