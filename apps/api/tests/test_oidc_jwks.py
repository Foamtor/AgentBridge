"""OIDC discovery/JWKS middleware contract tests."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from auth import oidc
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwt
from jose.utils import base64url_encode


def _base64url_int(value: int) -> str:
    width = max(1, (value.bit_length() + 7) // 8)
    return base64url_encode(value.to_bytes(width, "big")).decode("ascii")


@contextmanager
def _oidc_server(jwks: dict[str, Any]) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            issuer = f"http://{self.server.server_address[0]}:{self.server.server_address[1]}"
            if self.path == "/.well-known/openid-configuration":
                body = {"issuer": issuer, "jwks_uri": f"{issuer}/jwks/"}
                self._json(body)
                return
            if self.path == "/jwks/":
                self._json(jwks)
                return
            self.send_response(404)
            self.end_headers()

        def _json(self, body: dict[str, Any]) -> None:
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, _format: str, *_args: object) -> None:
            return None

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _rsa_material() -> tuple[bytes, dict[str, Any]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    numbers = private_key.public_key().public_numbers()
    return private_pem, {
        "keys": [
            {
                "kty": "RSA",
                "kid": "p2a-jwks-key",
                "use": "sig",
                "alg": "RS256",
                "n": _base64url_int(numbers.n),
                "e": _base64url_int(numbers.e),
            }
        ]
    }


def test_oidc_jwks_middleware_validates_issuer_audience_and_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_pem, jwks = _rsa_material()
    with _oidc_server(jwks) as issuer:
        oidc._openid_config.cache_clear()
        oidc._jwks.cache_clear()
        monkeypatch.setenv("AUTH_REQUIRED", "true")
        monkeypatch.setenv("AUTH_DEV_STUB", "false")
        monkeypatch.setenv("OIDC_ISSUER", issuer)
        monkeypatch.setenv("OIDC_AUDIENCE", "agentbridge-api")
        monkeypatch.delenv("OIDC_JWT_SECRET", raising=False)
        monkeypatch.setenv("AGENTBRIDGE_FAKE_RUNTIME", "1")
        token = jwt.encode(
            {
                "sub": "p2a-oidc-user",
                "tenant_id": "p2a-tenant",
                "iss": issuer,
                "aud": "agentbridge-api",
            },
            private_pem,
            algorithm="RS256",
            headers={"kid": "p2a-jwks-key"},
        )
        from testing.app_factory import create_test_app

        app = create_test_app()
        with TestClient(app) as client:
            response = client.post(
                "/chat/stream",
                headers={"Authorization": f"Bearer {token}"},
                json={"query": "hi", "thread_id": "p2a-jwks", "route": "echo"},
            )

    assert response.status_code == 200
