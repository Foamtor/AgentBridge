"""Small deployment-file helper for the operator-owned model key."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

_KEY_LINE = re.compile(r"^\s*MODEL_CONFIG_ENCRYPTION_KEY\s*=.*$", re.MULTILINE)


class ModelConfigEnvFileError(RuntimeError):
    pass


def generate_key() -> str:
    return Fernet.generate_key().decode("ascii")


def validate_key(value: str) -> str:
    try:
        Fernet(value.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise ModelConfigEnvFileError("model_config_encryption_key_invalid") from exc
    return value


def write_key(path: str | Path, value: str) -> None:
    """Replace only the model key and atomically replace the deployment file."""
    key = validate_key(value)
    target = Path(path)
    try:
        original = target.read_text(encoding="utf-8") if target.exists() else ""
        replacement = f"MODEL_CONFIG_ENCRYPTION_KEY={key}"
        if _KEY_LINE.search(original):
            content = _KEY_LINE.sub(replacement, original, count=1)
        else:
            content = original.rstrip("\r\n")
            content = f"{content}\n{replacement}\n" if content else f"{replacement}\n"
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    except OSError as exc:
        raise ModelConfigEnvFileError("model_config_env_file_unwritable") from exc
