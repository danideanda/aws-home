"""Comprobaciones de seguridad del servidor en modo solo lectura.

No ejecuta comandos: lee /var/log/auth.log, /etc/group, sshd_config,
/proc/net/tcp y permisos de ficheros.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUTH_LOG = Path("/var/log/auth.log")
SECRETS_DIR = Path("/etc/aws-home/secrets")
SSHD_CONFIG = Path("/etc/ssh/sshd_config")
SSHD_CONFIG_DIR = Path("/etc/ssh/sshd_config.d")
REBOOT_REQUIRED = Path("/var/run/reboot-required")

SECRET_FILES = ("api.key", "session.key", "courses.json")

_FAILURE_PATTERN = re.compile(
    r"Failed (?:password|publickey) for (?:invalid user )?\S+ from (\S+)"
)
_SYSLOG_TIME = re.compile(r"^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})")
_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def _line_timestamp(line: str, reference: datetime) -> float | None:
    match = _SYSLOG_TIME.match(line)
    if not match:
        return None
    month_name, day, hour, minute, second = match.groups()
    try:
        moment = datetime(
            reference.year,
            _MONTHS[month_name],
            int(day),
            int(hour),
            int(minute),
            int(second),
            tzinfo=timezone.utc,
        )
    except (KeyError, ValueError):
        return None
    if moment > reference:
        try:
            moment = moment.replace(year=reference.year - 1)
        except ValueError:
            return None
    return moment.timestamp()


def _read_auth_log(max_bytes: int) -> str | None:
    try:
        with AUTH_LOG.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            return handle.read().decode("utf-8", "replace")
    except OSError:
        return None


def _read_journal(hours: int) -> str | None:
    """Fallback sin shell: argv fijo, sin entrada del usuario."""
    try:
        result = subprocess.run(
            [
                "journalctl",
                "-u",
                "ssh",
                "--since",
                f"-{int(hours)} hours",
                "--no-pager",
                "-o",
                "short",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def failed_logins(hours: int = 24, max_bytes: int = 512 * 1024) -> dict[str, Any]:
    data = _read_auth_log(max_bytes)
    source = "auth.log"
    if data is None:
        data = _read_journal(hours)
        source = "journald"

    if data is None:
        return {
            "available": False,
            "window_hours": hours,
            "total": 0,
            "top_ips": [],
        }

    now = datetime.now(timezone.utc)
    cutoff = time.time() - hours * 3600
    counts: Counter[str] = Counter()
    total = 0

    for line in data.splitlines():
        match = _FAILURE_PATTERN.search(line)
        if not match:
            continue
        moment = _line_timestamp(line, now)
        if moment is not None and moment < cutoff:
            continue
        total += 1
        counts[match.group(1)] += 1

    return {
        "available": True,
        "source": source,
        "window_hours": hours,
        "total": total,
        "top_ips": [{"ip": ip, "count": count} for ip, count in counts.most_common(5)],
    }


def ssh_settings() -> dict[str, str]:
    files = [SSHD_CONFIG]
    try:
        files.extend(sorted(SSHD_CONFIG_DIR.glob("*.conf")))
    except OSError:
        pass

    wanted = {
        "port",
        "permitrootlogin",
        "passwordauthentication",
        "pubkeyauthentication",
        "maxauthtries",
        "challengeresponseauthentication",
    }
    settings: dict[str, str] = {}

    for path in files:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split(None, 1)
            if len(parts) != 2:
                continue
            key = parts[0].lower()
            if key in wanted:
                settings[key] = parts[1].strip()

    return settings


def sudo_members() -> list[str]:
    try:
        lines = Path("/etc/group").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if line.startswith("sudo:"):
            fields = line.split(":")
            if len(fields) >= 4:
                return [member for member in fields[3].split(",") if member]
    return []


def _secret_file_status() -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for name in SECRET_FILES:
        path = SECRETS_DIR / name
        entry: dict[str, Any] = {"name": name, "exists": False, "warnings": []}
        try:
            info = path.stat()
        except OSError:
            report.append(entry)
            continue

        mode = stat.S_IMODE(info.st_mode)
        entry.update(
            {
                "exists": True,
                "mode": oct(mode),
                "size": info.st_size,
                "owner_uid": info.st_uid,
                "group_gid": info.st_gid,
            }
        )
        if mode & 0o004:
            entry["warnings"].append("legible por cualquier usuario")
        if mode & 0o002:
            entry["warnings"].append("escribible por cualquier usuario")
        if mode & 0o020:
            entry["warnings"].append("escribible por el grupo")
        report.append(entry)
    return report


def listening_ports() -> list[int]:
    ports: set[int] = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 4 or fields[3] != "0A":
                continue  # 0A == LISTEN
            _, _, raw_port = fields[1].rpartition(":")
            try:
                ports.add(int(raw_port, 16))
            except ValueError:
                continue
    return sorted(ports)


def snapshot() -> dict[str, Any]:
    return {
        "failed_ssh_logins": failed_logins(),
        "ssh": ssh_settings(),
        "sudo_members": sudo_members(),
        "secret_files": _secret_file_status(),
        "listening_tcp_ports": listening_ports(),
        "reboot_required": REBOOT_REQUIRED.exists(),
    }
