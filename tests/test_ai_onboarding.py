from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest

from slidelineage.ai_onboarding import (
    OPENAI_API_KEY_URL,
    AiCredentialResolution,
    credential_failure_guidance,
    is_interactive_environment,
    resolve_ai_credentials,
)


def _answers(*values: str) -> tuple[Callable[[str], str], list[str]]:
    iterator: Iterator[str] = iter(values)
    prompts: list[str] = []

    def answer(prompt: str) -> str:
        prompts.append(prompt)
        return next(iterator)

    return answer, prompts


def test_interactive_detection_respects_terminals_and_ci() -> None:
    def yes() -> bool:
        return True

    def no() -> bool:
        return False

    assert is_interactive_environment(
        environment={}, stdin_isatty=yes, stdout_isatty=yes, stderr_isatty=no
    )
    assert not is_interactive_environment(
        environment={}, stdin_isatty=no, stdout_isatty=yes, stderr_isatty=yes
    )
    assert not is_interactive_environment(
        environment={"CI": "true"},
        stdin_isatty=yes,
        stdout_isatty=yes,
        stderr_isatty=yes,
    )
    assert not is_interactive_environment(
        environment={"GITHUB_ACTIONS": "true"},
        stdin_isatty=yes,
        stdout_isatty=yes,
        stderr_isatty=yes,
    )


def test_not_requested_and_existing_key_never_prompt_or_enter_result() -> None:
    def forbidden(_: str) -> str:
        raise AssertionError("prompted")

    assert (
        resolve_ai_credentials(
            ai_requested=False,
            deterministic_coverage_sufficient=False,
            environment={},
            input_fn=forbidden,
        ).credential_source
        == "not_requested"
    )
    secret = "test-only-never-log"
    result = resolve_ai_credentials(
        ai_requested=True,
        deterministic_coverage_sufficient=False,
        environment={"OPENAI_API_KEY": f" {secret} "},
        input_fn=forbidden,
    )
    assert result.ai_enabled_for_run
    assert secret not in repr(result)


@pytest.mark.parametrize(("confirmed", "opened"), [("n", False), ("y", True)])
def test_open_page_requires_confirmation_and_returns_to_menu(
    confirmed: str, opened: bool
) -> None:
    answer, _ = _answers("o", confirmed, "c")
    urls: list[str] = []
    output: list[str] = []
    result = resolve_ai_credentials(
        ai_requested=True,
        deterministic_coverage_sufficient=True,
        environment={},
        interactive=True,
        input_fn=answer,
        browser_open_fn=lambda url: urls.append(url) is None or True,
        output_fn=output.append,
    )
    assert result.user_declined
    assert result.browser_open_requested is opened
    assert urls == ([OPENAI_API_KEY_URL] if opened else [])


def test_browser_failure_is_recorded() -> None:
    answer, _ = _answers("o", "yes", "c")
    result = resolve_ai_credentials(
        ai_requested=True,
        deterministic_coverage_sufficient=True,
        environment={},
        interactive=True,
        input_fn=answer,
        browser_open_fn=lambda _: False,
        output_fn=lambda _: None,
    )
    assert result.browser_open_requested and not result.browser_open_succeeded


def test_paste_rejects_blank_and_stores_only_in_process_environment() -> None:
    answer, _ = _answers("p", "p")
    secrets = iter(["  ", " fake-test-key "])
    env: dict[str, str] = {}
    output: list[str] = []
    result = resolve_ai_credentials(
        ai_requested=True,
        deterministic_coverage_sufficient=False,
        environment=env,
        interactive=True,
        input_fn=answer,
        secret_input_fn=lambda _: next(secrets),
        output_fn=output.append,
    )
    assert env["OPENAI_API_KEY"] == "fake-test-key"
    assert result.credential_source == "interactive_session"
    assert "fake-test-key" not in repr(result) + "".join(output)


def test_continue_and_noninteractive_fallback_contracts() -> None:
    answer, _ = _answers("c")
    declined = resolve_ai_credentials(
        ai_requested=True,
        deterministic_coverage_sufficient=True,
        environment={},
        interactive=True,
        input_fn=answer,
        output_fn=lambda _: None,
    )
    assert declined.user_declined and not declined.exit_requested
    missing = resolve_ai_credentials(
        ai_requested=True,
        deterministic_coverage_sufficient=False,
        environment={"CI": "true"},
    )
    assert missing.exit_requested and missing.credential_source == "unavailable"
    guidance = credential_failure_guidance(noninteractive=True)
    assert "GitHub Secrets" in guidance and OPENAI_API_KEY_URL in guidance
    assert "schema-map" in guidance


@pytest.mark.parametrize("event", ["q", EOFError(), KeyboardInterrupt()])
def test_quit_eof_and_interrupt_are_focused(event: object) -> None:
    def answer(_: str) -> str:
        if isinstance(event, BaseException):
            raise event
        return str(event)

    output: list[str] = []
    result = resolve_ai_credentials(
        ai_requested=True,
        deterministic_coverage_sufficient=False,
        environment={},
        interactive=True,
        input_fn=answer,
        output_fn=output.append,
    )
    assert result.exit_requested
    assert "Traceback" not in "".join(output)
    assert "your-key" in credential_failure_guidance(noninteractive=False)


def test_result_contract_has_no_secret_field() -> None:
    assert "key" not in AiCredentialResolution.__dataclass_fields__
