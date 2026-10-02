"""Paths and identities shared by the portable Workboard commands."""

import re
import subprocess
from pathlib import Path

SESSION = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
PACKAGE_BIN = Path(__file__).resolve().parent.parent / "bin" / "samepage"


def valid_session(value):
    return isinstance(value, str) and SESSION.fullmatch(value) is not None


def project_paths(project):
    """Use the same main-checkout brain as bin/samepage, including worktrees."""
    cwd = Path(project).expanduser().resolve(strict=True)
    if not cwd.is_dir():
        raise ValueError("Project must be a directory")
    result = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True, text=True, check=False,
    )
    main = Path(result.stdout.strip()).resolve().parent if result.returncode == 0 else cwd
    return cwd, main / ".samepage"


def branch_wip(cwd, brain):
    result = subprocess.run(
        ["git", "-C", str(cwd), "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True, text=True, check=False,
    )
    branch = result.stdout.strip()
    if not branch:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        branch = result.stdout.strip() or "unborn"
    return brain / "wip" / (branch.replace("/", "-") + ".md")
