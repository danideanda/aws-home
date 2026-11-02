#!/usr/bin/env python3
"""Gestión de usuarios del sistema de cursos.

Uso (como root):
    sudo /home/admin/.venv/bin/python tools/course_users.py list
    sudo /home/admin/.venv/bin/python tools/course_users.py add alumno
    sudo /home/admin/.venv/bin/python tools/course_users.py passwd alumno
    sudo /home/admin/.venv/bin/python tools/course_users.py remove alumno

Las contraseñas se guardan como hash scrypt; el fichero resultante es
/etc/aws-home/secrets/courses.json con permisos 0640 root:admin.
"""

from __future__ import annotations

import argparse
import getpass
import grp
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from danideanda_api.auth import USERS_FILE, hash_password  # noqa: E402

GROUP_NAME = "admin"
FILE_MODE = 0o640


def load() -> dict[str, dict]:
    try:
        raw = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"users": {}}
    if not isinstance(raw, dict) or not isinstance(raw.get("users"), dict):
        return {"users": {}}
    return raw


def save(data: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USERS_FILE.with_name(USERS_FILE.name + ".tmp")

    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")

    os.chmod(tmp, FILE_MODE)
    try:
        gid = grp.getgrnam(GROUP_NAME).gr_gid
        os.chown(tmp, 0, gid)
    except KeyError:
        os.chown(tmp, 0, 0)

    os.replace(tmp, USERS_FILE)


def read_password(provided: str | None) -> str:
    if provided is not None:
        if len(provided) < 10:
            raise SystemExit("La contraseña debe tener al menos 10 caracteres.")
        return provided

    first = getpass.getpass("Contraseña: ")
    if len(first) < 10:
        raise SystemExit("La contraseña debe tener al menos 10 caracteres.")
    if first != getpass.getpass("Repite la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden.")
    return first


def command_add(args: argparse.Namespace) -> int:
    data = load()
    if args.username in data["users"]:
        print(f"El usuario {args.username!r} ya existe. Usa 'passwd'.", file=sys.stderr)
        return 1

    record = hash_password(read_password(args.password))
    record["created"] = datetime.now(timezone.utc).isoformat()
    data["users"][args.username] = record
    save(data)
    print(f"Usuario {args.username!r} creado.")
    return 0


def command_passwd(args: argparse.Namespace) -> int:
    data = load()
    if args.username not in data["users"]:
        print(f"El usuario {args.username!r} no existe.", file=sys.stderr)
        return 1

    record = hash_password(read_password(args.password))
    record["created"] = data["users"][args.username].get("created")
    record["updated"] = datetime.now(timezone.utc).isoformat()
    data["users"][args.username] = record
    save(data)
    print(f"Contraseña de {args.username!r} actualizada.")
    return 0


def command_remove(args: argparse.Namespace) -> int:
    data = load()
    if args.username not in data["users"]:
        print(f"El usuario {args.username!r} no existe.", file=sys.stderr)
        return 1
    del data["users"][args.username]
    save(data)
    print(f"Usuario {args.username!r} eliminado.")
    return 0


def command_list(_: argparse.Namespace) -> int:
    users = load()["users"]
    if not users:
        print("(sin usuarios)")
        return 0
    for name in sorted(users):
        print(name)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Usuarios del sistema de cursos")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="crear un usuario")
    add.add_argument("username")
    add.add_argument("--password", help="contraseña (evita el prompt; queda en el historial)")
    add.set_defaults(func=command_add)

    passwd = sub.add_parser("passwd", help="cambiar la contraseña")
    passwd.add_argument("username")
    passwd.add_argument("--password")
    passwd.set_defaults(func=command_passwd)

    remove = sub.add_parser("remove", help="eliminar un usuario")
    remove.add_argument("username")
    remove.set_defaults(func=command_remove)

    listing = sub.add_parser("list", help="listar usuarios")
    listing.set_defaults(func=command_list)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
