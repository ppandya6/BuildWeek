from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
WORKFLOW_PATH = ROOT / ".github/workflows/publish.yml"


def workflow():
    return yaml.load(WORKFLOW_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_triggers_are_tag_or_dry_run_manual_only():
    data = workflow()
    triggers = data["on"]
    assert set(triggers) == {"push", "workflow_dispatch"}
    assert triggers["push"] == {"tags": ["v*"]}
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"version"}
    assert inputs["version"]["default"] == "0.1.0a1"
    assert "pull_request" not in triggers


def test_publication_is_exact_tag_guarded_and_environment_protected():
    jobs = workflow()["jobs"]
    publish = jobs["publish"]
    assert publish["environment"]["name"] == "pypi"
    condition = publish["if"]
    assert "dry-run == 'false'" in condition
    assert "github.event_name == 'push'" in condition
    assert "refs/tags/v{0}" in condition
    assert publish["needs"] == ["preflight", "build", "validate", "approval"]
    assert "validate_release_ref.py" in WORKFLOW_PATH.read_text(encoding="utf-8")


def test_oidc_and_write_permissions_are_least_privilege():
    jobs = workflow()["jobs"]
    assert jobs["publish"]["permissions"] == {
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
    }
    for name, job in jobs.items():
        if name != "publish":
            assert "id-token" not in job.get("permissions", {})
    assert jobs["github-prerelease"]["permissions"] == {"contents": "write"}


def test_build_once_then_download_exact_artifact():
    data = workflow()
    jobs = data["jobs"]
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert text.count("python -m build") == 1
    build_steps = str(jobs["build"]["steps"])
    assert build_steps.index("twine check") < build_steps.index("upload-artifact")
    assert "validate_distribution.py --artifacts-only" in build_steps
    assert "generate_checksums.py dist" in build_steps
    publish_steps = str(jobs["publish"]["steps"])
    assert "download-artifact" in publish_steps
    assert "gh-action-pypi-publish" in publish_steps
    assert "python -m build" not in publish_steps


def test_dry_run_cannot_publish_or_create_release():
    jobs = workflow()["jobs"]
    assert "dry-run == 'false'" in jobs["publish"]["if"]
    assert "dry-run == 'false'" in jobs["github-prerelease"]["if"]
    validate = str(jobs["validate"]["steps"])
    assert "DRY RUN: NOTHING WAS PUBLISHED" in validate
    assert "dry-run == 'true'" in validate


def test_release_follows_publish_and_verification_and_classifies_prerelease():
    jobs = workflow()["jobs"]
    assert jobs["verify-published"]["needs"] == ["preflight", "publish"]
    assert jobs["github-prerelease"]["needs"] == [
        "preflight",
        "build",
        "verify-published",
    ]
    release_steps = str(jobs["github-prerelease"]["steps"])
    assert "--prerelease" in release_steps
    assert "--latest=false" in release_steps
    assert "extract_release_notes.py" in release_steps


def test_security_sensitive_actions_are_immutable_and_no_secrets_or_ai():
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "uses:" in line:
            reference = line.split("@", 1)[1].split()[0]
            assert len(reference) == 40
            assert all(character in "0123456789abcdef" for character in reference)
    lowered = text.lower()
    assert "pypi_api_token" not in lowered
    assert "password:" not in lowered
    assert "secrets." not in lowered
    assert "openai" not in lowered
    assert "repository-url" not in lowered
