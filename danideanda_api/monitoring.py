"""Monitorización del servidor en modo solo lectura.

Lee exclusivamente /proc y metadatos del sistema de ficheros. No ejecuta
comandos ni procesos externos.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def uptime_seconds() -> float | None:
    parts = _read("/proc/uptime").split()
    try:
        return round(float(parts[0]), 2)
    except (IndexError, ValueError):
        return None


def load_average() -> dict[str, float] | None:
    parts = _read("/proc/loadavg").split()
    try:
        return {"1m": float(parts[0]), "5m": float(parts[1]), "15m": float(parts[2])}
    except (IndexError, ValueError):
        return None


def memory() -> dict[str, int] | None:
    values: dict[str, int] = {}
    for line in _read("/proc/meminfo").splitlines():
        name, _, rest = line.partition(":")
        fields = rest.split()
        if not fields:
            continue
        try:
            values[name.strip()] = int(fields[0]) * 1024
        except ValueError:
            continue

    total = values.get("MemTotal")
    if total is None:
        return None
    available = values.get("MemAvailable", values.get("MemFree", 0))
    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_bytes": max(total - available, 0),
    }


def disk(path: str = "/") -> dict[str, int] | None:
    try:
        stats = os.statvfs(path)
    except OSError:
        return None
    total = stats.f_blocks * stats.f_frsize
    free = stats.f_bavail * stats.f_frsize
    return {
        "total_bytes": total,
        "free_bytes": free,
        "used_bytes": total - free,
    }


def process() -> dict[str, Any]:
    rss_bytes: int | None = None
    threads: int | None = None
    for line in _read("/proc/self/status").splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2:
                rss_bytes = int(parts[1]) * 1024
        elif line.startswith("Threads:"):
            parts = line.split()
            if len(parts) >= 2:
                threads = int(parts[1])

    try:
        open_fds = len(os.listdir("/proc/self/fd"))
    except OSError:
        open_fds = None

    return {
        "pid": os.getpid(),
        "rss_bytes": rss_bytes,
        "threads": threads,
        "open_file_descriptors": open_fds,
    }


def snapshot() -> dict[str, Any]:
    return {
        "uptime_seconds": uptime_seconds(),
        "load_average": load_average(),
        "cpu_count": os.cpu_count(),
        "memory": memory(),
        "disk": disk("/"),
        "process": process(),
    }
