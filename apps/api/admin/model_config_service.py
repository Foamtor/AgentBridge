"""Operator model configuration service with encrypted-at-rest API credentials."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class ModelConfigError(ValueError):
    pass


class ModelCredentialCipher:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise ModelConfigError("model_config_encryption_key_invalid") from exc

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError) as exc:
            raise ModelConfigError("model_config_decryption_failed") from exc


class ModelConfigService:
    def __init__(
        self,
        store: Any,
        *,
        encryption_key: str,
        build_model: Callable[[dict[str, Any], str], Any],
        replace_gateway_models: Callable[[dict[str, Any]], None],
        base_models: dict[str, Any],
        base_real_aliases: set[str],
    ) -> None:
        self._store = store
        self._cipher = ModelCredentialCipher(encryption_key) if encryption_key.strip() else None
        self._build_model = build_model
        self._replace_gateway_models = replace_gateway_models
        self._base_models = dict(base_models)
        self._base_real_aliases = set(base_real_aliases)
        self._real_aliases = set(base_real_aliases)

    @property
    def encryption_ready(self) -> bool:
        return self._cipher is not None

    def is_real_alias(self, alias: str | None) -> bool:
        return bool(alias and alias in self._real_aliases)

    @property
    def has_real_model(self) -> bool:
        return bool(self._real_aliases)

    async def refresh_runtime(self) -> None:
        models = dict(self._base_models)
        real_aliases = set(self._base_real_aliases)
        for record in await self._store.list():
            if not record["enabled"]:
                continue
            if self._cipher is None:
                logger.warning("model config %s not loaded: encryption key unavailable", record["alias"])
                continue
            try:
                models[record["alias"]] = self._build_model(
                    record, self._cipher.decrypt(record["api_key_ciphertext"])
                )
            except ModelConfigError:
                logger.warning("model config %s not loaded: credential cannot be decrypted", record["alias"])
                continue
            real_aliases.add(record["alias"])
        self._replace_gateway_models(models)
        self._real_aliases = real_aliases

    def _cipher_or_error(self) -> ModelCredentialCipher:
        if self._cipher is None:
            raise ModelConfigError("model_config_encryption_key_required")
        return self._cipher

    @staticmethod
    def public(record: dict[str, Any], *, runtime_ready: bool) -> dict[str, Any]:
        return {
            "alias": record["alias"],
            "provider": record["provider"],
            "api_base": record["api_base"],
            "model_name": record["model_name"],
            "temperature": record["temperature"],
            "enabled": record["enabled"],
            "key_configured": bool(record.get("api_key_ciphertext")),
            "runtime_ready": runtime_ready,
            "managed": True,
            "created_at": record.get("created_at"),
            "updated_at": record.get("updated_at"),
        }

    async def list_public(self) -> list[dict[str, Any]]:
        return [
            self.public(record, runtime_ready=self.is_real_alias(record["alias"]))
            for record in await self._store.list()
        ]

    def selectable_base(self, *, default_model: str) -> list[dict[str, Any]]:
        if not self._base_real_aliases:
            return []
        return [
            {"alias": alias, "model_name": default_model, "kind": "real"}
            for alias in sorted(self._base_real_aliases)
        ]

    async def create(self, payload: dict[str, Any], *, actor: str) -> dict[str, Any]:
        cipher = self._cipher_or_error()
        record = {
            **payload,
            "api_key_ciphertext": cipher.encrypt(payload["api_key"]),
            "created_by": actor,
        }
        created = await self._store.create(record)
        if created is None:
            raise ModelConfigError("model_alias_exists")
        await self.refresh_runtime()
        return self.public(created, runtime_ready=self.is_real_alias(created["alias"]))

    async def update(self, alias: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = await self._store.get(alias)
        if current is None:
            raise ModelConfigError("model_not_found")
        next_record = {**current, **payload}
        api_key = payload.get("api_key")
        if api_key:
            next_record["api_key_ciphertext"] = self._cipher_or_error().encrypt(api_key)
        updated = await self._store.update(alias, next_record)
        assert updated is not None
        await self.refresh_runtime()
        return self.public(updated, runtime_ready=self.is_real_alias(alias))

    async def delete(self, alias: str) -> bool:
        deleted = await self._store.delete(alias)
        if deleted:
            await self.refresh_runtime()
        return deleted
