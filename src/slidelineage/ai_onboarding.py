"""Safe, process-local credential onboarding for optional AI schema assistance."""

from __future__ import annotations

import getpass
import os
import sys
import webbrowser
from collections.abc import Callable, Mapping, MutableMapping
from dataclasses import dataclass
from typing import Literal

OPENAI_API_KEY_URL = "https://platform.openai.com/api-keys"
OPENAI_QUICKSTART_URL = "https://platform.openai.com/docs/quickstart"

CredentialSource = Literal[
    "environment", "interactive_session", "unavailable", "declined", "not_requested"
]


@dataclass(frozen=True)
class AiCredentialResolution:
    """Credential decision metadata; deliberately never contains a secret."""

    ai_enabled_for_run: bool
    credential_source: CredentialSource
    user_declined: bool = False
    browser_open_requested: bool = False
    browser_open_succeeded: bool = False
    warning: str | None = None
    exit_requested: bool = False


def is_interactive_environment(
    *,
    environment: Mapping[str, str] | None = None,
    stdin_isatty: Callable[[], bool] | None = None,
    stdout_isatty: Callable[[], bool] | None = None,
    stderr_isatty: Callable[[], bool] | None = None,
) -> bool:
    """Return whether local terminal interaction is safe and expected."""

    env = os.environ if environment is None else environment
    if env.get("CI", "").strip().lower() in {"1", "true", "yes"}:
        return False
    if env.get("GITHUB_ACTIONS", "").strip().lower() == "true":
        return False
    stdin_check = sys.stdin.isatty if stdin_isatty is None else stdin_isatty
    stdout_check = sys.stdout.isatty if stdout_isatty is None else stdout_isatty
    stderr_check = sys.stderr.isatty if stderr_isatty is None else stderr_isatty
    return stdin_check() and (stdout_check() or stderr_check())


def credential_failure_guidance(*, noninteractive: bool) -> str:
    """Return secret-free setup guidance for a focused CLI failure."""

    context = (
        "In GitHub Actions, store the key in GitHub Secrets and expose it as "
        "OPENAI_API_KEY. "
        if noninteractive
        else ""
    )
    return (
        "AI mode requires OPENAI_API_KEY unless an explicit schema-map file resolves "
        f"the fields. {context}API keys: {OPENAI_API_KEY_URL}\n"
        '$env:OPENAI_API_KEY="your-key"\n'
        'export OPENAI_API_KEY="your-key"'
    )


def resolve_ai_credentials(
    *,
    ai_requested: bool,
    deterministic_coverage_sufficient: bool,
    environment: MutableMapping[str, str] | None = None,
    interactive: bool | None = None,
    input_fn: Callable[[str], str] = input,
    secret_input_fn: Callable[[str], str] = getpass.getpass,
    browser_open_fn: Callable[[str], bool] = webbrowser.open,
    output_fn: Callable[[str], None] = print,
) -> AiCredentialResolution:
    """Resolve optional AI credentials without persisting or returning the key."""

    env = os.environ if environment is None else environment
    if not ai_requested:
        return AiCredentialResolution(False, "not_requested")
    if env.get("OPENAI_API_KEY", "").strip():
        return AiCredentialResolution(True, "environment")
    is_interactive = (
        is_interactive_environment(environment=env)
        if interactive is None
        else interactive
    )
    if not is_interactive:
        warning = (
            "AI was requested but credentials are unavailable; no AI request was sent."
        )
        return AiCredentialResolution(
            False,
            "unavailable",
            warning=warning,
            exit_requested=not deterministic_coverage_sufficient,
        )

    output_fn(
        "AI schema assistance is optional and OpenAI API usage may incur charges.\n"
        "Headers and aggregate column statistics may be sent; raw rows, literal "
        "record values, image paths, and image bytes are not sent.\n"
        "The key will not be stored by Slide-of-Life."
    )
    opened = False
    succeeded = False
    attempts = 0
    while attempts < 20:
        attempts += 1
        try:
            choice = (
                input_fn(
                    "[O] Open key page  [P] Paste key  "
                    "[C] Continue without AI  [Q] Quit: "
                )
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            output_fn("AI onboarding cancelled.")
            return AiCredentialResolution(
                False,
                "unavailable",
                exit_requested=True,
                warning="AI onboarding cancelled.",
            )
        if choice == "o":
            try:
                confirm = input_fn("Open the official OpenAI API key page? [y/N]: ")
            except (EOFError, KeyboardInterrupt):
                confirm = ""
            if confirm.strip().lower() in {"y", "yes"}:
                opened = True
                succeeded = bool(browser_open_fn(OPENAI_API_KEY_URL))
                output_fn(
                    "Browser-open request accepted."
                    if succeeded
                    else "Browser-open request was not accepted."
                )
            else:
                output_fn("Browser was not opened.")
            continue
        if choice == "p":
            try:
                key = secret_input_fn("OpenAI API key for this run: ").strip()
            except (EOFError, KeyboardInterrupt):
                output_fn("AI onboarding cancelled.")
                return AiCredentialResolution(
                    False,
                    "unavailable",
                    exit_requested=True,
                    warning="AI onboarding cancelled.",
                )
            if not key:
                output_fn("The API key cannot be blank; try again.")
                continue
            env["OPENAI_API_KEY"] = key
            return AiCredentialResolution(
                True,
                "interactive_session",
                browser_open_requested=opened,
                browser_open_succeeded=succeeded,
            )
        if choice == "c":
            warning = (
                "AI was requested but declined interactively; no AI request was sent."
            )
            return AiCredentialResolution(
                False,
                "declined",
                user_declined=True,
                browser_open_requested=opened,
                browser_open_succeeded=succeeded,
                warning=warning,
                exit_requested=not deterministic_coverage_sufficient,
            )
        if choice == "q":
            output_fn("AI onboarding cancelled.")
            return AiCredentialResolution(
                False,
                "unavailable",
                browser_open_requested=opened,
                browser_open_succeeded=succeeded,
                exit_requested=True,
                warning="AI onboarding cancelled.",
            )
        output_fn("Choose O, P, C, or Q.")
    return AiCredentialResolution(
        False,
        "unavailable",
        exit_requested=True,
        warning="AI onboarding retry limit reached.",
    )
