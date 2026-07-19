"""Shared pytest configuration and helpers for Slide-of-Life tests."""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

import slidelineage.ai_schema as ai_schema
from slidelineage.config import AuditConfig

ISOLATED_ENVIRONMENT_VARIABLES = (
    "OPENAI_API_KEY",
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT",
    "CI",
    "GITHUB_ACTIONS",
    "GITHUB_OUTPUT",
    "GITHUB_STEP_SUMMARY",
    "NO_COLOR",
    "FORCE_COLOR",
    "PYTHONINSPECT",
    "PYTHONSTARTUP",
)
TEST_SECRET = "test-secret-never-log-123"
_ORIGINAL_CREATE_OPENAI_CLIENT = ai_schema._create_openai_client


@dataclass
class FakeTerminalStream:
    """Minimal stream double whose terminal state never depends on the runner."""

    terminal: bool

    def isatty(self) -> bool:
        return self.terminal


@pytest.fixture(autouse=True)
def isolate_process_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove repository-relevant ambient state and prohibit live AI clients."""

    for name in ISOLATED_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)

    def forbid_live_openai_client(config: AuditConfig) -> object:
        del config
        raise AssertionError(
            "A live OpenAI client was requested; inject a fake client in this test"
        )

    monkeypatch.setattr(ai_schema, "_create_openai_client", forbid_live_openai_client)
    yield


@pytest.fixture
def openai_api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("OPENAI_API_KEY", TEST_SECRET)
    return TEST_SECRET


@pytest.fixture
def mocked_openai_constructor_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow SDK construction only for tests that replace the SDK import with a fake."""

    monkeypatch.setattr(
        ai_schema, "_create_openai_client", _ORIGINAL_CREATE_OPENAI_CLIENT
    )


@pytest.fixture
def ci_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")


@pytest.fixture
def github_actions_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> dict[str, Path]:
    output = tmp_path / "github-output.txt"
    summary = tmp_path / "github-summary.md"
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    return {"output": output, "summary": summary}


@pytest.fixture
def interactive_terminal() -> tuple[FakeTerminalStream, FakeTerminalStream]:
    return FakeTerminalStream(True), FakeTerminalStream(True)


@pytest.fixture
def noninteractive_terminal() -> tuple[FakeTerminalStream, FakeTerminalStream]:
    return FakeTerminalStream(False), FakeTerminalStream(False)


def audit_manifest(path: Path, patient: str, rid: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "img,patient,specimen,slide,site,label,rid\n"
        f"{rid}.png,{patient},S{rid},L{rid},I,A,{rid}\n",
        encoding="utf-8",
    )
    return path


def audit_config(
    tmp_path: Path, same_patient: bool = False, repair: bool = False
) -> AuditConfig:
    train = audit_manifest(tmp_path / "train.csv", "P1", "R1")
    test = audit_manifest(tmp_path / "test.csv", "P1" if same_patient else "P2", "R2")
    return AuditConfig(
        train_manifest=train,
        test_manifest=test,
        output_dir=tmp_path / "out",
        image_column="img",
        patient_column="patient",
        specimen_column="specimen",
        slide_column="slide",
        institution_column="site",
        label_column="label",
        record_id_column="rid",
        repair=repair,
    )
