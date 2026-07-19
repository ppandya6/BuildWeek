"""Build, inspect, and smoke-test release artifacts in isolated environments."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0a1"
REQUIRED_SDIST = {
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "action.yml",
    "skills/slide-of-life/SKILL.md",
    "tests/test_distribution_package.py",
}
FORBIDDEN = ("gh" + "p_", "github" + "_pat_", "/" + "Users/", "\\" + "Users\\")


def run(
    args: list[str], *, cwd: Path | None = None, expected: tuple[int, ...] = (0,)
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        args, cwd=cwd or ROOT, env=env, text=True, capture_output=True
    )
    if result.returncode not in expected:
        raise RuntimeError(
            f"command failed ({result.returncode}): {args!r}\n"
            f"{result.stdout}\n{result.stderr}"
        )
    return result


def python_in(env: Path) -> Path:
    return env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def command_in(env: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return env / ("Scripts" if os.name == "nt" else "bin") / f"{name}{suffix}"


def fixture(path: Path) -> tuple[Path, Path]:
    train, test = path / "train.csv", path / "test.csv"
    for target, row in ((train, ["train-1", "PAT-A"]), (test, ["test-1", "PAT-B"])):
        with target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["record_id", "patient_id"])
            writer.writerow(row)
    return train, test


def smoke(artifact: Path, *, ai: bool = False) -> str:
    with tempfile.TemporaryDirectory(prefix="slide-of-life-install-") as raw:
        temp = Path(raw)
        env = temp / "venv"
        venv.EnvBuilder(with_pip=True).create(env)
        py = python_in(env)
        spec = (
            f"slide-of-life[ai] @ {artifact.resolve().as_uri()}"
            if ai
            else str(artifact)
        )
        run([str(py), "-m", "pip", "install", spec], cwd=temp)
        location = run(
            [
                str(py),
                "-c",
                (
                    "import pathlib,slidelineage; "
                    "print(pathlib.Path(slidelineage.__file__).resolve())"
                ),
            ],
            cwd=temp,
        ).stdout.strip()
        if not Path(location).is_relative_to(env.resolve()):
            raise RuntimeError(f"module escaped venv: {location}")
        if ai:
            run(
                [str(py), "-c", "import openai; import slidelineage.ai_schema"],
                cwd=temp,
            )
            return location
        primary = command_in(env, "slide-of-life")
        compat = command_in(env, "slidelineage")
        run([str(primary), "--help"], cwd=temp)
        version = run([str(primary), "--version"], cwd=temp)
        if VERSION not in version.stdout:
            raise RuntimeError("incorrect CLI version")
        warning = run([str(compat), "--help"], cwd=temp)
        if "retained for compatibility" not in warning.stderr:
            raise RuntimeError("compatibility warning missing")
        module = run([str(py), "-m", "slidelineage", "--help"], cwd=temp)
        if "compatibility" in module.stderr:
            raise RuntimeError("module emitted alias warning")
        train, test = fixture(temp)
        output = temp / "audit"
        run(
            [
                str(primary),
                "audit",
                "--train",
                str(train),
                "--test",
                str(test),
                "--output",
                str(output),
                "--patient-column",
                "patient_id",
                "--record-id-column",
                "record_id",
            ],
            cwd=temp,
        )
        for name in ("report.json", "report.html", "findings.csv"):
            if not (output / name).is_file():
                raise RuntimeError(f"missing {name}")
        if (output / "repair_proposal.csv").exists():
            raise RuntimeError("unexpected repair proposal")
        if "Slide-of-Life" not in (output / "report.html").read_text(encoding="utf-8"):
            raise RuntimeError("report branding missing")
        return location


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifacts-only",
        action="store_true",
        help="validate existing dist artifacts without rebuilding",
    )
    args = parser.parse_args()
    if not args.artifacts_only:
        shutil.rmtree(ROOT / "dist", ignore_errors=True)
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        run([sys.executable, "-m", "build"])
    artifacts = sorted((ROOT / "dist").iterdir())
    wheels = [p for p in artifacts if p.suffix == ".whl"]
    sdists = [p for p in artifacts if p.name.endswith(".tar.gz")]
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError(f"expected one wheel and sdist: {artifacts}")
    run([sys.executable, "-m", "twine", "check", *map(str, artifacts)])
    wheel, sdist = wheels[0], sdists[0]
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
        payloads = [archive.read(n) for n in wheel_names]
    if any(n.startswith(("tests/", "skills/")) for n in wheel_names):
        raise RuntimeError("wheel contains repository-only files")
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        prefix = members[0].name.split("/", 1)[0]
        relative = {m.name.removeprefix(prefix + "/") for m in members}
        payloads += [
            archive.extractfile(m).read()
            for m in members
            if m.isfile() and archive.extractfile(m)
        ]
    missing = REQUIRED_SDIST - relative
    if missing:
        raise RuntimeError(f"sdist missing: {sorted(missing)}")
    text = b"\n".join(payloads).decode("utf-8", errors="ignore")
    for marker in FORBIDDEN:
        if marker in text:
            raise RuntimeError(f"archive security marker found: {marker}")
    if any(
        "generated/" in n
        or n.endswith(
            (
                "report.json",
                "report.html",
                "findings.csv",
                "repair_proposal.csv",
                ".env",
            )
        )
        for n in relative | set(wheel_names)
    ):
        raise RuntimeError("generated/private artifact included")
    wheel_path = smoke(wheel)
    sdist_path = smoke(sdist)
    smoke(wheel, ai=True)
    print(f"validated {wheel.name} and {sdist.name}")
    print(f"wheel module: {wheel_path}\nsdist module: {sdist_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
