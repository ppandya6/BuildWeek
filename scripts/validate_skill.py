"""Validate the repository's portable Slide-of-Life Agent Skill."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "slide-of-life"
REQUIRED_RESOURCES = {
    "SKILL.md",
    "agents/openai.yaml",
    "references/audit-workflow.md",
    "references/input-preparation.md",
    "references/report-interpretation.md",
    "references/ai-schema-assistance.md",
    "references/troubleshooting.md",
    "examples/basic-audit.md",
    "examples/repair-audit.md",
    "examples/github-action.md",
}
MARKDOWN_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
PLAUSIBLE_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")


def _frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        raw, _ = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("SKILL.md frontmatter is not closed") from exc
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict):
        raise ValueError("SKILL.md frontmatter must be a mapping")
    return parsed


def validate() -> list[str]:
    errors: list[str] = []
    missing = sorted(
        path for path in REQUIRED_RESOURCES if not (SKILL / path).is_file()
    )
    if missing:
        errors.append("missing required files: " + ", ".join(missing))
        return errors

    files = sorted(SKILL.rglob("*"))
    markdown = [path for path in files if path.suffix == ".md"]
    skill_text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    try:
        metadata = _frontmatter(skill_text)
    except ValueError as exc:
        errors.append(str(exc))
        metadata = {}
    if set(metadata) != {"name", "description"}:
        errors.append(
            "frontmatter must contain only standard name and description fields"
        )
    if metadata.get("name") != "slide-of-life":
        errors.append("frontmatter name must match the slide-of-life directory")
    description = metadata.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024:
        errors.append("description must contain 1-1024 characters")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in markdown)
    required_phrases = {
        "exit 0": "**0:**",
        "exit 1": "**1:**",
        "exit 2": "**2:**",
        "factual layer": "Factual detection",
        "policy layer": "Policy evaluation",
        "repair layer": "Repair proposal",
        "public command": "slide-of-life audit",
        "AI limitation": "only propose schema mappings",
        "review requirement": "requiring researcher review",
    }
    for label, phrase in required_phrases.items():
        if phrase not in combined:
            errors.append(f"missing {label}: {phrase}")

    for path in markdown:
        text = path.read_text(encoding="utf-8")
        if "SlideLineage" in text:
            errors.append(f"deprecated product name in {path.relative_to(ROOT)}")
        if PLAUSIBLE_KEY.search(text):
            errors.append(f"plausible API key in {path.relative_to(ROOT)}")
        for target in MARKDOWN_LINK.findall(text):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if not resolved.is_relative_to(SKILL.resolve()) or not resolved.exists():
                errors.append(
                    f"broken relative link in {path.relative_to(ROOT)}: {target}"
                )

    non_troubleshooting = "\n".join(
        path.read_text(encoding="utf-8")
        for path in markdown
        if path.name != "troubleshooting.md"
    )
    if "slidelineage audit" in combined:
        errors.append(
            "deprecated compatibility command must not be shown as an audit command"
        )
    allowed_mention = (
        "Mention the old `slidelineage` command only as deprecated compatibility "
        "guidance in troubleshooting."
    )
    if "`slidelineage`" in non_troubleshooting.replace(allowed_mention, ""):
        errors.append("compatibility command appears outside troubleshooting guidance")

    action = (SKILL / "examples/github-action.md").read_text(encoding="utf-8")
    if re.search(r"(?im)^\s+api-key\s*:", action):
        errors.append("GitHub Action example contains an API-key input")
    if "@main" in action or "@codex/" in action:
        errors.append("GitHub Action example presents an unpinned branch")
    forbidden = (
        "automatically replace",
        "automatically commit",
        "apply repairs automatically",
    )
    for phrase in forbidden:
        if phrase in combined.lower():
            errors.append(f"automatic manifest modification instruction: {phrase}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Skill package valid: {SKILL.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
