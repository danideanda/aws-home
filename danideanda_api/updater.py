import logging
import os
import subprocess
import sys
import threading
from pathlib import Path


logger = logging.getLogger(__name__)
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_REMOTES = {
    "https://github.com/danideanda/aws-home",
    "https://github.com/danideanda/aws-home.git",
    "git@github.com:danideanda/aws-home",
    "git@github.com:danideanda/aws-home.git",
    "ssh://git@github.com/danideanda/aws-home",
    "ssh://git@github.com/danideanda/aws-home.git",
}
CHECK_TIMEOUT_SECONDS = 60
_restart_required = False


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        timeout=CHECK_TIMEOUT_SECONDS,
        check=False,
    )


def _is_clean() -> bool:
    result = _git("status", "--porcelain", "--untracked-files=all")
    if result.returncode != 0:
        logger.error("Could not inspect the repository: %s", result.stderr.strip())
        return False
    if result.stdout:
        logger.warning("Automatic update skipped because the worktree is not clean")
        return False
    return True


def check_for_updates() -> bool:
    """Fast-forward the official main branch if the local checkout is clean."""
    global _restart_required

    if _restart_required:
        os.execv(
            sys.executable,
            [sys.executable, str(REPOSITORY_ROOT / "main.py"), *sys.argv[1:]],
        )
        return True

    remote = _git("remote", "get-url", "origin")
    if remote.returncode != 0:
        logger.error("Automatic update skipped: origin remote is unavailable")
        return False
    if remote.stdout.strip() not in EXPECTED_REMOTES:
        logger.error("Automatic update skipped: origin is not the official repository")
        return False

    branch = _git("branch", "--show-current")
    if branch.returncode != 0 or branch.stdout.strip() != "main":
        logger.warning("Automatic update skipped: checkout is not on branch main")
        return False
    if not _is_clean():
        return False

    fetch = _git("fetch", "--quiet", "--no-tags", "origin", "main")
    if fetch.returncode != 0:
        logger.error("Could not fetch origin/main: %s", fetch.stderr.strip())
        return False
    if not _is_clean():
        return False

    local_head = _git("rev-parse", "HEAD")
    remote_head = _git("rev-parse", "FETCH_HEAD")
    if local_head.returncode != 0 or remote_head.returncode != 0:
        logger.error("Could not compare local and remote commits")
        return False
    if local_head.stdout.strip() == remote_head.stdout.strip():
        return False

    is_fast_forward = _git("merge-base", "--is-ancestor", "HEAD", "FETCH_HEAD")
    if is_fast_forward.returncode != 0:
        logger.warning("Automatic update skipped: origin/main is not a fast-forward")
        return False

    merge = _git("merge", "--ff-only", "FETCH_HEAD")
    if merge.returncode != 0:
        logger.error("Could not fast-forward to origin/main: %s", merge.stderr.strip())
        return False

    _restart_required = True
    logger.info("Updated to origin/main; restarting the service")
    os.execv(
        sys.executable,
        [sys.executable, str(REPOSITORY_ROOT / "main.py"), *sys.argv[1:]],
    )
    return True


def _monitor(interval_seconds: int, stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            if check_for_updates():
                return
        except (OSError, subprocess.TimeoutExpired) as error:
            logger.exception("Automatic update check failed: %s", error)
        stop_event.wait(interval_seconds)


def start_update_monitor() -> None:
    raw_interval = os.getenv("UPDATE_CHECK_INTERVAL_SECONDS", "300")
    try:
        interval_seconds = int(raw_interval)
    except ValueError:
        logger.error("Invalid UPDATE_CHECK_INTERVAL_SECONDS; automatic updates disabled")
        return
    if interval_seconds < 60:
        logger.error(
            "Update interval must be at least 60 seconds; automatic updates disabled"
        )
        return

    stop_event = threading.Event()
    threading.Thread(
        target=_monitor,
        args=(interval_seconds, stop_event),
        name="repository-update-monitor",
        daemon=True,
    ).start()
    logger.info("Automatic update checks enabled every %s seconds", interval_seconds)
