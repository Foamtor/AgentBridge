# Authentik (optional OIDC mode)

The default Compose stack uses `AUTH_MODE=local` and does not require Authentik. Use this profile only when connecting AgentBridge to an existing OIDC identity provider.

## Start (optional)

```bash
docker compose --profile auth up -d
```

Then set in `.env`:

```text
AUTH_MODE=oidc
AUTH_REQUIRED=true
OIDC_ISSUER=http://localhost:9000/application/o/<app>/
OIDC_AUDIENCE=<client-id>
```

Configure an OAuth2/OIDC provider in Authentik UI and point the React debug console
at the issuer / client id. Full production hardening is out of scope for template smoke.
