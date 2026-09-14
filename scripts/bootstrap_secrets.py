"""Create local Docker secrets without rotating existing credentials or printing values."""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from urllib.parse import quote


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASE_SECRETS = (
    "django_secret_key", "jwt_signing_key", "db_password", "db_root_password", "redis_password",
)


def secure_directory(directory: Path) -> None:
    """Restrict traversal on POSIX; remove inherited Windows access before creating files."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        directory.chmod(0o700)
        return
    identity = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        check=True, capture_output=True, text=True,
    )
    rows = list(csv.reader(identity.stdout.splitlines()))
    if len(rows) != 1 or len(rows[0]) != 2 or not re.fullmatch(r"S-1-[0-9-]+", rows[0][1]):
        raise RuntimeError("No se pudo verificar el propietario de los secretos.")
    sid = rows[0][1]
    environment = dict(os.environ, AMANDAYE_SECRET_DIRECTORY=str(directory), AMANDAYE_OWNER_SID=sid)
    # A fresh DACL also removes old explicit grants, not only inherited access.
    permission_script = r"""
$ErrorActionPreference = 'Stop'
$secretAcl = New-Object System.Security.AccessControl.DirectorySecurity
$secretAcl.SetAccessRuleProtection($true, $false)
foreach ($secretSid in @($env:AMANDAYE_OWNER_SID, 'S-1-5-18')) {
    $identity = New-Object System.Security.Principal.SecurityIdentifier($secretSid)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $identity, 'FullControl', 'ContainerInherit, ObjectInherit', 'None', 'Allow')
    $secretAcl.AddAccessRule($rule)
}
[System.IO.Directory]::SetAccessControl($env:AMANDAYE_SECRET_DIRECTORY, $secretAcl)
"""
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", permission_script],
        check=True, capture_output=True, text=True, env=environment,
    )


def validate_path(directory: Path) -> Path:
    candidate = directory if directory.is_absolute() else PROJECT_ROOT / directory
    # Do not follow links or Windows junctions when creating credential files.
    for part in (candidate, *candidate.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("El directorio de secretos no puede atravesar enlaces.")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(PROJECT_ROOT / "secrets"):
        raise ValueError("Elija secrets/ o uno de sus subdirectorios, excluidos de Git.")
    return resolved


def read_existing(path: Path) -> str | None:
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        raise ValueError(f"Se rechazó un enlace en {path.name}.")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"{path.name} no es un archivo regular.")
    return path.read_text(encoding="utf-8").strip()


def write_new(path: Path, value: str) -> None:
    # O_EXCL never overwrites an existing secret, including during simultaneous runs.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as destination:
        destination.write(value + "\n")
    # Compose file secrets are bind mounts: local uid/gid/mode overrides are ignored.
    # The private 0700 parent protects the host, while the mount is readable by the
    # explicitly authorized non-root container. Windows uses the restricted ACL above.
    if os.name != "nt":
        path.chmod(0o444)


def bootstrap(directory: Path) -> tuple[Path, int]:
    directory = validate_path(directory)
    secure_directory(directory)
    values = {}
    missing = []
    for name in BASE_SECRETS:
        existing = read_existing(directory / name)
        if existing is not None and not re.fullmatch(r"[A-Za-z0-9_-]{64,}", existing):
            raise ValueError(f"{name} existente no cumple el formato seguro; no se modificó.")
        values[name] = existing if existing is not None else secrets.token_urlsafe(64)
        if existing is None:
            missing.append(name)
    if len(set(values.values())) != len(values):
        raise ValueError("Los secretos existentes deben ser independientes; no se modificaron.")

    redis_password = values["redis_password"]
    derived = {
        "redis_url": f"redis://:{quote(redis_password, safe='')}@redis:6379/0",
        "redis_config": (
            "bind 0.0.0.0\nprotected-mode yes\nport 6379\n"
            f"requirepass {redis_password}\n"
            "dir /data\nappendonly yes\nsave \"\"\n"
            "maxmemory 128mb\nmaxmemory-policy noeviction"
        ),
    }
    # Validate all existing derived values before writing any new credential.
    for name, expected in derived.items():
        existing = read_existing(directory / name)
        if existing is not None and existing != expected:
            raise ValueError(f"{name} no coincide con redis_password; no se sobrescribió.")
        if existing is None:
            missing.append(name)
    values.update(derived)
    for name in missing:
        write_new(directory / name, values[name])
    for name in values:
        path = directory / name
        if os.name == "nt":
            # Replace any explicit permissions retained by an older existing file.
            subprocess.run(["icacls", str(path), "/reset"], check=True, capture_output=True, text=True)
        else:
            path.chmod(0o444)
    return directory, len(missing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("secrets"))
    args = parser.parse_args()
    try:
        directory, created = bootstrap(args.directory)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        # Do not include subprocess output or file contents in errors.
        message = str(error) if isinstance(error, (ValueError, RuntimeError)) else "No se pudieron preparar los archivos o sus permisos."
        print(f"Error: {message}", file=sys.stderr)
        return 1
    print(f"Secretos preparados en {directory}: {created} creados. No se mostraron valores ni se rotaron credenciales existentes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
