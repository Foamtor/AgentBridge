"""Operator model configuration service with encrypted-at-rest API credentials."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_TOOL_PROBE_NAME = "agentbridge_connection_probe"
_TOOL_CALL_CAPABILITY = "tool_calling_v1"
_TOOL_PROBE = {
    "type": "function",
    "function": {
        "name": _TOOL_PROBE_NAME,
        "description": "Confirm that the model can select a tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "confirmation": {
                    "type": "string",
                    "description": "Return exactly ready.",
                }
            },
            "required": ["confirmation"],
            "additionalProperties": False,
        },
    },
}


class ModelConfigError(ValueError):
    def __init__(self, code: str, *, reason: str | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.reason = reason


class _ToolCallTestError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _provider_failure_code(exc: Exception, *, phase: str) -> str:
    """Map SDK/provider failures to safe diagnostics; never include response bodies."""
    status_code = getattr(exc, "status_code", None)
    if status_code is None:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int) and 400 <= status_code <= 599:
        return f"{phase}_http_{status_code}"
    return "tool_call_request_failed" if phase == "tool_call" else "connection_failed"


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

    async def configure_encryption_key(self, key: str) -> None:
        """Activate the first operator key without supporting unsafe rotation."""
        if self._cipher is not None:
            raise ModelConfigError("model_config_encryption_key_already_configured")
        self._cipher = ModelCredentialCipher(key)
        await self.refresh_runtime()

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
            "last_test_status": record.get("last_test_status"),
            "last_tested_at": record.get("last_tested_at"),
            "last_test_latency_ms": record.get("last_test_latency_ms"),
            "last_test_error": record.get("last_test_error"),
            "last_test_capability": record.get("last_test_capability"),
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
        next_record.update({
            "last_test_status": None,
            "last_tested_at": None,
            "last_test_latency_ms": None,
            "last_test_error": None,
            "last_test_capability": None,
        })
        updated = await self._store.update(alias, next_record)
        assert updated is not None
        await self.refresh_runtime()
        return self.public(updated, runtime_ready=self.is_real_alias(alias))

    async def test_connection(self, alias: str) -> dict[str, Any]:
        record = await self._store.get(alias)
        if record is None:
            raise ModelConfigError("model_not_found")
        if not record["enabled"]:
            raise ModelConfigError("model_disabled")
        api_key = self._cipher_or_error().decrypt(record["api_key_ciphertext"])
        started = time.monotonic()
        phase = "connection"
        try:
            model = self._build_model(record, api_key)
            invoke = getattr(model, "ainvoke", None)
            if not callable(invoke):
                raise TypeError("model does not support async invocation")
            await asyncio.wait_for(invoke("Reply exactly: OK"), timeout=10)
            phase = "tool_call"
            bind_tools = getattr(model, "bind_tools", None)
            if not callable(bind_tools):
                raise _ToolCallTestError("tool_call_binding_unsupported")
            try:
                tool_model = bind_tools([_TOOL_PROBE])
            except Exception as exc:
                raise _ToolCallTestError("tool_call_binding_failed") from exc
            tool_invoke = getattr(tool_model, "ainvoke", None)
            if not callable(tool_invoke):
                raise _ToolCallTestError("tool_call_invocation_unsupported")
            response = await asyncio.wait_for(
                tool_invoke(
                    "Use the agentbridge_connection_probe function now. "
                    "Set confirmation to ready and provide no other answer."
                ),
                timeout=10,
            )
            tool_calls = getattr(response, "tool_calls", None)
            if not any(
                isinstance(call, dict) and call.get("name") == _TOOL_PROBE_NAME
                for call in (tool_calls if isinstance(tool_calls, list) else [])
            ):
                raise _ToolCallTestError("tool_call_response_missing")
        except asyncio.TimeoutError as exc:
            await self._store.record_test(
                alias,
                status="failed",
                latency_ms=10000,
                error="tool_call_timeout" if phase == "tool_call" else "connection_timeout",
                capability=None,
            )
            code = "model_tool_call_test_timeout" if phase == "tool_call" else "model_connection_test_timeout"
            raise ModelConfigError(code) from exc
        except _ToolCallTestError as exc:
            await self._store.record_test(
                alias,
                status="failed",
                latency_ms=max(1, round((time.monotonic() - started) * 1000)),
                error=exc.code,
                capability=None,
            )
            raise ModelConfigError("model_tool_call_test_failed") from exc
        except Exception as exc:
            tool_call_failed = phase == "tool_call"
            failure_code = _provider_failure_code(
                exc,
                phase="tool_call" if tool_call_failed else "connection",
            )
            await self._store.record_test(
                alias,
                status="failed",
                latency_ms=max(1, round((time.monotonic() - started) * 1000)),
                error=failure_code,
                capability=None,
            )
            raise ModelConfigError(
                "model_tool_call_test_failed"
                if tool_call_failed
                else "model_connection_test_failed",
                reason=failure_code,
            ) from exc
        latency_ms = max(1, round((time.monotonic() - started) * 1000))
        await self._store.record_test(
            alias,
            status="success",
            latency_ms=latency_ms,
            error=None,
            capability=_TOOL_CALL_CAPABILITY,
        )
        return {
            "ok": True,
            "latency_ms": latency_ms,
            "model_name": record["model_name"],
            "tool_calling": True,
        }

    async def delete(self, alias: str) -> bool:
        deleted = await self._store.delete(alias)
        if deleted:
            await self.refresh_runtime()
        return deleted
